from pathlib import Path

from rules_kb.loader import load_master_knowledge
from rules_kb.models import KnowledgeBase
from rules_kb.query import (
    filter_patterns,
    get_patterns_by_market_timeframe,
    list_markets,
    list_timeframes,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _build_sample_kb() -> KnowledgeBase:
    """Construct a minimal in-memory knowledge base for query testing."""

    return KnowledgeBase.model_validate(
        {
            "meta": {
                "kb_version": "0.1.0",
                "schema_version": "0.1.0",
                "project_codename": "Test",
                "symbol": "BTCUSDT",
                "market": "BTCUSDT_PERP",
            },
            "datasets": [
                {
                    "id": "ds4h",
                    "symbol": "BTCUSDT",
                    "market": "BTCUSDT_PERP",
                    "timeframe": "4h",
                    "source": ["binance_futures"],
                    "date_range": {"start": "2024-01-01", "end": "2024-02-01"},
                    "n_candles": 100,
                    "file_path": "data/ds4h.parquet",
                }
            ],
            "patterns": [
                {
                    "id": "P1",
                    "name": "Shape continuation",
                    "description": "Test pattern 4h",
                    "window_length": 3,
                    "timeframe": "4h",
                    "type": "forward",
                    "conditions": [{"feature": "BODY_PCT", "operator": ">", "value": 0.4}],
                    "target": "DIR_4H_NEXT",
                    "dataset_used": "ds4h",
                    "status": "active",
                    "tags": ["shape", "momentum"],
                    "direction": "long",
                    "confidence": 0.72,
                    "regime": "bull",
                },
                {
                    "id": "P2",
                    "name": "Volatility squeeze",
                    "description": "5m pattern",
                    "window_length": 5,
                    "timeframe": "5m",
                    "type": "forward",
                    "conditions": [{"feature": "VOL_BUCKET_5M", "operator": "==", "value": "LOW"}],
                    "target": "DIR_5M_NEXT",
                    "dataset_used": "ds4h",
                    "status": "candidate",
                    "tags": ["volatility"],
                    "metadata": {"confidence": 0.65, "regime": "bear"},
                },
            ],
        }
    )


def test_get_patterns_by_market_timeframe_filters_by_dataset_market():
    kb = _build_sample_kb()
    results = get_patterns_by_market_timeframe(kb, market="BTCUSDT_PERP", timeframe="4h")
    assert [p.id for p in results] == ["P1"]


def test_filter_patterns_by_confidence_tags_and_regime():
    kb = _build_sample_kb()
    filtered = filter_patterns(
        kb=None,
        patterns=kb.patterns,
        min_conf=0.7,
        tags=["shape"],
        regime="bull",
    )
    assert [p.id for p in filtered] == ["P1"]

    bear_filtered = filter_patterns(kb=None, patterns=kb.patterns, regime="bear")
    assert [p.id for p in bear_filtered] == ["P2"]


def test_list_markets_and_timeframes_from_master():
    master = load_master_knowledge(REPO_ROOT / "project" / "MASTER_KNOWLEDGE.yaml")
    markets = list_markets(master)
    assert master.project_scope.market_primary in markets

    timeframes = list_timeframes(master, master.project_scope.market_primary)
    assert "4h" in timeframes
    assert "5m" in timeframes
