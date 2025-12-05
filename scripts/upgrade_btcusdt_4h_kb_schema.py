#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Upgrade/normalize the BTCUSDT 4h KB YAML structure to match validator expectations.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


def is_valid_iso_date(s: Any) -> bool:
    if not isinstance(s, str) or not s.strip():
        return False
    try:
        date.fromisoformat(s.strip())
        return True
    except Exception:
        return False


def ensure_top_level(kb: Dict[str, Any], changes: List[str]) -> None:
    required = [
        "meta",
        "datasets",
        "features",
        "patterns",
        "trading_rules",
        "backtests",
        "performance_over_time",
        "status_history",
        "market_relations",
        "cross_market_patterns",
    ]
    for key in required:
        if key not in kb:
            kb[key] = {} if key != "trading_rules" else {}
            changes.append(f"created {key}")
        elif kb[key] is None:
            kb[key] = {} if key != "trading_rules" else {}
            changes.append(f"reset {key} to mapping")


def ensure_meta(kb: Dict[str, Any], changes: List[str]) -> None:
    kb.setdefault("meta", {})
    meta = kb["meta"]
    today = date.today().isoformat()

    defaults = {
        "symbol": "BTCUSDT",
        "market": "BTCUSDT_PERP",
        "timeframe_core": "4h",
        "description": "KB for BTCUSDT 4h with direction sequence patterns",
        "version": "0.2.0",
    }

    for k, v in defaults.items():
        if not meta.get(k):
            meta[k] = v
            changes.append(f"set meta.{k}={v}")

    if not is_valid_iso_date(meta.get("created_at")):
        meta["created_at"] = today
        changes.append(f"set meta.created_at={today}")
    meta["updated_at"] = today
    changes.append(f"set meta.updated_at={today}")


def ensure_datasets_btcusdt_4h(kb: Dict[str, Any], changes: List[str]) -> None:
    kb.setdefault("datasets", {})
    ds = kb["datasets"]
    if not isinstance(ds, dict):
        kb["datasets"] = {}
        ds = kb["datasets"]
        changes.append("reset datasets to mapping")

    default_ds = {
        "path_raw": "data/btcusdt_4h_raw.parquet",
        "path_features": "data/btcusdt_4h_features.parquet",
        "timeframe": "4h",
        "rows_raw": 4380,
        "rows_features": 4380,
        "exchange_primary": "coinex+binance",
        "loader": {
            "module": "Lib.btc_futures_loader",
            "function": "load_btcusdt_futures_klines",
            "params": {
                "timeframe": "4h",
                "n_candles": 4380,
                "price_type": "latest_price",
            },
        },
        "notes": ["Auto-filled or upgraded by upgrade_btcusdt_4h_kb_schema.py"],
    }

    if "btcusdt_4h" not in ds or not isinstance(ds.get("btcusdt_4h"), dict):
        ds["btcusdt_4h"] = {}
        changes.append("created datasets.btcusdt_4h")
    core = ds["btcusdt_4h"]

    for k, v in default_ds.items():
        if k not in core:
            core[k] = v
            changes.append(f"set datasets.btcusdt_4h.{k}")
        elif isinstance(v, dict):
            core.setdefault(k, {})
            for subk, subv in v.items():
                if subk not in core[k]:
                    core[k][subk] = subv
                    changes.append(f"set datasets.btcusdt_4h.{k}.{subk}")
                elif isinstance(subv, dict):
                    core[k].setdefault(subk, {})
                    for subsubk, subsubv in subv.items():
                        if subsubk not in core[k][subk]:
                            core[k][subk][subsubk] = subsubv
                            changes.append(f"set datasets.btcusdt_4h.{k}.{subk}.{subsubk}")


