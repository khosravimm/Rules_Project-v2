#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Standard BTCUSDT futures kline loader for CoinEx (primary) and Binance (auxiliary).

PROJECT PRINCIPLE (Mahdi's rule):
    - Primary data source is CoinEx (futures, BTCUSDT).
    - CoinEx API returns at most 1000 candles per request.
    - The latest candle from CoinEx is considered "not closed yet" and MUST be dropped.
      => At most 999 fully-closed candles from CoinEx.
    - When more than available closed CoinEx candles are needed, Binance Futures is used
      to extend the history backward.
    - For overlapping timestamps, CoinEx candles have priority.

EXTRA REQUIREMENTS:
    - All times (open_time) must be shown in local Iran time: Asia/Tehran.
    - The last (currently forming) candle must be excluded from the final data.

Supported timeframes in this loader:
    - "4h"  -> CoinEx period "4hour", Binance interval "4h"
    - "5m"  -> CoinEx period "5min",  Binance interval "5m"

Output schema:
    Columns:
        open_time   : timezone-aware datetime in Asia/Tehran
        open        : float
        high        : float
        low         : float
        close       : float
        volume      : float (base volume)
        quote_volume: float (quote volume; from CoinEx "value" or Binance "quote_asset_volume")
        dir_raw     : float {-1, 0, +1} = sign(close - open)
        log_ret     : float = log(close / open)
        exchange    : "coinex" or "binance"
        timeframe   : string, e.g. "4h" or "5m"

Requirements:
    pip install requests pandas numpy
"""

from __future__ import annotations

import sys
from typing import Dict, Tuple, Optional, List

import numpy as np
import pandas as pd
import requests


# ==========================
#  API ENDPOINTS
# ==========================

BINANCE_FAPI_URL = "https://fapi.binance.com/fapi/v1/klines"          # USDT-M Futures
COINEX_FUTURES_KLINE_URL = "https://api.coinex.com/v2/futures/kline"  # CoinEx API v2

# Iran local timezone name (IANA)
IRAN_TZ = "Asia/Tehran"


# ==========================
#  LOW-LEVEL FETCHERS
# ==========================

def fetch_binance_futures_klines(
    symbol: str,
    interval: str,
    limit: int = 1000,
    end_time_ms: Optional[int] = None,
    timeout: int = 15,
) -> pd.DataFrame:
    """
    Fetch a batch of futures klines from Binance (USDT-M Futures)
    for a given symbol & interval.

    IMPORTANT:
        - This function DOES NOT drop the last candle.
          We only use Binance here for *historical* candles (older than CoinEx range),
          so all of them are assumed to be closed.

    Endpoint:
        GET /fapi/v1/klines

    Request params:
        symbol   : e.g. "BTCUSDT"
        interval : e.g. "4h", "5m"
        limit    : max number of klines (Binance allows up to 1500)
        endTime  : (optional) end time in ms; when provided, the klines
                   returned will be up to (and including) that endTime,
                   going backward in history.

    Response (each kline):
        [
          0  open time (ms),
          1  open,
          2  high,
          3  low,
          4  close,
          5  volume,
          6  close time (ms),
          7  quote asset volume,
          8  number of trades,
          9  taker buy base asset volume,
          10 taker buy quote asset volume,
          11 ignore
        ]
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    if end_time_ms is not None:
        params["endTime"] = end_time_ms

    print(
        f"[Binance] Requesting {limit} {interval} klines for {symbol}"
        + (f" (endTime={end_time_ms})" if end_time_ms is not None else "")
        + " ..."
    )
    resp = requests.get(BINANCE_FAPI_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    raw = resp.json()

    if not raw:
        print("[Binance] Empty response.")
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
    df = pd.DataFrame(raw, columns=columns)

    # Convert numeric columns
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

    # Convert timestamps to timezone-aware UTC, then we'll convert later
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    # Sort ascending by time (just in case)
    df = df.sort_values("open_time").reset_index(drop=True)

    print(f"[Binance] Retrieved {len(df)} rows.")
    return df


def fetch_binance_futures_klines_paged(
    symbol: str,
    interval: str,
    total_limit: int,
    end_time_ms: Optional[int] = None,
    timeout: int = 15,
    max_per_call: int = 1500,
) -> pd.DataFrame:
    """
    Fetch up to `total_limit` klines from Binance by paging backward using endTime.

    The function goes backward in time, starting from `end_time_ms` (if provided),
    or from the most recent klines (if not provided), until it gathers at most
    `total_limit` bars.

    The result is sorted ascending by open_time.
    """
    remaining = total_limit
    frames: List[pd.DataFrame] = []
    current_end = end_time_ms

    while remaining > 0:
        this_limit = min(max_per_call, remaining)
        df = fetch_binance_futures_klines(
            symbol=symbol,
            interval=interval,
            limit=this_limit,
            end_time_ms=current_end,
            timeout=timeout,
        )
        if df.empty:
            break

        frames.append(df)

        # Prepare next page: go further back
        first_open = df["open_time"].iloc[0]
        current_end = int(first_open.timestamp() * 1000) - 1

        remaining -= len(df)
        if len(df) < this_limit:
            # No more history available
            break

    if not frames:
        return pd.DataFrame(
            columns=["open_time", "open", "high", "low", "close", "volume", "quote_asset_volume"]
        )

    df_all = pd.concat(frames, ignore_index=True)
    df_all = df_all.sort_values("open_time").reset_index(drop=True)

    if len(df_all) > total_limit:
        df_all = df_all.tail(total_limit).reset_index(drop=True)

    print(f"[Binance] Paged total rows: {len(df_all)}")
    return df_all


def fetch_coinex_futures_klines(
    market: str,
    period: str,
    limit: int = 1000,
    price_type: str = "latest_price",
    timeout: int = 15,
) -> pd.DataFrame:
    """
    Fetch futures kline data from CoinEx API v2 for a given market & period.

    PROJECT RULE:
        - CoinEx is our primary source.
        - CoinEx max limit is 1000 candles per request (enforced here).
        - The latest candle from CoinEx is considered "not closed" and will be
          dropped LATER in the loader, not here.

    Endpoint (v2):
        GET /v2/futures/kline

    Typical response:
        {
          "code": 0,
          "data": [
            {
              "market": "BTCUSDT",
              "created_at": 1701761760000,
              "open": "12345.6",
              "close": "12350.1",
              "high": "12380.0",
              "low": "12300.0",
              "volume": "123.456",
              "value": "123456.789"
            },
            ...
          ],
          "message": "OK"
        }

    For safety, also handles old-style:
        {"code":0,"data":{"kline":[...]}}
    """
    if limit > 1000:
        print(
            f"[CoinEx] Requested limit={limit} > 1000. "
            f"Clamping to CoinEx max 1000."
        )
        limit = 1000

    params = {
        "market": market,
        "period": period,
        "limit": limit,
        "price_type": price_type,
    }

    print(
        f"[CoinEx] Requesting {limit} {period} klines for {market} "
        f"(price_type={price_type}) ..."
    )
    resp = requests.get(COINEX_FUTURES_KLINE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    raw = resp.json()

    # Handle different possible shapes
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
            raise RuntimeError(
                f"Unexpected CoinEx data format: type={type(data)}; content={data}"
            )
    else:
        raise RuntimeError(f"Unexpected CoinEx response type: {type(raw)}")

    if not rows:
        raise RuntimeError("CoinEx API returned empty kline data.")

    df = pd.DataFrame(rows)

    # Ensure required columns exist
    expected_cols = {"created_at", "open", "close", "high", "low", "volume", "value"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise RuntimeError(f"CoinEx kline missing columns: {missing}")

    # Convert timestamp to timezone-aware UTC, then we'll convert later
    df["open_time"] = pd.to_datetime(df["created_at"], unit="ms", utc=True)

    # Convert numerics
    num_cols = ["open", "high", "low", "close", "volume", "value"]
    df[num_cols] = df[num_cols].astype(float)

    # Sort by time ascending
    df = df.sort_values("open_time").reset_index(drop=True)

    print(f"[CoinEx] Retrieved {len(df)} rows.")
    return df


# ==========================
#  STANDARDIZATION (to Iran time)
# ==========================

def standardize_binance_df(
    df: pd.DataFrame,
    timeframe: str,
) -> pd.DataFrame:
    """
    Convert raw Binance futures kline DataFrame into the standard schema
    and convert open_time from UTC to Asia/Tehran.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
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
        )

    out = pd.DataFrame()
    # Convert UTC -> Iran local time
    out["open_time"] = df["open_time"].dt.tz_convert(IRAN_TZ)

    out["open"] = df["open"].astype(float)
    out["high"] = df["high"].astype(float)
    out["low"] = df["low"].astype(float)
    out["close"] = df["close"].astype(float)
    out["volume"] = df["volume"].astype(float)
    out["quote_volume"] = df["quote_asset_volume"].astype(float)

    # Direction & log-return
    out["dir_raw"] = np.sign(out["close"] - out["open"])
    out["log_ret"] = np.log(out["close"] / out["open"])

    out["exchange"] = "binance"
    out["timeframe"] = timeframe

    return out.sort_values("open_time").reset_index(drop=True)


def standardize_coinex_df(
    df: pd.DataFrame,
    timeframe: str,
) -> pd.DataFrame:
    """
    Convert raw CoinEx futures kline DataFrame into the standard schema
    and convert open_time from UTC to Asia/Tehran.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
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
        )

    out = pd.DataFrame()
    # Convert UTC -> Iran local time
    out["open_time"] = df["open_time"].dt.tz_convert(IRAN_TZ)

    out["open"] = df["open"].astype(float)
    out["high"] = df["high"].astype(float)
    out["low"] = df["low"].astype(float)
    out["close"] = df["close"].astype(float)
    out["volume"] = df["volume"].astype(float)
    out["quote_volume"] = df["value"].astype(float)

    # Direction & log-return
    out["dir_raw"] = np.sign(out["close"] - out["open"])
    out["log_ret"] = np.log(out["close"] / out["open"])

    out["exchange"] = "coinex"
    out["timeframe"] = timeframe

    return out.sort_values("open_time").reset_index(drop=True)


# ==========================
#  HIGH-LEVEL LOADER
# ==========================

TIMEFRAME_CONFIG: Dict[str, Dict[str, str]] = {
    "4h": {
        "coinex_period": "4hour",
        "binance_interval": "4h",
    },
    "5m": {
        "coinex_period": "5min",
        "binance_interval": "5m",
    },
}


def load_btcusdt_futures_klines(
    timeframe: str,
    n_candles: int,
    price_type: str = "latest_price",
    coinex_raw_limit: int = 1000,
    binance_timeout: int = 15,
    coinex_timeout: int = 15,
) -> pd.DataFrame:
    """
    Load BTCUSDT futures klines according to project rules, with Iran local time
    and without the last (not closed) candle from CoinEx.

    LOGIC:
        - We first fetch from CoinEx (primary source).
          Because the last candle is not closed yet, we:
              * fetch up to (n_candles + 1) raw candles (but <= coinex_raw_limit <= 1000),
              * standardize,
              * then drop the last (most recent) candle,
              * so only fully closed candles remain.
        - Let ce_closed = number of closed CoinEx candles we have after dropping.
        - If n_candles <= ce_closed:
            -> return last n_candles from CoinEx only.
        - If n_candles > ce_closed:
            -> we need (n_candles - ce_closed) older candles from Binance Futures.
            -> we fetch them ending just before the earliest CoinEx candle (in UTC),
               standardize to Iran time, and stitch:
                    Binance older + CoinEx newer
               while giving CoinEx priority on overlapping timestamps.
            -> Then we return the last n_candles from the stitched result.

    Args:
        timeframe        : "4h" or "5m" (as of now).
        n_candles        : total number of CLOSED candles requested (>0).
        price_type       : CoinEx price_type ("latest_price", "index_price", "mark_price").
        coinex_raw_limit : raw maximum candles to fetch from CoinEx (<=1000).
                           Note: because we drop the last candle, max CLOSED candles
                           from CoinEx = coinex_raw_limit - 1.
        binance_timeout  : timeout for Binance API calls.
        coinex_timeout   : timeout for CoinEx API calls.

    Returns:
        DataFrame with the standard schema, with open_time in Asia/Tehran,
        and WITHOUT the last open (not closed) CoinEx candle.
    """
    if timeframe not in TIMEFRAME_CONFIG:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {list(TIMEFRAME_CONFIG.keys())}"
        )
    if n_candles <= 0:
        raise ValueError("n_candles must be positive.")

    cfg = TIMEFRAME_CONFIG[timeframe]
    coinex_period = cfg["coinex_period"]
    binance_interval = cfg["binance_interval"]

    # 1) Fetch from CoinEx (primary, up to coinex_raw_limit <= 1000)
    #    We need *one extra* raw candle because the last one will be dropped.
    safe_raw_limit = min(coinex_raw_limit, 1000)
    # Target raw count: n_candles + 1 if possible, otherwise safe_raw_limit
    ce_raw_limit = min(safe_raw_limit, n_candles + 1)

    print(
        f"[Loader] CoinEx raw fetch limit={ce_raw_limit} "
        f"(coinex_raw_limit={coinex_raw_limit}, n_candles={n_candles})"
    )

    df_ce_raw = fetch_coinex_futures_klines(
        market="BTCUSDT",
        period=coinex_period,
        limit=ce_raw_limit,
        price_type=price_type,
        timeout=coinex_timeout,
    )
    df_ce = standardize_coinex_df(df_ce_raw, timeframe=timeframe)

    # Drop the last (most recent) CoinEx candle = not closed yet
    if not df_ce.empty:
        print("[Loader] Dropping last CoinEx candle (assumed not closed yet).")
        df_ce = df_ce.iloc[:-1].reset_index(drop=True)

    ce_closed = len(df_ce)
    print(f"[Loader] Closed CoinEx candles available: {ce_closed}")

    if n_candles <= ce_closed:
        # Only use CoinEx, and we have enough closed candles
        df_result = df_ce.tail(n_candles).reset_index(drop=True)
        print(
            f"[Loader] Returning {len(df_result)} CLOSED candles from CoinEx only "
            f"(timeframe={timeframe})."
        )
        return df_result

    # 2) Need more candles than closed CoinEx provides -> fetch older from Binance

    remaining = n_candles - ce_closed
    print(
        f"[Loader] Need {n_candles} CLOSED candles, CoinEx provides {ce_closed}. "
        f"Fetching additional {remaining} older CLOSED candles from Binance ..."
    )

    if ce_closed == 0:
        raise RuntimeError(
            "No closed candles from CoinEx. Cannot determine anchor time to fetch Binance."
        )

    # We'll fetch Binance candles ending just before the earliest CoinEx candle.
    # NOTE: df_ce open_time is in Iran time; convert back to UTC timestamp for endTime.
    earliest_ce_open_local = df_ce["open_time"].min()
    earliest_ce_open_utc = earliest_ce_open_local.tz_convert("UTC")
    end_time_ms = int(earliest_ce_open_utc.timestamp() * 1000) - 1

    # Fetch slightly more than remaining (buffer) for safety
    binance_fetch_target = remaining + 50
    df_bn_raw = fetch_binance_futures_klines_paged(
        symbol="BTCUSDT",
        interval=binance_interval,
        total_limit=binance_fetch_target,
        end_time_ms=end_time_ms,
        timeout=binance_timeout,
        max_per_call=1500,
    )
    df_bn = standardize_binance_df(df_bn_raw, timeframe=timeframe)

    # 3) Stitch Binance (older) + CoinEx (newer)
    #    Priority on CoinEx when timestamps overlap.

    df_all = pd.concat([df_bn, df_ce], ignore_index=True)
    df_all = df_all.sort_values("open_time")

    # Drop duplicates by open_time, keeping last (CoinEx overwrites Binance on overlap)
    df_all = df_all.drop_duplicates(subset=["open_time"], keep="last")

    # Now take the most recent n_candles (all are CLOSED at this point)
    df_all = df_all.tail(n_candles).reset_index(drop=True)

    print(
        f"[Loader] Final stitched CLOSED series: {len(df_all)} candles "
        f"(Binance older + CoinEx newer) for timeframe={timeframe}."
    )
    print(
        f"[Loader] Exchange counts: "
        f"CoinEx={ (df_all['exchange'] == 'coinex').sum() }, "
        f"Binance={ (df_all['exchange'] == 'binance').sum() }"
    )

    return df_all


# ==========================
#  DEMO / SELF-TEST
# ==========================

def _demo() -> None:
    """
    Simple demo: load some candles for 4h and 5m and print tail.
    Demonstrates:
        - open_time in Asia/Tehran
        - last (open) CoinEx candle removed
        - stitching with Binance when needed
    """
    try:
        print("\n=== DEMO: 4h, n_candles=1200 ===")
        df_4h = load_btcusdt_futures_klines(timeframe="4h", n_candles=1200)
        print(df_4h.tail(5))

        print("\n=== DEMO: 5m, n_candles=800 ===")
        df_5m = load_btcusdt_futures_klines(timeframe="5m", n_candles=800)
        print(df_5m.tail(5))

    except Exception as e:
        print(f"DEMO ERROR: {e}", file=sys.stderr)


if __name__ == "__main__":
    _demo()
