#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/mine_4h_from_5m_micro_v2.py

Discover relations between 5m micro-structure inside past 4h bars and next 4h outcomes.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


FEATURES_TO_BIN = [
    "frac_up_5m",
    "frac_down_5m",
    "max_run_up_5m",
    "max_run_down_5m",
    "num_up_5m",
    "num_down_5m",
    "intra_range_pct",
    "intra_body_bias",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine 4h patterns from 5m micro-structure (v2).")
    parser.add_argument(
        "--intra-4h",
        default="data/btcusdt_4h_intra_5m_features.parquet",
        help="Input parquet with intra 5m features per 4h bar.",
    )
    parser.add_argument("--output-parquet", default="data/btcusdt_4h_micro_patterns.parquet", help="Output parquet path.")
    parser.add_argument("--output-json", default="data/btcusdt_4h_micro_patterns.json", help="Output JSON path.")
    parser.add_argument("--past-bars", type=int, default=2, help="Minimum context length.")
    parser.add_argument("--max-past-bars", type=int, default=11, help="Maximum context length.")
    parser.add_argument("--min-support", type=int, default=20, help="Minimum support to keep.")
    parser.add_argument("--min-accuracy", type=float, default=0.52, help="Minimum accuracy.")
    parser.add_argument("--min-lift", type=float, default=0.0, help="Minimum lift over baseline.")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging.")
    return parser.parse_args()


def canon_dir(x: Any) -> str:
    v = str(x).upper()
    if v in {"1", "+1", "UP", "RET_UP"} or x == 1:
        return "UP"
    if v in {"-1", "-1.0", "DOWN", "RET_DOWN"} or x == -1:
        return "DOWN"
    return "FLAT"


def bin_feature(series: pd.Series, bins: int = 3) -> pd.Series:
    valid = series.replace([np.inf, -np.inf], np.nan)
    try:
        cats = pd.qcut(valid, q=bins, labels=[f"q{i+1}" for i in range(bins)], duplicates="drop")
    except Exception:
        cats = pd.cut(valid, bins=bins, labels=[f"b{i+1}" for i in range(bins)])
    return cats.astype(str).fillna("nan")


def build_binned_df(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for feat in FEATURES_TO_BIN:
        if feat not in df.columns:
            continue
        out[f"{feat}_bin"] = bin_feature(df[feat])
    return out


def mine_patterns(
    dirs: List[str],
    returns: List[float],
    bins_df: pd.DataFrame,
    min_len: int,
    max_len: int,
    min_support: int,
    min_accuracy: float,
    min_lift: float,
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    patterns: List[Dict[str, Any]] = []
    n = len(dirs)
    feature_cols = list(bins_df.columns)
    for L in range(min_len, max_len + 1):
        if n <= L:
            continue
        baseline_counts: Dict[str, int] = defaultdict(int)
        for t in dirs[L:]:
            baseline_counts[t] += 1
        baseline_total = len(dirs[L:])
        seq_stats: Dict[str, Dict[str, Any]] = {}
        for idx in range(L, n):
            target = dirs[idx]
            key_parts = []
            for feat in feature_cols:
                ctx_vals = bins_df.iloc[idx - L : idx][feat].tolist()
                key_parts.append(f"{feat}:{','.join(ctx_vals)}")
            pattern_key = "|".join(key_parts)
            ret_val = returns[idx] if idx < len(returns) else None
            info = seq_stats.setdefault(pattern_key, {"count": 0, "targets": defaultdict(int), "rets": []})
            info["count"] += 1
            info["targets"][target] += 1
            if ret_val is not None and not pd.isna(ret_val):
                info["rets"].append(float(ret_val))
        if verbose:
            print(f"[INFO] Context {L}: {len(seq_stats)} unique micro-patterns")
        for pat_key, info in seq_stats.items():
            support = info["count"]
            favored_class = max(info["targets"].items(), key=lambda kv: kv[1])[0]
            acc = info["targets"][favored_class] / support
            baseline_acc = (baseline_counts.get(favored_class, 0) / baseline_total) if baseline_total > 0 else 0.0
            lift = acc - baseline_acc
            avg_ret_next = float(np.mean(info["rets"])) if info["rets"] else None
            if support < min_support or acc < min_accuracy or lift < min_lift:
                continue
            patterns.append(
                {
                    "context_length": L,
                    "micro_pattern": pat_key,
                    "sample_count": support,
                    "support": support,
                    "favored_class": favored_class,
                    "accuracy": acc,
                    "baseline_accuracy": baseline_acc,
                    "lift": lift,
                    "avg_ret_next": avg_ret_next,
                }
            )
        if verbose:
            kept = sum(1 for p in patterns if p["context_length"] == L)
            print(f"[INFO] Context {L}: kept {kept} pattern(s)")
    return patterns


def main() -> None:
    args = parse_args()
    intra_path = Path(args.intra_4h)
    if not intra_path.exists():
        print(f"[ERROR] Intra features file not found: {intra_path}")
        raise SystemExit(1)
    df = pd.read_parquet(intra_path)
    if "timestamp_4h" in df.columns:
        df = df.sort_values("timestamp_4h")
    for cand in ["DIR_4H", "dir_4h", "dir4h"]:
        if cand in df.columns:
            dir_series = df[cand].apply(canon_dir)
            break
    else:
        if not {"open", "close"}.issubset(df.columns):
            print("[ERROR] Cannot derive DIR_4H; missing open/close.")
            raise SystemExit(1)
        dir_series = (df["close"] - df["open"]).apply(lambda x: canon_dir(np.sign(x)))

    ret_series = df["close"].pct_change() if "close" in df.columns else pd.Series([np.nan] * len(df))

    bins_df = build_binned_df(df)
    patterns = mine_patterns(
        dir_series.tolist(),
        ret_series.tolist(),
        bins_df,
        min_len=args.past_bars,
        max_len=args.max_past_bars,
        min_support=args.min_support,
        min_accuracy=args.min_accuracy,
        min_lift=args.min_lift,
        verbose=args.verbose,
    )

    out_df = pd.DataFrame(patterns)
    out_parquet = Path(args.output_parquet)
    out_json = Path(args.output_json)
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_parquet, index=False)
    out_json.write_text(json.dumps(patterns, indent=2), encoding="utf-8")
    print(f"[OK] Mined {len(patterns)} micro-pattern(s) to {out_parquet}")
    print(f"[OK] JSON dump saved to {out_json}")


if __name__ == "__main__":
    main()
