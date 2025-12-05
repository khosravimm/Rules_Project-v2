from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "project" / "DOCUMENTS"

# Potential inputs
PATTERN_FILES = [
    DATA_DIR / "patterns_4h_raw_level1_with_embeddings.parquet",
    DATA_DIR / "patterns_5m_raw_level1_with_embeddings.parquet",
    DATA_DIR / "patterns_4h_raw_level1.parquet",
    DATA_DIR / "patterns_5m_raw_level1.parquet",
]
FAMILY_FILES = [
    DATA_DIR / "pattern_families_4h.parquet",
    DATA_DIR / "pattern_families_5m.parquet",
]

RAW_FILES = {
    "4h": DATA_DIR / "btcusdt_4h_raw.parquet",
    "5m": DATA_DIR / "btcusdt_5m_raw.parquet",
}

PATTERN_KB_PATH = ROOT / "kb" / "rules_patterns_master.yaml"
FAMILY_KB_PATH = ROOT / "project" / "KNOWLEDGE_BASE" / "patterns" / "pattern_families_level1.yaml"

PATTERN_INVENTORY_OUT = DATA_DIR / "pattern_inventory_level1_all.parquet"
FAMILY_INVENTORY_OUT = DATA_DIR / "pattern_inventory_families_all.parquet"
REPORT_PATH = DOCS_DIR / "PrisonBreaker_FullPatternInventory_v1_FA.md"


# -----------------------------------------------------------------------------
# Loading helpers
# -----------------------------------------------------------------------------
def load_pattern_tables() -> pd.DataFrame:
    """
    Load available Level-1 pattern tables (with embeddings preferred) and merge.
    Adds timeframe column based on filename if missing.
    """
    frames: List[pd.DataFrame] = []
    for path in PATTERN_FILES:
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if "timeframe" not in df.columns:
            if "_4h_" in path.name or path.name.startswith("patterns_4h"):
                df["timeframe"] = "4h"
            elif "_5m_" in path.name or path.name.startswith("patterns_5m"):
                df["timeframe"] = "5m"
        frames.append(df)
    if not frames:
        raise FileNotFoundError("No pattern parquet files found.")
    df_all = pd.concat(frames, ignore_index=True)

    # Harmonize column names
    if "agg_lift" in df_all.columns and "lift" not in df_all.columns:
        df_all = df_all.rename(columns={"agg_lift": "lift"})
    if "agg_support" in df_all.columns and "support" not in df_all.columns:
        df_all = df_all.rename(columns={"agg_support": "support"})
    if "agg_stability" in df_all.columns and "stability" not in df_all.columns:
        df_all = df_all.rename(columns={"agg_stability": "stability"})

    return df_all


def load_family_tables() -> pd.DataFrame:
    """Load family parquets and optionally enrich from YAML."""
    frames: List[pd.DataFrame] = []
    for path in FAMILY_FILES:
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        frames.append(df)
    if not frames:
        raise FileNotFoundError("No family parquet files found.")
    fam_df = pd.concat(frames, ignore_index=True)

    if FAMILY_KB_PATH.exists():
        kb = yaml.safe_load(FAMILY_KB_PATH.read_text(encoding="utf-8")) or {}
        fam_map = {f.get("id"): f for f in kb.get("families", [])}
        fam_df["kb_notes"] = fam_df["family_id"].apply(lambda x: fam_map.get(x, {}).get("notes"))
        fam_df["kb_strength"] = fam_df["family_id"].apply(lambda x: fam_map.get(x, {}).get("strength_level"))
        fam_df["kb_updated_at"] = fam_df["family_id"].apply(lambda x: fam_map.get(x, {}).get("updated_at"))
    return fam_df


def _raw_time_ranges() -> Dict[str, Tuple[pd.Timestamp, pd.Timestamp]]:
    ranges: Dict[str, Tuple[pd.Timestamp, pd.Timestamp]] = {}
    for tf, path in RAW_FILES.items():
        if path.exists():
            df = pd.read_parquet(path, columns=["open_time"])
            ts = pd.to_datetime(df["open_time"], utc=True)
            ranges[tf] = (ts.min(), ts.max())
    return ranges


