from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.code_problem import CodeProblem
from app.models.others import AsyncTask, Resource, UserPersonalizedResource
from app.models.quiz import QuizQuestion
from app.models.personalized_resource_generation import PersonalizedResourceGeneration
from app.models.user import User
from app.schemas.personalized import PersonalizedResourceGenerateRequest
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_catalog_gate import resolve_generation_catalog
from app.services import quiz_service
from app.schemas.internal_ai_chat import ChoiceQuestionDraft
from app.services.ai_chat_choice_quiz_service import persist_personal_choice_questions

router = APIRouter(prefix="/api/v1/personalized-resources", tags=["personalized-resources"])


def _webhook_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/webhooks/agent"


@router.get("")
async def list_personalized_resources(
    course_id: str = Query(...),
    source_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(UserPersonalizedResource).where(
        UserPersonalizedResource.user_id == current_user.id,
        UserPersonalizedResource.course_id == course_id,
        UserPersonalizedResource.is_deleted == False,
    )
    if source_type:
        query = query.where(UserPersonalizedResource.source_type == source_type)

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(UserPersonalizedResource.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    uprs = result.scalars().all()

    # Preload related resources, questions and private code problems.
    resource_ids = [u.resource_id for u in uprs if u.resource_id]
    question_ids = [u.question_id for u in uprs if u.question_id]
    code_problem_ids = [u.code_problem_id for u in uprs if u.code_problem_id]
    task_ids = [u.task_id for u in uprs if u.task_id]

    resources_map: dict = {}
    if resource_ids:
        res_r = await db.execute(
            select(Resource).where(Resource.id.in_(resource_ids), Resource.is_deleted == False)
        )
        resources_map = {r.id: r for r in res_r.scalars().all()}

    questions_map: dict = {}
    if question_ids:
        q_r = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id.in_(question_ids), QuizQuestion.is_deleted == False)
        )
        questions_map = {q.id: q for q in q_r.scalars().all()}

    code_problems_map: dict = {}
    if code_problem_ids:
        cp_r = await db.execute(
            select(CodeProblem).where(
                CodeProblem.id.in_(code_problem_ids),
                CodeProblem.owner_user_id == current_user.id,
                CodeProblem.is_deleted == False,
            )
        )
        code_problems_map = {problem.id: problem for problem in cp_r.scalars().all()}

    generations_by_target: dict[str, PersonalizedResourceGeneration] = {}
    if resource_ids or code_problem_ids:
        generation_result = await db.execute(
            select(PersonalizedResourceGeneration).where(
                PersonalizedResourceGeneration.user_id == current_user.id,
                PersonalizedResourceGeneration.course_id == course_id,
                PersonalizedResourceGeneration.is_deleted == False,
                or_(
                    PersonalizedResourceGeneration.published_resource_id.in_(resource_ids),
                    PersonalizedResourceGeneration.published_code_problem_id.in_(code_problem_ids),
                ),
            )
        )
        for generation in generation_result.scalars().all():
            target_id = generation.published_resource_id or generation.published_code_problem_id
            if target_id:
                generations_by_target[target_id] = generation

    tasks_map: dict = {}
    if task_ids:
        t_r = await db.execute(
            select(AsyncTask).where(AsyncTask.id.in_(task_ids), AsyncTask.is_deleted == False)
        )
        tasks_map = {t.id: t for t in t_r.scalars().all()}

    # processing_count: 全量统计（不限当前页），前端据此决定是否继续轮询
    pc_r = await db.execute(
        select(func.count()).select_from(
            select(UserPersonalizedResource.id)
            .join(AsyncTask, AsyncTask.id == UserPersonalizedResource.task_id)
            .where(
                UserPersonalizedResource.user_id == current_user.id,
                UserPersonalizedResource.course_id == course_id,
                UserPersonalizedResource.is_deleted == False,
                AsyncTask.status == "processing",
            )
            .subquery()
        )
    )
    processing_count = pc_r.scalar() or 0

    items = []
    for u in uprs:
        task = tasks_map.get(u.task_id) if u.task_id else None
        task_status = task.status if task else None
        generation = generations_by_target.get(u.resource_id or u.code_problem_id or "")

        resource_data = None
        if u.resource_id:
            r = resources_map.get(u.resource_id)
            if r:
                resource_data = {
                    "id": r.id,
                    "title": r.title,
                    "type": r.type,
                    "description": r.description or "",
                    "chapter": r.chapter,
                    "knowledge_point": r.knowledge_point,
                }

        question_data = None
        if u.question_id:
            q = questions_map.get(u.question_id)
            if q:
                question_data = {
                    "id": q.id,
                    "type": q.type,
                    "content": q.content,
                    "options": q.options or [],
                    "knowledge_point": q.knowledge_point,
                    "chapter": q.chapter,
                    "difficulty": q.difficulty,
                }

        code_problem_data = None
        if u.code_problem_id:
            problem = code_problems_map.get(u.code_problem_id)
            if problem:
                code_problem_data = {
                    "id": problem.id,
                    "title": problem.title,
                    "language": problem.language,
                    "difficulty": problem.difficulty,
                    "chapter": problem.chapter,
                    "knowledge_point": problem.knowledge_point,
                }

        items.append({
            "id": u.id,
            "source_type": u.source_type,
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "task_id": u.task_id,
            "task_status": task_status,
            "generation_status": generation.status if generation else None,
            "review_decision": generation.review_decision if generation else None,
            "review_warnings": (
                (generation.review_report or {}).get("warnings", []) if generation else []
            ),
            "resource_type": generation.resource_type if generation else None,
            "resource": resource_data,
            "question": question_data,
            "code_problem": code_problem_data,
        })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "processing_count": processing_count,
        },
    }


