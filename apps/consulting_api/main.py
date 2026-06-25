"""
Consulting API — FastAPI application.

Phase 1: Framework Q&A (RAG with citations) over the indexed frameworks,
scoped to app_name="consulting". Structuring routes (/structure) follow later.
"""

from aiplatform.settings import settings
from aiplatform.storage.models import Base
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine as _create_sync_engine

from apps.consulting_api.api.routes import router

# Ensure the documents/chunks/embeddings tables exist (idempotent — CREATE TABLE
# IF NOT EXISTS). Uses the psycopg2-compatible ALEMBIC_DATABASE_URL.
_sync_engine = _create_sync_engine(settings.alembic_database_url)
Base.metadata.create_all(_sync_engine)
_sync_engine.dispose()

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else _PRODUCTION_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "consulting"}
