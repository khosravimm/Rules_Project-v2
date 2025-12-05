#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/reset_btcusdt_kb_for_v2.py

Reset or archive BTCUSDT KBs to prepare for v2 mining pipeline (4h + 5m).
"""

from __future__ import annotations

import argparse
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset/archive BTCUSDT KBs for v2 pipeline.")
    parser.add_argument("--kb-4h", default="kb/btcusdt_4h_knowledge.yaml", help="Path to 4h KB.")
    parser.add_argument("--kb-5m", default="kb/btcusdt_5m_knowledge.yaml", help="Path to 5m KB.")
    parser.add_argument("--archive", action="store_true", help="Archive existing patterns/rules/backtests under archive.v1.")
    return parser.parse_args()


def read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"[ERROR] Failed to read {path}: {exc}")
        raise SystemExit(1)


def write_yaml_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tmp:
        yaml.safe_dump(data, tmp, allow_unicode=True, sort_keys=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def reset_kb_4h(path: Path, archive: bool) -> None:
    kb = read_yaml(path)
    now_iso = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    meta = kb.get("meta") if isinstance(kb.get("meta"), dict) else {}
    meta["timeframe_core"] = "4h"
    meta["version"] = "v2"
    meta["updated_at"] = now_iso
    if "created_at" not in meta:
        meta["created_at"] = now_iso
    kb["meta"] = meta

    # Preserve datasets; ensure 4h/5m entries exist
    datasets = kb.get("datasets") if isinstance(kb.get("datasets"), dict) else {}
    datasets.setdefault(
        "btcusdt_4h",
        {
            "path_raw": "data/btcusdt_4h_raw.parquet",
            "path_features": "data/btcusdt_4h_features.parquet",
            "timeframe": "4h",
        },
    )
    datasets.setdefault(
        "btcusdt_5m",
        {
            "path_raw": "data/btcusdt_5m_raw.parquet",
            "path_features": "data/btcusdt_5m_features.parquet",
            "timeframe": "5m",
        },
    )
    kb["datasets"] = datasets

    # Handle archive or removal
    sections = {k: kb.get(k) for k in ["patterns", "trading_rules", "backtests"]}
    if archive:
        kb.setdefault("archive", {})
        kb["archive"].setdefault("v1", {})
        for name, val in sections.items():
            kb["archive"]["v1"][name] = val
    # Regardless, reset sections to fresh skeleton
    kb["patterns"] = {
        "dir_sequence_4h": {"version": "v2", "items": []},
        "intra_4h_from_5m": {"version": "v2", "items": []},
    }
    kb["trading_rules"] = {}
    kb["backtests"] = {}

    write_yaml_atomic(path, kb)
    print(f"[OK] 4h KB reset at {path}")


def init_kb_5m(path: Path) -> None:
    now_iso = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    kb = read_yaml(path)
    if not kb:
        kb = {}

    meta = kb.get("meta") if isinstance(kb.get("meta"), dict) else {}
    meta.setdefault("symbol", "BTCUSDT")
    meta["timeframe_core"] = "5m"
    meta.setdefault("version", "1.0.0")
    meta.setdefault("created_at", now_iso)
    meta["updated_at"] = now_iso
    kb["meta"] = meta

    datasets = kb.get("datasets") if isinstance(kb.get("datasets"), dict) else {}
    datasets["btcusdt_5m"] = {
        "path_raw": "data/btcusdt_5m_raw.parquet",
        "path_features": "data/btcusdt_5m_features.parquet",
    }
    kb["datasets"] = datasets

    kb["patterns"] = {
        "dir_sequence_5m": {"version": "v1", "items": []},
    }

    write_yaml_atomic(path, kb)
    print(f"[OK] 5m KB initialized at {path}")


def main() -> None:
    args = parse_args()
    reset_kb_4h(Path(args.kb_4h), archive=args.archive)
    init_kb_5m(Path(args.kb_5m))


if __name__ == "__main__":
    main()
