from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from .ohlcv_loader import TIMEFRAME_CONFIG, load_ohlcv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

OUTPUT_MAP: Dict[str, Path] = {
    "4h": DATA_DIR / "btcusdt_4h_raw.parquet",
    "5m": DATA_DIR / "btcusdt_5m_raw.parquet",
}

YEARS_OF_HISTORY = 2
# Extra candles to request beyond the strict 2-year span to tolerate trimming and overlap handling.
BUFFER_BY_TIMEFRAME = {"4h": 24, "5m": 500}

REQUIRED_COLUMNS = ["open_time", "open", "high", "low", "close", "volume"]


def _target_counts(timeframe: str, years: int = YEARS_OF_HISTORY) -> Tuple[int, pd.Timestamp, pd.Timestamp]:
    """Compute how many candles we need for the requested span plus a small buffer."""
    if timeframe not in TIMEFRAME_CONFIG:
        raise ValueError(f"Unsupported timeframe '{timeframe}'.")

    now = pd.Timestamp.now(tz="UTC")
    start = now - pd.DateOffset(years=years)
    seconds = int(TIMEFRAME_CONFIG[timeframe]["seconds"])
    span_seconds = (now - start).total_seconds()
    base = math.ceil(span_seconds / seconds)
    buffered = int(base + BUFFER_BY_TIMEFRAME.get(timeframe, 0))
    return buffered, start, now


def _sanitize(df: pd.DataFrame, timeframe: str, now: pd.Timestamp) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Sort, drop duplicates, and remove not-yet-closed candles."""
    if df.empty:
        raise RuntimeError(f"No data returned for timeframe={timeframe}.")

    df = df.copy()
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df = df.sort_values("open_time").reset_index(drop=True)

    delta = pd.Timedelta(seconds=int(TIMEFRAME_CONFIG[timeframe]["seconds"]))
    dup_mask = df.duplicated(subset=["open_time"])
    dup_count = int(dup_mask.sum())
    if dup_count:
        df = df[~dup_mask].reset_index(drop=True)

    df = df[df["open_time"] + delta <= now].reset_index(drop=True)

    gaps = df["open_time"].diff().dropna()
    gap_mask = gaps > delta
    gap_count = int(gap_mask.sum())

    return df, {"dup_count": dup_count, "gap_count": gap_count}


def _validate_schema(df: pd.DataFrame, timeframe: str) -> None:
    """Ensure required columns exist and have sensible types."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise AssertionError(f"{timeframe}: missing required columns: {missing}")

    if not pd.api.types.is_datetime64_any_dtype(df["open_time"]):
        raise AssertionError(f"{timeframe}: open_time must be datetime64.")


def _validate_coverage(
    df: pd.DataFrame, timeframe: str, target_start: pd.Timestamp, now: pd.Timestamp, gap_info: Dict[str, int]
) -> None:
    """Check 2-year span, duplicates, gaps, and closed bars."""
    delta = pd.Timedelta(seconds=int(TIMEFRAME_CONFIG[timeframe]["seconds"]))
    start = df["open_time"].min()
    end = df["open_time"].max()
    span = end - start

    min_span = pd.Timedelta(days=YEARS_OF_HISTORY * 365 - 1)
    if span < min_span:
        raise AssertionError(f"{timeframe}: coverage span too short ({span}).")

    if start > target_start + delta:
        raise AssertionError(
            f"{timeframe}: earliest candle {start} is later than target start {target_start} (tolerance one step)."
        )

    contiguous_rows = math.floor(span / delta) + 1
    if len(df) + 3 < contiguous_rows:
        raise AssertionError(
            f"{timeframe}: row count {len(df)} suggests large gaps (expected ~{contiguous_rows})."
        )

    if gap_info["dup_count"] > 0:
        print(f"[warn] {timeframe}: dropped {gap_info['dup_count']} duplicate candles.")
    if gap_info["gap_count"] > 0:
        print(f"[warn] {timeframe}: detected {gap_info['gap_count']} gaps in the series.")

    last_close = end + delta
    if last_close > now:
        raise AssertionError(f"{timeframe}: last candle not closed (end={end}, close_ts={last_close}, now={now}).")


def _fetch_timeframe(timeframe: str) -> Tuple[pd.DataFrame, pd.Timestamp]:
    """Fetch a single timeframe using the canonical loader and validate."""
    target_count, target_start, now = _target_counts(timeframe)
    base_expected = math.ceil(
        (now - target_start).total_seconds() / int(TIMEFRAME_CONFIG[timeframe]["seconds"])
    )
    print(
        f"[info] Fetching {timeframe} candles (target {target_count}, expected~{base_expected} for {YEARS_OF_HISTORY} years)."
    )

    df = load_ohlcv(
        market="BTCUSDT_PERP",
        timeframe=timeframe,
        n_candles=target_count,
        primary_exchange="coinex_futures",
        secondary_exchange="binance_futures",
        tz="UTC",
    )

    df, info = _sanitize(df, timeframe=timeframe, now=now)
    _validate_schema(df, timeframe=timeframe)
    _validate_coverage(df, timeframe=timeframe, target_start=target_start, now=now, gap_info=info)

    row_count = len(df)
    start = df["open_time"].min()
    end = df["open_time"].max()
    print(f"[info] {timeframe}: rows={row_count}, start={start}, end={end}, gaps={info['gap_count']}")
    return df, target_start


def fetch_and_save_btcusdt_history_4h5m(force: bool = True) -> Dict[str, Path]:
    """
    Fetch >=2 years of BTCUSDT futures OHLCV for 4h and 5m and write canonical Parquet files.
    Returns a mapping timeframe -> saved path.
    """
    DATA_DIR.mkdir(exist_ok=True)
    saved: Dict[str, Path] = {}

    for tf in ("4h", "5m"):
        out_path = OUTPUT_MAP[tf]
        if out_path.exists() and not force:
            print(f"[info] Skipping fetch for {tf}; file already exists at {out_path}")
            saved[tf] = out_path
            continue

        df, target_start = _fetch_timeframe(tf)
        df.to_parquet(out_path, index=False)
        print(f"[info] {tf}: saved to {out_path}")

        # Reload to ensure persisted data remains valid.
        df_saved = pd.read_parquet(out_path)
        df_saved["open_time"] = pd.to_datetime(df_saved["open_time"], utc=True)
        now_check = pd.Timestamp.now(tz="UTC")
        df_check, info_saved = _sanitize(df_saved, timeframe=tf, now=now_check)
        _validate_schema(df_check, timeframe=tf)
        _validate_coverage(
            df_check, timeframe=tf, target_start=target_start, now=now_check, gap_info=info_saved
        )
        saved[tf] = out_path

    return saved


def main() -> None:
    results = fetch_and_save_btcusdt_history_4h5m(force=True)
    for tf, path in results.items():
        print(f"[done] {tf} -> {path}")


if __name__ == "__main__":
    main()
