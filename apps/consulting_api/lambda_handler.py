"""
AWS Lambda entrypoint for the consulting API.

Default invocation: Mangum adapts API Gateway HTTP API events to the FastAPI app.

One-off maintenance invocations (payload {"action": ...}):
  {"action": "ingest"}  -> ingest the framework PDFs baked into the image (data/)
                           into the production DB from inside the VPC. Use this once
                           after the first deploy to populate ai-platform-db-v2.
  {"action": "health"}  -> lightweight check that returns the app name.
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


def handler(event, context):
    action = event.get("action") if isinstance(event, dict) else None
    if action == "ingest":
        return _ingest()
    if action == "health":
        return {"status": "ok", "app": "consulting"}
    return _mangum(event, context)
