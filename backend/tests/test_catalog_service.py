import os
import sys
from urllib.parse import urlparse

import pytest
import pytest_asyncio

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
from app.db.session import async_session_factory

@pytest.mark.asyncio
async def test_get_catalog_not_found():
    async with async_session_factory() as db:
        service = CatalogService(db)
        with pytest.raises(CatalogNotFoundError):
            await service.get_catalog("invalid_id")
