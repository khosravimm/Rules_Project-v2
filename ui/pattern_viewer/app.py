from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

import dash
from dash import Dash, dcc, html, dash_table, Input, Output, State
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
HITS_PART_DIR = {
    "4h": DATA_DIR / "pattern_hits_4h_level1_partitioned",
    "5m": DATA_DIR / "pattern_hits_5m_level1_partitioned",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _assert_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"[ERROR] Missing {label}: {path}")


def load_candles(timeframe: str) -> pd.DataFrame:
    file_map = {
        "4h": DATA_DIR / "btcusdt_4h_raw.parquet",
        "5m": DATA_DIR / "btcusdt_5m_raw.parquet",
    }
    path = file_map[timeframe]
    _assert_exists(path, f"candles ({timeframe})")
    df = pd.read_parquet(path)
    # Normalize time column; existing code uses open_time
    time_col = "open_time" if "open_time" in df.columns else "timestamp"
    df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)
    df["time_col"] = time_col
    return df


def _stable_pattern_id(row: pd.Series) -> str:
    base = (
        f"{row.get('timeframe','?')}|{row.get('pattern_type','?')}"
        f"|{row.get('window_size','?')}|{row.get('definition','?')}"
    )
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
    path = DATA_DIR / f"patterns_{timeframe}_raw_level1.parquet"
    _assert_exists(path, f"patterns ({timeframe})")
    df = pd.read_parquet(path)
    df = _compute_score(df)
    if "pattern_id" not in df.columns:
        df["pattern_id"] = df.apply(_stable_pattern_id, axis=1)
    df["timeframe"] = timeframe
    return df


def load_pattern_hits(timeframe: str) -> pd.DataFrame:
    path = DATA_DIR / f"pattern_hits_{timeframe}_level1.parquet"
    _assert_exists(path, f"pattern hits ({timeframe})")
    df = pd.read_parquet(path)
    for col in ["answer_time", "start_time", "end_time"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    return df


def load_families(timeframe: str) -> Optional[pd.DataFrame]:
    path = DATA_DIR / f"pattern_families_{timeframe}.parquet"
    if not path.exists():
        print(f"[WARN] Family file missing for {timeframe}: {path}")
        return None
    df = pd.read_parquet(path)
    return df


# ---------------------------------------------------------------------------
# Data in memory
# ---------------------------------------------------------------------------
TIMEFRAMES = ["4h", "5m"]
CANDLES: Dict[str, pd.DataFrame] = {}
PATTERNS: Dict[str, pd.DataFrame] = {}
FAMILIES: Dict[str, Optional[pd.DataFrame]] = {}

for tf in TIMEFRAMES:
    CANDLES[tf] = load_candles(tf)
    PATTERNS[tf] = load_patterns(tf)
    FAMILIES[tf] = load_families(tf)
    print(
        f"[LOAD] timeframe={tf} candles={len(CANDLES[tf])} patterns={len(PATTERNS[tf])}"
    )

def _default_range() -> List[str]:
    df = CANDLES["4h"]
    time_col = df["time_col"].iloc[0]
    if df.empty:
        return []
    end = df[time_col].iloc[-1]
    start_idx = max(len(df) - 42, 0)  # ~7 days of 4h candles
    start = df[time_col].iloc[start_idx]
    return [start.isoformat(), end.isoformat()]


def get_initial_time_range_4h() -> Tuple[pd.Timestamp, pd.Timestamp]:
    df = CANDLES["4h"]
    time_col = df["time_col"].iloc[0]
    if df.empty:
        now = pd.Timestamp.utcnow()
        return now - pd.Timedelta(days=7), now
    end = pd.to_datetime(df[time_col].iloc[-1])
    start_idx = max(len(df) - 42, 0)
    start = pd.to_datetime(df[time_col].iloc[start_idx])
    return start, end


DEFAULT_X_RANGE = _default_range()
# Conservative slider maxima
SUP_MAX = 1000
LIFT_MAX = 5.0
LIFT_MAX_SLIDER = max(5.0, math.ceil(LIFT_MAX))
SUP_MAX_SLIDER = max(1000, int(math.ceil(SUP_MAX / 100.0) * 100))
FAMILY_AVAILABLE = any(f is not None and not f.empty for f in FAMILIES.values())


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------
PTYPE_COLORS = {
    "sequence": "rgba(0,176,246,0.25)",
    "candle_shape": "rgba(250,90,90,0.25)",
    "feature_rule": "rgba(0,200,83,0.25)",
}
STRENGTH_COLORS = {
    "strong": "rgba(255,193,7,0.25)",
    "medium": "rgba(0,184,148,0.25)",
    "weak": "rgba(116,185,255,0.25)",
}
HARD_HIT_CAP = 1000
DEFAULT_MAX_HITS = 100
TABLE_ROW_CAP = 100
DRAW_HARD_CAP = 300


def make_candle_fig(tf: str, x_range: Optional[Tuple[str, str]] = None) -> go.Figure:
    df = CANDLES[tf]
    if x_range and len(x_range) == 2:
        time_col_local = df["time_col"].iloc[0]
        start_ts = pd.to_datetime(x_range[0])
        end_ts = pd.to_datetime(x_range[1])
        df = df[(df[time_col_local] >= start_ts) & (df[time_col_local] <= end_ts)]
    time_col = df["time_col"].iloc[0]
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df[time_col],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name=f"{tf} candles",
                increasing_line_color="rgba(0,200,83,0.8)",
                decreasing_line_color="rgba(250,90,90,0.8)",
            )
        ]
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=40),
        template="plotly_dark",
        height=420 if tf == "4h" else 360,
        xaxis_title="Time",
        yaxis_title="Price",
        dragmode="zoom",
    )
    if x_range:
        fig.update_xaxes(range=x_range)
    return fig


