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


def _ingest() -> dict:
    """Run the framework ingestion against the configured (production) DB."""
    from scripts.ingest_frameworks import collect_files, run

    files = collect_files(_DATA_ROOT)
    exit_code = asyncio.run(_with_fresh_pool(run(files, _DATA_ROOT, dry_run=False)))
    return {"status": "ok" if exit_code == 0 else "partial", "files": len(files)}


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

    rc_skills, rc_projects = asyncio.run(_with_fresh_pool(_run_all()))
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

    return {"status": "ok", "documents_by_app": asyncio.run(_with_fresh_pool(_q()))}


def handler(event, context):
    action = event.get("action") if isinstance(event, dict) else None
    if action == "ingest":
        return _ingest()
    if action == "ingest_memory":
        return _ingest_memory()
    if action == "status":
        return _status()
    if action == "health":
        return {"status": "ok", "app": "consulting"}
    return _mangum(event, context)
