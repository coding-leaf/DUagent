from pydantic import BaseModel,Field
from typing import Optional

"""
┌──────────────────┬─────────────────────────────────────────────────────┐
  │       type       │                        说明                         │
  ├──────────────────┼─────────────────────────────────────────────────────┤
  │ chunk            │ 大模型吐出的文本片段（一个字一个字往前端推）        │
  ├──────────────────┼─────────────────────────────────────────────────────┤
  │ diagram          │ 图解（Mermaid 语法）                                │
  ├──────────────────┼─────────────────────────────────────────────────────┤
  │ knowledge_points │ 用到的知识点列表                                    │
  ├──────────────────┼─────────────────────────────────────────────────────┤
  │ suggestion       │ 补充建议 + 相似题                                   │
  ├──────────────────┼─────────────────────────────────────────────────────┤
  │ done             │ 结束信号，携带 conversation_id、suggested_exercises │
"""
class ModalPreference(BaseModel):
    video_animation:Optional[float]=Field(None,ge=0,le=100)
    chart_logic: Optional[float] = Field(None, ge=0, le=100)
    text_analysis: Optional[float] = Field(None, ge=0, le=100)
    code_practice: Optional[float] = Field(None, ge=0, le=100)
    formula_derivation: Optional[float] = Field(None, ge=0, le=100)


class DisciplineBadge(BaseModel):
    """学科底座徽章"""
    subject: str = Field(..., description="学科名称")
    level: str = Field(..., description="徽章等级")
    streak_days: int = Field(0, description="连续学习天数")

class UserProfile(BaseModel):
    """用户画像（6维，Backend 从 SQL 组装传入）"""
    # 维度1：引导粒度
    guidance_level: str = Field(..., description="L1(启发) / L2(伴学) / L3(保姆)")
    # 维度2：模态偏好
    modal_preference: Optional[ModalPreference] = None
    # 维度3：知识坐标（已掌握）
    knowledge_mastered: list[str] = Field(default_factory=list)
    # 维度4：认知盲区（薄弱点）
    knowledge_weak: list[str] = Field(default_factory=list)
    # 维度5：驱动意图
    drive_intent: Optional[str] = Field(None, description="exam_sprint / daily_homework / casual")
    # 维度6：学科底座
    discipline_badge: Optional[DisciplineBadge] = None
class RecentMessage(BaseModel):
    """一轮对话消息"""
    role: str = Field(..., description="user / assistant")
    content: str = Field(..., description="消息内容")
class ChatRequest(BaseModel):
    """POST /agent/v1/tutoring/chat 请求体"""
    user_id: str = Field(..., description="用户 ID")
    course_id: str = Field(..., description="课程 ID")
    conversation_id: Optional[str] = Field(None, description="对话 ID，续接时传入")
    message: str = Field(..., description="用户当前消息")
    user_profile: UserProfile = Field(..., description="用户画像")
    conversation_summary: Optional[str] = Field(None, description="全局对话摘要")
    recent_messages: list[RecentMessage] = Field(default_factory=list)

class ChunkEvent(BaseModel):
      """SSE 事件：文本片段"""
      type: str = Field("chunk")
      content: str = Field(..., description="增量文本")


class KnowledgePoint(BaseModel):
      """引用的知识点"""
      name: str = Field(..., description="知识点名称")
      chapter: Optional[str] = Field(None, description="所属章节")
      mastery: Optional[float] = Field(None, ge=0, le=100, description="用户掌握度")


class KnowledgePointsEvent(BaseModel):
      """SSE 事件：引用的知识点列表"""
      type: str = Field("knowledge_points")
      points: list[KnowledgePoint] = Field(default_factory=list)


class DiagramEvent(BaseModel):
      """SSE 事件：图解（mermaid 语法或图表 JSON）"""
      type: str = Field("diagram")
      diagram_type: str = Field(..., description="mermaid / chart_json")
      content: str = Field(..., description="图解内容")


class SuggestedExercise(BaseModel):
      """相似例题"""
      title: str = Field(..., description="题目")
      chapter: Optional[str] = Field(None)


class SuggestionEvent(BaseModel):
      """SSE 事件：补充学习建议 + 相似例题"""
      type: str = Field("suggestion")
      advice: str = Field(..., description="学习建议文字")
      exercises: list[SuggestedExercise] = Field(default_factory=list)


class DoneEvent(BaseModel):
      """SSE 事件：本轮回答完成"""
      type: str = Field("done")
      message_id: str = Field(..., description="本条回复的消息 ID")
      conversation_id: Optional[str] = Field(None, description="对话 ID")
      knowledge_points_used: list[KnowledgePoint] = Field(default_factory=list)
      suggested_exercises: list[SuggestedExercise] = Field(default_factory=list)
