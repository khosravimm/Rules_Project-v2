from __future__ import annotations

from typing import Optional, Dict

import pandas as pd

from .schema import _standardize_df


def load_crypto_ohlcv(symbol: str, exchange: str, timeframe: str, limit: Optional[int] = None, since: Optional[str] = None) -> pd.DataFrame:
    """
    Load crypto OHLCV via CCXT.
    - symbol: e.g., 'BTC/USDT'
    - exchange: e.g., 'binance', 'coinex'
    - timeframe: e.g., '5m', '1h', '4h', '1d'
    """
    try:
        import ccxt  # type: ignore
    except ImportError as exc:
        raise ImportError("ccxt is required for load_crypto_ohlcv. Install with `pip install ccxt`.") from exc

    if not hasattr(ccxt, exchange):
        raise ValueError(f"Exchange '{exchange}' not supported by ccxt.")

    ex_class = getattr(ccxt, exchange)
    client = ex_class()
    since_ms = None
    if since:
        since_ms = int(pd.Timestamp(since, tz="UTC").timestamp() * 1000)

    ohlcv = client.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=limit)
    # CCXT returns [timestamp, open, high, low, close, volume]
    df = pd.DataFrame(
        ohlcv,
        columns=["time", "open", "high", "low", "close", "volume"],
    )
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.set_index("time")
    meta: Dict = {"exchange": exchange, "timeframe": timeframe, "symbol": symbol}
    return _standardize_df(df, source=f"ccxt:{exchange}", metadata=meta)
