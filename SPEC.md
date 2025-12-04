## Rules_Project-v2 — Technical Specification (Authoritative)

Version: 0.1.0  
Scope: BTC_Futures_Adaptive_Patterns / PrisonBreaker  
Primary: BTCUSDT_PERP, 4h + 5m (extensible)

### 1) Purpose
Machine-usable YAML KB + Python loaders/validators + CLI. KB is the source of truth for discovered patterns, trading rules, datasets, and related metadata; not the chat log.

### 2) Reference files
- Strategy/spec: `project/MASTER_KNOWLEDGE.yaml` (v0.1.1)
- Schema: `kb/KB_SCHEMA.yaml` (v0.1.0)
- Example KB: `kb/btcusdt_4h_knowledge.yaml`

### 3) KB structure (per KB_SCHEMA)
Sections and required fields:
- `meta`: {kb_version, schema_version, project_codename, symbol, market, description?, notes?}
- `datasets`: id, symbol, market, timeframe, source[list], date_range{start,end}, n_candles, file_path
- `features`: name, description, dtype, origin_level, formula, tags[list]
- `clusters`: id, name, method, timeframe, feature_set[list], n_clusters, description?, centroid_features{dict}
- `patterns`: id, name, description, window_length, timeframe, type, conditions[list of {feature, operator, value}], target, dataset_used?, status, tags[list], (optional) direction/confidence/regime/metadata
- `trading_rules`: id, name, description?, symbol, direction, entry{pattern_refs[list], extra_conditions[list of {feature,operator,value}]}, exit{tp_sl{tp_multiple, sl_multiple, tstop_n_bars?}}?, risk{max_leverage?, position_size_factor?}?, dataset_used?, status
- `rule_relations`: id, type, rule_a, rule_b, evidence{backtests[list], logical_reasoning?}?
- `cross_market_patterns`: id, markets[list], description?, conditions[list of {market, feature, operator, value}], target_market, target_prediction, status
- `market_relations`: id, base_market, other_market, timeframe, lead_lag{best_lag_other_leads_base?, corr_at_best_lag?, p_value?}?, indicators{rolling_corr_mean?, rolling_corr_std?, granger_p_value?}?, notes[list]
- `backtests`: id, rule_id, date_range{start,end}, metrics{trades?, win_rate?, avg_r_multiple?, max_drawdown?, sharpe_like?, expected_value?}?, equity_curve_path?, parameters_used{dict}
- `performance_over_time`: pattern_id, window_id, window_range{start,end}, stats{trades?, win_rate?, avg_r?, ev?, sample_weight?}
- `status_history`: pattern_id, date, old_status, new_status, reason?, backtest_refs[list]

Constraints (`meta_constraints`):
- IDs unique per section.
- Cross-references (`dataset_used`, `pattern_refs`, `rule_id`, etc.) must resolve.
- File strategy: prefer single `kb/*_knowledge.yaml`; if split, each fragment still must satisfy schema and keep valid references.

### 4) File strategy & enforcement (MASTER_KNOWLEDGE)
- `file_strategy.single_file_initial = true`, `path_initial = kb/btcusdt_4h_knowledge.yaml`.
- `enforcement.single_file_default = true`, `id_uniqueness = true`, `cross_reference_validation = true`.
- Notes: the `rules_kb` validator must pass before use; if split later, all fragments must comply with `KB_SCHEMA` and retain valid cross-references.

### 5) Python models (pydantic v2) — `src/rules_kb/models.py`
- Entities per schema: `Dataset`, `FeatureDefinition`, `ClusterDefinition`, `PatternRule`, `TradingRule`, `RuleRelation`, `CrossMarketPattern`, `MarketRelation`, `BacktestRef`, `PerformanceOverTime`, `StatusHistory`.
- Metadata: `KnowledgeMeta`, `MasterMeta`, `KnowledgeBase`, `MasterKnowledge`.
- Referential checks + ID uniqueness enforced in `KnowledgeBase.validate_references`.
- Optional fields for backward-compatible extensions: pattern direction/confidence/regime/metadata, optional metrics fields.
- TODO (future hardening): restrict enums for direction/status/type; normalize status vocab with lifecycle in master.

