from __future__ import annotations

import os
from typing import Dict

import pandas as pd

from .schema import _standardize_df


def load_alpha_series(symbol: str, category: str, timeframe: str) -> pd.DataFrame:
    """
    Load series via Alpha Vantage wrapper.
    category examples: 'crypto', 'fx', 'stock'
    timeframe examples: '1min', '5min', '15min', '30min', '60min', 'daily', 'weekly'
    """
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        raise EnvironmentError("Set ALPHAVANTAGE_API_KEY in environment to use Alpha Vantage.")

    try:
        from alpha_vantage.timeseries import TimeSeries  # type: ignore
        from alpha_vantage.foreignexchange import ForeignExchange  # type: ignore
        from alpha_vantage.cryptocurrencies import CryptoCurrencies  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "alpha_vantage is required for load_alpha_series. Install with `pip install alpha_vantage`."
        ) from exc

    category_lower = category.lower()
    if category_lower == "stock":
        ts = TimeSeries(key=api_key, output_format="pandas")
        if timeframe in {"1min", "5min", "15min", "30min", "60min"}:
            data, _meta = ts.get_intraday(symbol=symbol, interval=timeframe, outputsize="full")
        elif timeframe == "weekly":
            data, _meta = ts.get_weekly(symbol=symbol)
        else:
            data, _meta = ts.get_daily(symbol=symbol, outputsize="full")
        df = data
    elif category_lower == "fx":
        fx = ForeignExchange(key=api_key, output_format="pandas")
        if timeframe == "daily":
            data, _meta = fx.get_currency_exchange_daily(from_symbol=symbol.split("/")[0], to_symbol=symbol.split("/")[1])
        else:
            # fallback to intraday 5min
            data, _meta = fx.get_currency_exchange_intraday(
                from_symbol=symbol.split("/")[0],
                to_symbol=symbol.split("/")[1],
                interval="5min",
                outputsize="full",
            )
        df = data
    elif category_lower == "crypto":
        cc = CryptoCurrencies(key=api_key, output_format="pandas")
        data, _meta = cc.get_digital_currency_daily(symbol=symbol, market="USD")
        df = data
    else:
        raise ValueError(f"Unsupported category for Alpha Vantage: {category}")

    df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
    # AlphaVantage column names vary; attempt to map.
    rename_map = {}
    for col in df.columns:
        cl = col.lower()
        if "open" in cl:
            rename_map[col] = "open"
        elif "high" in cl:
            rename_map[col] = "high"
        elif "low" in cl:
            rename_map[col] = "low"
        elif "close" in cl:
            rename_map[col] = "close"
        elif "volume" in cl:
            rename_map[col] = "volume"
        elif "market cap" in cl:
            rename_map[col] = "volume"
    df = df.rename(columns=rename_map)
    meta: Dict = {"symbol": symbol, "timeframe": timeframe, "category": category_lower}
    return _standardize_df(df, source="alpha_vantage", metadata=meta)
