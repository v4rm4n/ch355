# - ch355/api/auth/utils.py -

from datetime import datetime, timedelta, timezone
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt

from config import AUTHCFG

def verify_google_token(token: str) -> dict:
    """Verifies the Google ID token and returns the user's profile info."""
    try:
        return dict(
            id_token.verify_oauth2_token(
                token, requests.Request(), AUTHCFG["GOOGLE_CLIENT_ID"]
            )
        )
    except ValueError as e:
        raise ValueError(f"Invalid Google token: {str(e)}")

def create_access_token(data: dict) -> str:
    """Mints a new JWT for the ch355 game backend."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=AUTHCFG["JWT_EXPIRE_MINUTES"])
    to_encode.update({"exp": expire})
    
    return jwt.encode(to_encode, AUTHCFG["JWT_SECRET"], algorithm=AUTHCFG["JWT_ALGORITHM"])