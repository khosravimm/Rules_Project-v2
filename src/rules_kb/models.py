"""Data models for the rules knowledge base."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeValidationError(ValueError):
    """Raised when the knowledge base structure violates the expected schema."""


# Allowed value sets for soft enum validation
ALLOWED_PATTERN_TYPES = {"forward", "backward", "meta"}
ALLOWED_STATUSES = {"exploratory", "candidate", "active", "watchlist", "deprecated"}
ALLOWED_DIRECTIONS = {"long", "short", "filter_only"}
ALLOWED_RULE_REL_TYPES = {"conflict", "confirm", "complement"}


def _validate_enum(value: Optional[str], allowed: set[str], field_name: str) -> Optional[str]:
    """Validate that a string value is within the allowed set; raises on mismatch."""

    if value is None:
        return None
    lower = value.lower()
    if lower not in allowed:
        raise KnowledgeValidationError(f"Invalid value '{value}' for {field_name}; allowed: {sorted(allowed)}")
    return lower


# --------------------------------------------------------------------------- #
# Shared primitives
# --------------------------------------------------------------------------- #


class DateRange(BaseModel):
    """Represents a start/end window."""

    start: date | datetime
    end: date | datetime

    model_config = ConfigDict(extra="forbid")


class Condition(BaseModel):
    """Simple feature/operator/value condition."""

    feature: str
    operator: str
    value: Any

    model_config = ConfigDict(extra="forbid")


class CrossMarketCondition(Condition):
    """Condition that is tied to a specific market."""

    market: str

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Knowledge base models (kb/*_knowledge.yaml)
# --------------------------------------------------------------------------- #


class KnowledgeMeta(BaseModel):
    """Metadata describing a single market/timeframe knowledge base file."""

    kb_version: str
    schema_version: str
    project_codename: str
    symbol: str
    market: str
    description: Optional[str] = None
    notes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class Dataset(BaseModel):
    """Reference to a prepared dataset used for discovery/backtests."""

    id: str
    symbol: str
    market: str
    timeframe: str
    source: List[str]
    date_range: DateRange
    n_candles: int
    file_path: str

    model_config = ConfigDict(extra="forbid")


class FeatureDefinition(BaseModel):
    """Feature description."""

    name: str
    description: str
    dtype: str
    origin_level: str
    formula: str
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ClusterDefinition(BaseModel):
    """Cluster specification for grouped feature behavior."""

    id: str
    name: str
    method: str
    timeframe: str
    feature_set: List[str] = Field(default_factory=list)
    n_clusters: int
    description: Optional[str] = None
    centroid_features: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class PatternMetadata(BaseModel):
    """Optional metadata for discovered patterns."""

    confidence: Optional[float] = None
    sample_count: Optional[int] = None
    discovered_by: Optional[str] = None
    discovery_date: Optional[date | datetime] = None
    regime: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class PatternRule(BaseModel):
    """A discovered trading pattern."""

    id: str
    name: str
    description: str
    window_length: int
    timeframe: str
    type: str
    conditions: List[Condition] = Field(default_factory=list)
    target: str
    dataset_used: Optional[str] = None
    status: str
    tags: List[str] = Field(default_factory=list)
    direction: Optional[str] = None
    confidence: Optional[float] = None
    sample_size: Optional[int] = None
    regime: Optional[str] = None
    metadata: Optional[PatternMetadata] = None
    # TODO: consider migrating status to an enum once schema formalizes allowed values.

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_enums(self) -> "PatternRule":
        self.type = _validate_enum(self.type, ALLOWED_PATTERN_TYPES, "patterns.type")  # type: ignore[assignment]
        self.status = _validate_enum(self.status, ALLOWED_STATUSES, "patterns.status")  # type: ignore[assignment]
        self.direction = _validate_enum(self.direction, ALLOWED_DIRECTIONS, "patterns.direction")  # type: ignore[assignment]
        return self


class TradingRuleEntry(BaseModel):
    """Entry configuration for a trading rule."""

    pattern_refs: List[str] = Field(default_factory=list)
    extra_conditions: List[Condition] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class TradingRuleExitTPnSL(BaseModel):
    """Take-profit / stop-loss configuration."""

    tp_multiple: float
    sl_multiple: float
    tstop_n_bars: Optional[int] = None

    model_config = ConfigDict(extra="forbid")


class TradingRuleExit(BaseModel):
    """Exit configuration for a trading rule."""

    tp_sl: Optional[TradingRuleExitTPnSL] = None

    model_config = ConfigDict(extra="forbid")


class TradingRuleRisk(BaseModel):
    """Risk controls for a trading rule."""

    max_leverage: Optional[int] = None
    position_size_factor: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class TradingRule(BaseModel):
    """A fully specified trading rule built from patterns."""

    id: str
    name: str
    description: Optional[str] = None
    symbol: str
    direction: str
    entry: TradingRuleEntry
    exit: Optional[TradingRuleExit] = None
    risk: Optional[TradingRuleRisk] = None
    dataset_used: Optional[str] = None
    status: str

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_enums(self) -> "TradingRule":
        self.direction = _validate_enum(self.direction, ALLOWED_DIRECTIONS, "trading_rules.direction")  # type: ignore[assignment]
        self.status = _validate_enum(self.status, ALLOWED_STATUSES, "trading_rules.status")  # type: ignore[assignment]
        return self


class RuleRelationEvidence(BaseModel):
    """Evidence supporting a relation between two rules."""

    backtests: List[str] = Field(default_factory=list)
    logical_reasoning: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class RuleRelation(BaseModel):
    """Logical relation between two rules/patterns."""

    id: str
    type: str
    rule_a: str
    rule_b: str
    evidence: Optional[RuleRelationEvidence] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_enums(self) -> "RuleRelation":
        self.type = _validate_enum(self.type, ALLOWED_RULE_REL_TYPES, "rule_relations.type")  # type: ignore[assignment]
        return self


class CrossMarketPattern(BaseModel):
    """Pattern that spans multiple markets."""

    id: str
    markets: List[str]
    description: Optional[str] = None
    conditions: List[CrossMarketCondition] = Field(default_factory=list)
    target_market: str
    target_prediction: str
    status: str

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_enums(self) -> "CrossMarketPattern":
        self.status = _validate_enum(self.status, ALLOWED_STATUSES, "cross_market_patterns.status")  # type: ignore[assignment]
        return self


class MarketRelationIndicators(BaseModel):
    """Indicator metrics describing relation between markets."""

    rolling_corr_mean: Optional[float] = None
    rolling_corr_std: Optional[float] = None
    granger_p_value: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class MarketRelationLeadLag(BaseModel):
    """Lead/lag statistics for a market pair."""

    best_lag_other_leads_base: Optional[int] = None
    corr_at_best_lag: Optional[float] = None
    p_value: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class MarketRelation(BaseModel):
    """Relationship between a base market and another market."""

    id: str
    base_market: str
    other_market: str
    timeframe: str
    lead_lag: Optional[MarketRelationLeadLag] = None
    indicators: Optional[MarketRelationIndicators] = None
    notes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class BacktestMetrics(BaseModel):
    """Evaluation metrics for a backtest."""

    trades: Optional[int] = None
    win_rate: Optional[float] = None
    avg_r_multiple: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_like: Optional[float] = None
    expected_value: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class BacktestRef(BaseModel):
    """Reference to a completed backtest."""

    id: str
    rule_id: str
    date_range: DateRange
    metrics: Optional[BacktestMetrics] = None
    equity_curve_path: Optional[str] = None
    parameters_used: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class PerformanceStats(BaseModel):
    """Performance statistics over a window."""

    trades: Optional[int] = None
    win_rate: Optional[float] = None
    avg_r: Optional[float] = None
    ev: Optional[float] = None
    sample_weight: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class PerformanceOverTime(BaseModel):
    """Performance of a pattern across time windows."""

    pattern_id: str
    window_id: str
    window_range: DateRange
    stats: PerformanceStats

    model_config = ConfigDict(extra="forbid")


class StatusHistory(BaseModel):
    """Lifecycle transitions of a pattern."""

    pattern_id: str
    date: date | datetime
    old_status: str
    new_status: str
    reason: Optional[str] = None
    backtest_refs: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class KnowledgeBase(BaseModel):
    """Root object for kb/*_knowledge.yaml."""

    meta: KnowledgeMeta
    datasets: List[Dataset] = Field(default_factory=list)
    features: List[FeatureDefinition] = Field(default_factory=list)
    clusters: List[ClusterDefinition] = Field(default_factory=list)
    patterns: List[PatternRule] = Field(default_factory=list)
    trading_rules: List[TradingRule] = Field(default_factory=list)
    rule_relations: List[RuleRelation] = Field(default_factory=list)
    cross_market_patterns: List[CrossMarketPattern] = Field(default_factory=list)
    market_relations: List[MarketRelation] = Field(default_factory=list)
    backtests: List[BacktestRef] = Field(default_factory=list)
    performance_over_time: List[PerformanceOverTime] = Field(default_factory=list)
    status_history: List[StatusHistory] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_references(self) -> "KnowledgeBase":
        """Ensure referential integrity across sections."""

        dataset_ids = [dataset.id for dataset in self.datasets]
        if len(dataset_ids) != len(set(dataset_ids)):
            raise KnowledgeValidationError("Duplicate dataset ids detected in knowledge base.")

        pattern_ids = [pattern.id for pattern in self.patterns]
        if len(pattern_ids) != len(set(pattern_ids)):
            raise KnowledgeValidationError("Duplicate pattern ids detected in knowledge base.")

        trading_rule_ids = [rule.id for rule in self.trading_rules]
        if len(trading_rule_ids) != len(set(trading_rule_ids)):
            raise KnowledgeValidationError("Duplicate trading_rule ids detected in knowledge base.")

        dataset_id_set = set(dataset_ids)
        for pattern in self.patterns:
            if pattern.dataset_used and pattern.dataset_used not in dataset_id_set:
                raise KnowledgeValidationError(
                    f"Pattern {pattern.id} references unknown dataset '{pattern.dataset_used}'."
                )

        pattern_id_set = set(pattern_ids)
        for rule in self.trading_rules:
            missing_patterns = [ref for ref in rule.entry.pattern_refs if ref not in pattern_id_set]
            if missing_patterns:
                raise KnowledgeValidationError(
                    f"Trading rule {rule.id} references unknown patterns: {', '.join(missing_patterns)}"
                )
            if rule.dataset_used and rule.dataset_used not in dataset_id_set:
                raise KnowledgeValidationError(
                    f"Trading rule {rule.id} references unknown dataset '{rule.dataset_used}'."
                )

        trading_rule_id_set = set(trading_rule_ids)
        for backtest in self.backtests:
            if backtest.rule_id not in trading_rule_id_set:
                raise KnowledgeValidationError(
                    f"Backtest {backtest.id} references unknown trading rule '{backtest.rule_id}'."
                )

        return self


# --------------------------------------------------------------------------- #
# Master knowledge models (project/MASTER_KNOWLEDGE.yaml)
# --------------------------------------------------------------------------- #


class PhaseDefinition(BaseModel):
    """Project phase description."""

    id: str
    name: str
    description: str

    model_config = ConfigDict(extra="forbid")


class ProjectScope(BaseModel):
    """Scope of the overall project."""

    symbol_primary: str
    market_primary: str
    exchanges_primary: List[str]
    timeframes_core: List[str]
    horizon_years: int
    approx_candles: Dict[str, int]
    phases: List[PhaseDefinition] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class LoaderPolicy(BaseModel):
    """Loader policy description."""

    allow_custom_loader: bool
    description: str

    model_config = ConfigDict(extra="forbid")


class LoaderInterface(BaseModel):
    """Expected loader interface for OHLCV data."""

    ohlcv_loader_function: str
    required_columns: List[str]
    responsibilities: List[str]

    model_config = ConfigDict(extra="forbid")


class TimeframeDesign(BaseModel):
    """Design for a given timeframe category."""

    description: str
    features_expected: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class DataSplittingStrategy(BaseModel):
    """Splitting strategy for datasets."""

    type: str
    description: str

    model_config = ConfigDict(extra="forbid")


class DataSplitting(BaseModel):
    """Data splitting policy."""

    rationale: str
    strategy: DataSplittingStrategy
    weighting: Dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class DataDesign(BaseModel):
    """Overall data design."""

    loader_policy: LoaderPolicy
    loader_interface: LoaderInterface
    timeframes: Dict[str, TimeframeDesign]
    data_splitting: DataSplitting

    model_config = ConfigDict(extra="forbid")


class CandleObjectDefinition(BaseModel):
    """Feature model for candle object."""

    description: str
    base_fields: List[str]
    derived_fields_4h: List[Dict[str, str]]
    sequence_window: "SequenceWindowDefinition"

    model_config = ConfigDict(extra="forbid")


class SequenceWindowDefinition(BaseModel):
    """Sequence window configuration."""

    lengths: List[int]
    description: str
    representation: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class FeatureModel(BaseModel):
    """Feature model section."""

    candle_object: CandleObjectDefinition

    model_config = ConfigDict(extra="forbid")


class PatternDiscoveryMethods(BaseModel):
    """Methods used for pattern discovery."""

    classical: List[str] = Field(default_factory=list)
    ml_based: List[str] = Field(default_factory=list)
    statistical_validation: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class PatternTypeDefinition(BaseModel):
    """Definition of a pattern type."""

    description: str
    output_target: Optional[List[str]] = None

    model_config = ConfigDict(extra="forbid")


class MicroPatternDefinition(BaseModel):
    """Definition for micro (5m) patterns."""

    description: str

    model_config = ConfigDict(extra="forbid")


class MicroPatterns(BaseModel):
    """Micro-pattern configurations."""

    independent: MicroPatternDefinition
    conditional_on_4h: MicroPatternDefinition

    model_config = ConfigDict(extra="forbid")


class PatternDiscovery(BaseModel):
    """Pattern discovery strategy."""

    objectives: List[str] = Field(default_factory=list)
    window_lengths: List[int] = Field(default_factory=list)
    methods: PatternDiscoveryMethods
    pattern_types: Dict[str, PatternTypeDefinition]
    micro_5m_patterns: MicroPatterns

    model_config = ConfigDict(extra="forbid")


class AccuracyBucket(BaseModel):
    """Accuracy bucket definition."""

    acc_min: float
    acc_max: float

    model_config = ConfigDict(extra="forbid")


class PatternScoring(BaseModel):
    """Pattern scoring policy."""

    accuracy_buckets: Dict[str, AccuracyBucket]
    metrics: Dict[str, Any]
    classification_rules: Dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class StatusTransitionRule(BaseModel):
    """Rules for transitioning between statuses."""

    from_: str = Field(alias="from")
    to: str
    condition: str

    model_config = ConfigDict(extra="forbid")


class UpdateCycle(BaseModel):
    """Lifecycle update cadence."""

    frequency: str
    steps: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class PatternLifecycle(BaseModel):
    """Lifecycle of discovered patterns."""

    statuses: List[str]
    update_cycle: UpdateCycle
    status_transition_rules: Dict[str, List[StatusTransitionRule]]
    focus_on_medium_and_weak: Dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class MarketsGroup(BaseModel):
    """Primary/secondary markets for multi-market scope."""

    primary: List[str]
    secondary_candidates: List[str]
    note: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class MultiMarketScope(BaseModel):
    """Scope for multiple markets and cross-market analysis."""

    markets: MarketsGroup
    cross_market_relations: Dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class KnowledgeBaseStrategy(BaseModel):
    """Strategy for managing knowledge base files."""

    concept: str
    main_sections: List[str]
    file_strategy: Dict[str, Any]
    enforcement: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class PipelineDefinition(BaseModel):
    """Pipeline definition."""

    id: str
    name: str
    description: str
    inputs: List[str]
    outputs: List[str]

    model_config = ConfigDict(extra="forbid")


class ToolingRole(BaseModel):
    """Tooling/LLM role description."""

    description: str
    usage: Optional[List[str]] = None

    model_config = ConfigDict(extra="forbid")


class ToolingSection(BaseModel):
    """Tooling guidance."""

    llm_role: ToolingRole
    codex_role: ToolingRole

    model_config = ConfigDict(extra="forbid")


class ImplementationNotes(BaseModel):
    """Implementation notes and principles."""

    principles: List[str]
    tooling: ToolingSection

    model_config = ConfigDict(extra="forbid")


class MasterMeta(BaseModel):
    """Metadata for the master knowledge file."""

    project_name: str
    project_codename: str
    version: str
    created_at: date | datetime
    author_role: str
    description: str
    primary_goal: str
    secondary_goals: List[str]
    languages: List[str]
    notes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class MasterKnowledge(BaseModel):
    """Root object for project/MASTER_KNOWLEDGE.yaml."""

    meta: MasterMeta
    project_scope: ProjectScope
    data_design: DataDesign
    feature_model: FeatureModel
    pattern_discovery: PatternDiscovery
    pattern_scoring: PatternScoring
    pattern_lifecycle: PatternLifecycle
    multi_market_scope: MultiMarketScope
    knowledge_base: KnowledgeBaseStrategy
    pipelines: List[PipelineDefinition]
    implementation_notes: ImplementationNotes

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "BacktestMetrics",
    "BacktestRef",
    "ClusterDefinition",
    "Condition",
    "CrossMarketCondition",
    "CrossMarketPattern",
    "Dataset",
    "DateRange",
    "FeatureDefinition",
    "FeatureModel",
    "KnowledgeBase",
    "KnowledgeBaseStrategy",
    "KnowledgeMeta",
    "KnowledgeValidationError",
    "MarketRelation",
    "MarketRelationIndicators",
    "MarketRelationLeadLag",
    "MasterKnowledge",
    "MasterMeta",
    "PatternDiscovery",
    "PatternLifecycle",
    "PatternMetadata",
    "PatternRule",
    "PatternScoring",
    "PerformanceOverTime",
    "PerformanceStats",
    "PipelineDefinition",
    "ProjectScope",
    "RuleRelation",
    "RuleRelationEvidence",
    "SequenceWindowDefinition",
    "StatusHistory",
    "TradingRule",
    "TradingRuleEntry",
    "TradingRuleExit",
    "TradingRuleExitTPnSL",
    "TradingRuleRisk",
]
