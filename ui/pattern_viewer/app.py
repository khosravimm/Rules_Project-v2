from __future__ import annotations

from pathlib import Path
import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

import dash
from dash import Dash, dcc, html, dash_table, Input, Output, State
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


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
HITS: Dict[str, pd.DataFrame] = {}
FAMILIES: Dict[str, Optional[pd.DataFrame]] = {}

for tf in TIMEFRAMES:
    CANDLES[tf] = load_candles(tf)
    PATTERNS[tf] = load_patterns(tf)
    HITS[tf] = load_pattern_hits(tf)
    FAMILIES[tf] = load_families(tf)
    print(
        f"[LOAD] timeframe={tf} candles={len(CANDLES[tf])} patterns={len(PATTERNS[tf])} hits={len(HITS[tf])}"
    )

def _default_range() -> List[str]:
    df = CANDLES["4h"]
    time_col = df["time_col"].iloc[0]
    if df.empty:
        return []
    end = df[time_col].iloc[-1]
    start_idx = max(len(df) - 300, 0)
    start = df[time_col].iloc[start_idx]
    return [start.isoformat(), end.isoformat()]


DEFAULT_X_RANGE = _default_range()
SUP_MAX = int(
    max((h["support"].max() for h in HITS.values() if not h.empty), default=1000)
)
LIFT_MAX = float(
    max((h["lift"].max() for h in HITS.values() if not h.empty), default=5.0)
)
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


def make_candle_fig(tf: str, x_range: Optional[Tuple[str, str]] = None) -> go.Figure:
    df = CANDLES[tf]
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
    for tf in TIMEFRAMES:
        df = PATTERNS[tf]
        for _, row in df.iterrows():
            label = f"{tf} | w={int(row['window_size'])} | {row['pattern_type']} | sup={row['support']} | id={row['pattern_id']}"
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
        html.H3("PrisonBreaker – BTCUSDT Pattern Viewer (Level-1)", style={"textAlign": "center"}),
        html.Div(
            [
                # Left rail
                html.Div(
                    [
                        html.H5("Timeframes"),
                        dcc.Checklist(
                            id="tf-check",
                            options=[{"label": "4h", "value": "4h"}, {"label": "5m", "value": "5m"}],
                            value=["4h", "5m"],
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
                            value=["on"],
                        ),
                        html.Label("Max hits to draw per timeframe (visible range)"),
                        dcc.Slider(
                            id="max-hits-slider",
                            min=0,
                            max=2000,
                            step=50,
                            value=500,
                            marks={0: "0", 500: "500", 1000: "1000", 2000: "2000"},
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
    visible_range = None
    if x_range_use and len(x_range_use) == 2:
        visible_range = (pd.to_datetime(x_range_use[0]), pd.to_datetime(x_range_use[1]))
    clicked_time = None
    if click_data and "points" in click_data and click_data["points"]:
        ts = click_data["points"][0].get("x")
        if ts:
            clicked_time = pd.to_datetime(ts)

    hits_filtered = filter_hits(
        timeframes=timeframes,
        view_mode=view_mode,
        pattern_ids=pattern_ids,
        family_ids=family_ids,
        allowlist=allowlist,
        pattern_types=ptypes,
        ws_range=(ws_range[0], ws_range[1]),
        lift_range=(lift_range[0], lift_range[1]),
        stab_range=(stab_range[0], stab_range[1]),
        sup_range=(sup_range[0], sup_range[1]),
        visible_range=visible_range,
        clicked_time=clicked_time,
    )

    fig4h = make_candle_fig("4h", x_range=x_range_use)
    fig5m = make_candle_fig("5m", x_range=x_range_use)

    overlays_on = overlay_enabled and "on" in overlay_enabled
    if overlays_on and not hits_filtered.empty:
        for tf, fig in [("4h", fig4h), ("5m", fig5m)]:
            if tf not in timeframes:
                continue
            tf_hits = hits_filtered[hits_filtered["timeframe"] == tf]
            if visible_range:
                start, end = visible_range
                tf_hits = tf_hits[(tf_hits["answer_time"] >= start) & (tf_hits["answer_time"] <= end)]
            if tf_hits.empty:
                continue
            df_price = CANDLES[tf]
            time_col = df_price["time_col"].iloc[0]
            if visible_range:
                df_vis = df_price[(df_price[time_col] >= start) & (df_price[time_col] <= end)]
            else:
                df_vis = df_price
            y_min = float(df_vis["low"].min()) if not df_vis.empty else float(df_price["low"].min())
            y_max = float(df_vis["high"].max()) if not df_vis.empty else float(df_price["high"].max())
            shapes, markers = hits_to_shapes_and_markers(tf_hits, tf, y_min, y_max, max_hits)
            existing_shapes = list(fig.layout.shapes) if fig.layout.shapes else []
            fig.update_layout(shapes=shapes + existing_shapes)
            for m in markers:
                fig.add_trace(m)

    table_df = hits_filtered.copy()
    if visible_range:
        start, end = visible_range
        table_df = table_df[(table_df["answer_time"] >= start) & (table_df["answer_time"] <= end)]
    table_records = table_df.sort_values("answer_time").to_dict("records")
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
