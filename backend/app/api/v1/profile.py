import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.session import async_session_factory
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, Evaluation, UserProfile, Resource
from app.models.quiz import QuizSession
from app.models.user import User
from app.schemas.ai_features import ProfileInitializeRequest, RefreshRequest
from app.services.agent_client import AgentServiceError, agent_client
from app.services.resource_scope import resolve_course_resource_scope, resource_scope_clause

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

_default_profile = {
    "modal_preference": {
        "video_animation": 50, "chart_logic": 50, "text_analysis": 50,
        "code_practice": 50, "formula_derivation": 50,
    },
    "guidance_level": {"current": "L2", "updated_at": ""},
    "knowledge_coordinates": [],
    "cognitive_blindspots": [],
    "drive_intent": {"type": "casual", "intensity": 30},
    "discipline_badge": {"subject": "", "level": "", "streak_days": 0},
    "generated_at": None,
}


class ProfileDialogueUpdateRequest(BaseModel):
    course_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=1000)


async def _acquire_profile_lock(db: AsyncSession, user_id: str, course_id: str) -> str:
    """Acquire a MySQL named lock for serializing profile writes."""
    lock_name = f"profile_{user_id}_{course_id}"
    if db.bind.dialect.name == "sqlite":
        return lock_name
    lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
    if not lock_result.scalar():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        )
    return lock_name


async def _release_profile_lock(db: AsyncSession, lock_name: str) -> None:
    """Release a previously acquired MySQL named lock for profile writes."""
    if db.bind.dialect.name == "sqlite":
        return
    await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})


async def _get_or_create_profile(db: AsyncSession, user_id: str, course_id: str) -> UserProfile:
    result = await db.execute(
        select(UserProfile)
        .where(
            UserProfile.user_id == user_id,
            UserProfile.course_id == course_id,
        )
        .order_by(UserProfile.generated_at.desc())
    )
    pf = result.scalars().first()
    if pf:
        if pf.is_deleted:
            pf.is_deleted = False
        return pf

    pf = UserProfile(user_id=user_id, course_id=course_id)
    db.add(pf)
    return pf


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


def _merge_dialogue_profile(pf: UserProfile, extracted: dict) -> dict:
    now = datetime.now(timezone.utc)
    learning_goal = extracted.get("learning_goal")
    weak_points = _as_list(extracted.get("weak_points") or extracted.get("cognitive_blindspots"))
    preferred_resources = _as_list(extracted.get("preferred_resources"))
    guidance_level = extracted.get("guidance_level")

    drive_intent = dict(pf.drive_intent or _default_profile["drive_intent"])
    if learning_goal:
        drive_intent["learning_goal"] = str(learning_goal)
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

    modal_preference = dict(pf.modal_preference or _default_profile["modal_preference"])
    for resource in preferred_resources:
        key = str(resource)
        if key:
            modal_preference[key] = max(int(modal_preference.get(key, 50)), 70)

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


def _resource_preference_summary(modal_preference: dict) -> str:
    if not modal_preference:
        return "暂无明显资源偏好"
    ordered = sorted(modal_preference.items(), key=lambda item: item[1] if isinstance(item[1], (int, float)) else 0, reverse=True)
    return "、".join(str(name) for name, score in ordered[:3] if isinstance(score, (int, float)))


def _profile_dimensions(profile: dict) -> list[dict]:
    drive_intent = profile.get("drive_intent") or {}
    blindspots = profile.get("cognitive_blindspots") or []
    modal_preference = profile.get("modal_preference") or {}
    knowledge_coordinates = profile.get("knowledge_coordinates") or []
    discipline_badge = profile.get("discipline_badge") or {}
    guidance_level = profile.get("guidance_level") or {}

    weak_source = "profile_dialogue" if any(
        isinstance(item, dict) and item.get("source") == "profile_dialogue"
        for item in blindspots
    ) else ("evaluation" if blindspots else "system_pending")

    return [
        {
            "key": "learning_goal",
            "label": "学习目标",
            "value": drive_intent.get("learning_goal") or drive_intent.get("type") or "待补充",
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
                key not in _default_profile["modal_preference"] for key in modal_preference
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
            "value": len(knowledge_coordinates),
            "source": "evaluation",
        },
        {
            "key": "discipline",
            "label": "学习纪律",
            "value": discipline_badge or {},
            "source": "activity",
        },
    ]


