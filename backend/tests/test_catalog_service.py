import os
import sys
import uuid
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

from app.services.catalog_service import CatalogService
from app.exceptions.catalog_exceptions import CatalogNotFoundError
from app.db.session import async_session_factory, engine, init_db
from app.models.catalog import CourseCatalog


@pytest.mark.asyncio(loop_scope="module")
async def test_get_catalog_not_found():
    try:
        async with async_session_factory() as db:
            service = CatalogService(db)
            with pytest.raises(CatalogNotFoundError):
                await service.get_catalog("invalid_id")
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_list_ready_catalogs_filters_deleted_and_orders_by_title():
    try:
        await init_db()
        suffix = uuid.uuid4().hex[:8]
        ready_b_id = f"ready-b-{suffix}"
        ready_a_id = f"ready-a-{suffix}"
        async with async_session_factory() as db:
            db.add_all([
                CourseCatalog(
                    id=ready_b_id,
                    title=f"B Catalog {suffix}",
                    status="ready",
                    knowledge_status="ready",
                ),
                CourseCatalog(
                    id=f"draft-a-{suffix}",
                    title=f"A Draft {suffix}",
                    status="draft",
                    knowledge_status="draft",
                ),
                CourseCatalog(
                    id=ready_a_id,
                    title=f"A Catalog {suffix}",
                    status="ready",
                    knowledge_status="ready",
                ),
                CourseCatalog(
                    id=f"deleted-{suffix}",
                    title=f"Deleted Catalog {suffix}",
                    status="ready",
                    knowledge_status="ready",
                    is_deleted=True,
                ),
            ])
            await db.commit()

            service = CatalogService(db)
            catalogs = await service.list_ready_catalogs("ready")

        ids = [catalog.id for catalog in catalogs]
        assert ids.index(ready_a_id) < ids.index(ready_b_id)
        assert f"deleted-{suffix}" not in ids
    finally:
        await engine.dispose()
