import enum

# --- STRICT TYPE DEFINITIONS FOR WEBSOCKET EVENTS ---
class WSEvent(str, enum.Enum):
    MOVE = "move"
    CHAT = "chat"
    PLAYER_CONNECTED = "player_connected"
    PLAYER_DISCONNECTED = "player_disconnected"
    ERROR = "error"
# ----------------------------------------------------