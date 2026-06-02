# - ch355/services/postgres.py -

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from config import STORECFG
from services import ECHO


class PostgresManager:
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self.connected = False

    async def connect(self):
        try:
            self.engine = create_async_engine(
                STORECFG["POSTGRES_URL"],
                echo=False,
                pool_size=STORECFG["POSTGRES_POOL_SIZE"],
                max_overflow=STORECFG["POSTGRES_MAX_OVERFLOW"],
            )
            # verify connection
            async with self.engine.connect() as conn:
                await asyncio.wait_for(conn.run_sync(lambda _: None), timeout=3.0)

            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            self.connected = True
            ECHO.info("Connected to Postgres")

        except (SQLAlchemyError, asyncio.TimeoutError) as e:
            self.connected = False
            ECHO.error("Postgres connection failed", error=str(e))
            raise RuntimeError("Postgres connection failed")

    async def close(self):
        if self.engine:
            await self.engine.dispose()
            self.connected = False
            ECHO.info("Postgres connection closed")

    def get_session(self) -> AsyncSession:
        if not self.connected or self.session_factory is None:
            raise RuntimeError("Not connected to Postgres")
        return self.session_factory()

PG = PostgresManager()