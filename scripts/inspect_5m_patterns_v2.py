#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/inspect_5m_patterns_v2.py

Inspect 5m direction-sequence patterns from 5m KB.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


STRENGTH_ORDER = {
    "very_strong": 0,
    "strong": 1,
    "medium": 2,
    "weak": 3,
    "very_weak": 4,
}


@dataclass
class Pattern5M:
    id: str
    length: int
    dirs: List[str]
    favored_class: str
    support: int
    sample_count: int
    accuracy: float
    baseline_accuracy: float
    lift: float
    avg_ret_next: Optional[float]
    strength_bucket: str
    status: str
    tags: List[str]


def strength_rank(bucket: str) -> int:
    return STRENGTH_ORDER.get(bucket, 999)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect 5m direction-sequence patterns.")
    parser.add_argument("--kb", "-k", default="kb/btcusdt_5m_knowledge.yaml", help="Path to 5m KB YAML file.")
    parser.add_argument(
        "--bucket",
        choices=["very_strong", "strong", "medium", "weak", "very_weak", "all"],
        default="all",
        help="Filter by strength bucket.",
    )
    parser.add_argument(
        "--status",
        choices=["exploratory", "candidate", "active", "deprecated", "rejected", "all"],
        default="all",
        help="Filter by lifecycle status.",
    )
    parser.add_argument("--length", type=int, default=None, help="Filter by sequence length.")
    parser.add_argument("--min-support", type=int, default=0, help="Minimum support/sample_count.")
    parser.add_argument("--min-acc", type=float, default=0.0, help="Minimum accuracy.")
    parser.add_argument(
        "--sort-by",
        choices=["strength", "accuracy", "support", "lift"],
        default="strength",
        help="Sorting key.",
    )
    parser.add_argument("--desc", action="store_true", help="Sort descending.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of patterns.")
    parser.add_argument("--json", action="store_true", help="Also output JSON.")
    return parser.parse_args()


def load_patterns_from_kb(kb_path: Path) -> List[Pattern5M]:
    if not kb_path.exists():
        print(f"[ERROR] KB not found: {kb_path}")
        raise SystemExit(1)
    kb = yaml.safe_load(kb_path.read_text(encoding="utf-8")) or {}
    items = kb.get("patterns", {}).get("dir_sequence_5m", {}).get("items", [])
    if not isinstance(items, list):
        return []
    patterns: List[Pattern5M] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        seq = item.get("sequence", {}) or {}
        dirs = seq.get("dirs") or []
        if not isinstance(dirs, list):
            dirs = []
        length = seq.get("length") or len(dirs)
        stats = item.get("stats", {}) or {}
        patterns.append(
            Pattern5M(
                id=str(item.get("id", "")),
                length=int(length),
                dirs=[str(d) for d in dirs],
                favored_class=str(item.get("target", {}).get("favored_class", "")),
                support=int(stats.get("support") or 0),
                sample_count=int(stats.get("sample_count") or 0),
                accuracy=float(stats.get("accuracy") or 0.0),
                baseline_accuracy=float(stats.get("baseline_accuracy") or 0.0),
                lift=float(stats.get("lift") or 0.0),
                avg_ret_next=stats.get("avg_ret_next"),
                strength_bucket=str(item.get("scoring", {}).get("strength_bucket", "")),
                status=str(item.get("lifecycle", {}).get("status", "")),
                tags=[str(t) for t in (item.get("tags") or [])],
            )
        )
    return patterns


def filter_patterns(patterns: List[Pattern5M], args: argparse.Namespace) -> List[Pattern5M]:
    out: List[Pattern5M] = []
    for p in patterns:
        if args.bucket != "all" and p.strength_bucket != args.bucket:
            continue
        if args.status != "all" and p.status != args.status:
            continue
        if args.length is not None and p.length != args.length:
            continue
        if p.sample_count < args.min_support:
            continue
        if p.accuracy < args.min_acc:
            continue
        out.append(p)
    return out


def sort_patterns(patterns: List[Pattern5M], key: str, descending: bool) -> List[Pattern5M]:
    if key == "strength":
        return sorted(patterns, key=lambda p: (strength_rank(p.strength_bucket), -p.accuracy, -p.sample_count), reverse=descending)
    if key == "accuracy":
        return sorted(patterns, key=lambda p: p.accuracy, reverse=descending)
    if key == "support":
        return sorted(patterns, key=lambda p: p.sample_count, reverse=descending)
    if key == "lift":
        return sorted(patterns, key=lambda p: p.lift, reverse=descending)
    return patterns


def format_table(patterns: List[Pattern5M]) -> str:
    headers = ["id", "len", "dirs", "fav", "str", "sup", "acc", "base", "lift", "status"]
    rows = []
    for p in patterns:
        rows.append(
            [
                p.id,
                str(p.length),
                ",".join(p.dirs),
                p.favored_class,
                p.strength_bucket,
                str(p.sample_count),
                f"{p.accuracy:.3f}",
                f"{p.baseline_accuracy:.3f}",
                f"{p.lift:.3f}",
                p.status,
            ]
        )
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def fmt_row(row: List[str]) -> str:
        return "  ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))

    lines = [fmt_row(headers), fmt_row(["-" * w for w in col_widths])]
    for row in rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    patterns = load_patterns_from_kb(Path(args.kb))
    total = len(patterns)
    patterns = filter_patterns(patterns, args)
    patterns = sort_patterns(patterns, key=args.sort_by, descending=args.desc)
    if args.limit and args.limit > 0:
        patterns = patterns[: args.limit]
    if not patterns:
        print("[INFO] No patterns matched filters.")
        print(f"[INFO] Selected 0 pattern(s) out of {total}.")
        raise SystemExit(0)
    print(format_table(patterns))
    print(f"[INFO] Selected {len(patterns)} pattern(s) out of {total}.")
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": p.id,
                        "length": p.length,
                        "dirs": p.dirs,
                        "favored_class": p.favored_class,
                        "support": p.support,
                        "sample_count": p.sample_count,
                        "accuracy": p.accuracy,
                        "baseline_accuracy": p.baseline_accuracy,
                        "lift": p.lift,
                        "avg_ret_next": p.avg_ret_next,
                        "strength_bucket": p.strength_bucket,
                        "status": p.status,
                        "tags": p.tags,
                    }
                    for p in patterns
                ],
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
