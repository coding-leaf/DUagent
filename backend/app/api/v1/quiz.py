import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.session import async_session_factory
from app.models.others import AsyncTask
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.schemas.operations import QuizGenerateRequest, QuizSubmitRequest
from app.models.catalog import CourseCatalog, CourseOffering
from app.services.agent_client import AgentServiceError, agent_client
from app.services import quiz_service
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.course_catalog_gate import resolve_generation_catalog
from app.services.resource_scope import resolve_course_resource_scope

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/quiz", tags=["quiz"])


def _submitted_quiz_sessions_query(user_id: str, course_id: str):
    """返回至少包含一条有效 QuizAnswer 的已提交练习查询。"""
    return select(QuizSession).where(
        QuizSession.user_id == user_id,
        QuizSession.course_id == course_id,
        QuizSession.is_deleted == False,
        exists().where(
            QuizAnswer.quiz_id == QuizSession.id,
            QuizAnswer.is_deleted == False,
        ),
    )


@router.get("/questions")
async def get_questions(
    course_id: str = Query(...),
    chapter: str = Query(None),
    knowledge_point: str = Query(None),
    type: str = Query(None),
    source: str = Query(None),
    node_id: str = Query(None),
    question_ids: str = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = await resolve_course_resource_scope(db, course_id)
    query = select(QuizQuestion).where(
        or_(
            and_(QuizQuestion.catalog_id.is_(None), QuizQuestion.course_id == course_id),
            QuizQuestion.catalog_id == scope.catalog_id,
        ),
        QuizQuestion.is_deleted == False,
        (QuizQuestion.source.in_(["common", "baseline"]))
        | ((QuizQuestion.source == "personalized") & (QuizQuestion.owner_user_id == current_user.id)),
    )
    if question_ids:
        # 如果传入了具体的题目 ID，直接过滤，忽略其它条件（或者保留基础过滤），并忽略 limit
        ids_list = [qid.strip() for qid in question_ids.split(",") if qid.strip()]
        if ids_list:
            query = query.where(QuizQuestion.id.in_(ids_list))
    else:
        # 原有的条件过滤和 limit 仅在没有明确 question_ids 时生效
        if chapter:
            query = query.where(QuizQuestion.chapter == chapter)
        if knowledge_point:
            query = query.where(QuizQuestion.knowledge_point == knowledge_point)
        if type:
            query = query.where(QuizQuestion.type == type)
        if source:
            query = query.where(QuizQuestion.source == source)

        if node_id:
            kg_node_name = node_id
            kg = await get_active_knowledge_graph(db, course_id)
            if kg is None:
                offering_result = await db.execute(
                    select(CourseOffering).where(
                        CourseOffering.id == course_id,
                        CourseOffering.is_deleted == False,
                    )
                )
                offering = offering_result.scalar_one_or_none()
                if offering is not None:
                    catalog_result = await db.execute(
                        select(CourseCatalog).where(
                            CourseCatalog.id == offering.catalog_id,
                            CourseCatalog.is_deleted == False,
                        )
                    )
                    catalog = catalog_result.scalar_one_or_none()
                    if catalog is not None and catalog.kg_host_course_id:
                        kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id)
            if kg and kg.nodes:
                kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
                for kg_node in kg_nodes:
                    if isinstance(kg_node, dict) and kg_node.get("id") == node_id:
                        kg_node_name = kg_node.get("name", node_id)
                        break
            query = query.where(QuizQuestion.knowledge_point == kg_node_name)

        query = query.limit(limit)

    result = await db.execute(query)
    questions = result.scalars().all()

    quiz_session = QuizSession(
        user_id=current_user.id,
        course_id=course_id,
        chapter=chapter or "",
        total_count=len(questions),
    )
    db.add(quiz_session)
    await db.flush()
    await db.refresh(quiz_session)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "quiz_id": quiz_session.id,
            "course_id": course_id,
            "chapter": chapter or "",
            "questions": [
                {
                    "id": q.id,
                    "type": q.type,
                    "source": q.source,
                    "personalized": q.personalized,
                    "chapter": q.chapter,
                    "knowledge_point": q.knowledge_point,
                    "difficulty": q.difficulty,
                    "content": q.content,
                    "options": q.options if q.options is not None else [],
                }
                for q in questions
            ],
            "total_count": len(questions),
        },
    }


