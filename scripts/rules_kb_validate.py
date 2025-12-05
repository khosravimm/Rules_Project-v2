#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/rules_kb_validate.py

Validate knowledge-base YAML files for structural consistency and basic sanity
based on project specification (MASTER_KNOWLEDGE.yaml guidelines).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Allowed sets
ALLOWED_STRENGTH = {"very_strong", "strong", "medium", "weak", "very_weak"}
ALLOWED_STATUS = {"exploratory", "candidate", "active", "deprecated", "rejected"}
ALLOWED_TAG_CORE = {"dir_sequence"}
ALLOWED_TAG_STRICT = {"auto", "forward"}


@dataclass
class ValidationIssue:
    level: str  # "ERROR", "WARNING", "INFO"
    location: str
    message: str


@dataclass
class ValidationResult:
    ok: bool = True
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    infos: List[ValidationIssue] = field(default_factory=list)

    def add_error(self, loc: str, msg: str) -> None:
        self.ok = False
        self.errors.append(ValidationIssue("ERROR", loc, msg))

    def add_warning(self, loc: str, msg: str) -> None:
        self.warnings.append(ValidationIssue("WARNING", loc, msg))

    def add_info(self, loc: str, msg: str) -> None:
        self.infos.append(ValidationIssue("INFO", loc, msg))


# --------------------------------------------------------------------------- #
# Utility helpers
# --------------------------------------------------------------------------- #
def is_iso_date(s: Any) -> bool:
    if not isinstance(s, str) or not s.strip():
        return False
    try:
        date.fromisoformat(s.strip())
        return True
    except Exception:
        return False


def expect_mapping(val: Any) -> bool:
    return isinstance(val, dict)


def expect_list(val: Any) -> bool:
    return isinstance(val, list)


def expect_non_empty_string(val: Any) -> bool:
    return isinstance(val, str) and len(val.strip()) > 0


# --------------------------------------------------------------------------- #
# Validation functions
# --------------------------------------------------------------------------- #
def validate_meta(kb: Dict[str, Any], res: ValidationResult, strict: bool) -> None:
    loc = "meta"
    meta = kb.get("meta")
    if not expect_mapping(meta):
        res.add_error(loc, "meta is missing or not a mapping")
        return

    symbol = meta.get("symbol")
    timeframe_core = meta.get("timeframe_core")
    version = meta.get("version")
    created_at = meta.get("created_at")
    updated_at = meta.get("updated_at")

    # symbol and timeframe_core are required
    if not expect_non_empty_string(symbol):
        res.add_error(f"{loc}.symbol", "symbol is missing or empty")
    if not expect_non_empty_string(timeframe_core):
        res.add_error(f"{loc}.timeframe_core", "timeframe_core is missing or empty")

    # version, created_at, updated_at
    if not expect_non_empty_string(version):
        if strict:
            res.add_error(f"{loc}.version", "version is missing or empty")
        else:
            res.add_warning(f"{loc}.version", "version is missing or empty")
    if created_at is None or not is_iso_date(created_at):
        if strict:
            res.add_error(f"{loc}.created_at", f"invalid ISO date: {created_at!r}")
        else:
            res.add_warning(f"{loc}.created_at", f"invalid ISO date: {created_at!r}")
    if updated_at is None or not is_iso_date(updated_at):
        if strict:
            res.add_error(f"{loc}.updated_at", f"invalid ISO date: {updated_at!r}")
        else:
            res.add_warning(f"{loc}.updated_at", f"invalid ISO date: {updated_at!r}")


def validate_datasets(kb: Dict[str, Any], res: ValidationResult) -> None:
    loc = "datasets"
    datasets = kb.get("datasets")
    if not expect_mapping(datasets):
        res.add_error(loc, "datasets is missing or not a mapping")
        return

    core = datasets.get("btcusdt_4h")
    if not expect_mapping(core):
        res.add_error(f"{loc}.btcusdt_4h", "core dataset missing or not a mapping")
        return

    path_raw = core.get("path_raw")
    path_features = core.get("path_features")
    timeframe = core.get("timeframe")
    rows_raw = core.get("rows_raw")
    rows_features = core.get("rows_features")

    if not expect_non_empty_string(path_raw):
        res.add_error(f"{loc}.btcusdt_4h.path_raw", "path_raw missing/empty")
    if not expect_non_empty_string(path_features):
        res.add_error(f"{loc}.btcusdt_4h.path_features", "path_features missing/empty")
    if not expect_non_empty_string(timeframe):
        res.add_error(f"{loc}.btcusdt_4h.timeframe", "timeframe missing/empty")
    if not isinstance(rows_raw, int) or rows_raw <= 0:
        res.add_error(f"{loc}.btcusdt_4h.rows_raw", "rows_raw must be int > 0")
    if not isinstance(rows_features, int) or rows_features <= 0:
        res.add_error(f"{loc}.btcusdt_4h.rows_features", "rows_features must be int > 0")


