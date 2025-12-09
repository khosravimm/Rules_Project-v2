"""High-level query helpers for the knowledge base."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set

from .models import KnowledgeBase, MasterKnowledge, PatternRule


def _pattern_confidence(pattern: PatternRule) -> Optional[float]:
    """Return the best-available confidence for a pattern."""

    if pattern.confidence is not None:
        return pattern.confidence
    if pattern.metadata and pattern.metadata.confidence is not None:
        return pattern.metadata.confidence
    return None


def _pattern_regime(pattern: PatternRule) -> Optional[str]:
    """Return regime associated with the pattern if present."""

    if pattern.regime:
        return pattern.regime
    if pattern.metadata and pattern.metadata.regime:
        return pattern.metadata.regime
    return None


def _pattern_tags(pattern: PatternRule) -> Set[str]:
    """Return combined tags from the pattern and optional metadata."""

    tags: Set[str] = set(pattern.tags or [])
    if pattern.metadata:
        tags.update(pattern.metadata.tags or [])
    return tags


def _iter_pattern_rules(kb: KnowledgeBase) -> List[PatternRule]:
    """Flatten patterns dict (direct or grouped) into PatternRule objects."""

    patterns_out: List[PatternRule] = []
    for val in kb.patterns.values():
        if isinstance(val, dict) and "items" in val and isinstance(val["items"], list):
            for item in val["items"]:
                if isinstance(item, dict):
                    patterns_out.append(PatternRule.model_validate(item))
        elif isinstance(val, dict):
            patterns_out.append(PatternRule.model_validate(val))
        elif isinstance(val, PatternRule):
            patterns_out.append(val)
    return patterns_out


def _coerce_patterns(source: Iterable[PatternRule] | dict) -> List[PatternRule]:
    """
    Normalize a patterns payload (dict keyed by group/id or iterable) into PatternRule objects.

    This keeps existing filtering logic compatible with the dict-based YAML layout.
    """

    patterns_out: List[PatternRule] = []
    if isinstance(source, dict):
        for val in source.values():
            if isinstance(val, dict) and "items" in val and isinstance(val["items"], list):
                for item in val["items"]:
                    if isinstance(item, PatternRule):
                        patterns_out.append(item)
                    elif isinstance(item, dict):
                        patterns_out.append(PatternRule.model_validate(item))
            elif isinstance(val, PatternRule):
                patterns_out.append(val)
            elif isinstance(val, dict):
                patterns_out.append(PatternRule.model_validate(val))
        return patterns_out

    for p in source:
        if isinstance(p, PatternRule):
            patterns_out.append(p)
        elif isinstance(p, dict):
            patterns_out.append(PatternRule.model_validate(p))
    return patterns_out


def get_patterns_by_market_timeframe(kb: KnowledgeBase, market: str, timeframe: str) -> List[PatternRule]:
    """Return patterns for a given market/timeframe."""

    market_lower = market.lower()
    timeframe_lower = timeframe.lower()
    dataset_index = {}
    for ds_id, ds_val in kb.datasets.items():
        try:
            ds_obj = ds_val if isinstance(ds_val, PatternRule) else ds_val  # type: ignore[truthy-bool]
        except Exception:
            ds_obj = ds_val
        dataset_index[ds_id] = ds_obj

    results: List[PatternRule] = []

    for pattern in _iter_pattern_rules(kb):
        pattern_timeframe = (pattern.timeframe or "").lower()
        if pattern_timeframe != timeframe_lower:
            continue

        ds_used = pattern.dataset_used
        dataset_market = None
        if ds_used and ds_used in dataset_index:
            ds_val = dataset_index[ds_used]
            dataset_market = getattr(ds_val, "market", None)
        matches_market = False
        if dataset_market and dataset_market.lower() == market_lower:
            matches_market = True
        elif kb.meta.market.lower() == market_lower or kb.meta.symbol.lower() == market_lower:
            matches_market = True

        if matches_market:
            results.append(pattern)

    return results


def filter_patterns(
    kb: KnowledgeBase | None,
    *,
    min_conf: Optional[float] = None,
    tags: Optional[Sequence[str]] = None,
    regime: Optional[str] = None,
    direction: Optional[str] = None,
    window_size: Optional[int] = None,
    status: Optional[str] = None,
    patterns: Optional[Iterable[PatternRule]] = None,
) -> List[PatternRule]:
    """Filter patterns according to the provided criteria."""

    if patterns is None:
        if kb is None:
            raise ValueError("Either `kb` or `patterns` must be provided.")
        patterns_to_filter = _iter_pattern_rules(kb)
    else:
        patterns_to_filter = _coerce_patterns(patterns)
    filtered: List[PatternRule] = []

    required_tags = set(tag.lower() for tag in tags) if tags else set()

    for pattern in patterns_to_filter:
        confidence = _pattern_confidence(pattern)
        if min_conf is not None and (confidence is None or confidence < min_conf):
            continue

        if status is not None and pattern.status.lower() != status.lower():
            continue

        if direction is not None and pattern.direction and pattern.direction.lower() != direction.lower():
            continue
        if direction is not None and pattern.direction is None:
            # If a direction filter is provided but the pattern lacks direction, exclude it.
            continue

        if window_size is not None and pattern.window_length != window_size:
            continue

        if regime is not None:
            pat_regime = _pattern_regime(pattern)
            if pat_regime is None or pat_regime.lower() != regime.lower():
                continue

        if required_tags:
            pattern_tags = {tag.lower() for tag in _pattern_tags(pattern)}
            if not required_tags.issubset(pattern_tags):
                continue

        filtered.append(pattern)

    return filtered


def list_markets(master: MasterKnowledge) -> List[str]:
    """List unique markets described in the master knowledge file."""

    markets: Set[str] = {master.project_scope.market_primary}
    markets.update(master.multi_market_scope.markets.primary)
    markets.update(master.multi_market_scope.markets.secondary_candidates)
    return sorted(markets)


def list_timeframes(master: MasterKnowledge, market: str) -> List[str]:
    """List timeframes for a given market based on master knowledge hints."""

    market_lower = market.lower()
    known_markets = {m.lower() for m in list_markets(master)}
    if market_lower not in known_markets:
        return []

    timeframes: Set[str] = set(master.project_scope.timeframes_core)
    timeframes.update(master.project_scope.approx_candles.keys())

    return sorted(timeframes)
