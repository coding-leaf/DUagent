from typing import Any

from pydantic import BaseModel, Field

from agent_service.schemas.common import ApiResponse


AnswerValue = str | list[str]


class AssessmentQuestion(BaseModel):
    id: str = Field(..., description="题目 ID")
    type: str = Field(..., description="题型")
    content: str = Field(..., description="题目内容")
    options: list[dict[str, Any]] = Field(default_factory=list, description="选项列表")
    correct_answer: AnswerValue = Field(..., description="正确答案，单选/简答为 string，多选为 array")
    knowledge_point: str = Field(..., description="关联知识点")


class AssessmentAnswer(BaseModel):
    question_id: str = Field(..., description="题目 ID")
    answer: AnswerValue = Field(..., description="用户提交的答案，单选/简答为 string，多选为 array")


class AssessmentEvaluateRequest(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    course_id: str = Field(..., description="课程 ID")
    quiz_id: str = Field(..., description="练习 ID")
    questions: list[AssessmentQuestion] = Field(..., description="题目列表")
    answers: list[AssessmentAnswer] = Field(..., description="用户答案")
    user_mastery: dict[str, Any] | None = Field(None, description="用户当前知识点掌握度")


class PerQuestionResult(BaseModel):
    question_id: str | None = Field(None, description="题目 ID")
    is_correct: bool | None = Field(None, description="是否正确")
    explanation: str | None = Field(None, description="LLM 解析")
    related_knowledge_points: list[str] = Field(default_factory=list, description="关联知识点")


class WeakPoint(BaseModel):
    name: str | None = Field(None, description="知识点名称")
    error_pattern: str | None = Field(None, description="错误模式描述")


class Diagnosis(BaseModel):
    summary: str | None = Field(None, description="诊断总结")
    weak_points: list[WeakPoint] = Field(default_factory=list, description="薄弱知识点")
    suggestions: list[str] = Field(default_factory=list, description="复习建议")


class AssessmentResult(BaseModel):
    per_question_results: list[PerQuestionResult] = Field(default_factory=list, description="每题评估结果")
    diagnosis: Diagnosis | None = Field(None, description="综合诊断")


class QuestionGenerateRequest(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    course_id: str = Field(..., description="课程 ID")
    knowledge_base_id: str | None = Field(None, description="课程知识库 ID；Backend 可由 course_id 解析后传入")
    chapter: str | None = Field(None, description="章节")
    knowledge_point: str | None = Field(None, description="知识点")
    question_types: list[str] = Field(default_factory=list, description="single_choice / multi_choice / code / short_answer")
    count: int = Field(5, ge=1, description="生成题数")
    difficulty: str | None = Field(None, description="easy / medium / hard")
    personalized: bool = Field(True, description="是否生成个性化题")
    personalization_context: dict[str, Any] | None = Field(None, description="个性化上下文")


class QuestionOption(BaseModel):
    key: str | None = Field(None, description="A/B/C/D")
    text: str | None = Field(None, description="选项文本")


class GeneratedQuestion(BaseModel):
    type: str = Field(..., description="single_choice / multi_choice / code / short_answer")
    content: str = Field(..., description="题目内容")
    options: list[QuestionOption] = Field(default_factory=list, description="选项列表，非选择题为空数组")
    answer: Any = Field(..., description="标准答案，单选/简答为 string，多选可为 array")
    explanation: str = Field(..., description="解析")
    chapter: str | None = Field(None, description="章节")
    knowledge_point: str = Field(..., description="关联知识点")
    difficulty: str | None = Field(None, description="easy / medium / hard")


class QuestionGenerateResult(BaseModel):
    questions: list[GeneratedQuestion] = Field(default_factory=list)


class AssessmentEvaluateResponse(ApiResponse[AssessmentResult]):
    pass


class QuestionGenerateResponse(ApiResponse[QuestionGenerateResult]):
    pass
