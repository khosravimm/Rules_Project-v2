"""KB upgrade utilities: meta normalization, coverage, placeholders."""

from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List, Sequence

from .versioning import bump_kb_version


REQUIRED_WINDOW_LENGTHS_DEFAULT = list(range(2, 12))


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def ensure_meta(kb: Dict[str, Any]) -> None:
    meta = kb.setdefault("meta", {})
    meta.setdefault("project_codename", "PrisonBreaker")
    meta.setdefault("symbol", "BTCUSDT")
    meta.setdefault("market", "BTCUSDT_PERP")
    meta.setdefault("timeframe_core", "4h")
    meta.setdefault("schema_version", meta.get("schema_version", "0.1.0"))
    meta.setdefault("kb_version", meta.get("kb_version", meta.get("version", "0.1.0")))
    meta.setdefault("version", meta.get("version", meta.get("kb_version", "0.1.0")))
    now = _now_iso()
    meta.setdefault("created_at", now.split("T")[0])
    meta["updated_at"] = now
    meta.setdefault("version_history", [])
    meta.setdefault("notes", [])
    meta.setdefault(
        "auto_update_policy",
        {
            "on_data_prep": (
                "After running data_prep_4h5m, only datasets and possibly features are updated; "
                "kb_version patch-level may be bumped if schema changes."
            ),
            "on_pattern_discovery": (
                "After discover_patterns_btc, patterns (and optionally clusters) must be updated, "
                "and kb_version minor-level must be bumped."
            ),
            "on_trading_rule_eval": (
                "After evaluate_trading_rules_btc, trading_rules, backtests, and performance_over_time "
                "must be updated, and kb_version minor-level must be bumped."
            ),
            "on_continuous_refresh": (
                "During continuous_rebacktest_and_refresh, all main sections (patterns, trading_rules, "
                "backtests, performance_over_time, status_history, cross_market_patterns, market_relations) "
                "may be updated; kb_version should be bumped (minor or major) depending on changes."
            ),
        },
    )


def _derive_discovered_lengths(kb: Dict[str, Any]) -> List[int]:
    patterns = kb.get("patterns", {})
    dir_seq = patterns.get("dir_sequence_4h", {})
    items = dir_seq.get("items", []) if isinstance(dir_seq, dict) else []
    lengths: set[int] = set()
    if isinstance(items, list):
        for it in items:
            try:
                seq = it.get("sequence", {}) or {}
                length = seq.get("length")
                if isinstance(length, int):
                    lengths.add(length)
                elif isinstance(seq.get("dirs"), list):
                    lengths.add(len(seq["dirs"]))
            except Exception:
                continue
    miner = dir_seq.get("miner", {}) if isinstance(dir_seq, dict) else {}
    mls = miner.get("window_lengths")
    if isinstance(mls, list):
        for v in mls:
            if isinstance(v, int):
                lengths.add(v)
    return sorted(lengths)


def ensure_discovery_coverage(kb: Dict[str, Any], required_lengths: Sequence[int] = REQUIRED_WINDOW_LENGTHS_DEFAULT) -> None:
    required = sorted(set(int(x) for x in required_lengths))
    discovered = _derive_discovered_lengths(kb)
    missing = [x for x in required if x not in discovered]

    coverage = kb.setdefault("discovery_coverage", {})
    core_4h = coverage.setdefault("core_4h", {})
    core_4h["dir_sequence"] = {
        "required_window_lengths": required,
        "discovered_window_lengths": discovered,
        "missing_window_lengths": missing,
        "status": "complete" if not missing else ("not_started" if not discovered else "partial"),
        "notes": [
            "auto_dir_sequence_miner_v1 currently only covers L=2..5 on DIR_4H."
            if missing
            else "Full 2..11 coverage achieved."
        ],
    }

    micro = coverage.setdefault("micro_5m", {})
    micro.setdefault(
        "independent",
        {
            "status": "not_started",
            "notes": ["No independent 5m pattern miner has been run yet."],
        },
    )
    micro.setdefault(
        "conditional_on_4h",
        {
            "status": "not_started",
            "notes": ["No micro←→macro 5m/4h pattern miner has been run yet."],
        },
    )


