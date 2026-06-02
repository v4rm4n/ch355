# - ch355/api/router.py -

from fastapi import APIRouter

main_router = APIRouter(prefix="/api")

from .auth import auth_router
main_router.include_router(auth_router)
