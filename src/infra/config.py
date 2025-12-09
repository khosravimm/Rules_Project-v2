"""Central configuration loader for PrisonBreaker/Pattern Lab backend."""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# Base directories (can be overridden via environment)
DATA_DIR = Path(os.getenv("DATA_DIR", REPO_ROOT / "data")).expanduser()
KB_DIR = Path(os.getenv("KB_DIR", REPO_ROOT / "project" / "KNOWLEDGE_BASE")).expanduser()
PROJECT_DIR = Path(os.getenv("PROJECT_DIR", REPO_ROOT / "project")).expanduser()

# API runtime options
API_PORT = int(os.getenv("API_PORT", "8000"))

# Defaults
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "BTCUSDT_PERP")
SUPPORTED_TIMEFRAMES = {"4h", "5m"}
TIMEFRAME_SECONDS = {
    "4h": 4 * 3600,
    "5m": 5 * 60,
}

# Canonical files (relative to DATA_DIR / KB_DIR)
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
PATTERN_KB_PATH = KB_DIR / "patterns" / "patterns.yaml"
MASTER_KNOWLEDGE_PATH = PROJECT_DIR / "MASTER_KNOWLEDGE.yaml"

__all__ = [
    "API_PORT",
    "CANDLE_FILES",
    "DATA_DIR",
    "DEFAULT_SYMBOL",
    "FEATURE_FILES",
    "KB_DIR",
    "MASTER_KNOWLEDGE_PATH",
    "PATTERN_FAMILY_FILE",
    "PATTERN_HIT_FILES",
    "PATTERN_INVENTORY_FILE",
    "PATTERN_KB_PATH",
    "PROJECT_DIR",
    "REPO_ROOT",
    "SUPPORTED_TIMEFRAMES",
    "TIMEFRAME_SECONDS",
]