# ---------------------------------------------------------------------------
# Hit filtering and limiting helpers
# ---------------------------------------------------------------------------
def _month_range(start: pd.Timestamp, end: pd.Timestamp) -> List[Tuple[int, int]]:
    months = []
    cur = pd.Timestamp(year=start.year, month=start.month, day=1, tz=start.tz)
    end_anchor = pd.Timestamp(year=end.year, month=end.month, day=1, tz=end.tz)
    while cur <= end_anchor:
        months.append((cur.year, cur.month))
        cur = cur + pd.DateOffset(months=1)
    return months


def load_hits_for_timerange(
    timeframe: str,
    start_time,
    end_time,
    base_filters: dict,
) -> pd.DataFrame:
    """
    Lazily load hits from partitioned parquet for the timeframe and time window.
    """
    part_dir = HITS_PART_DIR[timeframe]
    if not part_dir.exists():
        print(f"[hits-load] missing partition dir for {timeframe}: {part_dir}")
        return pd.DataFrame()

    start_ts = pd.to_datetime(start_time)
    end_ts = pd.to_datetime(end_time)
    ym = _month_range(start_ts, end_ts)
    years = sorted({y for y, _ in ym})
    months = sorted({m for _, m in ym})

    dataset = ds.dataset(part_dir, format="parquet")
    expr = (ds.field("year").isin(years)) & (ds.field("month").isin(months))
    table = dataset.to_table(filter=expr)
    df = table.to_pandas()
    if df.empty:
        print(f"[hits-load] timeframe={timeframe} range=({start_ts},{end_ts}) -> loaded=0 rows")
        return df
    df["answer_time"] = pd.to_datetime(df["answer_time"], utc=True, errors="coerce")
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
    df = df[(df["answer_time"] >= start_ts) & (df["answer_time"] <= end_ts) | ((df["start_time"] <= end_ts) & (df["end_time"] >= start_ts))]
    # Apply static filters
    df = apply_static_filters_to_hits(df, base_filters)
    print(f"[hits-load] timeframe={timeframe} range=({start_ts},{end_ts}) -> loaded={len(df)} rows")
    return df


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

    if pt:
        df = df[df["pattern_type"].isin(pt)]
    df = df[(df["window_size"] >= ws_min) & (df["window_size"] <= ws_max)]
    df = df[(df["lift"] >= lift_min) & (df["lift"] <= lift_max)]
    df = df[(df["stability"] >= stab_min) & (df["stability"] <= stab_max)]
    df = df[(df["support"] >= sup_min) & (df["support"] <= sup_max)]

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


