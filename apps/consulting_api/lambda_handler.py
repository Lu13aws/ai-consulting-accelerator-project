"""
AWS Lambda entrypoint for the consulting API.

Default invocation: Mangum adapts API Gateway HTTP API events to the FastAPI app.

One-off maintenance invocations (payload {"action": ...}):
  {"action": "ingest"}         -> ingest the framework PDFs baked into the image (data/)
                                  into the production DB from inside the VPC. Run once after
                                  the first deploy to populate ai-platform-db-v2.
  {"action": "ingest_memory"}  -> ingest the Organizational Memory baked into the image
                                  (data/_memory/skills + data/_memory/projects) under
                                  app_name="skills" / "projects". Run once after the first deploy.
  {"action": "health"}         -> lightweight check that returns the app name.
"""

import asyncio
from pathlib import Path

from mangum import Mangum

from apps.consulting_api.main import app

_mangum = Mangum(app, lifespan="off")

# data/ is copied into the image at the Lambda task root (see Dockerfile.lambda).
_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"


async def _with_fresh_pool(coro):
    """Lambda reuses warm containers, so the module-global async engine's connection pool can be
    bound to a previous invocation's (now-closed) event loop — which breaks asyncpg on every DB op
    with "got Future attached to a different loop" / "another operation is in progress". Drop the
    stale pool first so new connections open in THIS loop (close=False avoids awaiting the old
    cross-loop connections). The coroutine is created by the caller but only awaited here, after
    the dispose."""
    from aiplatform.storage.database import engine

    await engine.dispose(close=False)
    return await coro


def _run_action(coro):
    """Run a maintenance coroutine WITHOUT poisoning the warm container for later API requests.
    asyncio.run() closes its loop and sets the thread's current loop to None; a subsequent Mangum
    (API) invocation on the same warm container then dies in asyncio.get_event_loop() with
    'no current event loop'. So run on a dedicated loop and leave a fresh current loop behind."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_with_fresh_pool(coro))
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def _ingest(index: int | None = None) -> dict:
    """Run the framework ingestion against the configured (production) DB.

    With `index` (0-based), ingest ONLY that one file — used to drive a per-file orchestration so a
    single oversized PDF that exceeds the 900s/3008MB Lambda limits is skipped (its invocation times
    out) instead of blocking every file after it in the alphabetical bulk run."""
    from scripts.ingest_frameworks import collect_files, run

    files = collect_files(_DATA_ROOT)
    total = len(files)
    if index is not None:
        files = files[index : index + 1]
    exit_code = _run_action(run(files, _DATA_ROOT, dry_run=False))
    return {"status": "ok" if exit_code == 0 else "partial", "files": len(files), "index": index, "total": total}


def _ingest_memory() -> dict:
    """Ingest the baked Organizational Memory (skills + projects) into the production DB."""
    from scripts.ingest_projects_local import run as run_projects
    from scripts.ingest_skills import collect_files as collect_skills
    from scripts.ingest_skills import run as run_skills

    skills_dir = _DATA_ROOT / "_memory" / "skills"
    projects_dir = _DATA_ROOT / "_memory" / "projects"
    skill_files = collect_skills(skills_dir)

    async def _run_all() -> tuple[int, int]:
        # Skills + projects share ONE event loop (a second asyncio.run() would rebind the engine).
        rc_s = await run_skills(skill_files, dry_run=False)
        rc_p = await run_projects(dry_run=False, from_dir=projects_dir)
        return rc_s, rc_p

    rc_skills, rc_projects = _run_action(_run_all())
    return {
        "status": "ok" if (rc_skills == 0 and rc_projects == 0) else "partial",
        "skills": len(skill_files),
        "projects": len(list(projects_dir.glob("*.md"))) if projects_dir.is_dir() else 0,
    }


def _status() -> dict:
    """Count indexed documents per app_name in the production DB (ingest progress check)."""
    from aiplatform.storage.database import get_async_session
    from aiplatform.storage.models import Document
    from sqlalchemy import func, select

    async def _q() -> dict:
        async with get_async_session() as session:
            rows = (
                await session.execute(select(Document.app_name, func.count()).group_by(Document.app_name))
            ).all()
        return dict(rows)

    return {"status": "ok", "documents_by_app": _run_action(_q())}


def handler(event, context):
    action = event.get("action") if isinstance(event, dict) else None
    if action == "ingest":
        return _ingest(event.get("index"))
    if action == "ingest_memory":
        return _ingest_memory()
    if action == "status":
        return _status()
    if action == "health":
        return {"status": "ok", "app": "consulting"}
    return _mangum(event, context)
