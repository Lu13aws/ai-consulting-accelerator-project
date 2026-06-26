"""
Consulting API — FastAPI application.

Phase 1: Framework Q&A (RAG with citations) and BA/RE/PM artifact structuring,
scoped to app_name="consulting".
"""

import logging
import os

from aiplatform.settings import settings
from aiplatform.storage.models import Base
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine as _create_sync_engine

from apps.consulting_api.api.consulting_routes import router as consulting_router
from apps.consulting_api.api.engagement_routes import router as engagement_router
from apps.consulting_api.api.routes import router

logger = logging.getLogger(__name__)


def _bootstrap_schema() -> None:
    """Ensure documents/chunks/embeddings exist (idempotent CREATE TABLE IF NOT EXISTS).

    Best-effort: a missing/unreachable DB must not crash app import (e.g. in tests or
    during a transient outage). Real requests will surface DB errors per-request.
    """
    try:
        engine = _create_sync_engine(settings.alembic_database_url)
        Base.metadata.create_all(engine)
        engine.dispose()
    except Exception as exc:  # noqa: BLE001 — never fail import on DB bootstrap
        logger.warning("Schema bootstrap skipped (DB unreachable): %s", exc)

    # Engagement tables live in their own (confidential) DB — create them on its engine.
    try:
        from apps.consulting_api.storage.engagement_db import ENGAGEMENT_DB_URL
        from apps.consulting_api.storage.engagement_models import Base as EngagementBase

        eng_engine = _create_sync_engine(ENGAGEMENT_DB_URL.replace("+asyncpg", ""))
        EngagementBase.metadata.create_all(eng_engine)
        # create_all does not add columns to an existing table — apply additive changes.
        from sqlalchemy import text as _sql_text

        with eng_engine.begin() as conn:
            conn.execute(
                _sql_text(
                    "ALTER TABLE consulting_engagements ADD COLUMN IF NOT EXISTS assessment TEXT"
                )
            )
            conn.execute(
                _sql_text(
                    "ALTER TABLE consulting_engagements "
                    "ADD COLUMN IF NOT EXISTS extras JSONB NOT NULL DEFAULT '{}'::jsonb"
                )
            )
            conn.execute(
                _sql_text(
                    "ALTER TABLE consulting_engagements "
                    "ADD COLUMN IF NOT EXISTS turns JSONB NOT NULL DEFAULT '[]'::jsonb"
                )
            )
            conn.execute(
                _sql_text(
                    "ALTER TABLE consulting_engagements "
                    "ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false"
                )
            )
        eng_engine.dispose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Engagement schema bootstrap skipped: %s", exc)


_bootstrap_schema()

app = FastAPI(
    title="AI Consulting Accelerator",
    description="Framework Q&A and BA/RE/PM artifact structuring (grounded in cited frameworks).",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

_PRODUCTION_ORIGINS = [
    "https://consulting.bridging-data.com",
    "http://localhost:3000",
    "http://localhost:3001",
]

# Extra production origins (e.g. the CloudFront URL) can be added at deploy time
# via CONSULTING_CORS_ORIGINS (comma-separated) without a code change.
_extra_origins = [o.strip() for o in os.environ.get("CONSULTING_CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [*_PRODUCTION_ORIGINS, *_extra_origins],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(consulting_router, prefix="/api/v1/consulting")
app.include_router(engagement_router, prefix="/api/v1/consulting/engagements")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "consulting"}
