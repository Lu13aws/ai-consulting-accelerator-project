"""
Engagement routes (Phase 2) under /api/v1/consulting/engagements.

A stateful, multi-round discovery flow. Persistence uses the dedicated engagement session
(confidential DB); skill calls reuse the RAG/vector session.
"""

import re
from uuid import UUID

from aiplatform.retrieval.embedder import CostLimitExceeded
from aiplatform.storage.database import get_session
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.consulting_api.api.schemas import (
    AnswerRequest,
    EngagementCreateRequest,
    EngagementDetail,
    EngagementListResponse,
    EngagementSummary,
    EngagementUpdateRequest,
    GenerateRequest,
)
from apps.consulting_api.services.engagement_service import EngagementService, build_report
from apps.consulting_api.services.report_render import render_docx, render_pdf
from apps.consulting_api.storage.engagement_db import get_engagement_session
from apps.consulting_api.storage.engagement_models import Engagement

router = APIRouter()


def _detail(e: Engagement) -> EngagementDetail:
    return EngagementDetail(
        id=str(e.id),
        title=e.title,
        status=e.status,
        archived=e.archived,
        language=e.language,
        initial_input=e.initial_input,
        initial_analysis=e.initial_analysis,
        hypotheses=e.hypotheses,
        open_questions=e.open_questions,
        answers=e.answers,
        refined_analysis=e.refined_analysis,
        requirements=e.requirements,
        assessment=e.assessment,
        extras=e.extras or {},
        turns=e.turns or [],
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


@router.post("", response_model=EngagementDetail)
async def create_engagement(
    request: EngagementCreateRequest,
    eng_session: AsyncSession = Depends(get_engagement_session),
    rag_session: AsyncSession = Depends(get_session),
) -> EngagementDetail:
    """Round 1: kick off discovery (analysis + hypotheses + open questions)."""
    service = EngagementService(eng_session, rag_session)
    try:
        return _detail(await service.create(request.input))
    except CostLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc


@router.get("", response_model=EngagementListResponse)
async def list_engagements(
    include_archived: bool = False,
    eng_session: AsyncSession = Depends(get_engagement_session),
) -> EngagementListResponse:
    service = EngagementService(eng_session, eng_session)  # list does not call skills
    items = await service.list_recent(include_archived=include_archived)
    return EngagementListResponse(
        count=len(items),
        engagements=[
            EngagementSummary(
                id=str(e.id),
                title=e.title,
                status=e.status,
                archived=e.archived,
                created_at=e.created_at,
            )
            for e in items
        ],
    )


@router.patch("/{engagement_id}", response_model=EngagementDetail)
async def update_engagement(
    engagement_id: UUID,
    request: EngagementUpdateRequest,
    eng_session: AsyncSession = Depends(get_engagement_session),
) -> EngagementDetail:
    """Rename and/or (un)archive an engagement."""
    service = EngagementService(eng_session, eng_session)
    try:
        return _detail(
            await service.update(engagement_id, title=request.title, archived=request.archived)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_engagement(
    engagement_id: UUID,
    eng_session: AsyncSession = Depends(get_engagement_session),
) -> Response:
    service = EngagementService(eng_session, eng_session)
    try:
        await service.delete(engagement_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{engagement_id}", response_model=EngagementDetail)
async def get_engagement(
    engagement_id: UUID,
    eng_session: AsyncSession = Depends(get_engagement_session),
) -> EngagementDetail:
    service = EngagementService(eng_session, eng_session)
    engagement = await service.get(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found.")
    return _detail(engagement)


@router.post("/{engagement_id}/answer", response_model=EngagementDetail)
async def answer_engagement(
    engagement_id: UUID,
    request: AnswerRequest,
    eng_session: AsyncSession = Depends(get_engagement_session),
    rag_session: AsyncSession = Depends(get_session),
) -> EngagementDetail:
    """Round 2: incorporate the answers into a refined analysis + requirements."""
    service = EngagementService(eng_session, rag_session)
    try:
        return _detail(await service.answer(engagement_id, request.answers))
    except CostLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{engagement_id}/conclude", response_model=EngagementDetail)
async def conclude_engagement(
    engagement_id: UUID,
    eng_session: AsyncSession = Depends(get_engagement_session),
    rag_session: AsyncSession = Depends(get_session),
) -> EngagementDetail:
    """Synthesize the engagement into classified requirements + a consultant assessment."""
    service = EngagementService(eng_session, rag_session)
    try:
        return _detail(await service.conclude(engagement_id))
    except CostLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{engagement_id}/generate", response_model=EngagementDetail)
async def generate_downstream(
    engagement_id: UUID,
    request: GenerateRequest,
    eng_session: AsyncSession = Depends(get_engagement_session),
    rag_session: AsyncSession = Depends(get_session),
) -> EngagementDetail:
    """Generate a downstream artifact (roadmap / stakeholders) from the engagement context."""
    service = EngagementService(eng_session, rag_session)
    try:
        return _detail(await service.generate(engagement_id, request.tool))
    except CostLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        # Unknown tool → 422; missing engagement → 404
        code = status.HTTP_404_NOT_FOUND if "not found" in str(exc) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc)) from exc


_REPORT_FORMATS = {
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@router.get("/{engagement_id}/report")
async def engagement_report(
    engagement_id: UUID,
    format: str = "md",
    eng_session: AsyncSession = Depends(get_engagement_session),
) -> Response:
    """Download the whole engagement as one report (Markdown, Word, or PDF)."""
    if format not in _REPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown format '{format}'. Available: {', '.join(_REPORT_FORMATS)}.",
        )
    engagement = await EngagementService(eng_session, eng_session).get(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found.")

    markdown = build_report(engagement)
    if format == "docx":
        content: bytes | str = render_docx(markdown)
    elif format == "pdf":
        content = render_pdf(markdown)
    else:
        content = markdown

    slug = re.sub(r"[^a-z0-9]+", "-", engagement.title.lower()).strip("-")[:50] or "engagement"
    return Response(
        content=content,
        media_type=_REPORT_FORMATS[format],
        headers={"Content-Disposition": f'attachment; filename="{slug}.{format}"'},
    )
