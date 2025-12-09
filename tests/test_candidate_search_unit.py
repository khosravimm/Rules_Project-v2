import numpy as np
import pandas as pd

from api.services import candidate_search as cs


def _dummy_features():
    times = pd.date_range("2023-01-01", periods=24, freq="4H", tz="UTC")
    return pd.DataFrame(
        {
            "open_time": times,
            "open": np.linspace(100, 130, len(times)),
            "high": np.linspace(101, 132, len(times)),
            "low": np.linspace(99, 128, len(times)),
            "close": np.linspace(100.5, 131.5, len(times)),
            "volume": np.linspace(1000, 2000, len(times)),
            "BODY_PCT": np.random.random(len(times)),
            "UPPER_WICK_PCT": np.random.random(len(times)),
            "LOWER_WICK_PCT": np.random.random(len(times)),
            "RANGE_PCT": np.random.random(len(times)),
            "RET_4H": np.random.normal(scale=0.01, size=len(times)),
        }
    )


def test_search_similar_windows(monkeypatch):
    df = _dummy_features()
    monkeypatch.setattr(cs, "load_feature_frame", lambda timeframe: df.copy())
    start = df["open_time"].iloc[2]
    end = df["open_time"].iloc[5]
    summary, occurrences = cs.search_similar_windows("4h", start, end, max_candidates=5, search_cap=10)
    assert summary["approx_support"] > 0
    assert summary["direction_hint"] in {"up", "down", "flat"}
    assert len(occurrences) > 0
    assert all(o.similarity is not None for o in occurrences)
