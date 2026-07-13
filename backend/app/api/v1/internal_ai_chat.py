from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.internal_ai_chat import (
    DialogueProfileUpdateRequest,
    LearnerProfileReadRequest,
    LearningProgressRequest,
    OJEvaluationRequest,
    PersonalPracticeDeliveryRequest,
    PersonalPracticePrepareRequest,
    RecentAnswersRequest,
    PersonalizedResourceRecommendRequest,
    PersonalizedResourceStartRequest,
)
from app.services.ai_chat_profile_service import (
    read_dialogue_learner_profile,
    update_dialogue_learner_profile,
)
from app.services.ai_chat_resource_service import (
    recommend_personalized_resources,
    start_ai_chat_resource_generation,
)
from app.services.ai_chat_learning_context import (
    build_learning_progress_overview,
    query_recent_answers,
)
from app.services.oj_execution_service import execute_code_in_oj, OJExecutionError
from app.services.personal_practice_delivery_service import (
    PersonalPracticeDeliveryError,
    finalize_personal_practice_delivery,
    prepare_personal_practice_delivery,
    record_personal_practice_delivery_failure,
    resume_personal_practice_delivery,
)

router = APIRouter(prefix="/internal/ai-chat", tags=["internal-ai-chat"])


def _practice_http_error(message: str, reason: str, status_code: int = 400) -> HTTPException:
    code = 40001 if status_code == status.HTTP_400_BAD_REQUEST else 50000
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "data": {"reason": reason}},
    )


async def _mark_delivery_failed(
    db: AsyncSession,
    generation_id: str,
    reason: str,
) -> None:
    await db.rollback()
    try:
        await record_personal_practice_delivery_failure(
            db, generation_id=generation_id, reason=reason,
        )
        await db.commit()
    except Exception:
        await db.rollback()


def verify_internal_agent_token(
    x_internal_agent_token: str | None = Header(default=None, alias="X-Internal-Agent-Token"),
) -> None:
    expected = settings.INTERNAL_AGENT_TOKEN
    if not expected or x_internal_agent_token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 40300, "message": "internal agent token invalid", "data": None},
        )


@router.post("/learning-progress")
async def read_learning_progress(
    req: LearningProgressRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await build_learning_progress_overview(
        db,
        user_id=req.user_id,
        course_id=req.course_id,
        limit_nodes=req.limit_nodes,
    )
    return {"code": 200, "message": "success", "data": data}


@router.post("/recent-answers")
async def read_recent_answers(
    req: RecentAnswersRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await query_recent_answers(
        db,
        user_id=req.user_id,
        course_id=req.course_id,
        scope=req.scope,
        node_id=req.node_id,
        knowledge_point=req.knowledge_point,
        limit=req.limit,
        only_wrong=req.only_wrong,
    )
    return {"code": 200, "message": "success", "data": data}


@router.post("/learner-profile/read")
async def read_learner_profile(
    req: LearnerProfileReadRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await read_dialogue_learner_profile(
        db, user_id=req.user_id, course_id=req.course_id
    )
    return {"code": 200, "message": "success", "data": data}


@router.post("/learner-profile/update")
async def update_learner_profile(
    req: DialogueProfileUpdateRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await update_dialogue_learner_profile(db, **req.model_dump())
    return {"code": 200, "message": "success", "data": data}


@router.post("/personalized-resources/recommend")
async def recommend_resources(
    req: PersonalizedResourceRecommendRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await recommend_personalized_resources(db, **req.model_dump())
    return {"code": 200, "message": "success", "data": data}


@router.post("/personalized-resources/generate")
async def generate_resource(
    req: PersonalizedResourceStartRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await start_ai_chat_resource_generation(db, **req.model_dump())
    return {"code": 200, "message": "success", "data": data}


@router.post("/oj/evaluate")
async def evaluate_oj_code(
    req: OJEvaluationRequest,
    _auth: None = Depends(verify_internal_agent_token),
):
    """
    智能体调用的代码评测接口。
    若 OJ 执行异常，捕获异常并返回 degraded 标记，供智能体静默退化到静态分析。
    """
    try:
        data = await execute_code_in_oj(
            code=req.code,
            language=req.language,
            stdin=req.stdin,
        )
        return {"code": 200, "message": "success", "data": data}
    except OJExecutionError as exc:
        if exc.reason == "unsupported_language":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 40001, "message": exc.message, "data": None},
            )
        # Agent execution degradation fallback
        return {
            "code": 200,
            "message": "degraded",
            "data": {
                "status": "degraded",
                "reason": exc.reason,
                "compile_status": "UNKNOWN",
                "execution": None,
                "message": f"OJ评测服务不可用，请启动LLM静态分析对代码进行人工走查与逻辑判定。原因: {exc.message}",
            }
        }


@router.post("/personal-practices/prepare")
async def prepare_personal_practice(
    req: PersonalPracticePrepareRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        generation = await prepare_personal_practice_delivery(
            db,
            request=req,
            execute_case=execute_code_in_oj,
        )
        await db.commit()
    except (PersonalPracticeDeliveryError, ValueError) as exc:
        await db.rollback()
        reason = getattr(exc, "reason", str(exc))
        raise _practice_http_error("互动练习草案验证失败", reason)
    except SQLAlchemyError:
        await db.rollback()
        raise _practice_http_error(
            "互动练习草案保存失败", "database_error", status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return {
        "code": 200,
        "message": "success",
        "data": {
            "generation_id": generation.id,
            "status": generation.status,
        },
    }


@router.post("/personal-practices/finalize")
async def finalize_personal_practice(
    req: PersonalPracticeDeliveryRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await finalize_personal_practice_delivery(
            db,
            generation_id=req.generation_id,
            user_id=req.user_id,
            course_id=req.course_id,
        )
        await db.commit()
    except PersonalPracticeDeliveryError as exc:
        await db.rollback()
        raise _practice_http_error("互动练习发布验证失败", exc.reason)
    except Exception as exc:
        await _mark_delivery_failed(db, req.generation_id, exc.__class__.__name__)
        raise _practice_http_error(
            "互动练习发布失败", "delivery_failed", status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return {"code": 200, "message": "success", "data": data}


@router.post("/personal-practices/resume")
async def resume_personal_practice(
    req: PersonalPracticeDeliveryRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await resume_personal_practice_delivery(
            db,
            generation_id=req.generation_id,
            user_id=req.user_id,
            course_id=req.course_id,
        )
        await db.commit()
    except PersonalPracticeDeliveryError as exc:
        await db.rollback()
        raise _practice_http_error("互动练习恢复失败", exc.reason)
    return {"code": 200, "message": "success", "data": data}
