#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/inspect_4h_patterns.py

Read-only inspection tool for 4h direction-sequence patterns in the KB.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Strength ordering
STRENGTH_ORDER = {
    "very_strong": 0,
    "strong": 1,
    "medium": 2,
    "weak": 3,
    "very_weak": 4,
}


@dataclass
class Pattern4H:
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
    parser = argparse.ArgumentParser(description="Inspect 4h direction-sequence patterns in KB.")
    parser.add_argument("--kb", "-k", default="kb/btcusdt_4h_knowledge.yaml", help="Path to KB YAML file.")
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
    parser.add_argument("--favored", default="all", help="Filter by favored_class (e.g. UP/DOWN/FLAT/all).")
    parser.add_argument("--length", type=int, default=None, help="Filter by sequence length.")
    parser.add_argument("--min-support", type=int, default=0, help="Minimum support/sample_count.")
    parser.add_argument("--min-acc", type=float, default=0.0, help="Minimum accuracy.")
    parser.add_argument(
        "--sort-by",
        choices=["strength", "accuracy", "support", "lift"],
        default="strength",
        help="Sorting key.",
    )
    parser.add_argument("--desc", action="store_true", help="Sort descending (where applicable).")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of patterns shown.")
    parser.add_argument("--json", action="store_true", help="Also print JSON dump of selected patterns.")
    return parser.parse_args()


def load_patterns_from_kb(kb_path: Path) -> List[Pattern4H]:
    if not kb_path.exists():
        print(f"[ERROR] KB file not found: {kb_path}")
        raise SystemExit(1)
    try:
        kb = yaml.safe_load(kb_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"[ERROR] Failed to read KB: {exc}")
        raise SystemExit(1)

    try:
        items = kb.get("patterns", {}).get("dir_sequence_4h", {}).get("items", [])
    except Exception:
        items = []

    if not isinstance(items, list):
        print("[WARNING] No patterns found at patterns.dir_sequence_4h.items")
        return []

    patterns: List[Pattern4H] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        seq = item.get("sequence", {}) or {}
        dirs = seq.get("dirs") if isinstance(seq, dict) else []
        if dirs is None:
            dirs = []
        if not isinstance(dirs, list):
            dirs = []
        dirs = [str(d) for d in dirs]

        length = 0
        if isinstance(seq, dict) and "length" in seq and isinstance(seq.get("length"), int):
            length = seq["length"]
        elif dirs:
            length = len(dirs)

        target = item.get("target", {}) or {}
        favored_class = target.get("favored_class", "UNKNOWN")

        stats = item.get("stats", {}) or {}
        support = int(stats.get("support") or 0)
        sample_count = int(stats.get("sample_count") or 0)
        accuracy = float(stats.get("accuracy") or 0.0)
        baseline_accuracy = float(stats.get("baseline_accuracy") or 0.0)
        lift = float(stats.get("lift") or 0.0)
        avg_ret_next = stats.get("avg_ret_next", None)
        try:
            if avg_ret_next is not None:
                avg_ret_next = float(avg_ret_next)
        except Exception:
            avg_ret_next = None

        scoring = item.get("scoring", {}) or {}
        strength_bucket = scoring.get("strength_bucket", "unknown")

        lifecycle = item.get("lifecycle", {}) or {}
        status = lifecycle.get("status", "unknown")

        tags = item.get("tags") or []
        if not isinstance(tags, list):
            tags = []

        patterns.append(
            Pattern4H(
                id=str(item.get("id", "")),
                length=length,
                dirs=dirs,
                favored_class=str(favored_class),
                support=support,
                sample_count=sample_count,
                accuracy=accuracy,
                baseline_accuracy=baseline_accuracy,
                lift=lift,
                avg_ret_next=avg_ret_next,
                strength_bucket=str(strength_bucket),
                status=str(status),
                tags=[str(t) for t in tags],
            )
        )
    return patterns


def filter_patterns(patterns: List[Pattern4H], args: argparse.Namespace) -> List[Pattern4H]:
    out: List[Pattern4H] = []
    for p in patterns:
        if args.bucket != "all" and p.strength_bucket != args.bucket:
            continue
        if args.status != "all" and p.status != args.status:
            continue
        if args.favored.lower() != "all" and p.favored_class.lower() != args.favored.lower():
            continue
        if args.length is not None and p.length != args.length:
            continue
        if p.sample_count < args.min_support:
            continue
        if p.accuracy < args.min_acc:
            continue
        out.append(p)
    return out


def sort_patterns(patterns: List[Pattern4H], key: str, descending: bool = True) -> List[Pattern4H]:
    if key == "strength":
        return sorted(
            patterns,
            key=lambda p: (
                strength_rank(p.strength_bucket),
                -p.accuracy,
                -p.sample_count,
            ),
            reverse=descending,
        )
    if key == "accuracy":
        return sorted(patterns, key=lambda p: p.accuracy, reverse=descending)
    if key == "support":
        return sorted(patterns, key=lambda p: p.sample_count, reverse=descending)
    if key == "lift":
        return sorted(patterns, key=lambda p: p.lift, reverse=descending)
    return patterns


def format_table(patterns: List[Pattern4H]) -> str:
    headers = [
        "id",
        "len",
        "dirs",
        "fav",
        "str",
        "sup",
        "acc",
        "base",
        "lift",
        "avg_ret_next",
        "status",
    ]
    rows = []
    for p in patterns:
        dirs_txt = ",".join(p.dirs)
        rows.append(
            [
                p.id,
                str(p.length),
                dirs_txt,
                p.favored_class,
                p.strength_bucket,
                str(p.sample_count),
                f"{p.accuracy:.3f}",
                f"{p.baseline_accuracy:.3f}",
                f"{p.lift:.3f}",
                "" if p.avg_ret_next is None else f"{p.avg_ret_next:.4f}",
                p.status,
            ]
        )

    # compute widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def fmt_row(row: List[str]) -> str:
        return "  ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))

    out_lines = [fmt_row(headers)]
    out_lines.append(fmt_row(["-" * w for w in col_widths]))
    for row in rows:
        out_lines.append(fmt_row(row))
    return "\n".join(out_lines)


def main() -> None:
    args = parse_args()
    kb_path = Path(args.kb)

    patterns = load_patterns_from_kb(kb_path)
    total = len(patterns)

    if total == 0:
        print("[WARNING] No patterns found at patterns.dir_sequence_4h.items")
        raise SystemExit(0)

    patterns = filter_patterns(patterns, args)
    patterns = sort_patterns(patterns, key=args.sort_by, descending=args.desc)

    if args.limit and args.limit > 0:
        patterns = patterns[: args.limit]

    if not patterns:
        print("[INFO] No patterns matched the given filters.")
        print(f"[INFO] Selected 0 pattern(s) out of {total} total.")
        raise SystemExit(0)

    print(format_table(patterns))
    print(f"[INFO] Selected {len(patterns)} pattern(s) out of {total} total.")

    if args.json:
        json_data = [
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
        ]
        print(json.dumps(json_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
