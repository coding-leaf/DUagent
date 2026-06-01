import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, CourseKnowledgeGraph, Evaluation, LearningPath, Resource, UserProfile
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/learning-path", tags=["learning-path"])


async def _acquire_learning_path_lock(db: AsyncSession, user_id: str, course_id: str) -> str:
    """Acquire a MySQL named lock for serializing learning-path writes."""
    lock_name = f"learningpath_{user_id}_{course_id}"
    lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
    if not lock_result.scalar():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        )
    return lock_name


async def _release_learning_path_lock(db: AsyncSession, lock_name: str) -> None:
    """Release a previously acquired MySQL named lock for learning-path writes."""
    await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})


@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 永远读最新一条（幂等写入可能遗留多行在软删窗口期）
    result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.user_id == current_user.id,
            LearningPath.course_id == course_id,
            LearningPath.is_deleted == False,
        )
        .order_by(LearningPath.generated_at.desc())
    )
    lp = result.scalars().first()

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
        .order_by(UserProfile.generated_at.desc())
    )
    pf = pf_r.scalars().first()
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
    kg = kg_r.scalars().first()
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
    await db.commit()

    try:
        payload = await _assemble_learning_path_payload(current_user.id, course_id, db)
        data = await agent_client.post_json("/agent/v1/learning-path/generate", payload)

        lock_name = await _acquire_learning_path_lock(db, current_user.id, course_id)
        try:
            now = datetime.now(timezone.utc)
            old_result = await db.execute(
                select(LearningPath).where(
                    LearningPath.user_id == current_user.id,
                    LearningPath.course_id == course_id,
                    LearningPath.is_deleted == False,
                )
            )
            for old in old_result.scalars().all():
                old.is_deleted = True

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
            await db.commit()
        finally:
            await _release_learning_path_lock(db, lock_name)
    except AgentServiceError as e:
        await db.rollback()
        task.status = "failed"
        task.error_code = str(e.agent_code or "agent_error")
        task.error_message = e.message
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()
    except HTTPException as e:
        await db.rollback()
        if task.status == "processing":
            task.status = "failed"
            task.error_code = "lock_timeout"
            task.error_message = "服务繁忙，请稍后重试"
            task.completed_at = datetime.now(timezone.utc)
            await db.flush()
            await db.commit()
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(
            "Learning path refresh: unexpected error user_id=%s course_id=%s type=%s message=%s",
            current_user.id, course_id, type(e).__name__, str(e),
        )
        task.status = "failed"
        task.error_code = "internal_error"
        task.error_message = str(e)[:500]
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )


@router.get("/nodes/{node_id}/resources")
async def get_node_resources(
    node_id: str,
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定学习路径节点的关联资源。

    从 LearningPath.nodes 中查找节点名称，从 Resource/QuizQuestion 表中
    按 knowledge_point 和 chapter 匹配资源并分组返回。
    """
    # 课程权限校验：学生需已加入课程
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

    node_name = node_id
    chapter = ""

    # 1. 查找用户在该课程的最新学习路径
    lp_result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.user_id == current_user.id,
            LearningPath.course_id == course_id,
            LearningPath.is_deleted == False,
        )
        .order_by(LearningPath.generated_at.desc())
    )
    lp = lp_result.scalars().first()
    if lp and lp.nodes:
        nodes = lp.nodes if isinstance(lp.nodes, list) else []
        for node in nodes:
            if isinstance(node, dict) and node.get("id") == node_id:
                node_name = node.get("name", node_id)
                break

    # 2. 从知识图谱获取 chapter（schema 约定 [{id, name, chapter}]）
    kg_result = await db.execute(
        select(CourseKnowledgeGraph)
        .where(
            CourseKnowledgeGraph.course_id == course_id,
            CourseKnowledgeGraph.is_deleted == False,
        )
    )
    kg = kg_result.scalars().first()
    if kg and kg.nodes:
        kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
        for kg_node in kg_nodes:
            if isinstance(kg_node, dict) and kg_node.get("id") == node_id:
                chapter = kg_node.get("chapter", "")
                break

    # 3. weak_point_tutorials: Resource 按 knowledge_point 匹配
    weak_point_tutorials = []
    res_result = await db.execute(
        select(Resource)
        .where(
            Resource.course_id == course_id,
            Resource.knowledge_point == node_name,
            Resource.is_deleted == False,
        )
    )
    for r in res_result.scalars().all():
        weak_point_tutorials.append({
            "title": r.title,
            "content": r.content or "",
        })

    # 4. exercises: QuizQuestion 按 knowledge_point 匹配
    exercises = []
    qq_result = await db.execute(
        select(QuizQuestion)
        .where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.knowledge_point == node_name,
            QuizQuestion.is_deleted == False,
        )
    )
    for q in qq_result.scalars().all():
        exercises.append({
            "id": q.id,
            "type": q.type,
            "content": q.content,
        })

    # 5. chapter_materials: Resource 按 chapter 匹配（依赖 KG 预置数据）
    chapter_materials = []
    if chapter:
        ch_result = await db.execute(
            select(Resource)
            .where(
                Resource.course_id == course_id,
                Resource.chapter == chapter,
                Resource.is_deleted == False,
            )
        )
        for r in ch_result.scalars().all():
            chapter_materials.append({
                "title": r.title,
                "type": r.type,
                "url": r.url or "",
            })

    # 6. full_exercise_set: 课程全部 QuizQuestion（限 50 条）
    full_exercise_set = []
    all_qq_result = await db.execute(
        select(QuizQuestion)
        .where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.is_deleted == False,
        )
        .limit(50)
    )
    for q in all_qq_result.scalars().all():
        full_exercise_set.append({
            "id": q.id,
            "type": q.type,
            "content": q.content,
        })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "node_id": node_id,
            "node_name": node_name,
            "weak_point_tutorials": weak_point_tutorials,
            "exercises": exercises,
            "chapter_materials": chapter_materials,
            "full_exercise_set": full_exercise_set,
        },
    }
