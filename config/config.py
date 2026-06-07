# - ch355/config/config.py

import os

from dotenv import load_dotenv

from . import validators

load_dotenv()

APPCFG = {
    "VERSION": "0.1.0"

}

APICFG = {
    "UVICORN_LOG_LEVEL": validators.uvicorn.log_level("UVICORN_LOG_LEVEL", "INFO"),
    "UVICORN_HOST": validators.uvicorn.host("UVICORN_HOST", "0.0.0.0"),
    "UVICORN_PORT": validators.uvicorn.port("UVICORN_PORT", 8000),
    "UVICORN_RELOAD": validators.uvicorn.reload("UVICORN_RELOAD", False),
}

AUTHCFG = {
    "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID", "your-google-client-id"),
    "JWT_SECRET": os.getenv("JWT_SECRET", "super-secret-key-change-in-prod"),
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_MINUTES": 60 * 24 * 7,
    "JWT_REFRESH_EXPIRE_MINUTES": 60 * 24 * 30,
}

STORECFG = {
    "REDIS_URL": validators.storage.redis_url("REDIS_URL", "redis://localhost:6379/0"),
    "REDIS_MAX_CONNECTIONS": validators.storage.pool_size("REDIS_MAX_CONNECTIONS", 100),
    "POSTGRES_URL": validators.storage.postgres_url("POSTGRES_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ch355"),
    "POSTGRES_POOL_SIZE": validators.storage.pool_size("POSTGRES_POOL_SIZE", 10),
    "POSTGRES_MAX_OVERFLOW": validators.storage.max_overflow("POSTGRES_MAX_OVERFLOW", 20),
}