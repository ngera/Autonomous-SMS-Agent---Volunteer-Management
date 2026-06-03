from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_size=5,
    max_overflow=10,
    # pool_pre_ping issues a cheap `SELECT 1` on each checkout. If the
    # connection is dead or left in a bad state by a prior request that
    # raised mid-transaction, the pool transparently swaps in a fresh
    # one instead of handing the dirty connection to the next request.
    # Costs ~1ms per request; prevents the "cannot use Connection.
    # transaction() in a manually started transaction" failure that
    # otherwise persists across uvicorn --reload until a hard restart.
    pool_pre_ping=True,
    # Recycle connections after 30 minutes so cloud-provider TCP idle
    # timeouts (Supabase, RDS) can't surprise us with half-closed sockets.
    pool_recycle=1800,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
