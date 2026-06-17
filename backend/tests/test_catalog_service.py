import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.catalog_service import CatalogService
from app.exceptions.catalog_exceptions import CatalogNotFoundError

@pytest.mark.asyncio
async def test_get_catalog_not_found(db: AsyncSession):
    service = CatalogService(db)
    with pytest.raises(CatalogNotFoundError):
        await service.get_catalog("invalid_id")
