# - ch355/api/game/router.py -

import jwt
import uuid
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils import get_db
from api.auth.models import User
from api.match.models import Match, MatchStatus
from config.config import AUTHCFG

from .manager import manager
from services.logger import ECHO

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
        "event": "player_connected",
        "user_id": str(user.id),
        "name": user.name
    })

    # 4. The Infinite Game Loop
    try:
        while True:
            # Wait for the client to send a JSON message (e.g., {"event": "move", "uci": "e2e4"})
            data = await websocket.receive_text()
            
            # Parse it to ensure it's valid JSON, then add the sender's ID
            payload = json.loads(data)
            payload["sender_id"] = str(user.id)
            
            # Shoot it up to Redis to be broadcast to both players!
            await manager.broadcast_to_match(match_id_str, payload)

    except WebSocketDisconnect:
        # 5. Handle Disconnections Elegantly
        manager.disconnect(websocket, match_id_str)
        
        await manager.broadcast_to_match(match_id_str, {
            "event": "player_disconnected",
            "user_id": str(user.id),
            "name": user.name
        })
    except Exception as e:
        ECHO.error(f"WebSocket error in match {match_id_str}: {e}")
        manager.disconnect(websocket, match_id_str)