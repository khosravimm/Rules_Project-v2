from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml


def _apply_conditions(
    df: pd.DataFrame,
    conditions: List[Dict[str, Any]],
    *,
    pattern_id: str = "",
) -> pd.Series:
    """
    Given a DataFrame and a list of condition dicts, return a boolean Series
    that is True where all conditions are satisfied.

    Supported operators:
      - "==", "!=", ">", ">=", "<", "<=", "in"
    The "in" operator expects `value` to be a list or set.
    """
    mask = pd.Series(True, index=df.index)
    for cond in conditions:
        feature = cond["feature"]
        op = cond["operator"]
        val = cond["value"]

        if feature not in df.columns:
            prefix = f"[{pattern_id}] " if pattern_id else ""
            raise RuntimeError(f"{prefix}Missing feature '{feature}' required for pattern evaluation.")

        series = df[feature]

        if op == "==":
            mask &= series == val
        elif op == "!=":
            mask &= series != val
        elif op == ">":
            mask &= series > val
        elif op == ">=":
            mask &= series >= val
        elif op == "<":
            mask &= series < val
        elif op == "<=":
            mask &= series <= val
        elif op == "in":
            mask &= series.isin(val)
        else:
            raise ValueError(f"Unsupported operator '{op}' in pattern conditions.")

    return mask


def evaluate_4h_patterns(
    features_path: str = "data/btcusdt_4h_features.parquet",
    patterns_yaml: str = "kb/rules_4h_patterns.yaml",
    output_stats_parquet: str = "data/btcusdt_4h_patterns_stats.parquet",
    output_perf_yaml: str = "kb/rules_4h_patterns_performance.yaml",
    min_support: int = 20,
) -> None:
    """
    Evaluate all 4h directional patterns defined in rules_4h_patterns.yaml
    on the BTCUSDT 4h feature dataset and store the performance metrics.

    - Loads the features DataFrame from `features_path`.
    - Loads the patterns list from `patterns_yaml` (YAML).
    - For each pattern, builds a boolean mask over the DataFrame according to
      the pattern.conditions list.
    - Computes support and basic performance metrics for the pattern.
    - Saves:
        - A tabular summary as Parquet to `output_stats_parquet`.
        - A KB-friendly YAML summary (per pattern id) to `output_perf_yaml`.
    """
    features_df = pd.read_parquet(features_path)

    data = yaml.safe_load(Path(patterns_yaml).read_text(encoding="utf-8"))
    patterns = data.get("patterns", []) if isinstance(data, dict) else []
    if not patterns:
        return

    rows: List[Dict[str, Any]] = []

    default_target = "DIR_4H_NEXT"
    for pattern in patterns:
        pattern_id = pattern.get("id", "")
        target_col = pattern.get("target", default_target)
        conditions = pattern.get("conditions", [])

        y_all = features_df[target_col] if target_col in features_df else pd.Series([], dtype=float)
        n_up_all = int((y_all > 0).sum())
        n_down_all = int((y_all < 0).sum())
        n_eff_all = n_up_all + n_down_all
        baseline_win_rate = n_up_all / n_eff_all if n_eff_all > 0 else None

        try:
            mask = _apply_conditions(features_df, conditions, pattern_id=pattern_id)
            df_pat = features_df[mask].copy()
            support = len(df_pat)

            y = df_pat[target_col] if target_col in df_pat else pd.Series([], dtype=float)
            n_up = int((y > 0).sum())
            n_down = int((y < 0).sum())
            n_flat = int((y == 0).sum())
            n_pos = n_up
            n_neg = n_down
            n_eff = n_pos + n_neg

            win_rate = n_pos / n_eff if n_eff > 0 else None
            avg_ret = (
                float(df_pat["RET_4H_NEXT"].mean())
                if "RET_4H_NEXT" in df_pat and not df_pat.empty
                else None
            )

            if support < min_support:
                status_hint = "too_rare"
            elif n_eff == 0:
                status_hint = "no_signal"
            elif baseline_win_rate is not None and win_rate is not None:
                if win_rate >= baseline_win_rate + 0.10:
                    status_hint = "strong"
                elif win_rate >= baseline_win_rate + 0.05:
                    status_hint = "medium"
                else:
                    status_hint = "weak"
            else:
                status_hint = "weak"
        except RuntimeError:
            support = 0
            n_up = n_down = n_flat = n_eff = 0
            win_rate = None
            avg_ret = None
            status_hint = "missing_feature"

        rows.append(
            {
                "pattern_id": pattern_id,
                "timeframe": pattern.get("timeframe", "4h"),
                "window_length": pattern.get("window_length"),
                "support": support,
                "n_up": n_up,
                "n_down": n_down,
                "n_flat": n_flat,
                "n_eff": n_eff,
                "win_rate": win_rate,
                "avg_ret": avg_ret,
                "baseline_win_rate": baseline_win_rate,
                "status_hint": status_hint,
            }
        )

    stats_df = pd.DataFrame(rows)
    stats_df.to_parquet(output_stats_parquet, index=False)

    perf_kb: Dict[str, Any] = {
        "meta": {
            "source_patterns_file": patterns_yaml,
            "features_file": features_path,
            "generated_at": datetime.utcnow().isoformat(),
            "min_support": min_support,
        },
        "patterns": [],
    }

    for row in rows:
        perf_kb["patterns"].append(
            {
                "id": row["pattern_id"],
                "timeframe": row["timeframe"],
                "window_length": row["window_length"],
                "support": int(row["support"]),
                "n_up": int(row["n_up"]),
                "n_down": int(row["n_down"]),
                "n_flat": int(row["n_flat"]),
                "n_eff": int(row["n_eff"]),
                "win_rate": float(row["win_rate"]) if row["win_rate"] is not None else None,
                "avg_ret": float(row["avg_ret"]) if row["avg_ret"] is not None else None,
                "baseline_win_rate": (
                    float(row["baseline_win_rate"]) if row["baseline_win_rate"] is not None else None
                ),
                "status_hint": row["status_hint"],
            }
        )

    with open(output_perf_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(perf_kb, f, sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    evaluate_4h_patterns()
