#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/build_4h_intra_5m_features.py

Aggregate 5m micro-structure inside each 4h bar and save enriched 4h dataset.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build intra-5m features per 4h bar.")
    parser.add_argument("--raw-4h", default="data/btcusdt_4h_raw.parquet", help="Path to 4h raw parquet.")
    parser.add_argument("--features-4h", default="data/btcusdt_4h_features.parquet", help="Path to 4h features parquet.")
    parser.add_argument("--raw-5m", default="data/btcusdt_5m_raw.parquet", help="Path to 5m raw parquet.")
    parser.add_argument("--features-5m", default="data/btcusdt_5m_features.parquet", help="Path to 5m features parquet.")
    parser.add_argument("--output", default="data/btcusdt_4h_intra_5m_features.parquet", help="Output parquet path.")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging.")
    return parser.parse_args()


def find_ts_column(df: pd.DataFrame) -> str:
    for cand in ["timestamp", "ts", "open_time"]:
        if cand in df.columns:
            return cand
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    raise KeyError("No datetime-like column found.")


def canonical_dir(series: pd.Series) -> pd.Series:
    def canon(x: Any) -> str:
        v = str(x).upper()
        if v in {"1", "+1", "UP", "RET_UP"} or x == 1:
            return "UP"
        if v in {"-1", "-1.0", "DOWN", "RET_DOWN"} or x == -1:
            return "DOWN"
        return "FLAT"
    return series.apply(canon)


def load_merge_4h(raw_path: Path, feat_path: Path) -> pd.DataFrame:
    raw = pd.read_parquet(raw_path)
    feats = pd.read_parquet(feat_path)
    ts_raw = find_ts_column(raw)
    ts_feat = find_ts_column(feats)
    raw[ts_raw] = pd.to_datetime(raw[ts_raw])
    feats[ts_feat] = pd.to_datetime(feats[ts_feat])
    df = pd.merge(raw, feats, left_on=ts_raw, right_on=ts_feat, how="outer", suffixes=("_raw", "_feat"))
    ts_col = "timestamp"
    if ts_col in df.columns:
        pass
    elif f"{ts_raw}_raw" in df.columns:
        df = df.rename(columns={f"{ts_raw}_raw": ts_col})
    elif ts_raw in df.columns:
        df = df.rename(columns={ts_raw: ts_col})
    elif f"{ts_feat}_feat" in df.columns:
        df = df.rename(columns={f"{ts_feat}_feat": ts_col})
    elif ts_feat in df.columns:
        df = df.rename(columns={ts_feat: ts_col})
    if ts_col not in df.columns:
        raise KeyError("Could not standardize timestamp for 4h data.")
    df = df.drop_duplicates(subset=[ts_col]).sort_values(ts_col)
    df = df.set_index(ts_col)
    return df


def load_5m(feat_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(feat_path)
    ts = find_ts_column(df)
    df[ts] = pd.to_datetime(df[ts])
    df = df.set_index(ts).sort_index()
    return df


def longest_run(dirs: List[str], target: str) -> int:
    best = cur = 0
    for d in dirs:
        if d == target:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def build_features_for_bar(
    ts: pd.Timestamp,
    bar_row: pd.Series,
    df5m: pd.DataFrame,
    dir5m: pd.Series,
) -> Dict[str, Any]:
    start = ts
    end = ts + pd.Timedelta(hours=4)
    mask = (df5m.index >= start) & (df5m.index < end)
    slice_df = df5m.loc[mask]
    slice_dirs = dir5m.loc[mask]
    open_4h = float(bar_row.get("open", np.nan))
    close_4h = float(bar_row.get("close", np.nan))

    res: Dict[str, Any] = {}
    res["num_5m"] = int(slice_df.shape[0])
    if slice_df.empty:
        res.update(
            {
                "num_up_5m": 0,
                "num_down_5m": 0,
                "num_flat_5m": 0,
                "frac_up_5m": 0.0,
                "frac_down_5m": 0.0,
                "frac_flat_5m": 0.0,
                "max_run_up_5m": 0,
                "max_run_down_5m": 0,
                "first3_5m_dirs": [],
                "last3_5m_dirs": [],
                "intra_range_pct": None,
                "intra_body_bias": None,
            }
        )
        return res

    dirs_list = slice_dirs.tolist()
    num_up = sum(1 for d in dirs_list if d == "UP")
    num_down = sum(1 for d in dirs_list if d == "DOWN")
    num_flat = sum(1 for d in dirs_list if d == "FLAT")
    res["num_up_5m"] = num_up
    res["num_down_5m"] = num_down
    res["num_flat_5m"] = num_flat
    total = max(len(dirs_list), 1)
    res["frac_up_5m"] = num_up / total
    res["frac_down_5m"] = num_down / total
    res["frac_flat_5m"] = num_flat / total
    res["max_run_up_5m"] = longest_run(dirs_list, "UP")
    res["max_run_down_5m"] = longest_run(dirs_list, "DOWN")
    res["first3_5m_dirs"] = dirs_list[:3]
    res["last3_5m_dirs"] = dirs_list[-3:]

    try:
        hi = float(slice_df["high"].max())
        lo = float(slice_df["low"].min())
        res["intra_range_pct"] = (hi - lo) / open_4h if open_4h not in {0, np.nan} else None
    except Exception:
        res["intra_range_pct"] = None
    try:
        res["intra_body_bias"] = (close_4h - open_4h) / open_4h if open_4h not in {0, np.nan} else None
    except Exception:
        res["intra_body_bias"] = None

    return res


def main() -> None:
    args = parse_args()
    raw4h = Path(args.raw_4h)
    feat4h = Path(args.features_4h)
    raw5m = Path(args.raw_5m)
    feat5m = Path(args.features_5m)
    output = Path(args.output)

    for p in [raw4h, feat4h, raw5m, feat5m]:
        if not p.exists():
            print(f"[ERROR] File not found: {p}")
            raise SystemExit(1)

    df4h = load_merge_4h(raw4h, feat4h)
    df5m = load_5m(feat5m)
    dir5m = None
    for cand in ["DIR_5M", "dir_5m", "dir5m"]:
        if cand in df5m.columns:
            dir5m = canonical_dir(df5m[cand])
            break
    if dir5m is None:
        if not {"open", "close"}.issubset(df5m.columns):
            print("[ERROR] Cannot derive DIR_5M; missing open/close.")
            raise SystemExit(1)
        sign_series = pd.Series(np.sign(df5m["close"] - df5m["open"]), index=df5m.index)
        dir5m = canonical_dir(sign_series)

    rows: List[Dict[str, Any]] = []
    for ts, row in df4h.iterrows():
        base: Dict[str, Any] = row.to_dict()
        base["timestamp_4h"] = ts
        feats = build_features_for_bar(ts, row, df5m, dir5m)
        base.update(feats)
        rows.append(base)

    out_df = pd.DataFrame(rows)
    out_df = out_df.sort_values("timestamp_4h")
    output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(output, index=False)
    if args.verbose:
        print(out_df.head())
    print(f"[OK] Saved intra 5m features to {output}")


if __name__ == "__main__":
    main()
