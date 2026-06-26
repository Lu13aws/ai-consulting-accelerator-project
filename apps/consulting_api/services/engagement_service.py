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
            status="in_discovery",
            language=_detect_language(initial_input),
            initial_input=initial_input,
            initial_analysis=analysis,
            hypotheses=hypotheses,
            open_questions=open_questions,
            turns=[],
        )
        self._eng.add(engagement)
        await self._eng.flush()
        return engagement

    @staticmethod
    def _current_open_questions(engagement: Engagement) -> str:
        """The questions awaiting an answer: the last round's, or the kickoff's."""
        if engagement.turns:
            return engagement.turns[-1].get("open_questions") or ""
        return engagement.open_questions or ""

    @staticmethod
    def _all_answers(engagement: Engagement) -> str:
        return "\n\n".join(t.get("answers", "") for t in (engagement.turns or []) if t.get("answers"))

    async def answer(self, engagement_id: UUID, answers: str) -> Engagement:
        """One discovery round: refine (delta) and generate the NEXT, deeper questions."""
        engagement = await self._eng.get(Engagement, engagement_id)
        if engagement is None:
            raise ValueError(f"Engagement {engagement_id} not found.")

        prev_analysis = engagement.refined_analysis or engagement.initial_analysis or ""
        current_questions = self._current_open_questions(engagement)

        # Delta-aware refinement: show what THIS round's answers changed.
        findings = await self._run(
            "consulting.refine-analysis",
            {
                "initial_analysis": prev_analysis,
                "open_questions": current_questions,
                "answers": answers,
                "initial_input": engagement.initial_input,
            },
        )
        # Next, deeper questions — given the updated picture and what's already covered.
        next_questions = await self._run(
            "consulting.open-questions",
            {
                "context": (
                    f"{engagement.initial_input}\n\nCurrent findings:\n{findings}\n\n"
                    f"Already covered by previous answers:\n{self._all_answers(engagement)}\n{answers}"
                )
            },
        )

        turn = {"answers": answers, "findings": findings, "open_questions": next_questions}
        engagement.turns = [*(engagement.turns or []), turn]
        engagement.refined_analysis = findings  # latest picture
        engagement.status = "in_discovery"
        await self._eng.flush()
        return engagement

    async def conclude(self, engagement_id: UUID) -> Engagement:
        """Synthesize the engagement: classified requirements + consultant assessment."""
        engagement = await self._eng.get(Engagement, engagement_id)
        if engagement is None:
            raise ValueError(f"Engagement {engagement_id} not found.")

        analysis = engagement.refined_analysis or engagement.initial_analysis or ""
        context = (
            f"{engagement.initial_input}\n\nAnalysis:\n{analysis}\n\n"
            f"Discovery answers:\n{self._all_answers(engagement)}"
        )
        requirements = await self._run(
            "consulting.structure-requirements", {"requirements": context}
        )
        assessment = await self._run(
            "consulting.consultant-assessment", {"context": context}
        )

        engagement.requirements = requirements
        engagement.assessment = assessment
        engagement.status = "concluded"
        await self._eng.flush()
        return engagement

    # Downstream tools that can be generated from an engagement's context.
    DOWNSTREAM_TOOLS = ("roadmap", "stakeholders")

    async def generate(self, engagement_id: UUID, tool: str) -> Engagement:
        """Generate a downstream artifact (roadmap / stakeholders) from the engagement
        context and attach it under `extras[tool]`."""
        if tool not in self.DOWNSTREAM_TOOLS:
            raise ValueError(
                f"Unknown tool '{tool}'. Available: {', '.join(self.DOWNSTREAM_TOOLS)}."
            )
        engagement = await self._eng.get(Engagement, engagement_id)
        if engagement is None:
            raise ValueError(f"Engagement {engagement_id} not found.")

        analysis = engagement.refined_analysis or engagement.initial_analysis or ""
        if tool == "roadmap":
            artifact = await self._run(
                "consulting.structure-roadmap",
                {
                    "vision": engagement.initial_input,
                    "goals": analysis,
                    "known_scope": engagement.requirements or "",
                },
            )
        else:  # stakeholders — single-field skill input mapped to both required fields
            context = f"{engagement.initial_input}\n\n{analysis}"
            artifact = await self._run(
                "consulting.analyze-stakeholders",
                {"project_description": context, "known_stakeholders": context},
            )

        # Reassign (not in-place mutate) so SQLAlchemy tracks the JSONB change.
        engagement.extras = {**(engagement.extras or {}), tool: artifact}
        await self._eng.flush()
        return engagement

    async def get(self, engagement_id: UUID) -> Engagement | None:
        return await self._eng.get(Engagement, engagement_id)

    async def list_recent(self, limit: int = 50) -> list[Engagement]:
        stmt = select(Engagement).order_by(Engagement.created_at.desc()).limit(limit)
        return list((await self._eng.execute(stmt)).scalars().all())
