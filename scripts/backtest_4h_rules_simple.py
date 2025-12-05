#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/backtest_4h_rules_simple.py

Simple, transparent backtest for 4h direction-sequence rules stored in KB.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml


@dataclass
class RuleBacktestResult:
    rule_id: str
    test_direction: str
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    total_R: float
    avg_R: float
    max_drawdown_R: float
    first_trade_time: Optional[str]
    last_trade_time: Optional[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple backtest for 4h rules from KB.")
    parser.add_argument("--kb", "-k", default="kb/btcusdt_4h_knowledge.yaml", help="Path to KB YAML file.")
    parser.add_argument("--rules", nargs="*", default=[], help="Rule IDs to backtest.")
    parser.add_argument("--rules-file", help="File with rule IDs, one per line (# for comments).")
    parser.add_argument(
        "--rule-status",
        default="candidate",
        choices=["draft", "candidate", "active", "all"],
        help="Filter rules by lifecycle status (default: candidate).",
    )
    parser.add_argument(
        "--direction-mode",
        choices=["rule", "reverse"],
        default="rule",
        help=(
            "How to determine trade direction: "
            "'rule' uses the direction stored in the rule "
            "('long'/'short'); 'reverse' backtests the opposite side "
            "(long->short, short->long)."
        ),
    )
    parser.add_argument("--start-date", help="Start date YYYY-MM-DD (inclusive).")
    parser.add_argument("--end-date", help="End date YYYY-MM-DD (inclusive).")
    parser.add_argument("--max-rules", type=int, default=None, help="Limit number of rules to backtest.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write results; just print.")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging.")
    return parser.parse_args()


def collect_rule_ids(args: argparse.Namespace) -> List[str]:
    ids: List[str] = []
    for rid in args.rules or []:
        if rid and rid not in ids:
            ids.append(rid)
    if args.rules_file:
        pfile = Path(args.rules_file)
        if not pfile.exists():
            print(f"[ERROR] rules-file not found: {pfile}")
            raise SystemExit(1)
        for line in pfile.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line not in ids:
                ids.append(line)
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


def load_4h_data(path_raw: Path, path_features: Path) -> pd.DataFrame:
    """Load raw and features parquet, merge on timestamp, ensure DIR_4H exists."""
    if not path_raw.exists():
        raise FileNotFoundError(f"Raw 4h file not found: {path_raw}")
    if not path_features.exists():
        raise FileNotFoundError(f"Features 4h file not found: {path_features}")

    raw = pd.read_parquet(path_raw)
    feats = pd.read_parquet(path_features)

    # detect timestamp column
    def find_ts(df: pd.DataFrame) -> str:
        for c in ["timestamp", "ts", "open_time"]:
            if c in df.columns:
                return c
        for c in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                return c
        raise KeyError("No datetime-like column found in dataframe")

    ts_raw = find_ts(raw)
    ts_feat = find_ts(feats)
    raw[ts_raw] = pd.to_datetime(raw[ts_raw])
    feats[ts_feat] = pd.to_datetime(feats[ts_feat])

    df = pd.merge(raw, feats, left_on=ts_raw, right_on=ts_feat, how="inner", suffixes=("_raw", "_feat"))
    if f"{ts_raw}_raw" in df.columns:
        df = df.rename(columns={f"{ts_raw}_raw": "timestamp"})
    if f"{ts_feat}_feat" in df.columns:
        df = df.rename(columns={f"{ts_feat}_feat": "timestamp"})
    if "timestamp" not in df.columns and ts_raw in df.columns:
        df = df.rename(columns={ts_raw: "timestamp"})
    if "timestamp" not in df.columns:
        raise KeyError("timestamp column not found after merge")
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").set_index("timestamp")

    # normalize OHLC columns (prefer raw)
    for col in ["open", "high", "low", "close"]:
        if col + "_raw" in df.columns:
            df[col] = df[col + "_raw"]
        elif col in df.columns:
            df[col] = df[col]
        elif col + "_feat" in df.columns:
            df[col] = df[col + "_feat"]

    # ensure DIR_4H
    dir_cols = [c for c in df.columns if c.upper() == "DIR_4H" or c.lower() == "dir_4h"]
    if dir_cols:
        df["DIR_4H"] = df[dir_cols[0]]
    else:
        if "close" not in df.columns or "open" not in df.columns:
            raise KeyError("Need close/open to compute DIR_4H")
        df["DIR_4H"] = (df["close"] > df["open"]).astype(int) - (df["close"] < df["open"]).astype(int)

    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            raise KeyError(f"Missing OHLC column: {col}")
    return df


def load_rules_from_kb(kb: Dict[str, Any], args: argparse.Namespace) -> List[Dict[str, Any]]:
    rules = kb.get("trading_rules", {}).get("rules", [])
    if not isinstance(rules, list):
        return []
    rule_ids_filter = collect_rule_ids(args)
    out = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        if not rid:
            continue
        status = r.get("lifecycle", {}).get("status", "unknown")
        if args.rule_status != "all" and status != args.rule_status:
            continue
        if rule_ids_filter and rid not in rule_ids_filter:
            continue
        out.append(r)
    out = sorted(out, key=lambda x: x.get("id", ""))
    if args.max_rules:
        out = out[: args.max_rules]
    return out


def get_pattern_by_id(kb: Dict[str, Any], pattern_id: str) -> Optional[Dict[str, Any]]:
    items = kb.get("patterns", {}).get("dir_sequence_4h", {}).get("items", [])
    if not isinstance(items, list):
        return None
    for p in items:
        if isinstance(p, dict) and p.get("id") == pattern_id:
            return p
    return None


def extract_sequence_from_pattern(pattern: Dict[str, Any]) -> List[str]:
    seq = pattern.get("sequence", {}) or {}
    dirs = seq.get("dirs", [])
    out: List[str] = []
    for d in dirs:
        s = str(d).upper()
        if s in {"UP", "RET_UP", "1", "+1"}:
            out.append("UP")
        elif s in {"DOWN", "RET_DOWN", "-1"}:
            out.append("DOWN")
        else:
            out.append("FLAT")
    return out


def resolve_test_direction(rule_direction: str, direction_mode: str) -> str:
    """
    Return the direction to use for simulation.

    - If direction_mode == "rule": return rule_direction as-is.
    - If direction_mode == "reverse":
        - If rule_direction == "long":  return "short"
        - If rule_direction == "short": return "long"
        - Otherwise (unknown value):    return rule_direction as-is.
    """
    dir_norm = str(rule_direction).lower()
    mode_norm = str(direction_mode).lower()
    if mode_norm == "rule":
        return dir_norm
    if mode_norm == "reverse":
        if dir_norm == "long":
            return "short"
        if dir_norm == "short":
            return "long"
    return dir_norm


def generate_entry_signals(df: pd.DataFrame, sequence_dirs: List[str]) -> pd.Series:
    """Return boolean Series marking where pattern fires at bar t (entry at t+1)."""
    n = len(sequence_dirs)
    if n == 0:
        return pd.Series(False, index=df.index)
    dirs = [d.upper() for d in sequence_dirs]

    def canon(x: Any) -> str:
        s = str(x).upper()
        if s in {"UP", "RET_UP", "1", "+1"}:
            return "UP"
        if s in {"DOWN", "RET_DOWN", "-1"}:
            return "DOWN"
        return "FLAT"

    dir_series = df["DIR_4H"].apply(canon)
    signals = []
    vals = dir_series.tolist()
    for i in range(len(vals)):
        if i < n - 1:
            signals.append(False)
            continue
        window = vals[i - n + 1 : i + 1]
        signals.append(window == dirs)
    return pd.Series(signals, index=df.index)


def backtest_rule(
    df: pd.DataFrame,
    rule: Dict[str, Any],
    pattern: Dict[str, Any],
    sequence_dirs: List[str],
    test_direction: str,
) -> RuleBacktestResult:
    exit_logic = rule.get("logic", {}).get("exit", {}) or {}
    stop_loss_pct = float(exit_logic.get("stop_loss", {}).get("value", 0.02) or 0.02)
    rr = float(exit_logic.get("take_profit", {}).get("rr", 2.0) or 2.0)
    max_bars_hold = int(exit_logic.get("time_based", {}).get("max_bars_hold", 4) or 4)

    signals = generate_entry_signals(df, sequence_dirs)
    direction = str(test_direction or "").lower()
    if direction not in {"long", "short"}:
        return RuleBacktestResult(
            rule_id=rule.get("id", "UNKNOWN"),
            test_direction=direction,
            n_trades=0,
            n_wins=0,
            n_losses=0,
            win_rate=0.0,
            total_R=0.0,
            avg_R=0.0,
            max_drawdown_R=0.0,
            first_trade_time=None,
            last_trade_time=None,
        )
    timestamps = df.index.tolist()
    closes = df["close"].tolist()
    highs = df["high"].tolist()
    lows = df["low"].tolist()

    in_pos = False
    entry_idx = None
    n_trades = n_wins = n_losses = 0
    equity_R = 0.0
    peak_R = 0.0
    max_dd_R = 0.0
    first_trade_time = None
    last_trade_time = None

    for i in range(len(df)):
        if in_pos:
            bars_held = i - entry_idx
            entry_price = closes[entry_idx]
            sl_price = entry_price * (1 - stop_loss_pct) if direction == "long" else entry_price * (1 + stop_loss_pct)
            tp_price = entry_price * (1 + stop_loss_pct * rr) if direction == "long" else entry_price * (1 - stop_loss_pct * rr)

            bar_low = lows[i]
            bar_high = highs[i]
            exit_price = None
            if direction == "long":
                if bar_low <= sl_price and bar_high >= tp_price:
                    exit_price = sl_price
                elif bar_low <= sl_price:
                    exit_price = sl_price
                elif bar_high >= tp_price:
                    exit_price = tp_price
            else:
                if bar_high >= sl_price and bar_low <= tp_price:
                    exit_price = sl_price
                elif bar_high >= sl_price:
                    exit_price = sl_price
                elif bar_low <= tp_price:
                    exit_price = tp_price

            if exit_price is None and bars_held >= max_bars_hold:
                exit_price = closes[i]

            if exit_price is not None:
                raw_return = (exit_price / entry_price - 1) if direction == "long" else (entry_price / exit_price - 1)
                outcome_R = raw_return / stop_loss_pct
                equity_R += outcome_R
                peak_R = max(peak_R, equity_R)
                max_dd_R = min(max_dd_R, equity_R - peak_R)
                n_trades += 1
                if outcome_R > 0:
                    n_wins += 1
                else:
                    n_losses += 1
                last_trade_time = timestamps[i].isoformat()
                in_pos = False
                entry_idx = None
                continue

        if not in_pos and signals.iat[i]:
            if i + 1 < len(df):
                in_pos = True
                entry_idx = i + 1
                first_trade_time = first_trade_time or timestamps[i + 1].isoformat()

    win_rate = (n_wins / n_trades) if n_trades > 0 else 0.0
    avg_R = (equity_R / n_trades) if n_trades > 0 else 0.0

    return RuleBacktestResult(
        rule_id=rule.get("id", "UNKNOWN"),
        test_direction=direction,
        n_trades=n_trades,
        n_wins=n_wins,
        n_losses=n_losses,
        win_rate=win_rate,
        total_R=equity_R,
        avg_R=avg_R,
        max_drawdown_R=max_dd_R,
        first_trade_time=first_trade_time,
        last_trade_time=last_trade_time,
    )


def attach_backtest_to_kb(
    kb: Dict[str, Any],
    run_id: str,
    created_at: str,
    args: argparse.Namespace,
    results: List[RuleBacktestResult],
) -> None:
    # Normalize backtests container
    if not isinstance(kb.get("backtests"), dict):
        kb["backtests"] = {}
    backtests = kb["backtests"]
    if not isinstance(backtests.get("simple_4h_rules"), dict):
        backtests["simple_4h_rules"] = {}
    simple = backtests["simple_4h_rules"]
    if not isinstance(simple.get("run_history"), list):
        simple["run_history"] = []
    run_hist = simple["run_history"]

    run_entry = {
        "run_id": run_id,
        "created_at": created_at,
        "params": {
            "rule_status_filter": args.rule_status,
            "direction_mode": args.direction_mode,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "max_rules": args.max_rules,
        },
        "results": [
            {
                "rule_id": r.rule_id,
                "test_direction": r.test_direction,
                "n_trades": r.n_trades,
                "n_wins": r.n_wins,
                "n_losses": r.n_losses,
                "win_rate": r.win_rate,
                "total_R": r.total_R,
                "avg_R": r.avg_R,
                "max_drawdown_R": r.max_drawdown_R,
                "first_trade_time": r.first_trade_time,
                "last_trade_time": r.last_trade_time,
            }
            for r in results
        ],
    }
    run_hist.append(run_entry)


def write_kb_atomic(kb_path: Path, kb: Dict[str, Any]) -> None:
    tmp_path = kb_path.with_suffix(kb_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(kb, f, allow_unicode=True, sort_keys=False)
    tmp_path.replace(kb_path)


def main() -> None:
    args = parse_args()
    kb_path = Path(args.kb)
    kb = load_kb(kb_path)

    ds = kb.get("datasets", {}).get("btcusdt_4h", {}) or {}
    path_raw = ds.get("path_raw")
    path_features = ds.get("path_features")
    if not path_raw or not path_features:
        print("[ERROR] datasets.btcusdt_4h.path_raw/path_features missing in KB.")
        raise SystemExit(1)

    df = load_4h_data(Path(path_raw), Path(path_features))
    if args.start_date:
        df = df[df.index >= pd.to_datetime(args.start_date)]
    if args.end_date:
        df = df[df.index <= pd.to_datetime(args.end_date) + pd.Timedelta(days=1)]

    rules = load_rules_from_kb(kb, args)
    if not rules:
        print("[INFO] No rules to backtest after filtering.")
        raise SystemExit(0)

    results: List[RuleBacktestResult] = []
    for rule in rules:
        pattern_refs = rule.get("pattern_refs") or []
        if not isinstance(pattern_refs, list) or not pattern_refs:
            print(f"[WARNING] Rule {rule.get('id')} has no pattern_refs; skipping.")
            continue
        pattern_id = pattern_refs[0]
        if len(pattern_refs) > 1:
            print(f"[INFO] Rule {rule.get('id')} has multiple pattern_refs; using first: {pattern_id}")
        patt = get_pattern_by_id(kb, pattern_id)
        if patt is None:
            print(f"[WARNING] Pattern {pattern_id} not found for rule {rule.get('id')}; skipping.")
            continue

        seq_dirs = extract_sequence_from_pattern(patt)
        rule_direction = str(rule.get("direction", "")).lower()
        test_direction = resolve_test_direction(rule_direction, args.direction_mode)
        res = backtest_rule(df, rule, patt, seq_dirs, test_direction)
        results.append(res)
        if args.verbose:
            print(
                f"[INFO] Rule {res.rule_id}: direction={res.test_direction}, trades={res.n_trades}, win%={res.win_rate:.2f}, "
                f"total_R={res.total_R:.2f}"
            )

    if results:
        headers = ["Rule ID", "Dir", "Trades", "Win%", "Total R", "Avg R", "MaxDD R"]
        rows = []
        for r in results:
            rows.append(
                [
                    r.rule_id,
                    r.test_direction,
                    str(r.n_trades),
                    f"{r.win_rate:.2f}",
                    f"{r.total_R:+.2f}",
                    f"{r.avg_R:+.2f}",
                    f"{r.max_drawdown_R:+.2f}",
                ]
            )
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))

        def fmt_row(row: List[str]) -> str:
            return "  ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))

        print(fmt_row(headers))
        print(fmt_row(["-" * w for w in col_widths]))
        for row in rows:
            print(fmt_row(row))
        print(f"[INFO] Tested {len(results)} rule(s).")
        print(f"[INFO] direction-mode = {args.direction_mode}")
    else:
        print("[INFO] No results to show.")
        raise SystemExit(0)

    if args.dry_run:
        print("[DRY-RUN] Not writing backtests into KB.")
        raise SystemExit(0)

    run_id = datetime.utcnow().strftime("simple_4h_rules_%Y%m%d_%H%M%S")
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    attach_backtest_to_kb(kb, run_id, created_at, args, results)
    write_kb_atomic(kb_path, kb)
    print(f"[OK] Backtest run saved into KB under backtests.simple_4h_rules.run_history (run_id={run_id}).")


if __name__ == "__main__":
    main()
