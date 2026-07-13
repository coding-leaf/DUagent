from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.others import AsyncTask, LearningActivity, LearningPath, Resource, UserPersonalizedResource, UserProfile
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_catalog_gate import resolve_generation_catalog
from app.services.resource_scope import (
    ensure_course_resource_access,
    resolve_course_resource_scope,
    resource_scope_clause,
)


_TYPE_PREFERENCES = {
    "text_analysis": {"personal_lesson", "reading", "lesson", "document"},
    "chart_logic": {"diagram", "mindmap"},
    "code_practice": {"practice", "example", "code"},
    "formula_derivation": {"practice"},
}


def build_ai_chat_resource_task_id(
    *, user_id: str, course_id: str, conversation_id: str, run_id: str,
    goal: str, resource_type: str,
) -> str:
    raw = "\x1f".join((user_id, course_id, conversation_id, run_id, goal.strip(), resource_type))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def score_personalized_resource(resource: Resource, context: dict[str, Any]) -> tuple[int, list[str]]:
    searchable = " ".join(str(value or "") for value in (
        resource.title, resource.description, resource.chapter, resource.knowledge_point,
        " ".join(resource.tags or []) if isinstance(resource.tags, list) else resource.tags,
    )).lower()
    target_terms = {term for term in str(context.get("target") or "").lower().split() if len(term) > 1}
    score = sum(2 for term in target_terms if term in searchable)
    reasons: list[str] = []
    knowledge_point = str(context.get("knowledge_point") or "").strip()
    if knowledge_point and knowledge_point.lower() in searchable:
        score += 6
        reasons.append("匹配当前知识点")
    weak_points = context.get("weak_points") or set()
    if any(str(point).lower() in searchable for point in weak_points):
        score += 4
        reasons.append("针对当前薄弱或推荐节点")
    if resource.type in (context.get("preferred_types") or set()):
        score += 3
        reasons.append("符合资源偏好")
    recent_count = int((context.get("recent_types") or {}).get(resource.type, 0))
    if recent_count:
        score += min(recent_count, 2)
        reasons.append("延续近期学习方式")
    if score and not reasons:
        reasons.append("匹配当前学习目标")
    return score, reasons


async def recommend_personalized_resources(
    db: AsyncSession, *, user_id: str, course_id: str, target: str,
    knowledge_point: str | None = None, limit: int = 3,
) -> dict:
    user = await _get_user(db, user_id)
    await ensure_course_resource_access(db, user, course_id)
    scope = await resolve_course_resource_scope(db, course_id)
    resources = (await db.execute(
        select(Resource).where(
            resource_scope_clause(scope.class_course_id, scope.catalog_id),
            Resource.is_deleted.is_(False),
        )
    )).scalars().all()

    profile = (await db.execute(select(UserProfile).where(
        UserProfile.user_id == user_id,
        UserProfile.course_id == course_id,
        UserProfile.is_deleted.is_(False),
    ))).scalars().first()
    path = (await db.execute(select(LearningPath).where(
        LearningPath.user_id == user_id,
        LearningPath.course_id == course_id,
        LearningPath.is_deleted.is_(False),
    ))).scalars().first()
    activities = (await db.execute(select(LearningActivity).where(
        LearningActivity.user_id == user_id,
        LearningActivity.course_id == course_id,
        LearningActivity.is_deleted.is_(False),
    ).order_by(LearningActivity.occurred_at.desc()).limit(20))).scalars().all()

    preferred_types: set[str] = set()
    for key, value in (profile.modal_preference or {}).items() if profile else []:
        if int(value or 0) >= 70:
            preferred_types.update(_TYPE_PREFERENCES.get(key, set()))
    weak_points = {
        str(item.get("name") or item.get("node_name") or "")
        for item in (profile.cognitive_blindspots or []) if profile and isinstance(item, dict)
    }
    if path and isinstance(path.nodes, list):
        weak_points.update(
            str(node.get("name") or "") for node in path.nodes
            if isinstance(node, dict) and node.get("status") in {"weak", "recommended"}
        )
    resource_types = {resource.id: resource.type for resource in resources}
    recent_types = Counter(
        resource_types.get(activity.resource_id) for activity in activities if activity.resource_id
    )
    recent_types.pop(None, None)
    context = {
        "target": target,
        "knowledge_point": knowledge_point,
        "preferred_types": preferred_types,
        "weak_points": {point for point in weak_points if point},
        "recent_types": recent_types,
    }
    ranked = []
    for resource in resources:
        score, reasons = score_personalized_resource(resource, context)
        if score > 0:
            ranked.append((score, resource, reasons))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    items = [{
        "id": resource.id,
        "title": resource.title,
        "type": resource.type,
        "summary": resource.description or resource.knowledge_point or "",
        "reason": "；".join(reasons),
    } for _score, resource, reasons in ranked[:max(1, min(limit, 3))]]
    return {"status": "available" if items else "empty", "items": items, "returned_count": len(items)}


async def start_ai_chat_resource_generation(
    db: AsyncSession, *, user_id: str, course_id: str, conversation_id: str,
    run_id: str, goal: str, resource_type: str,
) -> dict:
    user = await _get_user(db, user_id)
    await ensure_course_resource_access(db, user, course_id)
    existing = (await db.execute(select(AsyncTask).where(
        AsyncTask.user_id == user_id,
        AsyncTask.course_id == course_id,
        AsyncTask.task_type == "resource_generation",
        AsyncTask.is_deleted.is_(False),
        AsyncTask.result["ai_chat_run_id"].as_string() == run_id,
    ).order_by(AsyncTask.create_time.asc()).limit(1))).scalars().first()
    if existing:
        return _task_result(existing)

    catalog = await resolve_generation_catalog(db, course_id)
    task_id = build_ai_chat_resource_task_id(
        user_id=user_id, course_id=course_id, conversation_id=conversation_id,
        run_id=run_id, goal=goal, resource_type=resource_type,
    )
    task = await db.get(AsyncTask, task_id)
    if task:
        return _task_result(task)
    task = AsyncTask(
        id=task_id,
        task_type="resource_generation",
        status="processing",
        user_id=user_id,
        course_id=course_id,
        result={
            **catalog.model_dump(),
            "ai_chat_run_id": run_id,
            "conversation_id": conversation_id,
            "goal": goal,
            "resource_type": resource_type,
        },
    )
    db.add(task)
    db.add(UserPersonalizedResource(
        user_id=user_id, course_id=course_id, source_type="ai_chat", task_id=task_id,
    ))
    await db.flush()
    try:
        await agent_client.post_json(
            "/agent/v2/personalized-resources/generations",
            {
                "task_id": task_id,
                "user_id": user_id,
                "course_id": course_id,
                "course_title": catalog.catalog_title,
                "goal": goal,
                "resource_preferences": [resource_type],
                "conversation_id": conversation_id,
                "source_type": "ai_chat",
            },
        )
    except AgentServiceError as exc:
        task.status = "failed"
        task.error_code = str(exc.agent_code or "agent_error")[:20]
        task.error_message = exc.message[:500]
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()
    return _task_result(task)


async def _get_user(db: AsyncSession, user_id: str) -> User:
    user = (await db.execute(select(User).where(
        User.id == user_id, User.is_deleted.is_(False), User.is_active.is_(True),
    ))).scalar_one_or_none()
    if user is None:
        raise ValueError("user_not_found")
    return user


def _task_result(task: AsyncTask) -> dict:
    return {
        "status": task.status,
        "task_id": task.id,
        "course_id": task.course_id,
        "error_message": task.error_message or "",
    }
