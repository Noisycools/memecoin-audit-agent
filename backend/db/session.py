from __future__ import annotations

import asyncio
from typing import Any
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base


class AsyncSessionAdapter:
    """Async wrapper around SQLAlchemy 2.0 Session using asyncio.to_thread (no greenlet required)."""

    def __init__(self, sync_session: Session) -> None:
        self._session = sync_session

    async def __aenter__(self) -> AsyncSessionAdapter:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is not None:
            await asyncio.to_thread(self._session.rollback)
        await asyncio.to_thread(self._session.close)

    def add(self, instance: Any) -> None:
        self._session.add(instance)

    async def execute(self, statement: Any) -> Any:
        return await asyncio.to_thread(self._session.execute, statement)

    async def flush(self) -> None:
        await asyncio.to_thread(self._session.flush)

    async def commit(self) -> None:
        await asyncio.to_thread(self._session.commit)


class AsyncSessionFactory:
    def __init__(self, sync_factory: sessionmaker[Session]) -> None:
        self._sync_factory = sync_factory

    def __call__(self) -> AsyncSessionAdapter:
        return AsyncSessionAdapter(self._sync_factory())


async def create_async_session_factory(database_url: str) -> AsyncSessionFactory:
    sync_url = (
        database_url.replace("sqlite+aiosqlite://", "sqlite://")
        .replace("postgresql+asyncpg://", "postgresql://")
    )
    connect_args = {"check_same_thread": False} if sync_url.startswith("sqlite") else {}
    engine = create_engine(sync_url, future=True, connect_args=connect_args)

    if sync_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn: Any, _connection_record: Any) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    await asyncio.to_thread(Base.metadata.create_all, engine)
    sync_factory = sessionmaker(engine, expire_on_commit=False)
    return AsyncSessionFactory(sync_factory)
