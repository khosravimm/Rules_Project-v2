from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd

from api.services import data_access as da


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


__all__ = ["fetch_pattern_hits", "fetch_pattern_meta"]
