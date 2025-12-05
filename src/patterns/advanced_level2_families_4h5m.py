from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
KB_PATH = ROOT / "project" / "KNOWLEDGE_BASE" / "patterns" / "pattern_families_level1.yaml"

PATTERN_FILES = {
    "4h": DATA_DIR / "patterns_4h_raw_level1_with_embeddings.parquet",
    "5m": DATA_DIR / "patterns_5m_raw_level1_with_embeddings.parquet",
}
FAMILY_OUT = {
    "4h": DATA_DIR / "pattern_families_4h.parquet",
    "5m": DATA_DIR / "pattern_families_5m.parquet",
}
GRAPH_OUT = {
    "4h": DATA_DIR / "pattern_graph_4h_edges.parquet",
    "5m": DATA_DIR / "pattern_graph_5m_edges.parquet",
}


# -----------------------------------------------------------------------------
# Similarity helpers
# -----------------------------------------------------------------------------
def _to_matrix(embeddings: Iterable) -> np.ndarray:
    rows = [np.array(e, dtype=float).flatten() for e in embeddings]
    if not rows:
        return np.empty((0, 0))
    max_len = max(r.shape[0] for r in rows)
    padded = []
    for r in rows:
        if r.shape[0] < max_len:
            pad = np.zeros(max_len - r.shape[0], dtype=float)
            r = np.concatenate([r, pad])
        padded.append(r)
    return np.vstack(padded)


