"""Request/response models for the consulting API."""

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
