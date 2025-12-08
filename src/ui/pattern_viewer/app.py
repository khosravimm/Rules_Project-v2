"""
Dash Pattern Viewer UI for PrisonBreaker (BTCUSDT 4h/5m, Level-1 patterns)

Run with:
    cd D:/Code/chatgpt/Rules_Project-v2
    python -m src.ui.pattern_viewer.app

App will listen on http://127.0.0.1:8050
"""

import pathlib
from datetime import datetime, timedelta

import pandas as pd
from dash import Dash, dcc, html, dash_table, Input, Output, State
import plotly.graph_objects as go

# ---------------------------------------------------------------------
# Paths & data loading (single-time, in-memory for speed)
# ---------------------------------------------------------------------

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]

DATA_4H_PATHS = [
    PROJECT_ROOT / "data" / "btcusdt_4h_features.parquet",
    PROJECT_ROOT / "data" / "btcusdt_4h_raw.parquet",
]
DATA_5M_PATHS = [
    PROJECT_ROOT / "data" / "btcusdt_5m_features.parquet",
    PROJECT_ROOT / "data" / "btcusdt_5m_raw.parquet",
]

HITS_4H_PATH = PROJECT_ROOT / "data" / "pattern_hits_4h_level1.parquet"
HITS_5M_PATH = PROJECT_ROOT / "data" / "pattern_hits_5m_level1.parquet"


def _load_first_existing(paths):
    for p in paths:
        if p.exists():
            return pd.read_parquet(p)
    raise FileNotFoundError(f"None of these files exist: {paths}")


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize OHLC dataframe to columns:
        time (datetime), open, high, low, close, volume
    Adjust here if your parquet columns differ.
    """
    cols = {c.lower(): c for c in df.columns}

    def pick(*candidates):
        for c in candidates:
            if c in cols:
                return cols[c]
        raise KeyError(f"Could not find any of columns {candidates} in {df.columns}")

    ts_col = pick("time", "timestamp", "open_time", "date")
    o_col = pick("open", "o")
    h_col = pick("high", "h")
    l_col = pick("low", "l")
    c_col = pick("close", "c")
    v_col = pick("volume", "vol", "base_volume")

    out = pd.DataFrame(
        {
            "time": pd.to_datetime(df[ts_col]),
            "open": df[o_col].astype(float),
            "high": df[h_col].astype(float),
            "low": df[l_col].astype(float),
            "close": df[c_col].astype(float),
            "volume": df[v_col].astype(float),
        }
    ).sort_values("time")

    return out


def _normalize_hits(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Normalize pattern_hits dataframe to standard columns used by the UI.

    Expected (or mapped) columns:
        timeframe, pattern_id, w, pattern_type, role,
        support, lift, stability, score,
        family_id, strength, start_time, ans_time
    """
    cols = {c.lower(): c for c in df.columns}

    def pick_opt(*candidates, default=None):
        for c in candidates:
            if c in cols:
                return cols[c]
        return default

    def pick_req(*candidates):
        col = pick_opt(*candidates)
        if col is None:
            raise KeyError(f"Missing required column among {candidates}")
        return col

    # Required mappings
    pattern_col = pick_req("pattern_id", "pattern")
    w_col = pick_opt("w", "window", "window_size", default=None)
    type_col = pick_opt("pattern_type", "type", default=None)
    role_col = pick_opt("role", "hit_role", default=None)
    support_col = pick_opt("support", "count", default=None)
    lift_col = pick_opt("lift", default=None)
    stab_col = pick_opt("stability", "stability_score", default=None)
    score_col = pick_opt("score", "total_score", default=None)
    fam_col = pick_opt("family_id", "family", default=None)
    strength_col = pick_opt("strength", "strength_level", default=None)
    start_col = pick_req("start_time", "window_start", "start_ts")
    ans_col = pick_req("ans_time", "answer_time", "ans_ts")

    out = pd.DataFrame()
    out["timeframe"] = timeframe
    out["pattern_id"] = df[pattern_col].astype(str)

    if w_col:
        out["w"] = df[w_col].astype("Int64")
    else:
        out["w"] = pd.NA

    if type_col:
        out["pattern_type"] = df[type_col].astype(str)
    else:
        out["pattern_type"] = "unknown"

    if role_col:
        out["role"] = df[role_col].astype(str)
    else:
        out["role"] = "answer"

    if support_col:
        out["support"] = df[support_col].astype(float)
    else:
        out["support"] = pd.NA

    if lift_col:
        out["lift"] = df[lift_col].astype(float)
    else:
        out["lift"] = 1.0

    if stab_col:
        out["stability"] = df[stab_col].astype(float)
    else:
        out["stability"] = 1.0

    if score_col:
        out["score"] = df[score_col].astype(float)
    else:
        out["score"] = 1.0

    if fam_col:
        out["family_id"] = df[fam_col].astype(str)
    else:
        out["family_id"] = "fam_unknown"

    if strength_col:
        out["strength"] = df[strength_col].astype(str)
    else:
        out["strength"] = "weak"

    out["start_time"] = pd.to_datetime(df[start_col])
    out["ans_time"] = pd.to_datetime(df[ans_col])

    out = out.sort_values("start_time")

    return out


