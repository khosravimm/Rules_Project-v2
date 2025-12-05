#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Promote selected 4h direction-sequence patterns to trading rules and update KB.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

NOW_ISO = datetime.utcnow().isoformat(timespec="seconds") + "Z"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote 4h patterns to trading rules in the KB.")
    parser.add_argument("--kb", "-k", default="kb/btcusdt_4h_knowledge.yaml", help="Path to KB YAML file.")
    parser.add_argument(
        "--patterns",
        "-p",
        nargs="*",
        default=[],
        help="Pattern IDs to promote (e.g. PAT4H_DIR_L3_001 ...).",
    )
    parser.add_argument(
        "--patterns-file",
        help="Path to a file containing pattern IDs (one per line, # for comments).",
    )
    parser.add_argument(
        "--new-pattern-status",
        default="candidate",
        choices=["exploratory", "candidate", "active", "deprecated", "rejected"],
        help="Lifecycle status to set on promoted patterns.",
    )
    parser.add_argument(
        "--rule-status",
        default="draft",
        choices=["draft", "candidate", "active", "deprecated", "rejected"],
        help="Lifecycle status for created/updated rules.",
    )
    parser.add_argument(
        "--direction",
        default="auto",
        choices=["long", "short", "auto"],
        help="Direction override. If auto, derive from favored_class UP->long, DOWN->short.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write changes; just report.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed logs.",
    )
    return parser.parse_args()


def collect_pattern_ids(args: argparse.Namespace) -> List[str]:
    ids: List[str] = []
    # from CLI
    for pid in args.patterns or []:
        if pid and pid not in ids:
            ids.append(pid)
    # from file
    if args.patterns_file:
        pfile = Path(args.patterns_file)
        if not pfile.exists():
            print(f"[ERROR] patterns-file not found: {pfile}")
            raise SystemExit(1)
        for line in pfile.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line not in ids:
                ids.append(line)
    if not ids:
        print("[ERROR] No pattern IDs provided (use --patterns and/or --patterns-file).")
        raise SystemExit(1)
    return ids


def load_kb(kb_path: Path) -> Dict[str, Any]:
    if not kb_path.exists():
        print(f"[ERROR] KB file not found: {kb_path}")
        raise SystemExit(1)
    try:
        return yaml.safe_load(kb_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"[ERROR] Failed to read KB: {exc}")
        raise SystemExit(1)


