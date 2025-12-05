"""Extended validation against MASTER_KNOWLEDGE and coverage expectations."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _get_required_lengths(master: Dict[str, Any]) -> List[int]:
    try:
        return list(master.get("pattern_discovery", {}).get("window_lengths", []))
    except Exception:
        return []


def _collect_messages() -> Dict[str, List[str]]:
    return {"errors": [], "warnings": [], "info": []}


def _warn(msgs: Dict[str, List[str]], text: str) -> None:
    msgs["warnings"].append(text)


def _err(msgs: Dict[str, List[str]], text: str) -> None:
    msgs["errors"].append(text)


def _ok(msgs: Dict[str, List[str]], text: str) -> None:
    msgs["info"].append(text)


def validate_against_master(kb: Dict[str, Any], master: Dict[str, Any]) -> Dict[str, List[str]]:
    """Validate coverage and lifecycle constraints per MASTER_KNOWLEDGE."""

    msgs = _collect_messages()
    required_lengths = _get_required_lengths(master)
    if not required_lengths:
        _warn(msgs, "[WARN] MASTER_KNOWLEDGE.pattern_discovery.window_lengths missing or empty.")

    coverage = kb.get("discovery_coverage", {})
    dir_cov = coverage.get("core_4h", {}).get("dir_sequence", {})
    if not dir_cov:
        _err(msgs, "[ERROR] discovery_coverage.core_4h.dir_sequence missing.")
    else:
        missing = dir_cov.get("missing_window_lengths", [])
        status = dir_cov.get("status", "unknown")
        if required_lengths:
            missing_required = [l for l in required_lengths if l not in dir_cov.get("discovered_window_lengths", [])]
            if missing_required and status not in {"partial", "not_started"}:
                _warn(
                    msgs,
                    f"[WARN] dir_sequence coverage missing {missing_required} but status is {status!r}.",
                )
        if missing:
            _warn(msgs, f"[WARN] 4h dir_sequence coverage is partial (missing={missing}).")
        else:
            _ok(msgs, "[OK] 4h dir_sequence coverage present.")

    micro = coverage.get("micro_5m", {})
    indep = micro.get("independent", {})
    cond = micro.get("conditional_on_4h", {})
    if not indep:
        _warn(msgs, "[WARN] micro_5m.independent coverage missing.")
    else:
        status = indep.get("status")
        if status not in {"planned", "running", "complete", "done", "not_started", "partial"}:
            _warn(msgs, f"[WARN] micro_5m.independent status unexpected: {status}")
    if not cond:
        _warn(msgs, "[WARN] micro_5m.conditional_on_4h coverage missing.")
    else:
        status = cond.get("status")
        if status not in {"planned", "running", "complete", "done", "not_started", "partial"}:
            _warn(msgs, f"[WARN] micro_5m.conditional_on_4h status unexpected: {status}")

    patterns = kb.get("patterns", {})
    for key in ["micro_5m_independent", "micro_5m_conditional_on_4h"]:
        if key not in patterns:
            _warn(msgs, f"[WARN] patterns.{key} placeholder missing.")
        else:
            miner = patterns.get(key, {}).get("miner", {})
            status = miner.get("status")
            if status not in {"planned", "running", "done", "complete"}:
                _warn(msgs, f"[WARN] patterns.{key}.miner.status is {status!r}")

    # Trading rules lifecycle under incomplete coverage
    rules = kb.get("trading_rules", {}).get("rules", []) if isinstance(kb.get("trading_rules"), dict) else []
    if rules:
        dir_status = dir_cov.get("status")
        micro_statuses = {indep.get("status"), cond.get("status")}
        if dir_status != "complete" or ("not_started" in micro_statuses or None in micro_statuses):
            for rule in rules:
                lifecycle = rule.get("lifecycle", {}) if isinstance(rule, dict) else {}
                status = lifecycle.get("status")
                if status in {"active", "candidate"}:
                    _warn(
                        msgs,
                        f"[WARN] trading rule {rule.get('id')} is {status} while coverage is incomplete.",
                    )
    return msgs


def summarize_messages(msgs: Dict[str, List[str]]) -> Tuple[bool, str]:
    ok = not msgs["errors"]
    lines: List[str] = []
    for kind in ["errors", "warnings", "info"]:
        for m in msgs[kind]:
            lines.append(m)
    return ok, "\n".join(lines)


__all__ = ["validate_against_master", "summarize_messages"]
