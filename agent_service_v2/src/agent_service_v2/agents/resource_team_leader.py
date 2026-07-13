import json

from pydantic import BaseModel, Field


class ResourceTeamRequest(BaseModel):
    task_id: str
    user_id: str
    course_id: str
    course_title: str | None = None
    goal: str = Field(min_length=1, max_length=2000)
    knowledge_point: str | None = None
    resource_preferences: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    conversation_id: str | None = None
    source_type: str = "manual"


def build_resource_team_leader_prompt() -> str:
    return """你是个性化学习资源团队 Leader，负责规划和发布，不直接代替 Worker 生成或审核。

必须使用 AgentScope 官方团队工具执行以下生命周期：
1. 使用 AgentCreate 创建至少一个 resource_generator Worker 和一个 resource_reviewer Worker。
2. 在创建 resource_generator 时，必须在 prompt 中告知其传入你的 task_id（作为 run_id 传入）与 conversation_id，并且必须将用户消息中的 course_title（课程名称，例如“C语言”）强力注入到它的 prompt 中（明确告知其：“当前课程为：<course_title>”）。以此确保生成员在调用 create_personalized_resource_draft/validate_personal_code_problem_draft 时能够正确填入 run_id 和 conversation_id，并且生成的资源（思维导图、测验、课件等）完全针对该课程，绝不跑偏或默认生成不相干的编程语言（如 Python 资料）。
3. 生成员必须使用 RAG 或可信课程上下文，创建草案并调用确定性验证工具；OJ 结果只能作为验证报告，不能由生成员自行判定审核通过。
4. 将草案摘要与脱敏验证报告交给审核员。审核员必须调用 review_personalized_resource：只有隐私、安全、事实依据缺失、验证失败或目标明显不匹配属于 hard_failures；覆盖度、表达和扩展建议属于 warnings。
5. hard_failures 为空时，warnings 不得阻止发布，应为 approved 或 approved_with_advice。
6. 若首次审核 rejected，可让生成员最多一次返修；再次 rejected 则结束，不得无限循环。
7. 只有 Leader 可调用 publish_personalized_resource。发布或终止后使用 TeamDelete 清理团队。
8. Worker 必须通过 TeamSay 回报；不得伪造 Worker 结果，不得把参考答案、隐藏测试输入或 AgentScope 原生对象写入面向学生的内容。
"""


def build_resource_team_user_message(request: ResourceTeamRequest) -> str:
    return json.dumps(
        {
            "task_id": request.task_id,
            "user_id": request.user_id,
            "course_id": request.course_id,
            "course_title": request.course_title,
            "goal": request.goal,
            "knowledge_point": request.knowledge_point,
            "resource_preferences": request.resource_preferences,
            "difficulty": request.difficulty,
            "conversation_id": request.conversation_id,
            "source_type": request.source_type,
        },
        ensure_ascii=False,
    )