def get_pattern_map(kb: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    items = (
        kb.get("patterns", {})
        .get("dir_sequence_4h", {})
        .get("items", [])
    )
    if not isinstance(items, list):
        return {}
    return {p.get("id"): p for p in items if isinstance(p, dict) and p.get("id")}


def derive_rule_id_from_pattern(pattern_id: str, direction: str) -> str:
    base = pattern_id
    if pattern_id.startswith("PAT"):
        base = "RULE" + pattern_id[3:]
    else:
        base = f"RULE_{pattern_id}"
    suffix = "_LONG" if direction == "long" else "_SHORT"
    return base + suffix


def ensure_list(val: Any) -> List[Any]:
    return val if isinstance(val, list) else []


def find_rule_by_id(rules: List[Dict[str, Any]], rule_id: str) -> Optional[Dict[str, Any]]:
    for r in rules:
        if isinstance(r, dict) and r.get("id") == rule_id:
            return r
    return None


def resolve_direction(direction_mode: str, pattern: Dict[str, Any]) -> Optional[str]:
    if direction_mode in {"long", "short"}:
        return direction_mode
    target = pattern.get("target", {}) or {}
    favored = str(target.get("favored_class", "")).upper()
    if favored == "UP":
        return "long"
    if favored == "DOWN":
        return "short"
    return None


def promote_patterns(
    kb: Dict[str, Any],
    pattern_ids: List[str],
    new_pattern_status: str,
    rule_status: str,
    direction_mode: str,
    dry_run: bool,
    verbose: bool,
) -> Tuple[int, int, int]:
    promoted = 0
    created = 0
    updated = 0

    # Ensure trading_rules structure
    kb.setdefault("trading_rules", {})
    tr = kb["trading_rules"]
    if not isinstance(tr, dict):
        kb["trading_rules"] = {}
        tr = kb["trading_rules"]
    tr.setdefault("rules", [])
    rules_list: List[Dict[str, Any]] = tr["rules"]
    if not isinstance(rules_list, list):
        tr["rules"] = []
        rules_list = tr["rules"]

    pmap = get_pattern_map(kb)
    for pid in pattern_ids:
        patt = pmap.get(pid)
        if patt is None:
            print(f"[WARNING] Pattern {pid} not found; skipping.")
            continue

        direction = resolve_direction(direction_mode, patt)
        if direction is None:
            print(f"[WARNING] Could not resolve direction for pattern {pid}; skipping.")
            continue

        rule_id = derive_rule_id_from_pattern(pid, direction)

        # Update pattern lifecycle
        lifecycle = patt.setdefault("lifecycle", {})
        if not isinstance(lifecycle, dict):
            lifecycle = {}
            patt["lifecycle"] = lifecycle
        lifecycle["status"] = new_pattern_status
        lifecycle["last_evaluated_at"] = NOW_ISO
        notes = ensure_list(lifecycle.get("notes"))
        notes.append(f"Promoted to rule {rule_id} on {NOW_ISO}")
        lifecycle["notes"] = notes
        promoted += 1
        if verbose:
            print(f"[INFO] Pattern {pid}: status -> {new_pattern_status}, note added.")

        # Create/update rule
        existing = find_rule_by_id(rules_list, rule_id)
        if existing is None:
            rule = {
                "id": rule_id,
                "name": f"4h pattern {pid} → {direction.upper()}",
                "timeframe": "4h",
                "direction": direction,
                "pattern_refs": [pid],
                "logic": {
                    "entry": {
                        "description": f"Enter {direction.upper()} after pattern {pid} fires.",
                        "conditions": [
                            f"Last N 4h DIR_4H matches the sequence from pattern {pid}.",
                            "No conflicting higher-priority risk constraint.",
                        ],
                    },
                    "exit": {
                        "description": "Initial generic exit; must be refined via backtesting.",
                        "stop_loss": {"type": "percent", "value": 0.02},
                        "take_profit": {"type": "rr", "rr": 2.0},
                        "time_based": {"max_bars_hold": 4},
                    },
                },
                "risk": {
                    "max_risk_per_trade_pct": 1.0,
                    "leverage": 10,
                    "notes": [],
                },
                "lifecycle": {
                    "status": rule_status,
                    "created_at": NOW_ISO,
                    "updated_at": NOW_ISO,
                    "notes": [f"Rule created from pattern {pid} with direction={direction}."],
                },
                "tags": [
                    "auto_pattern_based",
                    "btc_4h",
                    "dir_sequence",
                    f"pattern_id:{pid}",
                    f"direction:{direction}",
                ],
            }
            rules_list.append(rule)
            created += 1
            if verbose:
                print(f"[INFO] Created rule {rule_id} from pattern {pid}.")
        else:
            # update existing
            existing.setdefault("lifecycle", {})
            if not isinstance(existing["lifecycle"], dict):
                existing["lifecycle"] = {}
            existing["lifecycle"]["status"] = rule_status
            existing["lifecycle"]["updated_at"] = NOW_ISO
            lifecycle_notes = ensure_list(existing["lifecycle"].get("notes"))
            lifecycle_notes.append(f"Updated from pattern {pid} at {NOW_ISO}")
            existing["lifecycle"]["notes"] = lifecycle_notes
            # ensure pattern_refs
            existing.setdefault("pattern_refs", [])
            if pid not in existing["pattern_refs"]:
                if not isinstance(existing["pattern_refs"], list):
                    existing["pattern_refs"] = []
                existing["pattern_refs"].append(pid)
            updated += 1
            if verbose:
                print(f"[INFO] Updated existing rule {rule_id} (status {rule_status}).")

        if dry_run:
            continue

    return promoted, created, updated


def write_kb_atomic(kb_path: Path, kb: Dict[str, Any]) -> None:
    tmp_path = kb_path.with_suffix(kb_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(kb, f, allow_unicode=True, sort_keys=False)
    tmp_path.replace(kb_path)


def main() -> None:
    args = parse_args()
    kb_path = Path(args.kb)
    pattern_ids = collect_pattern_ids(args)

    kb = load_kb(kb_path)
    promoted, created, updated = promote_patterns(
        kb=kb,
        pattern_ids=pattern_ids,
        new_pattern_status=args.new_pattern_status,
        rule_status=args.rule_status,
        direction_mode=args.direction,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    if args.dry_run:
        print(f"[DRY-RUN] Would promote {promoted} pattern(s), create {created}, update {updated} rule(s).")
        raise SystemExit(0)

    write_kb_atomic(kb_path, kb)
    print(f"[OK] Updated KB: {kb_path}")
    print(f"[OK] Patterns promoted: {promoted}")
    print(f"[OK] Rules created: {created}, updated: {updated}")


if __name__ == "__main__":
    main()