def validate_miner(miner: Any, res: ValidationResult, loc: str) -> None:
    if not expect_mapping(miner):
        res.add_error(loc, "miner is missing or not a mapping")
        return
    name = miner.get("name")
    wls = miner.get("window_lengths")
    min_support = miner.get("min_support")
    data_range = miner.get("data_range")

    if not expect_non_empty_string(name):
        res.add_error(f"{loc}.name", "name missing/empty")
    if not expect_list(wls) or len(wls) == 0 or not all(isinstance(x, int) for x in wls):
        res.add_error(f"{loc}.window_lengths", "window_lengths must be a non-empty list of ints")
    if not isinstance(min_support, int) or min_support < 1:
        res.add_error(f"{loc}.min_support", "min_support must be int >= 1")
    if not expect_mapping(data_range):
        res.add_error(f"{loc}.data_range", "data_range missing/not a mapping")
    else:
        start = data_range.get("start")
        end = data_range.get("end")
        if not is_iso_date(start):
            res.add_error(f"{loc}.data_range.start", f"invalid ISO date: {start!r}")
        if not is_iso_date(end):
            res.add_error(f"{loc}.data_range.end", f"invalid ISO date: {end!r}")


def validate_patterns_dir_sequence_4h(kb: Dict[str, Any], res: ValidationResult, strict: bool) -> None:
    loc = "patterns.dir_sequence_4h"
    patterns = kb.get("patterns")
    if not expect_mapping(patterns):
        res.add_error("patterns", "patterns missing or not a mapping")
        return

    dir_seq = patterns.get("dir_sequence_4h")
    if not expect_mapping(dir_seq):
        res.add_error(loc, "dir_sequence_4h missing or not a mapping")
        return

    description = dir_seq.get("description")
    miner = dir_seq.get("miner")
    items = dir_seq.get("items")

    if description is None or not isinstance(description, str):
        res.add_error(f"{loc}.description", "description missing or not a string")

    validate_miner(miner, res, f"{loc}.miner")

    if not expect_list(items):
        res.add_error(f"{loc}.items", "items must be a list")
        return

    for idx, p in enumerate(items):
        ploc = f"{loc}.items[{idx}]"
        if not expect_mapping(p):
            res.add_error(ploc, "item is not a mapping")
            continue

        # Required keys
        rid = p.get("id")
        name = p.get("name")
        timeframe = p.get("timeframe")
        ptype = p.get("pattern_type")
        source = p.get("source")
        seq = p.get("sequence")
        target = p.get("target")
        stats = p.get("stats")
        scoring = p.get("scoring")
        lifecycle = p.get("lifecycle")
        tags = p.get("tags")

        # Basic required fields
        if not expect_non_empty_string(rid) or not str(rid).startswith("PAT4H_DIR_"):
            res.add_error(f"{ploc}.id", "id missing/empty or does not start with PAT4H_DIR_")
        if not expect_non_empty_string(name):
            res.add_error(f"{ploc}.name", "name missing/empty")
        if timeframe != "4h":
            res.add_error(f"{ploc}.timeframe", "timeframe must be '4h'")
        if not expect_non_empty_string(ptype):
            res.add_error(f"{ploc}.pattern_type", "pattern_type missing/empty")

        # source
        if not expect_mapping(source):
            res.add_error(f"{ploc}.source", "source missing/not a mapping")
        else:
            dataset = source.get("dataset")
            miner_name = source.get("miner")
            discovered_at = source.get("discovered_at")
            discovered_from = source.get("discovered_from")
            if dataset != "btcusdt_4h":
                res.add_error(f"{ploc}.source.dataset", "dataset must be 'btcusdt_4h'")
            if not expect_non_empty_string(miner_name):
                res.add_error(f"{ploc}.source.miner", "miner missing/empty")
            if not is_iso_date(discovered_at):
                res.add_error(f"{ploc}.source.discovered_at", f"invalid ISO date: {discovered_at!r}")
            if not expect_non_empty_string(discovered_from):
                res.add_error(f"{ploc}.source.discovered_from", "discovered_from missing/empty")

        # sequence
        if not expect_mapping(seq):
            res.add_error(f"{ploc}.sequence", "sequence missing/not a mapping")
        else:
            dirs = seq.get("dirs")
            length = seq.get("length")
            if not expect_list(dirs) or len(dirs) < 2:
                res.add_error(f"{ploc}.sequence.dirs", "dirs must be list with len >= 2")
            elif not all(isinstance(d, (str, int)) for d in dirs):
                res.add_error(f"{ploc}.sequence.dirs", "dirs items must be str or int")
            if not isinstance(length, int):
                res.add_error(f"{ploc}.sequence.length", "length must be int")
            elif isinstance(dirs, list) and isinstance(length, int) and length != len(dirs):
                res.add_warning(f"{ploc}.sequence.length", f"length ({length}) != len(dirs) ({len(dirs)})")

        # target
        if not expect_mapping(target):
            res.add_error(f"{ploc}.target", "target missing/not a mapping")
        else:
            var = target.get("variable")
            favored = target.get("favored_class")
            if not expect_non_empty_string(var):
                res.add_error(f"{ploc}.target.variable", "variable missing/empty")
            elif var != "DIR_4H_NEXT":
                res.add_warning(f"{ploc}.target.variable", f"unexpected variable: {var}")
            if not expect_non_empty_string(favored):
                res.add_error(f"{ploc}.target.favored_class", "favored_class missing/empty")

        # stats
        if not expect_mapping(stats):
            res.add_error(f"{ploc}.stats", "stats missing/not a mapping")
        else:
            support = stats.get("support")
            sample_count = stats.get("sample_count")
            accuracy = stats.get("accuracy")
            baseline = stats.get("baseline_accuracy")
            lift = stats.get("lift")
            avg_ret = stats.get("avg_ret_next", None)

            if not isinstance(support, int) or support < 0:
                res.add_error(f"{ploc}.stats.support", "support must be int >= 0")
            if not isinstance(sample_count, int) or sample_count < 0:
                res.add_error(f"{ploc}.stats.sample_count", "sample_count must be int >= 0")
            if isinstance(sample_count, int) and isinstance(support, int):
                if sample_count < support:
                    res.add_warning(f"{ploc}.stats.sample_count", "sample_count < support")
                if abs(sample_count - support) > 5:
                    res.add_warning(f"{ploc}.stats.sample_count", f"sample_count differs from support by > 5 ({sample_count} vs {support})")

            if not isinstance(accuracy, (int, float)) or not (0 <= accuracy <= 1):
                res.add_error(f"{ploc}.stats.accuracy", "accuracy must be float in [0,1]")
            if not isinstance(baseline, (int, float)) or not (0 <= baseline <= 1):
                res.add_error(f"{ploc}.stats.baseline_accuracy", "baseline_accuracy must be float in [0,1]")
            if isinstance(accuracy, (int, float)) and isinstance(baseline, (int, float)):
                if accuracy < baseline:
                    res.add_warning(f"{ploc}.stats.accuracy", "accuracy < baseline_accuracy")
                if strict and accuracy < 0.5:
                    res.add_error(f"{ploc}.stats.accuracy", "accuracy < 0.5 (strict)")
                elif not strict and accuracy < 0.5:
                    res.add_warning(f"{ploc}.stats.accuracy", "accuracy < 0.5")

            if not isinstance(lift, (int, float)):
                res.add_error(f"{ploc}.stats.lift", "lift must be numeric")
            else:
                if isinstance(accuracy, (int, float)) and isinstance(baseline, (int, float)):
                    if abs(lift - (accuracy - baseline)) > 0.01:
                        res.add_warning(f"{ploc}.stats.lift", f"lift deviates from accuracy-baseline by >0.01 (lift={lift}, acc-base={accuracy-baseline})")

            if avg_ret is not None and not isinstance(avg_ret, (int, float)):
                res.add_warning(f"{ploc}.stats.avg_ret_next", "avg_ret_next should be numeric or null")

        # scoring
        if not expect_mapping(scoring):
            res.add_error(f"{ploc}.scoring", "scoring missing/not a mapping")
        else:
            bucket = scoring.get("strength_bucket")
            comment = scoring.get("reliability_comment")
            if bucket not in ALLOWED_STRENGTH:
                res.add_error(f"{ploc}.scoring.strength_bucket", f"invalid strength_bucket: {bucket}")
            if comment is None or not isinstance(comment, str):
                res.add_warning(f"{ploc}.scoring.reliability_comment", "reliability_comment missing or not a string")

        # lifecycle
        if not expect_mapping(lifecycle):
            res.add_error(f"{ploc}.lifecycle", "lifecycle missing/not a mapping")
        else:
            status = lifecycle.get("status")
            last_eval = lifecycle.get("last_evaluated_at")
            notes = lifecycle.get("notes")
            if status not in ALLOWED_STATUS:
                res.add_error(f"{ploc}.lifecycle.status", f"invalid status: {status}")
            if not is_iso_date(last_eval):
                res.add_error(f"{ploc}.lifecycle.last_evaluated_at", f"invalid ISO date: {last_eval!r}")
            if notes is not None and not expect_list(notes):
                res.add_warning(f"{ploc}.lifecycle.notes", "notes should be a list")

        # tags
        if not expect_list(tags) or len(tags) == 0:
            res.add_error(f"{ploc}.tags", "tags must be a non-empty list")
        else:
            tagset = set(str(t) for t in tags)
            if not ALLOWED_TAG_CORE.issubset(tagset):
                res.add_error(f"{ploc}.tags", f"tags must include dir_sequence; got {tags}")
            expected_length_tag = None
            if seq and isinstance(seq, dict) and "length" in seq:
                expected_length_tag = f"length_{seq.get('length')}"
                if expected_length_tag not in tagset:
                    res.add_warning(f"{ploc}.tags", f"expected length tag {expected_length_tag} missing")
            if strict:
                if not ALLOWED_TAG_STRICT.issubset(tagset):
                    res.add_error(f"{ploc}.tags", f"strict mode: tags must include {sorted(ALLOWED_TAG_STRICT)}; got {tags}")
            else:
                if not ALLOWED_TAG_STRICT.issubset(tagset):
                    res.add_warning(f"{ploc}.tags", f"recommended tags {sorted(ALLOWED_TAG_STRICT)} missing; got {tags}")


