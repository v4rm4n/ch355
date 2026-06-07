# - ch355/api/game/router.py -

import jwt
import uuid
import json

from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.logger import ECHO

from api.utils import get_db
from api.auth.models import User
from api.match.models import Match, MatchStatus
from api.match.utils import parse_time_control, format_pgn_clock, resolve_match_ratings
from config.config import AUTHCFG

from . import schemas
from .manager import manager
from .engine import process_move, get_turn_color


router = APIRouter(
    prefix="/game",
    tags=["Game WebSocket"]
)

async def get_ws_current_user(token: str, db: AsyncSession) -> User | None:
    """Custom authentication bouncer for WebSockets."""
    try:
        token_data = jwt.decode(token, AUTHCFG["JWT_SECRET"], algorithms=["HS256"])
        if token_data.get("type") != "access":
            raise ValueError("Invalid token type")
            
        user_id_str = token_data.get("sub")
        if not user_id_str:
            raise ValueError("Token missing subject")
            
        user_id = uuid.UUID(user_id_str)
        
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
            
        return user
    except Exception as e:
        ECHO.warning(f"WebSocket auth failed: {e}")
        return None


@router.websocket("/ws/{match_id}")
async def game_websocket(
    websocket: WebSocket,
    match_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # 1. Authenticate the WebSocket
    user = await get_ws_current_user(token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Fetch the match and verify the user actually belongs in this game
    query = select(Match).where(Match.id == match_id)
    result = await db.execute(query)
    match_record = result.scalar_one_or_none()

    if not match_record:
        await websocket.close(code=status.WS_1004_NO_STATUS_RCVD)
        return

    is_player = (match_record.white_player_id == user.id or match_record.black_player_id == user.id)
    if not is_player:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 3. Connect to the Manager and Redis
    match_id_str = str(match_id)
    await manager.connect(websocket, match_id_str)
    
    # Optional: Broadcast a system message that a player connected
    await manager.broadcast_to_match(match_id_str, {
        "event": schemas.WSEvent.PLAYER_CONNECTED,
        "user_id": str(user.id),
        "name": user.name
    })

    # Game Loop
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"event": schemas.WSEvent.ERROR, "message": "Invalid JSON"}))
                continue
                
            payload["sender_id"] = str(user.id)
            event_type = payload.get("event")

            # --- THE AUTHORITATIVE GAME LOGIC ---
            if event_type == schemas.WSEvent.MOVE:
                uci_move = payload.get("uci")

                # TYPE GUARD: Prevent None values from filtering down into the chess engine parameters
                if not uci_move or not isinstance(uci_move, str):
                    await websocket.send_text(json.dumps({"event": schemas.WSEvent.ERROR, "message": "Invalid or missing UCI move attribute."}))
                    continue

                await db.refresh(match_record)

                if match_record.status not in [MatchStatus.STARTING, MatchStatus.ACTIVE]:
                    await websocket.send_text(json.dumps({"event": schemas.WSEvent.ERROR, "message": "Match is over."}))
                    continue

                current_turn_color = get_turn_color(match_record.pgn_moves)
                expected_id = match_record.white_player_id if current_turn_color == "white" else match_record.black_player_id
                
                if str(expected_id) != str(user.id):
                    await websocket.send_text(json.dumps({"event": schemas.WSEvent.ERROR, "message": "Not your turn!"}))
                    continue

                # Initialize fallback tracking variables at parent scope so Pylance knows they are always bound
                base_fallback = 0.0
                increment_secs = 0.0

                # Check if clocks should even tick
                is_timed = match_record.time_control.lower() != "untimed"

                # --- AUTHORITATIVE CLOCK MATH (ONLY IF TIMED) ---
                if is_timed:
                    now = datetime.now(timezone.utc)
                    base_fallback, increment_secs = parse_time_control(match_record.time_control)
                    
                    white_time = match_record.white_time_left if match_record.white_time_left is not None else base_fallback
                    black_time = match_record.black_time_left if match_record.black_time_left is not None else base_fallback
                    
                    if match_record.status == MatchStatus.ACTIVE and match_record.last_move_at is not None:
                        elapsed_seconds = (now - match_record.last_move_at).total_seconds()
                        
                        if current_turn_color == "white":
                            white_time -= elapsed_seconds
                            match_record.white_time_left = white_time
                            
                            if white_time <= 0:
                                match_record.status = MatchStatus.COMPLETED
                                await resolve_match_ratings(match_record, match_record.black_player_id, False, db)
                                await db.commit()
                                await manager.broadcast_to_match(match_id_str, {
                                    "event": schemas.WSEvent.GAME_OVER, 
                                    "reason": "timeout", 
                                    "winner_id": str(match_record.black_player_id),
                                    "match_status": match_record.status.value
                                })
                                continue
                            
                            match_record.white_time_left = white_time + increment_secs
                        else:
                            black_time -= elapsed_seconds
                            match_record.black_time_left = black_time
                            
                            if black_time <= 0:
                                match_record.status = MatchStatus.COMPLETED
                                await resolve_match_ratings(match_record, match_record.white_player_id, False, db)
                                await db.commit()
                                await manager.broadcast_to_match(match_id_str, {
                                    "event": schemas.WSEvent.GAME_OVER, 
                                    "reason": "timeout", 
                                    "winner_id": str(match_record.white_player_id),
                                    "match_status": match_record.status.value
                                })
                                continue
                            
                            match_record.black_time_left = black_time + increment_secs

                    # Always track the last move checkpoint time for the next turn calculations
                    match_record.last_move_at = now
                else:
                    # Clean up fields for untimed games so they show up as null in database records
                    match_record.white_time_left = None
                    match_record.black_time_left = None
                    match_record.last_move_at = None
                # -------------------------------------------------

                # --- CALCULATE TIME ANNOTATION FOR THE COMPLETED MOVE ---
                clk_annotation = None
                if is_timed:
                    # We look at the updated post-move values now calculated perfectly in the DB record
                    active_clock_val = match_record.white_time_left if current_turn_color == "white" else match_record.black_time_left
                    clock_to_format = active_clock_val if active_clock_val is not None else base_fallback
                    clk_annotation = format_pgn_clock(clock_to_format)

                # --- PROCESS MOVE & EMBED GENERATED CLOCK ATTACHMENT ---
                is_legal, new_pgn, engine_status = process_move(
                    match_record.pgn_moves, 
                    uci_move, 
                    clock_annotation=clk_annotation
                )

                if not is_legal:
                    await websocket.send_text(json.dumps({"event": schemas.WSEvent.ERROR, "message": f"Illegal move: {uci_move}"}))
                    continue

                # Natively stores the clean history string built by python-chess
                match_record.pgn_moves = new_pgn

                if match_record.status == MatchStatus.STARTING:
                    match_record.status = MatchStatus.ACTIVE
                    
                if engine_status == "completed":
                    match_record.status = MatchStatus.COMPLETED
                    winner_id = match_record.white_player_id if current_turn_color == "white" else match_record.black_player_id
                    w_change, b_change = await resolve_match_ratings(match_record, winner_id, False, db)
                    payload["winner_id"] = str(winner_id)

                await db.commit()

                # Sync payload values directly down to client targets
                payload["pgn"] = match_record.pgn_moves
                payload["match_status"] = match_record.status.value
                payload["white_time_left"] = match_record.white_time_left
                payload["black_time_left"] = match_record.black_time_left

            await manager.broadcast_to_match(match_id_str, payload)

    except WebSocketDisconnect:
        manager.disconnect(websocket, match_id_str)
        await manager.broadcast_to_match(match_id_str, {
            "event": schemas.WSEvent.PLAYER_DISCONNECTED,
            "user_id": str(user.id),
            "name": user.name
        })
    except Exception as e:
        ECHO.error(f"WebSocket error in match {match_id_str}: {e}")
        manager.disconnect(websocket, match_id_str)