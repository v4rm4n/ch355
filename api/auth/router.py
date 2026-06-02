# - ch355/api/auth/router.py -

from fastapi import APIRouter

from api.utils import response

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post("/register", status_code = 201)
async def register():
    return response(message = "User registerd successfully!")

@router.post("/login")
async def login():
    return response(
        message = "Logged in successfully!",
        data = {"access_token": "dummy-jwt-token", "token_type": "bearer"},
        code = 200,
        )