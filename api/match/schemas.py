# - ch355/api/match/schemas.py -

from pydantic import BaseModel, Field
from typing import Optional

class MatchCreate(BaseModel):
    opponent_id: Optional[int] = None
    play_as: str = Field(default="random", description="'white', 'black', or 'random'")
    is_rated: bool = Field(default=True, description="Competitive mode")
    is_private: bool = Field(default=False, description="Match visibility")
    time_control: str = Field(default="10+0", description="e.g., '10+0', '3+2', 'untimed'")

class MatchResponse(BaseModel):
    id: int
    white_player_id: Optional[int]
    black_player_id: Optional[int]
    status: str
    is_rated: bool
    is_private: bool
    time_control: str