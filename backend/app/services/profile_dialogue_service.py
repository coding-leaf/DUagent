import copy
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

try:
    from app.models.profile import UserProfile
except ImportError:
    from app.models.others import UserProfile

from app.infrastructure.locks import profile_lock
from app.services.profile_presenters import DEFAULT_PROFILE
from app.services.profile_service import ProfileService

_LEARNING_GOAL_KEYWORDS = (
    ("exam_sprint", ("备考", "考试", "期末", "冲刺", "考研", "考证")),
    ("daily_homework", ("课后", "作业", "巩固", "复习", "日常")),
    ("casual", ("兴趣", "拓展", "了解", "自学")),
)

_RESOURCE_PREFERENCE_KEYWORDS = (
    ("video_animation", ("视频", "动画", "ai", "交互", "对话", "提问", "聊天")),
    ("chart_logic", ("图解", "图表", "思维导图", "流程图", "diagram", "mindmap")),
    ("code_practice", ("代码", "实操", "编程", "练习")),
    ("text_analysis", ("文本", "文档", "阅读", "文字")),
    ("formula_derivation", ("公式", "推导")),
)

def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

def _dedupe_limit(items: list, limit: int = 10) -> list:
    seen: set[str] = set()
    result = []
    for item in items:
        if isinstance(item, dict):
            key = str(item.get("name") or item.get("point") or item)
        else:
            key = str(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result

def _classify_learning_goal(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text in {"exam_sprint", "daily_homework", "casual"}:
        return text
    for goal, keywords in _LEARNING_GOAL_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return goal
    return None

def _classify_resource_preferences(values: list) -> list[str]:
    preferences: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        if text in DEFAULT_PROFILE["modal_preference"]:
            preferences.append(text)
            continue
        for preference, keywords in _RESOURCE_PREFERENCE_KEYWORDS:
            if any(keyword.lower() in text.lower() for keyword in keywords):
                preferences.append(preference)
    return _dedupe_limit(preferences, limit=5)

def _normalize_fields(extracted: dict) -> dict:
    raw_goal = extracted.get("learning_goal") or extracted.get("drive_intent")
    raw_preferences = _as_list(
        extracted.get("preferred_resources")
        or extracted.get("learning_preferences")
        or extracted.get("resource_preference")
    )
    raw_preferences.extend(_as_list(raw_goal))
    return {
        **extracted,
        "learning_goal": _classify_learning_goal(raw_goal),
        "preferred_resources": _classify_resource_preferences(raw_preferences),
    }

def _merge_profile(pf: UserProfile, normalized: dict) -> dict:
    now = datetime.now(timezone.utc)
    learning_goal = normalized.get("learning_goal")
    weak_points = _as_list(normalized.get("weak_points") or normalized.get("cognitive_blindspots"))
    preferred_resources = _as_list(normalized.get("preferred_resources"))
    guidance_level = normalized.get("guidance_level")

    # Use deepcopy defensively
    drive_intent = copy.deepcopy(pf.drive_intent or DEFAULT_PROFILE["drive_intent"])
    if learning_goal:
        drive_intent["learning_goal"] = str(learning_goal)
        drive_intent["type"] = str(learning_goal)
        drive_intent["source"] = "profile_dialogue"

    blindspots = list(pf.cognitive_blindspots or [])
    blindspots.extend(
        {
            "name": str(point),
            "source": "profile_dialogue",
            "updated_at": now.isoformat(),
        }
        for point in weak_points
        if point
    )

    modal_preference = copy.deepcopy(pf.modal_preference or DEFAULT_PROFILE["modal_preference"])
    for resource in preferred_resources:
        key = str(resource)
        if key:
            try:
                current_val = int(modal_preference.get(key, 50))
            except (ValueError, TypeError):
                current_val = 50
            modal_preference[key] = max(current_val, 70)

    if guidance_level:
        pf.guidance_level_current = str(guidance_level)
        pf.guidance_level_updated_at = now

    pf.drive_intent = drive_intent
    pf.cognitive_blindspots = _dedupe_limit(blindspots)
    pf.modal_preference = modal_preference
    pf.generated_at = now

    return {
        "learning_goal": learning_goal,
        "weak_points": weak_points,
        "preferred_resources": preferred_resources,
        "guidance_level": guidance_level,
    }

class ProfileDialogueService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.profile_service = ProfileService(db)

    async def update_from_dialogue(self, user_id: str, course_id: str, extracted_data: dict) -> UserProfile:
        async with profile_lock(self.db, user_id, course_id):
            pf = await self.profile_service.get_or_create_profile(user_id, course_id)
            if pf.generated_at is None:
                pf.generated_at = datetime.now(timezone.utc)
            await self.db.flush()

            normalized = _normalize_fields(extracted_data)
            _merge_profile(pf, normalized)
            
            flag_modified(pf, "drive_intent")
            flag_modified(pf, "cognitive_blindspots")
            flag_modified(pf, "modal_preference")
            
            await self.db.flush()
            return pf
