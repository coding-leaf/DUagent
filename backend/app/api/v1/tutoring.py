import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_db
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.operations import TutoringChatRequest

router = APIRouter(prefix="/api/v1/tutoring", tags=["tutoring"])


@router.post("/chat")
async def tutoring_chat(
    req: TutoringChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate scope
    if req.scope == "course" and not req.course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "scope=course 时必须提供 course_id", "data": None},
        )

    if req.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == req.conversation_id,
                Conversation.user_id == current_user.id,
                Conversation.is_deleted == False,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "对话不存在", "data": None},
            )
    else:
        title = req.message[:50] + ("..." if len(req.message) > 50 else "")
        conv = Conversation(
            user_id=current_user.id,
            scope=req.scope,
            course_id=req.course_id if req.scope == "course" else None,
            title=title,
        )
        db.add(conv)
        await db.flush()
        await db.refresh(conv)

    # Save user message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=req.message,
        meta_json={"scope": req.scope, "course_id": req.course_id},
    )
    db.add(user_msg)
    await db.flush()

    conversation_id = conv.id
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content="",
        meta_json={"scope": req.scope, "course_id": req.course_id},
    )
    db.add(assistant_msg)
    await db.flush()
    a_msg_id = assistant_msg.id

    conv.update_time = datetime.now(timezone.utc)
    await db.flush()

    async def event_generator():
        response_text = f"你好！关于这个问题，我来为你解答..."
        for i in range(0, len(response_text), 5):
            chunk = response_text[i : i + 5]
            yield {"event": "chunk", "data": json.dumps({"type": "chunk", "content": chunk})}
            await asyncio.sleep(0.03)

        yield {
            "event": "done",
            "data": json.dumps({"type": "done", "conversation_id": conversation_id, "message_id": a_msg_id}),
        }

    return EventSourceResponse(event_generator())


@router.get("/conversations")
async def list_conversations(
    scope: str = Query(None),
    course_id: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Conversation).where(
        Conversation.user_id == current_user.id, Conversation.is_deleted == False
    )
    if scope:
        query = query.where(Conversation.scope == scope)
    if course_id:
        query = query.where(Conversation.course_id == course_id)

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Conversation.update_time.desc()).offset(offset).limit(page_size)
    )
    convs = result.scalars().all()

    conv_list = []
    for c in convs:
        mc_r = await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == c.id, Message.is_deleted == False
            )
        )
        msg_count = mc_r.scalar() or 0

        lm_r = await db.execute(
            select(Message)
            .where(Message.conversation_id == c.id, Message.is_deleted == False)
            .order_by(Message.create_time.desc())
        )
        last_msg = lm_r.scalars().first()

        conv_list.append({
            "id": c.id,
            "scope": c.scope,
            "course_id": c.course_id,
            "title": c.title,
            "last_message": last_msg.content[:50] if last_msg and last_msg.content else "",
            "message_count": msg_count,
            "updated_at": c.update_time.isoformat() if c.update_time else "",
        })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "conversations": conv_list,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted == False,
        )
    )
    conv = c_result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "对话不存在", "data": None},
        )

    m_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.is_deleted == False)
        .order_by(Message.create_time.asc())
    )
    messages = m_result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": conv.id,
            "scope": conv.scope,
            "course_id": conv.course_id,
            "title": conv.title,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content or "",
                    "diagrams": m.diagrams or [],
                    "knowledge_points": m.knowledge_points or [],
                    "meta": m.meta_json or {},
                    "timestamp": m.create_time.isoformat() if m.create_time else "",
                }
                for m in messages
            ],
            "created_at": conv.create_time.isoformat() if conv.create_time else "",
            "updated_at": conv.update_time.isoformat() if conv.update_time else "",
        },
    }
