from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChapterProgressItem(BaseModel):
    chapter: str = Field(..., description="章节名称")
    completion_rate: float = Field(..., ge=0, le=100, description="完成率 0-100")
    time_spent: int = Field(..., ge=0, description="学习时长（分钟）")


class LearningProgress(BaseModel):
    chapter_progress: list[ChapterProgressItem] = Field(..., description="各章节完成度")


class QuizResultItem(BaseModel):
    chapter: str = Field(..., description="章节")
    score: float = Field(..., ge=0, le=100, description="正确率")
    created_at: datetime = Field(..., description="完成时间")


class ResourceUsage(BaseModel):
    by_type: dict[str, Any] = Field(..., description="{document: N, mindmap: N, reading: N, code: N, video: N}")
    by_chapter: dict[str, Any] | None = Field(None, description="各章节资源使用分布")


class EvaluationGenerateRequest(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    course_id: str = Field(..., description="课程 ID")
    learning_progress: LearningProgress = Field(..., description="学习进度数据（Backend SQL 统计）")
    quiz_results: list[QuizResultItem] = Field(..., description="各次练习结果汇总")
    resource_usage: ResourceUsage = Field(..., description="资源使用统计")


class TableColumn(BaseModel):
    key: str = Field(..., description="字段键名")
    title: str = Field(..., description="表头名称")


class TableData(BaseModel):
    columns: list[TableColumn] = Field(..., description="表头")
    rows: list[dict[str, Any]] = Field(..., description="数据行")


class EvaluationData(BaseModel):
    progress_table: TableData | None = Field(None, description="学习进度表")
    mastery_table: TableData | None = Field(None, description="知识点掌握程度表")
    resource_usage_table: TableData | None = Field(None, description="资源使用习惯记录表")
    summary_text: str | None = Field(None, description="LLM 综合文字总结")