def _cosine_knn_edges(emb: np.ndarray, keys: List[str], k: int = 5, tau: float = 0.75) -> pd.DataFrame:
    """
    Build k-NN edges using cosine similarity with batching to avoid huge matrices.
    """
    if emb.size == 0:
        return pd.DataFrame(columns=["from_pattern", "to_pattern", "similarity", "kind"])
    norm = np.linalg.norm(emb, axis=1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    x = emb / norm
    n = x.shape[0]
    edges: List[Tuple[str, str, float]] = []

    batch = 256
    for start in range(0, n, batch):
        end = min(n, start + batch)
        xb = x[start:end]
        sims = xb @ x.T  # shape (b, n)
        for i in range(end - start):
            sim_row = sims[i]
            sim_row[start + i] = -1.0  # exclude self
            top_idx = np.argpartition(sim_row, -k)[-k:]
            for j in top_idx:
                score = sim_row[j]
                if score >= tau:
                    edges.append((keys[start + i], keys[j], float(score)))
    return pd.DataFrame(edges, columns=["from_pattern", "to_pattern", "similarity"]).assign(kind="embedding")


# -----------------------------------------------------------------------------
# Clustering (lightweight k-means)
# -----------------------------------------------------------------------------
def _kmeans(x: np.ndarray, k: int, max_iter: int = 25, seed: int = 42) -> np.ndarray:
    """Simple k-means returning cluster labels."""
    n, d = x.shape
    rng = np.random.default_rng(seed)
    if k <= 1 or n <= k:
        return np.zeros(n, dtype=int)
    idx = rng.choice(n, size=k, replace=False)
    centers = x[idx]
    labels = np.zeros(n, dtype=int)
    for _ in range(max_iter):
        dist = np.linalg.norm(x[:, None, :] - centers[None, :, :], axis=2)
        new_labels = dist.argmin(axis=1)
        if np.all(new_labels == labels):
            break
        labels = new_labels
        for c in range(k):
            mask = labels == c
            if mask.any():
                centers[c] = x[mask].mean(axis=0)
    return labels


# -----------------------------------------------------------------------------
# Family builder
# -----------------------------------------------------------------------------
def _family_strength(agg_lift: float, agg_support: float, support_median: float) -> str:
    """
    strength rules:
      - strong: agg_lift >= 1.2 and agg_support >= median
      - medium: 1.05 <= agg_lift < 1.2
      - weak: otherwise
    """
    if agg_lift >= 1.2 and agg_support >= support_median:
        return "strong"
    if agg_lift >= 1.05:
        return "medium"
    return "weak"


def _build_families_for_timeframe(df: pd.DataFrame, timeframe: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["embedding"] = df["embedding"].apply(lambda x: x if isinstance(x, list) else list(x))
    df = df[df["embedding"].apply(lambda x: len(x) > 0)]
    support_median = df["support"].median()
    families: List[Dict[str, Any]] = []
    edge_rows: List[pd.DataFrame] = []
    created = datetime.utcnow().isoformat()

    # Build per-group families to keep semantics coherent.
    for ptype, sub in df.groupby("pattern_type"):
        embeds = _to_matrix(sub["embedding"])
        keys = [f"{ptype}|w{sub.iloc[i]['window_size']}|{sub.iloc[i]['definition']}" for i in range(len(sub))]

        # Graph edges
        edges = _cosine_knn_edges(embeds, keys, k=5, tau=0.8)
        edge_rows.append(edges)

        n = len(sub)
        if n == 0:
            continue
        if n <= 3:
            labels = np.zeros(n, dtype=int)
        else:
            k = min(10, max(1, int(math.sqrt(n / 2))))
            labels = _kmeans(embeds, k=k)

        for cid in np.unique(labels):
            mask = labels == cid
            cluster = sub.loc[mask]
            emb_centroid = embeds[mask].mean(axis=0).astype(float).tolist()

            agg_support = float(cluster["support"].sum())
            lift_weights = cluster["support"].replace(0, 1)
            agg_lift = float((cluster["lift"] * lift_weights).sum() / lift_weights.sum())
            stab_series = cluster["stability"].replace({np.nan: None})
            if stab_series.notnull().any():
                agg_stability = float(
                    (stab_series.fillna(0.0) * lift_weights).sum() / lift_weights.sum()
                )
            else:
                agg_stability = float("nan")

            strength = _family_strength(agg_lift, agg_support, support_median)
            member_keys = [
                f"{row.pattern_type}|w{row.window_size}|{row.definition}" for row in cluster.itertuples()
            ]
            dom_ws = cluster["window_size"].value_counts().index.tolist()[:2]
            dom_ptype = cluster["pattern_type"].value_counts().index.tolist()

            fid = f"fam_{timeframe}_{ptype}_{cid:03d}"
            note = (
                f"{ptype} family with {len(cluster)} members; lift~{agg_lift:.2f}; "
                f"support={agg_support:.0f}; strength={strength}"
            )
            families.append(
                {
                    "family_id": fid,
                    "timeframe": timeframe,
                    "member_keys": member_keys,
                    "dominant_window_sizes": dom_ws,
                    "dominant_pattern_types": dom_ptype,
                    "agg_support": agg_support,
                    "agg_lift": agg_lift,
                    "agg_stability": agg_stability,
                    "strength_level": strength,
                    "embedding_centroid": emb_centroid,
                    "notes": note,
                    "created_at": created,
                }
            )

    fam_df = pd.DataFrame(families)
    graph_df = pd.concat(edge_rows, ignore_index=True) if edge_rows else pd.DataFrame()
    return fam_df, graph_df


# -----------------------------------------------------------------------------
# YAML updater
# -----------------------------------------------------------------------------
def _load_existing_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _bump_version(version: str) -> str:
    if not version or "." not in version:
        return "v1.0.0"
    try:
        prefix = version.strip().lstrip("v")
        parts = prefix.split(".")
        major, minor, patch = parts if len(parts) == 3 else (parts + ["0"] * (3 - len(parts)))
        patch_num = int(patch) + 1
        return f"v{major}.{minor}.{patch_num}"
    except Exception:
        return "v1.0.0"


def _update_kb_yaml(fam_all: List[pd.DataFrame]) -> None:
    data = _load_existing_yaml(KB_PATH)
    meta = data.get("meta", {})
    prev_version = meta.get("version", "v1.0.0")
    new_version = _bump_version(prev_version)
    updated_at = datetime.utcnow().isoformat()

    families_yaml: List[Dict[str, Any]] = data.get("families", [])
    for fam_df in fam_all:
        for row in fam_df.itertuples():
            families_yaml.append(
                {
                    "id": row.family_id,
                    "timeframe": row.timeframe,
                    "strength_level": row.strength_level,
                    "window_sizes": list(row.dominant_window_sizes),
                    "pattern_types": list(row.dominant_pattern_types),
                    "agg_support": float(row.agg_support),
                    "agg_lift": float(row.agg_lift),
                    "agg_stability": float(row.agg_stability)
                    if not math.isnan(row.agg_stability)
                    else None,
                    "member_count": len(row.member_keys),
                    "notes": row.notes,
                }
            )

    kb_content = {
        "meta": {
            "version": new_version,
            "updated_at": updated_at,
            "source": "Codex Advanced Level-2 Families",
            "description": "Level-1 pattern families for 4h and 5m (embedding + stats based).",
        },
        "families": families_yaml,
    }
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with KB_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(kb_content, f, sort_keys=False, allow_unicode=True)


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
def build_advanced_pattern_families_4h5m() -> None:
    fam_results: List[pd.DataFrame] = []
    for tf in ("4h", "5m"):
        path = PATTERN_FILES[tf]
        if not path.exists():
            raise FileNotFoundError(f"Missing pattern file: {path}")
        df = pd.read_parquet(path)
        fam_df, graph_df = _build_families_for_timeframe(df, timeframe=tf)
        fam_results.append(fam_df)

        fam_out = FAMILY_OUT[tf]
        graph_out = GRAPH_OUT[tf]
        fam_df.to_parquet(fam_out, index=False)
        if not graph_df.empty:
            graph_df.to_parquet(graph_out, index=False)

        strong = (fam_df["strength_level"] == "strong").sum()
        medium = (fam_df["strength_level"] == "medium").sum()
        weak = (fam_df["strength_level"] == "weak").sum()
        print(
            f"[families] {tf}: patterns={len(df)}, families={len(fam_df)}, "
            f"strong={strong}, medium={medium}, weak={weak}"
        )
        print(fam_df.head(3))

    _update_kb_yaml(fam_results)

    for tf in ("4h", "5m"):
        fpath = FAMILY_OUT[tf]
        if fpath.exists():
            df = pd.read_parquet(fpath)
            print(f"[summary] {fpath.name}: shape={df.shape}")
            print(df.head(2))
    print(f"[yaml] updated: {KB_PATH}")
    print(
        "Advanced Phase 3 completed:\n"
        "- Level-1 pattern families built for 4h and 5m (embedding + stats)\n"
        "- KB family summary updated."
    )


if __name__ == "__main__":
    build_advanced_pattern_families_4h5m()
