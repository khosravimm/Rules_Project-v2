
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "project" / "DOCUMENTS"

PATTERN_PRIORITY: Dict[str, List[Path]] = {
    "4h": [
        DATA_DIR / "patterns_4h_raw_level1_with_embeddings.parquet",
        DATA_DIR / "patterns_4h_raw_level1.parquet",
    ],
    "5m": [
        DATA_DIR / "patterns_5m_raw_level1_with_embeddings.parquet",
        DATA_DIR / "patterns_5m_raw_level1.parquet",
    ],
}

FAMILY_FILES: List[Path] = [
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
# Data loading helpers
# -----------------------------------------------------------------------------
def _load_first_available(paths: List[Path]) -> Tuple[pd.DataFrame, List[str]]:
    for path in paths:
        if path.exists():
            return pd.read_parquet(path), [str(path)]
    return pd.DataFrame(), []


def _harmonize_pattern_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "agg_support": "support",
        "agg_lift": "lift",
        "agg_stability": "stability",
        "window_sizes": "window_size",
    }
    df = df.rename(columns=rename_map)
    for col in [
        "timeframe",
        "window_size",
        "pattern_type",
        "definition",
        "target",
        "support",
        "lift",
        "stability",
        "notes",
        "created_at",
        "last_updated_at",
    ]:
        if col not in df.columns:
            df[col] = np.nan
    return df


def load_level1_patterns() -> pd.DataFrame:
    """
    - Detect and load Level-1 pattern tables for 4h and 5m
      from the available Parquet files.
    - Harmonise column names (rename to common schema: timeframe, window_size,
      pattern_type, definition, support, lift, stability, target, etc.).
    - Return a single combined DataFrame with a 'timeframe' column.
    """
    frames: List[pd.DataFrame] = []
    for tf, paths in PATTERN_PRIORITY.items():
        df, sources = _load_first_available(paths)
        if df.empty:
            continue
        df = _harmonize_pattern_columns(df)
        df["timeframe"] = df["timeframe"].fillna(tf)
        df["source_files"] = [sources] * len(df)
        frames.append(df)

    if not frames:
        return pd.DataFrame(
            columns=[
                "id",
                "timeframe",
                "window_size",
                "pattern_type",
                "definition",
                "base_type",
                "target",
                "support",
                "lift",
                "stability",
                "sample_candles",
                "time_range_start",
                "time_range_end",
                "pattern_score",
                "source_files",
                "created_at",
                "last_updated_at",
            ]
        )

    df_all = pd.concat(frames, ignore_index=True)
    return df_all


def _harmonize_family_columns(df: pd.DataFrame, source: str) -> pd.DataFrame:
    rename_map = {
        "dominant_window_sizes": "window_sizes",
        "dominant_pattern_types": "pattern_types",
    }
    df = df.rename(columns=rename_map)
    for col in [
        "family_id",
        "timeframe",
        "window_sizes",
        "pattern_types",
        "member_pattern_ids",
        "agg_support",
        "agg_lift",
        "agg_stability",
        "strength_level",
        "created_at",
        "last_updated_at",
    ]:
        if col not in df.columns:
            df[col] = np.nan
    for text_col in ["created_at", "last_updated_at"]:
        df[text_col] = df[text_col].astype("object")
    df["source_files"] = [[source]] * len(df)
    return df


def _load_family_yaml() -> Dict[str, dict]:
    if not FAMILY_KB_PATH.exists():
        return {}
    data = yaml.safe_load(FAMILY_KB_PATH.read_text(encoding="utf-8")) or {}
    return {fam.get("id"): fam for fam in data.get("families", [])}