@router.post("/generate")
async def generate_personalized_resource(
    req: PersonalizedResourceGenerateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    catalog_context = await resolve_generation_catalog(db, req.course_id)

    if req.generate_type == "quiz":
        # ------- Quiz 生成路径（同步，Agent 直接返回题目）-------
        from app.schemas.operations import QuizGenerateRequest

        quiz_req = QuizGenerateRequest(
            course_id=req.course_id,
            chapter=req.chapter,
            knowledge_point=req.knowledge_point,
            question_types=req.question_types,
            count=req.count,
            difficulty=req.difficulty,
            personalized=True,
        )
        payload = await quiz_service.assemble_generate_payload(
            current_user.id,
            req.course_id,
            catalog_context.catalog_id,
            catalog_context.catalog_title,
            quiz_req,
            db,
        )

        # 若有错题 ID，查询错题内容并写入 wrong_points（覆盖历史错题上下文）
        if req.wrong_question_ids:
            wrong_r = await db.execute(
                select(QuizQuestion.id, QuizQuestion.content, QuizQuestion.knowledge_point)
                .where(
                    QuizQuestion.id.in_(req.wrong_question_ids),
                    QuizQuestion.is_deleted == False,
                )
            )
            wrong_points = [
                {"name": row.knowledge_point or "", "content": (row.content or "")[:200]}
                for row in wrong_r.all()
            ]
            if wrong_points:
                ctx = payload.get("personalization_context") or {}
                ctx["wrong_points"] = wrong_points
                payload["personalization_context"] = ctx

        try:
            data = await agent_client.post_json("/agent/v2/knowledge/quiz/generations", payload)
        except AgentServiceError as e:
            return JSONResponse(
                status_code=500,
                content={"code": 500, "message": f"Agent 调用失败: {e.message}", "data": None},
            )

        questions = data.get("questions", [])
        try:
            drafts = [ChoiceQuestionDraft.model_validate(question) for question in questions]
        except ValidationError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "code": 502,
                    "message": "Agent 返回了不受支持或不完整的选择题",
                    "data": {"reason": str(exc.errors()[0].get("type", "validation_error"))},
                },
            )
        chapter = req.chapter or (questions[0].get("chapter", "") if questions else "")
        knowledge_point = req.knowledge_point or (
            questions[0].get("knowledge_point", "") if questions else ""
        )
        question_ids = await persist_personal_choice_questions(
            db,
            owner_user_id=current_user.id,
            course_id=req.course_id,
            catalog_id=catalog_context.catalog_id,
            chapter=chapter,
            knowledge_point=knowledge_point,
            source_type=req.source_type,
            questions=drafts,
        )

        await db.flush()
        await db.commit()

        return JSONResponse(
            status_code=202,
            content={
                "code": 202,
                "message": "accepted",
                "data": {"generate_type": "quiz", "question_count": len(question_ids)},
            },
        )

    else:
        # ------- Resource 生成路径（异步 Webhook）-------
        task = AsyncTask(
            task_type="resource_generation",
            status="processing",
            user_id=current_user.id,
            course_id=req.course_id,
            result=catalog_context.model_dump(),
        )
        db.add(task)
        await db.flush()
        await db.refresh(task)

        is_goal_generation = bool(req.goal)
        res_payload: dict = {
            "task_id": task.id,
            "user_id": current_user.id,
            "course_id": req.course_id if is_goal_generation else catalog_context.catalog_id,
            "course_title": catalog_context.catalog_title,
            "webhook_url": _webhook_url(request),
        }
        if req.goal:
            res_payload["goal"] = req.goal
        if req.chapter:
            res_payload["chapter"] = req.chapter
        if req.knowledge_point:
            res_payload["knowledge_point"] = req.knowledge_point
        if req.resource_types:
            res_payload["resource_types"] = req.resource_types
        if req.resource_preferences:
            res_payload["resource_preferences"] = req.resource_preferences
        if req.difficulty:
            res_payload["difficulty"] = req.difficulty

        try:
            agent_path = (
                "/agent/v2/personalized-resources/generations"
                if is_goal_generation
                else "/agent/v2/knowledge/resources/generations"
            )
            await agent_client.post_json(agent_path, res_payload)
        except AgentServiceError as e:
            task.status = "failed"
            task.error_code = str(e.agent_code or "agent_error")[:20]
            task.error_message = e.message
            task.completed_at = datetime.now(timezone.utc)
            await db.flush()

        # 写入 user_personalized_resources（task_id 关联，resource_id 等 Webhook 回调补全）
        upr = UserPersonalizedResource(
            user_id=current_user.id,
            course_id=req.course_id,
            source_type=req.source_type,
            task_id=task.id,
        )
        db.add(upr)
        await db.flush()
        await db.commit()

        return JSONResponse(
            status_code=202,
            content={
                "code": 202,
                "message": "accepted",
                "data": {"task_id": task.id, "generate_type": "resource"},
            },
        )


