from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from patterns.advanced_level1_miner_4h5m import (  # noqa: E402
    FEATURE_MAP,
    build_sliding_windows,
    _direction_label,
    _shape_label,
    _window_feature_bucket,
    _load_features,
)

DATA_DIR = ROOT / "data"

PATTERN_PATHS = {
    "4h": DATA_DIR / "patterns_4h_raw_level1.parquet",
    "5m": DATA_DIR / "patterns_5m_raw_level1.parquet",
}

FAMILY_PATHS = {
    "4h": DATA_DIR / "pattern_families_4h.parquet",
    "5m": DATA_DIR / "pattern_families_5m.parquet",
}

OUTPUT_DEFAULT = {
    "4h": DATA_DIR / "pattern_hits_4h_level1.parquet",
    "5m": DATA_DIR / "pattern_hits_5m_level1.parquet",
}

DEFAULT_PATTERN_TYPES = ["sequence", "candle_shape", "feature_rule"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute pattern hits for Level-1 patterns (4h/5m).")
    parser.add_argument("--timeframe", choices=["4h", "5m", "both"], default="both")
    parser.add_argument(
        "--pattern-types",
        help="Comma-separated list: sequence,candle_shape,feature_rule (default: all available).",
        default=None,
    )
    parser.add_argument("--window-size-min", type=int, default=2)
    parser.add_argument("--window-size-max", type=int, default=11)
    parser.add_argument("--max-patterns", type=int, default=500, help="Max patterns per timeframe after filtering.")
    parser.add_argument("--output-dir", default="data", help="Directory to place output parquet files.")
    return parser.parse_args()


def _stable_pattern_id(row: pd.Series) -> str:
    """
    Reuse the stable id approach from the inventory report:
      pat_{abs(hash(timeframe|pattern_type|window_size|definition)) % 10_000_000}
    """
    base = (
        f"{row.get('timeframe','?')}|{row.get('pattern_type','?')}"
        f"|{row.get('window_size','?')}|{row.get('definition','?')}"
    )
    return f"pat_{abs(hash(base)) % 10_000_000}"


def _compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    if "score" in df.columns:
        return df
    df = df.copy()
    df["score"] = (
        0.5 * np.maximum(df["lift"] - 1.0, 0.0)
        + 0.3 * np.log(df["support"] + 1.0)
        + 0.2 * np.maximum(df["stability"], 0.0)
    )
    return df


def _load_patterns_for_timeframe(
    timeframe: str,
    pattern_types: Optional[Iterable[str]],
    ws_min: int,
    ws_max: int,
    max_patterns: int,
) -> pd.DataFrame:
    path = PATTERN_PATHS[timeframe]
    if not path.exists():
        raise FileNotFoundError(f"Missing pattern file: {path}")
    df = pd.read_parquet(path)
    df = df.copy()
    if "pattern_id" in df.columns:
        df["pattern_id"] = df["pattern_id"]
    elif "id" in df.columns:
        df["pattern_id"] = df["id"]
    else:
        df["pattern_id"] = df.apply(_stable_pattern_id, axis=1)

    if pattern_types:
        allowed = set(pattern_types)
        df = df[df["pattern_type"].isin(allowed)]

    df = df[(df["window_size"] >= ws_min) & (df["window_size"] <= ws_max)]
    df = _compute_scores(df)
    df = df.sort_values("score", ascending=False)
    if max_patterns and max_patterns > 0:
        df = df.head(max_patterns)
    return df.reset_index(drop=True)


def _load_family_lookup(timeframe: str) -> Dict[str, Tuple[str, Optional[str]]]:
    """
    Build a lookup: canonical_key -> (family_id, strength)
    canonical_key = pattern_type|w{window_size}|{definition} (lowercase)
    """
    path = FAMILY_PATHS.get(timeframe)
    if not path or not path.exists():
        print(f"[warn] Family file missing for {timeframe}: {path}")
        return {}
    fam_df = pd.read_parquet(path)
    lookup: Dict[str, Tuple[str, Optional[str]]] = {}
    for _, row in fam_df.iterrows():
        fam_id = row.get("family_id")
        strength = row.get("strength_level") or row.get("strength")
        members = row.get("member_keys", [])
        if isinstance(members, np.ndarray):
            members = members.tolist()
        if not isinstance(members, list):
            continue
        for mk in members:
            key = str(mk).lower()
            lookup[key] = (fam_id, strength)
    return lookup


def _attach_family_columns(df: pd.DataFrame, fam_lookup: Dict[str, Tuple[str, Optional[str]]]) -> pd.DataFrame:
    if not fam_lookup:
        df = df.copy()
        df["family_id"] = None
        df["strength"] = None
        return df

    def _map_family(row: pd.Series) -> Tuple[Optional[str], Optional[str]]:
        key = f"{row['pattern_type']}|w{int(row['window_size'])}|{row['definition']}".lower()
        fam = fam_lookup.get(key)
        if fam:
            return fam[0], fam[1]
        return None, None

    fam_ids: List[Optional[str]] = []
    strengths: List[Optional[str]] = []
    for _, r in df.iterrows():
        fid, strength = _map_family(r)
        fam_ids.append(fid)
        strengths.append(strength)
    df = df.copy()
    df["family_id"] = fam_ids
    df["strength"] = strengths
    return df


def _build_pattern_index_map(
    df_sorted: pd.DataFrame,
    window_size: int,
    enabled_types: Set[str],
) -> Tuple[Dict[str, List[int]], List[pd.Timestamp], List[pd.Timestamp]]:
    """
    Rebuild the pattern -> window index map using the exact logic from the Level-1 miner.
    Keys follow the miner convention: "{ptype}::{definition}"
    """
    windows, starts, ends = build_sliding_windows(df_sorted, window_size=window_size)
    n_windows = len(windows)
    mapping: Dict[str, List[int]] = {}
    if n_windows == 0 or not enabled_types:
        return mapping, starts, ends

    opens = df_sorted["open"].to_numpy(dtype=float)
    closes = df_sorted["close"].to_numpy(dtype=float)
    dir_labels = _direction_label(opens, closes)

    for idx in range(n_windows):
        win = windows[idx]
        if "sequence" in enabled_types:
            seq_key = "|".join(dir_labels[idx : idx + window_size])
            mapping.setdefault(f"sequence::{seq_key}", []).append(idx)
        if "candle_shape" in enabled_types:
            sh = tuple(_shape_label(*win[i, :4]) for i in range(window_size))
            sh_key = "|".join(sh)
            mapping.setdefault(f"candle_shape::{sh_key}", []).append(idx)
        if "feature_rule" in enabled_types:
            feat_key = _window_feature_bucket(win)
            mapping.setdefault(f"feature_rule::{feat_key}", []).append(idx)

    return mapping, starts, ends


def _collect_hits_for_timeframe(
    timeframe: str,
    patterns: pd.DataFrame,
    features_path: Path,
) -> pd.DataFrame:
    df_feat = _load_features(features_path)
    df_feat = df_feat.sort_values("open_time").reset_index(drop=True)
    times: List[pd.Timestamp] = df_feat["open_time"].tolist()

    hits: List[Dict[str, object]] = []

    for window_size, group in patterns.groupby("window_size"):
        ws_int = int(window_size)
        enabled_types = set(group["pattern_type"].unique().tolist())
        index_map, window_starts, window_ends = _build_pattern_index_map(
            df_feat,
            window_size=ws_int,
            enabled_types=enabled_types,
        )
        print(
            f"[match] timeframe={timeframe} w={ws_int} "
            f"patterns={len(group)} windows={len(window_starts)} map_keys={len(index_map)}"
        )
        for _, pat in group.iterrows():
            ptype = pat["pattern_type"]
            definition = pat["definition"]
            key = f"{ptype}::{definition}"
            idx_list = index_map.get(key, [])
            if not idx_list:
                continue
            for idx in idx_list:
                answer_index = idx + ws_int
                if answer_index >= len(times):
                    continue
                start_index = idx
                end_index = idx + ws_int - 1
                hits.append(
                    {
                        "timeframe": timeframe,
                        "pattern_id": pat["pattern_id"],
                        "pattern_type": ptype,
                        "window_size": ws_int,
                        "family_id": pat.get("family_id"),
                        "strength": pat.get("strength"),
                        "answer_index": int(answer_index),
                        "start_index": int(start_index),
                        "end_index": int(end_index),
                        "answer_time": times[answer_index],
                        "start_time": times[start_index],
                        "end_time": times[end_index],
                        "support": int(pat["support"]),
                        "lift": float(pat["lift"]),
                        "stability": float(pat["stability"]),
                        "score": float(pat["score"]),
                    }
                )
    cols = [
        "timeframe",
        "pattern_id",
        "pattern_type",
        "window_size",
        "family_id",
        "strength",
        "answer_index",
        "start_index",
        "end_index",
        "answer_time",
        "start_time",
        "end_time",
        "support",
        "lift",
        "stability",
        "score",
    ]
    return pd.DataFrame(hits, columns=cols)


def _resolve_timeframes(choice: str) -> List[str]:
    if choice == "both":
        return ["4h", "5m"]
    return [choice]


def main() -> None:
    args = parse_args()
    pattern_types = (
        [p.strip() for p in args.pattern_types.split(",") if p.strip()]
        if args.pattern_types
        else None
    )
    timeframes = _resolve_timeframes(args.timeframe)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for tf in timeframes:
        pat_df = _load_patterns_for_timeframe(
            timeframe=tf,
            pattern_types=pattern_types,
            ws_min=args.window_size_min,
            ws_max=args.window_size_max,
            max_patterns=args.max_patterns,
        )
        if pat_df.empty:
            print(f"[warn] No patterns after filtering for {tf}; skipping.")
            continue

        fam_lookup = _load_family_lookup(tf)
        pat_df = _attach_family_columns(pat_df, fam_lookup)

        hits_df = _collect_hits_for_timeframe(
            timeframe=tf,
            patterns=pat_df,
            features_path=FEATURE_MAP[tf],
        )

        out_path = output_dir / OUTPUT_DEFAULT[tf].name
        hits_df.to_parquet(out_path, index=False)
        print(f"[OK] Wrote {out_path} ({len(hits_df)} hits)")


if __name__ == "__main__":
    main()
