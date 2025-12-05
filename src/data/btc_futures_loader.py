"""
DEPRECATED MODULE (soft)

This file is kept only for backward compatibility.
The canonical OHLCV loader is now src/data/ohlcv_loader.py (load_ohlcv).

All new code MUST use load_ohlcv() from ohlcv_loader instead of this module.
This module may be removed in the future once all call sites are migrated.
"""

from __future__ import annotations

import pandas as pd

from .ohlcv_loader import load_ohlcv


def load_btcusdt_futures_klines(
    timeframe: str,
    n_candles: int,
    price_type: str = "latest_price",
    coinex_raw_limit: int = 1000,
    binance_timeout: int = 15,
    coinex_timeout: int = 15,
) -> pd.DataFrame:
    """
    Backward-compatible wrapper around load_ohlcv for BTCUSDT perpetual futures.
    See src/data/ohlcv_loader.py for the generic implementation.
    """
    return load_ohlcv(
        market="BTCUSDT_PERP",
        timeframe=timeframe,
        n_candles=n_candles,
        primary_exchange="coinex_futures",
        secondary_exchange="binance_futures",
        price_type=price_type,
        end_time=None,
        tz="Asia/Tehran",
        coinex_raw_limit=coinex_raw_limit,
        binance_timeout=binance_timeout,
        coinex_timeout=coinex_timeout,
    )
