"""
UI-facing routes under /api/v1/consulting/*.

Thin wrappers that delegate to ConsultingService — they give the demo UI clean,
purpose-specific endpoints while the underlying logic stays in the generic
query()/structure_artifact() service. Each structuring route targets a named skill.
"""

from aiplatform.retrieval.embedder import CostLimitExceeded
from aiplatform.storage.database import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.consulting_api.api.schemas import (
    ConsultingQueryRequest,
    ProblemRequest,
    QueryRequest,
    QueryResponse,
    RequirementsRequest,
    RoadmapRequest,
    RunRequest,
    SkillsResponse,
    StakeholdersRequest,
    StructureRequest,
    StructureResponse,
)
from apps.consulting_api.services.consulting_service import ConsultingService

router = APIRouter()


async def _structure(session: AsyncSession, skill: str, inputs: dict[str, str]) -> StructureResponse:
    try:
        return await ConsultingService(session).structure_artifact(
            StructureRequest(skill=skill, inputs=inputs)
        )
    except CostLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/query", response_model=QueryResponse)
async def query(
    request: ConsultingQueryRequest,
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    """Framework Q&A (RAG with citations)."""
    try:
        return await ConsultingService(session).query(
            QueryRequest(question=request.question, top_k=request.top_k)
        )
    except CostLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/structure/problem", response_model=StructureResponse)
async def structure_problem(
    request: ProblemRequest,
    session: AsyncSession = Depends(get_session),
) -> StructureResponse:
    inputs = {"problem_description": request.problem_description}
    if request.additional_context:
        inputs["additional_context"] = request.additional_context
    return await _structure(session, "consulting.structure-business-problem", inputs)


@router.post("/structure/requirements", response_model=StructureResponse)
async def structure_requirements(
    request: RequirementsRequest,
    session: AsyncSession = Depends(get_session),
) -> StructureResponse:
    inputs = {"requirements": request.requirements}
    if request.context:
        inputs["context"] = request.context
    return await _structure(session, "consulting.structure-requirements", inputs)


@router.post("/structure/roadmap", response_model=StructureResponse)
async def structure_roadmap(
    request: RoadmapRequest,
    session: AsyncSession = Depends(get_session),
) -> StructureResponse:
    inputs = {"vision": request.vision, "goals": request.goals}
    for field in ("known_scope", "constraints", "target_users"):
        value = getattr(request, field)
        if value:
            inputs[field] = value
    return await _structure(session, "consulting.structure-roadmap", inputs)


@router.post("/stakeholders", response_model=StructureResponse)
async def stakeholders(
    request: StakeholdersRequest,
    session: AsyncSession = Depends(get_session),
) -> StructureResponse:
    # The UI offers one textarea; the skill needs project + stakeholders, so the
    # single description feeds both (the model extracts stakeholders from it).
    inputs = {"project_description": request.input, "known_stakeholders": request.input}
    return await _structure(session, "consulting.analyze-stakeholders", inputs)


@router.get("/skills", response_model=SkillsResponse)
async def list_skills(session: AsyncSession = Depends(get_session)) -> SkillsResponse:
    """List the registered skills (with their layer) for the UI."""
    return ConsultingService(session).list_skills()


@router.post("/run", response_model=StructureResponse)
async def run_skill(
    request: RunRequest,
    session: AsyncSession = Depends(get_session),
) -> StructureResponse:
    """Generic skill invocation (used by the Discovery tools)."""
    return await _structure(session, request.skill, request.inputs)