### 6) Loaders — `src/rules_kb/loader.py`
- `load_yaml(path)`: `yaml.safe_load`; error on missing/empty/non-mapping.
- `load_knowledge(path) -> KnowledgeBase`: Pydantic validation; raises `KnowledgeValidationError`.
- `load_master_knowledge(path) -> MasterKnowledge`.

### 7) Queries — `src/rules_kb/query.py`
- `get_patterns_by_market_timeframe(kb, market, timeframe)`.
- `filter_patterns(..., min_conf, tags, regime, direction, window_size, status, patterns|kb)`.
- `list_markets(master)`, `list_timeframes(master, market)`.
- Behavior: direction filter drops patterns with missing direction; tags/regime/confidence/window filters supported.

### 8) CLI — `src/rules_kb/cli.py`
- Commands: `validate`, `list-markets`, `list-timeframes --market MKT`,
  `list-patterns --market MKT --timeframe TF [--min-conf ... --tag ... --regime ... --direction ... --window-size ... --status ...]`.
- Renders simple tables; no external deps.

### 9) Tests — `tests/`
- Positive: load/validate `kb/btcusdt_4h_knowledge.yaml`, `project/MASTER_KNOWLEDGE.yaml`.
- Negative: bad dataset reference → `KnowledgeValidationError`.
- Query: filter by confidence/tag/regime; select patterns by market/timeframe.
- Tooling: `pyproject.toml` deps `pydantic>=2.7`, `pyyaml>=6.0`, dev=`pytest>=7.4`.

### 10) Development / extension guidance
- New markets/timeframes: add `*_knowledge.yaml` per schema; ensure references resolve.
- If splitting files (patterns/trading_rules/backtests separated), each must pass schema and maintain cross-file references.
- Adding metadata: introduce optional fields; document in schema/models; keep backward-compatible.
- Consider future enum hardening (direction/status/type) and alignment with lifecycle/status in master.

### 11) Open items / risks
- Enum hardening (direction/status/type) not yet enforced in schema/data; plan before engines rely on strict values.
- Cross-market sections may be empty; need real data and validations.
- Status/lifecycle vocab alignment across master + schema if consumed programmatically (e.g., candidate/active/watchlist/deprecated).

### 12) Pattern discovery doctrine (candles, micro/macro)
- Data scope: 2 years of 4h (~4380 candles) and 5m (~210,240 candles); drop partial candles; standardize timezone.
- Sequence lengths: analyze windows of 2..11 for both 4h and 5m. Forward patterns to predict next candle; backward/meta patterns to confirm/contradict and prune bad predictions.
- Micro vs. macro: analyze 5m independently (local behavior) and conditionally on parent 4h (micro→macro mapping to improve 4h forecasts).
- Methods: sequence/pattern mining (e.g., PrefixSpan/…); Markov/TCN/LSTM/GBM over fixed windows; clustering (kmeans/GMM/…) on features; statistical validation and multiple-testing control (White’s RC/SPA, permutation/surrogate). Literature review and up-to-date method selection are mandatory, not optional.
- Recording patterns: store in `patterns` with conditions {feature, operator, value}, target, dataset_used, status, tags; optional direction/confidence/regime for richer metadata.
- Trading rules: in `trading_rules`, referencing patterns + extra conditions, exit, risk; clusters may be used as conditions.
- Relations among patterns/rules: `rule_relations` (conflict/confirm/complement) to control errors and combine results.
- Strength buckets (by accuracy): very_strong ≥0.80, strong 0.60–0.80, medium 0.55–0.60, weak 0.52–0.55, very_weak <0.52. Prioritize re-mining/improving medium/weak with better methods.
- Monitoring & lifecycle: use `performance_over_time` and `status_history`; statuses (exploratory/candidate/active/watchlist/deprecated) as in MASTER; address drift via periodic updates (pipelines in MASTER).
- Lead-lag: capture which market leads (best_lag_other_leads_base, corr_at_best_lag, granger_p_value) in `market_relations`. Cross-market patterns may inform trading on related instruments, not just BTC.
- Phase execution: core and cross-market phases can be run jointly if data/validation permit (pipeline `continuous_rebacktest_and_refresh` added in MASTER). Tooling choice (VS Code/Codex/etc.) is optional; adherence to schema/validation is mandatory.
- Enforced enums (soft validation in models): pattern type {forward, backward, meta}; status {exploratory, candidate, active, watchlist, deprecated}; direction {long, short, filter_only}; rule relation type {conflict, confirm, complement}.
