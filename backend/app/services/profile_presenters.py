from typing import Dict, Any, List
from app.models.user import User
from app.models.others import UserProfile

_default_profile = {
    "guidance_level_current": "L2",
    "modal_preference": {
        "video_animation": 50,
        "chart_logic": 50,
        "text_analysis": 50,
        "code_practice": 50,
        "formula_derivation": 50,
    },
    "drive_intent": {
        "learning_goal": "casual",
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

def _resource_preference_summary(modal_preference: dict) -> str:
    if not modal_preference or all(v == 50 for v in modal_preference.values()):
        return "未设置偏好"
    valid_prefs = [k for k, v in modal_preference.items() if v >= 70]
    if not valid_prefs:
        return "偏好均衡"
    pref_mapping = {
        "video_animation": "视频/动画",
        "chart_logic": "图表/逻辑",
        "text_analysis": "文本阅读",
        "code_practice": "代码练习",
        "formula_derivation": "公式推导",
    }
    return "、".join(pref_mapping[p] for p in valid_prefs if p in pref_mapping)

def _profile_dimensions(profile: dict) -> list[dict]:
    dimensions = [
        {"name": "自主学习度", "value": 60},
        {"name": "成就导向度", "value": 60},
        {"name": "反思性特征", "value": 60},
        {"name": "持久力指数", "value": 60},
    ]
    if not profile:
        return dimensions
    
    habits = profile.get("drive_intent", {}).get("learning_habits", {})
    if habits:
        dimensions[0]["value"] = max(30, min(100, int(habits.get("autonomy_score", 60))))
        dimensions[1]["value"] = max(30, min(100, int(habits.get("achievement_score", 60))))
        dimensions[2]["value"] = max(30, min(100, int(habits.get("reflective_score", 60))))
        dimensions[3]["value"] = max(30, min(100, int(habits.get("persistence_score", 60))))
        
    return dimensions

def profile_data(pf: UserProfile | None, course_id: str, user: User | None = None) -> dict:
    if pf is None:
        data = dict(_default_profile)
        data.update({
            "id": None,
            "user_id": user.id if user else None,
            "course_id": course_id,
            "generated_at": None,
            "knowledge_coordinates": [],
            "cognitive_blindspots": [],
        })
    else:
        data = {
            "id": pf.id,
            "user_id": pf.user_id,
            "course_id": pf.course_id,
            "generated_at": pf.generated_at.isoformat() if pf.generated_at else None,
            "guidance_level_current": pf.guidance_level_current or "L2",
            "modal_preference": pf.modal_preference or _default_profile["modal_preference"],
            "knowledge_coordinates": pf.knowledge_coordinates or [],
            "cognitive_blindspots": pf.cognitive_blindspots or [],
            "drive_intent": pf.drive_intent or _default_profile["drive_intent"],
            "discipline_badge": pf.discipline_badge or _default_profile["discipline_badge"],
        }
        
    data["resource_preference_summary"] = _resource_preference_summary(data["modal_preference"])
    data["dimensions"] = _profile_dimensions(data)
    if user:
        data["role"] = user.role
        data["guidance_level_base"] = user.guidance_level
    else:
        data["role"] = "student"
        data["guidance_level_base"] = "L2"
        
    return data
