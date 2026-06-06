# - ch355/api/auth/models.py -

from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from services.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    elo_rating: Mapped[int] = mapped_column(Integer, default=1200, nullable=False)
    matches_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matches_won: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matches_lost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matches_drawn: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    conduct_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    resign_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)