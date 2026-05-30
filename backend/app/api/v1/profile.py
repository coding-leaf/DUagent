from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, Evaluation, UserProfile, Resource
from app.models.quiz import QuizSession
from app.models.user import User
from app.schemas.ai_features import ProfileInitializeRequest
from app.services.agent_client import AgentServiceError, agent_client

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


def _profile_data(pf: UserProfile | None, course_id: str) -> dict:
    if pf is None:
        data = dict(_default_profile)
        data["course_id"] = course_id
        return data
    return {
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


@router.post("/initialize")
async def initialize_profile(
    req: ProfileInitializeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    answers = req.answers or {}
    profile = UserProfile(
        user_id=current_user.id,
        course_id=req.course_id,
        guidance_level_current=answers.get("guidance_level", "L2"),
        guidance_level_updated_at=datetime.now(timezone.utc),
        modal_preference={k: 60 for k in (answers.get("modal_preference") or ["text"])},
        drive_intent={"type": answers.get("learning_goal", "casual"), "intensity": 50},
        knowledge_coordinates=[{"name": "入门", "status": "learning", "mastered_at": None}],
        generated_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)

    return {"code": 200, "message": "success", "data": _profile_data(profile, req.course_id)}


@router.get("")
async def get_profile(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserProfile)
        .where(
            UserProfile.user_id == current_user.id,
            UserProfile.course_id == course_id,
            UserProfile.is_deleted == False,
        )
    )
    pf = result.scalar_one_or_none()
    return {"code": 200, "message": "success", "data": _profile_data(pf, course_id)}


async def _assemble_profile_payload(user_id: str, course_id: str, db: AsyncSession) -> dict:
    """组装调用 Agent /profile/generate 所需的 payload。从 SQL 聚合评估、练习、资源使用、近期活跃数据。"""
    payload: dict = {"user_id": user_id, "course_id": course_id}

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
                Resource.course_id == course_id, Resource.type == t, Resource.is_deleted == False
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


@router.post("/refresh")
async def refresh_profile(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """请求刷新用户画像。调用 Agent /profile/generate，成功后 upsert UserProfile。"""
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

    # 创建任务
    task = AsyncTask(
        task_type="profile_refresh",
        status="processing",
        user_id=current_user.id,
        course_id=course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    try:
        # 组装请求 payload
        payload = await _assemble_profile_payload(current_user.id, course_id, db)
        # 调用 Agent Service
        data = await agent_client.post_json("/agent/v1/profile/generate", payload)
    except AgentServiceError as e:
        task.status = "failed"
        task.error_code = str(e.agent_code or "agent_error")
        task.error_message = e.message
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()
        return JSONResponse(
            status_code=202,
            content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
        )

    # 校验并 upsert UserProfile
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.user_id == current_user.id,
            UserProfile.course_id == course_id,
            UserProfile.is_deleted == False,
        )
    )
    pf = result.scalar_one_or_none()
    if pf is None:
        pf = UserProfile(user_id=current_user.id, course_id=course_id)
        db.add(pf)

    pf.modal_preference = data.get("modal_preference", pf.modal_preference)
    gs = data.get("guidance_level_suggestion") or {}
    pf.guidance_level_current = gs.get("recommended", pf.guidance_level_current)
    pf.guidance_level_updated_at = now
    pf.knowledge_coordinates = data.get("knowledge_coordinates", pf.knowledge_coordinates)
    pf.cognitive_blindspots = data.get("cognitive_blindspots", pf.cognitive_blindspots)
    pf.drive_intent = data.get("drive_intent", pf.drive_intent)
    pf.discipline_badge = data.get("discipline_badge", pf.discipline_badge)
    pf.generated_at = now

    # 标记任务完成
    task.status = "completed"
    task.result = {"updated_at": now.isoformat()}
    task.completed_at = now
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )
