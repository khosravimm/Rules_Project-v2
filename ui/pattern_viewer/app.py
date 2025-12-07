from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import dash
from dash import Dash, html
from flask import request, jsonify

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
HITS_PART_DIR = {
    "4h": DATA_DIR / "pattern_hits_4h_level1_partitioned",
    "5m": DATA_DIR / "pattern_hits_5m_level1_partitioned",
}
HITS_RAW_PATH = {
    "4h": DATA_DIR / "pattern_hits_4h_level1.parquet",
    "5m": DATA_DIR / "pattern_hits_5m_level1.parquet",
}
PATTERNS_PATH = {
    "4h": DATA_DIR / "patterns_4h_raw_level1.parquet",
    "5m": DATA_DIR / "patterns_5m_raw_level1.parquet",
}
FAMILIES_PATH = {
    "4h": DATA_DIR / "pattern_families_4h.parquet",
    "5m": DATA_DIR / "pattern_families_5m.parquet",
}
CANDLES_PATH = {
    "4h": DATA_DIR / "btcusdt_4h_raw.parquet",
    "5m": DATA_DIR / "btcusdt_5m_raw.parquet",
}

HARD_DRAW_CAP = 500
DEFAULT_MAX_HITS = 200
TIMEFRAMES = ["4h", "5m"]

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _assert_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"[ERROR] Missing {label}: {path}")


def load_candles(timeframe: str) -> pd.DataFrame:
    path = CANDLES_PATH[timeframe]
    _assert_exists(path, f"candles {timeframe}")
    df = pd.read_parquet(path)
    time_col = "open_time" if "open_time" in df.columns else "timestamp"
    df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)
    df["time_col"] = time_col
    return df


def _stable_pattern_id(row: pd.Series) -> str:
    base = f"{row.get('timeframe','?')}|{row.get('pattern_type','?')}|{row.get('window_size','?')}|{row.get('definition','?')}"
    return f"pat_{abs(hash(base)) % 10_000_000}"


def _compute_score(df: pd.DataFrame) -> pd.DataFrame:
    if "score" in df.columns:
        return df
    df = df.copy()
    df["score"] = (
        0.5 * np.maximum(df["lift"] - 1.0, 0.0)
        + 0.3 * np.log(df["support"] + 1.0)
        + 0.2 * np.maximum(df["stability"], 0.0)
    )
    return df


def load_patterns(timeframe: str) -> pd.DataFrame:
    path = PATTERNS_PATH[timeframe]
    _assert_exists(path, f"patterns {timeframe}")
    df = pd.read_parquet(path)
    df = _compute_score(df)
    if "pattern_id" not in df.columns:
        df["pattern_id"] = df.apply(_stable_pattern_id, axis=1)
    return df


def load_families(timeframe: str) -> Optional[pd.DataFrame]:
    path = FAMILIES_PATH[timeframe]
    if not path.exists():
        print(f"[WARN] family file missing for {timeframe}")
        return None
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
CANDLES: Dict[str, pd.DataFrame] = {tf: load_candles(tf) for tf in TIMEFRAMES}
PATTERNS: Dict[str, pd.DataFrame] = {tf: load_patterns(tf) for tf in TIMEFRAMES}
FAMILIES: Dict[str, Optional[pd.DataFrame]] = {tf: load_families(tf) for tf in TIMEFRAMES}
FAMILY_AVAILABLE = any(f is not None and not f.empty for f in FAMILIES.values())

for tf in TIMEFRAMES:
    print(f"[LOAD] timeframe={tf} candles={len(CANDLES[tf])} patterns={len(PATTERNS[tf])}")


# ---------------------------------------------------------------------------
# Helpers for hits loading and filtering
# ---------------------------------------------------------------------------


def _month_range(start: pd.Timestamp, end: pd.Timestamp) -> List[Tuple[int, int]]:
    months = []
    cur = pd.Timestamp(year=start.year, month=start.month, day=1, tz=start.tz)
    end_anchor = pd.Timestamp(year=end.year, month=end.month, day=1, tz=end.tz)
    while cur <= end_anchor:
        months.append((cur.year, cur.month))
        cur = cur + pd.DateOffset(months=1)
    return months


def apply_static_filters_to_hits(hits_df: pd.DataFrame, base_filters: dict) -> pd.DataFrame:
    if hits_df.empty:
        return hits_df
    df = hits_df
    pt = base_filters.get("pattern_types", [])
    ws_min, ws_max = base_filters.get("ws_range", (2, 11))
    lift_min, lift_max = base_filters.get("lift_range", (0.0, 10.0))
    stab_min, stab_max = base_filters.get("stab_range", (0.0, 1.0))
    sup_min, sup_max = base_filters.get("sup_range", (0, 1_000_000))
    allowlist = base_filters.get("allowlist", True)
    pattern_ids = base_filters.get("pattern_ids", [])
    family_ids = base_filters.get("family_ids", [])
    view_mode = base_filters.get("view_mode", "pattern")
    strength_filter = base_filters.get("strengths", [])

    if pt:
        df = df[df["pattern_type"].isin(pt)]
    df = df[(df["window_size"] >= ws_min) & (df["window_size"] <= ws_max)]
    df = df[(df["lift"] >= lift_min) & (df["lift"] <= lift_max)]
    df = df[(df["stability"] >= stab_min) & (df["stability"] <= stab_max)]
    df = df[(df["support"] >= sup_min) & (df["support"] <= sup_max)]
    if strength_filter:
        df = df[df["strength"].isin(strength_filter)]

    if view_mode == "family":
        if family_ids:
            df = df[df["family_id"].isin(family_ids)]
        else:
            return df.iloc[0:0]
    else:
        if pattern_ids:
            if allowlist:
                df = df[df["pattern_id"].isin(pattern_ids)]
            else:
                df = df[~df["pattern_id"].isin(pattern_ids)]
        if family_ids:
            df = df[df["family_id"].isin(family_ids)]
    return df


def load_hits_for_timerange(
    timeframe: str,
    start_time,
    end_time,
    base_filters: dict,
) -> pd.DataFrame:
    part_dir = HITS_PART_DIR[timeframe]
    start_ts = pd.to_datetime(start_time)
    end_ts = pd.to_datetime(end_time)
    df = pd.DataFrame()
    if part_dir.exists():
        ym = _month_range(start_ts, end_ts)
        years = sorted({y for y, _ in ym})
        months = sorted({m for _, m in ym})
        dataset = ds.dataset(part_dir, format="parquet")
        expr = (ds.field("year").isin(years)) & (ds.field("month").isin(months))
        table = dataset.to_table(filter=expr)
        df = table.to_pandas()
    else:
        raw_path = HITS_RAW_PATH[timeframe]
        if raw_path.exists():
            df = pd.read_parquet(raw_path)

    if df.empty:
        print(f"[hits-load] timeframe={timeframe} range=({start_ts},{end_ts}) -> loaded=0")
        return df

    df["answer_time"] = pd.to_datetime(df["answer_time"], utc=True, errors="coerce")
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
    df = df[(df["end_time"] >= start_ts) & (df["start_time"] <= end_ts)]
    df = apply_static_filters_to_hits(df, base_filters)
    print(f"[hits-load] timeframe={timeframe} range=({start_ts},{end_ts}) -> loaded={len(df)} rows")
    return df


def limit_hits_for_render(hits_df: pd.DataFrame, max_hits: Optional[int]) -> pd.DataFrame:
    if hits_df.empty:
        return hits_df
    limit = max_hits if max_hits is not None else DEFAULT_MAX_HITS
    limit = HARD_DRAW_CAP if (limit <= 0 or limit > HARD_DRAW_CAP) else limit
    sort_cols = [c for c in ["score", "support", "stability"] if c in hits_df.columns]
    if sort_cols:
        hits_df = hits_df.sort_values(sort_cols, ascending=[False] * len(sort_cols))
    return hits_df.head(limit)


# ---------------------------------------------------------------------------
# Dash app (minimal layout) and Flask routes for API
# ---------------------------------------------------------------------------
app: Dash = dash.Dash(__name__)
server = app.server
app.title = "PrisonBreaker – Pattern Viewer API"
app.layout = html.Div(
    [
        html.H4("PrisonBreaker Pattern Viewer API"),
        html.Div("This Dash server only serves JSON for the TradingView frontend."),
    ]
)


@server.route("/api/candles", methods=["GET"])
def api_candles():
    timeframe = request.args.get("timeframe", "4h")
    if timeframe not in TIMEFRAMES:
        return jsonify({"error": "unsupported timeframe"}), 400
    start = request.args.get("start")
    end = request.args.get("end")
    df = CANDLES[timeframe]
    time_col = df["time_col"].iloc[0]
    if start:
        df = df[df[time_col] >= pd.to_datetime(start, utc=True)]
    if end:
        df = df[df[time_col] <= pd.to_datetime(end, utc=True)]
    candles = []
    for _, row in df.iterrows():
        candles.append(
            {
                "time": pd.to_datetime(row[time_col]).isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]) if "volume" in row else None,
            }
        )
    return jsonify({"symbol": "BTCUSDT", "timeframe": timeframe, "candles": candles})


