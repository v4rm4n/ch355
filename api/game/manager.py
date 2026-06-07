# - ch355/api/game/manager.py -

import asyncio
import json

from fastapi import WebSocket

from services.redis import REDIS
from services.logger import ECHO

class ConnectionManager:
    def __init__(self):
        # Tracks WebSockets connected to THIS specific Uvicorn worker/pod.
        # Structure: { "match_uuid": [websocket1, websocket2] }
        self.active_connections: dict[str, list[WebSocket]] = {}
        
        # Tracks Redis pubsub background tasks so we can cancel them cleanly
        self.pubsub_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, match_id: str):
        """Accepts a new WS connection and wires it up to Redis."""
        await websocket.accept()
        
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []
            # First player on this pod for this match! Start listening to Redis.
            self.pubsub_tasks[match_id] = asyncio.create_task(self._listen_to_redis(match_id))
        
        self.active_connections[match_id].append(websocket)
        ECHO.info(f"WebSocket connected locally for match {match_id}")

    def disconnect(self, websocket: WebSocket, match_id: str):
        """Removes a WS connection and cleans up Redis listeners if empty."""
        if match_id in self.active_connections:
            if websocket in self.active_connections[match_id]:
                self.active_connections[match_id].remove(websocket)
            
            # If no one on this pod is playing this match anymore, kill the Redis listener
            if not self.active_connections[match_id]:
                del self.active_connections[match_id]
                
                if match_id in self.pubsub_tasks:
                    self.pubsub_tasks[match_id].cancel()
                    del self.pubsub_tasks[match_id]
                    ECHO.info(f"Cleaned up Redis listener for match {match_id}")

    async def broadcast_to_match(self, match_id: str, message: dict):
        """
        Takes a move from a player and publishes it to Redis.
        Does NOT send directly to the local socket—relies on Redis to echo it back.
        """
        client = REDIS.get_client()
        channel = f"match:{match_id}"
        await client.publish(channel, json.dumps(message))

    async def _listen_to_redis(self, match_id: str):
        """
        Background task that subscribes to a Redis channel.
        Uses get_message() in a loop to avoid socket timeout crashes.
        """
        client = REDIS.get_client()
        pubsub = client.pubsub()
        channel = f"match:{match_id}"
        
        await pubsub.subscribe(channel)
        ECHO.info(f"Pod subscribed to Redis channel {channel}")
        
        try:
            while True:
                try:
                    # Ask Redis for a message, wait max 1 second. 
                    # ignore_subscribe_messages=True filters out system noise.
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    
                    if message and message["type"] == "message":
                        payload = message["data"]
                        
                        if isinstance(payload, bytes):
                            payload = payload.decode("utf-8")
                        
                        if match_id in self.active_connections:
                            for connection in list(self.active_connections[match_id]):
                                try:
                                    await connection.send_text(payload)
                                except Exception as ws_err:
                                    ECHO.error(f"Failed to send to WS: {ws_err}")
                                    
                except Exception as inner_err:
                    # If the socket times out underneath us, just catch it and loop again!
                    if "Timeout" in str(inner_err) or "TimeoutError" in type(inner_err).__name__:
                        pass
                    else:
                        ECHO.warning(f"Redis polling issue: {inner_err}")
                
                # Crucial: Yield control to FastAPI so it can process other players
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            # Triggered when the last player disconnects and the manager cancels the task
            ECHO.info(f"Unsubscribing from {channel}")
            await pubsub.unsubscribe(channel)
            await pubsub.close()

# Instantiate a single global instance for the router to use
manager = ConnectionManager()