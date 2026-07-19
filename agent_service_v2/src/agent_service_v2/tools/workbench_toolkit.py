from __future__ import annotations

from agentscope.tool import FunctionTool, ToolBase, ToolGroup
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.artifact_files import build_write_artifact_file
from agent_service_v2.tools.planning import build_planning_group
from agent_service_v2.tools.input_models import ArtifactFileInput


OPTIONAL_PRACTICE_GROUPS = frozenset(
    {"personal_code_problem", "personal_choice_quiz"}
)


def split_workbench_tool_groups(
    groups: list[ToolGroup],
) -> tuple[list[ToolBase], list[ToolGroup]]:
    dynamic_groups = [
        group for group in groups if group.name in OPTIONAL_PRACTICE_GROUPS
    ]
    basic_tools = [
        tool
        for group in groups
        if group.name not in OPTIONAL_PRACTICE_GROUPS
        for tool in group.tools
    ]
    return basic_tools, dynamic_groups


def build_workbench_tool_groups(
    *,
    memory_tools: list[ToolBase] | None,
    rag_tools: list[ToolBase] | None,
    learning_progress_tools: list[ToolBase] | None,
    oj_execution_tools: list[ToolBase] | None = None,
    personal_code_problem_tools: list[ToolBase] | None = None,
    personal_choice_quiz_tools: list[ToolBase] | None = None,
    personal_practice_delivery_tools: list[ToolBase] | None = None,
    workspace: LocalWorkspace,
    run_id: str,
    learner_profile_tools: list[ToolBase] | None = None,
    personalized_resource_tools: list[ToolBase] | None = None,
) -> list[ToolGroup]:
    groups = [build_planning_group()]
    if memory_tools:
        groups.append(
            ToolGroup(
                name="memory",
                description="Search and update long-term learner memory.",
                tools=memory_tools,
            )
        )
    if rag_tools:
        groups.append(
            ToolGroup(
                name="rag",
                description="Retrieve course-grounded learning context.",
                tools=rag_tools,
            )
        )
    if learning_progress_tools:
        groups.append(
            ToolGroup(
                name="learning_progress",
                description="Read real learner progress and recent answer evidence from Backend.",
                instructions=(
                    "Use read_learning_progress before giving overall next-step learning advice. "
                    "Use read_recent_answers before explaining specific mistakes. "
                    "If the tools return empty or unavailable data, say evidence is insufficient."
                ),
                tools=learning_progress_tools,
            )
        )
    if learner_profile_tools:
        groups.append(
            ToolGroup(
                name="learner_profile",
                description="Read and update explicit stable course learner-profile facts.",
                instructions=(
                    "Read the profile before personalized advice. Update it only when the current "
                    "message explicitly states a stable goal, preference, guidance need, teaching "
                    "instruction, or learning habit. Never write inferred mastery or weak points."
                ),
                tools=learner_profile_tools,
            )
        )
    if personalized_resource_tools:
        groups.append(
            ToolGroup(
                name="personalized_resources",
                description="Recommend existing course resources or start one bounded personalized generation task.",
                instructions=(
                    "Recommend existing resources first. Only when no effective recommendation is returned, "
                    "start one non-video resource generation task for this run. A started task is not published."
                ),
                tools=personalized_resource_tools,
            )
        )
    if oj_execution_tools:
        groups.append(
            ToolGroup(
                name="oj_execution",
                description="Compile and run source code in an isolated online sandbox.",
                tools=oj_execution_tools,
            )
        )
    if personal_code_problem_tools:
        groups.append(
            ToolGroup(
                name="personal_code_problem",
                description=(
                    "Activate when the user explicitly requests a private programming exercise; "
                    "then call publish_personal_code_problem."
                ),
                instructions=(
                    "只处理用户明确要求的私有编程题练习。激活前应已取得用户明确要求的教材或学情依据；"
                    "依据不足时停止发布。statement 不得包含参考答案或隐藏用例。reference_solution "
                    "必须是可直接提交 OJ 的完整程序；public_inputs 与 hidden_inputs 总数不超过 8，"
                    "且不得在聊天或 Artifact 中泄露 reference_solution 和 hidden_inputs。只有 "
                    'outcome="success"、status="published"、problem_id 非空且返回 '
                    "CodeSandboxCard artifact 时才能声称练习可用。generation_id 不是 problem_id。"
                    "rejected、unavailable、degraded、delivery_failed、delivery_incomplete 或 error "
                    "均不得声称发布成功；delivery_incomplete 且包含 generation_id 时，调用恢复工具，"
                    "不要重新生成草案。"
                ),
                tools=personal_code_problem_tools,
            )
        )
    if personal_choice_quiz_tools:
        groups.append(
            ToolGroup(
                name="personal_choice_quiz",
                description=(
                    "Activate when the user explicitly requests answerable single-choice or "
                    "multi-choice practice; then call publish_personal_choice_quiz."
                ),
                instructions=(
                    "只处理用户明确要求的私有选择题练习。激活前应已取得用户明确要求的教材或学情依据；"
                    "依据不足时停止发布。题型只允许 single_choice 与 multi_choice。调用 "
                    "publish_personal_choice_quiz 后，只有 outcome=\"success\"、status=\"published\" "
                    "且返回 QuizCard artifact 时才能声称练习可用。rejected、unavailable、degraded、"
                    "delivery_incomplete 或 error 均不得声称发布成功。"
                ),
                tools=personal_choice_quiz_tools,
            )
        )
    if personal_practice_delivery_tools:
        groups.append(
            ToolGroup(
                name="personal_practice_delivery",
                description="Resume interrupted Backend publication of interactive practice.",
                tools=personal_practice_delivery_tools,
            )
        )
    artifact_tool = FunctionTool(build_write_artifact_file(workspace=workspace, run_id=run_id))
    artifact_tool.input_schema = ArtifactFileInput.tool_schema()
    groups.extend(
        [
            ToolGroup(
                name="artifact",
                description="Create validated learning artifacts in the AgentScope run workspace.",
                instructions=(
                    "Use write_artifact_file only for Markdown or Mermaid. "
                    "Interactive practice cards are created atomically by their publishing tools."
                ),
                tools=[artifact_tool],
            ),
        ]
    )
    return groups
