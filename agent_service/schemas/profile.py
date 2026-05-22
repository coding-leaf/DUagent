from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_service.schemas.common import ApiResponse

GuidanceLevel = Literal["L1", "L2", "L3"]
KnowledgeStatus = Literal["mastered", "learning"]
BlindspotSeverity = Literal["high", "medium", "low"]
DriveIntentType = Literal["exam_sprint", "daily_homework", "casual"]


class ModalPreference(BaseModel):
    video_animation: float | None = Field(None, ge=0, le=100, description="视频动画偏好 0-100")
    chart_logic: float | None = Field(None, ge=0, le=100, description="图表逻辑偏好 0-100")
    text_analysis: float | None = Field(None, ge=0, le=100, description="文字解析偏好 0-100")
    code_practice: float | None = Field(None, ge=0, le=100, description="代码实践偏好 0-100")
    formula_derivation: float | None = Field(None, ge=0, le=100, description="公式推导偏好 0-100")


class ProfileEvaluationData(BaseModel):
    progress: dict[str, Any] | None = Field(None, description="学习进度")
    mastery: dict[str, Any] | None = Field(None, description="掌握程度")
    resource_usage: dict[str, Any] | None = Field(None, description="资源使用统计")


class QuizHistoryItem(BaseModel):
    score: float = Field(..., description="正确率")
    chapter: str | None = Field(None, description="章节")
    created_at: datetime = Field(..., description="完成时间")


class ResourceUsageStats(BaseModel):
    video_count: int | None = Field(None, ge=0, description="视频使用次数")
    document_count: int | None = Field(None, ge=0, description="文档使用次数")
    code_count: int | None = Field(None, ge=0, description="代码资源使用次数")
    quiz_count: int | None = Field(None, ge=0, description="做题次数")


class DriveIntentData(BaseModel):
    recent_7d_sessions: int | None = Field(None, ge=0, description="近 7 天学习次数")
    recent_7d_duration: int | None = Field(None, ge=0, description="近 7 天学习时长（分钟）")


class ProfileGenerateRequest(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    course_id: str = Field(..., description="课程 ID")
    evaluation_data: ProfileEvaluationData | None = Field(None, description="最新学习效果评估")
    quiz_history: list[QuizHistoryItem] = Field(default_factory=list, description="练习历史记录")
    resource_usage_stats: ResourceUsageStats | None = Field(None, description="资源类型使用比例")
    drive_intent_data: DriveIntentData | None = Field(None, description="近期学习频率（Backend SQL 统计）")


class GuidanceLevelSuggestion(BaseModel):
    recommended: GuidanceLevel | None = Field(None, description="L1 / L2 / L3")
    reason: str | None = Field(None, description="建议依据")


class KnowledgeCoordinate(BaseModel):
    name: str = Field(..., description="知识点名称")
    status: KnowledgeStatus = Field(..., description="mastered / learning")


class CognitiveBlindspot(BaseModel):
    name: str = Field(..., description="知识点名称")
    error_count: int = Field(..., ge=0, description="错误次数")
    severity: BlindspotSeverity = Field(..., description="high / medium / low")


class DriveIntent(BaseModel):
    type: DriveIntentType = Field(..., description="exam_sprint / daily_homework / casual")
    intensity: float | None = Field(None, ge=0, le=100, description="近 7 天学习强度 0-100")


class DisciplineBadge(BaseModel):
    subject: str | None = Field(None, description="学科名称")
    level: str | None = Field(None, description="徽章等级")
    streak_days: int | None = Field(None, ge=0, description="连续学习天数")


class ProfileData(BaseModel):
    modal_preference: ModalPreference | None = Field(None, description="模态偏好（五维雷达图）")
    guidance_level_suggestion: GuidanceLevelSuggestion | None = Field(None, description="引导粒度建议")
    knowledge_coordinates: list[KnowledgeCoordinate] = Field(default_factory=list, description="知识坐标标签")
    cognitive_blindspots: list[CognitiveBlindspot] = Field(default_factory=list, description="认知盲区标签")
    drive_intent: DriveIntent | None = Field(None, description="驱动意图（状态光环）")
    discipline_badge: DisciplineBadge | None = Field(None, description="学科底座徽章")


class ProfileGenerateResponse(ApiResponse[ProfileData]):
    pass