def filter_hits_for_time_range(
    hits_df: pd.DataFrame,
    start_time,
    end_time,
) -> pd.DataFrame:
    if hits_df.empty:
        return hits_df
    start_ts = pd.to_datetime(start_time)
    end_ts = pd.to_datetime(end_time)
    mask = (hits_df["end_time"] >= start_ts) & (hits_df["start_time"] <= end_ts)
    return hits_df[mask]


def limit_hits_for_render(hits_df: pd.DataFrame, max_hits: Optional[int]) -> pd.DataFrame:
    if hits_df.empty:
        return hits_df
    limit = max_hits if max_hits is not None else DEFAULT_MAX_HITS
    if limit <= 0 or limit > DRAW_HARD_CAP:
        limit = DRAW_HARD_CAP
    sort_cols = [c for c in ["score", "support", "stability"] if c in hits_df.columns]
    if sort_cols:
        hits_df = hits_df.sort_values(sort_cols, ascending=[False] * len(sort_cols))
    return hits_df.head(limit)


def build_hit_shapes_for_chart(
    hits_df: pd.DataFrame,
    y_min: float,
    y_max: float,
    color_mode: str = "pattern_type",
) -> Tuple[List[dict], List[go.Scatter]]:
    if hits_df.empty:
        return [], []
    shapes: List[dict] = []
    marker_x: List[pd.Timestamp] = []
    marker_y: List[float] = []
    marker_text: List[str] = []

    for _, row in hits_df.iterrows():
        if color_mode == "strength" and isinstance(row.get("strength"), str):
            color = STRENGTH_COLORS.get(str(row["strength"]).lower(), "rgba(200,200,200,0.25)")
        elif color_mode == "family_id" and pd.notna(row.get("family_id")):
            color = "rgba(156, 136, 255, 0.22)"
        else:
            color = PTYPE_COLORS.get(row["pattern_type"], "rgba(200,200,200,0.25)")
        shapes.append(
            {
                "type": "rect",
                "xref": "x",
                "yref": "y",
                "x0": row["start_time"],
                "x1": row["end_time"],
                "y0": y_min,
                "y1": y_max,
                "fillcolor": color,
                "line": {"width": 0},
                "opacity": 0.25,
            }
        )
        marker_x.append(row["answer_time"])
        marker_text.append(
            f"{row['pattern_type']} w={row['window_size']} score={row.get('score', np.nan):.2f} id={row['pattern_id']}"
        )

    price_series = CANDLES[hits_df.iloc[0]["timeframe"]]
    time_col = price_series["time_col"].iloc[0]
    price_map = dict(zip(price_series[time_col], price_series["close"]))
    marker_y = [price_map.get(ts, np.nan) for ts in marker_x]
    marker_trace = go.Scatter(
        x=marker_x,
        y=marker_y,
        mode="markers",
        marker=dict(color="yellow", size=6, symbol="triangle-up"),
        name="pattern hits",
        text=marker_text,
        hoverinfo="text",
    )
    return shapes, [marker_trace]


