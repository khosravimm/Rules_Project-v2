from __future__ import annotations

from typing import Dict

import pandas as pd

from .schema import _standardize_df


_YF_INTERVAL_MAP = {
    "1m": "1m",
    "2m": "2m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "90m": "90m",
    "1d": "1d",
    "1wk": "1wk",
    "1mo": "1mo",
    "4h": "60m",  # approximate using 1h; users can aggregate downstream
}


def load_traditional_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Load OHLCV for indices/ETFs/stocks via yfinance.
    """
    try:
        import yfinance as yf  # type: ignore
    except ImportError as exc:
        raise ImportError("yfinance is required for load_traditional_ohlcv. Install with `pip install yfinance`.") from exc

    interval = _YF_INTERVAL_MAP.get(timeframe, timeframe)
    ticker = yf.Ticker(symbol)
    df = ticker.history(interval=interval)
    if df.empty:
        return _standardize_df(df, source="yfinance", metadata={"symbol": symbol, "timeframe": timeframe})
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df.index = pd.to_datetime(df.index, utc=True)
    meta: Dict = {"symbol": symbol, "timeframe": timeframe}
    return _standardize_df(df, source="yfinance", metadata=meta)