def validate_top_level(kb: Dict[str, Any], res: ValidationResult) -> None:
    required_top = [
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
    for k in required_top:
        if k not in kb:
            res.add_error(k, f"top-level key '{k}' is missing")


def validate_kb(kb: Dict[str, Any], strict: bool) -> ValidationResult:
    res = ValidationResult()
    validate_top_level(kb, res)
    validate_meta(kb, res, strict)
    validate_datasets(kb, res)
    validate_patterns_dir_sequence_4h(kb, res, strict)
    return res


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def print_human(result: ValidationResult, kb_path: Path) -> None:
    if result.errors or result.warnings:
        print(
            f"[ERROR] {len(result.errors)} error(s), {len(result.warnings)} warning(s) in {kb_path}"
        )
        for issue in result.errors + result.warnings:
            print(f"  - [{issue.level}] {issue.location}: {issue.message}")
    else:
        print(f"[OK] KB validation passed: {kb_path}")


def print_json(result: ValidationResult) -> None:
    data = {
        "ok": result.ok,
        "errors": [issue.__dict__ for issue in result.errors],
        "warnings": [issue.__dict__ for issue in result.warnings],
        "infos": [issue.__dict__ for issue in result.infos],
    }
    print(json.dumps(data, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Validate KB YAML file.")
    parser.add_argument(
        "--kb", "-k", default="kb/btcusdt_4h_knowledge.yaml", help="Path to KB YAML file."
    )
    parser.add_argument("--strict", action="store_true", help="Enable strict validation.")
    parser.add_argument("--json", action="store_true", help="Output result as JSON too.")
    args = parser.parse_args()

    kb_path = Path(args.kb)
    if not kb_path.exists():
        print(f"[ERROR] KB file not found: {kb_path}")
        raise SystemExit(1)

    try:
        kb = yaml.safe_load(kb_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"[ERROR] Failed to read KB: {exc}")
        raise SystemExit(1)

    result = validate_kb(kb, strict=args.strict)

    print_human(result, kb_path)
    if args.json:
        print_json(result)

    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
