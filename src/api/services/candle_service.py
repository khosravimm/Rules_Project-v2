from __future__ import annotations

from typing import Optional

import pandas as pd

from api.services import data_access as da


def fetch_candles(timeframe: str, start: Optional[pd.Timestamp], end: Optional[pd.Timestamp], limit: int) -> pd.DataFrame:
    df = da.load_candles_between(timeframe, start, end)
    if start is None and end is None and limit and not df.empty and len(df) > limit:
        df = df.tail(limit)
    return df


def get_window_around(
    timeframe: str,
    center_ts_utc: pd.Timestamp,
    before_bars: int = 80,
    after_bars: int = 40,
) -> pd.DataFrame:
    """
    Return a candle window around a center timestamp (inclusive).

    - center_ts_utc must be tz-aware UTC (naive values are localized to UTC).
    - Returns up to `before_bars` prior candles, the center candle, and
      up to `after_bars` subsequent candles (fewer if at dataset edges).
    """
    if before_bars < 0 or after_bars < 0:
        raise ValueError("before_bars/after_bars must be non-negative.")

    center = da._to_utc(center_ts_utc)
    if pd.isna(center):
        raise ValueError("center_ts_utc is invalid or cannot be parsed.")

    df = da.load_candles_between(timeframe, None, None)
    if df.empty:
        return df

    df = df.sort_values("open_time").reset_index(drop=True)
    times = df["open_time"]

    # Locate the candle at or before the center timestamp.
    prior = df[df["open_time"] <= center]
    if prior.empty:
        center_idx = 0
    else:
        center_idx = int(prior.index[-1])

    start_idx = max(center_idx - before_bars, 0)
    end_idx = min(center_idx + after_bars, len(df) - 1)

    return df.iloc[start_idx : end_idx + 1].reset_index(drop=True)


def fetch_latest_candle(timeframe: str) -> pd.DataFrame:
    df = da.load_candles_between(timeframe, None, None)
    if df.empty:
        return df
    return df.tail(1)


__all__ = ["fetch_candles", "fetch_latest_candle", "get_window_around"]
