from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.others import AsyncTask
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.schemas.operations import QuizGenerateRequest, QuizSubmitRequest

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


@router.post("/generate")
async def generate_questions(
    req: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = AsyncTask(
        task_type="quiz_generation",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Simulate generation
    new_q = QuizQuestion(
        course_id=req.course_id,
        chapter=req.chapter or "",
        knowledge_point=req.knowledge_point or "",
        type=(req.question_types or ["single_choice"])[0],
        source="personalized",
        personalized=True,
        owner_user_id=current_user.id,
        difficulty=req.difficulty or "medium",
        content="个性化生成的示例题目（v1模拟）",
        options=[{"key": "A", "text": "选项A"}, {"key": "B", "text": "选项B"}],
        correct_answer="A",
    )
    db.add(new_q)
    await db.flush()

    task.status = "completed"
    task.result = {"question_ids": [new_q.id]}
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

    for ans in req.answers:
        q_id = ans.get("question_id", "")
        user_answer = ans.get("answer", "")

        q_result = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id == q_id, QuizQuestion.is_deleted == False)
        )
        question = q_result.scalar_one_or_none()

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
        else:
            is_correct = True
            correct_answer = str(user_answer)

        if is_correct:
            correct_count += 1

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

    # Create async task for LLM diagnosis
    task = AsyncTask(
        task_type="quiz_generation",
        status="processing",
        user_id=current_user.id,
        course_id=quiz.course_id,
    )
    db.add(task)
    await db.flush()
    task.status = "completed"
    task.result = {"updated_at": datetime.now(timezone.utc).isoformat()}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

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
        )
    )
    all_quizzes = all_qr.scalars().all()
    total_attempts = max(len(all_quizzes), 1)
    avg_score = sum(q.score for q in all_quizzes) / total_attempts if all_quizzes else 0
    avg_time = sum(q.time_spent for q in all_quizzes) / total_attempts if all_quizzes else 0

    score_trend = [
        {"date": q.create_time.strftime("%Y-%m-%d") if q.create_time else "", "score": q.score}
        for q in all_quizzes[-10:]
    ]

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
            "diagnosis": {
                "summary": "根据练习情况，你的整体表现良好。",
                "weak_points": [{"name": "进阶概念", "error_rate": 0.6}],
                "suggestions": ["多练习进阶应用题", "回顾基础定义"],
            },
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