def hits_to_shapes_and_markers(
    hits: pd.DataFrame,
    tf: str,
    y_min: float,
    y_max: float,
    max_hits: int,
) -> Tuple[List[dict], List[go.Scatter]]:
    if hits.empty:
        return [], []
    hits_sorted = hits.sort_values("score", ascending=False)
    if max_hits and max_hits > 0:
        hits_sorted = hits_sorted.head(max_hits)
    shapes: List[dict] = []
    marker_x: List[pd.Timestamp] = []
    marker_y: List[float] = []
    marker_text: List[str] = []
    color_map = PTYPE_COLORS
    for _, row in hits_sorted.iterrows():
        color = color_map.get(row["pattern_type"], "rgba(200,200,200,0.25)")
        shapes.append(
            {
                "type": "rect",
                "xref": "x",
                "yref": "y",
                "x0": row["start_time"],
                "x1": row["end_time"],
                "y0": y_min,
                "y1": y_max,
                "fillcolor": color,
                "line": {"width": 0},
                "opacity": 0.25,
            }
        )
        marker_x.append(row["answer_time"])
        marker_y.append(row.get("answer_price", np.nan))
        marker_text.append(
            f"{row['pattern_type']} w={row['window_size']} score={row['score']:.2f} id={row['pattern_id']}"
        )
    price_series = CANDLES[tf]
    time_col = price_series["time_col"].iloc[0]
    price_map = dict(zip(price_series[time_col], price_series["close"]))
    marker_y = [price_map.get(ts, np.nan) for ts in marker_x]
    marker_trace = go.Scatter(
        x=marker_x,
        y=marker_y,
        mode="markers",
        marker=dict(color="yellow", size=6, symbol="triangle-up"),
        name="pattern hits",
        text=marker_text,
        hoverinfo="text",
    )
    return shapes, [marker_trace]


def filter_hits(
    timeframes: List[str],
    view_mode: str,
    pattern_ids: List[str],
    family_ids: List[str],
    allowlist: bool,
    pattern_types: Sequence[str],
    ws_range: Tuple[int, int],
    lift_range: Tuple[float, float],
    stab_range: Tuple[float, float],
    sup_range: Tuple[int, int],
    visible_range: Optional[Tuple[pd.Timestamp, pd.Timestamp]],
    clicked_time: Optional[pd.Timestamp],
) -> pd.DataFrame:
    frames = []
    for tf in timeframes:
        hits = HITS[tf]
        hits = hits[hits["pattern_type"].isin(pattern_types)]
        hits = hits[(hits["window_size"] >= ws_range[0]) & (hits["window_size"] <= ws_range[1])]
        hits = hits[(hits["lift"] >= lift_range[0]) & (hits["lift"] <= lift_range[1])]
        hits = hits[(hits["stability"] >= stab_range[0]) & (hits["stability"] <= stab_range[1])]
        hits = hits[(hits["support"] >= sup_range[0]) & (hits["support"] <= sup_range[1])]

        if visible_range:
            start, end = visible_range
            mask = (hits["answer_time"] >= start) & (hits["answer_time"] <= end)
            hits = hits[mask]

        if view_mode == "pattern":
            if pattern_ids:
                if allowlist:
                    hits = hits[hits["pattern_id"].isin(pattern_ids)]
                else:
                    hits = hits[~hits["pattern_id"].isin(pattern_ids)]
            if family_ids:
                hits = hits[hits["family_id"].isin(family_ids)]
        elif view_mode == "family":
            if family_ids:
                hits = hits[hits["family_id"].isin(family_ids)]
            else:
                hits = hits.iloc[0:0]
        elif view_mode == "candle" and clicked_time is not None:
            hits = hits[
                ((hits["start_time"] <= clicked_time) & (hits["end_time"] >= clicked_time))
                | (hits["answer_time"] == clicked_time)
            ]
        frames.append(hits)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def hits_table_columns() -> List[dict]:
    cols = [
        {"name": "timeframe", "id": "timeframe"},
        {"name": "pattern_id", "id": "pattern_id"},
        {"name": "pattern_type", "id": "pattern_type"},
        {"name": "window_size", "id": "window_size"},
        {"name": "strength", "id": "strength"},
        {"name": "answer_time", "id": "answer_time"},
        {"name": "start_time", "id": "start_time"},
        {"name": "support", "id": "support"},
        {"name": "lift", "id": "lift"},
        {"name": "stability", "id": "stability"},
        {"name": "score", "id": "score"},
    ]
    return cols


def pattern_dropdown_options() -> List[dict]:
    opts: List[dict] = []
    TOP_N = 100
    for tf in TIMEFRAMES:
        df = PATTERNS[tf]
        df_sorted = df.sort_values("score", ascending=False).head(TOP_N) if "score" in df.columns else df.head(TOP_N)
        for _, row in df_sorted.iterrows():
            label = f"{tf} | w={int(row['window_size'])} | {row['pattern_type']} | sup={row['support']} | id={row['pattern_id']} (top)"
            opts.append({"label": label, "value": row["pattern_id"]})
    return opts


