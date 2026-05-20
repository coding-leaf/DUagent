from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask
from app.models.quiz import Question, QuizAnswer, QuizSession
from app.models.user import User
from app.schemas.operations import QuizSubmitRequest

router = APIRouter(prefix="/api/v1/quiz", tags=["quiz"])


@router.get("/questions")
async def get_questions(
    course_id: str = Query(...),
    chapter: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Question).where(Question.course_id == course_id)
    if chapter:
        query = query.where(Question.chapter == chapter)

    result = await db.execute(query)
    questions = result.scalars().all()

    if not questions:
        # Return sample questions if DB is empty
        questions = [
            Question(
                id="q_sample_1",
                course_id=course_id,
                chapter=chapter or "第1章",
                type="single_choice",
                content="示例题目：以下哪个是正确选项？",
                options=[{"key": "A", "text": "选项A"}, {"key": "B", "text": "选项B"}, {"key": "C", "text": "选项C"}, {"key": "D", "text": "选项D"}],
                correct_answer="A",
                explanation="A 是正确答案因为...",
            ),
            Question(
                id="q_sample_2",
                course_id=course_id,
                chapter=chapter or "第1章",
                type="multi_choice",
                content="示例多选题：请选择所有正确的选项。",
                options=[{"key": "A", "text": "选项A"}, {"key": "B", "text": "选项B"}, {"key": "C", "text": "选项C"}],
                correct_answer='["A","C"]',
                explanation="A 和 C 是正确答案。",
            ),
        ]

    quiz_session = QuizSession(
        user_id=current_user.id,
        course_id=course_id,
        chapter=chapter or "",
        total_count=len(questions),
    )
    db.add(quiz_session)
    await db.flush()
    await db.refresh(quiz_session)

    question_list = []
    for q in questions:
        q_data = {
            "id": q.id,
            "type": q.type,
            "content": q.content,
            "options": q.options if q.type in ("single_choice", "multi_choice") else None,
        }
        question_list.append(q_data)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "quiz_id": quiz_session.id,
            "course_id": course_id,
            "chapter": chapter or "",
            "questions": question_list,
            "total_count": len(question_list),
        },
    }


@router.post("/submit")
async def submit_answers(
    req: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get quiz session
    result = await db.execute(select(QuizSession).where(QuizSession.id == req.quiz_id))
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

        q_result = await db.execute(select(Question).where(Question.id == q_id))
        question = q_result.scalar_one_or_none()

        is_correct = False
        correct_answer = ""
        explanation = ""

        if question:
            correct_answer = question.correct_answer
            explanation = question.explanation

            if question.type == "multi_choice":
                user_sorted = sorted(user_answer) if isinstance(user_answer, list) else sorted(str(user_answer))
                correct_sorted = sorted(eval(correct_answer)) if correct_answer.startswith("[") else sorted(correct_answer.split(","))
                is_correct = user_sorted == correct_sorted
            else:
                is_correct = str(user_answer).strip().upper() == str(correct_answer).strip().upper()
        else:
            # Question not in DB, treat as correct for demo
            is_correct = True
            correct_answer = str(user_answer)

        if is_correct:
            correct_count += 1

        per_question_results.append({
            "question_id": q_id,
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "explanation": explanation,
        })

    score = (correct_count / total * 100) if total > 0 else 0
    quiz.score = score
    quiz.correct_count = correct_count
    quiz.total_count = total
    quiz.time_spent = req.time_spent
    await db.flush()

    # Create async task for LLM diagnosis
    task = AsyncTask(
        task_type="quiz_diagnosis",
        status="processing",
        user_id=current_user.id,
        course_id=quiz.course_id,
    )
    db.add(task)
    await db.flush()

    # Simulate async diagnosis completion
    task.status = "completed"
    task.result = {"diagnosis": "基于你的答题情况，建议重点复习以下知识点..."}
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
    # Latest quiz
    qr = await db.execute(
        select(QuizSession)
        .where(QuizSession.user_id == current_user.id, QuizSession.course_id == course_id)
        .order_by(QuizSession.created_at.desc())
    )
    latest = qr.scalars().first()

    # Stats
    all_qr = await db.execute(
        select(QuizSession).where(
            QuizSession.user_id == current_user.id, QuizSession.course_id == course_id
        )
    )
    all_quizzes = all_qr.scalars().all()
    total_attempts = max(len(all_quizzes), 1)
    avg_score = sum(q.score for q in all_quizzes) / total_attempts
    avg_time = sum(q.time_spent for q in all_quizzes) / total_attempts

    score_trend = [
        {"date": q.created_at.strftime("%Y-%m-%d") if q.created_at else "", "score": q.score}
        for q in all_quizzes[-10:]
    ]

    latest_data = None
    if latest:
        latest_data = {
            "quiz_id": latest.id,
            "score": latest.score,
            "time_spent": latest.time_spent,
            "created_at": latest.created_at.isoformat() if latest.created_at else "",
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
                "weak_points": [
                    {"name": "进阶概念", "error_rate": 0.6},
                ],
                "suggestions": [
                    "多练习进阶应用题",
                    "回顾基础定义",
                ],
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
        QuizSession.user_id == current_user.id, QuizSession.course_id == course_id
    )

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(QuizSession.created_at.desc()).offset(offset).limit(page_size))
    records = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": [
            {
                "quiz_id": r.id,
                "course_id": r.course_id,
                "chapter": r.chapter,
                "score": r.score,
                "time_spent": r.time_spent,
                "question_count": r.total_count,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
