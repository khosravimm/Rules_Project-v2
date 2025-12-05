#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/mine_4h_dir_sequences_v2.py

Discover 4h direction-sequence patterns for BTCUSDT with lengths 2..11 (configurable).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine 4h direction sequences (v2).")
    parser.add_argument("--features", default="data/btcusdt_4h_features.parquet", help="Path to 4h features parquet.")
    parser.add_argument("--output-parquet", default="data/btcusdt_4h_patterns_L2_11.parquet", help="Output parquet path.")
    parser.add_argument("--output-json", default="data/btcusdt_4h_patterns_L2_11.json", help="Output JSON path.")
    parser.add_argument("--min-length", type=int, default=2, help="Minimum sequence length.")
    parser.add_argument("--max-length", type=int, default=11, help="Maximum sequence length.")
    parser.add_argument("--min-support", type=int, default=20, help="Minimum support/sample_count.")
    parser.add_argument("--min-lift", type=float, default=0.0, help="Minimum lift over baseline.")
    parser.add_argument("--min-accuracy", type=float, default=0.5, help="Minimum accuracy.")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging.")
    return parser.parse_args()


def ensure_dir_column(df: pd.DataFrame) -> pd.Series:
    """Return a Series of canonical directions UP/DOWN/FLAT for 4h bars."""
    for cand in ["DIR_4H", "dir_4h", "dir4h"]:
        if cand in df.columns:
            ser = df[cand]
            break
    else:
        if not {"close", "open"}.issubset(set(df.columns)):
            raise KeyError("Could not find DIR_4H and cannot derive (missing close/open).")
        ser = np.sign(df["close"] - df["open"])
    def canon(x: Any) -> str:
        v = str(x).upper()
        if v in {"1", "+1", "UP", "RET_UP"} or x == 1:
            return "UP"
        if v in {"-1", "-1.0", "DOWN", "RET_DOWN"} or x == -1:
            return "DOWN"
        return "FLAT"
    return ser.apply(canon)


def mine_sequences(
    dirs: List[str],
    returns: List[float],
    min_len: int,
    max_len: int,
    min_support: int,
    min_lift: float,
    min_accuracy: float,
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    patterns: List[Dict[str, Any]] = []
    n = len(dirs)
    for L in range(min_len, max_len + 1):
        if n <= L:
            continue
        targets_all = dirs[L:]
        baseline_counts: Dict[str, int] = defaultdict(int)
        for t in targets_all:
            baseline_counts[t] += 1
        baseline_total = len(targets_all)
        seq_stats: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        for idx in range(L, n):
            seq = tuple(dirs[idx - L : idx])
            target = dirs[idx]
            ret_val = returns[idx] if idx < len(returns) else None
            info = seq_stats.setdefault(seq, {"count": 0, "targets": defaultdict(int), "rets": []})
            info["count"] += 1
            info["targets"][target] += 1
            if ret_val is not None and not pd.isna(ret_val):
                info["rets"].append(float(ret_val))
        if verbose:
            print(f"[INFO] Length {L}: collected {len(seq_stats)} unique sequences")
        for seq, info in seq_stats.items():
            support = info["count"]
            targets = info["targets"]
            favored_class = max(targets.items(), key=lambda kv: kv[1])[0]
            acc = targets[favored_class] / support
            baseline_acc = (baseline_counts.get(favored_class, 0) / baseline_total) if baseline_total > 0 else 0.0
            lift = acc - baseline_acc
            avg_ret_next = float(np.mean(info["rets"])) if info["rets"] else None
            if support < min_support or acc < min_accuracy or lift < min_lift:
                continue
            patterns.append(
                {
                    "sequence": list(seq),
                    "length": L,
                    "support": support,
                    "sample_count": support,
                    "favored_class": favored_class,
                    "accuracy": acc,
                    "baseline_accuracy": baseline_acc,
                    "lift": lift,
                    "avg_ret_next": avg_ret_next,
                }
            )
        if verbose:
            kept = sum(1 for p in patterns if p["length"] == L)
            print(f"[INFO] Length {L}: kept {kept} pattern(s) after filtering")
    return patterns


def main() -> None:
    args = parse_args()
    feat_path = Path(args.features)
    if not feat_path.exists():
        print(f"[ERROR] Features file not found: {feat_path}")
        raise SystemExit(1)
    df = pd.read_parquet(feat_path)
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp")
    dirs = ensure_dir_column(df).tolist()
    ret_curr = df["close"].pct_change().tolist() if "close" in df.columns else [np.nan] * len(df)

    patterns = mine_sequences(
        dirs,
        ret_curr,
        min_len=args.min_length,
        max_len=args.max_length,
        min_support=args.min_support,
        min_lift=args.min_lift,
        min_accuracy=args.min_accuracy,
        verbose=args.verbose,
    )

    out_df = pd.DataFrame(patterns)
    out_parquet = Path(args.output_parquet)
    out_json = Path(args.output_json)
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_parquet, index=False)
    out_json.write_text(json.dumps(patterns, indent=2), encoding="utf-8")

    print(f"[OK] Mined {len(patterns)} pattern(s) into {out_parquet}")
    print(f"[OK] JSON dump saved to {out_json}")


if __name__ == "__main__":
    main()
