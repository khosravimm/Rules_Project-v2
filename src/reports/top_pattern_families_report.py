from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "project" / "DOCUMENTS"

FAMILY_PATHS = {
    "4h": DATA_DIR / "pattern_families_4h.parquet",
    "5m": DATA_DIR / "pattern_families_5m.parquet",
}

REPORT_PATH = DOCS_DIR / "PrisonBreaker_TopPatternFamilies_v1_FA.md"


# -----------------------------------------------------------------------------
# Loading
# -----------------------------------------------------------------------------
def load_family_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load pattern family parquet files for 4h and 5m.
    Raises FileNotFoundError if required files are missing.
    """
    missing = [p for p in FAMILY_PATHS.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing family parquet files: {missing}")

    df_4h = pd.read_parquet(FAMILY_PATHS["4h"])
    df_5m = pd.read_parquet(FAMILY_PATHS["5m"])
    return df_4h, df_5m


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------
def compute_family_scores(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Add a 'family_score' column based on explicit weights.

    Scoring rule (documented for transparency):
      lift_norm      = max(agg_lift - 1.0, 0.0)
      support_norm   = log(agg_support + 1.0)
      stability_norm = max(agg_stability, 0) if not NaN else 0
      weights: w_lift=0.5, w_support=0.3, w_stability=0.2
      family_score   = w_lift*lift_norm + w_support*support_norm + w_stability*stability_norm
      boost: if strength_level == "strong": family_score *= 1.1
    """
    df = df.copy()
    # Normalize column names for downstream tables.
    if "dominant_window_sizes" in df.columns:
        df["window_sizes"] = df["dominant_window_sizes"]
    if "dominant_pattern_types" in df.columns:
        df["pattern_types"] = df["dominant_pattern_types"]
    df["lift_norm"] = (df["agg_lift"] - 1.0).clip(lower=0.0)
    df["support_norm"] = np.log(df["agg_support"] + 1.0)
    df["stability_norm"] = df["agg_stability"].apply(lambda x: max(x, 0.0) if not pd.isna(x) else 0.0)

    w_lift, w_support, w_stability = 0.5, 0.3, 0.2
    df["family_score"] = (
        w_lift * df["lift_norm"]
        + w_support * df["support_norm"]
        + w_stability * df["stability_norm"]
    )
    df.loc[df["strength_level"] == "strong", "family_score"] *= 1.1
    df["timeframe"] = timeframe
    return df


