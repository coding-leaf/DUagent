from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class CourseCatalogCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class CourseCatalogItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str
    knowledge_status: str
    material_count: int
    last_ingestion_task_id: Optional[str] = None
    last_ingestion_status: Optional[str] = None
    chunk_count: int = 0
    last_error: Optional[str] = None
    created_at: str


class CourseCatalogMaterialCreateRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    source_type: str = Field(..., min_length=1, max_length=30)
    storage_uri: Optional[str] = None


class CourseCatalogMaterialItem(BaseModel):
    id: str
    catalog_id: str
    filename: str
    source_type: str
    file_size: int = 0
    status: str
    chunk_count: int = 0
    last_error: Optional[str] = None
    ingested_at: Optional[str] = None
    created_at: str


class CourseCatalogIngestionAccepted(BaseModel):
    task_id: str
    catalog_id: str
    status: str


class CourseOfferingCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    catalog_id: str = Field(..., min_length=1)
    description: Optional[str] = None


class CatalogKnowledgeGraphGenerationRequest(BaseModel):
    source_type: Literal["outline_text", "kg_json"]
    outline_text: Optional[str] = None
    kg_json: Optional[dict] = None
    activate: bool = True

    @model_validator(mode="after")
    def validate_matching_payload(self):
        outline_text = (self.outline_text or "").strip()
        if self.source_type == "outline_text":
            if not outline_text:
                raise ValueError("outline_text is required when source_type=outline_text")
            if self.kg_json is not None:
                raise ValueError("kg_json must be omitted when source_type=outline_text")
            self.outline_text = outline_text
            return self

        if not isinstance(self.kg_json, dict):
            raise ValueError("kg_json is required when source_type=kg_json")
        if self.outline_text is not None and outline_text:
            raise ValueError("outline_text must be omitted when source_type=kg_json")
        self.outline_text = None
        return self


class CatalogKnowledgeGraphGenerationData(BaseModel):
    task_id: str
    catalog_id: str
    status: str


class CatalogKnowledgeGraphGenerationResponse(BaseModel):
    code: int
    message: str
    data: CatalogKnowledgeGraphGenerationData


class CatalogKnowledgeGraphSummary(BaseModel):
    graph_id: str
    course_id: str
    version: int
    source_type: str
    generation_strategy: str
    node_count: int
    edge_count: int
    is_active: bool
    created_at: str


class CatalogKnowledgeGraphTaskSummary(BaseModel):
    task_id: str
    status: str
    progress: int
    error_code: Optional[str] = None
    error_message: str = ""
    created_at: str
    completed_at: Optional[str] = None


class CatalogKnowledgeGraphStatusData(BaseModel):
    catalog_id: str
    course_id: Optional[str] = None
    active_graph: Optional[CatalogKnowledgeGraphSummary] = None
    last_generation_task: Optional[CatalogKnowledgeGraphTaskSummary] = None
