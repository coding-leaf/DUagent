from pydantic import BaseModel, Field

from agent_service.schemas.common import ApiResponse, ResourceTaskResponse


class ResourceGenerateRequest(BaseModel):
    task_id: str = Field(..., description="Backend 预先创建的任务 ID，Agent 返回和回调时原样带回")
    user_id: str = Field(..., description="触发教师用户 ID")
    course_id: str = Field(..., description="课程 ID")
    webhook_url: str = Field(..., description="完成回调 URL")
    chapter: str | None = Field(None, description="章节")
    knowledge_point: str | None = Field(None, description="知识点")
    resource_types: list[str] | None = Field(
        None,
        description="资源类型列表：document / mindmap / reading / code；不传则默认生成这四类",
    )


class ResourceGenerateAcceptedResponse(ApiResponse[ResourceTaskResponse]):
    pass
