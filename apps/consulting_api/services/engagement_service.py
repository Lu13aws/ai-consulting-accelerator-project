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
from apps.consulting_api.services.patterns import load_pattern_catalog
from apps.consulting_api.services.skills import DRAFT_DISCLAIMER
from apps.consulting_api.storage.engagement_models import Engagement


def _title(text: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else "Engagement"
    return (first[:97] + "…") if len(first) > 98 else first


def build_report(engagement: Engagement) -> str:
    """Compose all of an engagement's artifacts into one Markdown report (pure)."""
    parts: list[str] = [
        f"# {engagement.title}",
        "_AI Consulting Accelerator — engagement report. AI-generated draft for human "
        "review; validate before use._",
        f"Status: {engagement.status}",
    ]

    def section(title: str, body: str | None) -> None:
        if body and body.strip():
            parts.append(f"## {title}\n\n{body.strip()}")

    section("Situation", engagement.initial_input)
    section("Initial Analysis", engagement.initial_analysis)
    section("Hypotheses", engagement.hypotheses)

    for i, turn in enumerate(engagement.turns or [], start=1):
        section(f"Round {i} — Answers", turn.get("answers"))
        section(f"Round {i} — Updated Findings", turn.get("findings"))

    # Legacy (pre-turns) engagements kept answers/refined in columns
    if not (engagement.turns or []):
        section("Answers", engagement.answers)
        section("Refined Analysis", engagement.refined_analysis)

    section("Requirements", engagement.requirements)
    section("Consultant's Assessment", engagement.assessment)

    extras = engagement.extras or {}
    section("Pattern Fit (to validate)", extras.get("patterns"))
    section("Relevant Existing Knowledge (references)", extras.get("knowledge"))
    section("Roadmap", extras.get("roadmap"))
    section("Stakeholder Analysis", extras.get("stakeholders"))

    return "\n\n".join(parts) + "\n"


class EngagementService:
    def __init__(self, engagement_session: AsyncSession, rag_session: AsyncSession) -> None:
        self._eng = engagement_session
        self._consulting = ConsultingService(rag_session)

    async def _run(self, skill: str, inputs: dict[str, str], *, top_k: int = 6) -> str:
        resp = await self._consulting.structure_artifact(
            StructureRequest(skill=skill, inputs=inputs, top_k=top_k)
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

    # Tools that can be generated from a (concluded) engagement's context.
    DOWNSTREAM_TOOLS = ("roadmap", "stakeholders", "patterns", "knowledge")

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
        elif tool == "patterns":
            # Pattern recognition: match the understanding against the curated catalog.
            # top_k=0 — the grounding is the catalog (passed in), not the framework RAG.
            context = f"{engagement.initial_input}\n\n{analysis}"
            artifact = await self._run(
                "consulting.match-patterns",
                {"context": context, "patterns": load_pattern_catalog()},
                top_k=0,
            )
        elif tool == "knowledge":
            # Organizational Memory: retrieve relevant EXISTING internal knowledge (skills)
            # and present it as cited references — never invented. Empty → say so (no LLM).
            # Two complementary signals, merged: (1) a focused technical keyword bag distilled
            # from the context (sharp query — best recall), and (2) the business context itself
            # (matches skills tagged with a business-language `description`). Neither alone
            # suffices: a long business problem embeds diffusely; an un-tagged skill needs the
            # keywords. Merge by source, keep the best score.
            context = f"{engagement.initial_input}\n\n{analysis}\n\n{engagement.requirements or ''}"
            keywords = await self._consulting.derive_search_keywords(context)
            queries = [q for q in (keywords, context) if q.strip()]

            # Retrieve PER SOURCE with a cap, so no single source dominates. Radar reports are
            # dense weekly snapshots that would otherwise crowd out the skills — cap at 1 (the
            # most relevant). Internal, non-confidential Organizational-Memory sources only;
            # more report types later = more (app_name, cap) entries.
            async def _top(source: str, cap: int) -> list:
                best: dict[str, object] = {}
                for q in queries:
                    for h in await self._consulting.retrieve_knowledge(
                        q, source, top_k=cap * 2, similarity_threshold=0.25
                    ):
                        if h.source_uri not in best or h.score > best[h.source_uri].score:
                            best[h.source_uri] = h
                return sorted(best.values(), key=lambda h: h.score, reverse=True)[:cap]

            # (app_name, cap) per Organizational-Memory source. Reports capped at 1 each (dense
            # weekly snapshots) so the how-to skills aren't crowded out; relevance gating keeps
            # an irrelevant source out entirely.
            hits = []
            for source, cap in (("skills", 4), ("projects", 1), ("radar", 1), ("competitor", 1), ("regulatory", 1)):
                hits += await _top(source, cap)
            if not hits:
                note = (
                    "Keine relevante interne Vorwissensbasis gefunden."
                    if engagement.language == "de"
                    else "No relevant prior internal knowledge found."
                )
                artifact = (
                    f"## Relevant Existing Knowledge (references — validate)\n\n{note}\n\n{DRAFT_DISCLAIMER}"
                )
            else:
                block = "\n\n".join(
                    f"[{i}] {h.source_uri}\n{h.excerpt}" for i, h in enumerate(hits, 1)
                )
                artifact = await self._run(
                    "consulting.relevant-knowledge",
                    {"context": context, "knowledge": block},
                    top_k=0,
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

    async def update(
        self, engagement_id: UUID, *, title: str | None = None, archived: bool | None = None
    ) -> Engagement:
        """Rename and/or (un)archive an engagement."""
        engagement = await self._eng.get(Engagement, engagement_id)
        if engagement is None:
            raise ValueError(f"Engagement {engagement_id} not found.")
        if title is not None:
            engagement.title = title.strip()[:200]
        if archived is not None:
            engagement.archived = archived
        await self._eng.flush()
        return engagement

    async def delete(self, engagement_id: UUID) -> None:
        engagement = await self._eng.get(Engagement, engagement_id)
        if engagement is None:
            raise ValueError(f"Engagement {engagement_id} not found.")
        await self._eng.delete(engagement)
        await self._eng.flush()

    async def list_recent(self, limit: int = 50, include_archived: bool = False) -> list[Engagement]:
        stmt = select(Engagement)
        if not include_archived:
            stmt = stmt.where(Engagement.archived.is_(False))
        stmt = stmt.order_by(Engagement.created_at.desc()).limit(limit)
        return list((await self._eng.execute(stmt)).scalars().all())
