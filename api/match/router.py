# - ch355/api/match/router.py -

import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils import response
from api.utils import get_db
from api.auth.models import User
from api.auth.dependencies import get_current_user

from . import schemas
from .models import Match, MatchStatus

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
    # GUARD 1: Prevent challenging yourself
    if payload.opponent_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="You cannot play against yourself."
        )

    # GUARD 2: The "One Match Only" Rule
    # Check if the user is already in a match that hasn't expired/finished
    existing_match_query = select(Match).where(
        ((Match.white_player_id == current_user.id) | (Match.black_player_id == current_user.id)) &
        (Match.status.in_([MatchStatus.PENDING, MatchStatus.ACTIVE]))
    )

    existing_match_result = await db.execute(existing_match_query)

    if existing_match_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active or pending match. Please finish or cancel it first."
        )

    # 1. Determine who plays White and who plays Black
    creator_color = payload.play_as.lower()
    if creator_color not in ["white", "black"]:
        creator_color = random.choice(["white", "black"])

    # NOTE: Since the opponent hasn't joined yet, their slot remains None!
    white_id = current_user.id if creator_color == "white" else None
    black_id = current_user.id if creator_color == "black" else None

    # 2. Determine initial status
    initial_status = "pending" if payload.opponent_id is None else "active"

    # 3. Create the DB record (Status is ALWAYS pending until someone joins)
    new_match = Match(
        white_player_id=white_id,
        black_player_id=black_id,
        status=MatchStatus.PENDING,
        is_rated=payload.is_rated,
        is_private=payload.is_private,
        time_control=payload.time_control
        # Note: If you add `invited_user_id` to your model later, you'd map payload.opponent_id here!
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


@router.get("/open")
async def list_open_matches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches all public matches currently waiting for an opponent.
    Excludes matches created by the requesting user themselves.
    """
    # Query for public, pending matches where the current user is NOT already a participant
    query = (
        select(Match)
        .where(Match.status == MatchStatus.PENDING)
        .where(Match.is_private == False)
        .where((Match.white_player_id != current_user.id) | Match.white_player_id.is_(None))
        .where((Match.black_player_id != current_user.id) | Match.black_player_id.is_(None))
        .order_by(Match.created_at.desc())
    )
    
    result = await db.execute(query)
    open_matches = result.scalars().all()

    # Map the database records cleanly through your Pydantic schema
    match_list = [
        schemas.MatchResponse(
            id=m.id,
            white_player_id=m.white_player_id,
            black_player_id=m.black_player_id,
            status=m.status,
            is_rated=m.is_rated,
            is_private=m.is_private,
            time_control=m.time_control
        ).model_dump()
        for m in open_matches
    ]

    return response(
        data=match_list,
        message=f"Found {len(match_list)} open match lobbies."
    )


@router.delete("/{match_id}")
async def delete_match(
    match_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancels and hard-deletes a pending match from the lobby.
    Only the match creator can delete it, and only if no opponent has joined yet.
    """
    # 1. Fetch the match to inspect ownership and current status
    query = select(Match).where(Match.id == match_id)
    result = await db.execute(query)
    match_record = result.scalar_one_or_none()

    # Guard: Match doesn't exist
    if match_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found."
        )

    # 2. Guard: Verify ownership. The creator could be white OR black depending on setup
    is_creator = (match_record.white_player_id == current_user.id or 
                  match_record.black_player_id == current_user.id)
    
    if not is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to cancel this match."
        )

    # 3. Guard: Prevent deleting active or historical games
    if match_record.status != MatchStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a match that has already started or concluded."
        )

    # 4. Perform the clean delete operation
    delete_query = delete(Match).where(Match.id == match_id)
    await db.execute(delete_query)
    await db.commit()

    return response(
        data={"deleted_match_id": str(match_id)},  # <--- Fixed: Cast UUID safely to string
        message="Match successfully canceled and removed from lobby."
    )

@router.post("/{match_id}/join")
async def join_match(
    match_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Allows a user to join an open, pending match.
    Flips the status to STARTING for the WebSocket handshake.
    """
    # GUARD 1: The "One Match Only" Rule for the Joiner
    existing_match_query = select(Match).where(
        ((Match.white_player_id == current_user.id) | (Match.black_player_id == current_user.id)) &
        (Match.status.in_([MatchStatus.PENDING, MatchStatus.STARTING, MatchStatus.ACTIVE]))
    )
    existing_match_result = await db.execute(existing_match_query)
    if existing_match_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active or pending match. Please finish or cancel it first."
        )

    # 1. Fetch the target match
    query = select(Match).where(Match.id == match_id)
    result = await db.execute(query)
    match_record = result.scalar_one_or_none()

    # GUARD 2: Does the match exist?
    if not match_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Match not found."
        )

    # GUARD 3: Is it still pending? (Handles race conditions if 5 people click Join)
    if match_record.status != MatchStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Match is no longer available."
        )

    # GUARD 4: Prevent joining your own match
    if match_record.white_player_id == current_user.id or match_record.black_player_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="You cannot join a match you created."
        )

    # 2. Claim the empty seat
    if match_record.white_player_id is None:
        match_record.white_player_id = current_user.id
    elif match_record.black_player_id is None:
        match_record.black_player_id = current_user.id
    else:
        # Fallback (Should never trigger due to Guard 3, but safe to have)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Match is already full."
        )

    # 3. Flip the state to STARTING to initiate the WebSocket handshake phase
    match_record.status = MatchStatus.STARTING
    
    await db.commit()
    await db.refresh(match_record)

    return response(
        data=schemas.MatchResponse(
            id=match_record.id,
            white_player_id=match_record.white_player_id,
            black_player_id=match_record.black_player_id,
            status=match_record.status,
            is_rated=match_record.is_rated,
            is_private=match_record.is_private,
            time_control=match_record.time_control
        ).model_dump(),
        message="Successfully joined the match. Proceeding to WebSocket handshake."
    )

@router.get("/{match_id}")
async def get_match_state(
    match_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches the current state of a match. 
    Used by the frontend to load the board before opening the WebSocket.
    """
    query = select(Match).where(Match.id == match_id)
    result = await db.execute(query)
    match_record = result.scalar_one_or_none()

    if not match_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found."
        )

    return response(
        data=schemas.MatchResponse(
            id=match_record.id,
            white_player_id=match_record.white_player_id,
            black_player_id=match_record.black_player_id,
            status=match_record.status,
            is_rated=match_record.is_rated,
            is_private=match_record.is_private,
            time_control=match_record.time_control,
            pgn_moves=match_record.pgn_moves
        ).model_dump(),
        message="Match state retrieved successfully."
    )