# - ch355/api/auth/router.py -

from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils import response
from services import PG

from . import schemas
from . import utils

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with PG.get_session() as session:
        yield session

@router.post("/google")
async def google_login(
    payload: schemas.GoogleAuthRequest, 
    db: AsyncSession = Depends(get_db)
):
    try:
        # Offload the blocking crypto/network call to a thread!
        user_info = await run_in_threadpool(utils.verify_google_token, payload.id_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    
    email = user_info.get("email")
    name = user_info.get("name", "Unknown Player")
    
    # TODO: 1. Query Postgres to see if 'email' exists.
    # TODO: 2. If they don't exist, create a new User in Postgres.
    # TODO: 3. Get the database User ID.
    
    # For now, we will just mint a token using their email as a placeholder
    access_token = utils.create_access_token({"sub": email})
    
    return response(data = schemas.AuthResponse(access_token = access_token), message = "Generated a JWT using Google Auth")