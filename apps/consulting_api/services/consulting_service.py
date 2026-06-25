"""
Consulting Framework Q&A and artifact structuring.

Q&A: embed question -> retrieve framework chunks -> grounded, cited answer.
Structuring: invoke a named skill -> retrieve grounding chunks -> structured,
cited Markdown artifact (see CLAUDE.md Memory Architecture + Prompt Design).

Scoped to app_name="consulting".
"""

from aiplatform.llm import Message, get_llm_provider
from aiplatform.retrieval.embedder import Embedder
from aiplatform.retrieval.vector_store import SearchResult, VectorStore
from aiplatform.storage.models import Chunk, Document
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.consulting_api.api.schemas import (
    FrameworkDocument,
    QueryRequest,
    QueryResponse,
    SkillInfo,
    SkillsResponse,
    SourceReference,
    SourcesResponse,
    StructureRequest,
    StructureResponse,
)
from apps.consulting_api.services.skills import DRAFT_DISCLAIMER, SKILLS, get_skill

APP_NAME = "consulting"

_DE_STOPWORDS = (" der ", " die ", " das ", " und ", " für ", " mit ", " nicht ",
                 " eine ", " einen ", " ich ", " wir ", " soll ", " muss ", " möchte ",
                 " sich ", " auf ", " von ", " den ", " dem ")
_EN_STOPWORDS = (" the ", " and ", " for ", " with ", " not ", " a ", " an ", " to ",
                 " should ", " must ", " we ", " users ", " of ", " on ", " want ")


def _detect_language(text: str) -> str:
    """Lightweight DE/EN detection for structuring inputs (umlauts + stopwords)."""
    t = f" {text.lower()} "
    if any(ch in t for ch in "äöüß"):
        return "de"
    de = sum(t.count(w) for w in _DE_STOPWORDS)
    en = sum(t.count(w) for w in _EN_STOPWORDS)
    return "de" if de > en else "en"


_CONSULTING_QA_SYSTEM_PROMPT = """\
You are a consulting assistant for Business Analysis, Requirements Engineering, \
Process and Project Management. You answer questions using ONLY the provided \
framework context (IREB, BABOK, BPMN, PMBOK, and related standards).

Rules:
- Ground every statement in the provided context. Cite the relevant sources \
inline using their [1], [2], … labels.
- If the context does not cover the question, say so plainly. Do not speculate, \
and do not draw on knowledge beyond the provided context.
- Do not claim expertise or certainty the context does not support.
- Answer in the SAME language as the question (the frameworks exist in both \
German and English).
- Be precise and practitioner-oriented. Use Markdown when it aids clarity.\
"""


