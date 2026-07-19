from agentscope.app import SubAgentTemplate

from agent_service_v2.agents.team_permissions import (
    build_generator_permission_context,
    build_reviewer_permission_context,
)


def build_resource_team_templates() -> list[SubAgentTemplate]:
    return [
        SubAgentTemplate(
            type="resource_generator",
            description="依据可信课程资料和学生目标生成结构化个性化资源草案，并调用确定性验证工具。",
            system_prompt_template=(
                "你是 {team_name} 的资源生成员 {member_name}。只生成被分配的草案，"
                "不得自行审核或宣布发布；完成后必须通过 TeamSay 向 {leader_name} 返回 generation_id、"
                "草案摘要和脱敏验证报告。"
            ),
            permission_context=build_generator_permission_context(),
            override_leader_mode=True,
            extend_leader_permission_rules=False,
            extend_leader_working_directories=False,
        ),
        SubAgentTemplate(
            type="resource_reviewer",
            description="宽松审核已验证草案，区分硬失败与不阻断发布的改进建议。",
            system_prompt_template=(
                "你是 {team_name} 的独立审核员 {member_name}。只依据草案和脱敏验证报告审核。"
                "仅隐私、安全、事实依据缺失、确定性验证失败或目标明显不匹配可列为 hard_failures；"
                "测试覆盖、表达风格和扩展建议放入 warnings，不得因此拒绝。"
                "使用 review_personalized_resource 记录结论，再通过 TeamSay 回报 {leader_name}。"
            ),
            permission_context=build_reviewer_permission_context(),
            override_leader_mode=True,
            extend_leader_permission_rules=False,
            extend_leader_working_directories=False,
        ),
    ]
