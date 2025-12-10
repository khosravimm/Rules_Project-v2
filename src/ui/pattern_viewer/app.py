"""
Dash Pattern Viewer UI for PrisonBreaker (BTCUSDT 4h/5m, Level-1 patterns)

Run with:
    cd D:/Code/chatgpt/Rules_Project-v2
    python -m src.ui.pattern_viewer.app

App will listen on http://127.0.0.1:8050
"""

import os
import pathlib
from functools import lru_cache
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import dash
from dash import Dash, dcc, html, dash_table, Input, Output, State
import plotly.graph_objects as go
import requests

UI_TIMEZONE = "Asia/Tehran"
TEHRAN_TZ = ZoneInfo("Asia/Tehran")
WINDOW_BEFORE_DEFAULT = 80
WINDOW_AFTER_DEFAULT = 40
API_BASE_URL = os.getenv("PATTERN_API_URL", "http://127.0.0.1:8000")

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
            "time": pd.to_datetime(df[ts_col], utc=True).dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None),
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
    out["pattern_id"] = df[pattern_col].astype(str)
    # assign timeframe after index is established so it fills all rows
    out["timeframe"] = timeframe

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

    start_ts_utc = pd.to_datetime(df[start_col], utc=True, errors="coerce")
    ans_ts_utc = pd.to_datetime(df[ans_col], utc=True, errors="coerce")
    out["start_time_utc"] = start_ts_utc
    out["ans_time_utc"] = ans_ts_utc
    out["start_time"] = start_ts_utc.dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
    out["ans_time"] = ans_ts_utc.dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)

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


@lru_cache(maxsize=1)
def _load_all_data():
    """Lazy-load OHLC and hits once, after the UI is ready."""
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
    return ohlc_4h, ohlc_5m, hits_4h, hits_5m


