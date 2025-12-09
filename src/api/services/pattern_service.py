from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd

from api.services import data_access as da
from core.candles import derive_direction_from_candles


def fetch_pattern_hits(
    timeframe: str,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    pattern_type: Optional[str],
    pattern_id: Optional[str],
    direction: Optional[str],
    strength_level: Optional[str],
) -> pd.DataFrame:
    df_hits = da.load_pattern_hits_frame(timeframe)
    if df_hits.empty:
        return df_hits
    return da.normalize_hits_dataframe(
        timeframe=timeframe,
        df_hits=df_hits,
        start=start,
        end=end,
        pattern_type=pattern_type,
        pattern_id=pattern_id,
        direction=direction,
        strength_level=strength_level,
    )


def fetch_pattern_meta(timeframe: Optional[str] = None) -> Dict[str, Dict]:
    return da.load_pattern_meta(timeframe)


def compute_pattern_metrics(
    pattern_id: str,
    timeframe: Optional[str],
) -> Dict[str, Optional[float]]:
    """
    Compute lightweight predictive metrics for a pattern using existing hits and candles.
    Metrics are kept minimal to avoid heavy recompute; all sources are cached loaders.
    """
    tf = timeframe
    hits_df = da.load_pattern_hits_frame(tf) if tf else pd.concat(
        [da.load_pattern_hits_frame(t) for t in da.SUPPORTED_TIMEFRAMES], ignore_index=True
    )
    if hits_df.empty:
        return {
            "pattern_id": pattern_id,
            "timeframe": tf,
            "total_hits": 0,
            "winrate": None,
            "avg_return": None,
            "median_return": None,
            "avg_lift": None,
            "avg_score": None,
            "avg_stability": None,
        }
    hits_df = hits_df[hits_df["pattern_id"] == pattern_id]
    if tf:
        hits_df = hits_df[hits_df["timeframe"] == tf]
    if hits_df.empty:
        return {
            "pattern_id": pattern_id,
            "timeframe": tf,
            "total_hits": 0,
            "winrate": None,
            "avg_return": None,
            "median_return": None,
            "avg_lift": None,
            "avg_score": None,
            "avg_stability": None,
        }

    candle_df = da.load_candles_between(tf or hits_df["timeframe"].iloc[0], None, None)
    candle_df = candle_df.sort_values("open_time").reset_index(drop=True)
    idx_map = {ts: i for i, ts in enumerate(candle_df["open_time"])}

    rets: List[float] = []
    wins = 0
    total = 0
    for row in hits_df.itertuples():
        ans = getattr(row, "answer_time", None)
        if pd.isna(ans):
            continue
        idx = idx_map.get(ans)
        if idx is None:
            continue
        entry_close = float(candle_df.iloc[idx]["close"])
        next_idx = idx + 1 if idx + 1 < len(candle_df) else idx
        next_close = float(candle_df.iloc[next_idx]["close"])
        r = (next_close - entry_close) / entry_close if entry_close else 0.0
        rets.append(r)
        dir_hit = derive_direction_from_candles(ans, candle_df)
        if dir_hit == "long" and r > 0:
            wins += 1
        elif dir_hit == "short" and r < 0:
            wins += 1
        total += 1

    avg_return = float(pd.Series(rets).mean()) if rets else None
    median_return = float(pd.Series(rets).median()) if rets else None
    winrate = wins / total if total else None
    return {
        "pattern_id": pattern_id,
        "timeframe": tf,
        "total_hits": int(total),
        "winrate": winrate,
        "avg_return": avg_return,
        "median_return": median_return,
        "avg_lift": float(hits_df["lift"].mean()) if "lift" in hits_df else None,
        "avg_score": float(hits_df["score"].mean()) if "score" in hits_df else None,
        "avg_stability": float(hits_df["stability"].mean()) if "stability" in hits_df else None,
    }


__all__ = ["fetch_pattern_hits", "fetch_pattern_meta", "compute_pattern_metrics"]
