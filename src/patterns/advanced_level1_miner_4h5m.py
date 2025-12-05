from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

RAW_MAP = {
    "4h": DATA_DIR / "btcusdt_4h_raw.parquet",
    "5m": DATA_DIR / "btcusdt_5m_raw.parquet",
}

PATTERN_OUT = {
    "4h": DATA_DIR / "patterns_4h_raw_level1.parquet",
    "5m": DATA_DIR / "patterns_5m_raw_level1.parquet",
}
PATTERN_EMB_OUT = {
    "4h": DATA_DIR / "patterns_4h_raw_level1_with_embeddings.parquet",
    "5m": DATA_DIR / "patterns_5m_raw_level1_with_embeddings.parquet",
}
WINDOW_EMB_OUT = {
    "4h": DATA_DIR / "window_embeddings_4h_level1.parquet",
    "5m": DATA_DIR / "window_embeddings_5m_level1.parquet",
}

FEATURE_COLUMNS = ["open", "high", "low", "close", "volume"]
EMBED_DIM = 16
MAX_TRAIN_WINDOWS = 50_000


# -----------------------------------------------------------------------------
# Window utilities
# -----------------------------------------------------------------------------
def build_sliding_windows(
    df: pd.DataFrame,
    window_size: int,
) -> Tuple[np.ndarray, List[pd.Timestamp], List[pd.Timestamp]]:
    """
    From a time-ordered OHLCV DataFrame build sliding windows of length `window_size`.
    Returns:
        - windows: np.ndarray shape (n_windows, window_size, feature_dim)
        - window_starts: list of start timestamps (open_time of first candle in window)
        - window_ends: list of end timestamps (open_time of last candle in window)
    Notes:
        - We keep only windows that have a "next" candle available for supervision.
    """
    if window_size < 2:
        raise ValueError("window_size must be >= 2")
    if not {"open_time", "open", "high", "low", "close", "volume"}.issubset(df.columns):
        raise ValueError("DataFrame must contain standard OHLCV columns.")

    df_sorted = df.sort_values("open_time").reset_index(drop=True)
    values = df_sorted[FEATURE_COLUMNS].to_numpy(dtype=float)
    times = pd.to_datetime(df_sorted["open_time"], utc=True)

    n = len(df_sorted)
    n_windows = n - window_size - 1  # reserve next candle for supervision
    if n_windows <= 0:
        return np.empty((0, window_size, len(FEATURE_COLUMNS))), [], []

    windows = np.lib.stride_tricks.sliding_window_view(values, (window_size, len(FEATURE_COLUMNS)))
    windows = windows.reshape(n - window_size + 1, window_size, len(FEATURE_COLUMNS))
    windows = windows[:n_windows]

    window_starts = [times[i] for i in range(n_windows)]
    window_ends = [times[i + window_size - 1] for i in range(n_windows)]
    return windows, window_starts, window_ends


# -----------------------------------------------------------------------------
# Classic pattern helpers
# -----------------------------------------------------------------------------
def _direction_label(open_arr: np.ndarray, close_arr: np.ndarray) -> np.ndarray:
    diff = np.sign(close_arr - open_arr)
    out = np.where(diff > 0, "UP", np.where(diff < 0, "DOWN", "FLAT"))
    return out


def _shape_label(opens: float, highs: float, lows: float, closes: float) -> str:
    body = closes - opens
    range_ = highs - lows + 1e-9
    body_ratio = abs(body) / range_
    if body_ratio < 0.1:
        return "DOJI"
    if body_ratio > 0.6:
        return "MARUBOZU_UP" if body > 0 else "MARUBOZU_DOWN"
    return "BULL" if body > 0 else "BEAR"


def _window_feature_bucket(window: np.ndarray) -> str:
    closes = window[:, 3]
    vols = window[:, 4]
    trend = closes[-1] / closes[0] - 1
    vol_ratio = vols[-1] / (np.median(vols) + 1e-9)
    range_pct = (window[:, 1] - window[:, 2]).mean() / (window[:, 0] + 1e-9).mean()

    trend_bucket = "TREND_UP" if trend > 0.01 else "TREND_DOWN" if trend < -0.01 else "TREND_FLAT"
    vol_bucket = "VOL_HIGH" if vol_ratio > 1.5 else "VOL_LOW" if vol_ratio < 0.7 else "VOL_NORMAL"
    range_bucket = "RANGE_WIDE" if range_pct > 0.01 else "RANGE_TIGHT"
    return f"{trend_bucket}|{vol_bucket}|{range_bucket}"


