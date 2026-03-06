from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core import config


def _build_database_url() -> str:
    return str(config.settings.SQLALCHEMY_DATABASE_URI).replace(
        "postgresql://", "postgresql+psycopg://"
    )


def init_engine(database_url: str | None = None) -> None:
    """(Re)initialize the database engine and session factory."""
    global engine, async_session_factory  # noqa: PLW0603

    engine = create_async_engine(
        database_url or _build_database_url(), echo=False, poolclass=NullPool
    )
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Use NullPool to avoid connection limits - each request gets a fresh connection
init_engine()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
