from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]

PATTERN_PARQUETS = [
    ROOT / "data" / "patterns_4h_raw_level1_with_embeddings.parquet",
    ROOT / "data" / "patterns_5m_raw_level1_with_embeddings.parquet",
]
FAMILY_PARQUETS = [
    ROOT / "data" / "pattern_families_4h.parquet",
    ROOT / "data" / "pattern_families_5m.parquet",
]

PATTERN_KB_PATH = ROOT / "kb" / "rules_patterns_master.yaml"
FAMILY_KB_PATH = ROOT / "project" / "KNOWLEDGE_BASE" / "patterns" / "pattern_families_level1.yaml"
MASTER_PATH = ROOT / "project" / "MASTER_KNOWLEDGE.yaml"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _bump_version(version: str | None) -> str:
    if not version or "." not in version:
        return "v1.0.0"
    try:
        prefix = version.strip().lstrip("v")
        parts = prefix.split(".")
        while len(parts) < 3:
            parts.append("0")
        major, minor, patch = parts
        patch_num = int(patch) + 1
        return f"v{major}.{minor}.{patch_num}"
    except Exception:
        return "v1.0.0"


def _pattern_status(lift: float, support: float, support_median: float) -> str:
    """
    Status logic:
      - strong: lift>=1.2 and support>=median
      - medium: 1.05<=lift<1.2
      - weak: otherwise
      - aging: if support < 0.5*median and lift < 0.98 (will override weak)
    """
    status = "weak"
    if lift >= 1.2 and support >= support_median:
        status = "strong"
    elif lift >= 1.05:
        status = "medium"
    else:
        status = "weak"
    if support < max(1.0, 0.5 * support_median) and lift < 0.98:
        status = "aging"
    return status


def _family_status(strength_level: str, support: float, lift: float, support_median: float) -> str:
    # keep provided strength_level but override to aging if decayed
    status = strength_level
    if support < max(1.0, 0.5 * support_median) and lift < 0.98:
        status = "aging"
    return status


def _hash_id(prefix: str, text: str) -> str:
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]}"


# -----------------------------------------------------------------------------
# Pattern KB evolution
# -----------------------------------------------------------------------------
def update_pattern_kb_from_parquet(source_tag: str = "AdvancedPhase2") -> Tuple[int, int, int]:
    """
    Upsert canonical patterns from Level-1 pattern parquet files.
    Returns counts: created, updated, aging_marked.
    """
    kb = _load_yaml(PATTERN_KB_PATH)
    patterns: List[Dict[str, Any]] = kb.get("patterns", [])
    # build index for matching existing patterns
    idx = {
        (p.get("timeframe"), p.get("pattern_type"), p.get("definition", "")): i
        for i, p in enumerate(patterns)
    }

    # load all parquet rows
    frames = [pd.read_parquet(p) for p in PATTERN_PARQUETS if p.exists()]
    if not frames:
        raise FileNotFoundError("No pattern parquet files found.")
    df = pd.concat(frames, ignore_index=True)
    support_median = float(df["support"].median())

    created = 0
    updated = 0
    aging_marked = 0

    for row in df.itertuples():
        key = (row.timeframe, row.pattern_type, row.definition)
        status = _pattern_status(float(row.lift), float(row.support), support_median)
        now = _now_iso()
        if key in idx:
            pat = patterns[idx[key]]
            old_status = pat.get("status", "weak")
            # aging/archiving logic: increment aging_count if still aging
            if status == "aging":
                pat["aging_count"] = pat.get("aging_count", 0) + 1
                aging_marked += 1
                if pat["aging_count"] >= 2 and old_status == "aging":
                    pat["status"] = "archived"
                else:
                    pat["status"] = "aging"
            else:
                pat["aging_count"] = 0
                pat["status"] = status
            pat["support"] = float(row.support)
            pat["lift"] = float(row.lift)
            pat["stability"] = float(row.stability) if not pd.isna(row.stability) else None
            pat["window_size"] = int(row.window_size)
            pat["last_seen_at"] = now
            pat["updated_at"] = now
            changelog = pat.setdefault("changelog", [])
            changelog.append(
                {
                    "timestamp": now,
                    "source": source_tag,
                    "updates": {"support": pat["support"], "lift": pat["lift"], "status": pat["status"]},
                }
            )
            updated += 1
        else:
            pat_id = _hash_id(f"pbk_{row.timeframe}_{row.pattern_type}", row.definition)
            patterns.append(
                {
                    "id": pat_id,
                    "timeframe": row.timeframe,
                    "pattern_type": row.pattern_type,
                    "window_size": int(row.window_size),
                    "definition": row.definition,
                    "support": float(row.support),
                    "lift": float(row.lift),
                    "stability": float(row.stability) if not pd.isna(row.stability) else None,
                    "status": status,
                    "origin_layer": "L1",
                    "created_at": now,
                    "updated_at": now,
                    "last_seen_at": now,
                    "source": source_tag,
                    "aging_count": 1 if status == "aging" else 0,
                }
            )
            created += 1

    kb["patterns"] = patterns
    meta = kb.get("meta", {})
    meta["version"] = _bump_version(meta.get("version"))
    meta["updated_at"] = _now_iso()
    kb["meta"] = meta

    PATTERN_KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PATTERN_KB_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(kb, f, sort_keys=False, allow_unicode=True)

    return created, updated, aging_marked


