# - ch355/api/router.py -

from fastapi import APIRouter

main_router = APIRouter(prefix="/api")

from .auth import auth_router
main_router.include_router(auth_router)

from .match import match_router
main_router.include_router(match_router)

from .game import game_router
main_router.include_router(game_router)
