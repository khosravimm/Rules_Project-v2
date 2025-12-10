import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.server import app
import api.services.data_access as da


@pytest.fixture()
def client_with_hits(tmp_path):
    orig_candle_files = da.CANDLE_FILES.copy()
    orig_feature_files = da.FEATURE_FILES.copy()
    orig_hit_files = da.PATTERN_HIT_FILES.copy()

    times_4h = pd.date_range("2025-01-01T00:00:00Z", periods=6, freq="4h")
    candles_4h = pd.DataFrame(
        {
            "open_time": times_4h,
            "open": range(6),
            "high": [v + 1 for v in range(6)],
            "low": [v - 1 for v in range(6)],
            "close": [v + 0.5 for v in range(6)],
            "volume": [10.0 + v for v in range(6)],
        }
    )
    path_4h = tmp_path / "candles_4h.parquet"
    candles_4h.to_parquet(path_4h, index=False)

    hits_4h = pd.DataFrame(
        [
            {
                "timeframe": "4h",
                "pattern_id": "p1",
                "pattern_type": "sequence",
                "answer_time": times_4h[2],
                "start_time": times_4h[0],
                "end_time": times_4h[2],
                "support": 5,
                "lift": 1.1,
                "stability": 0.8,
                "score": 0.4,
            },
            {
                "timeframe": "4h",
                "pattern_id": "p2",
                "pattern_type": "sequence",
                "answer_time": times_4h[4],
                "start_time": times_4h[2],
                "end_time": times_4h[4],
                "support": 8,
                "lift": 1.3,
                "stability": 0.9,
                "score": 0.6,
            },
        ]
    )
    path_hits_4h = tmp_path / "hits_4h.parquet"
    hits_4h.to_parquet(path_hits_4h, index=False)

    times_5m = pd.date_range("2025-01-01T00:00:00Z", periods=10, freq="5min")
    candles_5m = pd.DataFrame(
        {
            "open_time": times_5m,
            "open": range(10),
            "high": [v + 1 for v in range(10)],
            "low": [v - 1 for v in range(10)],
            "close": [v + 0.1 for v in range(10)],
            "volume": [5.0 + v for v in range(10)],
        }
    )
    path_5m = tmp_path / "candles_5m.parquet"
    candles_5m.to_parquet(path_5m, index=False)

    hits_5m = pd.DataFrame(
        [
            {
                "timeframe": "5m",
                "pattern_id": "m1",
                "pattern_type": "sequence",
                "answer_time": times_5m[5],
                "start_time": times_5m[3],
                "end_time": times_5m[5],
                "support": 12,
                "lift": 1.05,
                "stability": 0.7,
                "score": 0.3,
            }
        ]
    )
    path_hits_5m = tmp_path / "hits_5m.parquet"
    hits_5m.to_parquet(path_hits_5m, index=False)

    da.CANDLE_FILES = {"4h": path_4h, "5m": path_5m}
    da.FEATURE_FILES = {}
    da.PATTERN_HIT_FILES = {"4h": path_hits_4h, "5m": path_hits_5m}
    da.load_raw_candles.cache_clear()
    da.load_feature_frame.cache_clear()
    da.load_pattern_hits_frame.cache_clear()

    try:
        yield TestClient(app)
    finally:
        da.CANDLE_FILES = orig_candle_files
        da.FEATURE_FILES = orig_feature_files
        da.PATTERN_HIT_FILES = orig_hit_files
        da.load_raw_candles.cache_clear()
        da.load_feature_frame.cache_clear()
        da.load_pattern_hits_frame.cache_clear()


def test_pattern_hits_without_range(client_with_hits):
    client = client_with_hits
    resp = client.get("/api/pattern-hits", params={"timeframe": "4h"})
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert len(hits) == 2
    for h in hits:
        assert "pattern_id" in h and "entry_candle_ts" in h
        assert h.get("timeframe") == "4h"


def test_pattern_hits_with_range_filter(client_with_hits):
    client = client_with_hits
    resp = client.get(
        "/api/pattern-hits",
        params={
            "timeframe": "4h",
            "start": "2025-01-01T00:00:00Z",
            "end": "2025-01-01T12:00:00Z",
        },
    )
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert len(hits) == 1
    ts = pd.to_datetime(hits[0]["entry_candle_ts"], utc=True)
    assert ts >= pd.Timestamp("2025-01-01T00:00:00Z")
    assert ts <= pd.Timestamp("2025-01-01T12:00:00Z")


def test_pattern_hits_timeframe_5m(client_with_hits):
    client = client_with_hits
    resp = client.get("/api/pattern-hits", params={"timeframe": "5m"})
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert len(hits) == 1
    assert hits[0]["pattern_id"] == "m1"