@server.route("/api/pattern_hits", methods=["GET"])
def api_pattern_hits():
    timeframe = request.args.get("timeframe", "4h")
    if timeframe not in TIMEFRAMES:
        return jsonify({"error": "unsupported timeframe"}), 400
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"error": "start and end are required"}), 400
    pattern_ids = request.args.get("pattern_ids", "")
    family_ids = request.args.get("family_ids", "")
    pattern_types = request.args.get("pattern_types", "")
    strengths = request.args.get("strengths", "")
    ws_min = float(request.args.get("ws_min", 2))
    ws_max = float(request.args.get("ws_max", 11))
    lift_min = float(request.args.get("lift_min", 0))
    lift_max = float(request.args.get("lift_max", 5))
    stab_min = float(request.args.get("stab_min", 0))
    stab_max = float(request.args.get("stab_max", 1))
    sup_min = float(request.args.get("sup_min", 0))
    sup_max = float(request.args.get("sup_max", 1000000))
    allowlist = request.args.get("allowlist", "true").lower() != "false"
    view_mode = request.args.get("view_mode", "pattern")
    max_hits = int(request.args.get("max_hits", DEFAULT_MAX_HITS))

    base_filters = {
        "pattern_types": [p for p in pattern_types.split(",") if p] if pattern_types else [],
        "ws_range": (ws_min, ws_max),
        "lift_range": (lift_min, lift_max),
        "stab_range": (stab_min, stab_max),
        "sup_range": (sup_min, sup_max),
        "allowlist": allowlist,
        "pattern_ids": [p for p in pattern_ids.split(",") if p],
        "family_ids": [f for f in family_ids.split(",") if f],
        "strengths": [s for s in strengths.split(",") if s],
        "view_mode": view_mode,
    }
    hits_loaded = load_hits_for_timerange(timeframe, start, end, base_filters)
    hits_draw = limit_hits_for_render(hits_loaded, max_hits)
    hits_json = []
    for _, row in hits_draw.iterrows():
        hits_json.append(
            {
                "pattern_id": row.get("pattern_id") or row.get("id"),
                "pattern_type": row.get("pattern_type"),
                "window_size": int(row.get("window_size")),
                "family_id": row.get("family_id"),
                "strength": row.get("strength"),
                "start_time": row.get("start_time").isoformat() if pd.notna(row.get("start_time")) else None,
                "end_time": row.get("end_time").isoformat() if pd.notna(row.get("end_time")) else None,
                "answer_time": row.get("answer_time").isoformat() if pd.notna(row.get("answer_time")) else None,
                "support": int(row.get("support")),
                "lift": float(row.get("lift")),
                "stability": float(row.get("stability")),
                "score": float(row.get("score")),
            }
        )
    return jsonify({"symbol": "BTCUSDT", "timeframe": timeframe, "hits": hits_json})


@server.route("/api/pattern_meta", methods=["GET"])
def api_pattern_meta():
    patterns_list: List[dict] = []
    families_list: List[dict] = []
    for tf, df in PATTERNS.items():
        for _, row in df.iterrows():
            patterns_list.append(
                {
                    "pattern_id": row.get("pattern_id"),
                    "timeframe": tf,
                    "pattern_type": row.get("pattern_type"),
                    "window_size": int(row.get("window_size")),
                    "support": int(row.get("support")),
                    "lift": float(row.get("lift")),
                    "stability": float(row.get("stability")),
                    "score": float(row.get("score")),
                }
            )
    for tf, fam in FAMILIES.items():
        if fam is None or fam.empty:
            continue
        for _, row in fam.iterrows():
            families_list.append(
                {
                    "family_id": row.get("family_id"),
                    "timeframe": tf,
                    "strength": row.get("strength_level") or row.get("strength"),
                    "member_count": len(row.get("member_keys", []))
                    if isinstance(row.get("member_keys"), (list, np.ndarray))
                    else None,
                }
            )
    return jsonify({"patterns": patterns_list, "families": families_list, "family_available": FAMILY_AVAILABLE})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=False)
