from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

PATTERN_PATHS = {
    "4h": DATA_DIR / "patterns_4h_raw_level1.parquet",
    "5m": DATA_DIR / "patterns_5m_raw_level1.parquet",
}
FAMILY_PATHS = {
    "4h": DATA_DIR / "pattern_families_4h.parquet",
    "5m": DATA_DIR / "pattern_families_5m.parquet",
}

REPORT_FA = DOCS_DIR / "PrisonBreaker_FullPatternInventory_v2_FA.md"
REPORT_EN = DOCS_DIR / "PrisonBreaker_FullPatternInventory_v2_EN.md"


# -----------------------------------------------------------------------------
# Loading helpers
# -----------------------------------------------------------------------------
def load_patterns(path: str) -> pd.DataFrame:
    """
    Load a parquet file with level-1 patterns.
    Ensure required columns exist: timeframe, window_size, pattern_type, support, lift, stability.
    Return a pandas DataFrame.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Missing pattern file: {path}")
    df = pd.read_parquet(p)
    required = ["timeframe", "window_size", "pattern_type", "support", "lift", "stability"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Pattern file {path} missing required columns: {missing}")
    return df


def load_families(path: str) -> Optional[pd.DataFrame]:
    """
    Try to read a parquet file with family-level patterns.
    If the file does not exist, return None.
    If it exists, return a DataFrame.
    """
    p = Path(path)
    if not p.exists():
        return None
    return pd.read_parquet(p)


# -----------------------------------------------------------------------------
# Aggregations
# -----------------------------------------------------------------------------
def _score_patterns(df: pd.DataFrame) -> pd.DataFrame:
    if "score" in df.columns:
        return df
    score_col = "pattern_score" if "pattern_score" in df.columns else None
    if score_col:
        df["score"] = df[score_col]
        return df
    df = df.copy()
    df["score"] = (
        0.5 * np.maximum(df["lift"] - 1.0, 0.0)
        + 0.3 * np.log(df["support"] + 1.0)
        + 0.2 * np.maximum(df["stability"], 0.0)
    )
    return df


def summarize_by_window(df_tf: pd.DataFrame) -> pd.DataFrame:
    agg = df_tf.groupby("window_size").agg(
        mean_lift=("lift", "mean"),
        median_lift=("lift", "median"),
        mean_stability=("stability", "mean"),
        median_stability=("stability", "median"),
    )
    return agg.reset_index().sort_values("window_size")


def pattern_counts_by_window(df_tf: pd.DataFrame) -> pd.DataFrame:
    vc = df_tf["window_size"].value_counts().sort_index()
    return vc.reset_index().rename(columns={"index": "window_size", "window_size": "count"})


def pattern_type_distribution(df_tf: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    overall = df_tf["pattern_type"].value_counts().reset_index().rename(
        columns={"index": "pattern_type", "pattern_type": "count"}
    )
    pivot = (
        df_tf.pivot_table(index="window_size", columns="pattern_type", values="definition", aggfunc="count")
        .fillna(0)
        .astype(int)
        .reset_index()
        .sort_values("window_size")
    )
    return overall, pivot


def top_patterns(df_tf: pd.DataFrame, n: int = 200) -> pd.DataFrame:
    df_scored = _score_patterns(df_tf)
    cols = [
        "window_size",
        "pattern_type",
        "support",
        "lift",
        "stability",
        "score",
        "definition",
        "target",
    ]
    present = [c for c in cols if c in df_scored.columns]
    return df_scored[present].sort_values("score", ascending=False).head(n).reset_index(drop=True)


def truncate_definition(definition: str, max_len: int = 80) -> str:
    if len(definition) <= max_len:
        return definition
    return definition[: max_len - 3] + "..."


def families_strength_counts(fam_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    col = "strength_level" if "strength_level" in fam_df.columns else "strength" if "strength" in fam_df.columns else None
    if not col:
        return None
    return fam_df[col].value_counts().reset_index().rename(columns={"index": "strength", col: "count"})


def families_strength_by_type(fam_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    col_strength = "strength_level" if "strength_level" in fam_df.columns else "strength" if "strength" in fam_df.columns else None
    if col_strength is None or "pattern_types" not in fam_df.columns:
        return None
    def _normalize_ptypes(val) -> List[str]:
        if isinstance(val, list):
            return [str(v) for v in val]
        if pd.isna(val):
            return []
        return [str(val)]
    rows = []
    for _, row in fam_df.iterrows():
        ptypes = _normalize_ptypes(row["pattern_types"])
        strength = row[col_strength]
        for pt in ptypes:
            rows.append({"pattern_type": pt, "strength": strength})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    return df.value_counts(["pattern_type", "strength"]).reset_index(name="count")


# -----------------------------------------------------------------------------
# Markdown helpers (no external deps)
# -----------------------------------------------------------------------------
def df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_خالی / Empty_"
    headers = list(df.columns)
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, row in df.iterrows():
        lines.append("|" + "|".join(str(row[h]) for h in headers) + "|")
    return "\n".join(lines)


def build_timeframe_section_fa(tf: str, df_tf: pd.DataFrame, fam_df: Optional[pd.DataFrame]) -> str:
    total = len(df_tf)
    uniq_ws = sorted(df_tf["window_size"].dropna().unique().tolist())
    counts_ws = pattern_counts_by_window(df_tf)
    type_overall, type_pivot = pattern_type_distribution(df_tf)
    lift_summary = summarize_by_window(df_tf)
    tops = top_patterns(df_tf, n=200).copy()
    if "definition" in tops.columns:
        tops["short_definition"] = tops["definition"].apply(truncate_definition)
    tf_title = "۴ ساعته (4h)" if tf == "4h" else "۵ دقیقه‌ای (5m)"

    lines = []
    lines.append(f"## الگوهای تایم‌فریم {tf_title}")
    lines.append(f"- تعداد کل الگوها: {total}")
    lines.append(f"- بازه‌های زمانی (window_size): {uniq_ws}")
    lines.append("\nالگوها به تفکیک window_size:")
    lines.append(df_to_markdown(counts_ws))
    lines.append("\nتوزیع نوع الگو (کل):")
    lines.append(df_to_markdown(type_overall))
    lines.append("\nتوزیع نوع الگو بر حسب window_size:")
    lines.append(df_to_markdown(type_pivot))
    lines.append("\nخلاصه lift و stability بر حسب window_size:")
    lines.append(df_to_markdown(lift_summary))
    top_show = tops.head(10).copy()
    if "short_definition" in top_show.columns:
        columns = [
            "window_size",
            "pattern_type",
            "support",
            "lift",
            "stability",
            "score",
            "short_definition",
        ]
        present = [c for c in columns if c in top_show.columns]
        top_show = top_show[present]
    lines.append("\n۱۰ الگوی برتر بر اساس امتیاز (از میان ۲۰۰ برتر):")
    lines.append(df_to_markdown(top_show))

    if fam_df is not None:
        lines.append("\n### خلاصه خانواده‌ها")
        lines.append(f"- تعداد خانواده‌ها: {len(fam_df)}")
        strength_df = families_strength_counts(fam_df)
        if strength_df is not None:
            lines.append("توزیع قدرت خانواده‌ها:")
            lines.append(df_to_markdown(strength_df))
        strength_type_df = families_strength_by_type(fam_df)
        if strength_type_df is not None:
            lines.append("خانواده‌ها بر حسب نوع الگو و قدرت:")
            lines.append(df_to_markdown(strength_type_df))

    return "\n".join(lines)


def build_timeframe_section_en(tf: str, df_tf: pd.DataFrame, fam_df: Optional[pd.DataFrame]) -> str:
    total = len(df_tf)
    uniq_ws = sorted(df_tf["window_size"].dropna().unique().tolist())
    counts_ws = pattern_counts_by_window(df_tf)
    type_overall, type_pivot = pattern_type_distribution(df_tf)
    lift_summary = summarize_by_window(df_tf)
    tops = top_patterns(df_tf, n=200).copy()
    if "definition" in tops.columns:
        tops["short_definition"] = tops["definition"].apply(truncate_definition)
    tf_title = "4h Timeframe" if tf == "4h" else "5m Timeframe"

    lines = []
    lines.append(f"## {tf_title}")
    lines.append(f"- Total patterns: {total}")
    lines.append(f"- Window sizes: {uniq_ws}")
    lines.append("\nPattern counts per window_size:")
    lines.append(df_to_markdown(counts_ws))
    lines.append("\nPattern type distribution (overall):")
    lines.append(df_to_markdown(type_overall))
    lines.append("\nPattern type distribution by window_size:")
    lines.append(df_to_markdown(type_pivot))
    lines.append("\nLift and stability summary by window_size:")
    lines.append(df_to_markdown(lift_summary))
    top_show = tops.head(10).copy()
    if "short_definition" in top_show.columns:
        columns = [
            "window_size",
            "pattern_type",
            "support",
            "lift",
            "stability",
            "score",
            "short_definition",
        ]
        present = [c for c in columns if c in top_show.columns]
        top_show = top_show[present]
    lines.append("\nTop 10 patterns by score (from top 200):")
    lines.append(df_to_markdown(top_show))

    if fam_df is not None:
        lines.append("\n### Family-level summary")
        lines.append(f"- Total families: {len(fam_df)}")
        strength_df = families_strength_counts(fam_df)
        if strength_df is not None:
            lines.append("Strength distribution:")
            lines.append(df_to_markdown(strength_df))
        strength_type_df = families_strength_by_type(fam_df)
        if strength_type_df is not None:
            lines.append("Families by pattern_type and strength:")
            lines.append(df_to_markdown(strength_type_df))

    return "\n".join(lines)


def build_report_fa(
    patterns_4h: pd.DataFrame,
    patterns_5m: pd.DataFrame,
    families_4h: Optional[pd.DataFrame],
    families_5m: Optional[pd.DataFrame],
) -> str:
    now = datetime.utcnow().isoformat()
    lines = [
        "# گزارش کامل موجودی الگوها – نسخه v2",
        f"- تاریخ: {now}",
        "- ورودی‌ها: data/patterns_4h_raw_level1.parquet, data/patterns_5m_raw_level1.parquet",
        "",
        build_timeframe_section_fa("4h", patterns_4h, families_4h),
        "",
        build_timeframe_section_fa("5m", patterns_5m, families_5m),
    ]
    return "\n".join(lines)


def build_report_en(
    patterns_4h: pd.DataFrame,
    patterns_5m: pd.DataFrame,
    families_4h: Optional[pd.DataFrame],
    families_5m: Optional[pd.DataFrame],
) -> str:
    now = datetime.utcnow().isoformat()
    lines = [
        "# Full Pattern Inventory Report – v2",
        f"- Date: {now}",
        "- Inputs: data/patterns_4h_raw_level1.parquet, data/patterns_5m_raw_level1.parquet",
        "",
        build_timeframe_section_en("4h", patterns_4h, families_4h),
        "",
        build_timeframe_section_en("5m", patterns_5m, families_5m),
    ]
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> None:
    try:
        pat_4h = load_patterns(str(PATTERN_PATHS["4h"]))
        pat_5m = load_patterns(str(PATTERN_PATHS["5m"]))
    except Exception as exc:  # critical, no report
        raise SystemExit(f"[error] failed to load patterns: {exc}")

    fam_4h = load_families(str(FAMILY_PATHS["4h"]))
    fam_5m = load_families(str(FAMILY_PATHS["5m"]))

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    report_fa = build_report_fa(pat_4h, pat_5m, fam_4h, fam_5m)
    report_en = build_report_en(pat_4h, pat_5m, fam_4h, fam_5m)

    REPORT_FA.write_text(report_fa, encoding="utf-8")
    REPORT_EN.write_text(report_en, encoding="utf-8")

    print(f"[OK] Wrote {REPORT_FA}")
    print(f"[OK] Wrote {REPORT_EN}")


if __name__ == "__main__":
    main()
