# - ch355/api/match/utils.py -

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.auth.models import User

from .models import Match

def calculate_elo(rating_a: int, rating_b: int, outcome: float, k_factor: int = 32) -> int:
    """
    Standard Elo Rating implementation.
    Outcome parameter states: 1.0 = Win, 0.0 = Loss, 0.5 = Draw
    """
    expected_score = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))
    rating_change = round(k_factor * (outcome - expected_score))
    return int(rating_change)

async def resolve_match_ratings(
    match_record: Match, 
    winner_id: uuid.UUID | None, 
    is_draw: bool, 
    db: AsyncSession
) -> tuple[int | None, int | None]:
    """
    Mutates user profiles with computed Elo changes if the match is competitive.
    Saves state histories to the match record object directly.
    """
    # If the match was created casual mode, explicitly bypass updates
    if not match_record.is_rated:
        return None, None

    # Fetch User instances out of the database to perform mathematical operations
    white_user = await db.get(User, match_record.white_player_id)
    black_user = await db.get(User, match_record.black_player_id)

    if not white_user or not black_user:
        return None, None

    # Cache old scores
    w_old = white_user.elo_rating
    b_old = black_user.elo_rating

    if is_draw:
        w_change = calculate_elo(w_old, b_old, 0.5)
        b_change = calculate_elo(b_old, w_old, 0.5)
    else:
        # Determine exact point alignments based on the color allocation of the winner
        if winner_id == match_record.white_player_id:
            w_change = calculate_elo(w_old, b_old, 1.0)
            b_change = calculate_elo(b_old, w_old, 0.0)
            white_user.matches_won += 1
            black_user.matches_lost += 1
        else:
            w_change = calculate_elo(w_old, b_old, 0.0)
            b_change = calculate_elo(b_old, w_old, 1.0)
            white_user.matches_lost += 1
            black_user.matches_won += 1

    if is_draw:
        white_user.matches_drawn += 1
        black_user.matches_drawn += 1

    white_user.matches_played += 1
    black_user.matches_played += 1

    # Mutate structural profile values
    white_user.elo_rating += w_change
    black_user.elo_rating += b_change

    # Map variables straight onto our persistent database instance columns
    match_record.winner_id = winner_id
    match_record.white_rating_change = w_change
    match_record.black_rating_change = b_change

    return w_change, b_change

def parse_time_control(time_control_str: str) -> tuple[float, float]:
    """
    Parses strings like '10+5' or '3+2' into (base_seconds, increment_seconds).
    Defaults to 10 minutes (600s) flat if parsing fails or says 'untimed'.
    """
    try:
        if "+" in time_control_str:
            minutes_str, increment_str = time_control_str.split("+")
            base_seconds = float(minutes_str) * 60.0
            increment_seconds = float(increment_str)
            return base_seconds, increment_seconds
    except Exception:
        pass
    
    # Fallback default (10 minutes base, 0 increment)
    return 600.0, 0.0

def format_pgn_clock(seconds_remaining: float) -> str:
    """
    Formats remaining seconds into standard PGN clock comment format.
    The chess exporter handles the outer braces automatically.
    """
    if seconds_remaining < 0:
        seconds_remaining = 0.0
        
    hours = int(seconds_remaining // 3600)
    minutes = int((seconds_remaining % 3600) // 60)
    seconds = int(seconds_remaining % 60)
    milliseconds = int(round((seconds_remaining % 1) * 1000))
    
    return f"[%clk {hours:01d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}]"