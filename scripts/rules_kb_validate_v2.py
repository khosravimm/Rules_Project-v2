#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/rules_kb_validate_v2.py

Validate 4h/5m KB files for the v2 mining schema.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import yaml

ALLOWED_STRENGTH = {"very_strong", "strong", "medium", "weak", "very_weak"}
ALLOWED_STATUS = {"exploratory", "candidate", "active", "deprecated", "rejected"}


@dataclass
class Issue:
    level: str
    location: str
    message: str


@dataclass
class Result:
    ok: bool = True
    errors: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)

    def add_error(self, loc: str, msg: str) -> None:
        self.ok = False
        self.errors.append(Issue("ERROR", loc, msg))

    def add_warning(self, loc: str, msg: str) -> None:
        self.warnings.append(Issue("WARNING", loc, msg))


def is_iso_date(s: Any) -> bool:
    if not isinstance(s, str) or not s.strip():
        return False
    try:
        date.fromisoformat(s.split("T")[0])
        return True
    except Exception:
        return False


def expect_mapping(val: Any) -> bool:
    return isinstance(val, dict)


def expect_list(val: Any) -> bool:
    return isinstance(val, list)


def expect_str(val: Any) -> bool:
    return isinstance(val, str) and len(val.strip()) > 0


# ------------------------- Validation helpers ------------------------------ #
def validate_meta(kb: Dict[str, Any], res: Result, loc: str) -> None:
    meta = kb.get("meta")
    if not expect_mapping(meta):
        res.add_error(loc, "meta missing or not a mapping")
        return
    for key in ["symbol", "timeframe_core", "version"]:
        if not expect_str(meta.get(key, "")):
            res.add_error(f"{loc}.meta.{key}", f"{key} missing/empty")
    for key in ["created_at", "updated_at"]:
        if not is_iso_date(meta.get(key)):
            res.add_warning(f"{loc}.meta.{key}", f"{key} not a valid ISO date: {meta.get(key)!r}")


def validate_4h_patterns(kb: Dict[str, Any], res: Result, strict: bool) -> None:
    pat_root = kb.get("patterns", {})
    dir_seq = pat_root.get("dir_sequence_4h", {})
    if not expect_mapping(dir_seq):
        res.add_error("patterns.dir_sequence_4h", "missing or not a mapping")
        return
    items = dir_seq.get("items", [])
    if not expect_list(items):
        res.add_error("patterns.dir_sequence_4h.items", "items must be a list")
        return
    for idx, item in enumerate(items):
        ploc = f"patterns.dir_sequence_4h.items[{idx}]"
        if not expect_mapping(item):
            res.add_error(ploc, "item not a mapping")
            continue
        rid = item.get("id", "")
        if not expect_str(rid) or not rid.startswith("PAT4H_DIR_"):
            res.add_error(f"{ploc}.id", f"invalid id: {rid!r}")
        seq = item.get("sequence", {}) or {}
        dirs = seq.get("dirs")
        length = seq.get("length")
        if not expect_list(dirs) or len(dirs) < 2:
            res.add_error(f"{ploc}.sequence.dirs", "dirs must be list len>=2")
        if not isinstance(length, int):
            res.add_error(f"{ploc}.sequence.length", "length must be int")
        target = item.get("target", {}) or {}
        if not expect_str(target.get("variable")):
            res.add_error(f"{ploc}.target.variable", "variable missing/empty")
        if not expect_str(target.get("favored_class")):
            res.add_error(f"{ploc}.target.favored_class", "favored_class missing/empty")
        stats = item.get("stats", {}) or {}
        support = stats.get("support")
        accuracy = stats.get("accuracy")
        baseline = stats.get("baseline_accuracy")
        lift = stats.get("lift")
        if not isinstance(support, int) or support < 0:
            res.add_error(f"{ploc}.stats.support", "support must be int >=0")
        if not isinstance(accuracy, (int, float)) or not (0 <= accuracy <= 1):
            res.add_error(f"{ploc}.stats.accuracy", "accuracy must be in [0,1]")
        if not isinstance(baseline, (int, float)) or not (0 <= baseline <= 1):
            res.add_error(f"{ploc}.stats.baseline_accuracy", "baseline_accuracy must be in [0,1]")
        if not isinstance(lift, (int, float)):
            res.add_error(f"{ploc}.stats.lift", "lift must be numeric")
        scoring = item.get("scoring", {}) or {}
        bucket = scoring.get("strength_bucket")
        if bucket not in ALLOWED_STRENGTH:
            res.add_error(f"{ploc}.scoring.strength_bucket", f"invalid strength_bucket: {bucket}")
        lifecycle = item.get("lifecycle", {}) or {}
        status = lifecycle.get("status")
        if status not in ALLOWED_STATUS:
            res.add_error(f"{ploc}.lifecycle.status", f"invalid status: {status}")
        if strict and isinstance(accuracy, (int, float)) and isinstance(baseline, (int, float)):
            if accuracy < baseline:
                res.add_warning(f"{ploc}.stats.accuracy", "accuracy below baseline")


