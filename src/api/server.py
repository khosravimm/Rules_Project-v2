from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from .endpoints.trading import router as trading_router

app = FastAPI(title="PrisonBreaker API", version="0.1.0")
app.include_router(trading_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
