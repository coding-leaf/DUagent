from typing import Any

from pydantic import BaseModel, Field

from agent_service.schemas.common import ApiResponse


class KnowledgeGraphNode(BaseModel):
    id: str | None = None
    name: str | None = None
    chapter: str | None = None


class KnowledgeGraphEdge(BaseModel):
    from_: str | None = Field(None, alias="from", description="前置节点 ID")
    to: str | None = Field(None, description="后置节点 ID")


class KnowledgeGraph(BaseModel):
    nodes: list[KnowledgeGraphNode] = Field(default_factory=list, description="图谱节点")
    edges: list[KnowledgeGraphEdge] = Field(default_factory=list, description="前置依赖边")


class LearningPathGenerateRequest(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    course_id: str = Field(..., description="课程 ID")
    evaluation: dict[str, Any] = Field(..., description="学习效果评估数据")
    profile: dict[str, Any] = Field(..., description="用户画像数据")
    knowledge_graph: KnowledgeGraph = Field(..., description="静态课程知识点图谱（JSON 前置依赖关系）")


class LearningPathNode(BaseModel):
    id: str | None = Field(None, description="节点 ID")
    name: str | None = Field(None, description="知识点名称")
    status: str | None = Field(None, description="completed / in_progress / pending / recommended")
    mastery: float | None = Field(None, ge=0, le=100, description="掌握度 0-100")
    order: int | None = Field(None, description="排序序号")
    reason: str | None = Field(None, description="排在该位置的原因说明")


class LearningPathEdge(BaseModel):
    from_: str | None = Field(None, alias="from", description="前置节点 ID")
    to: str | None = Field(None, description="后置节点 ID")


class CurrentPosition(BaseModel):
    node_id: str | None = Field(None, description="当前节点 ID")
    node_name: str | None = Field(None, description="当前节点名称")


class LearningPathData(BaseModel):
    nodes: list[LearningPathNode] = Field(default_factory=list, description="路径节点")
    edges: list[LearningPathEdge] = Field(default_factory=list)
    current_position: CurrentPosition | None = None


class LearningPathGenerateResponse(ApiResponse[LearningPathData]):
    pass
