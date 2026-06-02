# - ch355/main.py -

import os
import uvicorn

from contextlib import asynccontextmanager
from fastapi import FastAPI

from config import APPCFG, APICFG
from services import configure_logging, ECHO
from services import REDIS

configure_logging(
    log_level = APICFG["UVICORN_LOG_LEVEL"],
    dev = APICFG["UVICORN_RELOAD"]
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await REDIS.connect()
    except RuntimeError:
        ECHO.error("Resource initialization failed")
        os._exit(1)
    
    try:
        ECHO.info(f"Serving @ {APICFG["UVICORN_HOST"]}:{APICFG["UVICORN_PORT"]}")
        yield
    
    finally:
        await REDIS.close()

app = FastAPI(lifespan = lifespan)

@app.get("/")
async def root():
    ECHO.info("Root endpoint hit!")
    return f"ch355 API v{APPCFG["VERSION"]}"

if __name__ == "__main__":
    uvicorn.run(
        app = "main:app" if APICFG["UVICORN_RELOAD"] else app,
        log_level = APICFG["UVICORN_LOG_LEVEL"],
        host = APICFG["UVICORN_HOST"],
        port = APICFG["UVICORN_PORT"],
        reload = APICFG["UVICORN_RELOAD"],
    )