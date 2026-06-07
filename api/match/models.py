# - ch355/api/match/models.py -

import uuid
import enum

from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, ForeignKey, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from services.database import Base

class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    STARTING = "starting"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELED = "canceled"

class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Both are nullable now. The creator might pick Black, leaving White empty!
    white_player_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    black_player_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True) 
    
    pgn_moves: Mapped[str] = mapped_column(String, default="")
    status: Mapped[MatchStatus] = mapped_column(
        SQLEnum(MatchStatus), default=MatchStatus.PENDING, index=True
    )

    is_rated: Mapped[bool] = mapped_column(Boolean, default=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    time_control: Mapped[str] = mapped_column(String(50), default="10+0") # "10+0", "blitz", "untimed"

    winner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    white_rating_change: Mapped[int | None] = mapped_column(Integer, nullable=True)
    black_rating_change: Mapped[int | None] = mapped_column(Integer, nullable=True)

    white_time_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    black_time_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_move_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )