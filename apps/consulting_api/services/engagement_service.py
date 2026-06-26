"""
Engagement orchestration (Phase 2 — Interview/Discovery Mode).

A light, stateful 2-round flow over the existing single-shot skills:

  Round 1 (create):  initial input → Initial Analysis + Hypotheses + Open Questions
  Round 2 (answer):  + the user's answers → Refined Analysis + classified Requirements

Persistence uses the dedicated engagement session (confidential DB); the skill calls
reuse ConsultingService against the RAG/vector session.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.consulting_api.api.schemas import StructureRequest
from apps.consulting_api.services.consulting_service import ConsultingService, _detect_language
from apps.consulting_api.storage.engagement_models import Engagement


def _title(text: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else "Engagement"
    return (first[:97] + "…") if len(first) > 98 else first


class EngagementService:
    def __init__(self, engagement_session: AsyncSession, rag_session: AsyncSession) -> None:
        self._eng = engagement_session
        self._consulting = ConsultingService(rag_session)

    async def _run(self, skill: str, inputs: dict[str, str]) -> str:
        resp = await self._consulting.structure_artifact(
            StructureRequest(skill=skill, inputs=inputs)
        )
        return resp.artifact

    async def create(self, initial_input: str) -> Engagement:
        """Round 1: kick off discovery (analysis + hypotheses + open questions)."""
        analysis = await self._run(
            "consulting.structure-business-problem", {"problem_description": initial_input}
        )
        hypotheses = await self._run(
            "consulting.generate-hypotheses", {"context": initial_input}
        )
        open_questions = await self._run(
            "consulting.open-questions", {"context": initial_input}
        )
        engagement = Engagement(
            title=_title(initial_input),
            status="awaiting_answers",
            language=_detect_language(initial_input),
            initial_input=initial_input,
            initial_analysis=analysis,
            hypotheses=hypotheses,
            open_questions=open_questions,
        )
        self._eng.add(engagement)
        await self._eng.flush()
        return engagement

    async def answer(self, engagement_id: UUID, answers: str) -> Engagement:
        """Round 2: incorporate the answers into a refined analysis + requirements."""
        engagement = await self._eng.get(Engagement, engagement_id)
        if engagement is None:
            raise ValueError(f"Engagement {engagement_id} not found.")

        enriched = (
            f"{engagement.initial_input}\n\n"
            f"Open questions:\n{engagement.open_questions or ''}\n\n"
            f"Answers to the open questions:\n{answers}"
        )
        refined = await self._run(
            "consulting.structure-business-problem", {"problem_description": enriched}
        )
        requirements = await self._run(
            "consulting.structure-requirements", {"requirements": enriched}
        )

        engagement.answers = answers
        engagement.refined_analysis = refined
        engagement.requirements = requirements
        engagement.status = "refined"
        await self._eng.flush()
        return engagement

    async def get(self, engagement_id: UUID) -> Engagement | None:
        return await self._eng.get(Engagement, engagement_id)

    async def list_recent(self, limit: int = 50) -> list[Engagement]:
        stmt = select(Engagement).order_by(Engagement.created_at.desc()).limit(limit)
        return list((await self._eng.execute(stmt)).scalars().all())
