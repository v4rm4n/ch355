# - ch355/api/match/router.py -

import random
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils import response
from api.utils import get_db
from api.auth.models import User
from api.auth.dependencies import get_current_user

from . import schemas
from .models import Match

router = APIRouter(
    prefix="/match",
    tags=["Match"]
)

@router.post("/create")
async def create_match(
    payload: schemas.MatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Prevent challenging yourself
    if payload.opponent_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="You cannot play against yourself."
        )

    # 1. Determine who plays White and who plays Black
    creator_color = payload.play_as.lower()
    if creator_color not in ["white", "black"]:
        creator_color = random.choice(["white", "black"])

    white_id = None
    black_id = None

    if creator_color == "white":
        white_id = current_user.id
        black_id = payload.opponent_id
    else:
        black_id = current_user.id
        white_id = payload.opponent_id

    # 2. Determine initial status
    initial_status = "pending" if payload.opponent_id is None else "active"

    # 3. Create the DB record
    new_match = Match(
        white_player_id=white_id,
        black_player_id=black_id,
        status=initial_status,
        is_rated=payload.is_rated,
        is_private=payload.is_private,
        time_control=payload.time_control
    )
    
    db.add(new_match)
    await db.commit()
    await db.refresh(new_match)

    return response(
        data=schemas.MatchResponse(
            id=new_match.id,
            white_player_id=new_match.white_player_id,
            black_player_id=new_match.black_player_id,
            status=new_match.status,
            is_rated=new_match.is_rated,
            is_private=new_match.is_private,
            time_control=new_match.time_control
        ).model_dump(),
        message="Match created successfully."
    )