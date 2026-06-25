from aiplatform.retrieval.embedder import CostLimitExceeded
from aiplatform.storage.database import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.consulting_api.api.schemas import (
    QueryRequest,
    QueryResponse,
    SkillsResponse,
    SourcesResponse,
    StructureRequest,
    StructureResponse,
)
from apps.consulting_api.services.consulting_service import ConsultingService

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_frameworks(
    request: QueryRequest,
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    """Answer a question grounded in the indexed consulting frameworks, with citations."""
    try:
        return await ConsultingService(session).query(request)
    except CostLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/structure", response_model=StructureResponse)
async def structure_artifact(
    request: StructureRequest,
    session: AsyncSession = Depends(get_session),
) -> StructureResponse:
    """Invoke a named structuring skill on the user's input, grounded in frameworks."""
    try:
        return await ConsultingService(session).structure_artifact(request)
    except CostLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/skills", response_model=SkillsResponse)
async def list_skills(
    session: AsyncSession = Depends(get_session),
) -> SkillsResponse:
    """List the registered structuring skills and their input contracts."""
    return ConsultingService(session).list_skills()


@router.get("/sources", response_model=SourcesResponse)
async def list_sources(
    session: AsyncSession = Depends(get_session),
) -> SourcesResponse:
    """List the framework documents currently indexed for consulting."""
    return await ConsultingService(session).list_sources()
