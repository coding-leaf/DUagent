import os
import sys
import uuid
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy import delete

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("mysql+"):
    pytest.skip("requires TEST_DATABASE_URL=mysql+...", allow_module_level=True)
test_database_name = urlparse(TEST_DATABASE_URL).path.strip("/")
if test_database_name == "duagent" or "test" not in test_database_name.lower():
    pytest.skip("refusing to use a non-test database", allow_module_level=True)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1 import tutoring as tutoring_routes
from app.db.session import async_session_factory, engine, init_db
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.operations import TutoringChatRequest
from app.services.tutoring_stream_adapter import TutoringStreamAdapter


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def route_context():
    await init_db()
    suffix = uuid.uuid4().hex[:8]
    async with async_session_factory() as db:
        user = User(
            username=f"tutoring_route_{suffix}",
            email=f"tutoring_route_{suffix}@example.com",
            password_hash="hash",
        )
        db.add(user)
        await db.commit()
        user_id = user.id
        yield db, user

        await db.rollback()
        conversation_ids = list((await db.execute(
            Conversation.__table__.select().with_only_columns(Conversation.id).where(
                Conversation.user_id == user_id
            )
        )).scalars().all())
        if conversation_ids:
            await db.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
            await db.execute(delete(Conversation).where(Conversation.id.in_(conversation_ids)))
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


@pytest.mark.asyncio
async def test_chat_ends_request_transaction_before_stream_adapter(
    route_context,
    monkeypatch,
):
    db, user = route_context
    observed: dict[str, bool] = {}

    async def fake_adapter_stream(
        self,
        *,
        payload,
        conversation_id,
        assistant_message_id,
    ):
        observed["in_transaction"] = db.in_transaction()
        yield {
            "event": "message",
            "data": '{"type":"done"}',
        }

    monkeypatch.setattr(TutoringStreamAdapter, "stream", fake_adapter_stream)

    response = await tutoring_routes.tutoring_chat(
        TutoringChatRequest(message="hello", scope="global"),
        current_user=user,
        db=db,
    )
    _ = [chunk async for chunk in response.body_iterator]

    assert observed["in_transaction"] is False
