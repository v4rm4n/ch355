# - ch355/api/auth/schemas.py -

from pydantic import BaseModel, Field

class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., description="The JWT ID token from Google")

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"