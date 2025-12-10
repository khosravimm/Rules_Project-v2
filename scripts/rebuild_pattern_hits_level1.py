#!/usr/bin/env python
"""
Rebuild Level-1 pattern hits for 4h and 5m using existing miner utilities.

Outputs:
  data/pattern_hits_4h_level1.parquet
  data/pattern_hits_5m_level1.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROJECT_SCRIPT = ROOT / "project" / "pattern_hits_level1.py"


def _run_cli(timeframe: str) -> None:
    """Call the existing CLI script for the given timeframe."""
    argv_backup = sys.argv
    sys.argv = [
        str(PROJECT_SCRIPT),
        "--timeframe",
        timeframe,
        "--output-dir",
        str(ROOT / "data"),
    ]
    try:
        import runpy

        runpy.run_path(str(PROJECT_SCRIPT), run_name="__main__")
    finally:
        sys.argv = argv_backup


def _summarize(path: Path) -> Tuple[int, str, str]:
    if not path.exists():
        return 0, "N/A", "N/A"
    df = pd.read_parquet(path)
    if df.empty:
        return 0, "N/A", "N/A"
    ts_col = None
    for cand in ("answer_time", "ans_time", "hit_time"):
        if cand in df.columns:
            ts_col = cand
            break
    if ts_col is None:
        return len(df), "N/A", "N/A"
    ts = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    ts = ts.dropna()
    if ts.empty:
        return len(df), "N/A", "N/A"
    return len(df), ts.min().isoformat(), ts.max().isoformat()


def rebuild_all(timeframes: Iterable[str] = ("4h", "5m")) -> None:
    for tf in timeframes:
        print(f"[rebuild] timeframe={tf}")
        _run_cli(tf)
        out_path = ROOT / "data" / f"pattern_hits_{tf}_level1.parquet"
        count, ts_min, ts_max = _summarize(out_path)
        print(f"[done] {tf}: rows={count}, range=[{ts_min} .. {ts_max}] -> {out_path}")


if __name__ == "__main__":
    rebuild_all()
