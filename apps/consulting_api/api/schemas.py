"""Request/response models for the consulting API."""

from datetime import datetime

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class SourceReference(BaseModel):
    chunk_id: str
    source_uri: str
    score: float
    excerpt: str
    category: str | None = None
    language: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    model: str
    input_tokens: int
    output_tokens: int


class StructureRequest(BaseModel):
    skill: str = Field(..., description="Skill name, e.g. consulting.structure-business-problem")
    inputs: dict[str, str] = Field(
        ..., description="Skill-specific input fields (see GET /skills for required fields)"
    )
    top_k: int = Field(default=6, ge=0, le=20, description="Grounding chunks to retrieve (0 = none)")


class StructureResponse(BaseModel):
    skill: str
    version: str
    artifact: str
    sources: list[SourceReference]
    model: str
    input_tokens: int
    output_tokens: int


class SkillInfo(BaseModel):
    name: str
    version: str
    description: str
    layer: str
    required_fields: list[str]
    optional_fields: list[str]


class SkillsResponse(BaseModel):
    skill_count: int
    skills: list[SkillInfo]


class FrameworkDocument(BaseModel):
    source_uri: str
    title: str | None = None
    category: str | None = None
    language: str | None = None
    chunk_count: int


class SourcesResponse(BaseModel):
    document_count: int
    documents: list[FrameworkDocument]


# ── Consulting-namespaced request bodies (used by the /api/v1/consulting/* UI routes) ──

class ConsultingQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class ProblemRequest(BaseModel):
    problem_description: str = Field(..., min_length=1)
    additional_context: str | None = None


class RequirementsRequest(BaseModel):
    requirements: str = Field(..., min_length=1)
    context: str | None = None


class RoadmapRequest(BaseModel):
    vision: str = Field(..., min_length=1)
    goals: str = Field(..., min_length=1)
    known_scope: str | None = None
    constraints: str | None = None
    target_users: str | None = None


class StakeholdersRequest(BaseModel):
    # Single free-text field per the UI; mapped to the skill's two required inputs.
    input: str = Field(..., min_length=1)


class RunRequest(BaseModel):
    # Generic skill invocation used by the Discovery UI (single-input skills).
    skill: str = Field(..., description="Skill name, e.g. consulting.identify-risks")
    inputs: dict[str, str] = Field(..., description="Skill-specific input fields")


# ── Engagements (Phase 2 — Interview/Discovery Mode) ──────────────────────────

class EngagementCreateRequest(BaseModel):
    input: str = Field(..., min_length=1, description="The customer's situation / problem in free text")


class AnswerRequest(BaseModel):
    answers: str = Field(..., min_length=1, description="Free-text answers to the open questions")


class EngagementSummary(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime


class EngagementDetail(BaseModel):
    id: str
    title: str
    status: str
    language: str
    initial_input: str
    initial_analysis: str | None = None
    hypotheses: str | None = None
    open_questions: str | None = None
    answers: str | None = None
    refined_analysis: str | None = None
    requirements: str | None = None
    assessment: str | None = None
    extras: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class EngagementListResponse(BaseModel):
    count: int
    engagements: list[EngagementSummary]


class GenerateRequest(BaseModel):
    tool: str = Field(..., description="Downstream tool to generate: roadmap | stakeholders")
