"""
Dedicated async engine + session factory for confidential engagement data.

Reads CONSULTING_ENGAGEMENT_DB_URL. It defaults to the main DATABASE_URL for local
development, but in PRODUCTION it MUST point at an ISOLATED database — engagement data
(client discovery conversations) must never live in the shared public ai-platform-db-v2.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiplatform.settings import settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ENGAGEMENT_DB_URL = os.environ.get("CONSULTING_ENGAGEMENT_DB_URL", settings.database_url)

engagement_engine = create_async_engine(ENGAGEMENT_DB_URL, pool_size=5, max_overflow=10)

_SessionLocal = async_sessionmaker(
    bind=engagement_engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def engagement_session_ctx() -> AsyncGenerator[AsyncSession, None]:
    async with _SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_engagement_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an engagement-DB session per request."""
    async with _SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
