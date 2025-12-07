from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def repartition_hits(
    src_path: Path,
    out_dir: Path,
    overwrite: bool,
) -> int:
    if not src_path.exists():
        raise FileNotFoundError(f"Missing input file: {src_path}")
    df = pd.read_parquet(src_path)
    print(f"[LOAD] {src_path.name} ({len(df)} rows)")
    if df.empty:
        return 0
    df["answer_time"] = pd.to_datetime(df["answer_time"], utc=True, errors="coerce")
    df = df.dropna(subset=["answer_time"])
    df["year"] = df["answer_time"].dt.year
    df["month"] = df["answer_time"].dt.month

    if out_dir.exists() and overwrite:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df.to_parquet(out_dir, partition_cols=["year", "month"], index=False)

    n_parts = sum(1 for _ in out_dir.rglob("*.parquet"))
    print(f"[SAVE] {out_dir} ({n_parts} parquet part files)")
    return n_parts


def main() -> None:
    parser = argparse.ArgumentParser(description="Repartition Level-1 pattern hits into time-partitioned parquet datasets.")
    parser.add_argument(
        "--output-dir-4h",
        default=DATA_DIR / "pattern_hits_4h_level1_partitioned",
        type=Path,
    )
    parser.add_argument(
        "--output-dir-5m",
        default=DATA_DIR / "pattern_hits_5m_level1_partitioned",
        type=Path,
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing partitioned directories if present.",
    )
    args = parser.parse_args()

    tasks = [
        (DATA_DIR / "pattern_hits_4h_level1.parquet", args.output_dir_4h),
        (DATA_DIR / "pattern_hits_5m_level1.parquet", args.output_dir_5m),
    ]

    for src, out_dir in tasks:
        repartition_hits(src, out_dir, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
