import os
import sys
import uuid
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy import delete, event, select

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("mysql+"):
    pytest.skip("requires TEST_DATABASE_URL=mysql+...", allow_module_level=True)
test_database_name = urlparse(TEST_DATABASE_URL).path.strip("/")
if test_database_name == "duagent" or "test" not in test_database_name.lower():
    pytest.skip("refusing to use a non-test database", allow_module_level=True)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_factory, engine, init_db
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.services.tutoring_presenters import conversation_detail, conversation_item
from app.services.tutoring_service import (
    ConversationPage,
    ConversationNotFoundError,
    EditConversationRequiredError,
    EditUserMessageRequiredError,
    PreparedTutoringTurn,
    RegenerateConversationRequiredError,
    RegenerateUserMessageRequiredError,
    TutoringService,
    message_order_key,
)


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def conversation_pair():
    await init_db()
    suffix = uuid.uuid4().hex[:8]
    async with async_session_factory() as db:
        user = User(
            username=f"tutoring_service_{suffix}",
            email=f"tutoring_service_{suffix}@example.com",
            password_hash="hash",
        )
        db.add(user)
        await db.flush()
        conversation = Conversation(
            user_id=user.id,
            scope="global",
            title="service test",
        )
        db.add(conversation)
        await db.flush()
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content="original",
        )
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="answer",
            diagrams=[{"type": "mermaid"}],
            knowledge_points=[{"name": "array"}],
        )
        db.add_all([user_message, assistant_message])
        await db.commit()
        await db.refresh(conversation)
        await db.refresh(user_message)
        await db.refresh(assistant_message)
        user_id = user.id
        conversation_id = conversation.id

        yield db, user, conversation, user_message, assistant_message

        await db.rollback()
        await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
        await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


@pytest.mark.asyncio
async def test_prepare_edit_locks_conversation_and_reuses_message_ids(conversation_pair):
    db, user, conversation, user_message, assistant_message = conversation_pair
    statements: list[str] = []

    def capture_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        turn = await TutoringService(db).prepare_edit_turn(
            user_id=user.id,
            conversation_id=conversation.id,
            message="edited",
            scope="global",
            course_id=None,
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

    assert isinstance(turn, PreparedTutoringTurn)
    assert turn.user_message_id == user_message.id
    assert turn.assistant_message_id == assistant_message.id
    assert user_message.content == "edited"
    assert assistant_message.content == ""
    assert assistant_message.diagrams is None
    assert assistant_message.knowledge_points is None
    assert any("FOR UPDATE" in statement.upper() for statement in statements)


@pytest.mark.asyncio
async def test_prepare_regenerate_keeps_user_and_clears_assistant(conversation_pair):
    db, user, conversation, user_message, assistant_message = conversation_pair

    turn = await TutoringService(db).prepare_regenerate_turn(
        user_id=user.id,
        conversation_id=conversation.id,
        message=user_message.content,
        scope="global",
        course_id=None,
    )

    assert turn.user_message_id == user_message.id
    assert turn.assistant_message_id == assistant_message.id
    assert user_message.content == "original"
    assert assistant_message.content == ""


@pytest.mark.asyncio
async def test_prepare_chat_creates_new_conversation_and_message_pair(conversation_pair):
    db, user, _, _, _ = conversation_pair

    turn = await TutoringService(db).prepare_chat_turn(
        user_id=user.id,
        conversation_id=None,
        message="new question",
        scope="global",
        course_id=None,
    )

    messages = list((await db.execute(
        select(Message)
        .where(Message.conversation_id == turn.conversation_id)
        .order_by(Message.create_time.asc())
    )).scalars().all())
    messages.sort(key=message_order_key)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [message.id for message in messages] == [
        turn.user_message_id,
        turn.assistant_message_id,
    ]


@pytest.mark.asyncio
async def test_prepare_actions_keep_current_validation_errors(conversation_pair):
    db, user, conversation, user_message, assistant_message = conversation_pair
    service = TutoringService(db)

    with pytest.raises(EditConversationRequiredError):
        await service.prepare_edit_turn(
            user_id=user.id,
            conversation_id=None,
            message="x",
            scope="global",
            course_id=None,
        )
    with pytest.raises(RegenerateConversationRequiredError):
        await service.prepare_regenerate_turn(
            user_id=user.id,
            conversation_id=None,
            message="x",
            scope="global",
            course_id=None,
        )
    with pytest.raises(ConversationNotFoundError):
        await service.prepare_edit_turn(
            user_id=user.id,
            conversation_id="missing",
            message="x",
            scope="global",
            course_id=None,
        )

    await db.delete(user_message)
    await db.delete(assistant_message)
    await db.flush()
    with pytest.raises(EditUserMessageRequiredError):
        await service.prepare_edit_turn(
            user_id=user.id,
            conversation_id=conversation.id,
            message="x",
            scope="global",
            course_id=None,
        )
    with pytest.raises(RegenerateUserMessageRequiredError):
        await service.prepare_regenerate_turn(
            user_id=user.id,
            conversation_id=conversation.id,
            message="x",
            scope="global",
            course_id=None,
        )


@pytest.mark.asyncio
async def test_tutoring_presenters_preserve_client_fields(conversation_pair):
    _, _, conversation, user_message, assistant_message = conversation_pair

    item = conversation_item(
        conversation,
        message_count=2,
        last_message=assistant_message,
    )
    detail = conversation_detail(
        conversation,
        [user_message, assistant_message],
    )

    assert set(item) == {
        "id",
        "scope",
        "course_id",
        "title",
        "last_message",
        "message_count",
        "updated_at",
    }
    assert item["last_message"] == "answer"
    assert set(detail) == {
        "id",
        "scope",
        "course_id",
        "title",
        "messages",
        "created_at",
        "updated_at",
    }
    assert [message["role"] for message in detail["messages"]] == [
        "user",
        "assistant",
    ]


@pytest.mark.asyncio
async def test_list_conversations_uses_four_bounded_queries_and_stable_last_message(
    conversation_pair,
):
    db, user, conversation, _, _ = conversation_pair
    select_statements: list[str] = []

    def capture_statement(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        page = await TutoringService(db).list_conversations(
            user_id=user.id,
            scope="global",
            course_id=None,
            page=1,
            page_size=20,
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

    assert isinstance(page, ConversationPage)
    assert page.total == 1
    assert len(select_statements) == 4
    row = page.items[0]
    assert row.conversation.id == conversation.id
    assert row.message_count == 2
    assert row.last_message.role == "assistant"
    assert row.last_message.content == "answer"


@pytest.mark.asyncio
async def test_list_conversations_empty_page_uses_two_queries(conversation_pair):
    db, _, _, _, _ = conversation_pair
    select_statements: list[str] = []

    def capture_statement(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        page = await TutoringService(db).list_conversations(
            user_id="missing-user",
            scope="global",
            course_id=None,
            page=1,
            page_size=20,
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

    assert page.total == 0
    assert page.items == []
    assert len(select_statements) == 2
