"""End-to-end pipeline helpers for fetching, caching, and mining basic patterns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Literal, Sequence

import numpy as np
import pandas as pd

from data.ohlcv_loader import load_ohlcv  # type: ignore

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


# -----------------------------------------------------------------------------
# Fetch & cache
# -----------------------------------------------------------------------------


def fetch_and_cache(
    timeframe: Literal["4h", "5m"],
    n_candles: int,
    out_path: Path,
    *,
    symbol: str = "BTCUSDT",
    price_type: str = "latest_price",
    force: bool = False,
) -> Path:
    """Fetch candles via the canonical OHLCV loader and persist as Parquet."""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        return out_path

    df = load_ohlcv(
        market="BTCUSDT_PERP",
        timeframe=timeframe,
        n_candles=n_candles,
        price_type=price_type,
        primary_exchange="coinex_futures",
        secondary_exchange="binance_futures",
        tz="Asia/Tehran",
    )
    df = df.sort_values("open_time").reset_index(drop=True)
    df.to_parquet(out_path, index=False)
    return out_path


# -----------------------------------------------------------------------------
# Feature engineering
# -----------------------------------------------------------------------------


def _body_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute common candle shape features."""

    eps = 1e-12
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    open_ = df["open"].astype(float)
    close = df["close"].astype(float)

    body_pct = (close - open_).abs() / (high - low + eps)
    upper_wick_pct = (high - np.maximum(open_, close)) / (high - low + eps)
    lower_wick_pct = (np.minimum(open_, close) - low) / (high - low + eps)
    range_pct = (high - low) / (open_ + eps)

    return pd.DataFrame(
        {
            "BODY_PCT": body_pct,
            "UPPER_WICK_PCT": upper_wick_pct,
            "LOWER_WICK_PCT": lower_wick_pct,
            "RANGE_PCT": range_pct,
        }
    )


def _dir_and_ret(df: pd.DataFrame, label_prefix: str) -> pd.DataFrame:
    """Compute return and direction labels."""

    open_ = df["open"].astype(float)
    close = df["close"].astype(float)
    ret = close / open_ - 1.0
    direction = np.where(close > open_, "RET_UP", "RET_DOWN")
    return pd.DataFrame({f"RET_{label_prefix}": ret, f"DIR_{label_prefix}": direction})


def _vol_bucket(ret_series: pd.Series, prefix: str) -> pd.Series:
    """Discretize absolute return into three buckets."""

    abs_ret = ret_series.abs()
    q1 = abs_ret.quantile(1 / 3)
    q2 = abs_ret.quantile(2 / 3)

    def bucket(x: float) -> str:
        if x <= q1:
            return "VOL_LOW"
        if x <= q2:
            return "VOL_MID"
        return "VOL_HIGH"

    return abs_ret.apply(bucket).rename(f"VOL_BUCKET_{prefix}")


def compute_features(df: pd.DataFrame, timeframe: Literal["4h", "5m"]) -> pd.DataFrame:
    """Compute basic features defined in KB for the given timeframe."""

    if timeframe not in {"4h", "5m"}:
        raise ValueError("timeframe must be '4h' or '5m'")

    base = df.copy()
    dir_ret = _dir_and_ret(base, label_prefix=timeframe.upper())
    body = _body_features(base)
    vol_bucket = _vol_bucket(dir_ret[f"RET_{timeframe.upper()}"], prefix=timeframe.upper())

    out = pd.concat([base, dir_ret, body, vol_bucket], axis=1)
    return out


# -----------------------------------------------------------------------------
# Simple directional pattern mining
# -----------------------------------------------------------------------------

ACCURACY_BUCKETS = [
    ("very_strong", 0.80, 1.00),
    ("strong", 0.60, 0.80),
    ("medium", 0.55, 0.60),
    ("weak", 0.52, 0.55),
    ("very_weak", 0.0, 0.52),
]


def _bucket_accuracy(acc: float) -> str:
    for name, lo, hi in ACCURACY_BUCKETS:
        if lo <= acc <= hi:
            return name
    return "unclassified"


