import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.session import async_session_factory
from app.models.others import AsyncTask
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.schemas.operations import QuizGenerateRequest, QuizSubmitRequest
from app.services.agent_client import AgentServiceError, agent_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/quiz", tags=["quiz"])


@router.get("/questions")
async def get_questions(
    course_id: str = Query(...),
    chapter: str = Query(None),
    knowledge_point: str = Query(None),
    type: str = Query(None),
    source: str = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(QuizQuestion).where(
        QuizQuestion.course_id == course_id,
        QuizQuestion.is_deleted == False,
        (QuizQuestion.source == "common")
        | ((QuizQuestion.source == "personalized") & (QuizQuestion.owner_user_id == current_user.id)),
    )
    if chapter:
        query = query.where(QuizQuestion.chapter == chapter)
    if knowledge_point:
        query = query.where(QuizQuestion.knowledge_point == knowledge_point)
    if type:
        query = query.where(QuizQuestion.type == type)
    if source:
        query = query.where(QuizQuestion.source == source)

    result = await db.execute(query.limit(limit))
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
                    "id": q.id, "type": q.type, "source": q.source,
                    "personalized": q.personalized, "content": q.content,
                    "options": q.options if q.options is not None else [],
                }
                for q in questions
            ],
            "total_count": len(questions),
        },
    }


async def _assemble_quiz_generate_payload(
    user_id: str, course_id: str, req: QuizGenerateRequest, db: AsyncSession,
) -> dict:
    """组装调用 Agent /assessment/generate-questions 所需的 payload。"""
    from app.models.others import Evaluation, LearningPath, UserProfile
    from app.models.quiz import QuizQuestion

    payload: dict = {
        "user_id": user_id,
        "course_id": course_id,
    }
    if req.chapter:
        payload["chapter"] = req.chapter
    if req.knowledge_point:
        payload["knowledge_point"] = req.knowledge_point
    if req.question_types:
        payload["question_types"] = req.question_types
    if req.count:
        payload["count"] = req.count
    if req.difficulty:
        payload["difficulty"] = req.difficulty
    payload["personalized"] = req.personalized

    # personalization_context: 评估、画像、错题、当前路径节点
    if req.personalized:
        ctx: dict = {}

        ev_result = await db.execute(
            select(Evaluation)
            .where(Evaluation.user_id == user_id, Evaluation.course_id == course_id, Evaluation.is_deleted == False)
            .order_by(Evaluation.generated_at.desc())
        )
        ev = ev_result.scalars().first()
        if ev:
            ctx["evaluation"] = {"summary": ev.summary_text}

        pf_result = await db.execute(
            select(UserProfile)
            .where(UserProfile.user_id == user_id, UserProfile.course_id == course_id, UserProfile.is_deleted == False)
        )
        pf = pf_result.scalar_one_or_none()
        if pf:
            ctx["profile"] = {
                "guidance_level": pf.guidance_level_current,
                "blindspots": pf.cognitive_blindspots,
            }

        # 用户最近错题知识点（显式 JOIN QuizSession + QuizAnswer + QuizQuestion）
        wrong_r = await db.execute(
            select(QuizQuestion.knowledge_point)
            .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
            .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
            .where(
                QuizSession.user_id == user_id,
                QuizSession.course_id == course_id,
                QuizSession.is_deleted == False,
                QuizAnswer.is_correct == False,
                QuizAnswer.is_deleted == False,
                QuizQuestion.course_id == course_id,
                QuizQuestion.is_deleted == False,
            )
            .order_by(QuizAnswer.create_time.desc())
            .limit(10)
        )
        seen = set()
        wrong_points = []
        for row in wrong_r:
            kp = row[0]
            if kp and kp not in seen:
                seen.add(kp)
                wrong_points.append({"name": kp})
        if wrong_points:
            ctx["wrong_points"] = wrong_points

        lp_result = await db.execute(
            select(LearningPath)
            .where(LearningPath.user_id == user_id, LearningPath.course_id == course_id, LearningPath.is_deleted == False)
        )
        lp = lp_result.scalar_one_or_none()
        if lp and lp.current_node_name:
            ctx["current_path_node"] = {"name": lp.current_node_name}

        if ctx:
            payload["personalization_context"] = ctx

    return payload


