import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_db
from app.models.conversation import Conversation, Message
from app.models.catalog import CourseOffering, CourseCatalog
from app.models.others import UserProfile
from app.models.user import User
from app.schemas.operations import TutoringChatRequest
from app.db.session import async_session_factory
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph

router = APIRouter(prefix="/api/v1/tutoring", tags=["tutoring"])


def _message_order_key(message: Message):
    role_rank = 0 if message.role == "user" else 1
    return (
        message.create_time or datetime.min,
        message.update_time or datetime.min,
        role_rank,
    )


def _build_learner_context(user: User) -> dict:
    """生成可进入 AI 上下文的脱敏学习资料，不包含身份识别字段。"""
    return {
        "major": user.major,
        "grade": user.grade,
        "guidance_level": user.guidance_level,
    }


async def _assemble_tutoring_payload(
    user_id: str, scope: str, course_id: str | None,
    conversation_id: str, message: str, db: AsyncSession,
    catalog_id: str | None = None,
    exclude_message_ids: set[str] | None = None,
) -> dict:
    """组装调用 Agent /tutoring/chat 所需的 payload。"""
    payload: dict = {
        "user_id": user_id,
        "scope": scope,
        "message": message,
        "conversation_id": conversation_id,
    }
    if course_id:
        payload["course_id"] = course_id

    # active_kg_nodes: 从关联的 Active KG 中提取精简节点
    payload["active_kg_nodes"] = []
    if scope == "course" and course_id:
        offering_r = await db.execute(select(CourseOffering).where(CourseOffering.id == course_id))
        offering = offering_r.scalar_one_or_none()
        
        target_catalog_id = None
        if catalog_id:
            target_catalog_id = catalog_id
            if offering and offering.catalog_id and offering.catalog_id != catalog_id:
                import logging
                logging.getLogger(__name__).warning(
                    f"Course_id({course_id}) maps to catalog_id({offering.catalog_id}) but catalog_id({catalog_id}) was provided. Using provided catalog_id for KG."
                )
        elif offering:
            target_catalog_id = offering.catalog_id

        if target_catalog_id:
            # 课程知识在 Qdrant 中按 catalog_id 入库，Agent 据此检索；course_id 仅作 offering 身份键。
            payload["catalog_id"] = target_catalog_id
            catalog_r = await db.execute(select(CourseCatalog).where(CourseCatalog.id == target_catalog_id))
            catalog = catalog_r.scalar_one_or_none()
            if catalog and catalog.kg_host_course_id:
                active_kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id)
                kg_nodes = active_kg.nodes if active_kg and isinstance(active_kg.nodes, list) else []
                if kg_nodes:
                    nodes = []
                    for node in kg_nodes:
                        nodes.append({
                            "id": node.get("id"),
                            "name": node.get("name"),
                            "chapter": node.get("chapter"),
                        })
                    payload["active_kg_nodes"] = nodes

    # user_profile: 从 SQL 读取最近画像
    if scope == "course" and course_id:
        pf_result = await db.execute(
            select(UserProfile)
            .where(
                UserProfile.user_id == user_id,
                UserProfile.course_id == course_id,
                UserProfile.is_deleted == False,
            )
        )
        pf = pf_result.scalar_one_or_none()
        if pf:
            payload["user_profile"] = {
                "guidance_level": pf.guidance_level_current,
                "modal_preference": pf.modal_preference,
                "knowledge_mastered": [
                    kc["name"] for kc in (pf.knowledge_coordinates or [])
                    if kc.get("status") == "mastered"
                ],
                "knowledge_weak": [
                    kc["name"] for kc in (pf.knowledge_coordinates or [])
                    if kc.get("status") != "mastered"
                ],
            }
        else:
            payload["user_profile"] = {"guidance_level": "L2"}
    else:
        payload["user_profile"] = {"guidance_level": "L2"}

    # conversation_summary: 对话全局摘要
    conv_r = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_r.scalar_one_or_none()
    if conv and conv.summary:
        payload["conversation_summary"] = conv.summary

    # recent_messages: 最近 10 轮消息
    messages_query = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.is_deleted == False)
    )
    if exclude_message_ids:
        messages_query = messages_query.where(Message.id.notin_(exclude_message_ids))

    msgs_r = await db.execute(
        messages_query
        .order_by(Message.create_time.desc(), Message.update_time.desc())
        .limit(20)
    )
    recent = list(msgs_r.scalars().all())
    recent.sort(key=_message_order_key)
    payload["recent_messages"] = [
        {"role": m.role, "content": m.content or "", "meta": m.meta_json or {}}
        for m in recent
    ]

    return payload