def _profile_data(pf: UserProfile | None, course_id: str) -> dict:
    if pf is None:
        data = dict(_default_profile)
        data["course_id"] = course_id
        data["profile_dimensions"] = _profile_dimensions(data)
        return data
    data = {
        "course_id": pf.course_id,
        "modal_preference": pf.modal_preference or _default_profile["modal_preference"],
        "guidance_level": {
            "current": pf.guidance_level_current,
            "updated_at": pf.guidance_level_updated_at.isoformat() if pf.guidance_level_updated_at else "",
        },
        "knowledge_coordinates": pf.knowledge_coordinates or [],
        "cognitive_blindspots": pf.cognitive_blindspots or [],
        "drive_intent": pf.drive_intent or _default_profile["drive_intent"],
        "discipline_badge": pf.discipline_badge or _default_profile["discipline_badge"],
        "generated_at": pf.generated_at.isoformat() if pf.generated_at else None,
    }
    data["profile_dimensions"] = _profile_dimensions(data)
    return data


@router.post("/initialize")
async def initialize_profile(
    req: ProfileInitializeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 幂等写入：重复初始化 = 覆盖旧结果（锁 + 软删旧行 → 插新行）
    lock_name = await _acquire_profile_lock(db, current_user.id, req.course_id)
    try:
        profile = await _get_or_create_profile(db, current_user.id, req.course_id)
        answers = req.answers or {}
        now = datetime.now(timezone.utc)
        
        profile.guidance_level_current = answers.get("guidance_level", "L2")
        profile.guidance_level_updated_at = now
        profile.modal_preference = {k: 60 for k in (answers.get("modal_preference") or ["text"])}
        profile.drive_intent = {"type": answers.get("learning_goal", "casual"), "intensity": 50}
        profile.knowledge_coordinates = [{"name": "入门", "status": "learning", "mastered_at": None}]
        profile.generated_at = now
            
        await db.flush()
        await db.refresh(profile)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "Profile initialize: error user_id=%s course_id=%s type=%s message=%s",
            current_user.id, req.course_id, type(e).__name__, str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 50000, "message": "初始化失败", "data": None},
        )
    finally:
        await _release_profile_lock(db, lock_name)

    return {"code": 200, "message": "success", "data": _profile_data(profile, req.course_id)}


@router.get("")
async def get_profile(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 永远读最新一条（幂等写入可能遗留多行在软删窗口期）
    result = await db.execute(
        select(UserProfile)
        .where(
            UserProfile.user_id == current_user.id,
            UserProfile.course_id == course_id,
            UserProfile.is_deleted == False,
        )
        .order_by(UserProfile.generated_at.desc())
    )
    pf = result.scalars().first()
    return {"code": 200, "message": "success", "data": _profile_data(pf, course_id)}


@router.post("/dialogue-update")
async def dialogue_update_profile(
    req: ProfileDialogueUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == "student":
        check = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.course_id == req.course_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if not check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "未加入该课程", "data": None},
            )

    payload = {
        "user_id": current_user.id,
        "course_id": req.course_id,
        "message": req.message,
    }
    try:
        data = await agent_client.post_json("/agent/v1/profile/dialogue-update", payload)
    except AgentServiceError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.agent_code or e.status_code, "message": e.message, "data": None},
        ) from e

    extracted = data.get("profile") if isinstance(data, dict) and isinstance(data.get("profile"), dict) else data
    if not isinstance(extracted, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": 50200, "message": "画像解析结果格式错误", "data": None},
        )

    lock_name = await _acquire_profile_lock(db, current_user.id, req.course_id)
    try:
        pf = await _get_or_create_profile(db, current_user.id, req.course_id)
        if pf.generated_at is None:
            pf.generated_at = datetime.now(timezone.utc)
        await db.flush()

        merged = _merge_dialogue_profile(pf, extracted)
        response_data = _profile_data(pf, req.course_id)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "Profile dialogue update: error user_id=%s course_id=%s type=%s message=%s",
            current_user.id, req.course_id, type(e).__name__, str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 50000, "message": "画像补充失败", "data": None},
        ) from e
    finally:
        await _release_profile_lock(db, lock_name)

    sources = {key: "profile_dialogue" for key, value in merged.items() if value}
    return {
        "code": 200,
        "message": "success",
        "data": {
            "profile": merged,
            "sources": sources,
            "profile_data": response_data,
        },
    }


