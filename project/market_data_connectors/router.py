from __future__ import annotations

from typing import Optional

import pandas as pd

from .schema import MarketKind
from .crypto_ccxt import load_crypto_ohlcv
from .traditional_yfinance import load_traditional_ohlcv
from .traditional_alpha_vantage import load_alpha_series
from .macro_fred import load_macro_series
from .crypto_aggregate_coingecko import load_crypto_aggregate


def load_market_series(
    symbol: str,
    kind: MarketKind,
    timeframe: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    exchange: str = "binance",
) -> pd.DataFrame:
    """
    Route data loading to appropriate connector.
    """
    if kind == MarketKind.CRYPTO:
        return load_crypto_ohlcv(symbol=symbol, exchange=exchange, timeframe=timeframe, since=start)
    if kind in {MarketKind.INDEX, MarketKind.FX, MarketKind.COMMODITY}:
        # Use yfinance for these traditional tickers
        df = load_traditional_ohlcv(symbol=symbol, timeframe=timeframe)
        if start:
            df = df[df.index >= pd.to_datetime(start, utc=True)]
        if end:
            df = df[df.index <= pd.to_datetime(end, utc=True)]
        return df
    if kind == MarketKind.MACRO:
        return load_macro_series(series_id=symbol)
    if kind == MarketKind.CRYPTO_AGG:
        return load_crypto_aggregate(metric=symbol)
    if kind == MarketKind.FX:
        return load_alpha_series(symbol=symbol, category="fx", timeframe=timeframe)

    # fallback for alpha vantage categories (stock/crypto)
    if kind == MarketKind.INDEX:
        return load_alpha_series(symbol=symbol, category="stock", timeframe=timeframe)

    raise ValueError(f"Unsupported market kind: {kind}")
