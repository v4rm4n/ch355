# - ch355/api/auth/router.py -

from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils import response
from services import PG

from . import schemas
from . import utils
from .models import User

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

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Google authentication token did not provide an email address."
        )
    
    # 1. Query Postgres to see if 'email' exists
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # 2. If they don't exist, auto-register them seamlessly
    if not user:
        # Use Google's name if available, otherwise generate a petname
        raw_name = user_info.get("name")
        display_name = raw_name if raw_name else utils.generate_petname()

        user = User(
            email = email,
            name = display_name
            # Elo, matches, and conduct scores use their model defaults automatically!
        )
        db.add(user)
        await db.commit()
        await db.refresh(user) # Reloads the user record to populate the autoincremented id

    # 3. Mint the game token using their database Primary Key ID as the 'sub'
    access_token = utils.create_access_token({"sub": str(user.id)})
    
    return response(
        data=schemas.AuthResponse(access_token=access_token), 
        message=f"Logged in successfully as {user.name}"
    )