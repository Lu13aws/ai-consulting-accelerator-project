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


def _ingest() -> dict:
    """Run the framework ingestion against the configured (production) DB."""
    from scripts.ingest_frameworks import collect_files, run

    files = collect_files(_DATA_ROOT)
    exit_code = asyncio.run(run(files, _DATA_ROOT, dry_run=False))
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
        # Run skills + projects in ONE event loop: the shared async DB engine binds to the
        # loop that first touches it, so a second asyncio.run() (a fresh loop) breaks asyncpg
        # with "got Future attached to a different loop" / "another operation is in progress".
        rc_s = await run_skills(skill_files, dry_run=False)
        rc_p = await run_projects(dry_run=False, from_dir=projects_dir)
        return rc_s, rc_p

    rc_skills, rc_projects = asyncio.run(_run_all())
    return {
        "status": "ok" if (rc_skills == 0 and rc_projects == 0) else "partial",
        "skills": len(skill_files),
        "projects": len(list(projects_dir.glob("*.md"))) if projects_dir.is_dir() else 0,
    }


def handler(event, context):
    action = event.get("action") if isinstance(event, dict) else None
    if action == "ingest":
        return _ingest()
    if action == "ingest_memory":
        return _ingest_memory()
    if action == "health":
        return {"status": "ok", "app": "consulting"}
    return _mangum(event, context)
