import asyncio
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.others import Evaluation, LearningPath, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.schemas.operations import QuizGenerateRequest, QuizSubmitRequest
from app.services.agent_client import AgentServiceError, agent_client

logger = logging.getLogger(__name__)


async def assemble_generate_payload(
    user_id: str,
    class_course_id: str,
    agent_course_id: str,
    req: QuizGenerateRequest,
    db: AsyncSession,
) -> dict:
    """组装调用 Agent /assessment/generate-questions 所需的 payload。"""
    payload: dict = {
        "user_id": user_id,
        "course_id": agent_course_id,
        "class_course_id": class_course_id,
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

    if req.personalized:
        ctx: dict = {}

        ev_result = await db.execute(
            select(Evaluation)
            .where(Evaluation.user_id == user_id, Evaluation.course_id == class_course_id, Evaluation.is_deleted == False)
            .order_by(Evaluation.generated_at.desc())
        )
        ev = ev_result.scalars().first()
        if ev:
            ctx["evaluation"] = {"summary": ev.summary_text}

        pf_result = await db.execute(
            select(UserProfile)
            .where(UserProfile.user_id == user_id, UserProfile.course_id == class_course_id, UserProfile.is_deleted == False)
        )
        pf = pf_result.scalar_one_or_none()
        if pf:
            ctx["profile"] = {
                "guidance_level": pf.guidance_level_current,
                "blindspots": pf.cognitive_blindspots,
            }

        wrong_r = await db.execute(
            select(QuizQuestion.knowledge_point)
            .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
            .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
            .where(
                QuizSession.user_id == user_id,
                QuizSession.course_id == class_course_id,
                QuizSession.is_deleted == False,
                QuizAnswer.is_correct == False,
                QuizAnswer.is_deleted == False,
                QuizQuestion.course_id == class_course_id,
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
            .where(LearningPath.user_id == user_id, LearningPath.course_id == class_course_id, LearningPath.is_deleted == False)
        )
        lp = lp_result.scalar_one_or_none()
        if lp and lp.current_node_name:
            ctx["current_path_node"] = {"name": lp.current_node_name}

        if ctx:
            payload["personalization_context"] = ctx

    return payload


async def run_diagnosis_background(
    quiz_id: str,
    user_id: str,
    course_id: str,
    agent_questions: list[dict],
    agent_answers: list[dict],
) -> None:
    """后台异步调用 Agent /assessment/evaluate 并将 LLM 诊断写入 QuizSession.diagnosis_json。"""
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


async def _load_quiz_questions(db: AsyncSession, q_ids: list[str]) -> dict[str, QuizQuestion]:
    """批量预取所有题目。"""
    if not q_ids:
        return {}
    q_batch = await db.execute(
        select(QuizQuestion).where(QuizQuestion.id.in_(q_ids), QuizQuestion.is_deleted == False)
    )
    return {q.id: q for q in q_batch.scalars().all()}


def _grade_submission(
    answers: list[dict], questions_by_id: dict[str, QuizQuestion]
) -> tuple[int, list[dict], list[dict], list[dict]]:
    """比对提交答案与正确答案进行评分，并构建诊断 payload。"""
    correct_count = 0
    per_question_results = []
    agent_questions = []
    agent_answers = []

    for ans in answers:
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
            is_correct = False
            correct_answer = ""

        if is_correct:
            correct_count += 1

        per_question_results.append({
            "question_id": q_id,
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "explanation": explanation or None,
        })

    return correct_count, per_question_results, agent_questions, agent_answers


async def _persist_quiz_answers(
    db: AsyncSession,
    quiz_id: str,
    answers: list[dict],
    questions_by_id: dict[str, QuizQuestion],
    per_question_results: list[dict],
) -> None:
    """持久化写库 QuizAnswer 实体。"""
    for idx, ans in enumerate(answers):
        q_id = ans.get("question_id", "")
        user_answer = ans.get("answer", "")
        question = questions_by_id.get(q_id)
        if question:
            res_item = per_question_results[idx]
            answer_record = QuizAnswer(
                quiz_id=quiz_id,
                question_id=q_id,
                user_answer=str(user_answer),
                is_correct=res_item["is_correct"],
                correct_answer=res_item["correct_answer"],
                explanation=res_item["explanation"] or "",
            )
            db.add(answer_record)


async def submit_quiz_answers(
    req: QuizSubmitRequest, user_id: str, db: AsyncSession
) -> tuple[dict, list[dict], list[dict], str]:
    """主编排逻辑：题目拉取 -> 判分 -> 写库 -> 返回结果元组。"""
    # 1. 校验会话
    result = await db.execute(
        select(QuizSession).where(QuizSession.id == req.quiz_id, QuizSession.is_deleted == False)
    )
    quiz = result.scalar_one_or_none()
    if quiz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "练习不存在", "data": None},
        )

    # 2. 拉取题目
    q_ids = [a.get("question_id", "") for a in req.answers]
    questions_by_id = await _load_quiz_questions(db, q_ids)

    # 3. 评分比对
    correct_count, per_question_results, agent_questions, agent_answers = _grade_submission(
        req.answers, questions_by_id
    )

    # 4. 写库持久化
    await _persist_quiz_answers(db, req.quiz_id, req.answers, questions_by_id, per_question_results)

    total = len(req.answers)
    score = (correct_count / total * 100) if total > 0 else 0
    quiz.score = score
    quiz.correct_count = correct_count
    quiz.total_count = total
    quiz.time_spent = req.time_spent
    await db.flush()

    res_data = {
        "quiz_id": req.quiz_id,
        "score": round(score, 1),
        "correct_count": correct_count,
        "total_count": total,
        "time_spent": req.time_spent,
        "per_question_results": per_question_results,
    }

    return res_data, agent_questions, agent_answers, quiz.course_id
