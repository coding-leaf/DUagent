from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.operations import TutoringChatRequest
from app.services.tutoring_payload_builder import TutoringPayloadBuilder
from app.services.tutoring_presenters import conversation_detail, conversation_item
from app.services.tutoring_service import (
    ConversationNotFoundError,
    EditConversationRequiredError,
    EditUserMessageRequiredError,
    RegenerateConversationRequiredError,
    RegenerateUserMessageRequiredError,
    TutoringService,
)
from app.services.tutoring_stream_adapter import TutoringStreamAdapter

router = APIRouter(prefix="/api/v1/tutoring", tags=["tutoring"])


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, ConversationNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "对话不存在", "data": None},
        )
    if isinstance(error, EditConversationRequiredError):
        message = "edit 模式必须提供 conversation_id"
    elif isinstance(error, RegenerateConversationRequiredError):
        message = "regenerate 模式必须提供 conversation_id"
    elif isinstance(error, EditUserMessageRequiredError):
        message = "edit 模式需要至少一条用户消息"
    elif isinstance(error, RegenerateUserMessageRequiredError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="最后一条用户消息不存在",
        )
    else:
        raise error
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": 40001, "message": message, "data": None},
    )


@router.post("/chat")
async def tutoring_chat(
    req: TutoringChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Prepare a tutoring turn, then proxy Agent SSE without holding DB state."""
    if req.scope == "course" and not req.course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 40001,
                "message": "scope=course 时必须提供 course_id",
                "data": None,
            },
        )

    effective_course_id = req.course_id if req.scope == "course" else None
    service = TutoringService(db)
    try:
        if req.action == "edit":
            turn = await service.prepare_edit_turn(
                user_id=current_user.id,
                conversation_id=req.conversation_id,
                message=req.message,
                scope=req.scope,
                course_id=effective_course_id,
            )
        elif req.action == "regenerate":
            turn = await service.prepare_regenerate_turn(
                user_id=current_user.id,
                conversation_id=req.conversation_id,
                message=req.message,
                scope=req.scope,
                course_id=effective_course_id,
            )
        else:
            turn = await service.prepare_chat_turn(
                user_id=current_user.id,
                conversation_id=req.conversation_id,
                message=req.message,
                scope=req.scope,
                course_id=effective_course_id,
            )
        await db.commit()
    except (
        ConversationNotFoundError,
        EditConversationRequiredError,
        EditUserMessageRequiredError,
        RegenerateConversationRequiredError,
        RegenerateUserMessageRequiredError,
    ) as error:
        await db.rollback()
        raise _http_error(error) from error
    except Exception:
        await db.rollback()
        raise

    try:
        payload = await TutoringPayloadBuilder(db).build(
            user_id=current_user.id,
            scope=turn.scope,
            course_id=turn.course_id,
            conversation_id=turn.conversation_id,
            message=turn.message,
            exclude_message_ids={
                turn.user_message_id,
                turn.assistant_message_id,
            },
        )
    finally:
        if db.in_transaction():
            await db.rollback()

    events = TutoringStreamAdapter().stream(
        payload=payload,
        conversation_id=turn.conversation_id,
        assistant_message_id=turn.assistant_message_id,
    )
    return EventSourceResponse(events)


@router.get("/conversations")
async def list_conversations(
    scope: str | None = Query(None),
    course_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await TutoringService(db).list_conversations(
        user_id=current_user.id,
        scope=scope,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
    return {
        "code": 200,
        "message": "success",
        "data": {
            "conversations": [
                conversation_item(
                    item.conversation,
                    item.message_count,
                    item.last_message,
                )
                for item in result.items
            ],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conversation, messages = await TutoringService(db).get_conversation(
            user_id=current_user.id,
            conversation_id=conversation_id,
        )
    except ConversationNotFoundError as error:
        raise _http_error(error) from error
    return {
        "code": 200,
        "message": "success",
        "data": conversation_detail(conversation, messages),
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await TutoringService(db).delete_conversation(
            user_id=current_user.id,
            conversation_id=conversation_id,
        )
        await db.commit()
    except ConversationNotFoundError as error:
        await db.rollback()
        raise _http_error(error) from error
    except Exception:
        await db.rollback()
        raise
    return {"code": 200, "message": "success", "data": None}
