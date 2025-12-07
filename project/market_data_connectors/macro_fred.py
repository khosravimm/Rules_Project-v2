from __future__ import annotations

import os
from typing import Dict

import pandas as pd

from .schema import _standardize_df


def load_macro_series(series_id: str) -> pd.DataFrame:
    """
    Load macroeconomic series via FRED API (fredapi).
    """
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise EnvironmentError("Set FRED_API_KEY in environment to use FRED.")

    try:
        from fredapi import Fred  # type: ignore
    except ImportError as exc:
        raise ImportError("fredapi is required for load_macro_series. Install with `pip install fredapi`.") from exc

    fred = Fred(api_key=api_key)
    series = fred.get_series(series_id)
    df = pd.DataFrame(series, columns=["value"])
    df.index = pd.to_datetime(df.index, utc=True)
    meta: Dict = {"series_id": series_id}
    return _standardize_df(df, source="fred", metadata=meta)
