from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data.ohlcv_loader import load_ohlcv

router = APIRouter()

Timeframe = Literal["5m", "15m", "1h", "4h", "1d"]
Direction = Literal["long", "short", "neutral"]
Strength = Literal["weak", "medium", "strong"]


class Candle(BaseModel):
    time: int  # unix seconds
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class CandlesResponse(BaseModel):
    symbol: str
    timeframe: Timeframe
    candles: List[Candle]


class PatternHit(BaseModel):
    id: str
    time: int  # unix seconds
    direction: Direction
    strength: Optional[Strength] = None


class PatternHitsResponse(BaseModel):
    symbol: str
    timeframe: Timeframe
    hits: List[PatternHit]


_TIMEFRAME_SUPPORTED = {"5m", "4h"}
_PATTERN_PATHS = {
    "4h": Path("data/pattern_hits_4h_level1.parquet"),
    "5m": Path("data/pattern_hits_5m_level1.parquet"),
}


@router.get("/api/candles", response_model=CandlesResponse)
def get_candles(
    symbol: str = Query("BTCUSDT"),
    timeframe: Timeframe = Query("4h"),
    limit: int = Query(500, ge=1, le=1500),
) -> CandlesResponse:
    if symbol.upper() not in {"BTCUSDT", "BTCUSDT_PERP"}:
        raise HTTPException(status_code=400, detail="Only BTCUSDT is supported currently.")
    tf = timeframe.lower()
    if tf not in _TIMEFRAME_SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{timeframe}'. Use one of {_TIMEFRAME_SUPPORTED}.")

    try:
        df = load_ohlcv(
            market="BTCUSDT_PERP",
            timeframe=tf,
            n_candles=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to load candles: {exc!r}")

    candles: List[Candle] = []
    if not df.empty:
        # ensure UTC and unix seconds
        times = pd.to_datetime(df["open_time"], utc=True, errors="coerce")
        for _, row in df.assign(open_time=times).iterrows():
            candles.append(
                Candle(
                    time=int(row["open_time"].timestamp()),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]) if "volume" in row else None,
                )
            )

    return CandlesResponse(symbol="BTCUSDT", timeframe=tf, candles=candles)


@router.get("/api/pattern-hits", response_model=PatternHitsResponse)
def get_pattern_hits(
    symbol: str = Query("BTCUSDT"),
    timeframe: Timeframe = Query("4h"),
    limit: int = Query(200, ge=1, le=2000),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
) -> PatternHitsResponse:
    tf = timeframe.lower()
    if tf not in _TIMEFRAME_SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{timeframe}'. Use one of {_TIMEFRAME_SUPPORTED}.")
    path = _PATTERN_PATHS[tf]
    if not path.exists():
        return PatternHitsResponse(symbol=symbol, timeframe=tf, hits=[])

    try:
        df_all = pd.read_parquet(path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to load pattern hits: {exc!r}")

    cols_keep = [c for c in ["pattern_id", "id", "timeframe", "answer_time", "pattern_type", "strength"] if c in df_all.columns]
    df = df_all[cols_keep].copy()

    if "timeframe" in df.columns:
        df = df[df["timeframe"] == tf]
    if "answer_time" in df.columns:
        df["answer_time"] = pd.to_datetime(df["answer_time"], utc=True, errors="coerce")
        if start:
            df = df[df["answer_time"] >= pd.to_datetime(start, utc=True)]
        if end:
            df = df[df["answer_time"] <= pd.to_datetime(end, utc=True)]

    df = df.sort_values("answer_time", ascending=False).head(limit)

    hits: List[PatternHit] = []
    for _, row in df.iterrows():
        ts = row.get("answer_time")
        unix_ts = int(ts.timestamp()) if pd.notna(ts) else 0
        hits.append(
            PatternHit(
                id=str(row.get("pattern_id") or row.get("id") or ""),
                time=unix_ts,
                direction="neutral",
                strength=row.get("strength") if pd.notna(row.get("strength")) else None,
            )
        )

    return PatternHitsResponse(symbol=symbol, timeframe=tf, hits=hits)