def validate_micro_patterns(kb: Dict[str, Any], res: Result, strict: bool) -> None:
    pat_root = kb.get("patterns", {})
    micro = pat_root.get("intra_4h_from_5m", {})
    if not expect_mapping(micro):
        res.add_error("patterns.intra_4h_from_5m", "missing or not a mapping")
        return
    items = micro.get("items", [])
    if not expect_list(items):
        res.add_error("patterns.intra_4h_from_5m.items", "items must be a list")
        return
    for idx, item in enumerate(items):
        ploc = f"patterns.intra_4h_from_5m.items[{idx}]"
        if not expect_mapping(item):
            res.add_error(ploc, "item not a mapping")
            continue
        rid = item.get("id", "")
        if not expect_str(rid) or not rid.startswith("PAT4H_MICRO_"):
            res.add_error(f"{ploc}.id", f"invalid id: {rid!r}")
        context = item.get("context", {}) or {}
        if not isinstance(context.get("length"), int):
            res.add_error(f"{ploc}.context.length", "context.length must be int")
        target = item.get("target", {}) or {}
        if not expect_str(target.get("variable")):
            res.add_error(f"{ploc}.target.variable", "variable missing/empty")
        if not expect_str(target.get("favored_class")):
            res.add_error(f"{ploc}.target.favored_class", "favored_class missing/empty")
        micro_pat = item.get("micro_pattern", {}) or {}
        feats = micro_pat.get("features")
        if not expect_mapping(feats):
            res.add_error(f"{ploc}.micro_pattern.features", "features must be mapping")
        stats = item.get("stats", {}) or {}
        support = stats.get("support")
        accuracy = stats.get("accuracy")
        baseline = stats.get("baseline_accuracy")
        lift = stats.get("lift")
        if not isinstance(support, int) or support < 0:
            res.add_error(f"{ploc}.stats.support", "support must be int >=0")
        if not isinstance(accuracy, (int, float)) or not (0 <= accuracy <= 1):
            res.add_error(f"{ploc}.stats.accuracy", "accuracy must be in [0,1]")
        if not isinstance(baseline, (int, float)) or not (0 <= baseline <= 1):
            res.add_error(f"{ploc}.stats.baseline_accuracy", "baseline_accuracy must be in [0,1]")
        if not isinstance(lift, (int, float)):
            res.add_error(f"{ploc}.stats.lift", "lift must be numeric")
        scoring = item.get("scoring", {}) or {}
        bucket = scoring.get("strength_bucket")
        if bucket not in ALLOWED_STRENGTH:
            res.add_error(f"{ploc}.scoring.strength_bucket", f"invalid strength_bucket: {bucket}")
        lifecycle = item.get("lifecycle", {}) or {}
        status = lifecycle.get("status")
        if status not in ALLOWED_STATUS:
            res.add_error(f"{ploc}.lifecycle.status", f"invalid status: {status}")
        if strict and isinstance(accuracy, (int, float)) and isinstance(baseline, (int, float)):
            if accuracy < baseline:
                res.add_warning(f"{ploc}.stats.accuracy", "accuracy below baseline")


