from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from patterns.advanced_level1_miner_4h5m import (  # noqa: E402
    FEATURE_MAP,
    PATTERN_EMB_OUT,
    PATTERN_OUT,
    WINDOW_EMB_OUT,
    mine_level1_patterns,
)


WINDOW_SIZES: Sequence[int] = tuple(range(2, 12))
PATTERN_TYPES = ["sequence", "candle_shape", "feature_rule"]


def print_window_size_summary() -> None:
    for tf in ("4h", "5m"):
        path = PATTERN_OUT[tf]
        if not path.exists():
            print(f"[verify] missing {path}")
            continue
        df = pd.read_parquet(path, columns=["window_size"])
        uniq = sorted({int(x) for x in df["window_size"].unique().tolist()})
        print(f"[verify] {tf} unique window_size -> {uniq}")


def main() -> None:
    tasks = [
        ("4h", FEATURE_MAP["4h"], PATTERN_OUT["4h"], PATTERN_EMB_OUT["4h"], WINDOW_EMB_OUT["4h"]),
        ("5m", FEATURE_MAP["5m"], PATTERN_OUT["5m"], PATTERN_EMB_OUT["5m"], WINDOW_EMB_OUT["5m"]),
    ]
    for tf, feat_path, pat_out, pat_emb_out, win_out in tasks:
        print(f"[run] mining timeframe={tf} from {feat_path}")
        mine_level1_patterns(
            timeframe=tf,
            features_path=str(feat_path),
            output_patterns_path=str(pat_out),
            window_sizes=WINDOW_SIZES,
            pattern_types=PATTERN_TYPES,
            output_patterns_with_embeddings_path=str(pat_emb_out),
            output_window_embeddings_path=str(win_out),
        )
    print_window_size_summary()


if __name__ == "__main__":
    main()
