"""
ORM model for consulting engagements (Phase 2 — Interview/Discovery Mode).

A separate DeclarativeBase from aiplatform's models: engagement data is CONFIDENTIAL
and lives in its own database (see engagement_db.py), never the shared public schema.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Engagement(Base):
    """A multi-turn discovery session: initial situation → questions → refined analysis."""

    __tablename__ = "consulting_engagements"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_discovery")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    # Lifecycle flag — separate from the discovery `status`; archived ones are hidden by default.
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    initial_input: Mapped[str] = mapped_column(Text, nullable=False)
    # Round 1 artifacts
    initial_analysis: Mapped[str | None] = mapped_column(Text)
    hypotheses: Mapped[str | None] = mapped_column(Text)
    open_questions: Mapped[str | None] = mapped_column(Text)
    # Round 2 input + artifacts
    answers: Mapped[str | None] = mapped_column(Text)
    refined_analysis: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str | None] = mapped_column(Text)
    # Downstream artifacts generated from this engagement's context, keyed by tool
    # (e.g. {"roadmap": "...", "stakeholders": "..."}). Scales without new columns.
    extras: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Discovery rounds timeline (append-only): each turn is
    # {"answers": str, "findings": str, "open_questions": str}.
    turns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
