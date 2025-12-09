from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, HTTPException

from api.config import SUPPORTED_TIMEFRAMES
from api.schemas import (
    CandidateOccurrenceOut,
    CandidateSearchRequest,
    CandidateSearchResponse,
    CandidateSummary,
    CreatePatternRequest,
    CreatePatternResponse,
    PatternMeta,
    PatternMetaResponse,
)
from api.services.candidate_search import search_similar_windows
from api.services.data_access import (
    DEFAULT_SYMBOL,
    _to_utc,
    append_pattern_to_kb,
    ensure_iterable,
    generate_pattern_id,
    load_pattern_meta,
)

router = APIRouter()


@router.get("/api/patterns/meta", response_model=PatternMetaResponse)
def get_pattern_meta(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: Optional[str] = None,
    pattern_id: Optional[str] = None,
) -> PatternMetaResponse:
    tf = timeframe.lower() if timeframe else None
    if tf and tf not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{timeframe}'. Use one of {SUPPORTED_TIMEFRAMES}.")

    meta_map = load_pattern_meta(tf)
    patterns: List[PatternMeta] = []
    for pid, meta in meta_map.items():
        if pattern_id and pid != pattern_id:
            continue
        if tf and meta.get("timeframe_origin") and meta.get("timeframe_origin") != tf:
            continue
        patterns.append(PatternMeta.model_validate(meta))

    return PatternMetaResponse(patterns=patterns)


@router.get("/api/patterns/{pattern_id}", response_model=PatternMeta)
def get_pattern(pattern_id: str, timeframe: Optional[str] = None) -> PatternMeta:
    tf = timeframe.lower() if timeframe else None
    meta_map = load_pattern_meta(tf)
    meta = meta_map.get(pattern_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"pattern_id '{pattern_id}' not found")
    if tf and meta.get("timeframe_origin") and meta.get("timeframe_origin") != tf:
        raise HTTPException(status_code=404, detail=f"pattern_id '{pattern_id}' not found for timeframe {tf}")
    return PatternMeta.model_validate(meta)


@router.post("/api/patterns/search_candidate", response_model=CandidateSearchResponse)
def search_candidate(req: CandidateSearchRequest) -> CandidateSearchResponse:
    tf = req.timeframe.lower()
    if tf not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{req.timeframe}'.")

    start_ts = _to_utc(req.selected_window.start_ts)
    end_ts = _to_utc(req.selected_window.end_ts)
    if pd.isna(start_ts) or pd.isna(end_ts):
        raise HTTPException(status_code=400, detail="Invalid start_ts or end_ts.")
    if end_ts < start_ts:
        raise HTTPException(status_code=400, detail="end_ts must be after start_ts.")

    try:
        summary_dict, occs = search_similar_windows(
            timeframe=tf,
            start_ts=start_ts,
            end_ts=end_ts,
            max_candidates=50,
            search_cap=120000 if tf == "5m" else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"candidate search failed: {exc}")  # pragma: no cover

    summary = CandidateSummary(**summary_dict)
    occurrences = [
        CandidateOccurrenceOut(
            start_ts=pd.to_datetime(o.start_ts, utc=True).to_pydatetime(),
            end_ts=pd.to_datetime(o.end_ts, utc=True).to_pydatetime(),
            entry_candle_ts=pd.to_datetime(o.entry_candle_ts, utc=True).to_pydatetime(),
            label_next_dir=o.label_next_dir,
            pnl_rr=o.pnl_rr,
            similarity=o.similarity,
        )
        for o in occs
    ]

    return CandidateSearchResponse(candidate_summary=summary, occurrences=occurrences)


@router.post("/api/patterns/create_from_candidate", response_model=CreatePatternResponse)
def create_pattern(req: CreatePatternRequest) -> CreatePatternResponse:
    tf = req.timeframe.lower()
    if tf not in SUPPORTED_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe '{req.timeframe}'.")

    start_ts = _to_utc(req.base_window.start_ts)
    end_ts = _to_utc(req.base_window.end_ts)
    if pd.isna(start_ts) or pd.isna(end_ts):
        raise HTTPException(status_code=400, detail="Invalid base_window timestamps.")
    if end_ts < start_ts:
        raise HTTPException(status_code=400, detail="base_window.end_ts must be after start_ts.")

    # Reuse candidate search to compute summary for metadata
    try:
        summary_dict, _ = search_similar_windows(
            timeframe=tf,
            start_ts=start_ts,
            end_ts=end_ts,
            max_candidates=20,
            search_cap=60000 if tf == "5m" else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"candidate evaluation failed: {exc}")

    now = datetime.utcnow().isoformat() + "Z"
    new_id = generate_pattern_id(tf, req.pattern_type, uuid4().hex[:8])
    entry = {
        "id": new_id,
        "symbol": req.symbol or DEFAULT_SYMBOL,
        "timeframe": tf,
        "timeframe_origin": tf,
        "pattern_type": req.pattern_type,
        "name": req.name,
        "description": req.description,
        "tags": ensure_iterable(req.tags),
        "strength_level": req.initial_strength_level,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "base_window": {
            "start_ts": start_ts.isoformat().replace("+00:00", "Z"),
            "end_ts": end_ts.isoformat().replace("+00:00", "Z"),
        },
        "candidate_stats": summary_dict,
    }
    append_pattern_to_kb(entry)

    pattern_meta = PatternMeta(
        pattern_id=new_id,
        symbol=req.symbol or DEFAULT_SYMBOL,
        timeframe_origin=tf,
        pattern_type=req.pattern_type,
        name=req.name,
        description=req.description,
        tags=ensure_iterable(req.tags),
        strength_level=req.initial_strength_level,
        status="active",
        support=summary_dict.get("approx_support"),
        lift=None,
        stability=None,
    )

    summary = CandidateSummary(**summary_dict)
    return CreatePatternResponse(pattern=pattern_meta, candidate_summary=summary)