def _empty_hits_df(timeframe: str) -> pd.DataFrame:
    """Return an empty hits dataframe with expected columns/dtypes."""
    return pd.DataFrame(
        {
            "timeframe": pd.Series(dtype="object"),
            "pattern_id": pd.Series(dtype="object"),
            "w": pd.Series(dtype="Int64"),
            "pattern_type": pd.Series(dtype="object"),
            "role": pd.Series(dtype="object"),
            "support": pd.Series(dtype="float"),
            "lift": pd.Series(dtype="float"),
            "stability": pd.Series(dtype="float"),
            "score": pd.Series(dtype="float"),
            "family_id": pd.Series(dtype="object"),
            "strength": pd.Series(dtype="object"),
            "start_time": pd.Series(dtype="datetime64[ns]"),
            "ans_time": pd.Series(dtype="datetime64[ns]"),
        }
    )


def _load_hits_safe(path: pathlib.Path, timeframe: str) -> pd.DataFrame:
    """Load hits parquet with fallback to empty dataframe on failure."""
    try:
        if not path.exists():
            print(f"[UI] Warning: hits file not found: {path}")
            return _empty_hits_df(timeframe)
        raw = pd.read_parquet(path)
        if raw.empty:
            print(f"[UI] Warning: hits file empty: {path}")
            return _empty_hits_df(timeframe)
        return _normalize_hits(raw, timeframe)
    except Exception as exc:  # noqa: broad-except
        print(f"[UI] Warning: failed to load hits from {path}: {exc}")
        return _empty_hits_df(timeframe)


# --- load everything once -----------------------------------------------------

print("[UI] Loading OHLC / pattern hits data ...")

ohlc_4h_raw = _load_first_existing(DATA_4H_PATHS)
ohlc_5m_raw = _load_first_existing(DATA_5M_PATHS)

ohlc_4h = _normalize_ohlc(ohlc_4h_raw)
ohlc_5m = _normalize_ohlc(ohlc_5m_raw)

hits_4h = _load_hits_safe(HITS_4H_PATH, "4h")
hits_5m = _load_hits_safe(HITS_5M_PATH, "5m")

print(
    f"[UI] 4h candles: {len(ohlc_4h)}, 5m candles: {len(ohlc_5m)}, "
    f"4h hits: {len(hits_4h)}, 5m hits: {len(hits_5m)}"
)

# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------


def get_initial_window_4h(days: int = 7):
    """Return (start, end) for last `days` days on 4h timeframe."""
    if ohlc_4h.empty:
        return None, None
    end = ohlc_4h["time"].max()
    start = end - timedelta(days=days)
    return start, end


def filter_hits(
    timeframe_list,
    pattern_types,
    strength_levels,
    lift_min,
    lift_max,
    stab_min,
    stab_max,
    sup_min,
    sup_max,
    pattern_allow_ids,
    family_allow_ids,
    allow_mode="allow",
    start_time=None,
    end_time=None,
):
    """Apply all filters on hits and return a filtered dataframe."""
    frames = []
    if "4h" in timeframe_list:
        frames.append(hits_4h)
    if "5m" in timeframe_list:
        frames.append(hits_5m)
    if not frames:
        return hits_4h.iloc[0:0].copy()

    df = pd.concat(frames, ignore_index=True)

    if pattern_types:
        df = df[df["pattern_type"].isin(pattern_types)]

    if strength_levels:
        df = df[df["strength"].isin(strength_levels)]

    df = df[
        (df["lift"] >= lift_min)
        & (df["lift"] <= lift_max)
        & (df["stability"] >= stab_min)
        & (df["stability"] <= stab_max)
        & (df["support"] >= sup_min)
        & (df["support"] <= sup_max)
    ]

    if start_time is not None:
        df = df[df["start_time"] >= start_time]
    if end_time is not None:
        df = df[df["start_time"] <= end_time]

    # Allow / Block list logic
    if pattern_allow_ids:
        if allow_mode == "allow":
            df = df[df["pattern_id"].isin(pattern_allow_ids)]
        else:
            df = df[~df["pattern_id"].isin(pattern_allow_ids)]

    if family_allow_ids:
        if allow_mode == "allow":
            df = df[df["family_id"].isin(family_allow_ids)]
        else:
            df = df[~df["family_id"].isin(family_allow_ids)]

    return df


