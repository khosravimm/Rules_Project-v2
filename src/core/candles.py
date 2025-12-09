"""Domain helpers around candle data."""

from __future__ import annotations

from typing import Optional

import pandas as pd


def derive_direction_from_candles(
    answer_time: pd.Timestamp,
    candles: pd.DataFrame,
) -> Optional[str]:
    """
    Infer long/short/neutral direction from the answer candle close/open.

    The function intentionally keeps the legacy long/short/neutral mapping
    so upper layers can map to up/down/flat if needed.
    """
    if candles.empty or pd.isna(answer_time):
        return None
    row = candles[candles["open_time"] == answer_time]
    if row.empty:
        return None
    r = float(row.iloc[0]["close"] - row.iloc[0]["open"])
    if r > 0:
        return "long"
    if r < 0:
        return "short"
    return "neutral"


__all__ = ["derive_direction_from_candles"]
