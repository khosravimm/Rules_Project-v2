#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/build_4h_patterns_kb_v2.py

Use mined 4h direction-sequence patterns (v2) to populate KB patterns.dir_sequence_4h.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml

# Ensure src/ is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.rules_kb.upgrade import upgrade_kb_structure

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build 4h dir-sequence patterns KB (v2).")
    parser.add_argument(
        "--input",
        default="data/btcusdt_4h_patterns_L2_11.parquet",
        help="Input parquet with mined patterns.",
    )
    parser.add_argument("--kb", default="kb/btcusdt_4h_knowledge.yaml", help="KB file to update.")
    parser.add_argument("--min-support", type=int, default=20, help="Minimum support to include.")
    parser.add_argument("--min-accuracy", type=float, default=0.5, help="Minimum accuracy to include.")
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


def normalize_sequence(seq_raw: Any) -> List[str]:
    if hasattr(seq_raw, "tolist"):
        seq_raw = seq_raw.tolist()
    if isinstance(seq_raw, str):
        txt = seq_raw.strip()
        if txt.startswith("[") and txt.endswith("]"):
            txt = txt[1:-1]
        tokens = [t.strip() for t in txt.replace(",", " ").split() if t.strip()]
    elif isinstance(seq_raw, (list, tuple)):
        tokens = [str(t) for t in seq_raw]
    else:
        tokens = []
    out: List[str] = []
    for tok in tokens:
        t = tok.upper()
        if t in {"U", "UP", "+1", "1", "RET_UP"}:
            out.append("UP")
        elif t in {"D", "DOWN", "-1", "RET_DOWN"}:
            out.append("DOWN")
        else:
            out.append("FLAT")
    return out


def strength_bucket(acc: float, lift: float, support: int) -> str:
    if support >= 200 and acc >= 0.65 and lift >= 0.10:
        return "very_strong"
    if support >= 120 and acc >= 0.60 and lift >= 0.07:
        return "strong"
    if support >= 60 and acc >= 0.55 and lift >= 0.04:
        return "medium"
    if acc >= 0.52 and lift >= 0.0:
        return "weak"
    return "very_weak"


def ensure_patterns_container(kb: Dict[str, Any]) -> None:
    kb.setdefault("patterns", {})
    kb["patterns"].setdefault("dir_sequence_4h", {})
    kb["patterns"]["dir_sequence_4h"]["version"] = "v2"


def main() -> None:
    args = parse_args()
    df = read_patterns(Path(args.input))
    kb_path = Path(args.kb)
    kb = read_kb(kb_path)

    ensure_patterns_container(kb)
    now_iso = datetime.utcnow().date().isoformat()

    items: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        support = int(row.get("support") or row.get("sample_count") or 0)
        accuracy = float(row.get("accuracy") or 0.0)
        baseline = float(row.get("baseline_accuracy") or 0.0)
        lift = float(row.get("lift") or (accuracy - baseline))
        if support < args.min_support or accuracy < args.min_accuracy:
            continue

        dirs = normalize_sequence(row.get("sequence"))
        length = int(row.get("length") or len(dirs) or 0)
        favored_class = str(row.get("favored_class", "UP")).upper()
        avg_ret_next = row.get("avg_ret_next")
        try:
            avg_ret_next = float(avg_ret_next) if avg_ret_next is not None else None
        except Exception:
            avg_ret_next = None

        bucket = strength_bucket(accuracy, lift, support)
        item = {
            "id": f"PAT4H_DIR_L{length}_{len(items)+1:03d}_V2",
            "timeframe": "4h",
            "pattern_type": "dir_sequence_forward",
            "source": {
                "dataset": "btcusdt_4h",
                "miner": "mine_4h_dir_sequences_v2",
                "discovered_at": now_iso,
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
                "dir_sequence_4h",
                f"length_{length}",
            ],
        }
        items.append(item)

    kb["patterns"]["dir_sequence_4h"]["items"] = items
    # Upgrade metadata/coverage and bump version (minor)
    master_path = Path("project/MASTER_KNOWLEDGE.yaml")
    master = yaml.safe_load(master_path.read_text(encoding="utf-8")) if master_path.exists() else {}
    kb = upgrade_kb_structure(
        kb,
        master=master,
        reason="add/update 4h dir_sequence patterns v2",
        level="minor",
    )
    write_kb_atomic(kb_path, kb)
    print(f"[OK] Wrote {len(items)} pattern(s) to {kb_path}")


if __name__ == "__main__":
    main()
