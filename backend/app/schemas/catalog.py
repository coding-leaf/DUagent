from typing import Optional

from pydantic import BaseModel, Field


class CourseCatalogCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class CourseCatalogItem(BaseModel):
    id: str
    title: str
    description: str
    status: str
    knowledge_status: str
    material_count: int
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
    status: str
    created_at: str


class CourseOfferingCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    catalog_id: str = Field(..., min_length=1)
    description: Optional[str] = None
