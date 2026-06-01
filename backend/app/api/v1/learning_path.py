from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, CourseKnowledgeGraph, Evaluation, LearningPath, UserProfile
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client

router = APIRouter(prefix="/api/v1/learning-path", tags=["learning-path"])


@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.user_id == current_user.id,
            LearningPath.course_id == course_id,
            LearningPath.is_deleted == False,
        )
    )
    lp = result.scalar_one_or_none()

    if lp is None:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": course_id,
                "nodes": [],
                "edges": [],
                "current_position": None,
                "generated_at": None,
            },
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": lp.course_id,
            "nodes": lp.nodes or [],
            "edges": lp.edges or [],
            "current_position": {
                "node_id": lp.current_node_id,
                "node_name": lp.current_node_name,
            } if lp.current_node_id else None,
            "generated_at": lp.generated_at.isoformat() if lp.generated_at else None,
        },
    }


async def _assemble_learning_path_payload(
    user_id: str, course_id: str, db: AsyncSession,
) -> dict:
    """组装调用 Agent /learning-path/generate 所需的 payload。"""
    payload: dict = {"user_id": user_id, "course_id": course_id}

    # evaluation: 最近一次评估
    ev_r = await db.execute(
        select(Evaluation)
        .where(Evaluation.user_id == user_id, Evaluation.course_id == course_id, Evaluation.is_deleted == False)
        .order_by(Evaluation.generated_at.desc())
    )
    ev = ev_r.scalars().first()
    payload["evaluation"] = {
        "progress_table": ev.progress_table,
        "mastery_table": ev.mastery_table,
        "summary_text": ev.summary_text,
    } if ev else {}

    # profile: 最近画像
    pf_r = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id == user_id, UserProfile.course_id == course_id, UserProfile.is_deleted == False)
    )
    pf = pf_r.scalar_one_or_none()
    payload["profile"] = {
        "modal_preference": pf.modal_preference,
        "guidance_level": pf.guidance_level_current,
        "knowledge_coordinates": pf.knowledge_coordinates,
    } if pf else {}

    # knowledge_graph: 课程静态知识图谱
    kg_r = await db.execute(
        select(CourseKnowledgeGraph)
        .where(CourseKnowledgeGraph.course_id == course_id, CourseKnowledgeGraph.is_deleted == False)
    )
    kg = kg_r.scalar_one_or_none()
    if kg:
        payload["knowledge_graph"] = {"nodes": kg.nodes or [], "edges": kg.edges or []}
    else:
        payload["knowledge_graph"] = {"nodes": [], "edges": []}

    return payload


@router.post("/refresh")
async def refresh_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """请求刷新学习路径。调用 Agent /learning-path/generate，成功后写入 LearningPath。"""
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

    task = AsyncTask(
        task_type="learning_path_refresh",
        status="processing",
        user_id=current_user.id,
        course_id=course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    try:
        payload = await _assemble_learning_path_payload(current_user.id, course_id, db)
        data = await agent_client.post_json("/agent/v1/learning-path/generate", payload)
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

    now = datetime.now(timezone.utc)
    cp = data.get("current_position") or {}
    lp = LearningPath(
        user_id=current_user.id,
        course_id=course_id,
        nodes=data.get("nodes", []),
        edges=data.get("edges", []),
        current_node_id=cp.get("node_id", ""),
        current_node_name=cp.get("node_name", ""),
        generated_at=now,
    )
    db.add(lp)
    task.status = "completed"
    task.result = {"updated_at": now.isoformat()}
    task.completed_at = now
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )


@router.get("/nodes/{node_id}/resources")
async def get_node_resources(node_id: str, current_user: User = Depends(get_current_user)):
    return {
        "code": 200,
        "message": "success",
        "data": {
            "node_id": node_id,
            "node_name": "示例知识点",
            "weak_point_tutorials": [],
            "exercises": [],
            "chapter_materials": [],
            "full_exercise_set": [],
        },
    }
