from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional, List

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Timeframe and market metadata
# ---------------------------------------------------------------------------

TIMEFRAME_CONFIG: Dict[str, Dict[str, object]] = {
    "4h": {
        "coinex_period": "4hour",
        "binance_interval": "4h",
        "seconds": 4 * 3600,
    },
    "5m": {
        "coinex_period": "5min",
        "binance_interval": "5m",
        "seconds": 5 * 60,
    },
}

MARKET_MAP: Dict[str, Dict[str, str]] = {
    "BTCUSDT_PERP": {
        "coinex_market": "BTCUSDT",
        "binance_symbol": "BTCUSDT",
        "type": "futures",
    },
}

STANDARD_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "dir_raw",
    "log_ret",
    "exchange",
    "timeframe",
]

BINANCE_FAPI_URL = "https://fapi.binance.com/fapi/v1/klines"
COINEX_FUTURES_KLINE_URL = "https://api.coinex.com/v2/futures/kline"


# ---------------------------------------------------------------------------
# Low-level fetchers
# ---------------------------------------------------------------------------

def _fetch_binance_futures_klines(
    symbol: str,
    interval: str,
    limit: int = 1000,
    end_time_ms: Optional[int] = None,
    timeout: int = 15,
) -> pd.DataFrame:
    """
    Fetch a batch of USDT-M futures klines from Binance.
    Response format mirrors the previous BTCUSDT futures loader implementation.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    if end_time_ms is not None:
        params["endTime"] = end_time_ms

    resp = requests.get(BINANCE_FAPI_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    raw = resp.json()

    columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "num_trades",
        "taker_buy_base",
        "taker_buy_quote",
        "ignore",
    ]
    if not raw:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(raw, columns=columns)
    num_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_asset_volume",
        "taker_buy_base",
        "taker_buy_quote",
    ]
    df[num_cols] = df[num_cols].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df.sort_values("open_time").reset_index(drop=True)


def _fetch_binance_futures_klines_paged(
    symbol: str,
    interval: str,
    total_limit: int,
    end_time_ms: Optional[int] = None,
    timeout: int = 15,
    max_per_call: int = 1500,
) -> pd.DataFrame:
    """
    Paged version: will collect up to total_limit candles by stepping endTime backwards.
    """
    if total_limit <= 0:
        return pd.DataFrame(
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "num_trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ]
        )

    remaining = total_limit
    frames: List[pd.DataFrame] = []
    current_end = end_time_ms

    while remaining > 0:
        this_limit = min(max_per_call, remaining)
        df = _fetch_binance_futures_klines(
            symbol=symbol,
            interval=interval,
            limit=this_limit,
            end_time_ms=current_end,
            timeout=timeout,
        )
        if df.empty:
            break

        frames.append(df)
        first_open = df["open_time"].iloc[0]
        current_end = int(first_open.timestamp() * 1000) - 1
        remaining -= len(df)
        if len(df) < this_limit:
            break

    if not frames:
        return pd.DataFrame(
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "num_trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ]
        )

    df_all = pd.concat(frames, ignore_index=True)
    df_all = df_all.sort_values("open_time").reset_index(drop=True)
    if len(df_all) > total_limit:
        df_all = df_all.tail(total_limit).reset_index(drop=True)
    return df_all


def _fetch_coinex_futures_klines(
    market: str,
    period: str,
    limit: int = 1000,
    price_type: str = "latest_price",
    timeout: int = 15,
) -> pd.DataFrame:
    """
    Fetch futures kline data from CoinEx v2 for the given market and period.
    Behavior mirrors the previous BTCUSDT futures loader implementation.
    """
    if limit > 1000:
        limit = 1000

    params = {
        "market": market,
        "period": period,
        "limit": limit,
        "price_type": price_type,
    }

    resp = requests.get(COINEX_FUTURES_KLINE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    raw = resp.json()

    if isinstance(raw, list):
        code = 0
        message = ""
        rows = raw
    elif isinstance(raw, dict):
        code = raw.get("code", 0)
        message = raw.get("message", "")
        if code != 0:
            raise RuntimeError(f"CoinEx API error: code={code}, message={message}")
        data = raw.get("data")
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and "kline" in data:
            rows = data.get("kline", [])
        else:
            raise RuntimeError(f"Unexpected CoinEx data format: type={type(data)}; content={data}")
    else:
        raise RuntimeError(f"Unexpected CoinEx response type: {type(raw)}")

    if not rows:
        raise RuntimeError("CoinEx API returned empty kline data.")

    df = pd.DataFrame(rows)
    expected_cols = {"created_at", "open", "close", "high", "low", "volume", "value"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise RuntimeError(f"CoinEx kline missing columns: {missing}")

    df["open_time"] = pd.to_datetime(df["created_at"], unit="ms", utc=True)
    num_cols = ["open", "high", "low", "close", "volume", "value"]
    df[num_cols] = df[num_cols].astype(float)
    return df.sort_values("open_time").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Standardization helpers
# ---------------------------------------------------------------------------

def _standardize_binance_df(df: pd.DataFrame, timeframe: str, tz: str) -> pd.DataFrame:
    """Convert raw Binance futures kline DataFrame into the standard schema."""
    if df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    out = pd.DataFrame()
    out["open_time"] = df["open_time"].dt.tz_convert(tz)
    out["open"] = df["open"].astype(float)
    out["high"] = df["high"].astype(float)
    out["low"] = df["low"].astype(float)
    out["close"] = df["close"].astype(float)
    out["volume"] = df["volume"].astype(float)
    out["quote_volume"] = df["quote_asset_volume"].astype(float)
    out["dir_raw"] = np.sign(out["close"] - out["open"])
    out["log_ret"] = np.log(out["close"] / out["open"])
    out["exchange"] = "binance"
    out["timeframe"] = timeframe
    return out.sort_values("open_time").reset_index(drop=True)


def _standardize_coinex_df(df: pd.DataFrame, timeframe: str, tz: str) -> pd.DataFrame:
    """Convert raw CoinEx futures kline DataFrame into the standard schema."""
    if df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    out = pd.DataFrame()
    out["open_time"] = df["open_time"].dt.tz_convert(tz)
    out["open"] = df["open"].astype(float)
    out["high"] = df["high"].astype(float)
    out["low"] = df["low"].astype(float)
    out["close"] = df["close"].astype(float)
    out["volume"] = df["volume"].astype(float)
    out["quote_volume"] = df["value"].astype(float)
    out["dir_raw"] = np.sign(out["close"] - out["open"])
    out["log_ret"] = np.log(out["close"] / out["open"])
    out["exchange"] = "coinex"
    out["timeframe"] = timeframe
    return out.sort_values("open_time").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def load_ohlcv(
    market: str,
    timeframe: str,
    n_candles: int,
    primary_exchange: str = "coinex_futures",
    secondary_exchange: Optional[str] = "binance_futures",
    price_type: str = "latest_price",
    end_time: Optional[datetime] = None,
    tz: str = "Asia/Tehran",
    coinex_raw_limit: int = 1000,
    binance_timeout: int = 15,
    coinex_timeout: int = 15,
) -> pd.DataFrame:
    """
    Generic OHLCV loader for futures/spot markets.

    - Fetches candles from the primary exchange (CoinEx by default).
    - Drops the last "not yet closed" candle from the primary exchange.
    - If more history is needed than the primary provides, fetches older candles
      from the secondary exchange (Binance by default).
    - Stitches older secondary candles with newer primary candles, giving priority
      to the primary exchange on overlapping timestamps.
    - Converts timestamps to the requested timezone (default: Asia/Tehran).
    - Returns a standardized OHLCV DataFrame.
    """
    if timeframe not in TIMEFRAME_CONFIG:
        raise ValueError(f"Unsupported timeframe '{timeframe}'. Supported: {list(TIMEFRAME_CONFIG.keys())}")
    if market not in MARKET_MAP:
        raise ValueError(f"Unsupported market '{market}'. Supported: {list(MARKET_MAP.keys())}")
    if n_candles <= 0:
        raise ValueError("n_candles must be positive.")
    if primary_exchange != "coinex_futures":
        raise ValueError("Only primary_exchange='coinex_futures' is supported currently.")
    if secondary_exchange not in {"binance_futures", None}:
        raise ValueError("secondary_exchange must be 'binance_futures' or None.")

    cfg = TIMEFRAME_CONFIG[timeframe]
    market_cfg = MARKET_MAP[market]

    coinex_market = market_cfg["coinex_market"]
    coinex_period = cfg["coinex_period"]
    binance_symbol = market_cfg["binance_symbol"]
    binance_interval = cfg["binance_interval"]

    safe_raw_limit = min(coinex_raw_limit, 1000)
    ce_raw_limit = min(safe_raw_limit, n_candles + 1)

    df_ce_raw = _fetch_coinex_futures_klines(
        market=coinex_market,
        period=coinex_period,
        limit=ce_raw_limit,
        price_type=price_type,
        timeout=coinex_timeout,
    )
    df_ce = _standardize_coinex_df(df_ce_raw, timeframe=timeframe, tz=tz)

    if not df_ce.empty:
        df_ce = df_ce.iloc[:-1].reset_index(drop=True)

    end_ts_local = None
    if end_time is not None:
        end_ts = pd.Timestamp(end_time)
        end_ts_utc = end_ts.tz_localize("UTC") if end_ts.tzinfo is None else end_ts.tz_convert("UTC")
        end_ts_local = end_ts_utc.tz_convert(tz)
        df_ce = df_ce[df_ce["open_time"] <= end_ts_local].reset_index(drop=True)

    ce_closed = df_ce.shape[0]
    if n_candles <= ce_closed:
        return df_ce.tail(n_candles).reset_index(drop=True)

    if secondary_exchange is None:
        raise RuntimeError(
            "Not enough closed candles from primary exchange and secondary_exchange is None; "
            "cannot backfill additional history."
        )

    remaining = n_candles - ce_closed
    if ce_closed > 0:
        earliest_ce_open_local = df_ce["open_time"].min()
        anchor_utc = earliest_ce_open_local.tz_convert("UTC")
    elif end_ts_local is not None:
        anchor_utc = end_ts_local.tz_convert("UTC")
    else:
        raise RuntimeError("No closed candles from CoinEx; cannot determine anchor for secondary fetch.")

    end_time_ms = int(anchor_utc.timestamp() * 1000) - 1

    binance_fetch_target = remaining + 50
    df_bn_raw = _fetch_binance_futures_klines_paged(
        symbol=binance_symbol,
        interval=binance_interval,
        total_limit=binance_fetch_target,
        end_time_ms=end_time_ms,
        timeout=binance_timeout,
    )
    df_bn = _standardize_binance_df(df_bn_raw, timeframe=timeframe, tz=tz)

    df_all = pd.concat([df_bn, df_ce], ignore_index=True)
    df_all = df_all.sort_values("open_time")
    df_all = df_all.drop_duplicates(subset=["open_time"], keep="last")
    if end_ts_local is not None:
        df_all = df_all[df_all["open_time"] <= end_ts_local]
    df_all = df_all.tail(n_candles).reset_index(drop=True)
    return df_all
