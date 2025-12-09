from __future__ import annotations

from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
KB_DIR = REPO_ROOT / "kb"
PROJECT_DIR = REPO_ROOT / "project"

# Canonical files
CANDLE_FILES = {
    "4h": DATA_DIR / "btcusdt_4h_raw.parquet",
    "5m": DATA_DIR / "btcusdt_5m_raw.parquet",
}
FEATURE_FILES = {
    "4h": DATA_DIR / "btcusdt_4h_features.parquet",
    "5m": DATA_DIR / "btcusdt_5m_features.parquet",
}
PATTERN_HIT_FILES = {
    "4h": DATA_DIR / "pattern_hits_4h_level1.parquet",
    "5m": DATA_DIR / "pattern_hits_5m_level1.parquet",
}
PATTERN_INVENTORY_FILE = DATA_DIR / "pattern_inventory_level1_all.parquet"
PATTERN_FAMILY_FILE = DATA_DIR / "pattern_inventory_families_all.parquet"
PATTERN_KB_PATH = PROJECT_DIR / "KNOWLEDGE_BASE" / "patterns" / "patterns.yaml"
MASTER_KNOWLEDGE_PATH = PROJECT_DIR / "MASTER_KNOWLEDGE.yaml"

DEFAULT_SYMBOL = "BTCUSDT_PERP"
SUPPORTED_TIMEFRAMES = {"4h", "5m"}
TIMEFRAME_SECONDS = {
    "4h": 4 * 3600,
    "5m": 5 * 60,
}