@router.delete("/{id}")
async def delete_personalized_resource(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserPersonalizedResource).where(
            UserPersonalizedResource.id == id,
            UserPersonalizedResource.user_id == current_user.id,
            UserPersonalizedResource.is_deleted == False
        )
    )
    upr = result.scalar_one_or_none()
    if not upr:
        return JSONResponse(status_code=404, content={"code": 404, "message": "Resource not found"})

    upr.is_deleted = True

    if upr.question_id:
        q_result = await db.execute(
            select(QuizQuestion).where(
                QuizQuestion.id == upr.question_id,
                QuizQuestion.owner_user_id == current_user.id
            )
        )
        q = q_result.scalar_one_or_none()
        if q:
            q.is_deleted = True

    if upr.resource_id:
        r_result = await db.execute(
            select(Resource).where(Resource.id == upr.resource_id)
        )
        r = r_result.scalar_one_or_none()
        if r and r.create_by == current_user.id:
            r.is_deleted = True

    if upr.code_problem_id:
        problem_result = await db.execute(
            select(CodeProblem).where(
                CodeProblem.id == upr.code_problem_id,
                CodeProblem.owner_user_id == current_user.id,
                CodeProblem.is_deleted == False,
            )
        )
        problem = problem_result.scalar_one_or_none()
        if problem:
            problem.is_deleted = True

    await db.commit()
    return {"code": 200, "message": "success", "data": None}
