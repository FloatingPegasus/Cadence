from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

async_engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

sync_engine = create_engine(
    settings.sync_database_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def configure_sqlite_engine(engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


configure_sqlite_engine(sync_engine)
configure_sqlite_engine(async_engine.sync_engine)


async def get_db():
    async with async_session() as db:
        yield db