class ConsultingService:
    def __init__(
        self,
        session: AsyncSession,
        app_name: str = APP_NAME,
        system_prompt: str = _CONSULTING_QA_SYSTEM_PROMPT,
        similarity_threshold: float | None = None,
    ) -> None:
        self._session = session
        self._app_name = app_name
        self._system_prompt = system_prompt
        self._similarity_threshold = similarity_threshold

    async def query(self, request: QueryRequest) -> QueryResponse:
        provider = get_llm_provider()
        embedder = Embedder(provider)

        # 1. Embed the question
        query_embedding = await embedder.embed_query(request.question)

        # 2. Retrieve relevant framework chunks (scoped to consulting)
        store = VectorStore(self._session)
        results = await store.search(
            query_embedding.vector,
            top_k=request.top_k,
            app_name=self._app_name,
            similarity_threshold=self._similarity_threshold,
        )

        # 3. No grounding context found — don't waste an LLM call or speculate
        if not results:
            return QueryResponse(
                answer=(
                    "I could not find relevant information in the indexed frameworks "
                    "to answer this question. Try rephrasing, or confirm that the "
                    "relevant framework has been ingested."
                ),
                sources=[],
                model=provider.default_chat_model,
                input_tokens=0,
                output_tokens=0,
            )

        # 4. Build numbered context blocks
        context_blocks = [
            f"[{i}] {r.content}\nSource: {r.source_uri}"
            for i, r in enumerate(results, start=1)
        ]
        context = "\n\n".join(context_blocks)

        # 5. Call the LLM
        messages = [
            Message(
                role="user",
                content=f"Context:\n{context}\n\nQuestion: {request.question}",
            ),
        ]
        llm_response = await provider.complete(messages, system_prompt=self._system_prompt)

        # 6. Source references for the UI (excerpt truncated to keep response lean)
        sources = [
            SourceReference(
                chunk_id=str(r.chunk_id),
                source_uri=r.source_uri,
                score=round(r.score, 4),
                excerpt=r.content[:300].strip(),
                category=r.metadata.get("category"),
                language=r.metadata.get("language"),
            )
            for r in results
        ]

        return QueryResponse(
            answer=llm_response.content,
            sources=sources,
            model=llm_response.model,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )

    async def list_sources(self) -> SourcesResponse:
        """List the framework documents currently indexed for consulting."""
        stmt = (
            select(
                Document.source_uri,
                Document.title,
                Document.doc_metadata,
                func.count(Chunk.id).label("chunk_count"),
            )
            .join(Chunk, Chunk.document_id == Document.id)
            .where(Document.app_name == self._app_name)
            .group_by(Document.id)
            .order_by(Document.source_uri)
        )
        rows = (await self._session.execute(stmt)).all()
        documents = [
            FrameworkDocument(
                source_uri=row.source_uri,
                title=row.title,
                category=(row.doc_metadata or {}).get("category"),
                language=(row.doc_metadata or {}).get("language"),
                chunk_count=row.chunk_count,
            )
            for row in rows
        ]
        return SourcesResponse(document_count=len(documents), documents=documents)

    def list_skills(self) -> SkillsResponse:
        """List the registered structuring skills (procedural memory)."""
        skills = [
            SkillInfo(
                name=s.name,
                version=s.version,
                description=s.description,
                required_fields=s.required_fields,
                optional_fields=s.optional_fields,
            )
            for s in sorted(SKILLS.values(), key=lambda s: s.name)
        ]
        return SkillsResponse(skill_count=len(skills), skills=skills)

    async def structure_artifact(self, request: StructureRequest) -> StructureResponse:
        """Invoke a named structuring skill on the user's input, grounded in frameworks."""
        skill = get_skill(request.skill)  # ValueError -> 422 if unknown

        # 1. Validate required input fields are present and non-empty
        missing = [
            f for f in skill.required_fields if not (request.inputs.get(f) or "").strip()
        ]
        if missing:
            raise ValueError(
                f"Skill '{skill.name}' requires non-empty fields: {', '.join(missing)}."
            )

        provider = get_llm_provider()

        # 2. Retrieve grounding chunks (skill seed + the user's input text).
        #    Filter to the input language (or language-agnostic chunks) so a
        #    cross-lingual match can't flip the generated artifact's language.
        results: list[SearchResult] = []
        if request.top_k > 0:
            embedder = Embedder(provider)
            input_text = "\n".join(request.inputs.values())
            seed_query = f"{skill.retrieval_seed}\n{input_text}"
            query_embedding = await embedder.embed_query(seed_query)
            store = VectorStore(self._session)
            candidates = await store.search(
                query_embedding.vector,
                top_k=request.top_k * 3,
                app_name=self._app_name,
                similarity_threshold=self._similarity_threshold,
            )
            # Filter by the detected language of each chunk's CONTENT (the stored
            # language metadata is often "unknown", so it can't be trusted here).
            lang = _detect_language(input_text)
            results = [
                r for r in candidates if _detect_language(r.content) == lang
            ][: request.top_k]

        # 3. Build numbered context + the user's structured input
        context = "\n\n".join(
            f"[{i}] {r.content}\nSource: {r.source_uri}"
            for i, r in enumerate(results, start=1)
        )
        input_block = "\n\n".join(
            f"## {field}\n{value}" for field, value in request.inputs.items() if value.strip()
        )

        user_content = (
            (f"Framework context:\n{context}\n\n" if context else "")
            + f"User input:\n{input_block}\n\n"
            + f"Produce the structured artifact now. End with this exact disclaimer line:\n{DRAFT_DISCLAIMER}"
        )

        # 4. Call the LLM
        llm_response = await provider.complete(
            [Message(role="user", content=user_content)],
            system_prompt=skill.system_prompt,
        )

        # 5. Guarantee the draft disclaimer is present (CLAUDE.md: always mark as draft)
        artifact = llm_response.content
        if DRAFT_DISCLAIMER not in artifact:
            artifact = f"{artifact.rstrip()}\n\n{DRAFT_DISCLAIMER}"

        sources = [
            SourceReference(
                chunk_id=str(r.chunk_id),
                source_uri=r.source_uri,
                score=round(r.score, 4),
                excerpt=r.content[:300].strip(),
                category=r.metadata.get("category"),
                language=r.metadata.get("language"),
            )
            for r in results
        ]

        return StructureResponse(
            skill=skill.name,
            version=skill.version,
            artifact=artifact,
            sources=sources,
            model=llm_response.model,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )
