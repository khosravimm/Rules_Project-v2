from __future__ import annotations

import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.config import API_PORT
from api.endpoints.patterns import router as patterns_router
from api.endpoints.trading import router as trading_router
from infra.logging import get_logger, setup_logging

setup_logging()
logger = get_logger("api")
app = FastAPI(title="PrisonBreaker API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REQUEST_COUNT = 0
START_TIME = time.time()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    global REQUEST_COUNT
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    REQUEST_COUNT += 1
    logger.info(
        "request %s %s -> %s in %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(trading_router)
app.include_router(patterns_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict:
    uptime = time.time() - START_TIME
    return {"uptime_seconds": uptime, "request_count": REQUEST_COUNT}


if __name__ == "__main__":
    uvicorn.run("api.server:app", host="0.0.0.0", port=API_PORT, reload=True)