@router.post("/chat")
async def tutoring_chat(
    req: TutoringChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """智能辅导对话 SSE。代理 Agent /tutoring/chat 流，完成后保存 assistant 消息。"""
    # Validate scope
    if req.scope == "course" and not req.course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "scope=course 时必须提供 course_id", "data": None},
        )

    effective_course_id: str | None = req.course_id if req.scope == "course" else None

    # Create or validate conversation
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
            course_id=effective_course_id,
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

    # Create placeholder for assistant message
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

    # Commit pre-stream DB writes so session doesn't hold lock during SSE
    await db.commit()

    # Assemble Agent payload (use new session for read-only payload assembly)
    payload = await _assemble_tutoring_payload(
        current_user.id, req.scope, effective_course_id,
        conversation_id, req.message, db,
        exclude_message_ids={user_msg.id, a_msg_id},
    )

    async def event_generator():
        """代理 Agent SSE 流给前端，同时累积 assistant 回复内容。"""
        accumulated_chunks: list[str] = []
        diagrams: list = []
        knowledge_points: list = []
        done_sent = False

        try:
            async for raw_bytes in agent_client.stream_sse("/agent/v1/tutoring/chat", payload):
                text = raw_bytes.decode("utf-8", errors="replace")
                # SSE 协议: data: {...}\n\n
                for line in text.split("\n"):
                    stripped = line.strip()
                    if not stripped or not stripped.startswith("data:"):
                        continue
                    data_str = stripped[5:].strip()
                    if not data_str:
                        continue

                    # Parse for accumulation and adapt Backend Client API boundary fields.
                    try:
                        parsed = json.loads(data_str)
                        t = parsed.get("type", "")
                        if t == "chunk":
                            accumulated_chunks.append(parsed.get("content", ""))
                        elif t == "diagram":
                            diagrams.append(parsed.get("data", parsed))
                        elif t == "knowledge_points":
                            # parsed 是 dict，兼容多种 key：points / knowledge_points / data
                            # 优先 "points"（向后兼容），其次 "knowledge_points"，最后 "data"
                            kp_candidate = (
                                parsed.get("points")
                                or parsed.get("knowledge_points")
                                or parsed.get("data")
                            )
                            if isinstance(kp_candidate, list):
                                knowledge_points = kp_candidate
                        elif t == "done":
                            done_sent = True
                            # done 事件的 knowledge_points_used 作为兜底捕获
                            kp_used = parsed.get("knowledge_points_used")
                            if not knowledge_points and isinstance(kp_used, list):
                                knowledge_points = kp_used
                            parsed["conversation_id"] = conversation_id
                            parsed["message_id"] = a_msg_id
                            data_str = json.dumps(parsed, ensure_ascii=False)
                    except json.JSONDecodeError:
                        pass

                    # Forward to frontend
                    yield {"event": "message", "data": data_str}

        except AgentServiceError:
            if not done_sent:
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "type": "done",
                        "conversation_id": conversation_id,
                        "message_id": a_msg_id,
                        "error": "Agent 服务暂时不可用",
                    }),
                }

        # 流结束后更新 assistant 消息
        full_content = "".join(accumulated_chunks)
        async with async_session_factory() as update_db:
            await update_db.execute(
                sql_update(Message)
                .where(Message.id == a_msg_id)
                .values(
                    content=full_content,
                    diagrams=diagrams if diagrams else None,
                    knowledge_points=knowledge_points if knowledge_points else None,
                )
            )
            await update_db.execute(
                sql_update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(update_time=datetime.now(timezone.utc))
            )
            await update_db.commit()

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
        .order_by(Message.create_time.asc(), Message.update_time.asc())
    )
    messages = sorted(m_result.scalars().all(), key=_message_order_key)

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
