import pandas as pd
import yaml

from api.services import data_access as da


def test_append_pattern_to_kb(monkeypatch, tmp_path):
    kb_path = tmp_path / "patterns.yaml"
    monkeypatch.setattr(da, "PATTERN_KB_PATH", kb_path)
    entry = {
        "id": "pbk_4h_sequence_test",
        "symbol": "BTCUSDT_PERP",
        "timeframe": "4h",
        "pattern_type": "sequence",
        "name": "Test pattern",
        "description": "unit test pattern",
    }
    da.append_pattern_to_kb(entry)
    loaded = yaml.safe_load(kb_path.read_text("utf-8"))
    assert loaded["patterns"][0]["id"] == entry["id"]
    assert loaded["meta"]["version"].startswith("v1.0.")
    assert "updated_at" in loaded["meta"]


def test_normalize_hits_dataframe_strength_filter():
    hits = pd.DataFrame(
        {
            "pattern_id": ["p1", "p2"],
            "pattern_type": ["sequence", "feature_rule"],
            "timeframe": ["4h", "4h"],
            "x0": [da._to_utc("2023-01-01T00:00:00Z"), da._to_utc("2023-01-02T00:00:00Z")],
            "x1": [da._to_utc("2023-01-01T04:00:00Z"), da._to_utc("2023-01-02T04:00:00Z")],
            "answer_time": [da._to_utc("2023-01-01T04:00:00Z"), da._to_utc("2023-01-02T04:00:00Z")],
            "strength": ["strong", "weak"],
        }
    )
    filtered = da.normalize_hits_dataframe(
        timeframe="4h",
        df_hits=hits,
        start=None,
        end=None,
        pattern_type=None,
        pattern_id=None,
        direction=None,
        strength_level="strong",
    )
    assert len(filtered) == 1
    assert filtered.iloc[0]["pattern_id"] == "p1"
