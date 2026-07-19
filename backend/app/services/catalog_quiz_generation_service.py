import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import AsyncTask
from app.models.quiz import QuizQuestion
from app.services.agent_client import AgentClient, AgentServiceError
from app.services.course_knowledge_graphs import get_active_knowledge_graph

logger = logging.getLogger(__name__)
quiz_agent_client = AgentClient(timeout=300.0)
QUIZ_GENERATION_CONCURRENCY = 2
QUIZ_BASELINE_SINGLE_COUNT = 3
QUIZ_BASELINE_MULTI_COUNT = 4


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def course_material_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40913, "message": "课程资料尚未完成入库", "data": None},
    )


def knowledge_base_empty() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40914, "message": "课程知识库为空", "data": None},
    )


def course_offering_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40915, "message": "课程资源库尚未绑定教学班", "data": None},
    )


class CatalogQuizGenerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_quiz_generation(
        self,
        catalog: CourseCatalog,
        *,
        actor_user_id: str,
    ) -> tuple[AsyncTask, list[str], list[str]]:
        if catalog.status != "ready":
            raise course_material_missing()
        if catalog.knowledge_status not in {"ready", "partial"}:
            raise course_material_missing()
        if (catalog.chunk_count or 0) <= 0:
            raise knowledge_base_empty()

        offerings_result = await self.db.execute(
            select(CourseOffering)
            .where(
                CourseOffering.catalog_id == catalog.id,
                CourseOffering.is_deleted == False,
            )
            .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
        )
        offerings = offerings_result.scalars().all()
        fanout_course_ids = [offering.id for offering in offerings]
        if not fanout_course_ids and catalog.kg_host_course_id:
            fanout_course_ids = [catalog.kg_host_course_id]
        if not fanout_course_ids:
            raise course_offering_missing()

        kg = await get_active_knowledge_graph(self.db, catalog.kg_host_course_id or "")
        if kg is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": 40917,
                    "message": "课程知识图谱未就绪",
                    "data": {"error_code": "kg_not_ready"},
                },
            )

        kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
        if not kg_nodes:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": 40918,
                    "message": "课程知识图谱节点为空",
                    "data": {"error_code": "kg_nodes_empty"},
                },
            )

        parent = AsyncTask(
            task_type="quiz_generation",
            status="processing",
            progress=10,
            user_id=actor_user_id,
            course_id=None,
            result={
                "catalog_id": catalog.id,
                "catalog_title": catalog.title,
                "agent_course_id": catalog.id,
                "fanout_course_ids": fanout_course_ids,
                "total_node_count": len(kg_nodes),
                "completed_node_count": 0,
                "failed_node_count": 0,
                "total_question_count": 0,
            },
        )
        self.db.add(parent)
        await self.db.flush()
        await self.db.refresh(parent)

        child_task_ids: list[str] = []
        for kg_node in kg_nodes:
            node_name = kg_node.get("name", "")
            chapter = kg_node.get("chapter", "")
            child = AsyncTask(
                task_type="quiz_generation",
                status="processing",
                progress=10,
                user_id=actor_user_id,
                course_id=fanout_course_ids[0],
                result={
                    "catalog_id": catalog.id,
                    "parent_task_id": parent.id,
                    "agent_course_id": catalog.id,
                    "node_name": node_name,
                    "chapter": chapter,
                    "course_ids": fanout_course_ids,
                    "fanout_catalog_id": catalog.id,
                },
            )
            self.db.add(child)
            await self.db.flush()
            child_task_ids.append(child.id)

        await self.db.commit()
        return parent, child_task_ids, fanout_course_ids