def mine_directional_patterns(
    df: pd.DataFrame,
    *,
    direction_col: str = "DIR_4H",
    window_lengths: Sequence[int] = tuple(range(2, 6)),
    min_support: int = 20,
) -> pd.DataFrame:
    """Mine simple directional sequences and next-direction probabilities.

    This is a lightweight statistical sweep (not a production miner) to seed pattern ideas.
    """

    if direction_col not in df.columns:
        raise ValueError(f"{direction_col} not in dataframe")
    directions = df[direction_col].astype(str).tolist()
    results = []

    for L in window_lengths:
        for i in range(len(directions) - L):
            seq = tuple(directions[i : i + L])
            next_dir = directions[i + L]
            results.append((L, seq, next_dir))

    if not results:
        return pd.DataFrame()

    res_df = pd.DataFrame(results, columns=["window_length", "sequence", "next_dir"])
    grouped = res_df.groupby(["window_length", "sequence", "next_dir"]).size().unstack(fill_value=0)
    grouped["support"] = grouped.sum(axis=1)
    grouped = grouped[grouped["support"] >= min_support]

    if grouped.empty:
        return pd.DataFrame()

    grouped["p_up"] = grouped.get("RET_UP", 0) / grouped["support"]
    grouped["p_down"] = grouped.get("RET_DOWN", 0) / grouped["support"]
    grouped["dominant_dir"] = np.where(grouped["p_up"] >= grouped["p_down"], "RET_UP", "RET_DOWN")
    grouped["dominant_conf"] = np.where(
        grouped["p_up"] >= grouped["p_down"], grouped["p_up"], grouped["p_down"]
    )
    grouped["accuracy_bucket"] = grouped["dominant_conf"].apply(_bucket_accuracy)

    grouped = grouped.reset_index()
    grouped["pattern_id"] = grouped.apply(
        lambda row: f"AUTO_DIR_{direction_col}_{row['window_length']}_" + "_".join(row["sequence"]), axis=1
    )
    grouped["description"] = grouped.apply(
        lambda row: f"Seq {row['sequence']} => {row['dominant_dir']} (conf={row['dominant_conf']:.2%}, support={int(row['support'])})",
        axis=1,
    )
    return grouped[
        [
            "pattern_id",
            "window_length",
            "sequence",
            "support",
            "dominant_dir",
            "dominant_conf",
            "accuracy_bucket",
            "p_up",
            "p_down",
            "description",
        ]
    ]


def save_pattern_summary(df: pd.DataFrame, out_path: Path) -> Path:
    """Persist mined pattern summary to Parquet and JSON."""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    json_path = out_path.with_suffix(".json")
    json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")
    return out_path


# -----------------------------------------------------------------------------
# Convenience runner
# -----------------------------------------------------------------------------


def run_basic_pipeline(
    *,
    n_candles_4h: int = 1200,
    n_candles_5m: int = 5000,
    force_fetch: bool = False,
) -> None:
    """Fetch, cache, compute features, and mine simple directional patterns."""

    data_4h = fetch_and_cache("4h", n_candles_4h, DATA_DIR / "btcusdt_4h_raw.parquet", force=force_fetch)
    data_5m = fetch_and_cache("5m", n_candles_5m, DATA_DIR / "btcusdt_5m_raw.parquet", force=force_fetch)

    df_4h = pd.read_parquet(data_4h)
    df_5m = pd.read_parquet(data_5m)

    feat_4h = compute_features(df_4h, "4h")
    feat_5m = compute_features(df_5m, "5m")
    feat_4h_path = DATA_DIR / "btcusdt_4h_features.parquet"
    feat_5m_path = DATA_DIR / "btcusdt_5m_features.parquet"
    feat_4h.to_parquet(feat_4h_path, index=False)
    feat_5m.to_parquet(feat_5m_path, index=False)

    patterns_4h = mine_directional_patterns(feat_4h, direction_col="DIR_4H", window_lengths=range(2, 6))
    if not patterns_4h.empty:
        save_pattern_summary(patterns_4h, DATA_DIR / "btcusdt_4h_patterns_auto.parquet")
    else:
        print("[WARN] No patterns found with minimum support.")


if __name__ == "__main__":  # pragma: no cover
    run_basic_pipeline()
