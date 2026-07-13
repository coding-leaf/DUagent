from __future__ import annotations

from typing import Any

from agentscope.message import AssistantMsg, Msg, UserMsg


def build_workbench_agent_input(*, message: str, context: dict[str, Any]) -> list[Msg]:
    inputs: list[Msg] = []
    context_text = _build_context_text(context)
    if context_text:
        inputs.append(UserMsg(name="system_context", content=context_text))

    for item in context.get("recent_messages") or []:
        msg = _history_message(item)
        if msg is not None:
            inputs.append(msg)

    inputs.append(UserMsg(name="student", content=message))
    return inputs


def _history_message(item: Any) -> Msg | None:
    if not isinstance(item, dict):
        return None
    content = str(item.get("content") or "").strip()
    if not content:
        return None
    role = item.get("role")
    if role == "user":
        return UserMsg(name="student", content=content)
    if role == "assistant":
        return AssistantMsg(name="assistant", content=content)
    return None


def _build_context_text(context: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = str(context.get("conversation_summary") or "").strip()
    if summary:
        lines.append(f"对话摘要：{summary}")

    profile = context.get("user_profile")
    if isinstance(profile, dict):
        profile_parts = []
        guidance = profile.get("guidance_level")
        if guidance:
            profile_parts.append(f"指导等级={guidance}")
        weak = _join_names(profile.get("knowledge_weak"))
        if weak:
            profile_parts.append(f"薄弱点={weak}")
        mastered = _join_names(profile.get("knowledge_mastered"))
        if mastered:
            profile_parts.append(f"已掌握={mastered}")
        custom_instruction = str(profile.get("custom_instruction") or "").strip()
        if custom_instruction:
            profile_parts.append(f"个性化要求={custom_instruction}")
        if profile_parts:
            lines.append("学习画像：" + "；".join(profile_parts))

    kg_nodes = context.get("active_kg_nodes")
    if isinstance(kg_nodes, list):
        node_names = [
            str(node.get("name") or "").strip()
            for node in kg_nodes
            if isinstance(node, dict) and str(node.get("name") or "").strip()
        ]
        if node_names:
            lines.append("课程知识点：" + "、".join(node_names[:20]))

    if not lines:
        return ""
    return (
        "本轮路由提示（仅用于工具路由，不是当前事实的确认结果）：\n"
        + "\n".join(lines)
    )


def _join_names(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    names = [str(item).strip() for item in value if str(item).strip()]
    return "、".join(names[:20])
