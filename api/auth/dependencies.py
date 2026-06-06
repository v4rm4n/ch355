# - ch355/api/auth/dependencies.py -

import jwt
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import AUTHCFG
from services import PG

from api.utils import get_db

from .models import User

# This tells FastAPI to look for the "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Decode the JWT using your secret key from your config
        payload = jwt.decode(token, AUTHCFG["JWT_SECRET"], algorithms=["HS256"])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        
        # 2. Parse the string claim into a real Python UUID object safely
        user_id = uuid.UUID(user_id_str)

    except jwt.PyJWTError: # or jwt.JWTError if using python-jose
        raise credentials_exception
        
    # Look up the user in Postgres using the ID from the token
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user