async def run_quiz_generation_background(
    parent_id: str,
    child_task_ids: list[str],
    fanout_course_ids: list[str],
) -> None:
    semaphore = asyncio.Semaphore(QUIZ_GENERATION_CONCURRENCY)

    async def _run_child(child_id: str) -> dict:
        async with semaphore:
            async with async_session_factory() as child_db:
                result = await generate_quiz_for_child(child_db, child_id, fanout_course_ids)
                await child_db.commit()
                return result

    results = await asyncio.gather(
        *[_run_child(child_id) for child_id in child_task_ids],
        return_exceptions=True,
    )

    async with async_session_factory() as db:
        parent_result = await db.execute(
            select(AsyncTask).where(AsyncTask.id == parent_id, AsyncTask.is_deleted == False)
        )
        parent = parent_result.scalar_one_or_none()
        if parent is None:
            logger.error("Quiz generation parent task missing: %s", parent_id)
            return

        completed = sum(
            1 for r in results if isinstance(r, dict) and r.get("status") == "completed"
        )
        failed = sum(
            1
            for r in results
            if isinstance(r, Exception) or (isinstance(r, dict) and r.get("status") == "failed")
        )
        total_qs = sum(
            (r.get("question_count") or 0)
            for r in results
            if isinstance(r, dict) and r.get("status") == "completed"
        )
        inserted_question_ids = [
            question_id
            for r in results
            if isinstance(r, dict)
            for question_id in (r.get("inserted_question_ids") or [])
        ]
        if inserted_question_ids:
            fanout_catalog_id = None
            for r in results:
                if isinstance(r, dict) and r.get("fanout_catalog_id"):
                    fanout_catalog_id = r["fanout_catalog_id"]
                    break
            if fanout_catalog_id:
                await db.execute(
                    update(QuizQuestion)
                    .where(
                        QuizQuestion.catalog_id == fanout_catalog_id,
                        QuizQuestion.source == "baseline",
                        QuizQuestion.is_deleted == False,
                        ~QuizQuestion.id.in_(inserted_question_ids),
                    )
                    .values(is_deleted=True)
                )
            else:
                for cid in fanout_course_ids:
                    await db.execute(
                        update(QuizQuestion)
                        .where(
                            QuizQuestion.course_id == cid,
                            QuizQuestion.source == "baseline",
                            QuizQuestion.is_deleted == False,
                            ~QuizQuestion.id.in_(inserted_question_ids),
                        )
                        .values(is_deleted=True)
                    )
        parent.status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
        parent.progress = 100
        parent.completed_at = now_utc()
        parent.result = {
            **parent.result,
            "completed_node_count": completed,
            "failed_node_count": failed,
            "total_question_count": total_qs,
            "inserted_question_count": len(inserted_question_ids),
        }
        await db.commit()


async def generate_quiz_for_child(
    db: AsyncSession,
    child_id: str,
    fanout_course_ids: list[str],
) -> dict:
    child_result = await db.execute(
        select(AsyncTask).where(AsyncTask.id == child_id, AsyncTask.is_deleted == False)
    )
    child = child_result.scalar_one_or_none()
    if child is None:
        return {"status": "failed", "error": "child task not found"}

    child_data = child.result or {}
    node_name = child_data.get("node_name", "")
    chapter = child_data.get("chapter") or ""
    course_ids = child_data.get("course_ids") or fanout_course_ids
    fanout_catalog_id = child_data.get("fanout_catalog_id")
    agent_course_id = child_data.get("agent_course_id") or child_data.get("catalog_id") or child.course_id or ""
    catalog_result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == agent_course_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = catalog_result.scalar_one_or_none()
    course_title = catalog.title if catalog else None

    try:
        questions = await generate_baseline_quiz_questions(
            child=child,
            agent_course_id=agent_course_id,
            course_title=course_title,
            course_ids=course_ids,
            chapter=chapter,
            node_name=node_name,
        )
        new_questions: list[QuizQuestion] = []
        inserted_question_ids: list[str] = []
        for cid in course_ids:
            for q in (questions if isinstance(questions, list) else []):
                if is_skeleton_quiz_question(q):
                    continue
                question_id = uuid4().hex[:16]
                inserted_question_ids.append(question_id)
                new_questions.append(
                    QuizQuestion(
                        id=question_id,
                        course_id=cid,
                        catalog_id=fanout_catalog_id,
                        chapter=chapter,
                        knowledge_point=node_name,
                        type=q.get("type", "single_choice"),
                        source="baseline",
                        personalized=False,
                        difficulty="medium",
                        content=q.get("content", ""),
                        options=q.get("options", []),
                        correct_answer=format_quiz_answer(q.get("answer", "")),
                        explanation=q.get("explanation", ""),
                    )
                )
        if not new_questions:
            child.status = "failed"
            child.progress = 100
            child.error_code = "skeleton_rejected"
            child.error_message = "Agent returned only skeleton fallback questions"
            child.completed_at = now_utc()
            child.result = {**child_data, "question_count": 0, "rejected_reason": "skeleton"}
            return {"status": "failed", "error": "skeleton_rejected"}
        for q in new_questions:
            db.add(q)

        child.status = "completed"
        child.progress = 100
        child.completed_at = now_utc()
        child.result = {
            **child_data,
            "agent_course_id": agent_course_id,
            "question_count": len(new_questions),
            "inserted_question_ids": inserted_question_ids,
        }
        return {
            "status": "completed",
            "question_count": len(new_questions),
            "inserted_question_ids": inserted_question_ids,
            "fanout_catalog_id": fanout_catalog_id,
        }
    except AgentServiceError as e:
        child.status = "failed"
        child.progress = 100
        child.error_code = str(e.agent_code or "agent_error")
        child.error_message = e.message
        child.completed_at = now_utc()
        return {"status": "failed", "error": e.message, "fanout_catalog_id": fanout_catalog_id}
    except Exception as e:
        child.status = "failed"
        child.progress = 100
        child.error_code = "unexpected_error"
        child.error_message = str(e)[:500]
        child.completed_at = now_utc()
        return {"status": "failed", "error": str(e)[:500], "fanout_catalog_id": fanout_catalog_id}


