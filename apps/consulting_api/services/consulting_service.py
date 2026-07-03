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

    _KEYWORD_SYSTEM_PROMPT = """\
You extract SEARCH KEYWORDS for an internal engineering knowledge base.

Given a business problem and its analysis, output a SHORT, space-separated list of the TECHNICAL
solution keywords implied by it — technologies, architecture patterns and capabilities a senior
engineer would expect (e.g. RAG, retrieval augmented generation, vector search, embeddings,
semantic search, serverless, AWS Lambda, API, authentication, data pipeline, ETL, dashboard,
knowledge base). This bridges business language to the technical vocabulary the knowledge base
is written in.

Output ONLY the keywords on a single line — no prose, no bullets, no punctuation other than
spaces. If the problem implies no technical/software solution at all, output nothing."""

    async def derive_search_keywords(self, text: str) -> str:
        """Expand business-language context into a compact technical keyword bag for cross-source
        retrieval — closes the vocabulary gap between business problems and technical knowledge.
        Returns "" when no technical solution is implied (so retrieval honestly finds nothing)."""
        provider = get_llm_provider()
        response = await provider.complete(
            [Message(role="user", content=text)],
            system_prompt=self._KEYWORD_SYSTEM_PROMPT,
            temperature=0,
            max_tokens=80,
        )
        # One line, keywords only — guard against the model adding stray prose/punctuation.
        return " ".join(response.content.replace("\n", " ").split())[:400]

    async def retrieve_knowledge(
        self,
        queries: str | list[str],
        source_caps: list[tuple[str, int]],
        similarity_threshold: float | None = 0.25,
    ) -> list[SourceReference]:
        """Cross-source "Organizational Memory" retrieval — returns cited references, nothing
        generated (empty = nothing relevant found, no fabrication).

        Each query text is embedded ONCE and run as a single multi-`app_name` search
        (`app_name = ANY(...)`); results are then capped PER SOURCE (`source_caps`) so a dense
        source can't crowd out the others. Multiple query texts (e.g. a keyword bag + the raw
        business context) are merged by source, keeping the best score."""
        texts = [queries] if isinstance(queries, str) else [q for q in queries if q and q.strip()]
        if not texts or not source_caps:
            return []

        apps = [app for app, _ in source_caps]
        pool_k = max(8, sum(cap for _, cap in source_caps) * 5)
        embedder = Embedder(get_llm_provider())
        store = VectorStore(self._session)

        best: dict[str, tuple[SourceReference, str]] = {}  # source_uri -> (ref, app_name)
        for text in texts:
            vector = (await embedder.embed_query(text)).vector
            for r in await store.search(
                vector, top_k=pool_k, app_name=apps, similarity_threshold=similarity_threshold
            ):
                if r.source_uri not in best or r.score > best[r.source_uri][0].score:
                    best[r.source_uri] = (
                        SourceReference(
                            chunk_id=str(r.chunk_id),
                            source_uri=r.source_uri,
                            score=round(r.score, 4),
                            excerpt=r.content[:300].strip(),
                            category=r.metadata.get("category"),
                            language=r.metadata.get("language"),
                        ),
                        r.app_name or "",
                    )

        out: list[SourceReference] = []
        for app, cap in source_caps:  # per-source cap, sources kept in the given order
            bucket = [ref for ref, ref_app in best.values() if ref_app == app]
            out += sorted(bucket, key=lambda s: s.score, reverse=True)[:cap]
        return out

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
                layer=s.layer,
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

        # Detect the input language ONCE — used both to lock the output language
        # (deterministic, so the model can't drift to a third language) and to filter
        # grounding chunks to the same language.
        input_text = "\n".join(request.inputs.values())
        lang = _detect_language(input_text)
        lang_name = "German" if lang == "de" else "English"

        # 2. Retrieve grounding chunks (skill seed + the user's input text), filtered to
        #    the input language so a cross-lingual match can't flip the output language.
        results: list[SearchResult] = []
        if request.top_k > 0:
            embedder = Embedder(provider)
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

        # Skills that end with their own tailored disclaimer (owns_disclaimer) must not also be
        # told to append the shared DRAFT_DISCLAIMER — that produced a double disclaimer.
        closing = (
            "Produce the structured artifact now."
            if skill.owns_disclaimer
            else f"Produce the structured artifact now. End with this exact disclaimer line:\n{DRAFT_DISCLAIMER}"
        )
        user_content = (
            f"Write the entire response in {lang_name}.\n\n"
            + (f"Framework context:\n{context}\n\n" if context else "")
            + f"User input:\n{input_block}\n\n"
            + closing
        )

        # 4. Call the LLM
        llm_response = await provider.complete(
            [Message(role="user", content=user_content)],
            system_prompt=skill.system_prompt,
        )

        # 5. Guarantee a draft disclaimer is present (CLAUDE.md: always mark as draft). Skills that
        # define their own closing disclaimer are trusted to emit it — don't stack the shared one.
        artifact = llm_response.content
        if not skill.owns_disclaimer and DRAFT_DISCLAIMER not in artifact:
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
