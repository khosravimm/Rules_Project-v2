from pathlib import Path
from textwrap import dedent

import pytest

from rules_kb.loader import load_knowledge, load_master_knowledge
from rules_kb.models import KnowledgeValidationError


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_load_existing_knowledge():
    kb_path = REPO_ROOT / "kb" / "btcusdt_4h_knowledge.yaml"
    kb = load_knowledge(kb_path)
    assert kb.meta.symbol == "BTCUSDT"
    assert kb.meta.market == "BTCUSDT_PERP"


def test_load_master_knowledge():
    master_path = REPO_ROOT / "project" / "MASTER_KNOWLEDGE.yaml"
    master = load_master_knowledge(master_path)
    assert master.project_scope.market_primary == "BTCUSDT_PERP"
    assert "4h" in master.project_scope.timeframes_core


def test_invalid_pattern_dataset_reference(tmp_path: Path):
    faulty_path = tmp_path / "faulty.yaml"
    faulty_path.write_text(
        dedent(
            """
            meta:
              kb_version: "0.0.1"
              schema_version: "0.1.0"
              project_codename: "Test"
              symbol: "TEST"
              market: "TEST_PERP"
            datasets:
              - id: "ds1"
                symbol: "TEST"
                market: "TEST_PERP"
                timeframe: "4h"
                source: ["demo"]
                date_range:
                  start: "2024-01-01"
                  end: "2024-02-01"
                n_candles: 10
                file_path: "data/test.parquet"
            features: []
            clusters: []
            patterns:
              - id: "p1"
                name: "Bad reference"
                description: "pattern references missing dataset"
                window_length: 3
                timeframe: "4h"
                type: "forward"
                conditions:
                  - feature: "A"
                    operator: ">"
                    value: 0
                target: "T"
                dataset_used: "unknown_ds"
                status: "active"
                tags: []
            trading_rules: []
            rule_relations: []
            cross_market_patterns: []
            market_relations: []
            backtests: []
            performance_over_time: []
            status_history: []
            """
        ).strip()
    )

    with pytest.raises(KnowledgeValidationError):
        load_knowledge(faulty_path)


def test_invalid_enum_values(tmp_path: Path):
    faulty_path = tmp_path / "faulty_enum.yaml"
    faulty_path.write_text(
        dedent(
            """
            meta:
              kb_version: "0.0.1"
              schema_version: "0.1.0"
              project_codename: "Test"
              symbol: "TEST"
              market: "TEST_PERP"
            datasets:
              - id: "ds1"
                symbol: "TEST"
                market: "TEST_PERP"
                timeframe: "4h"
                source: ["demo"]
                date_range:
                  start: "2024-01-01"
                  end: "2024-02-01"
                n_candles: 10
                file_path: "data/test.parquet"
            features: []
            clusters: []
            patterns:
              - id: "p1"
                name: "Bad enum"
                description: "pattern with invalid status and type"
                window_length: 3
                timeframe: "4h"
                type: "unknown_type"
                conditions:
                  - feature: "A"
                    operator: ">"
                    value: 0
                target: "T"
                dataset_used: "ds1"
                status: "not_a_status"
                tags: []
            trading_rules:
              - id: "r1"
                name: "Rule with bad direction"
                description: "invalid direction"
                symbol: "TEST"
                direction: "sideways"
                entry:
                  pattern_refs: ["p1"]
                  extra_conditions: []
                exit:
                  tp_sl:
                    tp_multiple: 1.0
                    sl_multiple: 1.0
                    tstop_n_bars: 2
                risk:
                  max_leverage: 5
                  position_size_factor: 0.5
                dataset_used: "ds1"
                status: "candidate"
            rule_relations: []
            cross_market_patterns: []
            market_relations: []
            backtests: []
            performance_over_time: []
            status_history: []
            """
        ).strip()
    )

    with pytest.raises(KnowledgeValidationError):
        load_knowledge(faulty_path)