def build_baseline_quiz_payload(
    *,
    child: AsyncTask,
    agent_course_id: str,
    course_title: str | None,
    course_ids: list[str],
    chapter: str,
    node_name: str,
    question_types: list[str],
    count: int,
) -> dict:
    return {
        "task_id": child.id,
        "user_id": child.user_id or "",
        "course_id": agent_course_id,
        "course_title": course_title,
        "class_course_ids": course_ids,
        "chapter": chapter,
        "knowledge_point": node_name,
        "question_types": question_types,
        "count": count,
        "difficulty": "medium",
        "source": "baseline",
    }


async def request_baseline_quiz_questions(payload: dict) -> list[dict]:
    data = await quiz_agent_client.post_json(
        "/agent/v2/knowledge/quiz/generations",
        payload,
    )
    questions = data.get("questions") if isinstance(data, dict) else []
    if not isinstance(questions, list):
        return []
    return [question for question in questions if isinstance(question, dict)]


async def generate_baseline_quiz_questions(
    *,
    child: AsyncTask,
    agent_course_id: str,
    course_title: str | None,
    course_ids: list[str],
    chapter: str,
    node_name: str,
) -> list[dict]:
    bulk_payload = build_baseline_quiz_payload(
        child=child,
        agent_course_id=agent_course_id,
        course_title=course_title,
        course_ids=course_ids,
        chapter=chapter,
        node_name=node_name,
        question_types=(["single_choice"] * QUIZ_BASELINE_SINGLE_COUNT)
        + (["multi_choice"] * QUIZ_BASELINE_MULTI_COUNT),
        count=QUIZ_BASELINE_SINGLE_COUNT + QUIZ_BASELINE_MULTI_COUNT,
    )
    questions = await request_baseline_quiz_questions(bulk_payload)
    if non_skeleton_quiz_questions(questions):
        return questions

    split_questions: list[dict] = []
    for question_type, count in (
        ("single_choice", QUIZ_BASELINE_SINGLE_COUNT),
        ("multi_choice", QUIZ_BASELINE_MULTI_COUNT),
    ):
        payload = build_baseline_quiz_payload(
            child=child,
            agent_course_id=agent_course_id,
            course_title=course_title,
            course_ids=course_ids,
            chapter=chapter,
            node_name=node_name,
            question_types=[question_type],
            count=count,
        )
        batch_questions = await request_baseline_quiz_questions(payload)
        split_questions.extend(non_skeleton_quiz_questions(batch_questions))
    return split_questions


def non_skeleton_quiz_questions(questions: list[dict]) -> list[dict]:
    return [
        question
        for question in questions
        if isinstance(question, dict) and not is_skeleton_quiz_question(question)
    ]


def format_quiz_answer(answer) -> str:
    if isinstance(answer, list):
        return ",".join(str(item).strip() for item in answer if str(item).strip())
    return str(answer or "").strip()


def quiz_option_text(option) -> str:
    if isinstance(option, dict):
        return str(option.get("text") or option.get("label") or option.get("content") or "").strip()
    return str(option or "").strip()


def is_skeleton_quiz_question(question: dict) -> bool:
    if not isinstance(question, dict):
        return False
    content = str(question.get("content") or "")
    if "请围绕" not in content or "完成一道" not in content:
        return False
    options = question.get("options")
    if not isinstance(options, list):
        return False
    option_texts = [quiz_option_text(option) for option in options]
    option_texts = [text for text in option_texts if text]
    return option_texts == ["正确表述", "易混淆表述", "相关补充表述", "无关表述"]
