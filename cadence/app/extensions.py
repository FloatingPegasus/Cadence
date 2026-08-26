from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from pgvector.psycopg import register_vector_async

from .config import settings

async_engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)

sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def configure_pgvector_async_engine(engine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _register_vector_async(dbapi_connection, _connection_record) -> None:
        dbapi_connection.run_async(register_vector_async)


configure_pgvector_async_engine(async_engine)


async def get_db():
    async with async_session() as db:
        yield db
