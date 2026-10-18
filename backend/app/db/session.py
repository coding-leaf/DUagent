from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.core.config import settings
from app.db.base import Base


_engine_kwargs: dict = {"echo": settings.DEBUG}
if "mysql" in settings.resolved_database_url:
    _engine_kwargs.update(pool_size=10, max_overflow=20)
engine = create_async_engine(settings.resolved_database_url, **_engine_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