def ensure_patterns_dir_sequence_4h(kb: Dict[str, Any], changes: List[str]) -> None:
    kb.setdefault("patterns", {})
    patterns = kb["patterns"]
    if not isinstance(patterns, dict):
        kb["patterns"] = {}
        patterns = kb["patterns"]
        changes.append("reset patterns to mapping")

    default_pattern_struct = {
        "description": "4h direction sequence patterns discovered automatically.",
        "miner": {
            "name": "auto_dir_sequence_miner_v1",
            "window_lengths": [2, 3, 4, 5],
            "min_support": 20,
            "data_range": {"start": "2024-01-01", "end": "2025-12-01"},
        },
        "items": [],
    }

    if "dir_sequence_4h" not in patterns or not isinstance(patterns.get("dir_sequence_4h"), dict):
        existing_items = []
        if isinstance(patterns.get("dir_sequence_4h"), list):
            existing_items = patterns["dir_sequence_4h"]
        patterns["dir_sequence_4h"] = default_pattern_struct
        patterns["dir_sequence_4h"]["items"] = existing_items
        changes.append("created patterns.dir_sequence_4h with default structure")

    dir_seq = patterns["dir_sequence_4h"]
    if not isinstance(dir_seq, dict):
        patterns["dir_sequence_4h"] = default_pattern_struct
        changes.append("reset patterns.dir_sequence_4h to default mapping")
        dir_seq = patterns["dir_sequence_4h"]

    dir_seq.setdefault("items", [])
    if not isinstance(dir_seq["items"], list):
        dir_seq["items"] = []
        changes.append("reset patterns.dir_sequence_4h.items to list")

    if "description" not in dir_seq or not isinstance(dir_seq.get("description"), str):
        dir_seq["description"] = default_pattern_struct["description"]
        changes.append("set patterns.dir_sequence_4h.description")
    dir_seq.setdefault("miner", {})
    miner = dir_seq["miner"]
    if not isinstance(miner, dict):
        dir_seq["miner"] = default_pattern_struct["miner"]
        changes.append("reset patterns.dir_sequence_4h.miner to default")
        miner = dir_seq["miner"]

    miner_defaults = default_pattern_struct["miner"]
    for k, v in miner_defaults.items():
        if k not in miner:
            miner[k] = v
            changes.append(f"set patterns.dir_sequence_4h.miner.{k}")
        elif isinstance(v, dict):
            miner.setdefault(k, {})
            for subk, subv in v.items():
                if subk not in miner[k]:
                    miner[k][subk] = subv
                    changes.append(f"set patterns.dir_sequence_4h.miner.{k}.{subk}")


def ensure_other_sections(kb: Dict[str, Any], changes: List[str]) -> None:
    defaults: List[Tuple[str, Any]] = [
        ("features", {}),
        ("trading_rules", {}),
        ("backtests", {}),
        ("performance_over_time", {}),
        ("status_history", {}),
        ("market_relations", {}),
        ("cross_market_patterns", {}),
    ]
    for key, default_val in defaults:
        if key not in kb:
            kb[key] = default_val
            changes.append(f"created {key}")
        elif kb[key] is None:
            kb[key] = default_val
            changes.append(f"reset {key} to default")


def upgrade_kb_structure(kb: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    changes: List[str] = []
    ensure_top_level(kb, changes)
    ensure_meta(kb, changes)
    ensure_datasets_btcusdt_4h(kb, changes)
    ensure_patterns_dir_sequence_4h(kb, changes)
    ensure_other_sections(kb, changes)
    return kb, changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Upgrade BTCUSDT 4h KB schema.")
    parser.add_argument(
        "--kb",
        "-k",
        default="kb/btcusdt_4h_knowledge.yaml",
        help="Path to KB YAML file to upgrade.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write changes, just report.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed change log.",
    )
    args = parser.parse_args()

    kb_path = Path(args.kb)
    if not kb_path.exists():
        print(f"[ERROR] KB file not found: {kb_path}")
        raise SystemExit(1)

    try:
        kb_raw = yaml.safe_load(kb_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"[ERROR] Failed to read KB: {exc}")
        raise SystemExit(1)

    if not isinstance(kb_raw, dict):
        print("[ERROR] KB root is not a mapping/dict.")
        raise SystemExit(1)

    kb_upgraded, changes = upgrade_kb_structure(kb_raw)

    if args.dry_run:
        print(f"[DRY-RUN] {len(changes)} change(s) would be applied to {kb_path}:")
        for c in changes:
            print(f" - {c}")
        raise SystemExit(0)

    tmp_path = kb_path.with_suffix(kb_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(kb_upgraded, f, allow_unicode=True, sort_keys=False)
    tmp_path.replace(kb_path)
    print(f"[OK] KB schema upgraded: {kb_path}")
    if args.verbose and changes:
        for c in changes:
            print(f" - {c}")


if __name__ == "__main__":
    main()
