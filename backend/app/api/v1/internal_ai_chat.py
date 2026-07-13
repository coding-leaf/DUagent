from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.internal_ai_chat import (
    LearningProgressRequest,
    OJEvaluationRequest,
    PersonalChoiceQuizCreateRequest,
    PersonalCodeProblemCreateRequest,
    RecentAnswersRequest,
)
from app.services.ai_chat_learning_context import (
    build_learning_progress_overview,
    query_recent_answers,
)
from app.services.oj_execution_service import execute_code_in_oj, OJExecutionError
from app.services.code_problem_service import (
    CodeProblemValidationError,
    create_validated_personal_problem_from_ai_chat,
)
from app.services.ai_chat_choice_quiz_service import (
    ChoiceQuizValidationError,
    create_personal_choice_quiz_from_ai_chat,
)

router = APIRouter(prefix="/internal/ai-chat", tags=["internal-ai-chat"])


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


@router.post("/code-problem-validations")
async def validate_personal_code_problem(
    req: PersonalCodeProblemCreateRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        created = await create_validated_personal_problem_from_ai_chat(
            db,
            owner_user_id=req.user_id,
            course_id=req.course_id,
            conversation_id=req.conversation_id,
            run_id=req.run_id,
            draft=req.draft,
            execute_case=execute_code_in_oj,
        )
    except CodeProblemValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 40001,
                "message": "代码题草案验证失败",
                "data": {"reason": exc.reason},
            },
        )
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 50000, "message": "代码题保存失败", "data": None},
        )
    return {
        "code": 200,
        "message": "success",
        "data": {
            "generation_id": created.generation.id,
            "status": created.generation.status,
            "problem_id": created.problem.id,
            "language": req.draft.language,
            "public_case_count": created.public_case_count,
            "hidden_case_count": created.hidden_case_count,
        },
    }


@router.post("/choice-quizzes")
async def create_personal_choice_quiz(
    req: PersonalChoiceQuizCreateRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        question_ids = await create_personal_choice_quiz_from_ai_chat(
            db,
            owner_user_id=req.user_id,
            course_id=req.course_id,
            conversation_id=req.conversation_id,
            chapter=req.chapter,
            knowledge_point=req.knowledge_point,
            questions=req.questions,
        )
        await db.commit()
    except ChoiceQuizValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 40001,
                "message": "选择题发布验证失败",
                "data": {"reason": exc.reason},
            },
        )
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 50000, "message": "选择题保存失败", "data": None},
        )
    return {
        "code": 200,
        "message": "success",
        "data": {
            "status": "published",
            "title": req.title,
            "question_ids": question_ids,
            "question_count": len(question_ids),
        },
    }
