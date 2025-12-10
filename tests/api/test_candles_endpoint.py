import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.server import app
import api.services.data_access as da
from api.utils.time_windows import compute_time_window_around


@pytest.fixture()
def client_with_candles(tmp_path):
    orig_candle_files = da.CANDLE_FILES.copy()
    orig_feature_files = da.FEATURE_FILES.copy()

    times_4h = pd.date_range("2025-01-01T00:00:00Z", periods=10, freq="4h")
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

    da.CANDLE_FILES = {"4h": path_4h, "5m": path_5m}
    da.FEATURE_FILES = {}
    da.load_raw_candles.cache_clear()
    da.load_feature_frame.cache_clear()

    try:
        yield TestClient(app)
    finally:
        da.CANDLE_FILES = orig_candle_files
        da.FEATURE_FILES = orig_feature_files
        da.load_raw_candles.cache_clear()
        da.load_feature_frame.cache_clear()


def test_candles_start_end_utc_default(client_with_candles):
    client = client_with_candles
    start = "2025-01-01T08:00:00"
    end = "2025-01-01T16:00:00"
    resp = client.get("/api/candles", params={"timeframe": "4h", "start": start, "end": end})
    assert resp.status_code == 200
    candles = resp.json()["candles"]
    assert len(candles) == 3
    timestamps = [pd.to_datetime(c["timestamp"], utc=True) for c in candles]
    assert timestamps[0] == pd.Timestamp("2025-01-01T08:00:00Z")
    assert timestamps[-1] == pd.Timestamp("2025-01-01T16:00:00Z")


def test_candles_center_window(client_with_candles):
    client = client_with_candles
    center = "2025-01-01T20:00:00Z"
    resp = client.get(
        "/api/candles",
        params={
            "timeframe": "4h",
            "center": center,
            "before_bars": 2,
            "after_bars": 1,
        },
    )
    assert resp.status_code == 200
    candles = resp.json()["candles"]
    assert len(candles) == 4
    timestamps = [pd.to_datetime(c["timestamp"], utc=True) for c in candles]
    assert pd.Timestamp(center) in timestamps
    assert timestamps[0] == pd.Timestamp("2025-01-01T12:00:00Z")
    assert timestamps[-1] == pd.Timestamp("2025-01-02T00:00:00Z")


def test_candles_invalid_mixed_params(client_with_candles):
    client = client_with_candles
    resp = client.get(
        "/api/candles",
        params={"timeframe": "4h", "center": "2025-01-01T00:00:00Z", "start": "2025-01-01T04:00:00Z"},
    )
    assert resp.status_code == 400

    resp2 = client.get("/api/candles", params={"timeframe": "4h", "start": "2025-01-01T04:00:00Z"})
    assert resp2.status_code == 400


def test_compute_time_window_helper():
    start, end = compute_time_window_around(
        pd.Timestamp("2025-01-01T20:00:00Z").to_pydatetime(), "4h", before_bars=1, after_bars=2
    )
    assert start == pd.Timestamp("2025-01-01T16:00:00Z")
    assert end == pd.Timestamp("2025-01-02T04:00:00Z")
