"""Public package interface for rules_kb."""

from .loader import load_knowledge, load_master_knowledge, load_yaml
from .models import (
    KnowledgeBase,
    KnowledgeValidationError,
    MasterKnowledge,
    PatternRule,
    TradingRule,
)
from .query import (
    filter_patterns,
    get_patterns_by_market_timeframe,
    list_markets,
    list_timeframes,
)
from .upgrade import upgrade_kb_structure
from .versioning import bump_kb_version, bump_major, bump_minor, bump_patch, parse_semver

__all__ = [
    "filter_patterns",
    "get_patterns_by_market_timeframe",
    "KnowledgeBase",
    "KnowledgeValidationError",
    "load_knowledge",
    "load_master_knowledge",
    "load_yaml",
    "MasterKnowledge",
    "PatternRule",
    "TradingRule",
    "list_markets",
    "list_timeframes",
    "upgrade_kb_structure",
    "bump_kb_version",
    "bump_major",
    "bump_minor",
    "bump_patch",
    "parse_semver",
]
