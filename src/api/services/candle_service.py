from __future__ import annotations

from typing import Optional

import pandas as pd

from api.services import data_access as da


def fetch_candles(timeframe: str, start: Optional[pd.Timestamp], end: Optional[pd.Timestamp], limit: int) -> pd.DataFrame:
    df = da.load_candles_between(timeframe, start, end)
    if start is None and end is None and limit and not df.empty and len(df) > limit:
        df = df.tail(limit)
    return df


def fetch_latest_candle(timeframe: str) -> pd.DataFrame:
    df = da.load_candles_between(timeframe, None, None)
    if df.empty:
        return df
    return df.tail(1)


__all__ = ["fetch_candles", "fetch_latest_candle"]
