from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from api.services.data_access import _isoformat, load_feature_frame


FeatureConfig = {
    "4h": ["RET_4H", "BODY_PCT", "UPPER_WICK_PCT", "LOWER_WICK_PCT", "RANGE_PCT", "volume"],
    "5m": ["RET_5M", "BODY_PCT", "UPPER_WICK_PCT", "LOWER_WICK_PCT", "RANGE_PCT", "volume"],
}


@dataclass
class CandidateOccurrence:
    start_ts: str
    end_ts: str
    entry_candle_ts: str
    label_next_dir: Optional[str]
    pnl_rr: Optional[float]
    similarity: float


def _normalize_features(df: pd.DataFrame, cols: List[str]) -> np.ndarray:
    arr = df[cols].copy()
    for c in cols:
        if c not in arr:
            arr[c] = 0.0
    arr = arr[cols]
    arr = arr.astype(float)
    arr = arr.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    values = arr.to_numpy()
    mean = values.mean(axis=0)
    std = values.std(axis=0)
    std[std == 0] = 1.0
    normalized = (values - mean) / std
    return normalized


def _window_similarity(template: np.ndarray, other: np.ndarray) -> float:
    denom = float(np.linalg.norm(template) * np.linalg.norm(other))
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(template, other) / denom)


def _direction_from_returns(rets: np.ndarray) -> str:
    s = float(np.nansum(np.sign(rets)))
    if s > 0:
        return "up"
    if s < 0:
        return "down"
    return "flat"


def search_similar_windows(
    timeframe: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    max_candidates: int = 50,
    search_cap: Optional[int] = None,
) -> Tuple[Dict[str, Any], List[CandidateOccurrence]]:
    """Search for similar windows in history using cosine similarity on features."""
    df = load_feature_frame(timeframe)
    df = df.sort_values("open_time").reset_index(drop=True)
    feature_cols = FeatureConfig.get(timeframe, [])
    if not feature_cols:
        raise ValueError(f"No feature configuration for timeframe {timeframe}")

    # ensure required return column exists
    ret_col = "RET_4H" if timeframe == "4h" else "RET_5M"
    if ret_col not in df.columns:
        # compute simple log return
        df[ret_col] = np.log(df["close"] / df["open"])

    selected = df[(df["open_time"] >= start_ts) & (df["open_time"] <= end_ts)]
    if selected.empty:
        raise ValueError("Selected window has no candles")
    template_len = len(selected)
    normalized_all = _normalize_features(df, feature_cols)
    template_norm = _normalize_features(selected, feature_cols).reshape(-1)
    if template_norm.size == 0:
        raise ValueError("Template window has no feature values")

    occurrences: List[CandidateOccurrence] = []
    rets = df[ret_col].to_numpy()

    total_windows = len(df) - template_len + 1
    if total_windows <= 0:
        raise ValueError("Not enough history to search for candidates")
    # Optional cap for very long 5m history
    start_index = 0
    end_index = len(df) - template_len + 1
    if search_cap is not None and total_windows > search_cap:
        start_index = end_index - search_cap

    for i in range(start_index, end_index):
        window_vec = normalized_all[i : i + template_len].reshape(-1)
        sim = _window_similarity(template_norm, window_vec)
        entry_idx = i + template_len - 1
        next_idx = entry_idx + 1 if entry_idx + 1 < len(df) else entry_idx
        future_ret = rets[next_idx] if next_idx < len(rets) else np.nan
        if np.isnan(future_ret):
            label_next = None
        elif future_ret > 0:
            label_next = "up"
        elif future_ret < 0:
            label_next = "down"
        else:
            label_next = "flat"

        entry_open = float(df["open"].iloc[entry_idx])
        entry_close = float(df["close"].iloc[entry_idx])
        exit_close = float(df["close"].iloc[next_idx]) if next_idx < len(df) else entry_close
        rr_denom = abs(entry_close - entry_open)
        pnl_rr = None
        if rr_denom > 0:
            pnl_rr = (exit_close - entry_close) / rr_denom

        occ = CandidateOccurrence(
            start_ts=_isoformat(df["open_time"].iloc[i]),
            end_ts=_isoformat(df["open_time"].iloc[i + template_len - 1]),
            entry_candle_ts=_isoformat(df["open_time"].iloc[entry_idx]),
            label_next_dir=label_next,
            pnl_rr=float(pnl_rr) if pnl_rr is not None else None,
            similarity=sim,
        )
        occurrences.append(occ)

    occurrences.sort(key=lambda x: x.similarity, reverse=True)
    occurrences = occurrences[:max_candidates]

    dir_hint = _direction_from_returns(selected[ret_col].to_numpy())
    winrate = None
    labels = [o.label_next_dir for o in occurrences if o.label_next_dir]
    if labels:
        wins = sum(1 for l in labels if l == "up")
        winrate = wins / len(labels) if labels else None

    summary = {
        "symbol": "BTCUSDT_PERP",
        "timeframe": timeframe,
        "num_candles": template_len,
        "direction_hint": dir_hint,
        "approx_support": len(occurrences),
        "approx_winrate": winrate,
    }
    return summary, occurrences


__all__ = ["search_similar_windows", "CandidateOccurrence"]