def _stability(win_mask: np.ndarray, win_targets: np.ndarray) -> float:
    """Compute stability as 1 - std of block win rates (3 blocks)."""
    n = len(win_mask)
    if n == 0:
        return float("nan")
    blocks = np.array_split(np.where(win_mask)[0], 3)
    rates = []
    for blk in blocks:
        if len(blk) == 0:
            continue
        t = win_targets[blk]
        pos = np.sum(t == "UP")
        neg = np.sum(t == "DOWN")
        eff = pos + neg
        if eff == 0:
            continue
        rates.append(pos / eff)
    if not rates:
        return float("nan")
    return 1.0 - float(np.std(rates))


def mine_classic_patterns_for_timeframe(
    df: pd.DataFrame,
    timeframe: str,
    window_sizes: Sequence[int],
    min_support: int = 25,
) -> Tuple[pd.DataFrame, Dict[int, Dict[str, List[int]]], Dict[int, np.ndarray]]:
    """
    Mine basic Level-1 patterns:
      - directional sequences
      - candle-shape sequences
      - simple feature-bucket rules
    Returns:
      patterns_df, pattern_index_map, window_targets_map
        pattern_index_map[window_size] -> dict mapping pattern_def -> list of window indices
        window_targets_map[window_size] -> array of target labels for each window
    """
    rows: List[Dict[str, Any]] = []
    pattern_index_map: Dict[int, Dict[str, List[int]]] = {}
    window_targets_map: Dict[int, np.ndarray] = {}

    df_sorted = df.sort_values("open_time").reset_index(drop=True)
    created = datetime.utcnow().isoformat()

    for w in window_sizes:
        windows, starts, ends = build_sliding_windows(df_sorted, window_size=w)
        n_windows = len(windows)
        if n_windows == 0:
            continue

        opens = df_sorted["open"].to_numpy(dtype=float)
        closes = df_sorted["close"].to_numpy(dtype=float)
        dir_labels = _direction_label(opens, closes)

        next_labels = dir_labels[w : w + n_windows]  # target is candle after window
        window_targets_map[w] = next_labels

        # sequences
        seq_map: Dict[str, List[int]] = {}
        shape_map: Dict[str, List[int]] = {}
        feat_map: Dict[str, List[int]] = {}

        baseline_pos = np.sum(next_labels == "UP")
        baseline_neg = np.sum(next_labels == "DOWN")
        baseline_eff = baseline_pos + baseline_neg
        baseline_rate = baseline_pos / baseline_eff if baseline_eff > 0 else 0.0

        for idx in range(n_windows):
            win = windows[idx]
            seq = tuple(dir_labels[idx : idx + w])
            seq_key = "|".join(seq)
            seq_map.setdefault(seq_key, []).append(idx)

            sh = tuple(
                _shape_label(*win[i, :4]) for i in range(w)
            )
            sh_key = "|".join(sh)
            shape_map.setdefault(sh_key, []).append(idx)

            feat_key = _window_feature_bucket(win)
            feat_map.setdefault(feat_key, []).append(idx)

        def _record(pattern_type: str, mapping: Dict[str, List[int]]) -> None:
            for key, idx_list in mapping.items():
                support = len(idx_list)
                if support < min_support:
                    continue
                t = next_labels[idx_list]
                pos = np.sum(t == "UP")
                neg = np.sum(t == "DOWN")
                eff = pos + neg
                if eff == 0:
                    continue
                win_rate = pos / eff
                lift = win_rate / baseline_rate if baseline_rate > 0 else float("nan")
                stab = _stability(np.array(idx_list), next_labels)
                rows.append(
                    {
                        "timeframe": timeframe,
                        "window_size": w,
                        "pattern_type": pattern_type,
                        "definition": key,
                        "target": "next_direction",
                        "support": int(support),
                        "lift": float(lift),
                        "stability": float(stab),
                        "notes": f"win_rate={win_rate:.3f}; baseline={baseline_rate:.3f}",
                        "created_at": created,
                    }
                )

        _record("sequence", seq_map)
        _record("candle_shape", shape_map)
        _record("feature_rule", feat_map)

        pattern_index_map[w] = {
            **{f"sequence::{k}": v for k, v in seq_map.items()},
            **{f"candle_shape::{k}": v for k, v in shape_map.items()},
            **{f"feature_rule::{k}": v for k, v in feat_map.items()},
        }

        print(f"[classic] {timeframe} w={w}: patterns={len(pattern_index_map[w])}, windows={n_windows}")

    return pd.DataFrame(rows), pattern_index_map, window_targets_map


