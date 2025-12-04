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


def get_patterns_by_market_timeframe(kb: KnowledgeBase, market: str, timeframe: str) -> List[PatternRule]:
    """Return patterns for a given market/timeframe."""

    market_lower = market.lower()
    timeframe_lower = timeframe.lower()
    dataset_index = {dataset.id: dataset for dataset in kb.datasets}
    results: List[PatternRule] = []

    for pattern in kb.patterns:
        pattern_timeframe = pattern.timeframe.lower()
        if pattern_timeframe != timeframe_lower:
            continue

        dataset = dataset_index.get(pattern.dataset_used) if pattern.dataset_used else None
        matches_market = False
        if dataset and dataset.market.lower() == market_lower:
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
        patterns_to_filter = list(kb.patterns)
    else:
        patterns_to_filter = list(patterns)
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