def ensure_pattern_placeholders(kb: Dict[str, Any], required_lengths: Sequence[int] = REQUIRED_WINDOW_LENGTHS_DEFAULT) -> None:
    patterns = kb.setdefault("patterns", {})
    # dir_sequence_4h coverage block
    dir_seq = patterns.setdefault("dir_sequence_4h", {})
    miner = dir_seq.setdefault("miner", {})
    miner.setdefault("coverage", {})
    miner["coverage"] = {
        "total_window_lengths": list(required_lengths),
        "mined_window_lengths": miner.get("window_lengths", []) or _derive_discovered_lengths(kb),
        "missing_window_lengths": [
            x for x in required_lengths if x not in (miner.get("window_lengths", []) or _derive_discovered_lengths(kb))
        ],
        "status": "complete"
        if not [
            x for x in required_lengths if x not in (miner.get("window_lengths", []) or _derive_discovered_lengths(kb))
        ]
        else "partial",
        "notes": [
            "This miner currently only covers 4-length windows 2..5. Full 2..11 is planned."
            if miner.get("coverage", {}).get("missing_window_lengths")
            else "Full coverage achieved."
        ],
    }
    dir_seq.setdefault(
        "description",
        "Forward 4h direction sequence patterns on DIR_4H for predicting DIR_4H_NEXT.",
    )

    # 5m placeholders
    patterns.setdefault(
        "micro_5m_independent",
        {
            "description": (
                "Independent 5m sequence patterns (DIR_5M, VOL_BUCKET_5M, BODY_PCT_5M, etc.), "
                "not conditioned on the parent 4h candle."
            ),
            "miner": {
                "name": "m5_independent_sequence_miner_v1",
                "status": "planned",
                "window_lengths": list(required_lengths),
                "notes": ["To be run on the full 210240 5m candles."],
            },
            "items": [],
        },
    )
    patterns.setdefault(
        "micro_5m_conditional_on_4h",
        {
            "description": (
                "5m micro-path patterns conditioned on the parent 4h candle features (DIR_4H, "
                "VOL_BUCKET_4H, REGIME_STATE, etc.), for micro→macro mapping."
            ),
            "miner": {
                "name": "m5_conditional_on_4h_miner_v1",
                "status": "planned",
                "conditioning_features": ["DIR_4H", "VOL_BUCKET_4H", "REGIME_STATE"],
                "window_lengths": list(required_lengths),
                "notes": ["To be implemented by a dedicated miner using the 4h_intra_5m_features dataset."],
            },
            "items": [],
        },
    )


def normalize_trading_rules(kb: Dict[str, Any]) -> None:
    rules = kb.get("trading_rules", {})
    if not isinstance(rules, dict):
        return
    items = rules.get("rules")
    if not isinstance(items, list):
        return
    now = _now_iso()
    for rule in items:
        if not isinstance(rule, dict):
            continue
        lifecycle = rule.setdefault("lifecycle", {})
        lifecycle["status"] = "draft"
        lifecycle.setdefault("created_at", now)
        lifecycle["updated_at"] = now
        notes = lifecycle.setdefault("notes", [])
        rid = rule.get("id", "RULE")
        pattern_refs = rule.get("pattern_refs") or []
        if pattern_refs:
            notes.append(
                f"Rule created from pattern {pattern_refs[0]} with direction={rule.get('direction', '')}."
            )
        notes.append(
            "Built before full 2..11 window coverage and before 5m pattern mining; use only for exploratory backtests."
        )


def upgrade_kb_structure(
    kb: Dict[str, Any],
    *,
    master: Dict[str, Any] | None = None,
    reason: str = "kb upgrade",
    level: str = "patch",
) -> Dict[str, Any]:
    """Upgrade KB in-place (meta, coverage, placeholders) and bump version."""

    required_lengths = (
        master.get("pattern_discovery", {}).get("window_lengths")
        if master and isinstance(master, dict)
        else REQUIRED_WINDOW_LENGTHS_DEFAULT
    )
    ensure_meta(kb)
    ensure_discovery_coverage(kb, required_lengths=required_lengths)
    ensure_pattern_placeholders(kb, required_lengths=required_lengths)
    normalize_trading_rules(kb)
    kb = bump_kb_version(
        kb,
        reason=reason,
        level=level,  # type: ignore[arg-type]
        now=datetime.utcnow(),
    )
    return kb


__all__ = ["upgrade_kb_structure", "ensure_discovery_coverage", "ensure_pattern_placeholders", "normalize_trading_rules"]