# -----------------------------------------------------------------------------
# Embedding model (PCA via SVD)
# -----------------------------------------------------------------------------
def _window_feature_matrix(windows: np.ndarray) -> np.ndarray:
    """Convert window tensor (n, w, 5) into flattened, normalized feature matrix."""
    if windows.size == 0:
        return np.empty((0, 0))
    n, w, _ = windows.shape
    close_ref = windows[:, 0:1, 3:4]  # shape (n,1,1) using first close as anchor
    close_ref = np.where(close_ref == 0, 1.0, close_ref)

    rel_price = windows[:, :, :4] / close_ref - 1.0
    body = (windows[:, :, 3] - windows[:, :, 0]) / (windows[:, :, 0] + 1e-9)
    range_ = (windows[:, :, 1] - windows[:, :, 2]) / (windows[:, :, 0] + 1e-9)
    vol = np.log1p(windows[:, :, 4])
    vol = vol - vol.mean(axis=1, keepdims=True)

    feats = np.concatenate(
        [
            rel_price.reshape(n, w * 4),
            body,
            range_,
            vol,
        ],
        axis=1,
    )
    return feats


def train_window_embedding_model(
    windows: np.ndarray,
    embedding_dim: int = EMBED_DIM,
    max_train: int = MAX_TRAIN_WINDOWS,
) -> Dict[str, np.ndarray]:
    """
    Train a lightweight embedding model using PCA (SVD) on window features.
    Returns dict with mean and components.
    """
    feat = _window_feature_matrix(windows)
    if feat.size == 0:
        return {"mean": np.array([]), "components": np.array([[]])}

    if feat.shape[0] > max_train:
        rng = np.random.default_rng(42)
        idx = rng.choice(feat.shape[0], size=max_train, replace=False)
        feat_train = feat[idx]
    else:
        feat_train = feat

    mean = feat_train.mean(axis=0, keepdims=True)
    centered = feat_train - mean
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    k = min(embedding_dim, vt.shape[0])
    components = vt[:k]
    return {"mean": mean, "components": components}


def compute_window_embeddings(model: Dict[str, np.ndarray], windows: np.ndarray) -> np.ndarray:
    feat = _window_feature_matrix(windows)
    if feat.size == 0 or model.get("components", np.array([])).size == 0:
        return np.empty((len(windows), 0))
    mean = model["mean"]
    comps = model["components"]
    centered = feat - mean
    return centered @ comps.T


# -----------------------------------------------------------------------------
# Pattern embedding aggregation
# -----------------------------------------------------------------------------
def _aggregate_pattern_embeddings(
    embeddings: np.ndarray,
    pattern_index_map: Dict[str, List[int]],
) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {}
    for key, idx_list in pattern_index_map.items():
        if not idx_list:
            continue
        emb = embeddings[idx_list]
        vec = emb.mean(axis=0).astype(float)
        out[key] = vec.tolist()
    return out


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
def _load_raw(timeframe: str) -> pd.DataFrame:
    path = RAW_MAP[timeframe]
    if not path.exists():
        raise FileNotFoundError(f"Missing raw parquet for timeframe {timeframe}: {path}")
    df = pd.read_parquet(path)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df = df.sort_values("open_time").reset_index(drop=True)
    return df