# -----------------------------------------------------------------------------
# Family KB evolution
# -----------------------------------------------------------------------------
def update_family_kb_from_parquet(source_tag: str = "AdvancedPhase3") -> Tuple[int, int]:
    """
    Upsert pattern families from parquet outputs.
    Returns counts: created, updated.
    """
    kb = _load_yaml(FAMILY_KB_PATH)
    families: List[Dict[str, Any]] = kb.get("families", [])
    fam_idx = {fam.get("id"): i for i, fam in enumerate(families)}

    frames = [pd.read_parquet(p) for p in FAMILY_PARQUETS if p.exists()]
    if not frames:
        raise FileNotFoundError("No family parquet files found.")
    df = pd.concat(frames, ignore_index=True)
    support_median = float(df["agg_support"].median())

    created = 0
    updated = 0

    for row in df.itertuples():
        fid = row.family_id
        status = _family_status(row.strength_level, float(row.agg_support), float(row.agg_lift), support_median)
        now = _now_iso()
        if fid in fam_idx:
            fam = families[fam_idx[fid]]
            fam["agg_support"] = float(row.agg_support)
            fam["agg_lift"] = float(row.agg_lift)
            fam["agg_stability"] = float(row.agg_stability) if not np.isnan(row.agg_stability) else None
            fam["window_sizes"] = [int(x) for x in row.dominant_window_sizes]
            fam["pattern_types"] = [str(x) for x in row.dominant_pattern_types]
            fam["member_count"] = int(len(row.member_keys))
            fam["strength_level"] = status
            fam["status"] = status
            fam["updated_at"] = now
            changelog = fam.setdefault("changelog", [])
            changelog.append(
                {
                    "timestamp": now,
                    "source": source_tag,
                    "updates": {
                        "agg_support": fam["agg_support"],
                        "agg_lift": fam["agg_lift"],
                        "status": fam["status"],
                    },
                }
            )
            updated += 1
        else:
            families.append(
                {
                    "id": fid,
                    "timeframe": row.timeframe,
                    "strength_level": status,
                    "status": status,
                    "window_sizes": [int(x) for x in row.dominant_window_sizes],
                    "pattern_types": [str(x) for x in row.dominant_pattern_types],
                    "agg_support": float(row.agg_support),
                    "agg_lift": float(row.agg_lift),
                    "agg_stability": float(row.agg_stability) if not np.isnan(row.agg_stability) else None,
                    "member_count": int(len(row.member_keys)),
                    "notes": str(row.notes),
                    "created_at": now,
                    "updated_at": now,
                    "source": source_tag,
                    "changelog": [
                        {
                            "timestamp": now,
                            "source": source_tag,
                            "updates": {"agg_support": float(row.agg_support), "agg_lift": float(row.agg_lift)},
                        }
                    ],
                }
            )
            created += 1

    kb["families"] = families
    meta = kb.get("meta", {})
    meta["version"] = _bump_version(meta.get("version"))
    meta["updated_at"] = _now_iso()
    meta.setdefault("source", "Codex Advanced Level-2 Families")
    meta.setdefault(
        "description", "Level-1 pattern families for 4h and 5m (embedding + stats based)."
    )
    kb["meta"] = meta

    FAMILY_KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FAMILY_KB_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(kb, f, sort_keys=False, allow_unicode=True)

    return created, updated


# -----------------------------------------------------------------------------
# Master index updater
# -----------------------------------------------------------------------------
def update_master_knowledge_index() -> None:
    master = _load_yaml(MASTER_PATH)
    kb_index = master.get("KNOWLEDGE_BASE_INDEX", {})

    patterns_meta = _load_yaml(PATTERN_KB_PATH).get("meta", {})
    families_meta = _load_yaml(FAMILY_KB_PATH).get("meta", {})

    kb_index["canonical_patterns"] = {
        "path": str(PATTERN_KB_PATH.relative_to(ROOT)),
        "version": patterns_meta.get("version", "v1.0.0"),
        "updated_at": patterns_meta.get("updated_at", _now_iso()),
    }
    kb_index["pattern_families"] = {
        "path": str(FAMILY_KB_PATH.relative_to(ROOT)),
        "version": families_meta.get("version", "v1.0.0"),
        "updated_at": families_meta.get("updated_at", _now_iso()),
    }

    master["KNOWLEDGE_BASE_INDEX"] = kb_index
    meta = master.get("meta", {})
    meta["version"] = master.get("meta", {}).get("version", "0.1.1")
    master["meta"] = meta

    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MASTER_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(master, f, sort_keys=False, allow_unicode=True)


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
def run_kb_evolution() -> None:
    pat_created, pat_updated, pat_aging = update_pattern_kb_from_parquet()
    fam_created, fam_updated = update_family_kb_from_parquet()
    update_master_knowledge_index()

    print(
        f"[summary] patterns: created={pat_created}, updated={pat_updated}, aging_marked={pat_aging}\n"
        f"[summary] families: created={fam_created}, updated={fam_updated}"
    )
    print(f"[paths] pattern KB: {PATTERN_KB_PATH}")
    print(f"[paths] family KB: {FAMILY_KB_PATH}")
    print(f"[paths] master index: {MASTER_PATH}")
    print(
        "KB Evolution completed:\n"
        "- canonical pattern KB updated\n"
        "- pattern families KB updated\n"
        "- MASTER_KNOWLEDGE index synchronized."
    )


if __name__ == "__main__":
    run_kb_evolution()