def load_families() -> pd.DataFrame:
    """
    - Load data/pattern_families_4h.parquet and data/pattern_families_5m.parquet.
    - If project/KNOWLEDGE_BASE/patterns/pattern_families_level1.yaml exists,
      use it to enrich membership info (member_pattern_ids) and meta timestamps.
    - Return a combined DataFrame for all families.
    """
    frames: List[pd.DataFrame] = []
    for path in FAMILY_FILES:
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        frames.append(_harmonize_family_columns(df, str(path)))

    if not frames:
        return pd.DataFrame(
            columns=[
                "family_id",
                "timeframe",
                "window_sizes",
                "pattern_types",
                "member_pattern_ids",
                "member_count",
                "agg_support",
                "agg_lift",
                "agg_stability",
                "strength_level",
                "family_score",
                "time_range_start",
                "time_range_end",
                "source_files",
                "created_at",
                "last_updated_at",
            ]
        )

    fam_df = pd.concat(frames, ignore_index=True)
    yaml_map = _load_family_yaml()

    if yaml_map:
        fam_df["member_pattern_ids"] = fam_df.get("member_pattern_ids", np.nan)
        fam_df["member_pattern_ids"] = fam_df["member_pattern_ids"].apply(
            lambda v: v if isinstance(v, list) else []
        )
        for idx, row in fam_df.iterrows():
            meta = yaml_map.get(row["family_id"], {})
            if meta:
                fam_df.at[idx, "strength_level"] = meta.get("strength_level", row.get("strength_level"))
                fam_df.at[idx, "window_sizes"] = meta.get("window_sizes", row.get("window_sizes"))
                fam_df.at[idx, "pattern_types"] = meta.get("pattern_types", row.get("pattern_types"))
                fam_df.at[idx, "agg_support"] = meta.get("agg_support", row.get("agg_support"))
                fam_df.at[idx, "agg_lift"] = meta.get("agg_lift", row.get("agg_lift"))
                fam_df.at[idx, "agg_stability"] = meta.get("agg_stability", row.get("agg_stability"))
                fam_df.at[idx, "member_count"] = meta.get("member_count", row.get("member_count"))
                fam_df.at[idx, "created_at"] = meta.get("created_at", row.get("created_at"))
                fam_df.at[idx, "last_updated_at"] = meta.get("updated_at", row.get("last_updated_at"))
    return fam_df


