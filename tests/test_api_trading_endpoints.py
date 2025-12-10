import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.server import app
import api.services.data_access as da


@pytest.fixture()
def client_with_test_data(tmp_path):
    # Backup originals
    orig_candle_files = da.CANDLE_FILES.copy()
    orig_feature_files = da.FEATURE_FILES.copy()
    orig_pattern_hit_files = da.PATTERN_HIT_FILES.copy()

    # Build small UTC candle datasets for 4h and 5m
    times_4h = pd.date_range("2025-01-01T00:00:00Z", periods=10, freq="4H")
    candles_4h = pd.DataFrame(
        {
            "open_time": times_4h,
            "open": range(10),
            "high": [v + 1 for v in range(10)],
            "low": [v - 1 for v in range(10)],
            "close": [v + 0.5 for v in range(10)],
            "volume": [100.0 + v for v in range(10)],
        }
    )
    path_4h = tmp_path / "candles_4h.parquet"
    candles_4h.to_parquet(path_4h, index=False)

    times_5m = pd.date_range("2025-01-01T00:00:00Z", periods=30, freq="5min")
    candles_5m = pd.DataFrame(
        {
            "open_time": times_5m,
            "open": range(30),
            "high": [v + 1 for v in range(30)],
            "low": [v - 1 for v in range(30)],
            "close": [v + 0.25 for v in range(30)],
            "volume": [50.0 + v for v in range(30)],
        }
    )
    path_5m = tmp_path / "candles_5m.parquet"
    candles_5m.to_parquet(path_5m, index=False)

    # Pattern hits for filtering checks
    hits_4h = pd.DataFrame(
        [
            {
                "timeframe": "4h",
                "pattern_id": "p1",
                "pattern_type": "sequence",
                "answer_time": times_4h[3],
                "start_time": times_4h[1],
                "end_time": times_4h[3],
                "support": 10,
                "lift": 1.2,
                "stability": 0.8,
                "score": 0.5,
            },
            {
                "timeframe": "4h",
                "pattern_id": "p2",
                "pattern_type": "sequence",
                "answer_time": times_4h[7],
                "start_time": times_4h[5],
                "end_time": times_4h[7],
                "support": 12,
                "lift": 1.3,
                "stability": 0.9,
                "score": 0.6,
            },
        ]
    )
    path_hits_4h = tmp_path / "hits_4h.parquet"
    hits_4h.to_parquet(path_hits_4h, index=False)

    hits_5m = pd.DataFrame(
        [
            {
                "timeframe": "5m",
                "pattern_id": "m1",
                "pattern_type": "sequence",
                "answer_time": times_5m[10],
                "start_time": times_5m[8],
                "end_time": times_5m[10],
                "support": 20,
                "lift": 1.1,
                "stability": 0.7,
                "score": 0.4,
            }
        ]
    )
    path_hits_5m = tmp_path / "hits_5m.parquet"
    hits_5m.to_parquet(path_hits_5m, index=False)

    # Point loaders to test data and clear caches
    da.CANDLE_FILES = {"4h": path_4h, "5m": path_5m}
    da.FEATURE_FILES = {}
    da.PATTERN_HIT_FILES = {"4h": path_hits_4h, "5m": path_hits_5m}
    da.load_feature_frame.cache_clear()
    da.load_raw_candles.cache_clear()
    da.load_pattern_hits_frame.cache_clear()

    try:
        yield TestClient(app)
    finally:
        # Restore originals and clear caches
        da.CANDLE_FILES = orig_candle_files
        da.FEATURE_FILES = orig_feature_files
        da.PATTERN_HIT_FILES = orig_pattern_hit_files
        da.load_feature_frame.cache_clear()
        da.load_raw_candles.cache_clear()
        da.load_pattern_hits_frame.cache_clear()


def test_candles_start_end_filter(client_with_test_data):
    client = client_with_test_data
    start = "2025-01-01T08:00:00Z"
    end = "2025-01-01T16:00:00Z"
    resp = client.get("/api/candles", params={"timeframe": "4h", "start": start, "end": end})
    assert resp.status_code == 200
    candles = resp.json()["candles"]
    assert len(candles) == 3
    timestamps = [pd.to_datetime(c["timestamp"], utc=True) for c in candles]
    assert timestamps[0] == pd.Timestamp(start)
    assert timestamps[-1] == pd.Timestamp(end)
    assert all(ts.tz == pd.Timestamp(start).tz for ts in timestamps)


def test_candles_center_window_counts(client_with_test_data):
    client = client_with_test_data
    center = "2025-01-01T20:00:00Z"  # 6th candle (index 5)
    resp = client.get(
        "/api/candles",
        params={
            "timeframe": "4h",
            "center": center,
            "window_before": 2,
            "window_after": 1,
        },
    )
    assert resp.status_code == 200
    candles = resp.json()["candles"]
    assert len(candles) == 4  # 2 before + center + 1 after
    timestamps = [pd.to_datetime(c["timestamp"], utc=True) for c in candles]
    assert timestamps[2] == pd.Timestamp(center)
    assert timestamps[0] == pd.Timestamp("2025-01-01T12:00:00Z")
    assert timestamps[-1] == pd.Timestamp("2025-01-02T00:00:00Z")
    assert all(ts.tzinfo is not None and ts.tzinfo.utcoffset(ts) == pd.Timedelta(0) for ts in timestamps)


def test_pattern_hits_filter_by_range(client_with_test_data):
    client = client_with_test_data
    resp = client.get(
        "/api/pattern-hits",
        params={
            "timeframe": "4h",
            "start": "2025-01-01T08:00:00Z",
            "end": "2025-01-01T16:00:00Z",
        },
    )
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert len(hits) == 1
    hit_ts = pd.to_datetime(hits[0]["entry_candle_ts"], utc=True)
    assert hit_ts == pd.Timestamp("2025-01-01T12:00:00Z")
    assert hit_ts.tzinfo is not None and hit_ts.tzinfo.utcoffset(hit_ts) == pd.Timedelta(0)


def test_pattern_hits_respects_timeframe_5m(client_with_test_data):
    client = client_with_test_data
    resp = client.get("/api/pattern-hits", params={"timeframe": "5m"})
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert len(hits) == 1
    assert hits[0]["pattern_id"] == "m1"
    ts = pd.to_datetime(hits[0]["entry_candle_ts"], utc=True)
    assert ts == pd.Timestamp("2025-01-01T00:50:00Z")
    assert ts.tzinfo is not None and ts.tzinfo.utcoffset(ts) == pd.Timedelta(0)
