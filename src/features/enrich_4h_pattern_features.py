from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd


def enrich_btcusdt_4h_pattern_features(
    features_path: str = "data/btcusdt_4h_features.parquet",
    output_path: str | None = None,
) -> None:
    """
    Load the existing BTCUSDT 4h feature dataset and enrich it with
    additional pattern-related columns required by rules_4h_patterns.yaml.

    If output_path is None, overwrite features_path in-place.
    Otherwise, write the enriched DataFrame to output_path.
    """
    df = pd.read_parquet(features_path)
    df = df.sort_values("open_time").reset_index(drop=True)

    required_base: List[str] = ["open_time", "open", "high", "low", "close", "volume"]
    missing = [col for col in required_base if col not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required base columns: {missing}")

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    open_ = df["open"].astype(float)
    close = df["close"].astype(float)

    full_range = high - low
    body = close - open_
    upper_wick = high - np.maximum(open_, close)
    lower_wick = np.minimum(open_, close) - low
    eps = 1e-12
    denom = np.where(np.abs(full_range) < eps, np.nan, full_range)

    df["BODY_PCT_LAST"] = body / denom
    df["UPPER_WICK_PCT_LAST"] = upper_wick / denom
    df["LOWER_WICK_PCT_LAST"] = lower_wick / denom

    df["DIR_4H"] = np.sign(body)
    df["RET_4H_LAST"] = np.log(close / open_)
    df["DIR_LABEL_4H"] = np.where(df["DIR_4H"] > 0, "UP", np.where(df["DIR_4H"] < 0, "DOWN", "FLAT"))

    df["BODY_PCT_MEAN_LAST3"] = df["BODY_PCT_LAST"].rolling(window=3, min_periods=3).mean()
    df["RET_SUM_LAST4"] = df["RET_4H_LAST"].rolling(window=4, min_periods=4).sum()
    df["RET_SUM_LAST5"] = df["RET_4H_LAST"].rolling(window=5, min_periods=5).sum()
    df["UPPER_WICK_PCT_MEAN_LAST5"] = df["UPPER_WICK_PCT_LAST"].rolling(window=5, min_periods=5).mean()
    df["LOWER_WICK_PCT_MEAN_LAST5"] = df["LOWER_WICK_PCT_LAST"].rolling(window=5, min_periods=5).mean()
    df["UP_COUNT_LAST5"] = (df["DIR_4H"] > 0).rolling(window=5, min_periods=5).sum()
    df["DOWN_COUNT_LAST5"] = (df["DIR_4H"] < 0).rolling(window=5, min_periods=5).sum()

    vol = df["volume"].astype(float)
    q1 = vol.quantile(1 / 3)
    q2 = vol.quantile(2 / 3)

    def _bucket_last(v: float) -> str:
        if np.isnan(v):
            return "VOL_UNKNOWN"
        if v <= q1:
            return "VOL_LOW"
        if v <= q2:
            return "VOL_MID"
        return "VOL_HIGH"

    df["VOL_BUCKET_4H_LAST"] = vol.apply(_bucket_last)

    vol_map = {"VOL_LOW": 0, "VOL_MID": 1, "VOL_HIGH": 2, "VOL_UNKNOWN": -1}
    inv_vol_map = {v: k for k, v in vol_map.items()}
    vol_ord = df["VOL_BUCKET_4H_LAST"].map(vol_map).fillna(-1)
    vol_ord_roll = vol_ord.rolling(window=5, min_periods=5).max()
    df["VOL_BUCKET_4H_LAST5_MAX"] = vol_ord_roll.map(inv_vol_map)

    s0 = df["DIR_LABEL_4H"]
    s1 = s0.shift(1)
    s2 = s0.shift(2)
    s3 = s0.shift(3)
    s4 = s0.shift(4)

    seq_mask = s0.notna() & s1.notna() & s2.notna() & s3.notna() & s4.notna()
    dir_seq = pd.Series(np.nan, index=df.index, dtype=object)
    dir_seq[seq_mask] = s4[seq_mask] + "," + s3[seq_mask] + "," + s2[seq_mask] + "," + s1[seq_mask] + "," + s0[seq_mask]
    df["DIR_SEQ_4H"] = dir_seq

    up5 = (df["DIR_4H"] > 0).rolling(window=5, min_periods=5).sum()
    down5 = (df["DIR_4H"] < 0).rolling(window=5, min_periods=5).sum()
    df["DIR_SEQ_4H_CONF_SCORE"] = ((up5 - down5).abs() / 5.0)

    new_cols = [
        "BODY_PCT_LAST",
        "UPPER_WICK_PCT_LAST",
        "LOWER_WICK_PCT_LAST",
        "DIR_4H",
        "DIR_LABEL_4H",
        "RET_4H_LAST",
        "BODY_PCT_MEAN_LAST3",
        "RET_SUM_LAST4",
        "RET_SUM_LAST5",
        "UPPER_WICK_PCT_MEAN_LAST5",
        "LOWER_WICK_PCT_MEAN_LAST5",
        "UP_COUNT_LAST5",
        "DOWN_COUNT_LAST5",
        "VOL_BUCKET_4H_LAST",
        "VOL_BUCKET_4H_LAST5_MAX",
        "DIR_SEQ_4H",
        "DIR_SEQ_4H_CONF_SCORE",
    ]
    for col in new_cols:
        if col not in df.columns:
            raise RuntimeError(f"Failed to create expected feature column: {col}")

    save_path = features_path if output_path is None else output_path
    df.to_parquet(save_path, index=False)


if __name__ == "__main__":
    enrich_btcusdt_4h_pattern_features()
