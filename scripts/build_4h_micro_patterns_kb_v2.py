#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/build_4h_micro_patterns_kb_v2.py

Build KB entries for 4h-from-5m micro-structure patterns (v2).
"""

from __future__ import annotations

import argparse
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml

from src.rules_kb.upgrade import upgrade_kb_structure

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build KB for 4h micro-patterns mined from 5m data (v2).")
    parser.add_argument(
        "--input",
        default="data/btcusdt_4h_micro_patterns.parquet",
        help="Input parquet from mine_4h_from_5m_micro_v2.py",
    )
    parser.add_argument("--kb", default="kb/btcusdt_4h_knowledge.yaml", help="KB YAML to update.")
    parser.add_argument("--min-support", type=int, default=20, help="Minimum support to include.")
    parser.add_argument("--min-accuracy", type=float, default=0.52, help="Minimum accuracy to include.")
    return parser.parse_args()


def read_patterns(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[ERROR] Patterns file not found: {path}")
        raise SystemExit(1)
    return pd.read_parquet(path)


def read_kb(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_kb_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tmp:
        yaml.safe_dump(data, tmp, allow_unicode=True, sort_keys=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def parse_micro_pattern(pattern_str: str) -> Dict[str, List[str]]:
    if not isinstance(pattern_str, str):
        return {}
    out: Dict[str, List[str]] = {}
    for part in pattern_str.split("|"):
        if ":" not in part:
            continue
        feat, seq_txt = part.split(":", 1)
        seq = [s for s in seq_txt.split(",") if s]
        out[feat] = seq
    return out


def strength_bucket(acc: float, lift: float, support: int) -> str:
    if support >= 200 and acc >= 0.64 and lift >= 0.08:
        return "very_strong"
    if support >= 120 and acc >= 0.60 and lift >= 0.05:
        return "strong"
    if support >= 60 and acc >= 0.56:
        return "medium"
    if acc >= 0.52:
        return "weak"
    return "very_weak"


def ensure_patterns_container(kb: Dict[str, Any]) -> None:
    kb.setdefault("patterns", {})
    kb["patterns"].setdefault("intra_4h_from_5m", {})
    kb["patterns"]["intra_4h_from_5m"]["version"] = "v2"


def main() -> None:
    args = parse_args()
    df = read_patterns(Path(args.input))
    kb_path = Path(args.kb)
    kb = read_kb(kb_path)
    ensure_patterns_container(kb)
    now_iso = datetime.utcnow().date().isoformat()

    items: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        support = int(row.get("support") or row.get("sample_count") or 0)
        acc = float(row.get("accuracy") or 0.0)
        baseline = float(row.get("baseline_accuracy") or 0.0)
        lift = float(row.get("lift") or (acc - baseline))
        if support < args.min_support or acc < args.min_accuracy:
            continue
        context_len = int(row.get("context_length") or 0)
        micro_pat = parse_micro_pattern(str(row.get("micro_pattern", "")))
        favored_class = str(row.get("favored_class", "UP")).upper()
        avg_ret_next = row.get("avg_ret_next")
        try:
            avg_ret_next = float(avg_ret_next) if avg_ret_next is not None else None
        except Exception:
            avg_ret_next = None
        bucket = strength_bucket(acc, lift, support)
        items.append(
            {
                "id": f"PAT4H_MICRO_M{context_len}_{len(items)+1:03d}",
                "context": {
                    "length": context_len,
                    "description": f"Last {context_len} 4h bars micro-structure pattern (binned 5m features).",
                },
                "micro_pattern": {
                    "features": micro_pat,
                },
                "target": {
                    "variable": "DIR_4H_NEXT",
                    "favored_class": favored_class,
                },
                "stats": {
                    "support": support,
                    "sample_count": support,
                    "accuracy": acc,
                    "baseline_accuracy": baseline,
                    "lift": lift,
                    "avg_ret_next": avg_ret_next,
                },
                "scoring": {
                    "strength_bucket": bucket,
                    "reliability_comment": "",
                },
                "lifecycle": {
                    "status": "exploratory",
                    "last_evaluated_at": now_iso,
                    "notes": [],
                },
                "tags": [
                    "v2",
                    "intra_4h_from_5m",
                    f"context_length:{context_len}",
                ],
            }
        )

    kb["patterns"]["intra_4h_from_5m"]["items"] = items
    master_path = Path("project/MASTER_KNOWLEDGE.yaml")
    master = yaml.safe_load(master_path.read_text(encoding="utf-8")) if master_path.exists() else {}
    kb = upgrade_kb_structure(
        kb,
        master=master,
        reason="add/update micro 4h_from_5m patterns v2",
        level="minor",
    )
    write_kb_atomic(kb_path, kb)
    print(f"[OK] Wrote {len(items)} micro-pattern(s) to {kb_path}")


if __name__ == "__main__":
    main()