def family_dropdown_options() -> List[dict]:
    opts: List[dict] = []
    for tf in TIMEFRAMES:
        fam = FAMILIES.get(tf)
        if fam is None or fam.empty:
            continue
        for _, row in fam.iterrows():
            members = row.get("member_keys", [])
            size = len(members) if isinstance(members, (list, np.ndarray)) else ""
            label = f"{tf} | {row['family_id']} | {row.get('strength_level','')} | size={size}"
            opts.append({"label": label, "value": row["family_id"]})
    return opts


# ---------------------------------------------------------------------------
# Dash app
# ---------------------------------------------------------------------------
app: Dash = dash.Dash(__name__)
app.title = "PrisonBreaker – BTCUSDT Pattern Viewer (Level-1)"

app.layout = html.Div(
    [
        html.H3("PrisonBreaker - BTCUSDT Pattern Viewer (Level-1)", style={"textAlign": "center"}),
        html.Div(
            [
                # Left rail
                html.Div(
                    [
                        html.H5("Timeframes"),
                        dcc.Checklist(
                            id="tf-check",
                            options=[{"label": "4h", "value": "4h"}, {"label": "5m", "value": "5m"}],
                            value=["4h"],  # only 4h selected by default
                            inline=True,
                        ),
                        html.H5("View mode"),
                        dcc.RadioItems(
                            id="view-mode",
                            options=[
                                {"label": "Pattern-centric", "value": "pattern"},
                                {"label": "Candle-centric", "value": "candle"},
                                {"label": "Family view", "value": "family"},
                            ],
                            value="pattern",
                        ),
                        html.H5("Pattern filters"),
                        dcc.Checklist(
                            id="ptype-check",
                            options=[
                                {"label": "sequence", "value": "sequence"},
                                {"label": "candle_shape", "value": "candle_shape"},
                                {"label": "feature_rule", "value": "feature_rule"},
                            ],
                            value=["sequence", "candle_shape", "feature_rule"],
                            inline=True,
                        ),
                        html.Label("Window size"),
                        dcc.RangeSlider(id="ws-slider", min=2, max=11, step=1, value=[2, 11]),
                        html.Label("Lift"),
                        dcc.RangeSlider(
                            id="lift-slider",
                            min=0.0,
                            max=LIFT_MAX_SLIDER,
                            step=0.1,
                            value=[0.0, LIFT_MAX_SLIDER],
                        ),
                        html.Label("Stability"),
                        dcc.RangeSlider(id="stab-slider", min=0.0, max=1.0, step=0.05, value=[0.0, 1.0]),
                        html.Label("Support"),
                        dcc.RangeSlider(
                            id="sup-slider",
                            min=0,
                            max=SUP_MAX_SLIDER,
                            step=max(10, SUP_MAX_SLIDER // 50),
                            value=[0, SUP_MAX_SLIDER],
                        ),
                        html.H5("Pattern selection"),
                        dcc.Dropdown(
                            id="pattern-dropdown",
                            options=pattern_dropdown_options(),
                            multi=True,
                            placeholder="Select patterns",
                        ),
                        dcc.RadioItems(
                            id="allowblock-radio",
                            options=[
                                {"label": "Allow-list", "value": "allow"},
                                {"label": "Block-list", "value": "block"},
                            ],
                            value="allow",
                            inline=True,
                        ),
                        html.H5("Family selection"),
                        dcc.Dropdown(
                            id="family-dropdown",
                            options=family_dropdown_options(),
                            multi=True,
                            placeholder="Select families",
                        ),
                        html.Div(
                            "Family data missing; family view will be limited."
                            if not FAMILY_AVAILABLE
                            else "",
                            style={"fontSize": "12px", "color": "#777", "marginTop": "4px"},
                        ),
                        html.H5("Overlay controls"),
                        dcc.Checklist(
                            id="overlay-enable",
                            options=[{"label": "Show pattern overlays", "value": "on"}],
                            value=[],  # off by default
                        ),
                        html.Label("Max hits to draw per timeframe (visible range)"),
                        dcc.Slider(
                            id="max-hits-slider",
                            min=0,
                            max=2000,
                            step=50,
                            value=100,
                            marks={0: "0", 100: "100", 300: "300", 500: "500", 1000: "1000", 2000: "2000"},
                        ),
                        html.Div(id="status-text", style={"marginTop": "12px", "fontSize": "12px", "color": "#555"}),
                    ],
                    style={
                        "width": "24%",
                        "display": "inline-block",
                        "verticalAlign": "top",
                        "padding": "0 12px",
                    },
                ),
                # Right content
                html.Div(
                    [
                        dcc.Graph(id="fig-4h", figure=make_candle_fig("4h", x_range=DEFAULT_X_RANGE)),
                        dcc.Graph(id="fig-5m", figure=make_candle_fig("5m", x_range=DEFAULT_X_RANGE)),
                        html.H5("Pattern hits"),
                        dash_table.DataTable(
                            id="hits-table",
                            columns=hits_table_columns(),
                            page_size=12,
                            style_table={"overflowX": "auto", "height": "320px", "overflowY": "auto"},
                            style_header={"backgroundColor": "#111", "color": "white"},
                            style_data={"backgroundColor": "#222", "color": "white", "fontSize": "12px"},
                        ),
                    ],
                    style={"width": "74%", "display": "inline-block", "padding": "0 10px"},
                ),
            ]
        ),
        dcc.Store(id="x-range-store", data=DEFAULT_X_RANGE),
    ]
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
@app.callback(
    Output("x-range-store", "data"),
    Input("fig-4h", "relayoutData"),
    State("x-range-store", "data"),
)
def sync_ranges(relayout_data, current_range):
    if relayout_data is None:
        return current_range
    keys = ["xaxis.range[0]", "xaxis.range[1]", "xaxis.range", "xaxis.autorange"]
    if any(k in relayout_data for k in keys):
        if "xaxis.range[0]" in relayout_data and "xaxis.range[1]" in relayout_data:
            return [relayout_data["xaxis.range[0]"], relayout_data["xaxis.range[1]"]]
        if "xaxis.range" in relayout_data and isinstance(relayout_data["xaxis.range"], list):
            return relayout_data["xaxis.range"]
    return current_range


@app.callback(
    Output("fig-4h", "figure"),
    Output("fig-5m", "figure"),
    Output("hits-table", "data"),
    Output("status-text", "children"),
    Input("tf-check", "value"),
    Input("view-mode", "value"),
    Input("pattern-dropdown", "value"),
    Input("family-dropdown", "value"),
    Input("allowblock-radio", "value"),
    Input("ptype-check", "value"),
    Input("ws-slider", "value"),
    Input("lift-slider", "value"),
    Input("stab-slider", "value"),
    Input("sup-slider", "value"),
    Input("x-range-store", "data"),
    Input("fig-4h", "clickData"),
    Input("overlay-enable", "value"),
    Input("max-hits-slider", "value"),
)
def update_figures(
    tf_values,
    view_mode,
    pattern_values,
    family_values,
    allowblock_value,
    ptypes,
    ws_range,
    lift_range,
    stab_range,
    sup_range,
    x_range,
    click_data,
    overlay_enabled,
    max_hits,
):
    timeframes = tf_values or []
    pattern_ids = pattern_values or []
    family_ids = family_values or []
    allowlist = allowblock_value == "allow"
    x_range_use = x_range if x_range else DEFAULT_X_RANGE
    if not x_range_use or len(x_range_use) != 2:
        start_init, end_init = get_initial_time_range_4h()
        x_range_use = [start_init.isoformat(), end_init.isoformat()]
    visible_range = (pd.to_datetime(x_range_use[0]), pd.to_datetime(x_range_use[1]))
    # Clamp overly wide ranges to keep initial loads small
    if (visible_range[1] - visible_range[0]) > pd.Timedelta(days=30):
        end_tmp = visible_range[1]
        start_tmp = end_tmp - pd.Timedelta(days=7)
        visible_range = (start_tmp, end_tmp)
        x_range_use = [start_tmp.isoformat(), end_tmp.isoformat()]
    clicked_time = None
    if click_data and "points" in click_data and click_data["points"]:
        ts = click_data["points"][0].get("x")
        if ts:
            clicked_time = pd.to_datetime(ts)

    base_filters = {
        "pattern_types": ptypes,
        "ws_range": (ws_range[0], ws_range[1]),
        "lift_range": (lift_range[0], lift_range[1]),
        "stab_range": (stab_range[0], stab_range[1]),
        "sup_range": (sup_range[0], sup_range[1]),
        "allowlist": allowlist,
        "pattern_ids": pattern_ids,
        "family_ids": family_ids,
        "view_mode": view_mode,
    }

    overlays_on = overlay_enabled and "on" in overlay_enabled
    print(f"[debug] show_overlays={overlays_on}")

    fig4h = make_candle_fig("4h", x_range=x_range_use)
    fig5m = make_candle_fig("5m", x_range=x_range_use) if "5m" in timeframes else make_candle_fig("5m", x_range=x_range_use)

    if not overlays_on or not timeframes:
        empty_records: List[dict] = []
        status_txt = "Overlays disabled; no pattern hits loaded."
        return fig4h, fig5m, empty_records, status_txt

    hits_draw_frames: List[pd.DataFrame] = []

    for tf, fig in [("4h", fig4h), ("5m", fig5m)]:
        if tf not in timeframes:
            continue

        load_start, load_end = visible_range
        if view_mode == "candle" and clicked_time is not None:
            delta = pd.Timedelta(days=3) if tf == "4h" else pd.Timedelta(hours=12)
            load_start = clicked_time - delta
            load_end = clicked_time + delta

        loaded_hits = load_hits_for_timerange(tf, load_start, load_end, base_filters)

        if view_mode == "candle" and clicked_time is not None:
            window_hits = loaded_hits[
                ((loaded_hits["start_time"] <= clicked_time) & (loaded_hits["end_time"] >= clicked_time))
                | (loaded_hits["answer_time"] == clicked_time)
            ]
        else:
            window_hits = loaded_hits

        draw_hits = limit_hits_for_render(window_hits, max_hits)
        hits_draw_frames.append(draw_hits)

        print(
            f"[hits] {tf}: loaded={len(loaded_hits)}, filtered={len(window_hits)}, draw={len(draw_hits)}"
        )

        if overlays_on and not draw_hits.empty:
            df_price = CANDLES[tf]
            time_col = df_price["time_col"].iloc[0]
            df_vis = df_price[
                (df_price[time_col] >= visible_range[0]) & (df_price[time_col] <= visible_range[1])
            ]
            if df_vis.empty:
                df_vis = df_price
            y_min = float(df_vis["low"].min()) if not df_vis.empty else float(df_price["low"].min())
            y_max = float(df_vis["high"].max()) if not df_vis.empty else float(df_price["high"].max())
            shapes, markers = build_hit_shapes_for_chart(draw_hits, y_min, y_max)
            existing_shapes = list(fig.layout.shapes) if fig.layout.shapes else []
            fig.update_layout(shapes=shapes + existing_shapes)
            for m in markers:
                fig.add_trace(m)

    table_df = pd.concat(hits_draw_frames, ignore_index=True) if hits_draw_frames else pd.DataFrame()
    table_df = limit_hits_for_render(table_df, TABLE_ROW_CAP) if not table_df.empty else table_df
    table_records = table_df.sort_values("answer_time").to_dict("records")[:TABLE_ROW_CAP] if not table_df.empty else []
    status_txt = (
        f"Hits in view: {len(table_records)} | timeframes={','.join(timeframes)} | "
        f"mode={view_mode}"
    )
    if view_mode == "family" and not FAMILY_AVAILABLE:
        status_txt += " | family data not available"
    return fig4h, fig5m, table_records, status_txt


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=False)
