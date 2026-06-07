# - ch355/api/game/router.py -

import jwt
import uuid
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.logger import ECHO

from api.utils import get_db
from api.auth.models import User
from api.match.models import Match, MatchStatus
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

    # 4. The Infinite Game Loop
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
                
                # 1. Fetch the absolute latest state from Postgres
                await db.refresh(match_record)

                # 2. Prevent moves if the game is over
                if match_record.status not in [MatchStatus.STARTING, MatchStatus.ACTIVE]:
                    await websocket.send_text(json.dumps({"event": schemas.WSEvent.ERROR, "message": "Match is over."}))
                    continue

                # 3. Enforce Turn Order
                current_turn_color = get_turn_color(match_record.pgn_moves)
                expected_id = match_record.white_player_id if current_turn_color == "white" else match_record.black_player_id
                
                if str(expected_id) != str(user.id):
                    await websocket.send_text(json.dumps({"event": schemas.WSEvent.ERROR, "message": "Not your turn!"}))
                    continue

                # 4. Validate and Process the Move
                is_legal, new_pgn, engine_status = process_move(match_record.pgn_moves, uci_move)
                
                if not is_legal:
                    await websocket.send_text(json.dumps({"event": schemas.WSEvent.ERROR, "message": f"Illegal move: {uci_move}"}))
                    continue

                # 5. Update Postgres
                match_record.pgn_moves = new_pgn
                
                # Flip from STARTING to ACTIVE on the very first move
                if match_record.status == MatchStatus.STARTING:
                    match_record.status = MatchStatus.ACTIVE
                    
                # Handle Checkmates / Draws
                if engine_status == "completed":
                    match_record.status = MatchStatus.COMPLETED
                
                await db.commit()

                # 6. Append the official PGN to the payload so frontends can sync perfectly
                payload["pgn"] = new_pgn
                payload["match_status"] = match_record.status.value

            # Shoot it up to Redis to be broadcast to both players!
            await manager.broadcast_to_match(match_id_str, payload)

    except WebSocketDisconnect:
        # 5. Handle Disconnections Elegantly
        manager.disconnect(websocket, match_id_str)
        
        await manager.broadcast_to_match(match_id_str, {
            "event": schemas.WSEvent.PLAYER_DISCONNECTED,
            "user_id": str(user.id),
            "name": user.name
        })
    except Exception as e:
        ECHO.error(f"WebSocket error in match {match_id_str}: {e}")
        manager.disconnect(websocket, match_id_str)