def select_top_families(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    Filter to strong/medium if available, sort by family_score desc, and return top_n.
    """
    df = df.copy()
    if "strength_level" in df.columns:
        df = df[df["strength_level"].isin(["strong", "medium", "weak"])]
    df = df.sort_values("family_score", ascending=False)
    return df.head(top_n).reset_index(drop=True)


# -----------------------------------------------------------------------------
# Reporting helpers
# -----------------------------------------------------------------------------
def _table_markdown(df: pd.DataFrame, cols: Dict[str, str]) -> str:
    """Return a markdown table string selecting and renaming columns."""
    if df.empty:
        return "_جدولی موجود نیست / No data_"
    sub = df[list(cols.keys())].rename(columns=cols)
    headers = list(sub.columns)
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, row in sub.iterrows():
        vals = [str(row[h]) for h in headers]
        lines.append("|" + "|".join(vals) + "|")
    return "\n".join(lines)


def _family_comment(row: pd.Series, lang: str = "fa") -> str:
    """Generate a short qualitative comment per family using its fields."""
    pt = ",".join(map(str, row["pattern_types"]))
    ws = ",".join(map(str, row["window_sizes"]))
    if lang == "fa":
        return (
            f"خانواده {row['family_id']} با نوع الگو {pt} و طول‌های پنجره {ws}، "
            f"قدرت (lift) حدود {row['agg_lift']:.2f} و پشتیبانی {int(row['agg_support'])} دارد."
        )
    return (
        f"Family {row['family_id']} ({pt}, windows {ws}) shows lift≈{row['agg_lift']:.2f} "
        f"with support {int(row['agg_support'])}."
    )


def build_bilingual_markdown_report(
    top_4h: pd.DataFrame,
    top_5m: pd.DataFrame,
    global_stats: Dict[str, Dict[str, int]],
    meta: Dict[str, str],
) -> str:
    now = meta.get("date_iso", datetime.utcnow().isoformat())
    scoring_desc = (
        "فرمول امتیاز: family_score = 0.5*max(lift-1,0) + 0.3*log(support+1) + "
        "0.2*max(stability,0) و برای خانواده‌های strong، امتیاز ۱۰٪ تقویت شده است."
    )
    scoring_desc_en = (
        "Score formula: family_score = 0.5*max(lift-1,0) + 0.3*log(support+1) + "
        "0.2*max(stability,0); strong families get a 10% boost."
    )

    table_4h = _table_markdown(
        top_4h,
        {
            "family_id": "family_id",
            "window_sizes": "window_sizes",
            "pattern_types": "pattern_types",
            "agg_support": "support",
            "agg_lift": "lift",
            "agg_stability": "stability",
            "strength_level": "strength",
            "family_score": "score",
        },
    )
    table_5m = _table_markdown(
        top_5m,
        {
            "family_id": "family_id",
            "window_sizes": "window_sizes",
            "pattern_types": "pattern_types",
            "agg_support": "support",
            "agg_lift": "lift",
            "agg_stability": "stability",
            "strength_level": "strength",
            "family_score": "score",
        },
    )

    # pick a few comments (up to 5 from each set)
    comments_fa = []
    comments_en = []
    for df in (top_4h.head(3), top_5m.head(3)):
        for _, r in df.iterrows():
            comments_fa.append(f"- {_family_comment(r, lang='fa')}")
            comments_en.append(f"- {_family_comment(r, lang='en')}")

    md = []
    md.append(f"# گزارش خانواده‌های الگو (Top Pattern Families) – نسخه v1.0.0\nتاریخ: {now}\nماژول: Codex Report Engine\nمنبع: الگوهای سطح ۱ و خانواده‌ها (Parquet/YAML)\n")
    md.append("## خلاصهٔ اجرایی\n")
    md.append(
        f"- ۴ ساعته: strong={global_stats['4h'].get('strong',0)}, medium={global_stats['4h'].get('medium',0)}, weak={global_stats['4h'].get('weak',0)}\n"
        f"- ۵ دقیقه: strong={global_stats['5m'].get('strong',0)}, medium={global_stats['5m'].get('medium',0)}, weak={global_stats['5m'].get('weak',0)}\n"
        f"- تعداد خانواده‌های انتخاب‌شده برای بررسی: ۴h={len(top_4h)}, ۵m={len(top_5m)}"
    )
    md.append("\n## روش امتیازدهی\n")
    md.append(f"- {scoring_desc}\n")
    md.append("\n## جدول خانواده‌های برتر ۴ ساعته\n")
    md.append(table_4h)
    md.append("\n## جدول خانواده‌های برتر ۵ دقیقه\n")
    md.append(table_5m)
    md.append("\n## توضیحات کیفی کوتاه\n")
    md.extend(comments_fa)

    md.append("\n\n---\n\n")
    md.append("# Pattern Families Report – v1.0.0 (EN)\nDate: {0}\nModule: Codex Report Engine\nSource: Level-1 patterns & families (Parquet/YAML)\n".format(now))
    md.append("## Executive Summary\n")
    md.append(
        f"- 4h: strong={global_stats['4h'].get('strong',0)}, medium={global_stats['4h'].get('medium',0)}, weak={global_stats['4h'].get('weak',0)}\n"
        f"- 5m: strong={global_stats['5m'].get('strong',0)}, medium={global_stats['5m'].get('medium',0)}, weak={global_stats['5m'].get('weak',0)}\n"
        f"- Selected families for review: 4h={len(top_4h)}, 5m={len(top_5m)}"
    )
    md.append("\n## Scoring Method\n")
    md.append(f"- {scoring_desc_en}\n")
    md.append("\n## Top 4h Families\n")
    md.append(table_4h)
    md.append("\n## Top 5m Families\n")
    md.append(table_5m)
    md.append("\n## Qualitative Notes\n")
    md.extend(comments_en)

    md.append("\n## Recommendations\n- Promote strong families to Rulebook candidates; run targeted backtests.\n- Revisit medium families with more regime-aware filters.\n- Monitor weak families for drift; archive if stability declines further.\n")
    return "\n".join(md)


def save_report(markdown_text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_text, encoding="utf-8")


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
def run_top_pattern_families_report(top_n: int = 20) -> None:
    df4, df5 = load_family_data()
    print(f"[load] 4h families: {len(df4)}, 5m families: {len(df5)}")

    df4 = compute_family_scores(df4, "4h")
    df5 = compute_family_scores(df5, "5m")

    global_stats = {
        "4h": df4["strength_level"].value_counts().to_dict() if "strength_level" in df4.columns else {},
        "5m": df5["strength_level"].value_counts().to_dict() if "strength_level" in df5.columns else {},
    }

    top4 = select_top_families(df4, top_n=top_n)
    top5 = select_top_families(df5, top_n=top_n)
    print(f"[select] top4h={len(top4)}, top5m={len(top5)}")

    meta = {"date_iso": datetime.utcnow().isoformat()}
    report = build_bilingual_markdown_report(top4, top5, global_stats, meta)
    save_report(report, REPORT_PATH)
    print(f"[save] report -> {REPORT_PATH}")
    print(
        "Top Pattern Families Report generated:\n"
        " - project/DOCUMENTS/PrisonBreaker_TopPatternFamilies_v1_FA.md\n"
        " - ranked families for 4h and 5m with scores and summaries."
    )


if __name__ == "__main__":
    run_top_pattern_families_report()
