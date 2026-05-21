from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
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


# Import all models so they register with Base.metadata before init_db
import app.models.user  # noqa: E402
import app.models.course  # noqa: E402
import app.models.quiz  # noqa: E402
import app.models.conversation  # noqa: E402
import app.models.others  # noqa: E402


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