@router.post("/generate")
async def generate_questions(
    req: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成个性化题目。调用 Agent /assessment/generate-questions，校验后写入 quiz_questions。"""
    from app.services.agent_client import AgentServiceError, agent_client

    task = AsyncTask(
        task_type="quiz_generation",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    try:
        payload = await _assemble_quiz_generate_payload(current_user.id, req.course_id, req, db)
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
    task.result = {"question_ids": question_ids}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )


async def _run_diagnosis_background(
    quiz_id: str,
    user_id: str,
    course_id: str,
    agent_questions: list[dict],
    agent_answers: list[dict],
) -> None:
    """后台异步调用 Agent /assessment/evaluate 并将 LLM 诊断写入 QuizSession.diagnosis_json。

    设计约束：
    - 只接收原始标量 + 预组装的 payload（不接收请求级 ORM 实例或 db session）。
    - Agent 调用不依赖 DB session（消除竞态：请求事务未提交时后台任务读不到数据）。
    - 写入使用 UPDATE 直接设置 diagnosis_json，内部自行创建独立 DB session。
    - 失败时记录结构化日志，不抛异常。
    """
    # 1. 调用 Agent（无 DB 依赖）
    try:
        data = await agent_client.post_json("/agent/v1/assessment/evaluate", {
            "user_id": user_id,
            "course_id": course_id,
            "quiz_id": quiz_id,
            "questions": agent_questions,
            "answers": agent_answers,
        })
    except AgentServiceError as e:
        logger.error(
            "Diagnosis background: AgentServiceError quiz_id=%s course_id=%s user_id=%s "
            "status=%s agent_code=%s message=%s",
            quiz_id, course_id, user_id,
            e.status_code, e.agent_code, e.message,
        )
        return
    except Exception as e:
        logger.error(
            "Diagnosis background: unexpected error quiz_id=%s course_id=%s user_id=%s "
            "type=%s message=%s",
            quiz_id, course_id, user_id,
            type(e).__name__, str(e),
        )
        return

    diagnosis = data.get("diagnosis") if isinstance(data, dict) else None
    if not diagnosis or not isinstance(diagnosis, dict):
        logger.warning(
            "Diagnosis background: Agent returned no diagnosis quiz_id=%s course_id=%s user_id=%s "
            "response_keys=%s",
            quiz_id, course_id, user_id,
            list(data.keys()) if isinstance(data, dict) else type(data).__name__,
        )
        return

    # 2. 写入 DB（独立 session，UPDATE 直接设 diagnosis_json）
    async with async_session_factory() as db:
        try:
            result = await db.execute(
                update(QuizSession)
                .where(QuizSession.id == quiz_id)
                .values(diagnosis_json=diagnosis)
            )
            await db.commit()
            if result.rowcount:
                logger.info(
                    "Diagnosis background: stored diagnosis_json quiz_id=%s course_id=%s user_id=%s",
                    quiz_id, course_id, user_id,
                )
            else:
                logger.warning(
                    "Diagnosis background: UPDATE affected 0 rows quiz_id=%s (row may not be committed yet)",
                    quiz_id,
                )
        except Exception as e:
            await db.rollback()
            logger.error(
                "Diagnosis background: DB write failed quiz_id=%s type=%s message=%s",
                quiz_id, type(e).__name__, str(e),
            )


@router.post("/submit")
async def submit_answers(
    req: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(QuizSession).where(QuizSession.id == req.quiz_id, QuizSession.is_deleted == False)
    )
    quiz = result.scalar_one_or_none()
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "练习不存在", "data": None},
        )

    correct_count = 0
    total = len(req.answers)
    per_question_results = []

    # 批量预取所有题目，同时用于评分和后台 Agent 诊断 payload 组装
    q_ids = [a.get("question_id", "") for a in req.answers]
    q_batch = await db.execute(
        select(QuizQuestion).where(QuizQuestion.id.in_(q_ids), QuizQuestion.is_deleted == False)
    )
    questions_by_id = {q.id: q for q in q_batch.scalars().all()}

    agent_questions = []
    agent_answers = []

    for ans in req.answers:
        q_id = ans.get("question_id", "")
        user_answer = ans.get("answer", "")

        question = questions_by_id.get(q_id)

        is_correct = False
        correct_answer = ""
        explanation = ""

        if question:
            correct_answer = question.correct_answer
            explanation = question.explanation or ""
            if question.type == "multi_choice":
                user_sorted = sorted(user_answer) if isinstance(user_answer, list) else sorted(str(user_answer))
                try:
                    correct_sorted = sorted(eval(correct_answer)) if correct_answer.startswith("[") else sorted(correct_answer.split(","))
                except Exception:
                    correct_sorted = sorted(correct_answer.split(","))
                is_correct = user_sorted == correct_sorted
            else:
                is_correct = str(user_answer).strip().upper() == str(correct_answer).strip().upper()

            # 预组装 Agent 诊断 payload（消除竞态：后台任务不依赖 DB 读取）
            correct_for_agent = correct_answer
            if isinstance(correct_for_agent, str) and correct_for_agent.strip().startswith("["):
                try:
                    correct_for_agent = eval(correct_for_agent)
                except Exception:
                    pass
            agent_questions.append({
                "id": question.id,
                "type": question.type,
                "content": question.content,
                "options": question.options if question.options is not None else [],
                "correct_answer": correct_for_agent,
                "knowledge_point": question.knowledge_point,
            })
            agent_answers.append({"question_id": q_id, "answer": user_answer})
        else:
            # 不存在的 question_id：不计入正确，不创建 QuizAnswer（避免 FK 违规）
            is_correct = False
            correct_answer = ""

        if is_correct:
            correct_count += 1

        if question:
            answer_record = QuizAnswer(
                quiz_id=req.quiz_id,
                question_id=q_id,
                user_answer=str(user_answer),
                is_correct=is_correct,
                correct_answer=correct_answer,
                explanation=explanation,
            )
            db.add(answer_record)

        per_question_results.append({
            "question_id": q_id,
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "explanation": explanation or None,
        })

    score = (correct_count / total * 100) if total > 0 else 0
    quiz.score = score
    quiz.correct_count = correct_count
    quiz.total_count = total
    quiz.time_spent = req.time_spent
    await db.flush()

    # 后台异步调用 Agent /assessment/evaluate 生成 LLM 诊断
    # 传入预组装的 payload（消除竞态：后台任务不读 DB，只做 Agent 调用 + UPDATE）
    asyncio.create_task(_run_diagnosis_background(
        quiz_id=req.quiz_id,
        user_id=current_user.id,
        course_id=quiz.course_id,
        agent_questions=agent_questions,
        agent_answers=agent_answers,
    ))

    return {
        "code": 200,
        "message": "success",
        "data": {
            "quiz_id": req.quiz_id,
            "score": round(score, 1),
            "correct_count": correct_count,
            "total_count": total,
            "time_spent": req.time_spent,
            "per_question_results": per_question_results,
        },
    }


@router.get("/result")
async def get_result(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    qr = await db.execute(
        select(QuizSession)
        .where(
            QuizSession.user_id == current_user.id,
            QuizSession.course_id == course_id,
            QuizSession.is_deleted == False,
        )
        .order_by(QuizSession.create_time.desc())
    )
    latest = qr.scalars().first()

    all_qr = await db.execute(
        select(QuizSession).where(
            QuizSession.user_id == current_user.id,
            QuizSession.course_id == course_id,
            QuizSession.is_deleted == False,
        ).order_by(QuizSession.create_time.asc())
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
    # summary 保持 SQL 模板（课程级聚合，与 course-level weak_points 语义一致）
    # suggestions 优先用 Agent 生成（actionable，不受 per-session vs course-level 影响）
    # weak_points 始终 SQL 聚合
    diagnosis_data = None
    if all_quizzes:
        agent_diag = latest.diagnosis_json if latest and isinstance(latest.diagnosis_json, dict) else None

        if agent_diag:
            # suggestions：Agent 值仅在非空 list 且元素全为 str 时覆盖
            agent_sug = agent_diag.get("suggestions")
            merged_suggestions = (
                agent_sug
                if isinstance(agent_sug, list) and len(agent_sug) > 0
                and all(isinstance(s, str) for s in agent_sug)
                else suggestions
            )
        else:
            merged_suggestions = suggestions

        # summary 保持 SQL 模板（课程级），weak_points 保持 SQL 聚合
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
    query = select(QuizSession).where(
        QuizSession.user_id == current_user.id,
        QuizSession.course_id == course_id,
        QuizSession.is_deleted == False,
    )

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
