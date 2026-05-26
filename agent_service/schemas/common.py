from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")
HealthStatus = Literal["healthy", "degraded", "unhealthy"]


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(..., description="业务状态码")
    message: str = Field(..., description="响应消息")
    data: T = Field(..., description="响应数据")


class HealthData(BaseModel):
    status: HealthStatus = Field(..., description="healthy / degraded / unhealthy")
    qdrant_connected: bool = Field(..., description="Qdrant 向量库连接状态")
    model_loaded: bool = Field(..., description="大模型加载状态")
    model_name: str = Field(..., description="当前加载的模型名称")
    uptime_seconds: int = Field(..., ge=0, description="服务运行时长（秒）")


class ResourceTaskResponse(BaseModel):
    task_id: str = Field(..., description="Backend 传入的异步任务 ID")
    estimated_duration: int = Field(..., ge=0, description="预计完成时间（秒）")


class HealthResponse(ApiResponse[HealthData]):
    pass