def make_candlestick_figure(df: pd.DataFrame, title: str):
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_white",
            xaxis={"title": "time"},
            yaxis={"title": "price"},
            margin=dict(l=40, r=10, t=30, b=20),
            title=title + " (no data)",
        )
        return fig

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df["time"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="price",
            )
        ]
    )
    fig.update_layout(
        template="plotly_white",
        xaxis={"title": "time"},
        yaxis={"title": "price"},
        margin=dict(l=40, r=10, t=30, b=20),
        title=title,
    )
    return fig


def _pattern_rgb(pattern_type: str):
    """Return RGB tuple for a pattern type."""
    mapping = {
        "sequence": (0, 102, 204),
        "candle_shape": (255, 140, 0),
        "feature_rule": (46, 139, 87),
    }
    return mapping.get(pattern_type, (128, 128, 128))


def _rgba_str(rgb, alpha: float) -> str:
    r, g, b = rgb
    return f"rgba({r}, {g}, {b}, {alpha})"


# ---------------------------------------------------------------------
# Dash app definition
# ---------------------------------------------------------------------

external_stylesheets = []

app = Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    title="PrisonBreaker – Pattern Viewer",
)

# ---- layout (تقریباً همان HTML v3، این‌بار با Dash components) -------------

timeframe_checklist = dcc.Checklist(
    id="tf-checklist",
    options=[
        {"label": "4h", "value": "4h"},
        {"label": "5m", "value": "5m"},
    ],
    value=["4h", "5m"],
    labelStyle={"display": "inline-flex", "marginRight": "8px"},
)

pattern_type_checklist = dcc.Checklist(
    id="pattern-type-checklist",
    options=[
        {"label": "sequence", "value": "sequence"},
        {"label": "candle_shape", "value": "candle_shape"},
        {"label": "feature_rule", "value": "feature_rule"},
    ],
    value=["sequence", "candle_shape", "feature_rule"],
    labelStyle={"display": "inline-flex", "marginRight": "8px"},
)

strength_checklist = dcc.Checklist(
    id="strength-checklist",
    options=[
        {"label": "weak", "value": "weak"},
        {"label": "medium", "value": "medium"},
        {"label": "strong", "value": "strong"},
    ],
    value=["weak", "medium", "strong"],
    labelStyle={"display": "inline-flex", "marginRight": "8px"},
)

# برای pattern_id و family_id چند اسم نمونه از hits جمع می‌کنیم
pattern_options = (
    pd.concat([hits_4h["pattern_id"], hits_5m["pattern_id"]])
    .drop_duplicates()
    .sort_values()
    .head(200)
)
family_options = (
    pd.concat([hits_4h["family_id"], hits_5m["family_id"]])
    .drop_duplicates()
    .sort_values()
    .head(200)
)