def _save_window_embeddings(
    timeframe: str,
    window_size: int,
    starts: List[pd.Timestamp],
    ends: List[pd.Timestamp],
    embeddings: np.ndarray,
    collector: List[Dict[str, Any]],
) -> None:
    for i in range(len(embeddings)):
        collector.append(
            {
                "timeframe": timeframe,
                "window_size": window_size,
                "window_start_ts": starts[i],
                "window_end_ts": ends[i],
                "embedding": embeddings[i].astype(float).tolist(),
            }
        )


def run_advanced_level1_mining_4h5m(
    window_sizes: Sequence[int] = tuple(range(2, 12)),
    min_support: int = 25,
) -> None:
    DATA_DIR.mkdir(exist_ok=True)

    for timeframe in ("4h", "5m"):
        print(f"[run] timeframe={timeframe}")
        df = _load_raw(timeframe)
        patterns_all: List[pd.DataFrame] = []
        patterns_with_emb: List[Dict[str, Any]] = []
        window_emb_rows: List[Dict[str, Any]] = []

        classic_df, pattern_index_map_by_w, window_targets_map = mine_classic_patterns_for_timeframe(
            df, timeframe=timeframe, window_sizes=window_sizes, min_support=min_support
        )
        patterns_all.append(classic_df)

        for w in window_sizes:
            windows, starts, ends = build_sliding_windows(df, window_size=w)
            if len(windows) == 0:
                continue

            model = train_window_embedding_model(windows)
            emb = compute_window_embeddings(model, windows)
            _save_window_embeddings(timeframe, w, starts, ends, emb, window_emb_rows)

            pattern_index_map = pattern_index_map_by_w.get(w, {})
            pattern_emb_map = _aggregate_pattern_embeddings(emb, pattern_index_map)

            for pat_key, vec in pattern_emb_map.items():
                ptype, definition = pat_key.split("::", 1)
                patterns_with_emb.append(
                    {
                        "timeframe": timeframe,
                        "window_size": w,
                        "pattern_type": ptype,
                        "definition": definition,
                        "embedding": vec,
                    }
                )

        # Merge classic stats with embeddings
        pat_df = pd.concat(patterns_all, ignore_index=True) if patterns_all else pd.DataFrame()
        pat_emb_df = pd.DataFrame(patterns_with_emb)

        if not pat_emb_df.empty and not pat_df.empty:
            merged = pat_df.merge(
                pat_emb_df,
                on=["timeframe", "window_size", "pattern_type", "definition"],
                how="left",
            )
        else:
            merged = pat_df.copy()

        pat_out = PATTERN_OUT[timeframe]
        pat_emb_out = PATTERN_EMB_OUT[timeframe]
        pat_df.to_parquet(pat_out, index=False)
        merged.to_parquet(pat_emb_out, index=False)

        if window_emb_rows:
            win_df = pd.DataFrame(window_emb_rows)
            win_out = WINDOW_EMB_OUT[timeframe]
            win_df.to_parquet(win_out, index=False)
            print(f"[save] window embeddings {timeframe}: {win_df.shape} -> {win_out}")

        print(f"[save] patterns {timeframe}: {pat_df.shape} -> {pat_out}")
        print(f"[save] patterns+emb {timeframe}: {merged.shape} -> {pat_emb_out}")

        # Log basics
        if not pat_df.empty:
            by_type = pat_df.groupby(["pattern_type", "window_size"]).size().reset_index(name="n")
            print(f"[stats] pattern counts:\n{by_type.head()}")
            top = pat_df.sort_values("lift", ascending=False).head(5)
            print(f"[stats] top patterns by lift:\n{top[['pattern_type','window_size','definition','support','lift']].head()}")

    # Final summaries
    for tf in ("4h", "5m"):
        for path in (PATTERN_OUT[tf], PATTERN_EMB_OUT[tf], WINDOW_EMB_OUT[tf]):
            if path.exists():
                df_tmp = pd.read_parquet(path)
                print(f"[summary] {path.name}: shape={df_tmp.shape}")
                if "embedding" in df_tmp.columns:
                    print(df_tmp.head(2))

    print(
        "Advanced Phase 2 completed:\n"
        "- Level-1 patterns mined (classic + embeddings) for 4h and 5m, k=2..11\n"
        "- Embedding tables generated for windows and patterns."
    )


if __name__ == "__main__":
    run_advanced_level1_mining_4h5m()
