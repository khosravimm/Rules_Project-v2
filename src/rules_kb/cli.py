"""Command-line interface for the rules knowledge base."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

from .io import load_yaml, write_yaml_atomic
from .loader import load_knowledge, load_master_knowledge
from .models import KnowledgeBase
from .query import (
    filter_patterns,
    get_patterns_by_market_timeframe,
    list_markets,
    list_timeframes,
)
from .upgrade import upgrade_kb_structure
from .validate import summarize_messages, validate_against_master


def render_table(headers: List[str], rows: Iterable[Iterable[str]]) -> str:
    """Render a human-friendly table without external dependencies."""

    row_list = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in row_list:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    header_line = " | ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    separator = "-+-".join("-" * width for width in widths)
    body_lines = [" | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row)) for row in row_list]
    lines = [header_line, separator] + body_lines if body_lines else [header_line]
    return "\n".join(lines)


def _load_all_knowledge(knowledge_dir: Path) -> List[KnowledgeBase]:
    """Load all kb/*_knowledge.yaml files from a directory."""

    knowledge_dir = knowledge_dir.resolve()
    knowledge_files = sorted(knowledge_dir.glob("*_knowledge.yaml"))
    return [load_knowledge(path) for path in knowledge_files]


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate master and knowledge YAMLs."""

    master_path = Path(args.master_path)
    master_raw = load_yaml(master_path)

    kb_path = Path(args.kb)
    kb_raw = load_yaml(kb_path)

    # Schema validation using existing pydantic model if possible
    ok_schema = True
    try:
        load_master_knowledge(master_path)
    except Exception as exc:  # pragma: no cover
        ok_schema = False
        print(f"[FAIL] Master schema validation: {exc}")
    try:
        load_knowledge(kb_path)
    except Exception as exc:  # pragma: no cover
        ok_schema = False
        print(f"[FAIL] KB schema validation: {exc}")

    msgs = validate_against_master(kb_raw, master_raw)
    ok_extra, text = summarize_messages(msgs)
    if text:
        print(text)

    return 0 if (ok_schema and ok_extra) else 1


def cmd_upgrade(args: argparse.Namespace) -> int:
    """Upgrade KB structure and bump version."""

    kb_path = Path(args.kb)
    master_path = Path(args.master_path)
    kb_raw = load_yaml(kb_path)
    master_raw = load_yaml(master_path)
    kb_upgraded = upgrade_kb_structure(
        kb_raw,
        master=master_raw,
        reason=args.reason,
        level=args.level,
    )
    write_yaml_atomic(kb_path, kb_upgraded)
    print(f"[OK] KB upgraded and written to {kb_path}")
    return 0


def cmd_list_markets(args: argparse.Namespace) -> int:
    """List markets described in master knowledge."""

    master = load_master_knowledge(Path(args.master_path))
    markets = list_markets(master)
    output = render_table(["Market"], [[m] for m in markets])
    print(output)
    return 0


def cmd_list_timeframes(args: argparse.Namespace) -> int:
    """List timeframes for a given market."""

    master = load_master_knowledge(Path(args.master_path))
    timeframes = list_timeframes(master, args.market)
    if not timeframes:
        print(f"No timeframes found for market '{args.market}'.")
        return 1

    output = render_table(["Timeframe"], [[tf] for tf in timeframes])
    print(output)
    return 0


def cmd_list_patterns(args: argparse.Namespace) -> int:
    """List patterns for a given market/timeframe with optional filters."""

    knowledge_dir = Path(args.knowledge_dir)
    knowledge_bases = _load_all_knowledge(knowledge_dir)
    all_patterns = []
    for kb in knowledge_bases:
        all_patterns.extend(get_patterns_by_market_timeframe(kb, args.market, args.timeframe))

    filtered = filter_patterns(
        kb=None,
        patterns=all_patterns,
        min_conf=args.min_conf,
        tags=args.tags,
        regime=args.regime,
        direction=args.direction,
        window_size=args.window_size,
        status=args.status,
    )

    if not filtered:
        print("No patterns found for the specified criteria.")
        return 0

    rows = []
    for pattern in filtered:
        rows.append(
            [
                pattern.id,
                pattern.name,
                pattern.timeframe,
                pattern.dataset_used or "",
                ",".join(pattern.tags) if pattern.tags else "",
                pattern.status,
                f"{pattern.confidence:.3f}" if pattern.confidence is not None else "",
            ]
        )

    output = render_table(
        ["ID", "Name", "Timeframe", "Dataset", "Tags", "Status", "Confidence"],
        rows,
    )
    print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="rules-kb", description="BTC futures rules knowledge base CLI")
    parser.add_argument(
        "--master-path",
        default=Path("project/MASTER_KNOWLEDGE.yaml"),
        help="Path to master knowledge YAML file.",
    )
    parser.add_argument(
        "--knowledge-dir",
        default=Path("kb"),
        help="Directory containing *_knowledge.yaml files (used by list-* commands).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate master and a KB YAML file.")
    validate_parser.add_argument("--kb", default=Path("kb/btcusdt_4h_knowledge.yaml"), help="KB YAML to validate.")
    validate_parser.set_defaults(func=cmd_validate)

    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade KB structure and bump version.")
    upgrade_parser.add_argument("--kb", default=Path("kb/btcusdt_4h_knowledge.yaml"), help="KB YAML to upgrade.")
    upgrade_parser.add_argument(
        "--level",
        choices=["major", "minor", "patch"],
        default="patch",
        help="Version bump level.",
    )
    upgrade_parser.add_argument(
        "--reason",
        default="kb upgrade",
        help="Reason to store in version history notes.",
    )
    upgrade_parser.set_defaults(func=cmd_upgrade)

    subparsers.add_parser("list-markets", help="List markets defined in master knowledge.").set_defaults(
        func=cmd_list_markets
    )

    tf_parser = subparsers.add_parser("list-timeframes", help="List timeframes for a market.")
    tf_parser.add_argument("--market", required=True, help="Market identifier (e.g., BTCUSDT_PERP).")
    tf_parser.set_defaults(func=cmd_list_timeframes)

    patterns_parser = subparsers.add_parser("list-patterns", help="List patterns for a market/timeframe.")
    patterns_parser.add_argument("--market", required=True, help="Market identifier.")
    patterns_parser.add_argument("--timeframe", required=True, help="Timeframe (e.g., 4h, 5m).")
    patterns_parser.add_argument("--min-conf", type=float, default=None, help="Minimum confidence filter.")
    patterns_parser.add_argument("--tags", nargs="+", default=None, help="Required tags for patterns.")
    patterns_parser.add_argument("--regime", default=None, help="Regime filter (case-insensitive).")
    patterns_parser.add_argument("--direction", default=None, help="Direction filter (e.g., long/short).")
    patterns_parser.add_argument(
        "--window-size",
        type=int,
        default=None,
        help="Window length filter (matches pattern window_length).",
    )
    patterns_parser.add_argument("--status", default=None, help="Status filter (e.g., active/candidate).")
    patterns_parser.set_defaults(func=cmd_list_patterns)

    return parser


def main(argv: List[str] | None = None) -> int:
    """Entry point for console_scripts."""

    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
