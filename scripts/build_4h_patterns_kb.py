#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/build_4h_patterns_kb.py

Reads auto-discovered 4h directional patterns, filters and classifies them,
and writes/updates kb/btcusdt_4h_knowledge.yaml accordingly.
"""

from __future__ import annotations

import argparse
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
import yaml

# -----------------------------------------------------------------------------
# Constants / Configuration
# -----------------------------------------------------------------------------
REQUIRED_LOGICAL_FIELDS = [
    "col_seq",
    "col_length",
    "col_support",
    "col_accuracy",
    "col_baseline",
]
OPTIONAL_LOGICAL_FIELDS = ["col_ret_next_mean"]

STRENGTH_BUCKETS = [
    ("very_strong", 0.80, 1.00),
    ("strong", 0.60, 0.80),
    ("medium", 0.55, 0.60),
    ("weak", 0.52, 0.55),
    ("very_weak", 0.0, 0.52),
]


class ColumnMapping:
    def __init__(
        self,
        col_seq: str,
        col_length: str,
        col_support: str,
        col_accuracy: str,
        col_baseline: str,
        col_ret_next_mean: Optional[str] = None,
    ) -> None:
        self.col_seq = col_seq
        self.col_length = col_length
        self.col_support = col_support
        self.col_accuracy = col_accuracy
        self.col_baseline = col_baseline
        self.col_ret_next_mean = col_ret_next_mean


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build KB patterns from auto-mined 4h sequences.")
    parser.add_argument(
        "--input",
        default="data/btcusdt_4h_patterns_auto.parquet",
        help="Path to auto patterns parquet file.",
    )
    parser.add_argument(
        "--kb",
        default="kb/btcusdt_4h_knowledge.yaml",
        help="Path to KB YAML file to update.",
    )
    parser.add_argument("--min-support", type=int, default=30, help="Minimum support to keep a pattern.")
    parser.add_argument("--min-acc", type=float, default=0.55, help="Minimum accuracy to keep a pattern.")
    return parser.parse_args()


def detect_columns(df: pd.DataFrame) -> ColumnMapping:
    """Map dataframe columns to required logical fields, or raise if missing."""
    cols = set(df.columns)

    def find(prefixes: Sequence[str]) -> Optional[str]:
        for c in cols:
            for p in prefixes:
                if c.lower() == p.lower():
                    return c
        for c in cols:
            for p in prefixes:
                if p.lower() in c.lower():
                    return c
        return None

    col_seq = find(["sequence", "seq"])
    col_length = find(["window_length", "length", "len"])
    col_support = find(["support", "count", "sample_count", "samples"])
    col_accuracy = find(["accuracy", "dominant_conf", "acc", "p_max"])
    col_baseline = find(["baseline", "p_down", "p_up", "baseline_accuracy"])
    col_ret_next_mean = find(["ret_next_mean", "avg_r", "avg_ret"])

    mapping = ColumnMapping(
        col_seq=col_seq or "",
        col_length=col_length or "",
        col_support=col_support or "",
        col_accuracy=col_accuracy or "",
        col_baseline=col_baseline or "",
        col_ret_next_mean=col_ret_next_mean,
    )

    missing = [k for k in REQUIRED_LOGICAL_FIELDS if not getattr(mapping, k)]
    if missing:
        raise ValueError(f"Missing required logical columns: {missing} in available columns {df.columns.tolist()}")
    return mapping


def classify_strength(acc: float, n: int) -> str:
    """Classify accuracy into strength buckets with sample-size adjustment."""
    bucket = "very_weak"
    for name, lo, hi in STRENGTH_BUCKETS:
        if lo <= acc < hi or (name == "very_strong" and acc >= hi):
            bucket = name
            break

    # Downgrade for small samples
    if n < 40 and bucket in {"very_strong", "strong"}:
        bucket = {"very_strong": "strong", "strong": "medium"}.get(bucket, bucket)

    # Upgrade for large samples near upper bound (weak/medium only)
    if n >= 100 and bucket in {"weak", "medium"}:
        if bucket == "weak" and acc >= 0.545:
            bucket = "medium"
        elif bucket == "medium" and acc >= 0.595:
            bucket = "strong"

    return bucket


def parse_sequence(seq_raw: Any) -> List[str]:
    """Parse a sequence representation into list of ['UP', 'DOWN', ...]."""
    if hasattr(seq_raw, "tolist"):
        seq_raw = seq_raw.tolist()
    if isinstance(seq_raw, (list, tuple)):
        seq_list = list(seq_raw)
    elif isinstance(seq_raw, str):
        s = seq_raw.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        if "," in s:
            seq_list = [x.strip() for x in s.split(",") if x.strip()]
        else:
            seq_list = [x.strip() for x in s.split() if x.strip()]
    else:
        raise ValueError(f"Unknown sequence format: {seq_raw}")

    dirs: List[str] = []
    for token in seq_list:
        t = token.upper()
        if t in {"U", "UP", "+1", "1", "RET_UP"}:
            dirs.append("UP")
        elif t in {"D", "DOWN", "-1", "RET_DOWN"}:
            dirs.append("DOWN")
        elif t in {"0", "FLAT"}:
            dirs.append("FLAT")
        else:
            raise ValueError(f"Unknown direction token: {token}")
    return dirs


def load_patterns(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    print(f"[INFO] Loaded patterns from {path}, columns: {df.columns.tolist()}")
    return df


def read_kb(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_kb_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", delete=False, encoding="utf-8", dir=str(path.parent)
    ) as tmp:
        yaml.safe_dump(data, tmp, allow_unicode=True, sort_keys=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def ensure_skeleton(existing: Dict[str, Any]) -> Dict[str, Any]:
    if existing:
        existing.setdefault("patterns", {})
        existing["patterns"].setdefault("dir_sequence_4h", {"description": "", "miner": "", "items": []})
        existing["patterns"]["dir_sequence_4h"].setdefault("items", [])
        return existing
    return {
        "meta": {},
        "datasets": [],
        "features": [],
        "patterns": {
            "dir_sequence_4h": {
                "description": "",
                "miner": "",
                "items": [],
            }
        },
        "trading_rules": [],
        "backtests": [],
        "performance_over_time": [],
        "status_history": [],
        "market_relations": [],
        "cross_market_patterns": [],
    }


# -----------------------------------------------------------------------------
# Main processing
# -----------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    kb_path = Path(args.kb)

    df = load_patterns(input_path)
    mapping = detect_columns(df)

    today_iso = date.today().isoformat()

    records = []
    for _, row in df.iterrows():
        try:
            dirs = parse_sequence(row[mapping.col_seq])
        except Exception as exc:
            print(f"[WARN] Skipping row due to sequence parse error: {exc}")
            continue

        length = int(row[mapping.col_length])
        support = int(row[mapping.col_support])
        accuracy = float(row[mapping.col_accuracy])
        baseline = float(row[mapping.col_baseline])
        avg_ret = None
        if mapping.col_ret_next_mean and mapping.col_ret_next_mean in row:
            try:
                avg_ret = float(row[mapping.col_ret_next_mean])
            except Exception:
                avg_ret = None

        if support < args.min_support or accuracy < args.min_acc:
            continue

        favored_class = "RET_UP" if accuracy >= (1 - accuracy) else "RET_DOWN"
        strength = classify_strength(accuracy, support)

        record = {
            "id": f"PAT4H_DIR_L{length}_{len(records)+1:03d}",
            "name": f"{length}-step direction sequence → {favored_class}",
            "timeframe": "4h",
            "pattern_type": "dir_sequence_forward",
            "source": {
                "dataset": "btcusdt_4h",
                "miner": "auto_dir_sequence_miner_v1",
                "discovered_at": today_iso,
                "discovered_from": "4h_only",
            },
            "sequence": {
                "dirs": dirs,
                "length": length,
            },
            "target": {
                "variable": "DIR_4H_NEXT",
                "favored_class": favored_class,
            },
            "stats": {
                "support": support,
                "sample_count": support,
                "accuracy": accuracy,
                "baseline_accuracy": baseline,
                "lift": accuracy - baseline,
                "avg_ret_next": avg_ret,
            },
            "scoring": {
                "strength_bucket": strength,
                "reliability_comment": "",
            },
            "lifecycle": {
                "status": "exploratory",
                "last_evaluated_at": today_iso,
                "notes": [],
            },
            "tags": [
                "auto",
                "forward",
                "dir_sequence",
                f"length_{length}",
            ],
        }
        records.append(record)

    kb = ensure_skeleton(read_kb(kb_path))
    kb["patterns"]["dir_sequence_4h"]["items"] = records

    write_kb_atomic(kb_path, kb)
    print(f"total patterns read: {len(df)}")
    print(f"patterns passing filters: {len(records)}")
    print(f"patterns written to KB: {len(records)}")


if __name__ == "__main__":
    main()
