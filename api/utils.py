# - ch355/api/utils.py -

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from services import PG

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with PG.get_session() as session:
        yield session

def response(data = None, message: str = "", code: int = 200):
    return {
        "status": "success" if code < 400 else "error",
        "code": code,
        "message": message,
        "data": data
    }