async def _assemble_profile_payload(user_id: str, course_id: str, db: AsyncSession) -> dict:
    """组装调用 Agent /profile/generate 所需的 payload。从 SQL 聚合评估、练习、资源使用、近期活跃数据。"""
    payload: dict = {"user_id": user_id, "course_id": course_id}
    resource_scope = await resolve_course_resource_scope(db, course_id)

    # evaluation_data: 最近一次学习效果评估
    ev_result = await db.execute(
        select(Evaluation)
        .where(Evaluation.user_id == user_id, Evaluation.course_id == course_id, Evaluation.is_deleted == False)
        .order_by(Evaluation.generated_at.desc())
    )
    ev = ev_result.scalars().first()
    if ev:
        payload["evaluation_data"] = {
            "progress": ev.progress_table,
            "mastery": ev.mastery_table,
            "resource_usage": ev.resource_usage_table,
        }

    # quiz_history: 最近 20 条练习记录
    qz_result = await db.execute(
        select(QuizSession)
        .where(QuizSession.user_id == user_id, QuizSession.course_id == course_id, QuizSession.is_deleted == False)
        .order_by(QuizSession.create_time.desc())
        .limit(20)
    )
    quizzes = qz_result.scalars().all()
    if quizzes:
        payload["quiz_history"] = [
            {"score": q.score, "chapter": q.chapter, "created_at": q.create_time.isoformat() if q.create_time else ""}
            for q in quizzes
        ]

    # resource_usage_stats: 各类型资源使用次数
    types = ["document", "mindmap", "reading", "code", "video"]
    from sqlalchemy import case
    counts = {}
    for t in types:
        c_result = await db.execute(
            select(func.count(Resource.id)).where(
                resource_scope_clause(course_id, resource_scope.catalog_id),
                Resource.type == t,
                Resource.is_deleted == False,
            )
        )
        counts[f"{t}_count"] = c_result.scalar() or 0
    # quiz_count from quiz_sessions
    quiz_count_r = await db.execute(
        select(func.count(QuizSession.id)).where(
            QuizSession.user_id == user_id, QuizSession.course_id == course_id, QuizSession.is_deleted == False
        )
    )
    counts["quiz_count"] = quiz_count_r.scalar() or 0
    payload["resource_usage_stats"] = counts

    # drive_intent_data: 近 7 天学习活跃度
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    sessions_r = await db.execute(
        select(func.count(QuizSession.id)).where(
            QuizSession.user_id == user_id, QuizSession.course_id == course_id,
            QuizSession.is_deleted == False, QuizSession.create_time >= seven_days_ago,
        )
    )
    payload["drive_intent_data"] = {
        "recent_7d_sessions": sessions_r.scalar() or 0,
        "recent_7d_duration": 0,
    }

    return payload


