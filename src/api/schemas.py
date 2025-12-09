from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Candles
# ---------------------------------------------------------------------------
class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class CandlesResponse(BaseModel):
    symbol: str
    timeframe: str
    candles: List[Candle]


# ---------------------------------------------------------------------------
# Pattern hits
# ---------------------------------------------------------------------------
class PatternHit(BaseModel):
    pattern_id: str
    pattern_type: Optional[str] = None
    direction: Optional[str] = None
    start_ts: Optional[datetime] = None
    end_ts: Optional[datetime] = None
    entry_candle_ts: Optional[datetime] = None
    accuracy: Optional[float] = None
    support: Optional[float] = None
    lift: Optional[float] = None
    stability: Optional[float] = None
    strength_level: Optional[str] = None


class PatternHitsResponse(BaseModel):
    symbol: str
    timeframe: str
    hits: List[PatternHit]


# ---------------------------------------------------------------------------
# Pattern metadata
# ---------------------------------------------------------------------------
class PatternMeta(BaseModel):
    pattern_id: str
    symbol: str
    timeframe_origin: Optional[str] = None
    pattern_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    strength_level: Optional[str] = None
    status: Optional[str] = None
    support: Optional[float] = None
    lift: Optional[float] = None
    stability: Optional[float] = None


class PatternMetaResponse(BaseModel):
    patterns: List[PatternMeta]


# ---------------------------------------------------------------------------
# Candidate search
# ---------------------------------------------------------------------------
class WindowSelection(BaseModel):
    start_ts: datetime
    end_ts: datetime


class CandidateSearchRequest(BaseModel):
    symbol: str = "BTCUSDT_PERP"
    timeframe: str
    selected_window: WindowSelection


class CandidateOccurrenceOut(BaseModel):
    start_ts: datetime
    end_ts: datetime
    entry_candle_ts: datetime
    label_next_dir: Optional[str] = None
    pnl_rr: Optional[float] = None
    similarity: float


class CandidateSummary(BaseModel):
    symbol: str
    timeframe: str
    num_candles: int
    direction_hint: Optional[str] = None
    approx_support: int
    approx_winrate: Optional[float] = None


class CandidateSearchResponse(BaseModel):
    candidate_summary: CandidateSummary
    occurrences: List[CandidateOccurrenceOut]


# ---------------------------------------------------------------------------
# Pattern creation
# ---------------------------------------------------------------------------
class CreatePatternRequest(BaseModel):
    symbol: str = "BTCUSDT_PERP"
    timeframe: str
    pattern_type: str
    base_window: WindowSelection
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    initial_strength_level: str = "weak"


class CreatePatternResponse(BaseModel):
    pattern: PatternMeta
    candidate_summary: Optional[CandidateSummary] = None


__all__ = [
    "Candle",
    "CandlesResponse",
    "PatternHit",
    "PatternHitsResponse",
    "PatternMeta",
    "PatternMetaResponse",
    "CandidateSearchRequest",
    "CandidateSearchResponse",
    "CreatePatternRequest",
    "CreatePatternResponse",
    "CandidateOccurrenceOut",
    "CandidateSummary",
    "WindowSelection",
]