def validate_5m_patterns(kb: Dict[str, Any], res: Result, strict: bool) -> None:
    pat_root = kb.get("patterns", {})
    dir_seq = pat_root.get("dir_sequence_5m", {})
    if not expect_mapping(dir_seq):
        res.add_error("patterns.dir_sequence_5m", "missing or not a mapping")
        return
    items = dir_seq.get("items", [])
    if not expect_list(items):
        res.add_error("patterns.dir_sequence_5m.items", "items must be a list")
        return
    for idx, item in enumerate(items):
        ploc = f"patterns.dir_sequence_5m.items[{idx}]"
        if not expect_mapping(item):
            res.add_error(ploc, "item not a mapping")
            continue
        rid = item.get("id", "")
        if not expect_str(rid) or not rid.startswith("PAT5M_DIR_"):
            res.add_error(f"{ploc}.id", f"invalid id: {rid!r}")
        seq = item.get("sequence", {}) or {}
        dirs = seq.get("dirs")
        length = seq.get("length")
        if not expect_list(dirs) or len(dirs) < 2:
            res.add_error(f"{ploc}.sequence.dirs", "dirs must be list len>=2")
        if not isinstance(length, int):
            res.add_error(f"{ploc}.sequence.length", "length must be int")
        target = item.get("target", {}) or {}
        if not expect_str(target.get("variable")):
            res.add_error(f"{ploc}.target.variable", "variable missing/empty")
        if not expect_str(target.get("favored_class")):
            res.add_error(f"{ploc}.target.favored_class", "favored_class missing/empty")
        stats = item.get("stats", {}) or {}
        support = stats.get("support")
        accuracy = stats.get("accuracy")
        baseline = stats.get("baseline_accuracy")
        lift = stats.get("lift")
        if not isinstance(support, int) or support < 0:
            res.add_error(f"{ploc}.stats.support", "support must be int >=0")
        if not isinstance(accuracy, (int, float)) or not (0 <= accuracy <= 1):
            res.add_error(f"{ploc}.stats.accuracy", "accuracy must be in [0,1]")
        if not isinstance(baseline, (int, float)) or not (0 <= baseline <= 1):
            res.add_error(f"{ploc}.stats.baseline_accuracy", "baseline_accuracy must be in [0,1]")
        if not isinstance(lift, (int, float)):
            res.add_error(f"{ploc}.stats.lift", "lift must be numeric")
        scoring = item.get("scoring", {}) or {}
        bucket = scoring.get("strength_bucket")
        if bucket not in ALLOWED_STRENGTH:
            res.add_error(f"{ploc}.scoring.strength_bucket", f"invalid strength_bucket: {bucket}")
        lifecycle = item.get("lifecycle", {}) or {}
        status = lifecycle.get("status")
        if status not in ALLOWED_STATUS:
            res.add_error(f"{ploc}.lifecycle.status", f"invalid status: {status}")
        if strict and isinstance(accuracy, (int, float)) and isinstance(baseline, (int, float)):
            if accuracy < baseline:
                res.add_warning(f"{ploc}.stats.accuracy", "accuracy below baseline")


def validate_4h_kb(path: Path, strict: bool) -> Result:
    res = Result()
    kb = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_meta(kb, res, "4h")
    validate_4h_patterns(kb, res, strict)
    validate_micro_patterns(kb, res, strict)
    return res


def validate_5m_kb(path: Path, strict: bool) -> Result:
    res = Result()
    kb = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_meta(kb, res, "5m")
    validate_5m_patterns(kb, res, strict)
    return res


def print_result(result: Result, kb_path: Path) -> None:
    if result.errors or result.warnings:
        print(f"[ERROR] {len(result.errors)} error(s), {len(result.warnings)} warning(s) in {kb_path}")
        for issue in result.errors + result.warnings:
            print(f"  - [{issue.level}] {issue.location}: {issue.message}")
    else:
        print(f"[OK] KB validation passed: {kb_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate v2 KB files (4h + 5m).")
    parser.add_argument("--kb-4h", default="kb/btcusdt_4h_knowledge.yaml", help="Path to 4h KB.")
    parser.add_argument("--kb-5m", default="kb/btcusdt_5m_knowledge.yaml", help="Path to 5m KB.")
    parser.add_argument("--strict", action="store_true", help="Enable strict validation.")
    parser.add_argument("--json", action="store_true", help="Output JSON results.")
    args = parser.parse_args()

    kb4h_path = Path(args.kb_4h)
    kb5m_path = Path(args.kb_5m)
    if not kb4h_path.exists():
        print(f"[ERROR] 4h KB not found: {kb4h_path}")
        raise SystemExit(1)
    if not kb5m_path.exists():
        print(f"[ERROR] 5m KB not found: {kb5m_path}")
        raise SystemExit(1)

    res4h = validate_4h_kb(kb4h_path, args.strict)
    res5m = validate_5m_kb(kb5m_path, args.strict)

    print_result(res4h, kb4h_path)
    print_result(res5m, kb5m_path)

    if args.json:
        output = {
            "kb_4h": {
                "ok": res4h.ok,
                "errors": [issue.__dict__ for issue in res4h.errors],
                "warnings": [issue.__dict__ for issue in res4h.warnings],
            },
            "kb_5m": {
                "ok": res5m.ok,
                "errors": [issue.__dict__ for issue in res5m.errors],
                "warnings": [issue.__dict__ for issue in res5m.warnings],
            },
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

    ok = res4h.ok and res5m.ok
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
