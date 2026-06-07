# - ch355/api/match/schemas.py -

import uuid

from pydantic import BaseModel, Field

from .models import MatchStatus

class MatchCreate(BaseModel):
    opponent_id: uuid.UUID | None = None
    play_as: str = Field(default="random", description="'white', 'black', or 'random'")
    is_rated: bool = Field(default=True, description="Competitive mode")
    is_private: bool = Field(default=False, description="Match visibility")
    time_control: str = Field(default="10+0", description="e.g., '10+0', '3+2', 'untimed'")

class MatchResponse(BaseModel):
    id: uuid.UUID
    white_player_id: uuid.UUID | None = None
    black_player_id: uuid.UUID | None = None
    status: MatchStatus
    is_rated: bool
    is_private: bool
    time_control: str