def _fetch_candles_api(timeframe: str, center_ts: str, before: int, after: int) -> pd.DataFrame:
    """Fetch candles from API using center window; fallback to empty frame on failure."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/candles",
            params={
                "timeframe": timeframe,
                "center": center_ts,
                "window_before": before,
                "window_after": after,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"status {resp.status_code}: {resp.text}")
        payload = resp.json()
        candles = payload.get("candles", [])
        if not candles:
            return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume"])
        df = pd.DataFrame(candles)
        df["open_time"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        return df.rename(columns={"timestamp": "open_time"})
    except Exception as exc:  # noqa: broad-except
        print(f"[UI] Warning: failed to fetch candles from API ({timeframe}): {exc}")
        return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume"])


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------


def get_initial_window_4h(days: int = 7):
    """Return (start, end) for last `days` days on 4h timeframe."""
    ohlc_4h, _, _, _ = _load_all_data()
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
    window_sizes,
    pattern_allow_ids,
    family_allow_ids,
    allow_mode="allow",
    start_time=None,
    end_time=None,
):
    """Apply all filters on hits and return a filtered dataframe."""
    _, _, hits_4h, hits_5m = _load_all_data()
    frames = []
    if "4h" in timeframe_list:
        frames.append(hits_4h)
    if "5m" in timeframe_list:
        frames.append(hits_5m)
    if not frames:
        return _empty_hits_df("4h")

    df = pd.concat(frames, ignore_index=True)

    # normalize window interval so that x0 <= x1 and strip tz
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce").dt.tz_localize(None)
    df["ans_time"] = pd.to_datetime(df["ans_time"], errors="coerce").dt.tz_localize(None)
    df["x0"] = pd.DataFrame({"a": df["start_time"], "b": df["ans_time"]}).min(axis=1)
    df["x1"] = pd.DataFrame({"a": df["start_time"], "b": df["ans_time"]}).max(axis=1)
    df = df.dropna(subset=["x0", "x1"])

    if pattern_types:
        df = df[df["pattern_type"].isin(pattern_types)]

    if strength_levels:
        df = df[df["strength"].isin(strength_levels)]

    # window sizes
    if window_sizes:
        window_set = set(int(x) for x in window_sizes if pd.notna(x))
        df = df[df["w"].isin(window_set)]

    df = df[
        (df["lift"] >= lift_min)
        & (df["lift"] <= lift_max)
        & (df["stability"] >= stab_min)
        & (df["stability"] <= stab_max)
        & (df["support"] >= sup_min)
        & (df["support"] <= sup_max)
    ]

    if start_time is not None:
        df = df[df["x1"] >= start_time]
    if end_time is not None:
        df = df[df["x0"] <= end_time]

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
    """
    TradingView-like candlestick:
    - رنگ سبز/قرمز تمیز
    - grid سبک
    - crosshair روی محور X/Y
    - hovermode "x unified"
    - بدون range slider
    """
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_white",
            xaxis=dict(
                title="time",
                showgrid=True,
                gridcolor="rgba(180,180,180,0.2)",
                rangeslider=dict(visible=False),
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikethickness=1,
                spikedash="solid",
            ),
            yaxis=dict(
                title="price",
                showgrid=True,
                gridcolor="rgba(180,180,180,0.2)",
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikethickness=1,
                spikedash="solid",
            ),
            margin=dict(l=40, r=10, t=30, b=20),
            title=title + " (no data)",
            dragmode="pan",
            hovermode="x unified",
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
                increasing_line_color="#26a69a",
                increasing_fillcolor="#26a69a",
                decreasing_line_color="#ef5350",
                decreasing_fillcolor="#ef5350",
                whiskerwidth=0.4,
            )
        ]
    )

    fig.update_layout(
        template="plotly_white",
        xaxis=dict(
            title="time",
            showgrid=True,
            gridcolor="rgba(180,180,180,0.2)",
            rangeslider=dict(visible=False),
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikedash="solid",
        ),
        yaxis=dict(
            title="price",
            showgrid=True,
            gridcolor="rgba(180,180,180,0.2)",
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikedash="solid",
        ),
        margin=dict(l=40, r=10, t=30, b=20),
        title=title,
        dragmode="pan",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
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

ASSETS_PATH = pathlib.Path(__file__).parent / "assets"

app = Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    assets_folder=str(ASSETS_PATH),
    title="PrisonBreaker - Pattern Viewer",
)

# ---- layout (Pattern Viewer Dashboard) -------------

timeframe_checklist = dcc.Checklist(
    id="tf-checklist",
    options=[
        {"label": "4h", "value": "4h"},
        {"label": "5m", "value": "5m"},
    ],
    value=["4h"],
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

pattern_options = []
family_options = []

# layout اصلی
app.layout = html.Div(
    className="app-container",
    children=[
        dcc.Interval(id="data-loader", interval=250, n_intervals=0, max_intervals=1),
        dcc.Store(id="store-hits"),
        dcc.Store(id="selected-hit-ts"),
        # Header
        html.Div(
            className="header",
            children=[
                html.Div(
                    [
                        html.Div(
                            "PrisonBreaker – BTCUSDT Pattern Dashboard (Dash UI) · updated by Codex &",
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
                        # Window size
                        html.Div(
                            className="sidebar-section",
                            children=[
                                html.Div("Window size", className="sidebar-section-title"),
                                dcc.Dropdown(
                                    id="window-size-dropdown",
                                    options=[{"label": str(i), "value": i} for i in range(2, 12)],
                                    multi=True,
                                    value=[5],
                                    placeholder="Select window sizes",
                                    style={"fontSize": "12px"},
                                ),
                                html.Div(
                                    id="window-size-current",
                                    style={"fontSize": "11px", "marginTop": "4px"},
                                    children="selected: 5",
                                ),
                            ],
                        ),
                        # Pattern metrics filters
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
                                        dcc.RangeSlider(
                                            id="lift-range-slider",
                                            min=1.0,
                                            max=2.0,
                                            step=0.01,
                                            value=[1.0, 2.0],
                                            tooltip={"placement": "bottom", "always_visible": False},
                                        ),
                                        html.Div(
                                            className="slider-label-row",
                                            children=[
                                                html.Span(id="lift-min-value", children="1.00"),
                                                html.Span(id="lift-max-value", children="2.00"),
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
                                        dcc.RangeSlider(
                                            id="stab-range-slider",
                                            min=0.5,
                                            max=1.0,
                                            step=0.01,
                                            value=[0.8, 1.0],
                                            tooltip={"placement": "bottom", "always_visible": False},
                                        ),
                                        html.Div(
                                            className="slider-label-row",
                                            children=[
                                                html.Span(id="stab-min-value", children="0.80"),
                                                html.Span(id="stab-max-value", children="1.00"),
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
                                        dcc.RangeSlider(
                                            id="sup-range-slider",
                                            min=5,
                                            max=300,
                                            step=1,
                                            value=[20, 300],
                                            tooltip={"placement": "bottom", "always_visible": False},
                                        ),
                                        html.Div(
                                            className="slider-label-row",
                                            children=[
                                                html.Span(id="sup-min-value", children="20"),
                                                html.Span(id="sup-max-value", children="300"),
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
                        # Overlays
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
                                    value=["zones", "markers"],
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
                                                html.Span(
                                                    id="max-hits-value",
                                                    children="150",
                                                ),
                                            ],
                                        ),
                                        dcc.Slider(
                                            id="max-hits-slider",
                                            min=50,
                                            max=500,
                                            step=50,
                                            value=150,
                                        ),
                                        html.Div(
                                            className="slider-label-row",
                                            children=[html.Span("50"), html.Span("500")],
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
                                html.Div(
                                    style={
                                        "display": "flex",
                                        "gap": "6px",
                                        "marginBottom": "6px",
                                    },
                                    children=[
                                        html.Button(
                                            "Select all patterns",
                                            id="pattern-select-all",
                                            n_clicks=0,
                                            style={
                                                "fontSize": "11px",
                                                "padding": "4px 6px",
                                            },
                                        ),
                                        html.Button(
                                            "Clear patterns",
                                            id="pattern-clear",
                                            n_clicks=0,
                                            style={
                                                "fontSize": "11px",
                                                "padding": "4px 6px",
                                            },
                                        ),
                                    ],
                                ),
                                html.Button(
                                    "Apply filters",
                                    id="apply-filters",
                                    n_clicks=0,
                                    style={
                                        "marginBottom": "8px",
                                        "padding": "4px 10px",
                                        "fontSize": "12px",
                                    },
                                ),
                                html.Div(
                                    "pattern_id (multi)",
                                    className="sidebar-row",
                                ),
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
                                html.Div(
                                    style={
                                        "display": "flex",
                                        "gap": "6px",
                                        "marginBottom": "6px",
                                    },
                                    children=[
                                        html.Button(
                                            "Select all families",
                                            id="family-select-all",
                                            n_clicks=0,
                                            style={
                                                "fontSize": "11px",
                                                "padding": "4px 6px",
                                            },
                                        ),
                                        html.Button(
                                            "Clear families",
                                            id="family-clear",
                                            n_clicks=0,
                                            style={
                                                "fontSize": "11px",
                                                "padding": "4px 6px",
                                            },
                                        ),
                                    ],
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
                                        pd.DataFrame(), "BTCUSDT - 4H Candles"
                                    ),
                                    config={"displaylogo": False},
                                ),
                                dcc.Graph(
                                    id="chart-5m",
                                    figure=make_candlestick_figure(
                                        pd.DataFrame(), "BTCUSDT - 5M Candles"
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
                                        dcc.Tabs(
                                            id="info-tabs",
                                            value="pattern",
                                            children=[
                                                dcc.Tab(
                                                    label="Pattern",
                                                    value="pattern",
                                                    children=[
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
                                                                        {"name": "pattern_type", "id": "pattern_type"},
                                                                        {"name": "role", "id": "role"},
                                                                        {"name": "support", "id": "support"},
                                                                        {"name": "lift", "id": "lift"},
                                                                        {"name": "stability", "id": "stability"},
                                                                        {"name": "score", "id": "score"},
                                                                        {"name": "family_id", "id": "family_id"},
                                                                        {"name": "strength", "id": "strength"},
                                                                        {"name": "start_time", "id": "start_time"},
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
                                                    ],
                                                ),
                                                dcc.Tab(
                                                    label="Candle",
                                                    value="candle",
                                                    children=[
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
                                                                        {"name": "pattern_id", "id": "pattern_id"},
                                                                        {"name": "timeframe", "id": "timeframe"},
                                                                        {"name": "w", "id": "w"},
                                                                        {"name": "pattern_type", "id": "pattern_type"},
                                                                        {"name": "role", "id": "role"},
                                                                        {"name": "family_id", "id": "family_id"},
                                                                        {"name": "strength", "id": "strength"},
                                                                        {"name": "support", "id": "support"},
                                                                        {"name": "lift", "id": "lift"},
                                                                        {"name": "stability", "id": "stability"},
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
                                                    ],
                                                ),
                                                dcc.Tab(
                                                    label="Family",
                                                    value="family",
                                                    children=[
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
                                                                        {"name": "family_id", "id": "family_id"},
                                                                        {"name": "timeframe", "id": "timeframe"},
                                                                        {"name": "pattern_id", "id": "pattern_id"},
                                                                        {"name": "w", "id": "w"},
                                                                        {"name": "pattern_type", "id": "pattern_type"},
                                                                        {"name": "support", "id": "support"},
                                                                        {"name": "lift", "id": "lift"},
                                                                        {"name": "stability", "id": "stability"},
                                                                        {"name": "score", "id": "score"},
                                                                        {"name": "strength", "id": "strength"},
                                                                        {"name": "hits_visible", "id": "hits_visible"},
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
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------


@app.callback(
    Output("info-tabs", "value"),
    Input("view-mode-radio", "value"),
)
def sync_tabs_with_view_mode(view_mode):
    if view_mode in ("pattern", "candle", "family"):
        return view_mode
    return "pattern"


@app.callback(
    Output("window-size-current", "children"),
    Input("window-size-dropdown", "value"),
)
def update_window_size_label(w):
    if not w:
        return "selected: none"
    return "selected: " + ", ".join(str(i) for i in w)


@app.callback(
    Output("lift-min-value", "children"),
    Output("lift-max-value", "children"),
    Output("stab-min-value", "children"),
    Output("stab-max-value", "children"),
    Output("sup-min-value", "children"),
    Output("sup-max-value", "children"),
    Output("max-hits-value", "children"),
    Input("lift-range-slider", "value"),
    Input("stab-range-slider", "value"),
    Input("sup-range-slider", "value"),
    Input("max-hits-slider", "value"),
)
def update_range_labels(
    lift_range,
    stab_range,
    sup_range,
    max_hits,
):
    lift_min, lift_max = lift_range
    stab_min, stab_max = stab_range
    sup_min, sup_max = sup_range
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
    Output("pattern-id-dropdown", "options"),
    Output("family-id-dropdown", "options"),
    Output("pattern-id-dropdown", "value"),
    Output("family-id-dropdown", "value"),
    Input("data-loader", "n_intervals"),
    Input("pattern-select-all", "n_clicks"),
    Input("pattern-clear", "n_clicks"),
    Input("family-select-all", "n_clicks"),
    Input("family-clear", "n_clicks"),
    State("pattern-id-dropdown", "options"),
    State("family-id-dropdown", "options"),
)
def load_dropdown_options(_, p_all, p_clear, f_all, f_clear, current_pattern_opts, current_family_opts):
    _, _, hits_4h, hits_5m = _load_all_data()

    def build_options(series):
        if series.empty:
            return []
        return (
            series.dropna()
            .astype(str)
            .drop_duplicates()
            .sort_values()
            .map(lambda v: {"label": v, "value": v})
            .tolist()
        )

    pattern_opts = build_options(pd.concat([hits_4h["pattern_id"], hits_5m["pattern_id"]], ignore_index=True))
    family_opts = build_options(pd.concat([hits_4h["family_id"], hits_5m["family_id"]], ignore_index=True))

    pattern_value = dash.no_update
    family_value = dash.no_update
    ctx = dash.callback_context
    if ctx.triggered:
        trig = ctx.triggered[0]["prop_id"].split(".")[0]
        if trig == "pattern-select-all":
            pattern_value = [o["value"] for o in pattern_opts]
        elif trig == "pattern-clear":
            pattern_value = []
        elif trig == "family-select-all":
            family_value = [o["value"] for o in family_opts]
        elif trig == "family-clear":
            family_value = []
    return pattern_opts, family_opts, pattern_value, family_value


@app.callback(
    Output("store-hits", "data"),
    Input("data-loader", "n_intervals"),
    Input("apply-filters", "n_clicks"),
    Input("pattern-select-all", "n_clicks"),
    Input("pattern-clear", "n_clicks"),
    Input("family-select-all", "n_clicks"),
    Input("family-clear", "n_clicks"),
    Input("window-size-dropdown", "value"),
    State("tf-checklist", "value"),
    State("pattern-type-checklist", "value"),
    State("strength-checklist", "value"),
    State("lift-range-slider", "value"),
    State("stab-range-slider", "value"),
    State("sup-range-slider", "value"),
    State("window-size-dropdown", "value"),
    State("pattern-id-dropdown", "value"),
    State("family-id-dropdown", "value"),
    State("allow-block-radio", "value"),
    State("max-hits-slider", "value"),
)
def compute_hits_store(
    _n_intervals,
    _n_clicks,
    _p_all,
    _p_clear,
    _f_all,
    _f_clear,
    window_sizes_state,
    tf_list,
    pattern_types,
    strengths,
    lift_range,
    stab_range,
    sup_range,
    window_sizes,
    pattern_ids,
    family_ids,
    allow_mode,
    max_hits,
):
    if pattern_ids is None:
        pattern_ids = []
    if family_ids is None:
        family_ids = []
    _load_all_data()
    window_sizes = [int(x) for x in (window_sizes_state or []) if x is not None]
    lift_min, lift_max = lift_range
    stab_min, stab_max = stab_range
    sup_min, sup_max = sup_range
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
        window_sizes=window_sizes or [],
        pattern_allow_ids=pattern_ids,
        family_allow_ids=family_ids,
        allow_mode=allow_mode,
        start_time=None,
        end_time=None,
    ).sort_values("score", ascending=False)

    for col in ["start_time", "ans_time", "start_time_utc", "ans_time_utc"]:
        if col in hits_filtered:
            hits_filtered[col] = pd.to_datetime(hits_filtered[col], errors="coerce", utc=True)
            hits_filtered[col] = hits_filtered[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return hits_filtered.to_dict("records")


@app.callback(
    Output("selected-hit-ts", "data"),
    Input("pattern-table", "active_cell"),
    Input("store-hits", "data"),
)
def set_selected_hit(active_cell, hits_data):
    df = pd.DataFrame(hits_data or [])
    if df.empty:
        return dash.no_update
    if active_cell and "row" in active_cell and active_cell["row"] < len(df):
        row = df.iloc[active_cell["row"]]
        ts = row.get("ans_time_utc") or row.get("ans_time")
        return ts
    latest = df.sort_values("ans_time_utc" if "ans_time_utc" in df else "ans_time").iloc[-1]
    return latest.get("ans_time_utc") or latest.get("ans_time")


@app.callback(
    Output("chart-4h", "figure"),
    Output("chart-5m", "figure"),
    Input("store-hits", "data"),
    Input("overlay-checklist", "value"),
    Input("chart-4h", "relayoutData"),
    Input("max-hits-slider", "value"),
    Input("selected-hit-ts", "data"),
)
def update_charts(hits_data, overlay_values, relayout, max_hits, selected_hit_ts):
    if overlay_values is None:
        overlay_values = []
    ohlc_4h, ohlc_5m, _, _ = _load_all_data()
    hits_df = pd.DataFrame(hits_data or [])
    if not hits_df.empty:
        hits_df["start_time"] = pd.to_datetime(hits_df["start_time"], errors="coerce", utc=True)
        hits_df["ans_time"] = pd.to_datetime(hits_df["ans_time"], errors="coerce", utc=True)
        hits_df["start_time_utc"] = pd.to_datetime(hits_df.get("start_time_utc"), errors="coerce", utc=True)
        hits_df["ans_time_utc"] = pd.to_datetime(hits_df.get("ans_time_utc"), errors="coerce", utc=True)
        hits_df["x0"] = pd.DataFrame({"a": hits_df["start_time"], "b": hits_df["ans_time"]}).min(axis=1)
        hits_df["x1"] = pd.DataFrame({"a": hits_df["start_time"], "b": hits_df["ans_time"]}).max(axis=1)
        hits_df["x0_local"] = hits_df["x0"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
        hits_df["x1_local"] = hits_df["x1"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
        hits_df["ans_time_local"] = hits_df["ans_time"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
        hits_df = hits_df.dropna(subset=["x0", "x1"])

    center_ts = None
    if selected_hit_ts:
        center_ts = pd.to_datetime(selected_hit_ts, utc=True, errors="coerce")
    if center_ts is None and not hits_df.empty:
        center_ts = hits_df["ans_time_utc"].dropna().max() if "ans_time_utc" in hits_df else hits_df["ans_time"].max()

    # Fetch candles from API (preferred), fallback to local cache window
    window_4h = None
    window_5m = None
    if center_ts is not None:
        center_iso = center_ts.isoformat().replace("+00:00", "Z")
        window_4h = _fetch_candles_api("4h", center_iso, WINDOW_BEFORE_DEFAULT, WINDOW_AFTER_DEFAULT)
        window_5m = _fetch_candles_api("5m", center_iso, WINDOW_BEFORE_DEFAULT, WINDOW_AFTER_DEFAULT)

    if window_4h is not None and not window_4h.empty:
        start_4h = window_4h["open_time"].min()
        end_4h = window_4h["open_time"].max()
    else:
        start_4h, end_4h = get_initial_window_4h(days=3)

    if window_5m is None or window_5m.empty:
        window_5m = None

    if not hits_df.empty and "x0" in hits_df:
        start_utc = start_4h
        end_utc = end_4h
        if start_4h is not None and getattr(start_4h, "tzinfo", None) is None:
            try:
                start_utc = pd.Timestamp(start_4h).tz_localize(UI_TIMEZONE).tz_convert("UTC")
            except Exception:
                start_utc = start_4h
        if end_4h is not None and getattr(end_4h, "tzinfo", None) is None:
            try:
                end_utc = pd.Timestamp(end_4h).tz_localize(UI_TIMEZONE).tz_convert("UTC")
            except Exception:
                end_utc = end_4h
        hits_window = hits_df[
            (hits_df["x0"] <= end_utc) & (hits_df["x1"] >= start_utc)
        ]
    else:
        hits_window = hits_df
    if max_hits is not None and max_hits > 0 and len(hits_window) > max_hits:
        hits_window = (
            hits_window.sort_values("score", ascending=False, na_position="last")
            .head(max_hits)
        )
    if max_hits is not None and max_hits > 0:
        hits_window = hits_window.head(max_hits)

    if not hits_window.empty and {"x0_local", "x1_local", "ans_time_local"}.issubset(hits_window.columns):
        hits_window = hits_window.assign(
            x0=hits_window["x0_local"],
            x1=hits_window["x1_local"],
            ans_time=hits_window["ans_time_local"],
        )

    if window_4h is not None:
        df_4h = window_4h.copy()
        df_4h["time"] = window_4h["open_time"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
    else:
        df_4h = ohlc_4h[
            (ohlc_4h["time"] >= start_4h) & (ohlc_4h["time"] <= end_4h)
        ].copy()

    if window_5m is not None:
        df_5m = window_5m.copy()
        df_5m["time"] = window_5m["open_time"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
    else:
        start_local = start_4h.tz_convert(UI_TIMEZONE).dt.tz_localize(None) if hasattr(start_4h, "dt") else (
            start_4h.tz_convert(UI_TIMEZONE).tz_localize(None) if getattr(start_4h, "tzinfo", None) else start_4h
        )
        end_local = end_4h.tz_convert(UI_TIMEZONE).dt.tz_localize(None) if hasattr(end_4h, "dt") else (
            end_4h.tz_convert(UI_TIMEZONE).tz_localize(None) if getattr(end_4h, "tzinfo", None) else end_4h
        )
        df_5m = ohlc_5m[
            (ohlc_5m["time"] >= start_local) & (ohlc_5m["time"] <= end_local)
        ].copy()

    fig_4h = make_candlestick_figure(df_4h, "BTCUSDT - 4H Candles")
    fig_5m = make_candlestick_figure(df_5m, "BTCUSDT - 5M Candles")

    zones_enabled = "zones" in overlay_values
    markers_enabled = "markers" in overlay_values
    heatmap_enabled = "heatmap" in overlay_values

    def compute_bounds(df_prices):
        if df_prices.empty:
            return None, None
        y0 = df_prices["low"].min()
        y1 = df_prices["high"].max()
        if pd.isna(y0) or pd.isna(y1):
            return None, None
        return y0, y1

    def compute_delta(df_prices, fallback):
        if df_prices.empty:
            return fallback
        delta = df_prices["time"].diff().median()
        if pd.isna(delta) or delta <= pd.Timedelta(0):
            return fallback
        return delta

    def build_density_shapes(df_prices, hits_subset, delta, y_bounds):
        if df_prices.empty or hits_subset.empty:
            return []
        y0, y1 = y_bounds
        if y0 is None or y1 is None:
            return []
        times = df_prices["time"]
        if times.empty:
            return []

        def rgba_from_gradient(density: float) -> str:
            # Gradient stops: low -> mid -> high
            stops = [
                (0.0, (200, 200, 255, 0.05)),
                (0.5, (160, 160, 255, 0.15)),
                (1.0, (120, 120, 240, 0.32)),
            ]
            if density <= stops[0][0]:
                r, g, b, a = stops[0][1]
            elif density >= stops[-1][0]:
                r, g, b, a = stops[-1][1]
            else:
                # find segment
                for i in range(len(stops) - 1):
                    x0, c0 = stops[i]
                    x1, c1 = stops[i + 1]
                    if x0 <= density <= x1:
                        t = (density - x0) / (x1 - x0)
                        r = round(c0[0] + (c1[0] - c0[0]) * t)
                        g = round(c0[1] + (c1[1] - c0[1]) * t)
                        b = round(c0[2] + (c1[2] - c0[2]) * t)
                        a = c0[3] + (c1[3] - c0[3]) * t
                        break
                else:
                    r, g, b, a = stops[-1][1]
            return f"rgba({r}, {g}, {b}, {a})"

        # Build cumulative diff array for O(N) active count across candles
        diff = {}
        eps = pd.Timedelta(microseconds=1)
        for _, row in hits_subset.iterrows():
            start = row.get("x0")
            end = row.get("x1")
            if pd.isna(start) or pd.isna(end):
                continue
            diff[start] = diff.get(start, 0) + 1
            diff[end + eps] = diff.get(end + eps, 0) - 1

        if not diff:
            return []

        events = sorted(diff.items(), key=lambda kv: kv[0])
        evt_idx = 0
        active = 0
        counts = []
        for t in times:
            while evt_idx < len(events) and events[evt_idx][0] <= t:
                active += events[evt_idx][1]
                evt_idx += 1
            counts.append(active)

        if not counts:
            return []

        max_count = max(counts)
        if max_count <= 0:
            return []
        shapes = []
        for idx, t in enumerate(times):
            count = counts[idx]
            if count <= 0:
                continue
            if idx + 1 < len(times):
                x1 = times.iloc[idx + 1]
            else:
                x1 = t + delta
            if pd.isna(x1) or x1 <= t:
                x1 = t + delta
            density = count / max_count
            shapes.append(
                dict(
                    type="rect",
                    xref="x",
                    yref="y",
                    x0=t,
                    x1=x1,
                    y0=y0,
                    y1=y1,
                    fillcolor=rgba_from_gradient(density),
                    line={"color": "rgba(0, 0, 0, 0)", "width": 0},
                    layer="below",
                )
            )
        return shapes

    y_bounds_4h = compute_bounds(df_4h)
    y_bounds_5m = compute_bounds(df_5m)
    delta_4h = compute_delta(df_4h, timedelta(hours=4))
    delta_5m = compute_delta(df_5m, timedelta(minutes=5))

    shapes_zones_4h = []
    if zones_enabled and not df_4h.empty and not hits_window.empty:
        y0_4h, y1_4h = y_bounds_4h
        if y0_4h is not None and y1_4h is not None:
            hits_4h_zone = hits_window[hits_window["timeframe"] == "4h"]
            for _, row in hits_4h_zone.iterrows():
                rgb = _pattern_rgb(row["pattern_type"])
                shapes_zones_4h.append(
                    dict(
                        type="rect",
                        xref="x",
                        yref="y",
                        x0=row["x0"],
                        x1=row["x1"],
                        y0=y0_4h,
                        y1=y1_4h,
                        fillcolor=_rgba_str(rgb, 0.18),
                        line={"color": _rgba_str(rgb, 0.35), "width": 0.4},
                        layer="below",
                    )
                )

    shapes_zones_5m = []
    if zones_enabled and not df_5m.empty and not hits_window.empty:
        y0_5m, y1_5m = y_bounds_5m
        if y0_5m is not None and y1_5m is not None:
            hits_5m_zone = hits_window[hits_window["timeframe"] == "5m"]
            for _, row in hits_5m_zone.iterrows():
                rgb = _pattern_rgb(row["pattern_type"])
                shapes_zones_5m.append(
                    dict(
                        type="rect",
                        xref="x",
                        yref="y",
                        x0=row["x0"],
                        x1=row["x1"],
                        y0=y0_5m,
                        y1=y1_5m,
                        fillcolor=_rgba_str(rgb, 0.18),
                        line={"color": _rgba_str(rgb, 0.35), "width": 0.4},
                        layer="below",
                    )
                )

    shapes_heatmap_4h = []
    shapes_heatmap_5m = []
    if heatmap_enabled:
        shapes_heatmap_4h = build_density_shapes(
            df_4h,
            hits_window[hits_window["timeframe"] == "4h"],
            delta_4h,
            y_bounds_4h,
        )
        shapes_heatmap_5m = build_density_shapes(
            df_5m,
            hits_window[hits_window["timeframe"] == "5m"],
            delta_5m,
            y_bounds_5m,
        )

    if markers_enabled and not hits_window.empty:
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
            df_4h, hits_window[hits_window["timeframe"] == "4h"], "4h hits"
        )
        trace_5m_markers = marker_trace(
            df_5m, hits_window[hits_window["timeframe"] == "5m"], "5m hits"
        )
        if trace_4h_markers:
            fig_4h.add_trace(trace_4h_markers)
        if trace_5m_markers:
            fig_5m.add_trace(trace_5m_markers)

    shapes_final_4h = []
    shapes_final_5m = []
    if zones_enabled:
        shapes_final_4h.extend(shapes_zones_4h)
        shapes_final_5m.extend(shapes_zones_5m)
    if heatmap_enabled:
        shapes_final_4h.extend(shapes_heatmap_4h)
        shapes_final_5m.extend(shapes_heatmap_5m)

    if shapes_final_4h:
        fig_4h.update_layout(shapes=shapes_final_4h)
    if shapes_final_5m:
        fig_5m.update_layout(shapes=shapes_final_5m)

    return fig_4h, fig_5m


@app.callback(
    Output("pattern-table", "data"),
    Output("candle-summary", "children"),
    Output("candle-pattern-table", "data"),
    Output("family-table", "data"),
    Input("store-hits", "data"),
    Input("chart-4h", "relayoutData"),
    Input("chart-4h", "clickData"),
    Input("max-hits-slider", "value"),
    Input("selected-hit-ts", "data"),
)
def update_tables(hits_data, relayout, click_data, max_hits, selected_hit_ts):
    ohlc_4h, _, _, _ = _load_all_data()
    hits_df = pd.DataFrame(hits_data or [])
    if not hits_df.empty:
        hits_df["start_time"] = (
            pd.to_datetime(hits_df["start_time"], errors="coerce", utc=True)
        )
        hits_df["ans_time"] = (
            pd.to_datetime(hits_df["ans_time"], errors="coerce", utc=True)
        )
        hits_df["start_time_utc"] = pd.to_datetime(hits_df.get("start_time_utc"), errors="coerce", utc=True)
        hits_df["ans_time_utc"] = pd.to_datetime(hits_df.get("ans_time_utc"), errors="coerce", utc=True)
        hits_df["x0"] = pd.DataFrame({"a": hits_df["start_time"], "b": hits_df["ans_time"]}).min(axis=1)
        hits_df["x1"] = pd.DataFrame({"a": hits_df["start_time"], "b": hits_df["ans_time"]}).max(axis=1)
        hits_df["x0_local"] = hits_df["x0"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
        hits_df["x1_local"] = hits_df["x1"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
        hits_df["ans_time_local"] = hits_df["ans_time"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
        hits_df = hits_df.dropna(subset=["x0", "x1"])

    start_4h = None
    end_4h = None
    window_4h = None
    center_ts = None
    if selected_hit_ts:
        center_ts = pd.to_datetime(selected_hit_ts, utc=True, errors="coerce")
    if center_ts is None and not hits_df.empty:
        center_ts = hits_df["ans_time_utc"].dropna().max() if "ans_time_utc" in hits_df else hits_df["ans_time"].max()

    if center_ts is not None and not pd.isna(center_ts):
        center_iso = center_ts.isoformat().replace("+00:00", "Z")
        window_4h = _fetch_candles_api("4h", center_iso, WINDOW_BEFORE_DEFAULT, WINDOW_AFTER_DEFAULT)
        if not window_4h.empty:
            start_4h = window_4h["open_time"].min()
            end_4h = window_4h["open_time"].max()

    if start_4h is None or end_4h is None:
        start_4h, end_4h = get_initial_window_4h(days=3)

    if window_4h is not None and not window_4h.empty:
        df_4h = window_4h.copy()
        df_4h["time"] = window_4h["open_time"].dt.tz_convert(UI_TIMEZONE).dt.tz_localize(None)
    else:
        start_local = start_4h.tz_convert(UI_TIMEZONE).dt.tz_localize(None) if hasattr(start_4h, "dt") else (
            start_4h.tz_convert(UI_TIMEZONE).tz_localize(None) if getattr(start_4h, "tzinfo", None) else start_4h
        )
        end_local = end_4h.tz_convert(UI_TIMEZONE).dt.tz_localize(None) if hasattr(end_4h, "dt") else (
            end_4h.tz_convert(UI_TIMEZONE).tz_localize(None) if getattr(end_4h, "tzinfo", None) else end_4h
        )
        df_4h = ohlc_4h[
            (ohlc_4h["time"] >= start_local) & (ohlc_4h["time"] <= end_local)
        ].copy()

    if not hits_df.empty and "x0" in hits_df:
        start_utc = start_4h
        end_utc = end_4h
        if start_4h is not None and getattr(start_4h, "tzinfo", None) is None:
            try:
                start_utc = pd.Timestamp(start_4h).tz_localize(UI_TIMEZONE).tz_convert("UTC")
            except Exception:
                start_utc = start_4h
        if end_4h is not None and getattr(end_4h, "tzinfo", None) is None:
            try:
                end_utc = pd.Timestamp(end_4h).tz_localize(UI_TIMEZONE).tz_convert("UTC")
            except Exception:
                end_utc = end_4h
        hits_window = hits_df[
            (hits_df["x0"] <= end_utc) & (hits_df["x1"] >= start_utc)
        ]
    else:
        hits_window = hits_df
    if max_hits is not None and max_hits > 0:
        hits_window = hits_window.head(max_hits)

    if not hits_window.empty and {"x0_local", "x1_local", "ans_time_local"}.issubset(hits_window.columns):
        hits_window = hits_window.assign(
            x0=hits_window["x0_local"],
            x1=hits_window["x1_local"],
            start_time=hits_window["x0_local"],
            ans_time=hits_window["ans_time_local"],
        )
    pattern_table_data = hits_window.to_dict("records")

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

        if not hits_window.empty and "x0" in hits_window:
            mask = (hits_window["x0"] <= candle_time) & (
                hits_window["x1"] >= candle_time
            )
            candle_hits = hits_window[mask].copy()
        else:
            candle_hits = hits_window

        time_str = candle_time.strftime("%Y-%m-%d %H:%M")
        candle_summary = (
            f"Candle @ {time_str} ({UI_TIMEZONE}) · "
            f"O: {candle_row['open']:.2f} · "
            f"H: {candle_row['high']:.2f} · "
            f"L: {candle_row['low']:.2f} · "
            f"C: {candle_row['close']:.2f} "
            f"| Patterns affecting: {len(candle_hits)}"
        )
        candle_pattern_data = candle_hits.to_dict("records")

    if hits_window.empty:
        family_table_data = []
    else:
        grp = (
            hits_window.groupby(["family_id", "timeframe", "pattern_id"])
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

    return pattern_table_data, candle_summary, candle_pattern_data, family_table_data


# ---------------------------------------------------------------------
if __name__ == "__main__":
    if callable(getattr(app, "run", None)):
        app.run(
            debug=False,
            dev_tools_ui=False,
            dev_tools_hot_reload=False,
            dev_tools_props_check=False,
        )
    else:
        app.run_server(debug=False)
