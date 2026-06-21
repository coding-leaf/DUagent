import os
import sys
from urllib.parse import urlparse

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("mysql+"):
    pytest.skip("requires TEST_DATABASE_URL=mysql+...", allow_module_level=True)

parsed_test_url = urlparse(TEST_DATABASE_URL)
test_database_name = parsed_test_url.path.strip("/")
if test_database_name == "duagent":
    pytest.skip("refusing to use the real duagent database", allow_module_level=True)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from app.services.resource_service import ResourceService
from app.db.session import async_session_factory, engine
from app.db.base import Base
from app.models.user import User


async def clean_and_init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio(loop_scope="module")
async def test_get_resource_detail_not_found():
    try:
        await clean_and_init_db()
        async with async_session_factory() as db:
            service = ResourceService(db)
            mock_user = User(id="user-123", email="user123@test.com", role="student")
            with pytest.raises(HTTPException) as exc:
                await service.get_resource_detail("invalid_resource_id", mock_user)
            assert exc.value.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_list_resources_unauthorized():
    try:
        await clean_and_init_db()
        async with async_session_factory() as db:
            service = ResourceService(db)
            mock_user = User(id="user-456", email="user456@test.com", role="student")
            with pytest.raises(HTTPException) as exc:
                await service.list_resources("course-nonexistent", mock_user)
            assert exc.value.status_code == 404
    finally:
        await engine.dispose()