# layout اصلی
app.layout = html.Div(
    className="app-container",
    children=[
        # Header
        html.Div(
            className="header",
            children=[
                html.Div(
                    [
                        html.Div(
                            "PrisonBreaker – BTCUSDT Pattern Dashboard (Dash UI)",
                            className="header-title",
                        ),
                        html.Div(
                            "4h / 5m · Level-1 Patterns · Pattern / Candle / Family views",
                            className="header-subtitle",
                        ),
                    ]
                ),
                html.Div(
                    className="header-controls",
                    children=[
                        html.Span(
                            children=[html.Strong("Market:"), " BTCUSDT"],
                            className="badge",
                        ),
                        html.Div(
                            className="select",
                            children=[
                                html.Span("Timeframe:"),
                                dcc.Dropdown(
                                    id="header-tf-dropdown",
                                    options=[
                                        {"label": "4h", "value": "4h"},
                                        {"label": "5m", "value": "5m"},
                                    ],
                                    value="4h",
                                    clearable=False,
                                    style={"width": "60px", "fontSize": "12px"},
                                ),
                            ],
                        ),
                        html.Div(
                            className="button-toggle-group",
                            children=[
                                html.Span("View:"),
                                dcc.RadioItems(
                                    id="view-mode-radio",
                                    options=[
                                        {"label": "Pattern", "value": "pattern"},
                                        {"label": "Candle", "value": "candle"},
                                        {"label": "Family", "value": "family"},
                                    ],
                                    value="pattern",
                                    labelStyle={
                                        "display": "inline-flex",
                                        "padding": "2px 8px",
                                        "borderRadius": "999px",
                                        "border": "1px solid #ddd",
                                        "marginRight": "4px",
                                    },
                                    inputStyle={"marginRight": "4px"},
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        # Main layout grid
        html.Div(
            className="main-layout",
            children=[
                # Sidebar
                html.Aside(
                    className="sidebar",
                    children=[
                        # Timeframe
                        html.Div(
                            className="sidebar-section",
                            children=[
                                html.Div("Timeframe", className="sidebar-section-title"),
                                timeframe_checklist,
                            ],
                        ),
                        # Pattern type
                        html.Div(
                            className="sidebar-section",
                            children=[
                                html.Div(
                                    "Pattern type (multi-select)",
                                    className="sidebar-section-title",
                                ),
                                pattern_type_checklist,
                            ],
                        ),
                        # Window size (فقط یک slider، فعلا به صورت scalar)
                        html.Div(
                            className="sidebar-section",
                            children=[
                                html.Div("Window size", className="sidebar-section-title"),
                                html.Div(
                                    className="sidebar-row",
                                    children=[
                                        html.Label("2 → 11"),
                                        html.Span(id="window-size-current", children="current: 5"),
                                    ],
                                ),
                                dcc.Slider(
                                    id="window-size-slider",
                                    min=2,
                                    max=11,
                                    step=1,
                                    value=5,
                                ),
                                html.Div(
                                    className="slider-label-row",
                                    children=[html.Span("min 2"), html.Span("max 11")],
                                ),
                            ],
                        ),
                        # Pattern metrics filters (range)
                        html.Div(
                            className="sidebar-section",
                            children=[
                                html.Div(
                                    "Pattern metrics filters",
                                    className="sidebar-section-title",
                                ),
                                # Lift range
                                html.Div(
                                    className="metric-block",
                                    children=[
                                        html.Div(
                                            className="sidebar-row",
                                            children=[
                                                html.Label("Lift range"),
                                                html.Span("1.00 – 2.00"),
                                            ],
                                        ),
                                        html.Div(
                                            className="range-row",
                                            children=[
                                                html.Span("min", className="range-label"),
                                                dcc.Slider(
                                                    id="lift-min-slider",
                                                    min=1.0,
                                                    max=2.0,
                                                    step=0.01,
                                                    value=1.0,
                                                ),
                                                html.Span(
                                                    id="lift-min-value",
                                                    children="1.00",
                                                    className="range-value",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="range-row",
                                            children=[
                                                html.Span("max", className="range-label"),
                                                dcc.Slider(
                                                    id="lift-max-slider",
                                                    min=1.0,
                                                    max=2.0,
                                                    step=0.01,
                                                    value=2.0,
                                                ),
                                                html.Span(
                                                    id="lift-max-value",
                                                    children="2.00",
                                                    className="range-value",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                # Stability
                                html.Div(
                                    className="metric-block",
                                    children=[
                                        html.Div(
                                            className="sidebar-row",
                                            children=[
                                                html.Label("Stability range"),
                                                html.Span("0.50 – 1.00"),
                                            ],
                                        ),
                                        html.Div(
                                            className="range-row",
                                            children=[
                                                html.Span("min", className="range-label"),
                                                dcc.Slider(
                                                    id="stab-min-slider",
                                                    min=0.5,
                                                    max=1.0,
                                                    step=0.01,
                                                    value=0.8,
                                                ),
                                                html.Span(
                                                    id="stab-min-value",
                                                    children="0.80",
                                                    className="range-value",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="range-row",
                                            children=[
                                                html.Span("max", className="range-label"),
                                                dcc.Slider(
                                                    id="stab-max-slider",
                                                    min=0.5,
                                                    max=1.0,
                                                    step=0.01,
                                                    value=1.0,
                                                ),
                                                html.Span(
                                                    id="stab-max-value",
                                                    children="1.00",
                                                    className="range-value",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                # Support
                                html.Div(
                                    className="metric-block",
                                    children=[
                                        html.Div(
                                            className="sidebar-row",
                                            children=[
                                                html.Label("Support range"),
                                                html.Span("5 – 300"),
                                            ],
                                        ),
                                        html.Div(
                                            className="range-row",
                                            children=[
                                                html.Span("min", className="range-label"),
                                                dcc.Slider(
                                                    id="sup-min-slider",
                                                    min=5,
                                                    max=300,
                                                    step=1,
                                                    value=20,
                                                ),
                                                html.Span(
                                                    id="sup-min-value",
                                                    children="20",
                                                    className="range-value",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="range-row",
                                            children=[
                                                html.Span("max", className="range-label"),
                                                dcc.Slider(
                                                    id="sup-max-slider",
                                                    min=5,
                                                    max=300,
                                                    step=1,
                                                    value=300,
                                                ),
                                                html.Span(
                                                    id="sup-max-value",
                                                    children="300",
                                                    className="range-value",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # Strength
                        html.Div(
                            className="sidebar-section",
                            children=[
                                html.Div(
                                    "Strength (families)",
                                    className="sidebar-section-title",
                                ),
                                strength_checklist,
                            ],
                        ),
                        # Overlays (فقط کنترلی؛ فعلاً روی چارت استفاده نمی‌کنیم)
                        html.Div(
                            className="sidebar-section",
                            children=[
                                html.Div("Overlays", className="sidebar-section-title"),
                                dcc.Checklist(
                                    id="overlay-checklist",
                                    options=[
                                        {"label": "Show zones", "value": "zones"},
                                        {"label": "Show markers", "value": "markers"},
                                        {
                                            "label": "Show density heatmap",
                                            "value": "heatmap",
                                        },
                                    ],
                                    value=[],
                                    labelStyle={
                                        "display": "block",
                                        "fontSize": "11px",
                                    },
                                ),
                                html.Div(
                                    style={"marginTop": "6px"},
                                    children=[
                                        html.Div(
                                            className="sidebar-row",
                                            children=[
                                                html.Label("Max overlays (top N hits)"),
                                                html.Span(id="max-hits-value", children="300"),
                                            ],
                                        ),
                                        dcc.Slider(
                                            id="max-hits-slider",
                                            min=50,
                                            max=1000,
                                            step=50,
                                            value=300,
                                        ),
                                        html.Div(
                                            className="slider-label-row",
                                            children=[html.Span("50"), html.Span("1000")],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # Pattern selection
                        html.Div(
                            className="sidebar-section",
                            children=[
                                html.Div(
                                    "Pattern selection",
                                    className="sidebar-section-title",
                                ),
                                html.Div("pattern_id (multi)", className="sidebar-row"),
                                dcc.Dropdown(
                                    id="pattern-id-dropdown",
                                    options=[
                                        {"label": p, "value": p} for p in pattern_options
                                    ],
                                    multi=True,
                                ),
                                html.Div(
                                    "family_id (multi)",
                                    className="sidebar-row",
                                    style={"marginTop": "6px"},
                                ),
                                dcc.Dropdown(
                                    id="family-id-dropdown",
                                    options=[
                                        {"label": f, "value": f} for f in family_options
                                    ],
                                    multi=True,
                                ),
                                html.Div(
                                    style={"marginTop": "6px"},
                                    children=[
                                        html.Span(
                                            "Mode:",
                                            style={
                                                "fontSize": "11px",
                                                "fontWeight": 600,
                                            },
                                        ),
                                        dcc.RadioItems(
                                            id="allow-block-radio",
                                            options=[
                                                {"label": "Allow list", "value": "allow"},
                                                {"label": "Block list", "value": "block"},
                                            ],
                                            value="allow",
                                            labelStyle={
                                                "display": "inline-flex",
                                                "marginRight": "8px",
                                                "fontSize": "11px",
                                            },
                                            inputStyle={"marginRight": "4px"},
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                # Content
                html.Main(
                    className="content-area",
                    children=[
                        html.Div(
                            className="charts-wrapper",
                            children=[
                                dcc.Graph(
                                    id="chart-4h",
                                    figure=make_candlestick_figure(
                                        ohlc_4h[
                                            ohlc_4h["time"]
                                            >= (ohlc_4h["time"].max() - timedelta(days=7))
                                        ],
                                        "BTCUSDT – 4H Candles",
                                    ),
                                    config={"displaylogo": False},
                                ),
                                dcc.Graph(
                                    id="chart-5m",
                                    figure=make_candlestick_figure(
                                        ohlc_5m[
                                            ohlc_5m["time"]
                                            >= (ohlc_5m["time"].max() - timedelta(days=1))
                                        ],
                                        "BTCUSDT – 5M Candles",
                                    ),
                                    config={"displaylogo": False},
                                ),
                            ],
                        ),
                        html.Section(
                            className="info-panel",
                            children=[
                                html.Div(
                                    className="info-header",
                                    children=[
                                        html.Div(
                                            "Info Panel – Pattern / Candle / Family",
                                            className="info-title",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="info-body",
                                    children=[
                                        # Pattern-centric table
                                        html.Div(
                                            className="info-section",
                                            children=[
                                                html.Div(
                                                    "Pattern View (pattern-centric)",
                                                    className="info-section-title",
                                                ),
                                                dash_table.DataTable(
                                                    id="pattern-table",
                                                    columns=[
                                                        {"name": "timeframe", "id": "timeframe"},
                                                        {"name": "pattern_id", "id": "pattern_id"},
                                                        {"name": "w", "id": "w"},
                                                        {
                                                            "name": "pattern_type",
                                                            "id": "pattern_type",
                                                        },
                                                        {"name": "role", "id": "role"},
                                                        {"name": "support", "id": "support"},
                                                        {"name": "lift", "id": "lift"},
                                                        {
                                                            "name": "stability",
                                                            "id": "stability",
                                                        },
                                                        {"name": "score", "id": "score"},
                                                        {
                                                            "name": "family_id",
                                                            "id": "family_id",
                                                        },
                                                        {
                                                            "name": "strength",
                                                            "id": "strength",
                                                        },
                                                        {
                                                            "name": "start_time",
                                                            "id": "start_time",
                                                        },
                                                        {"name": "ans_time", "id": "ans_time"},
                                                    ],
                                                    page_size=10,
                                                    style_table={
                                                        "overflowX": "auto",
                                                        "fontSize": 11,
                                                    },
                                                    style_cell={"padding": "3px"},
                                                ),
                                            ],
                                        ),
                                        # Candle-centric
                                        html.Div(
                                            className="info-section",
                                            children=[
                                                html.Div(
                                                    "Candle View (candle-centric)",
                                                    className="info-section-title",
                                                ),
                                                html.Div(
                                                    id="candle-summary",
                                                    style={
                                                        "fontSize": "11px",
                                                        "marginBottom": "4px",
                                                    },
                                                ),
                                                dash_table.DataTable(
                                                    id="candle-pattern-table",
                                                    columns=[
                                                        {
                                                            "name": "pattern_id",
                                                            "id": "pattern_id",
                                                        },
                                                        {
                                                            "name": "timeframe",
                                                            "id": "timeframe",
                                                        },
                                                        {"name": "w", "id": "w"},
                                                        {
                                                            "name": "pattern_type",
                                                            "id": "pattern_type",
                                                        },
                                                        {"name": "role", "id": "role"},
                                                        {
                                                            "name": "family_id",
                                                            "id": "family_id",
                                                        },
                                                        {
                                                            "name": "strength",
                                                            "id": "strength",
                                                        },
                                                        {
                                                            "name": "support",
                                                            "id": "support",
                                                        },
                                                        {"name": "lift", "id": "lift"},
                                                        {
                                                            "name": "stability",
                                                            "id": "stability",
                                                        },
                                                        {"name": "score", "id": "score"},
                                                    ],
                                                    page_size=10,
                                                    style_table={
                                                        "overflowX": "auto",
                                                        "fontSize": 11,
                                                    },
                                                    style_cell={"padding": "3px"},
                                                ),
                                            ],
                                        ),
                                        # Family view
                                        html.Div(
                                            className="info-section",
                                            children=[
                                                html.Div(
                                                    "Family View (family-centric)",
                                                    className="info-section-title",
                                                ),
                                                dash_table.DataTable(
                                                    id="family-table",
                                                    columns=[
                                                        {
                                                            "name": "family_id",
                                                            "id": "family_id",
                                                        },
                                                        {
                                                            "name": "timeframe",
                                                            "id": "timeframe",
                                                        },
                                                        {
                                                            "name": "pattern_id",
                                                            "id": "pattern_id",
                                                        },
                                                        {"name": "w", "id": "w"},
                                                        {
                                                            "name": "pattern_type",
                                                            "id": "pattern_type",
                                                        },
                                                        {"name": "support", "id": "support"},
                                                        {"name": "lift", "id": "lift"},
                                                        {
                                                            "name": "stability",
                                                            "id": "stability",
                                                        },
                                                        {"name": "score", "id": "score"},
                                                        {
                                                            "name": "strength",
                                                            "id": "strength",
                                                        },
                                                        {
                                                            "name": "hits_visible",
                                                            "id": "hits_visible",
                                                        },
                                                    ],
                                                    page_size=10,
                                                    style_table={
                                                        "overflowX": "auto",
                                                        "fontSize": 11,
                                                    },
                                                    style_cell={"padding": "3px"},
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------


@app.callback(
    Output("window-size-current", "children"),
    Input("window-size-slider", "value"),
)
def update_window_size_label(w):
    return f"current: {w}"


@app.callback(
    Output("lift-min-value", "children"),
    Output("lift-max-value", "children"),
    Output("stab-min-value", "children"),
    Output("stab-max-value", "children"),
    Output("sup-min-value", "children"),
    Output("sup-max-value", "children"),
    Output("max-hits-value", "children"),
    Input("lift-min-slider", "value"),
    Input("lift-max-slider", "value"),
    Input("stab-min-slider", "value"),
    Input("stab-max-slider", "value"),
    Input("sup-min-slider", "value"),
    Input("sup-max-slider", "value"),
    Input("max-hits-slider", "value"),
)
def update_range_labels(
    lift_min,
    lift_max,
    stab_min,
    stab_max,
    sup_min,
    sup_max,
    max_hits,
):
    return (
        f"{lift_min:.2f}",
        f"{lift_max:.2f}",
        f"{stab_min:.2f}",
        f"{stab_max:.2f}",
        str(int(sup_min)),
        str(int(sup_max)),
        str(int(max_hits)),
    )


@app.callback(
    Output("chart-4h", "figure"),
    Output("chart-5m", "figure"),
    Output("pattern-table", "data"),
    Output("candle-summary", "children"),
    Output("candle-pattern-table", "data"),
    Output("family-table", "data"),
    Input("tf-checklist", "value"),
    Input("pattern-type-checklist", "value"),
    Input("strength-checklist", "value"),
    Input("lift-min-slider", "value"),
    Input("lift-max-slider", "value"),
    Input("stab-min-slider", "value"),
    Input("stab-max-slider", "value"),
    Input("sup-min-slider", "value"),
    Input("sup-max-slider", "value"),
    Input("pattern-id-dropdown", "value"),
    Input("family-id-dropdown", "value"),
    Input("allow-block-radio", "value"),
    Input("max-hits-slider", "value"),
    Input("chart-4h", "relayoutData"),
    Input("overlay-checklist", "value"),
    Input("chart-4h", "clickData"),
)
def update_all(
    tf_list,
    pattern_types,
    strengths,
    lift_min,
    lift_max,
    stab_min,
    stab_max,
    sup_min,
    sup_max,
    pattern_ids,
    family_ids,
    allow_mode,
    max_hits,
    relayout,
    overlay_values,
    click_data,
):
    if pattern_ids is None:
        pattern_ids = []
    if family_ids is None:
        family_ids = []
    if overlay_values is None:
        overlay_values = []

    # 1) تعیین بازه زمانی 4h از روی zoom (relayoutData) یا 7 روز آخر
    start_4h, end_4h = get_initial_window_4h(days=7)
    if relayout and "xaxis.range[0]" in relayout and "xaxis.range[1]" in relayout:
        try:
            start_4h = pd.to_datetime(relayout["xaxis.range[0]"])
            end_4h = pd.to_datetime(relayout["xaxis.range[1]"])
        except Exception:
            pass

    # 2) فیلتر کندل‌ها
    df_4h = ohlc_4h[
        (ohlc_4h["time"] >= start_4h) & (ohlc_4h["time"] <= end_4h)
    ].copy()

    # 5m window = همان بازه 4h (برای simplicity)
    df_5m = ohlc_5m[
        (ohlc_5m["time"] >= start_4h) & (ohlc_5m["time"] <= end_4h)
    ].copy()

    fig_4h = make_candlestick_figure(df_4h, "BTCUSDT – 4H Candles")
    fig_5m = make_candlestick_figure(df_5m, "BTCUSDT – 5M Candles")

    # 3) فیلتر hits بر اساس همه فیلترها
    hits_filtered = filter_hits(
        timeframe_list=tf_list,
        pattern_types=pattern_types,
        strength_levels=strengths,
        lift_min=lift_min,
        lift_max=lift_max,
        stab_min=stab_min,
        stab_max=stab_max,
        sup_min=sup_min,
        sup_max=sup_max,
        pattern_allow_ids=pattern_ids,
        family_allow_ids=family_ids,
        allow_mode=allow_mode,
        start_time=start_4h,
        end_time=end_4h,
    ).sort_values("score", ascending=False)

    # محدودیت top N hits
    if len(hits_filtered) > max_hits:
        hits_filtered = hits_filtered.head(max_hits)

    zones_enabled = "zones" in overlay_values
    markers_enabled = "markers" in overlay_values

    # Zones for 4h
    shapes_4h = []
    if zones_enabled and not df_4h.empty and not hits_filtered.empty:
        y0_4h = df_4h["low"].min()
        y1_4h = df_4h["high"].max()
        hits_4h_zone = hits_filtered[hits_filtered["timeframe"] == "4h"]
        for _, row in hits_4h_zone.iterrows():
            rgb = _pattern_rgb(row["pattern_type"])
            shapes_4h.append(
                dict(
                    type="rect",
                    xref="x",
                    yref="y",
                    x0=row["start_time"],
                    x1=row["ans_time"],
                    y0=y0_4h,
                    y1=y1_4h,
                    fillcolor=_rgba_str(rgb, 0.18),
                    line={"color": _rgba_str(rgb, 0.35), "width": 0.4},
                    layer="below",
                )
            )

    # Zones for 5m
    shapes_5m = []
    if zones_enabled and not df_5m.empty and not hits_filtered.empty:
        y0_5m = df_5m["low"].min()
        y1_5m = df_5m["high"].max()
        hits_5m_zone = hits_filtered[hits_filtered["timeframe"] == "5m"]
        for _, row in hits_5m_zone.iterrows():
            rgb = _pattern_rgb(row["pattern_type"])
            shapes_5m.append(
                dict(
                    type="rect",
                    xref="x",
                    yref="y",
                    x0=row["start_time"],
                    x1=row["ans_time"],
                    y0=y0_5m,
                    y1=y1_5m,
                    fillcolor=_rgba_str(rgb, 0.18),
                    line={"color": _rgba_str(rgb, 0.35), "width": 0.4},
                    layer="below",
                )
            )

    # Marker overlays
    if markers_enabled and not hits_filtered.empty:
        def marker_trace(df_prices, subset, name):
            if df_prices.empty or subset.empty:
                return None
            xs = []
            ys = []
            colors = []
            symbols = []
            texts = []
            for _, row in subset.iterrows():
                ans_time = row["ans_time"]
                price_row = df_prices[df_prices["time"] <= ans_time].tail(1)
                if price_row.empty:
                    continue
                price_val = price_row.iloc[0]["close"]
                xs.append(ans_time)
                ys.append(price_val)
                rgb = _pattern_rgb(row["pattern_type"])
                colors.append(_rgba_str(rgb, 0.9))
                symbols.append(
                    "triangle-up"
                    if row.get("role", "answer") == "answer"
                    else "circle"
                )
                texts.append(f"{row['pattern_id']} ({row['pattern_type']})")
            if not xs:
                return None
            return go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                marker={
                    "color": colors,
                    "size": 8,
                    "symbol": symbols,
                    "line": {"width": 0.6, "color": "rgba(0,0,0,0.2)"},
                },
                name=name,
                text=texts,
                hoverinfo="text+x+y",
                showlegend=False,
            )

        trace_4h_markers = marker_trace(
            df_4h, hits_filtered[hits_filtered["timeframe"] == "4h"], "4h hits"
        )
        trace_5m_markers = marker_trace(
            df_5m, hits_filtered[hits_filtered["timeframe"] == "5m"], "5m hits"
        )
        if trace_4h_markers:
            fig_4h.add_trace(trace_4h_markers)
        if trace_5m_markers:
            fig_5m.add_trace(trace_5m_markers)

    if shapes_4h:
        fig_4h.update_layout(shapes=shapes_4h)
    if shapes_5m:
        fig_5m.update_layout(shapes=shapes_5m)

    # TODO: Optional heatmap overlay can be added here using hits_filtered density.

    # pattern table (pattern-centric)
    pattern_table_data = hits_filtered.to_dict("records")

    # 4) Candle-centric: کندل آخر 4h در بازه را به عنوان نمونه در نظر می‌گیریم
    candle_summary = ""
    candle_pattern_data = []
    if not df_4h.empty:
        selected_time = None
        if click_data and "points" in click_data and click_data["points"]:
            try:
                selected_time = pd.to_datetime(click_data["points"][0]["x"])
            except Exception:
                selected_time = None
        if selected_time is None:
            selected_time = df_4h.iloc[-1]["time"]

        candle_row_exact = df_4h[df_4h["time"] == selected_time]
        if candle_row_exact.empty:
            candle_row = df_4h.iloc[-1]
        else:
            candle_row = candle_row_exact.iloc[0]
        candle_time = candle_row["time"]

        # hitsی که این کندل بین start_time و ans_time آنها قرار دارد
        mask = (hits_filtered["start_time"] <= candle_time) & (
            hits_filtered["ans_time"] >= candle_time
        )
        candle_hits = hits_filtered[mask].copy()

        candle_summary = (
            f"Candle @ {candle_time} · "
            f"O: {candle_row['open']:.2f} · "
            f"H: {candle_row['high']:.2f} · "
            f"L: {candle_row['low']:.2f} · "
            f"C: {candle_row['close']:.2f} "
            f"| Patterns affecting: {len(candle_hits)}"
        )
        candle_pattern_data = candle_hits.to_dict("records")

    # 5) Family view: جمع hits بر اساس family_id + timeframe
    if hits_filtered.empty:
        family_table_data = []
    else:
        grp = (
            hits_filtered.groupby(["family_id", "timeframe", "pattern_id"])
            .agg(
                {
                    "w": "max",
                    "pattern_type": "first",
                    "support": "mean",
                    "lift": "mean",
                    "stability": "mean",
                    "score": "mean",
                    "strength": "first",
                    "pattern_id": "size",
                }
            )
            .rename(columns={"pattern_id": "hits_visible"})
            .reset_index()
        )
        family_table_data = grp.to_dict("records")

    return (
        fig_4h,
        fig_5m,
        pattern_table_data,
        candle_summary,
        candle_pattern_data,
        family_table_data,
    )


# ---------------------------------------------------------------------
if __name__ == "__main__":
    if callable(getattr(app, "run", None)):
        app.run(debug=True)
    else:
        app.run_server(debug=True)
