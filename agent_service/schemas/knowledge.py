from typing import Literal

from pydantic import BaseModel, Field

from agent_service.schemas.common import ApiResponse


class KnowledgeIngestionMaterial(BaseModel):
    storage_uri: str = Field(..., min_length=1, description="课程目录共享存储中的资料相对路径")


class KnowledgeIngestionRequest(BaseModel):
    catalog_id: str = Field(..., description="Backend CourseCatalog ID，写入 Qdrant payload.course_id")
    materials: list[KnowledgeIngestionMaterial] = Field(..., description="待入库课程资料列表")


class KnowledgeIngestionMaterialResult(BaseModel):
    storage_uri: str = Field(..., description="原始资料路径")
    status: Literal["ingested", "failed"] = Field(..., description="单个资料入库状态")
    chunk_count: int = Field(0, ge=0, description="该资料写入的切片数量")
    error: str | None = Field(None, description="失败原因或补充说明")


class KnowledgeIngestionResultData(BaseModel):
    catalog_id: str = Field(..., description="Backend CourseCatalog ID")
    chunk_count: int = Field(..., ge=0, description="本次成功入库切片总数")
    materials: list[KnowledgeIngestionMaterialResult] = Field(..., description="逐资料处理结果")


class KnowledgeIngestionAcceptedResponse(ApiResponse[KnowledgeIngestionResultData]):
    pass