# -----------------------------------------------------------------------------
# Time ranges
# -----------------------------------------------------------------------------
def infer_time_ranges(
    df_patterns: pd.DataFrame,
    df_families: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    - Infer global time ranges from raw 4h/5m Parquet if present.
    - If per-pattern/family time fields exist, use them; else use global range per timeframe.
    - Add 'time_range_start' and 'time_range_end' columns to both dataframes.
    """
    df_pat = df_patterns.copy()
    df_fam = df_families.copy()

    def _global_ranges() -> Dict[str, Tuple[pd.Timestamp, pd.Timestamp]]:
        ranges: Dict[str, Tuple[pd.Timestamp, pd.Timestamp]] = {}
        for tf, path in RAW_FILES.items():
            if not path.exists():
                continue
            raw_df = pd.read_parquet(path, columns=["open_time"])
            ts = pd.to_datetime(raw_df["open_time"], utc=True)
            ranges[tf] = (ts.min(), ts.max())
        return ranges

    global_ranges = _global_ranges()

    df_pat["time_range_start"] = pd.NaT
    df_pat["time_range_end"] = pd.NaT
    df_fam["time_range_start"] = pd.NaT
    df_fam["time_range_end"] = pd.NaT

    pat_start_cols = [c for c in ["first_seen_at", "time_range_start"] if c in df_pat.columns]
    pat_end_cols = [c for c in ["last_seen_at", "time_range_end"] if c in df_pat.columns]

    fam_start_cols = [c for c in ["first_seen_at", "time_range_start"] if c in df_fam.columns]
    fam_end_cols = [c for c in ["last_seen_at", "time_range_end"] if c in df_fam.columns]

    if pat_start_cols and pat_end_cols:
        df_pat["time_range_start"] = pd.to_datetime(df_pat[pat_start_cols[0]], utc=True, errors="coerce")
        df_pat["time_range_end"] = pd.to_datetime(df_pat[pat_end_cols[0]], utc=True, errors="coerce")

    if fam_start_cols and fam_end_cols:
        df_fam["time_range_start"] = pd.to_datetime(df_fam[fam_start_cols[0]], utc=True, errors="coerce")
        df_fam["time_range_end"] = pd.to_datetime(df_fam[fam_end_cols[0]], utc=True, errors="coerce")

    for tf, (start, end) in global_ranges.items():
        pat_mask = (df_pat["timeframe"] == tf) & df_pat["time_range_start"].isna()
        fam_mask = (df_fam["timeframe"] == tf) & df_fam["time_range_start"].isna()
        df_pat.loc[pat_mask, ["time_range_start", "time_range_end"]] = (start, end)
        df_fam.loc[fam_mask, ["time_range_start", "time_range_end"]] = (start, end)

    return df_pat, df_fam


# -----------------------------------------------------------------------------
# Pattern enrichment
# -----------------------------------------------------------------------------
def classify_base_types(df_patterns: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the base_type rules:
      - direction: pattern_type in {sequence, candle_shape} AND target mentions direction/next_direction
      - value: target mentions return/ret/pnl (case-insensitive)
      - mixed: definition/notes mention BOTH a direction-like marker and a value-like marker
      - other: fallback
    """
    df = df_patterns.copy()
    direction_tokens = ["direction", "next_direction", "dir"]
    value_tokens = ["return", "ret", "pnl", "body_pct", "vol"]

    def _has_any(text: str, tokens: List[str]) -> bool:
        t = text.lower()
        return any(tok in t for tok in tokens)

    def _classify(row: pd.Series) -> str:
        ptype = str(row.get("pattern_type", "")).lower()
        target = str(row.get("target", "")).lower()
        definition = str(row.get("definition", ""))
        notes = str(row.get("notes", ""))
        if ptype in {"sequence", "candle_shape"} and _has_any(target, direction_tokens):
            return "direction"
        if _has_any(target, value_tokens):
            return "value"
        dir_like = _has_any(definition, direction_tokens) or _has_any(notes, direction_tokens)
        val_like = _has_any(definition, value_tokens) or _has_any(notes, value_tokens)
        if dir_like and val_like:
            return "mixed"
        return "other"

    df["base_type"] = df.apply(_classify, axis=1)
    return df


def _load_pattern_kb() -> Dict[Tuple[str, str, str], dict]:
    if not PATTERN_KB_PATH.exists():
        return {}
    data = yaml.safe_load(PATTERN_KB_PATH.read_text(encoding="utf-8")) or {}
    patterns = data.get("patterns", [])
    return {
        (str(p.get("timeframe")), str(p.get("pattern_type")), str(p.get("definition"))): p for p in patterns
    }


def _attach_pattern_ids(df_patterns: pd.DataFrame, kb_index: Dict[Tuple[str, str, str], dict]) -> pd.DataFrame:
    df = df_patterns.copy()
    ids: List[Optional[str]] = []
    strengths: List[Optional[str]] = []
    updated: List[Optional[str]] = []
    targets: List[Optional[str]] = []
    for _, row in df.iterrows():
        key = (str(row.get("timeframe")), str(row.get("pattern_type")), str(row.get("definition")))
        kb_entry = kb_index.get(key, {})
        ids.append(kb_entry.get("id"))
        strengths.append(kb_entry.get("status"))
        updated.append(kb_entry.get("updated_at"))
        targets.append(kb_entry.get("target"))

    df["id"] = ids
    df["strength_level"] = strengths
    df["last_updated_at"] = df["last_updated_at"].fillna(pd.Series(updated))
    df["target"] = df["target"].fillna(pd.Series(targets))

    def _stable_id(row: pd.Series) -> str:
        if isinstance(row.get("id"), str) and row["id"]:
            return row["id"]
        base = f"{row.get('timeframe','?')}|{row.get('pattern_type','?')}|{row.get('window_size','?')}|{row.get('definition','?')}"
        return f"pat_{abs(hash(base)) % 10_000_000}"

    df["id"] = df.apply(_stable_id, axis=1)
    return df


def compute_pattern_scores(df_patterns: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'pattern_score' column based on the scoring formula.
    lift_norm = max(lift - 1.0, 0.0)
    support_norm = log(support + 1.0)
    stability_norm = max(stability, 0.0)
    pattern_score = 0.5*lift_norm + 0.3*support_norm + 0.2*stability_norm
    If strength_level == strong -> *1.05
    """
    df = df_patterns.copy()

    df["lift_norm"] = df["lift"].apply(lambda x: max(float(x) - 1.0, 0.0) if not pd.isna(x) else 0.0)
    df["support_norm"] = df["support"].apply(
        lambda x: math.log(float(x) + 1.0) if not pd.isna(x) and float(x) > 0 else 0.0
    )
    df["stability_norm"] = df["stability"].apply(lambda x: max(float(x), 0.0) if not pd.isna(x) else 0.0)

    df["pattern_score"] = 0.5 * df["lift_norm"] + 0.3 * df["support_norm"] + 0.2 * df["stability_norm"]
    df.loc[df["strength_level"] == "strong", "pattern_score"] *= 1.05

    df["sample_candles"] = df.apply(
        lambda r: float(r["support"]) * float(r["window_size"])
        if not pd.isna(r.get("support")) and not pd.isna(r.get("window_size"))
        else np.nan,
        axis=1,
    )
    return df


# -----------------------------------------------------------------------------
# Family enrichment
# -----------------------------------------------------------------------------
def compute_family_scores(df_families: pd.DataFrame) -> pd.DataFrame:
    """
    Add/recompute 'family_score' column for families using:
      lift_norm = max(agg_lift - 1.0, 0.0)
      support_norm = log(agg_support + 1.0)
      stability_norm = max(agg_stability, 0.0) if not NaN else 0.0
      family_score = 0.5*lift_norm + 0.3*support_norm + 0.2*stability_norm
      Boost by strength_level: strong *1.10, medium *1.05
    """
    df = df_families.copy()
    df["lift_norm"] = df["agg_lift"].apply(lambda x: max(float(x) - 1.0, 0.0) if not pd.isna(x) else 0.0)
    df["support_norm"] = df["agg_support"].apply(
        lambda x: math.log(float(x) + 1.0) if not pd.isna(x) else 0.0
    )
    df["stability_norm"] = df["agg_stability"].apply(lambda x: max(float(x), 0.0) if not pd.isna(x) else 0.0)
    df["family_score"] = (
        0.5 * df["lift_norm"] + 0.3 * df["support_norm"] + 0.2 * df["stability_norm"]
    )
    df.loc[df["strength_level"] == "strong", "family_score"] *= 1.10
    df.loc[df["strength_level"] == "medium", "family_score"] *= 1.05
    return df


def _map_family_members(df_families: pd.DataFrame, df_patterns: pd.DataFrame) -> pd.DataFrame:
    """
    Map family member_keys to pattern ids when possible using a canonical key:
    pattern_type|w{window_size}|{definition}.
    """
    fam_df = df_families.copy()
    pat_lookup = {}
    for _, row in df_patterns.iterrows():
        w = row.get("window_size")
        win = int(w) if not pd.isna(w) else "nan"
        key = f"{str(row.get('pattern_type','')).lower()}|w{win}|{str(row.get('definition','')).lower()}"
        pat_lookup[key] = row.get("id")

    member_ids: List[List[str]] = []
    for _, row in fam_df.iterrows():
        ids: List[str] = []
        members = row.get("member_keys", []) if isinstance(row.get("member_keys"), list) else []
        for mk in members:
            key = str(mk).lower()
            pid = pat_lookup.get(key)
            if pid:
                ids.append(pid)
        member_ids.append(ids)

    fam_df["member_pattern_ids"] = fam_df.get("member_pattern_ids")
    fam_df["member_pattern_ids"] = [
        existing if isinstance(existing, list) and existing else ids
        for existing, ids in zip(fam_df["member_pattern_ids"], member_ids)
    ]
    fam_df["member_count"] = fam_df["member_pattern_ids"].apply(lambda v: len(v) if isinstance(v, list) else np.nan)
    return fam_df


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------
def save_parquet_inventories(df_patterns: pd.DataFrame, df_families: pd.DataFrame) -> None:
    """
    - Save:
        data/pattern_inventory_level1_all.parquet
        data/pattern_inventory_families_all.parquet
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df_patterns.to_parquet(PATTERN_INVENTORY_OUT, index=False)
    df_families.to_parquet(FAMILY_INVENTORY_OUT, index=False)


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------
def _df_markdown(df: pd.DataFrame, columns: List[str]) -> str:
    if df.empty:
        return "_جدول خالی / Empty table_"
    subset = df[columns]
    headers = list(subset.columns)
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, row in subset.iterrows():
        values = [str(row[h]) for h in headers]
        lines.append("|" + "|".join(values) + "|")
    return "\n".join(lines)


def build_bilingual_markdown_report(
    df_patterns: pd.DataFrame,
    df_families: pd.DataFrame,
    meta_info: dict,
) -> str:
    """
    Build a detailed FA+EN Markdown string:

    FA section:
      - عنوان: "گزارش کامل الگوها و روابط – نسخه v1.0.0"
      - متا: تاریخ، منبع داده‌ها
      - توضیح روش امتیازدهی pattern_score و family_score
      - توضیح base_type (جهت/مقدار/ترکیبی/سایر)
      - آمار کلی و جداول کامل برای 4h/5m و خانواده‌ها

    EN section mirrors the same content.
    """
    now = datetime.utcnow().isoformat()

    pat_4h = df_patterns[df_patterns["timeframe"] == "4h"]
    pat_5m = df_patterns[df_patterns["timeframe"] == "5m"]
    fam_4h = df_families[df_families["timeframe"] == "4h"]
    fam_5m = df_families[df_families["timeframe"] == "5m"]

    def _distribution_text(df: pd.DataFrame, column: str) -> str:
        if df.empty or column not in df.columns:
            return "هیچ داده‌ای / No data"
        counts = df[column].value_counts(dropna=False).to_dict()
        parts = [f"{k}:{v}" for k, v in counts.items()]
        return " | ".join(parts)

    meta_sources = meta_info.get("sources", {})
    global_ranges = meta_info.get("time_ranges", {})

    md: List[str] = []
    md.append("# گزارش کامل الگوها و روابط – نسخه v1.0.0")
    md.append(f"- تاریخ تولید: {now}")
    md.append("- مولد: Codex Full Pattern & Relation Inventory Reporter")
    md.append("## منابع داده")
    md.append(f"- جداول الگوی سطح ۱: {meta_sources.get('pattern_tables', [])}")
    md.append(f"- جداول خانواده‌ها: {meta_sources.get('family_tables', [])}")
    md.append(f"- محدوده‌های زمانی بر اساس داده خام: {global_ranges}")
    md.append("## منطق امتیازدهی و base_type")
    md.append(
        "- pattern_score = 0.5*max(lift-1,0) + 0.3*log(support+1) + 0.2*max(stability,0)؛ در حالت strong، امتیاز ۵٪ تقویت می‌شود."
    )
    md.append(
        "- family_score = 0.5*max(agg_lift-1,0) + 0.3*log(agg_support+1) + 0.2*max(agg_stability,0)؛ در حالت strong، ۱۰٪ و در medium، ۵٪ تقویت می‌شود."
    )
    md.append(
        "- قاعده base_type: اگر الگو از نوع sequence یا candle_shape باشد و target شامل جهت باشد → direction؛ اگر target شامل return/ret/pnl باشد → value؛ اگر توضیح شامل شاخص جهت و مقدار باشد → mixed؛ در غیر این صورت other."
    )
    md.append("## آمار کلی")
    md.append(f"- تعداد الگوهای ۴h: {len(pat_4h)} | ۵m: {len(pat_5m)}")
    md.append(
        f"- توزیع pattern_type: ۴h[{_distribution_text(pat_4h, 'pattern_type')}] | ۵m[{_distribution_text(pat_5m, 'pattern_type')}]"
    )
    md.append(
        f"- توزیع base_type: ۴h[{_distribution_text(pat_4h, 'base_type')}] | ۵m[{_distribution_text(pat_5m, 'base_type')}]"
    )
    md.append(
        f"- تعداد خانواده‌ها: ۴h={len(fam_4h)} | ۵m={len(fam_5m)}؛ توزیع strength_level ۴h[{_distribution_text(fam_4h, 'strength_level')}] | ۵m[{_distribution_text(fam_5m, 'strength_level')}]"
    )
    md.append("## الگوهای ۴h")
    md.append(
        _df_markdown(
            pat_4h[
                [
                    "id",
                    "window_size",
                    "pattern_type",
                    "base_type",
                    "support",
                    "sample_candles",
                    "lift",
                    "stability",
                    "time_range_start",
                    "time_range_end",
                    "pattern_score",
                ]
            ],
            [
                "id",
                "window_size",
                "pattern_type",
                "base_type",
                "support",
                "sample_candles",
                "lift",
                "stability",
                "time_range_start",
                "time_range_end",
                "pattern_score",
            ],
        )
    )
    md.append("## الگوهای ۵m")
    md.append(
        _df_markdown(
            pat_5m[
                [
                    "id",
                    "window_size",
                    "pattern_type",
                    "base_type",
                    "support",
                    "sample_candles",
                    "lift",
                    "stability",
                    "time_range_start",
                    "time_range_end",
                    "pattern_score",
                ]
            ],
            [
                "id",
                "window_size",
                "pattern_type",
                "base_type",
                "support",
                "sample_candles",
                "lift",
                "stability",
                "time_range_start",
                "time_range_end",
                "pattern_score",
            ],
        )
    )
    md.append("## خانواده‌ها (۴h و ۵m)")
    md.append(
        _df_markdown(
            df_families[
                [
                    "family_id",
                    "timeframe",
                    "member_count",
                    "window_sizes",
                    "pattern_types",
                    "agg_support",
                    "agg_lift",
                    "agg_stability",
                    "strength_level",
                    "family_score",
                ]
            ],
            [
                "family_id",
                "timeframe",
                "member_count",
                "window_sizes",
                "pattern_types",
                "agg_support",
                "agg_lift",
                "agg_stability",
                "strength_level",
                "family_score",
            ],
        )
    )
    md.append("## توضیحات کیفی کوتاه")
    md.append("- چند الگوی شاخص بر اساس pattern_score بالاتر مرتب شده‌اند و در جدول بالا قابل مشاهده‌اند.")
    md.append("- خانواده‌های strong عمدتا lift بالاتر از ۱ و پایداری مثبت دارند.")

    md.append("\n---\n")
    md.append("# Full Pattern & Relation Inventory – v1.0.0 (EN)")
    md.append(f"- Generated at: {now}")
    md.append("- Generator: Codex Full Pattern & Relation Inventory Reporter")
    md.append("## Data sources")
    md.append(f"- Level-1 pattern tables: {meta_sources.get('pattern_tables', [])}")
    md.append(f"- Family tables: {meta_sources.get('family_tables', [])}")
    md.append(f"- Time ranges from raw OHLCV: {global_ranges}")
    md.append("## Scoring and base_type logic")
    md.append(
        "- pattern_score = 0.5*max(lift-1,0) + 0.3*log(support+1) + 0.2*max(stability,0); strong patterns get a 5% boost."
    )
    md.append(
        "- family_score = 0.5*max(agg_lift-1,0) + 0.3*log(agg_support+1) + 0.2*max(agg_stability,0); boost 10% for strong, 5% for medium."
    )
    md.append(
        "- base_type rule: sequence/candle_shape with direction target → direction; targets mentioning return/ret/pnl → value; direction+value cues in definition/notes → mixed; else other."
    )
    md.append("## Overall stats")
    md.append(
        f"- Patterns: 4h={len(pat_4h)} | 5m={len(pat_5m)}; Families: 4h={len(fam_4h)} | 5m={len(fam_5m)}"
    )
    md.append(
        f"- pattern_type distribution: 4h[{_distribution_text(pat_4h, 'pattern_type')}] | 5m[{_distribution_text(pat_5m, 'pattern_type')}]"
    )
    md.append(
        f"- base_type distribution: 4h[{_distribution_text(pat_4h, 'base_type')}] | 5m[{_distribution_text(pat_5m, 'base_type')}]"
    )
    md.append(
        f"- strength_level distribution: 4h[{_distribution_text(fam_4h, 'strength_level')}] | 5m[{_distribution_text(fam_5m, 'strength_level')}]"
    )
    md.append("## 4h patterns")
    md.append(
        _df_markdown(
            pat_4h[
                [
                    "id",
                    "window_size",
                    "pattern_type",
                    "base_type",
                    "support",
                    "sample_candles",
                    "lift",
                    "stability",
                    "time_range_start",
                    "time_range_end",
                    "pattern_score",
                ]
            ],
            [
                "id",
                "window_size",
                "pattern_type",
                "base_type",
                "support",
                "sample_candles",
                "lift",
                "stability",
                "time_range_start",
                "time_range_end",
                "pattern_score",
            ],
        )
    )
    md.append("## 5m patterns")
    md.append(
        _df_markdown(
            pat_5m[
                [
                    "id",
                    "window_size",
                    "pattern_type",
                    "base_type",
                    "support",
                    "sample_candles",
                    "lift",
                    "stability",
                    "time_range_start",
                    "time_range_end",
                    "pattern_score",
                ]
            ],
            [
                "id",
                "window_size",
                "pattern_type",
                "base_type",
                "support",
                "sample_candles",
                "lift",
                "stability",
                "time_range_start",
                "time_range_end",
                "pattern_score",
            ],
        )
    )
    md.append("## Families")
    md.append(
        _df_markdown(
            df_families[
                [
                    "family_id",
                    "timeframe",
                    "member_count",
                    "window_sizes",
                    "pattern_types",
                    "agg_support",
                    "agg_lift",
                    "agg_stability",
                    "strength_level",
                    "family_score",
                ]
            ],
            [
                "family_id",
                "timeframe",
                "member_count",
                "window_sizes",
                "pattern_types",
                "agg_support",
                "agg_lift",
                "agg_stability",
                "strength_level",
                "family_score",
            ],
        )
    )
    md.append("## Qualitative notes")
    md.append("- Highlighted patterns/families are ordered by score in the tables above.")
    md.append("- Where per-pattern date ranges were unavailable, global timeframe ranges were used.")
    return "\n".join(md)


def save_markdown_report(markdown_text: str) -> None:
    """
    - Ensure directory project/DOCUMENTS/ exists.
    - Save:
        project/DOCUMENTS/PrisonBreaker_FullPatternInventory_v1_FA.md
    """
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(markdown_text, encoding="utf-8")


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
def run_full_pattern_inventory_report():
    """
    - Load patterns and families.
    - Infer time ranges.
    - Classify base types.
    - Compute scores.
    - Save inventories to Parquet.
    - Build and save the Markdown report.
    - Print a concise console summary.
    """
    patterns_raw = load_level1_patterns()
    families_raw = load_families()

    kb_index = _load_pattern_kb()
    patterns = _attach_pattern_ids(patterns_raw, kb_index)
    patterns = classify_base_types(patterns)
    patterns = compute_pattern_scores(patterns)

    families = families_raw.copy()
    families = _map_family_members(families, patterns)
    patterns, families = infer_time_ranges(patterns, families)
    families = compute_family_scores(families)

    save_parquet_inventories(patterns, families)

    meta_info = {
        "sources": {
            "pattern_tables": [
                str(path) for paths in PATTERN_PRIORITY.values() for path in paths if path.exists()
            ],
            "family_tables": [str(p) for p in FAMILY_FILES if p.exists()],
        },
        "time_ranges": {
            tf: {
                "start": str(start),
                "end": str(end),
            }
            for tf, (start, end) in {
                tf: (
                    patterns[patterns["timeframe"] == tf]["time_range_start"].min(),
                    patterns[patterns["timeframe"] == tf]["time_range_end"].max(),
                )
                for tf in patterns["timeframe"].dropna().unique()
            }.items()
        },
    }

    report = build_bilingual_markdown_report(patterns, families, meta_info)
    save_markdown_report(report)

    pat_counts = patterns.groupby(["timeframe", "pattern_type"]).size().reset_index(name="n")
    fam_counts = families.groupby(["timeframe", "strength_level"]).size().reset_index(name="n")

    print("[patterns] counts by timeframe and pattern_type:")
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
