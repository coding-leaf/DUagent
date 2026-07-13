import copy
from typing import Dict, Any, List
from app.models.user import User
from app.models.others import UserProfile

DEFAULT_PROFILE = {
    "modal_preference": {
        "video_animation": 50,
        "chart_logic": 50,
        "text_analysis": 50,
        "code_practice": 50,
        "formula_derivation": 50,
    },
    "drive_intent": {
        "type": "casual",
        "learning_goal": "casual",
        "intensity": 30,
        "learning_habits": {},
        "knowledge_progress_summary": {},
    },
    "discipline_badge": {
        "badge_id": "freshman",
        "name": "学习新手",
        "description": "刚刚开启智能学习之旅，保持好的学习习惯哦！",
        "level": 1,
    },
}

def _safe_int(val: Any, default: int = 60) -> int:
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default

def _resource_preference_summary(modal_preference: dict) -> str:
    if not modal_preference or all(_safe_int(v, 50) == 50 for v in modal_preference.values()):
        return "未设置偏好"
    valid_prefs = [k for k, v in modal_preference.items() if _safe_int(v, 50) >= 70]
    if not valid_prefs:
        return "偏好均衡"
    pref_mapping = {
        "video_animation": "AI 交互",
        "chart_logic": "图表/逻辑",
        "text_analysis": "文本阅读",
        "code_practice": "代码练习",
        "formula_derivation": "公式推导",
    }
    return "、".join(pref_mapping[p] for p in valid_prefs if p in pref_mapping)

def _profile_dimensions(profile: dict) -> list[dict]:
    drive_intent = profile.get("drive_intent") or {}
    learning_habits = drive_intent.get("learning_habits") or {}
    knowledge_progress_summary = drive_intent.get("knowledge_progress_summary") or {}
    blindspots = profile.get("cognitive_blindspots") or []
    modal_preference = profile.get("modal_preference") or {}
    knowledge_coordinates = profile.get("knowledge_coordinates") or []
    guidance_level = profile.get("guidance_level") or {}

    weak_source = "profile_dialogue" if any(
        isinstance(item, dict) and item.get("source") == "profile_dialogue"
        for item in blindspots
    ) else ("evaluation" if blindspots else "system_pending")

    return [
        {
            "key": "learning_goal",
            "label": "学习目标",
            "value": drive_intent.get("type") or "待补充",
            "source": drive_intent.get("source") or "system_profile",
        },
        {
            "key": "weak_points",
            "label": "薄弱点",
            "value": [item.get("name") if isinstance(item, dict) else item for item in blindspots],
            "source": weak_source,
        },
        {
            "key": "resource_preference",
            "label": "资源偏好",
            "value": _resource_preference_summary(modal_preference),
            "source": "profile_dialogue" if any(
                key not in DEFAULT_PROFILE["modal_preference"] for key in modal_preference
            ) else "resource_usage",
        },
        {
            "key": "guidance_level",
            "label": "引导强度",
            "value": guidance_level.get("current") or "L2",
            "source": "system_profile",
        },
        {
            "key": "knowledge_progress",
            "label": "知识进展",
            "value": knowledge_progress_summary if knowledge_progress_summary else len(knowledge_coordinates),
            "source": "kg_quiz_activity",
        },
        {
            "key": "learning_habits",
            "label": "学习习惯",
            "value": learning_habits,
            "source": "activity",
        },
    ]

def profile_data(pf: UserProfile | None, course_id: str, user: User | None = None) -> dict:
    if pf is None:
        data = copy.deepcopy(DEFAULT_PROFILE)
        data.update({
            "id": None,
            "user_id": user.id if user else None,
            "course_id": course_id,
            "generated_at": None,
            "knowledge_coordinates": [],
            "cognitive_blindspots": [],
            "guidance_level": {
                "current": user.guidance_level if user and user.guidance_level else "L2",
                "updated_at": "",
            },
        })
    else:
        data = {
            "id": pf.id,
            "user_id": pf.user_id,
            "course_id": pf.course_id,
            "generated_at": pf.generated_at.isoformat() if pf.generated_at else None,
            "guidance_level": {
                "current": user.guidance_level if user and user.guidance_level else (pf.guidance_level_current or "L2"),
                "updated_at": pf.guidance_level_updated_at.isoformat() if pf.guidance_level_updated_at else "",
            },
            "modal_preference": pf.modal_preference or copy.deepcopy(DEFAULT_PROFILE["modal_preference"]),
            "knowledge_coordinates": pf.knowledge_coordinates or [],
            "cognitive_blindspots": pf.cognitive_blindspots or [],
            "drive_intent": pf.drive_intent or copy.deepcopy(DEFAULT_PROFILE["drive_intent"]),
            "discipline_badge": pf.discipline_badge or copy.deepcopy(DEFAULT_PROFILE["discipline_badge"]),
        }

    data["resource_preference_summary"] = _resource_preference_summary(data["modal_preference"])
    data["profile_dimensions"] = _profile_dimensions(data)
    if user:
        data["role"] = user.role
    else:
        data["role"] = "student"

    return data
