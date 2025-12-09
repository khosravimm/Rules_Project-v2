from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api.config import SUPPORTED_TIMEFRAMES
from api.schemas import Candle, CandlesResponse, PatternHit, PatternHitsResponse
from api.services.candle_service import fetch_candles, fetch_latest_candle
from api.services.data_access import DEFAULT_SYMBOL, _to_utc, load_candles_between
from api.services.pattern_service import fetch_pattern_hits
from core.candles import derive_direction_from_candles

router = APIRouter()


@router.get("/api/candles", response_model=CandlesResponse)
def get_candles(
    symbol: str = Query(DEFAULT_SYMBOL),
    timeframe: str = Query("4h"),
    start: Optional[str] = Query(None, description="ISO-8601 UTC start"),
    end: Optional[str] = Query(None, description="ISO-8601 UTC end"),
    limit: int = Query(500, ge=1, le=5000),
) -> CandlesResponse:
    tf = timeframe.lower()
    if tf not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{timeframe}'. Use one of {SUPPORTED_TIMEFRAMES}.")

    start_ts = _to_utc(start) if start else None
    end_ts = _to_utc(end) if end else None
    try:
        df = fetch_candles(tf, start_ts, end_ts, limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"failed to load candles: {exc!r}")

    candles: List[Candle] = []
    for row in df.itertuples():
        ts = pd.to_datetime(row.open_time, utc=True, errors="coerce")
        candles.append(
            Candle(
                timestamp=ts.to_pydatetime(),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume) if hasattr(row, "volume") else None,
            )
        )

    return CandlesResponse(symbol=symbol, timeframe=tf, candles=candles)


@router.get("/api/pattern-hits", response_model=PatternHitsResponse)
def get_pattern_hits(
    symbol: str = Query(DEFAULT_SYMBOL),
    timeframe: str = Query("4h"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    pattern_type: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    pattern_id: Optional[str] = Query(None),
    strength_level: Optional[str] = Query(None, description="strength level filter"),
    limit: int = Query(400, ge=1, le=5000),
) -> PatternHitsResponse:
    tf = timeframe.lower()
    if tf not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{timeframe}'. Use one of {SUPPORTED_TIMEFRAMES}.")

    start_ts = _to_utc(start) if start else None
    end_ts = _to_utc(end) if end else None

    df_hits = fetch_pattern_hits(
        timeframe=tf,
        start=start_ts,
        end=end_ts,
        pattern_type=pattern_type,
        pattern_id=pattern_id,
        direction=direction,
        strength_level=strength_level,
    )
    if df_hits.empty:
        return PatternHitsResponse(symbol=symbol, timeframe=tf, hits=[])

    try:
        candle_df = load_candles_between(tf, None, None)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"failed to load candles for direction check: {exc!r}")
    hits: List[PatternHit] = []

    for row in df_hits.itertuples():
        derived_dir = derive_direction_from_candles(getattr(row, "answer_time", pd.NaT), candle_df)
        dir_filter = getattr(row, "_direction_filter", None)
        if dir_filter and derived_dir and derived_dir != dir_filter:
            continue
        hits.append(
            PatternHit(
                pattern_id=str(getattr(row, "pattern_id", "")),
                pattern_type=getattr(row, "pattern_type", None),
                direction=derived_dir,
                start_ts=pd.to_datetime(getattr(row, "x0", None), utc=True, errors="coerce").to_pydatetime()
                if getattr(row, "x0", None) is not None
                else None,
                end_ts=pd.to_datetime(getattr(row, "x1", None), utc=True, errors="coerce").to_pydatetime()
                if getattr(row, "x1", None) is not None
                else None,
                entry_candle_ts=pd.to_datetime(getattr(row, "answer_time", None), utc=True, errors="coerce").to_pydatetime()
                if getattr(row, "answer_time", None) is not None
                else None,
                accuracy=float(getattr(row, "score", np.nan)) if hasattr(row, "score") and not pd.isna(row.score) else None,
                support=float(getattr(row, "support", np.nan)) if hasattr(row, "support") and not pd.isna(row.support) else None,
                lift=float(getattr(row, "lift", np.nan)) if hasattr(row, "lift") and not pd.isna(row.lift) else None,
                stability=float(getattr(row, "stability", np.nan)) if hasattr(row, "stability") and not pd.isna(row.stability) else None,
                strength_level=getattr(row, "strength", None),
            )
        )
        if len(hits) >= limit:
            break

    return PatternHitsResponse(symbol=symbol, timeframe=tf, hits=hits)


@router.get("/api/candles/latest", response_model=CandlesResponse)
def get_latest_candle(
    symbol: str = Query(DEFAULT_SYMBOL),
    timeframe: str = Query("4h"),
) -> CandlesResponse:
    tf = timeframe.lower()
    if tf not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{timeframe}'. Use one of {SUPPORTED_TIMEFRAMES}.")
    try:
        df = fetch_latest_candle(tf)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"failed to load candles: {exc!r}")

    if df.empty:
        return CandlesResponse(symbol=symbol, timeframe=tf, candles=[])
    last = df.tail(1)
    candles: List[Candle] = []
    for row in last.itertuples():
        ts = pd.to_datetime(row.open_time, utc=True, errors="coerce")
        candles.append(
            Candle(
                timestamp=ts.to_pydatetime(),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume) if hasattr(row, "volume") else None,
            )
        )
    return CandlesResponse(symbol=symbol, timeframe=tf, candles=candles)
