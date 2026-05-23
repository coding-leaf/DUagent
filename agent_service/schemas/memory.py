from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent_service.schemas.common import ApiResponse

MemoryRole = Literal["user", "assistant"]
FactType = Literal["blind_spot", "mastered_point", "cognitive_preference"]


class MemoryMessage(BaseModel):
    role: MemoryRole = Field(..., description="user / assistant")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(..., description="消息时间")


class ExtractedFact(BaseModel):
    content: str | None = Field(None, description="事实内容（如：用户在递归概念上卡壳）")
    fact_type: FactType | None = Field(None, description="blind_spot / mastered_point / cognitive_preference")
    knowledge_point: str | None = Field(None, description="关联知识点名称（如有）")
    confidence: float | None = Field(None, ge=0, le=1, description="置信度 0-1")


class MemoryCompressRequest(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    conversation_id: str = Field(..., description="对话 ID")
    old_summary: str | None = Field(None, description="旧的全局摘要（首次压缩时为空）")
    messages_to_compress: list[MemoryMessage] = Field(..., description="本轮需要压缩的对话消息（最早的 N 轮）")
    existing_facts: list[str] = Field(default_factory=list, description="已存储的长期记忆事实 ID 列表（用于去重）")


class MemoryCompressResult(BaseModel):
    new_summary: str | None = Field(None, description="融合后的新全局摘要")
    extracted_facts: list[ExtractedFact] = Field(default_factory=list, description="提取的语义事实")


class MemoryCompressResponse(ApiResponse[MemoryCompressResult]):
    pass
