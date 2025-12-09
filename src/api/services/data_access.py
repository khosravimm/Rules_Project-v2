from __future__ import annotations

import math
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
import yaml

from api.config import (
    CANDLE_FILES,
    DEFAULT_SYMBOL,
    FEATURE_FILES,
    PATTERN_HIT_FILES,
    PATTERN_INVENTORY_FILE,
    PATTERN_KB_PATH,
    SUPPORTED_TIMEFRAMES,
)


def _to_utc(ts: Any) -> pd.Timestamp:
    """Convert a timestamp-like object to UTC pandas Timestamp."""
    if ts is None or (isinstance(ts, float) and math.isnan(ts)):
        return pd.NaT
    t = pd.to_datetime(ts, utc=True, errors="coerce")
    return t


def _isoformat(ts: pd.Timestamp | datetime | None) -> Optional[str]:
    if ts is None or pd.isna(ts):
        return None
    if isinstance(ts, pd.Timestamp):
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return ts.isoformat().replace("+00:00", "Z")
    return datetime.fromisoformat(str(ts)).astimezone().isoformat()


# ---------------------------------------------------------------------------
# Data frame loaders (cached)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=4)
def load_feature_frame(timeframe: str) -> pd.DataFrame:
    """Load feature-enriched OHLCV frame for the timeframe."""
    if timeframe not in FEATURE_FILES:
        raise ValueError(f"Unsupported timeframe {timeframe}")
    path = FEATURE_FILES[timeframe]
    if not path.exists():
        raise FileNotFoundError(f"Feature parquet not found: {path}")
    df = pd.read_parquet(path)
    if "open_time" not in df.columns:
        raise RuntimeError(f"open_time column missing in {path}")
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True, errors="coerce")
    df = df.dropna(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
    return df


@lru_cache(maxsize=4)
def load_raw_candles(timeframe: str) -> pd.DataFrame:
    """Load raw OHLCV frame for the timeframe."""
    if timeframe not in CANDLE_FILES:
        raise ValueError(f"Unsupported timeframe {timeframe}")
    path = CANDLE_FILES[timeframe]
    if not path.exists():
        raise FileNotFoundError(f"Candle parquet not found: {path}")
    df = pd.read_parquet(path)
    if "open_time" not in df.columns:
        raise RuntimeError(f"open_time column missing in {path}")
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True, errors="coerce")
    df = df.dropna(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
    return df


def load_candles_between(
    timeframe: str,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
) -> pd.DataFrame:
    """Return OHLCV candles within [start, end] from local data."""
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe '{timeframe}'")

    df: Optional[pd.DataFrame] = None
    if timeframe in FEATURE_FILES and FEATURE_FILES[timeframe].exists():
        df = load_feature_frame(timeframe)[
            ["open_time", "open", "high", "low", "close", "volume"]
        ].copy()
    elif timeframe in CANDLE_FILES and CANDLE_FILES[timeframe].exists():
        df = load_raw_candles(timeframe)[
            ["open_time", "open", "high", "low", "close", "volume"]
        ].copy()

    if df is None:
        return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume"])

    if start is not None:
        df = df[df["open_time"] >= start]
    if end is not None:
        df = df[df["open_time"] <= end]
    return df.sort_values("open_time").reset_index(drop=True)


@lru_cache(maxsize=4)
def load_pattern_hits_frame(timeframe: str) -> pd.DataFrame:
    """Load pattern hits table for timeframe with normalized timestamps."""
    if timeframe not in PATTERN_HIT_FILES:
        raise ValueError(f"Unsupported timeframe '{timeframe}'")
    path = PATTERN_HIT_FILES[timeframe]
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
    except Exception:
        # corrupted or placeholder parquet
        return pd.DataFrame()
    for col in ("answer_time", "start_time", "end_time"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    df["x0"] = pd.DataFrame({"a": df.get("start_time"), "b": df.get("end_time")}).min(axis=1)
    df["x1"] = pd.DataFrame({"a": df.get("start_time"), "b": df.get("end_time")}).max(axis=1)
    df = df.dropna(subset=["x0", "x1"])
    return df.sort_values("answer_time").reset_index(drop=True)


@lru_cache(maxsize=2)
def load_pattern_inventory(timeframe: Optional[str] = None) -> pd.DataFrame:
    """Load pattern inventory table (all timeframes) and optionally filter."""
    if not PATTERN_INVENTORY_FILE.exists():
        return pd.DataFrame()
    df = pd.read_parquet(PATTERN_INVENTORY_FILE)
    if timeframe:
        df = df[df["timeframe"] == timeframe]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pattern KB helpers
# ---------------------------------------------------------------------------
def load_kb_patterns() -> Dict[str, Any]:
    """Return the patterns KB structure (meta + patterns list)."""
    if not PATTERN_KB_PATH.exists():
        return {"meta": {"version": "v1.0.0"}, "patterns": []}
    with PATTERN_KB_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "patterns" not in data or data["patterns"] is None:
        data["patterns"] = []
    return data


def _bump_version(version: Optional[str]) -> str:
    if not version:
        return "v1.0.0"
    prefix = version.lstrip("v")
    parts = prefix.split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        major, minor, patch = [int(p) for p in parts[:3]]
        patch += 1
        return f"v{major}.{minor}.{patch}"
    except Exception:
        return "v1.0.0"


def append_pattern_to_kb(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Append a pattern entry to patterns.yaml and return persisted object."""
    kb = load_kb_patterns()
    patterns: List[Dict[str, Any]] = list(kb.get("patterns", []))
    patterns.append(entry)

    meta = kb.get("meta", {}) or {}
    meta["updated_at"] = datetime.utcnow().isoformat() + "Z"
    meta["version"] = _bump_version(meta.get("version"))

    kb["meta"] = meta
    kb["patterns"] = patterns

    PATTERN_KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PATTERN_KB_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(kb, handle, sort_keys=False, allow_unicode=True)
    return entry


# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------
def derive_direction_from_candles(
    answer_time: pd.Timestamp,
    candles: pd.DataFrame,
) -> Optional[str]:
    """Infer direction from the answer candle close/open."""
    if candles.empty or pd.isna(answer_time):
        return None
    row = candles[candles["open_time"] == answer_time]
    if row.empty:
        return None
    r = float(row.iloc[0]["close"] - row.iloc[0]["open"])
    if r > 0:
        return "long"
    if r < 0:
        return "short"
    return "neutral"


def normalize_hits_dataframe(
    timeframe: str,
    df_hits: pd.DataFrame,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    pattern_type: Optional[str],
    pattern_id: Optional[str],
    direction: Optional[str],
) -> pd.DataFrame:
    """Filter and normalize pattern hits dataframe."""
    if df_hits.empty:
        return df_hits

    df = df_hits.copy()
    if "timeframe" in df.columns:
        df = df[df["timeframe"] == timeframe]
    if start is not None:
        df = df[df["x1"] >= start]
    if end is not None:
        df = df[df["x0"] <= end]
    if pattern_type:
        df = df[df["pattern_type"] == pattern_type]
    if pattern_id:
        df = df[df["pattern_id"] == pattern_id]
    if direction:
        # direction filtering will be applied after direction derivation
        df["_direction_filter"] = direction
    return df


def build_pattern_meta_from_hits(df_hits: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Aggregate pattern metadata from hits when KB inventory is missing."""
    meta: Dict[str, Dict[str, Any]] = {}
    if df_hits.empty:
        return meta
    grouped = df_hits.groupby("pattern_id").agg(
        pattern_type=("pattern_type", "first"),
        timeframe=("timeframe", "first"),
        support=("support", "max"),
        lift=("lift", "max"),
        stability=("stability", "max"),
        strength_level=("strength", "first"),
    )
    for pid, row in grouped.iterrows():
        meta[pid] = {
            "pattern_id": pid,
            "symbol": DEFAULT_SYMBOL,
            "timeframe_origin": row.get("timeframe"),
            "pattern_type": row.get("pattern_type"),
            "name": pid,
            "description": "",
            "tags": [],
            "strength_level": row.get("strength_level"),
            "status": "active",
            "support": row.get("support"),
            "lift": row.get("lift"),
            "stability": row.get("stability"),
        }
    return meta


def load_pattern_meta(timeframe: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Load metadata from inventory, KB, and hits; keyed by pattern_id."""
    meta: Dict[str, Dict[str, Any]] = {}

    inv = load_pattern_inventory(timeframe if timeframe else None)
    if not inv.empty:
        for row in inv.itertuples():
            pid = row.id
            meta[pid] = {
                "pattern_id": pid,
                "symbol": DEFAULT_SYMBOL,
                "timeframe_origin": getattr(row, "timeframe", timeframe),
                "pattern_type": row.pattern_type,
                "name": getattr(row, "definition", pid),
                "description": getattr(row, "definition", ""),
                "tags": [],
                "strength_level": getattr(row, "strength_level", None),
                "status": "active",
                "support": getattr(row, "support", None),
                "lift": getattr(row, "lift", None),
                "stability": getattr(row, "stability", None),
            }

    kb = load_kb_patterns()
    for pat in kb.get("patterns", []):
        pid = pat.get("id") or pat.get("pattern_id")
        if not pid:
            continue
        entry = meta.get(pid, {})
        entry.update(
            {
                "pattern_id": pid,
                "symbol": pat.get("symbol", DEFAULT_SYMBOL),
                "timeframe_origin": pat.get("timeframe") or pat.get("timeframe_origin"),
                "pattern_type": pat.get("pattern_type"),
                "name": pat.get("name", pid),
                "description": pat.get("description", ""),
                "tags": pat.get("tags", []),
                "strength_level": pat.get("rule_strength") or pat.get("strength_level"),
                "status": pat.get("status", "active"),
            }
        )
        if "support" in pat:
            entry["support"] = pat.get("support")
        if "lift" in pat:
            entry["lift"] = pat.get("lift")
        if "stability" in pat:
            entry["stability"] = pat.get("stability")
        meta[pid] = entry

    hit_frames: List[pd.DataFrame] = []
    if timeframe:
        hit_frames.append(load_pattern_hits_frame(timeframe))
    else:
        for tf in SUPPORTED_TIMEFRAMES:
            hit_frames.append(load_pattern_hits_frame(tf))
    if hit_frames:
        hits_df = pd.concat(hit_frames, ignore_index=True) if len(hit_frames) > 1 else hit_frames[0]
        meta_hits = build_pattern_meta_from_hits(hits_df)
        for pid, entry in meta_hits.items():
            if pid not in meta:
                meta[pid] = entry

    return meta


def generate_pattern_id(timeframe: str, pattern_type: str, nonce: str) -> str:
    safe_type = pattern_type.replace(" ", "_").lower()
    return f"pbk_{timeframe}_{safe_type}_{nonce}"


def ensure_iterable(value: Optional[Iterable[Any]]) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


__all__ = [
    "append_pattern_to_kb",
    "build_pattern_meta_from_hits",
    "derive_direction_from_candles",
    "ensure_iterable",
    "generate_pattern_id",
    "load_candles_between",
    "load_feature_frame",
    "load_kb_patterns",
    "load_pattern_hits_frame",
    "load_pattern_inventory",
    "load_pattern_meta",
    "normalize_hits_dataframe",
    "DEFAULT_SYMBOL",
    "_isoformat",
    "_to_utc",
]
