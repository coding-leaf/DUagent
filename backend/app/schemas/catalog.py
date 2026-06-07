from typing import Optional

from pydantic import BaseModel, Field


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