# -----------------------------------------------------------------------------
# Enrichment
# -----------------------------------------------------------------------------
def infer_time_ranges_for_patterns(df_patterns: pd.DataFrame) -> pd.DataFrame:
    """Assign time_range_start/end; if missing per-pattern info, use global range per timeframe."""
    df = df_patterns.copy()
    global_ranges = _raw_time_ranges()
    df["time_range_start"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["time_range_end"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    for tf, (start, end) in global_ranges.items():
        mask = df["timeframe"] == tf
        df.loc[mask, "time_range_start"] = start
        df.loc[mask, "time_range_end"] = end
    return df


def classify_base_type(df_patterns: pd.DataFrame) -> pd.DataFrame:
    """
    base_type rules:
      - direction: pattern_type in sequence/candle_shape and target includes direction
      - value: target mentions return/ret/pnl
      - mixed: definition mentions both DIR and RET markers
      - other: fallback
    """
    df = df_patterns.copy()
    def _classify(row: pd.Series) -> str:
        ptype = str(row.get("pattern_type", "")).lower()
        target = str(row.get("target", "")).lower()
        definition = str(row.get("definition", "")).lower()
        if ptype in {"sequence", "candle_shape"} and ("direction" in target or "dir" in target):
            return "direction"
        if any(x in target for x in ["return", "ret", "pnl"]):
            return "value"
        if "dir" in definition and ("ret" in definition or "return" in definition):
            return "mixed"
        return "other"
    df["base_type"] = df.apply(_classify, axis=1)
    return df


def compute_pattern_scores(df_patterns: pd.DataFrame, kb_map: Dict[Tuple[str, str, str], str]) -> pd.DataFrame:
    """
    pattern_score:
      lift_norm = max(lift-1,0)
      support_norm = log(support+1)
      stability_norm = max(stability,0)
      score = 0.5*lift_norm + 0.3*support_norm + 0.2*stability_norm
      if status == strong: score *= 1.05
    """
    df = df_patterns.copy()
    df["lift_norm"] = df["lift"].apply(lambda x: max(float(x) - 1.0, 0.0) if not pd.isna(x) else 0.0)
    df["support_norm"] = df["support"].apply(lambda x: math.log(float(x) + 1.0) if not pd.isna(x) else 0.0)
    df["stability_norm"] = df["stability"].apply(lambda x: max(float(x), 0.0) if not pd.isna(x) else 0.0)
    df["score"] = 0.5 * df["lift_norm"] + 0.3 * df["support_norm"] + 0.2 * df["stability_norm"]
    if "status" in df.columns:
        mask_strong = df["status"] == "strong"
        df.loc[mask_strong, "score"] = df.loc[mask_strong, "score"] * 1.05

    # attach KB ids if present
    if kb_map:
        df["id"] = df.apply(
            lambda r: kb_map.get((r.get("timeframe"), r.get("pattern_type"), r.get("definition")), None), axis=1
        )
    # generate fallback ids
    df["id"] = df["id"].fillna(
        df.apply(
            lambda r: f"pat_{r.get('timeframe','?')}_{r.get('pattern_type','?')}_{hash(str(r.get('definition',''))) % 10_000_000}",
            axis=1,
        )
    )
    # sample_candles estimate
    df["sample_candles"] = df.apply(
        lambda r: float(r["support"]) * float(r["window_size"]) if not pd.isna(r.get("window_size")) else np.nan,
        axis=1,
    )
    return df


def compute_family_scores(df_families: pd.DataFrame) -> pd.DataFrame:
    """
    family_score:
      lift_norm = max(agg_lift-1,0)
      support_norm = log(agg_support+1)
      stability_norm = max(agg_stability,0)
      score = 0.5*lift_norm + 0.3*support_norm + 0.2*stability_norm
      strong boost 1.10, medium boost 1.05
    """
    df = df_families.copy()
    df["lift_norm"] = df["agg_lift"].apply(lambda x: max(float(x) - 1.0, 0.0) if not pd.isna(x) else 0.0)
    df["support_norm"] = df["agg_support"].apply(lambda x: math.log(float(x) + 1.0) if not pd.isna(x) else 0.0)
    df["stability_norm"] = df["agg_stability"].apply(lambda x: max(float(x), 0.0) if not pd.isna(x) else 0.0)
    df["family_score"] = (
        0.5 * df["lift_norm"] + 0.3 * df["support_norm"] + 0.2 * df["stability_norm"]
    )
    df.loc[df.get("strength_level", "") == "strong", "family_score"] *= 1.10
    df.loc[df.get("strength_level", "") == "medium", "family_score"] *= 1.05
    return df


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------
def save_parquet_inventories(df_patterns: pd.DataFrame, df_families: pd.DataFrame) -> None:
    df_patterns.to_parquet(PATTERN_INVENTORY_OUT, index=False)
    df_families.to_parquet(FAMILY_INVENTORY_OUT, index=False)


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------
def _table_md(df: pd.DataFrame, columns: Dict[str, str], max_rows: int = None) -> str:
    subset = df[list(columns.keys())].rename(columns=columns)
    if max_rows is not None:
        subset = subset.head(max_rows)
    headers = subset.columns.tolist()
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, row in subset.iterrows():
        vals = [str(row[h]) for h in headers]
        lines.append("|" + "|".join(vals) + "|")
    return "\n".join(lines)


def build_bilingual_full_inventory_report(
    df_patterns: pd.DataFrame,
    df_families: pd.DataFrame,
    global_info: Dict[str, Dict[str, int]],
) -> str:
    now = datetime.utcnow().isoformat()

    pat_4h = df_patterns[df_patterns["timeframe"] == "4h"]
    pat_5m = df_patterns[df_patterns["timeframe"] == "5m"]
    fam_4h = df_families[df_families["timeframe"] == "4h"]
    fam_5m = df_families[df_families["timeframe"] == "5m"]

    scoring_text_fa = (
        "pattern_score = 0.5*max(lift-1,0) + 0.3*log(support+1) + 0.2*max(stability,0). "
        "برای الگوهای strong، امتیاز ۵٪ تقویت شده است. "
        "family_score مشابه است با وزن‌های ۰.۵/۰.۳/۰.۲ و تقویت ۱۰٪ برای strong."
    )
    scoring_text_en = (
        "pattern_score = 0.5*max(lift-1,0) + 0.3*log(support+1) + 0.2*max(stability,0); "
        "strong patterns get +5%. family_score uses the same weights with +10% for strong, +5% for medium."
    )

    md: List[str] = []
    md.append(f"# گزارش جامع موجودی الگو و روابط – نسخه v1.0.0\nتاریخ: {now}\nمولد: Codex Full Pattern Inventory Reporter\n")
    md.append("## مقدمه و هدف\nاین گزارش تمام الگوهای سطح ۱ و خانواده‌های کشف‌شده را فهرست می‌کند، همراه با امتیازدهی، بازه زمانی داده و شاخص‌های پشتیبانی/پایداری.\n")
    md.append("## فایل‌های ورودی خوانده‌شده\n- الگوها: pattern*_raw_level1*.parquet (4h/5m)\n- خانواده‌ها: pattern_families_*.parquet و YAML خانواده‌ها (در صورت وجود)\n- داده خام برای بازه زمانی: btcusdt_*_raw.parquet (اگر موجود)\n")
    md.append("## تعریف و روش امتیازدهی\n")
    md.append(f"- {scoring_text_fa}\n")
    md.append("### آمار کلی\n")
    md.append(
        f"- الگوهای ۴h: {len(pat_4h)} | الگوهای ۵m: {len(pat_5m)}\n"
        f"- خانواده‌های ۴h: {len(fam_4h)} | خانواده‌های ۵m: {len(fam_5m)}\n"
        f"- توزیع قدرت خانواده‌ها ۴h: {global_info['families_4h']}\n"
        f"- توزیع قدرت خانواده‌ها ۵m: {global_info['families_5m']}\n"
    )
    md.append("### جدول الگوهای ۴ ساعته\n")
    md.append(
        _table_md(
            pat_4h,
            {
                "id": "id",
                "pattern_type": "type",
                "window_size": "w",
                "base_type": "base",
                "support": "support",
                "sample_candles": "sample_candles",
                "lift": "lift",
                "stability": "stability",
                "score": "score",
                "time_range_start": "start",
                "time_range_end": "end",
            },
        )
    )
    md.append("\n### جدول الگوهای ۵ دقیقه\n")
    md.append(
        _table_md(
            pat_5m,
            {
                "id": "id",
                "pattern_type": "type",
                "window_size": "w",
                "base_type": "base",
                "support": "support",
                "sample_candles": "sample_candles",
                "lift": "lift",
                "stability": "stability",
                "score": "score",
                "time_range_start": "start",
                "time_range_end": "end",
            },
        )
    )
    md.append("\n### خانواده‌های ۴ ساعته\n")
    md.append(
        _table_md(
            fam_4h,
            {
                "family_id": "family_id",
                "member_keys": "members",
                "agg_support": "support",
                "agg_lift": "lift",
                "agg_stability": "stability",
                "strength_level": "strength",
                "family_score": "score",
                "created_at": "created_at",
            },
        )
    )
    md.append("\n### خانواده‌های ۵ دقیقه\n")
    md.append(
        _table_md(
            fam_5m,
            {
                "family_id": "family_id",
                "member_keys": "members",
                "agg_support": "support",
                "agg_lift": "lift",
                "agg_stability": "stability",
                "strength_level": "strength",
                "family_score": "score",
                "created_at": "created_at",
            },
        )
    )

    # English section
    md.append("\n---\n")
    md.append(f"# Full Pattern Inventory Report – v1.0.0 (EN)\nDate: {now}\nGenerator: Codex Full Pattern Inventory Reporter\n")
    md.append("## Purpose\nComplete listing of Level-1 patterns and families with scores, support, stability, and data ranges.\n")
    md.append("## Scoring\n")
    md.append(f"- {scoring_text_en}\n")
    md.append("## Counts\n")
    md.append(
        f"- Patterns 4h={len(pat_4h)}, 5m={len(pat_5m)}; Families 4h={len(fam_4h)}, 5m={len(fam_5m)}\n"
    )
    md.append("## 4h Patterns\n")
    md.append(
        _table_md(
            pat_4h,
            {
                "id": "id",
                "pattern_type": "type",
                "window_size": "w",
                "base_type": "base",
                "support": "support",
                "lift": "lift",
                "stability": "stability",
                "score": "score",
            },
            max_rows=200,
        )
    )
    md.append("\n## 5m Patterns\n")
    md.append(
        _table_md(
            pat_5m,
            {
                "id": "id",
                "pattern_type": "type",
                "window_size": "w",
                "base_type": "base",
                "support": "support",
                "lift": "lift",
                "stability": "stability",
                "score": "score",
            },
            max_rows=200,
        )
    )
    md.append("\n## 4h Families\n")
    md.append(
        _table_md(
            fam_4h,
            {
                "family_id": "family_id",
                "agg_support": "support",
                "agg_lift": "lift",
                "agg_stability": "stability",
                "strength_level": "strength",
                "family_score": "score",
            },
        )
    )
    md.append("\n## 5m Families\n")
    md.append(
        _table_md(
            fam_5m,
            {
                "family_id": "family_id",
                "agg_support": "support",
                "agg_lift": "lift",
                "agg_stability": "stability",
                "strength_level": "strength",
                "family_score": "score",
            },
        )
    )
    return "\n".join(md)


def save_markdown_report(markdown_text: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(markdown_text, encoding="utf-8")


# -----------------------------------------------------------------------------
# KB mapping
# -----------------------------------------------------------------------------
def _kb_pattern_index() -> Dict[Tuple[str, str, str], str]:
    if not PATTERN_KB_PATH.exists():
        return {}
    kb = yaml.safe_load(PATTERN_KB_PATH.read_text(encoding="utf-8")) or {}
    patterns = kb.get("patterns", [])
    return {
        (p.get("timeframe"), p.get("pattern_type"), p.get("definition", "")): p.get("id")
        for p in patterns
    }


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
def run_full_pattern_inventory_report() -> None:
    patterns = load_pattern_tables()
    families = load_family_tables()
    kb_map = _kb_pattern_index()

    patterns = infer_time_ranges_for_patterns(patterns)
    patterns = classify_base_type(patterns)
    patterns = compute_pattern_scores(patterns, kb_map)
    families = compute_family_scores(families)

    save_parquet_inventories(patterns, families)

    fam_strength_4h = families[families["timeframe"] == "4h"]["strength_level"].value_counts().to_dict()
    fam_strength_5m = families[families["timeframe"] == "5m"]["strength_level"].value_counts().to_dict()
    global_info = {
        "families_4h": fam_strength_4h,
        "families_5m": fam_strength_5m,
    }

    report = build_bilingual_full_inventory_report(patterns, families, global_info)
    save_markdown_report(report)

    pat_counts = patterns.groupby(["timeframe", "pattern_type"]).size().reset_index(name="n")
    fam_counts = families.groupby(["timeframe", "strength_level"]).size().reset_index(name="n")

    print("[patterns] counts by timeframe and type:")
    print(pat_counts)
    print("[families] counts by timeframe and strength_level:")
    print(fam_counts)
    print(f"[paths] patterns parquet -> {PATTERN_INVENTORY_OUT}")
    print(f"[paths] families parquet -> {FAMILY_INVENTORY_OUT}")
    print(f"[paths] report -> {REPORT_PATH}")
    print(
        "Full Pattern & Relation Inventory Report generated:\n"
        " - Level-1 patterns and families exported to Parquet\n"
        " - Detailed bilingual FA/EN Markdown report saved."
    )


if __name__ == "__main__":
    run_full_pattern_inventory_report()