@router.post("/generate")
async def generate_questions(
    req: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成个性化题目。调用 Agent /assessment/generate-questions，校验后写入 quiz_questions。"""
    catalog_context = await resolve_generation_catalog(db, req.course_id)

    task = AsyncTask(
        task_type="quiz_generation",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
        result=catalog_context.model_dump(),
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    try:
        payload = await quiz_service.assemble_generate_payload(
            current_user.id,
            req.course_id,
            catalog_context.catalog_id,
            req,
            db,
        )
        data = await agent_client.post_json("/agent/v1/assessment/generate-questions", payload)
    except AgentServiceError as e:
        task.status = "failed"
        task.error_code = str(e.agent_code or "agent_error")
        task.error_message = e.message
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return JSONResponse(
            status_code=202,
            content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
        )

    # 校验 Agent 返回并写入 quiz_questions
    questions = data.get("questions", [])
    question_ids: list[str] = []
    for q in questions:
        new_q = QuizQuestion(
            course_id=req.course_id,
            chapter=q.get("chapter", req.chapter or ""),
            knowledge_point=q.get("knowledge_point", req.knowledge_point or ""),
            type=q.get("type", "single_choice"),
            source="personalized",
            personalized=True,
            owner_user_id=current_user.id,
            difficulty=q.get("difficulty", req.difficulty or "medium"),
            content=q.get("content", ""),
            options=q.get("options", []),
            correct_answer=str(q.get("answer", "")),
            explanation=q.get("explanation", ""),
        )
        db.add(new_q)
        await db.flush()
        question_ids.append(new_q.id)

    task.status = "completed"
    task.result = {**catalog_context.model_dump(), "question_ids": question_ids}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )


@router.post("/submit")
async def submit_answers(
    req: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res_data, agent_questions, agent_answers, course_id = await quiz_service.submit_quiz_answers(
        req, current_user.id, db
    )

    # 后台异步调用 Agent /assessment/evaluate 生成 LLM 诊断
    asyncio.create_task(quiz_service.run_diagnosis_background(
        quiz_id=req.quiz_id,
        user_id=current_user.id,
        course_id=course_id,
        agent_questions=agent_questions,
        agent_answers=agent_answers,
    ))

    return {
        "code": 200,
        "message": "success",
        "data": res_data,
    }


@router.get("/result")
async def get_result(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    qr = await db.execute(
        _submitted_quiz_sessions_query(current_user.id, course_id)
        .order_by(QuizSession.create_time.desc())
    )
    latest = qr.scalars().first()

    all_qr = await db.execute(
        _submitted_quiz_sessions_query(current_user.id, course_id)
        .order_by(QuizSession.create_time.asc())
    )
    all_quizzes = all_qr.scalars().all()
    total_attempts = len(all_quizzes)
    avg_score = sum(q.score for q in all_quizzes) / total_attempts if all_quizzes else 0
    avg_time = sum(q.time_spent for q in all_quizzes) / total_attempts if all_quizzes else 0

    score_trend = [
        {"date": q.create_time.strftime("%Y-%m-%d") if q.create_time else "", "score": q.score}
        for q in all_quizzes[-10:]
    ]

    # --- 数据驱动诊断：基于 QuizAnswer JOIN QuizQuestion 按 knowledge_point 聚合 ---
    kp_stats: dict[str, dict] = {}
    if all_quizzes:
        qa_result = await db.execute(
            select(QuizAnswer, QuizQuestion.knowledge_point)
            .join(QuizQuestion, QuizAnswer.question_id == QuizQuestion.id)
            .where(
                QuizAnswer.quiz_id.in_([q.id for q in all_quizzes]),
                QuizAnswer.is_deleted == False,
            )
        )
        for answer, knowledge_point in qa_result.all():
            kp = knowledge_point or "未分类"
            if kp not in kp_stats:
                kp_stats[kp] = {"total": 0, "incorrect": 0}
            kp_stats[kp]["total"] += 1
            if not answer.is_correct:
                kp_stats[kp]["incorrect"] += 1

    weak_points = []
    for kp, stats in kp_stats.items():
        if stats["total"] > 0:
            error_rate = round(stats["incorrect"] / stats["total"], 2)
            weak_points.append({"name": kp, "error_rate": error_rate})
    weak_points.sort(key=lambda x: x["error_rate"], reverse=True)
    weak_points = weak_points[:5]

    if not all_quizzes:
        summary = "暂无练习数据，完成练习后可查看诊断结果。"
    elif avg_score >= 90:
        summary = f"整体表现优秀，平均正确率 {avg_score:.1f}%。"
    elif avg_score >= 70:
        summary = f"整体表现良好，平均正确率 {avg_score:.1f}%。建议关注薄弱知识点。"
    elif avg_score >= 50:
        summary = f"平均正确率 {avg_score:.1f}%，还有提升空间，建议加强薄弱知识点练习。"
    else:
        summary = f"平均正确率 {avg_score:.1f}%，基础薄弱，建议从基础知识开始系统复习。"

    suggestions = []
    if weak_points:
        top_weak_names = [wp["name"] for wp in weak_points[:3]]
        suggestions.append(f"重点复习：{'、'.join(top_weak_names)}")
        suggestions.append("建议针对错题对应的知识点多做专项练习")
        if avg_score < 70:
            suggestions.append("回顾相关章节的基础概念和例题")
    elif all_quizzes:
        suggestions.append("继续保持当前学习节奏")
        suggestions.append("尝试挑战更高难度的练习")
    else:
        suggestions.append("进行一次练习以生成个性化诊断")

    # 诊断：优先消费 Agent LLM 诊断的 suggestions（现有契约内部分融合）
    # 从最新到最旧遍历 QuizSession，取第一条有效 Agent suggestions
    # summary 保持 SQL 模板（课程级），weak_points 始终 SQL 聚合
    diagnosis_data = None
    if all_quizzes:
        merged_suggestions = suggestions

        for session in reversed(all_quizzes):
            diag = session.diagnosis_json
            if not isinstance(diag, dict):
                continue
            agent_sug = diag.get("suggestions")
            # Agent 值仅在非空 list 且所有元素为非空 str 时覆盖
            if (
                isinstance(agent_sug, list)
                and len(agent_sug) > 0
                and all(isinstance(s, str) and s.strip() for s in agent_sug)
            ):
                merged_suggestions = agent_sug
                break

        diagnosis_data = {
            "summary": summary,
            "weak_points": weak_points,
            "suggestions": merged_suggestions,
        }
    # --- 诊断计算结束 ---

    latest_data = None
    if latest:
        latest_data = {
            "quiz_id": latest.id,
            "score": latest.score,
            "time_spent": latest.time_spent,
            "created_at": latest.create_time.isoformat() if latest.create_time else "",
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": course_id,
            "latest_quiz": latest_data,
            "stats": {
                "total_attempts": total_attempts,
                "avg_score": round(avg_score, 1),
                "avg_time_spent": int(avg_time),
                "score_trend": score_trend,
            },
            "diagnosis": diagnosis_data,
        },
    }


@router.get("/history")
async def get_history(
    course_id: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = _submitted_quiz_sessions_query(current_user.id, course_id)

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(QuizSession.create_time.desc()).offset(offset).limit(page_size)
    )
    records = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "records": [
                {
                    "quiz_id": r.id,
                    "course_id": r.course_id,
                    "chapter": r.chapter,
                    "score": r.score,
                    "time_spent": r.time_spent,
                    "question_count": r.total_count,
                    "created_at": r.create_time.isoformat() if r.create_time else "",
                }
                for r in records
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
