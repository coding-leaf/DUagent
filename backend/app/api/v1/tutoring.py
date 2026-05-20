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
    # Create or reuse conversation
    if req.conversation_id:
        result = await db.execute(select(Conversation).where(Conversation.id == req.conversation_id))
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
            course_id=req.course_id,
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
    )
    db.add(user_msg)
    await db.flush()

    conversation_id = conv.id
    assistant_msg_id = Message(
        conversation_id=conv.id,
        role="assistant",
        content="",
    )
    db.add(assistant_msg_id)
    await db.flush()
    a_msg_id = assistant_msg_id.id

    conv.updated_at = datetime.now(timezone.utc)
    await db.flush()

    async def event_generator():
        # Simulated tutoring response
        response_text = f"你好！关于「{req.message}」这个问题，我来为你解答...\n\n这道题考察的是核心概念的理解。首先我们需要明确定义，然后逐步推导..."
        words = response_text

        # Stream chunks
        chunk_size = 5
        for i in range(0, len(words), chunk_size):
            chunk = words[i : i + chunk_size]
            yield {
                "event": "chunk",
                "data": json.dumps({"type": "chunk", "content": chunk}),
            }
            await asyncio.sleep(0.05)

        # Send diagram
        yield {
            "event": "diagram",
            "data": json.dumps({
                "type": "diagram",
                "content": "graph TD\n  A[概念] --> B[推导]\n  B --> C[结论]",
                "mermaid": True,
            }),
        }

        # Send knowledge points
        yield {
            "event": "knowledge_points",
            "data": json.dumps({
                "type": "knowledge_points",
                "points": [
                    {"name": "核心概念", "status": "mastered"},
                    {"name": "推导过程", "status": "learning"},
                ],
            }),
        }

        # Send suggestion
        yield {
            "event": "suggestion",
            "data": json.dumps({
                "type": "suggestion",
                "content": "建议你继续练习类似题型巩固理解",
                "related_exercises": [{"id": "ex1", "title": "配套练习1"}],
            }),
        }

        # Done
        yield {
            "event": "done",
            "data": json.dumps({
                "type": "done",
                "conversation_id": conversation_id,
                "message_id": a_msg_id,
            }),
        }

    return EventSourceResponse(event_generator())


@router.get("/conversations")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Conversation).where(Conversation.user_id == current_user.id)

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(Conversation.updated_at.desc()).offset(offset).limit(page_size))
    convs = result.scalars().all()

    conv_list = []
    for c in convs:
        # Count messages
        mc_r = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == c.id)
        )
        msg_count = mc_r.scalar() or 0

        # Last message
        lm_r = await db.execute(
            select(Message)
            .where(Message.conversation_id == c.id)
            .order_by(Message.timestamp.desc())
        )
        last_msg = lm_r.scalars().first()

        conv_list.append({
            "id": c.id,
            "title": c.title,
            "last_message": last_msg.content[:50] if last_msg and last_msg.content else "",
            "message_count": msg_count,
            "updated_at": c.updated_at.isoformat() if c.updated_at else "",
        })

    return {
        "code": 200,
        "message": "success",
        "data": conv_list,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = c_result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "对话不存在", "data": None},
        )

    m_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
    )
    messages = m_result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": conv.id,
            "title": conv.title,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "diagrams": m.diagrams,
                    "knowledge_points": m.knowledge_points,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else "",
                }
                for m in messages
            ],
            "created_at": conv.created_at.isoformat() if conv.created_at else "",
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else "",
        },
    }