async def _run_profile_refresh_background(
    task_id: str,
    user_id: str,
    course_id: str,
    payload: dict,
) -> None:
    """后台异步执行 Agent /profile/generate 并写入 UserProfile。

    设计约束：
    - 只接收原始标量 + 预组装 payload，不接收请求级 ORM 实例或 db session。
    - 内部自行创建独立 DB session，Agent 调用、锁、写库、task 更新全部在后台完成。
    - 失败时记录结构化日志 + 落 task failed，不抛异常。
    """
    async with async_session_factory() as db:
        try:
            data = await agent_client.post_json("/agent/v1/profile/generate", payload)

            lock_name = f"profile_{user_id}_{course_id}"
            if db.bind.dialect.name == "sqlite":
                locked = 1
            else:
                lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
                locked = lock_result.scalar()
            if not locked:
                raise RuntimeError(f"GET_LOCK timeout: {lock_name}")

            try:
                now = datetime.now(timezone.utc)
                pf = await _get_or_create_profile(db, user_id, course_id)
                await db.flush()
                pf.generated_at = now

                pf.modal_preference = data.get("modal_preference", {})
                gs = data.get("guidance_level_suggestion") or {}
                pf.guidance_level_current = gs.get("recommended", "L2")
                pf.guidance_level_updated_at = now
                pf.knowledge_coordinates = data.get("knowledge_coordinates", [])
                pf.cognitive_blindspots = data.get("cognitive_blindspots", [])
                pf.drive_intent = data.get("drive_intent", {})
                pf.discipline_badge = data.get("discipline_badge", {})

                await db.execute(
                    update(AsyncTask)
                    .where(AsyncTask.id == task_id)
                    .values(
                        status="completed",
                        result={"updated_at": now.isoformat()},
                        completed_at=now,
                    )
                )
                await db.commit()
                logger.info(
                    "Profile refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id, user_id, course_id,
                )
            finally:
                try:
                    if db.bind.dialect.name != "sqlite":
                        await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                except Exception:
                    logger.warning(
                        "Profile refresh background: RELEASE_LOCK failed lock_name=%s", lock_name,
                    )
        except AgentServiceError as e:
            await db.rollback()
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code=str(e.agent_code or "agent_error"),
                    error_message=e.message,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Profile refresh background: AgentServiceError task_id=%s user_id=%s course_id=%s "
                "status=%s agent_code=%s message=%s",
                task_id, user_id, course_id, e.status_code, e.agent_code, e.message,
            )
        except Exception as e:
            await db.rollback()
            error_msg = str(e)[:500]
            # 保留锁竞争语义（同步版稳定化阶段已定义的 error_code）
            is_lock_timeout = "GET_LOCK timeout" in str(e)
            error_code = "lock_timeout" if is_lock_timeout else "internal_error"
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code=error_code,
                    error_message=error_msg,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Profile refresh background: unexpected error task_id=%s user_id=%s course_id=%s "
                "type=%s message=%s",
                task_id, user_id, course_id, type(e).__name__, error_msg,
            )


@router.post("/refresh")
async def refresh_profile(
    req: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """请求刷新用户画像（真异步）。

    请求内：权限校验 → payload 组装 → 创建 AsyncTask → commit → 返回 202。
    后台 _run_profile_refresh_background：Agent 调用 → 锁 → 写库 → task 完成/失败。
    """
    course_id = req.course_id
    # 权限校验
    if current_user.role == "student":
        check = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if not check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "未加入该课程", "data": None},
            )

    # 组装 payload（需要 DB，在请求内完成）
    payload = await _assemble_profile_payload(current_user.id, course_id, db)

    # 创建任务并立即提交
    task = AsyncTask(
        task_type="profile_refresh",
        status="processing",
        user_id=current_user.id,
        course_id=course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    await db.commit()

    # 后台异步执行 Agent 调用 + 写库（不复用请求级 db/ORM）
    asyncio.create_task(_run_profile_refresh_background(
        task_id=task.id,
        user_id=current_user.id,
        course_id=course_id,
        payload=payload,
    ))

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )
