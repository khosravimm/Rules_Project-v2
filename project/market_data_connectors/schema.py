from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

import pandas as pd


class MarketKind(str, Enum):
    CRYPTO = "crypto"
    INDEX = "index"
    FX = "fx"
    COMMODITY = "commodity"
    MACRO = "macro"
    CRYPTO_AGG = "crypto_agg"


def _standardize_df(
    df: pd.DataFrame,
    source: str,
    metadata: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Ensure a uniform OHLCV schema with datetime index.
    Missing columns are filled with NaN; non-price series map their value to close/open/high/low.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "source", "metadata"])

    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "time" in df.columns:
            df.index = pd.to_datetime(df.pop("time"), utc=True, errors="coerce")
        else:
            df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
    df.index.name = "time"

    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            df[col] = pd.NA

    # If prices missing but a single 'value' exists (macro series), replicate to OHLC.
    if df[["open", "high", "low", "close"]].isna().all().all():
        value_col = None
        for candidate in ("value", "price", "close"):
            if candidate in df.columns and not df[candidate].isna().all():
                value_col = candidate
                break
        if value_col:
            df["open"] = df["high"] = df["low"] = df["close"] = df[value_col]

    df["source"] = source
    df["metadata"] = metadata or {}
    return df[["open", "high", "low", "close", "volume", "source", "metadata"]]
