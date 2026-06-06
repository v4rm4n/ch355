# - ch355/api/auth/router.py -

import jwt

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils import response, get_db
from config.config import AUTHCFG
from services import PG

from . import schemas
from . import utils
from .models import User
from .dependencies import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

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
    refresh_token = utils.create_refresh_token({"sub": str(user.id)})
    
    return response(
        data=schemas.AuthResponse(
            access_token = access_token,
            refresh_token = refresh_token, 
            ), 
        message=f"Logged in successfully as {user.name}"
    )

@router.post("/refresh")
async def refresh_access_token(payload: schemas.RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Takes a valid refresh token and issues a new access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    
    try:
        # Decode the refresh token
        token_data = jwt.decode(payload.refresh_token, AUTHCFG["JWT_SECRET"], algorithms=["HS256"])
        
        # Security check: Make sure they didn't send an access token here!
        if token_data.get("type") != "refresh":
            raise credentials_exception
            
        user_id: str | None = token_data.get("sub")
        if user_id is None:
            raise credentials_exception
            
    except jwt.PyJWTError:
        raise credentials_exception
        
    # Check if the user still exists in the database (they weren't deleted/banned)
    query = select(User).where(User.id == int(user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise credentials_exception
        
    # Mint a brand new access token
    new_access_token = utils.create_access_token({"sub": str(user.id)})
    
    return response(
        data={"access_token": new_access_token},
        message="Token refreshed successfully."
    )

@router.get("/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    """
    Fetches the profile of the currently logged-in user.
    The Bouncer (get_current_user) guarantees that 'current_user' is a valid DB record.
    """
    return response(
        data={
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "elo_rating": current_user.elo_rating,
            "matches_played": current_user.matches_played,
            "conduct_score": current_user.conduct_score
        },
        message="Profile fetched successfully."
    )