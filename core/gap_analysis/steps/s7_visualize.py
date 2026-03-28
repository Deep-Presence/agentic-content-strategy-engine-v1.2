from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)
import plotly.express as px
import plotly.graph_objects as go
import umap
from plotly.subplots import make_subplots
from sklearn.manifold import TSNE

from core.models.gap_analysis import AnalysisResult, EnrichedCitation, GeneratedQuery, SemanticUnit
from core.storage.backends.base import StorageBackend

TOP_N_CITATIONS = 5   # Max citations per query (ranked by best paragraph similarity)
TOP_K_PARAGRAPHS = 3  # Max paragraphs per citation URL

# Marker config matching prototype: Query=circle, Citation=square, Company=triangle
_TYPE_CONFIG = {
    "Query": {"color": "blue", "symbol": "circle", "size": 12},
    "Citation": {"color": "green", "symbol": "square", "size": 8},
    "Company": {"color": "red", "symbol": "triangle-up", "size": 10},
}


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ---------------------------------------------------------------------------
# Existing helpers (updated with top-K filtering)
# ---------------------------------------------------------------------------


def _collect_embedding_points(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
):
    points = []
    labels = []
    hover = []

    for q in queries:
        if q.embedding:
            points.append(q.embedding)
            labels.append(f"query:{q.cluster_name}")
            hover.append(q.query_text)
    for c in citations:
        for match in c.best_paragraphs[:TOP_K_PARAGRAPHS]:
            if match.embedding:
                points.append(match.embedding)
                labels.append("citation")
                hover.append(str(c.url))
    for unit in company_units:
        if unit.embedding:
            points.append(unit.embedding)
            labels.append("company")
            hover.append(str(unit.url) if unit.url else "company")
    return np.array(points), labels, hover


# ---------------------------------------------------------------------------
# New helpers for typed embedding collection and proximity computation
# ---------------------------------------------------------------------------


def _select_top_citations_for_query(
    citations: List[EnrichedCitation],
    query_embedding: List[float],
) -> List[EnrichedCitation]:
    """Rank citations by their best paragraph's similarity to query, return top-N."""
    scored: List[Tuple[float, EnrichedCitation]] = []
    for citation in citations:
        best_sim = 0.0
        for match in citation.best_paragraphs[:TOP_K_PARAGRAPHS]:
            if match.embedding:
                sim = _cosine_similarity(query_embedding, match.embedding)
                best_sim = max(best_sim, sim)
        scored.append((best_sim, citation))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:TOP_N_CITATIONS]]


def _build_citations_by_query(
    citations: List[EnrichedCitation],
) -> Dict[str, List[EnrichedCitation]]:
    mapping: Dict[str, List[EnrichedCitation]] = defaultdict(list)
    for c in citations:
        if c.query_id:
            mapping[c.query_id].append(c)
    return mapping


def _collect_typed_embeddings(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
) -> Tuple[np.ndarray, List[Dict]]:
    """Collect embeddings with type/cluster metadata for new visualizations.

    Applies top-N citation and top-K paragraph filtering.
    Returns (embeddings_array, metadata_list) where each metadata dict has:
      type: "Query" | "Citation" | "Company"
      cluster_name: str
      hover_text: str
    """
    embeddings: List[List[float]] = []
    meta: List[Dict] = []

    citations_by_query = _build_citations_by_query(citations)

    for q in queries:
        if not q.embedding:
            continue
        embeddings.append(q.embedding)
        meta.append({
            "type": "Query",
            "cluster_name": q.cluster_name,
            "hover_text": q.query_text,
            "query_id": q.query_id,
        })

        # Top-N citations for this query, top-K paragraphs each
        top_cits = _select_top_citations_for_query(
            citations_by_query.get(q.query_id, []),
            q.embedding,
        )
        for cit in top_cits:
            for match in cit.best_paragraphs[:TOP_K_PARAGRAPHS]:
                if match.embedding:
                    embeddings.append(match.embedding)
                    meta.append({
                        "type": "Citation",
                        "cluster_name": cit.cluster_name or q.cluster_name,
                        "hover_text": str(cit.url),
                    })

    for unit in company_units:
        if unit.embedding:
            embeddings.append(unit.embedding)
            meta.append({
                "type": "Company",
                "cluster_name": "Company",
                "hover_text": str(unit.url) if unit.url else (unit.text[:80] if unit.text else "company"),
            })

    if not embeddings:
        return np.array([]), []
    return np.array(embeddings), meta


def _compute_proximity_pairs(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
) -> List[Dict]:
    """Compute (query_id, cluster_name, similarity) for each query-citation pair.

    Applies top-N/top-K filtering.
    """
    citations_by_query = _build_citations_by_query(citations)
    pairs: List[Dict] = []

    for q in queries:
        if not q.embedding:
            continue
        top_cits = _select_top_citations_for_query(
            citations_by_query.get(q.query_id, []),
            q.embedding,
        )
        for cit in top_cits:
            for match in cit.best_paragraphs[:TOP_K_PARAGRAPHS]:
                if match.embedding:
                    sim = _cosine_similarity(q.embedding, match.embedding)
                    pairs.append({
                        "query_id": q.query_id,
                        "cluster_name": q.cluster_name,
                        "similarity": sim,
                    })
    return pairs


# ---------------------------------------------------------------------------
# Existing Plotly visualizations (unchanged)
# ---------------------------------------------------------------------------


def plot_embedding_space(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    storage: StorageBackend,
    key: str,
) -> None:
    points, labels, hover = _collect_embedding_points(queries, citations, company_units)
    if len(points) == 0:
        return
    reducer = umap.UMAP(n_components=2, random_state=42)
    coords = reducer.fit_transform(points)
    fig = px.scatter(
        x=coords[:, 0],
        y=coords[:, 1],
        color=labels,
        hover_name=hover,
        title="Embedding Space Explorer",
    )
    storage.write(key, fig.to_html())


def plot_gap_heatmap(analysis: AnalysisResult, storage: StorageBackend, key: str) -> None:
    if not analysis.gaps:
        return
    clusters = sorted({g.cluster_name or "unknown" for g in analysis.gaps})
    query_labels = [g.query_text[:60] for g in analysis.gaps]
    matrix = []
    for g in analysis.gaps:
        row = []
        for cluster in clusters:
            row.append(g.gap if g.cluster_name == cluster else 0.0)
        matrix.append(row)
    fig = px.imshow(
        matrix,
        x=clusters,
        y=query_labels,
        color_continuous_scale="RdBu",
        title="Gap Heatmap (per query)",
    )
    storage.write(key, fig.to_html())


def plot_gap_distribution(analysis: AnalysisResult, storage: StorageBackend, key: str) -> None:
    gaps = analysis.gaps
    if not gaps:
        return
    data = {
        "cluster": [g.cluster_name or "unknown" for g in gaps],
        "gap": [g.gap or 0.0 for g in gaps],
    }
    fig = px.box(data, x="cluster", y="gap", title="Gap Distribution by Cluster")
    storage.write(key, fig.to_html())


def plot_citation_treemap(analysis: AnalysisResult, storage: StorageBackend, key: str) -> None:
    domains = analysis.citation_patterns.get("domains", {})
    if not domains:
        return
    fig = px.treemap(
        names=list(domains.keys()),
        parents=[""] * len(domains),
        values=list(domains.values()),
        title="Citation Domain Treemap",
    )
    storage.write(key, fig.to_html())


def plot_cluster_radar(analysis: AnalysisResult, storage: StorageBackend, key: str) -> None:
    if not analysis.gaps:
        return
    cluster_data: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: {"company": [], "citation": []}
    )
    for gap in analysis.gaps:
        cluster = gap.cluster_name or "unknown"
        cluster_data[cluster]["company"].append(gap.best_company_similarity or 0.0)
        cluster_data[cluster]["citation"].append(gap.avg_citation_similarity or 0.0)
    clusters = list(cluster_data.keys())
    company_vals = [np.mean(cluster_data[c]["company"]) for c in clusters]
    citation_vals = [np.mean(cluster_data[c]["citation"]) for c in clusters]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(r=company_vals, theta=clusters, fill="toself", name="Company")
    )
    fig.add_trace(
        go.Scatterpolar(
            r=citation_vals, theta=clusters, fill="toself", name="Citations"
        )
    )
    fig.update_layout(title="Company vs Citation Similarity by Cluster")
    storage.write(key, fig.to_html())


# ---------------------------------------------------------------------------
# New Plotly visualizations matching prototype
# ---------------------------------------------------------------------------


def _reduce_embeddings(
    embeddings: np.ndarray,
    method: str,
) -> np.ndarray:
    """Reduce high-dimensional embeddings to 2D using t-SNE or UMAP."""
    if method == "tsne":
        perplexity = min(15, max(2, len(embeddings) - 1))
        reducer = TSNE(n_components=2, random_state=42, perplexity=perplexity)
        return reducer.fit_transform(embeddings)
    elif method == "umap":
        reducer = umap.UMAP(n_components=2, metric="cosine", random_state=42)
        return reducer.fit_transform(embeddings)
    else:
        raise ValueError(f"method must be 'tsne' or 'umap', got '{method}'")


def _plot_typed_embedding_space(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    storage: StorageBackend,
    key: str,
    method: str,
) -> None:
    """Plot embedding space with 3 distinct types: Query, Citation, Company.

    Query=blue circles, Citation=green squares, Company=red triangles.
    """
    embeddings, meta = _collect_typed_embeddings(queries, citations, company_units)
    if len(embeddings) == 0:
        return

    coords = _reduce_embeddings(embeddings, method)
    method_label = "t-SNE" if method == "tsne" else "UMAP"

    fig = go.Figure()
    # Plot in order: Citation, Company, Query (so queries render on top)
    for point_type in ["Citation", "Company", "Query"]:
        cfg = _TYPE_CONFIG[point_type]
        indices = [i for i, m in enumerate(meta) if m["type"] == point_type]
        if not indices:
            continue
        fig.add_trace(go.Scatter(
            x=coords[indices, 0],
            y=coords[indices, 1],
            mode="markers",
            name=point_type,
            text=[meta[i]["hover_text"] for i in indices],
            hoverinfo="text+name",
            marker=dict(
                color=cfg["color"],
                symbol=cfg["symbol"],
                size=cfg["size"],
                opacity=0.7,
            ),
        ))

    fig.update_layout(
        title=f"Query-Citation-Company Embedding Space ({method_label})",
        xaxis_title=f"{method_label} 1",
        yaxis_title=f"{method_label} 2",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    storage.write(key, fig.to_html())


def plot_tsne_embedding_space(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    storage: StorageBackend,
    key: str,
) -> None:
    _plot_typed_embedding_space(queries, citations, company_units, storage, key, "tsne")


def plot_umap_embedding_space(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    storage: StorageBackend,
    key: str,
) -> None:
    _plot_typed_embedding_space(queries, citations, company_units, storage, key, "umap")


def plot_clustered_embedding_space(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    storage: StorageBackend,
    key: str,
    method: str = "tsne",
) -> None:
    """Plot embedding space colored by cluster assignment.

    Points colored by cluster using qualitative palette.
    Company units always red. Different marker symbols per type.
    """
    embeddings, meta = _collect_typed_embeddings(queries, citations, company_units)
    if len(embeddings) == 0:
        return

    coords = _reduce_embeddings(embeddings, method)
    method_label = "t-SNE" if method == "tsne" else "UMAP"

    # Build cluster color map (exclude "Company" from color palette)
    cluster_names = sorted({
        m["cluster_name"] for m in meta if m["type"] != "Company"
    })
    palette = px.colors.qualitative.T10
    cluster_colors = {
        name: palette[i % len(palette)]
        for i, name in enumerate(cluster_names)
    }
    cluster_colors["Company"] = "red"

    fig = go.Figure()

    # One trace per (cluster, type) for clean legend grouping
    marker_symbols = {"Query": "circle", "Citation": "square", "Company": "triangle-up"}
    marker_sizes = {"Query": 12, "Citation": 8, "Company": 10}

    # Collect unique (cluster, type) combos
    seen_legend: set = set()
    for point_type in ["Citation", "Query", "Company"]:
        for cluster in (cluster_names + ["Company"] if point_type == "Company" else cluster_names):
            indices = [
                i for i, m in enumerate(meta)
                if m["type"] == point_type and m["cluster_name"] == cluster
            ]
            if not indices:
                continue

            legend_name = cluster if point_type != "Company" else "Company"
            show_legend = legend_name not in seen_legend
            seen_legend.add(legend_name)

            fig.add_trace(go.Scatter(
                x=coords[indices, 0],
                y=coords[indices, 1],
                mode="markers",
                name=legend_name,
                legendgroup=legend_name,
                showlegend=show_legend,
                text=[meta[i]["hover_text"] for i in indices],
                hoverinfo="text+name",
                marker=dict(
                    color=cluster_colors.get(cluster, "gray"),
                    symbol=marker_symbols[point_type],
                    size=marker_sizes[point_type],
                    opacity=0.7,
                ),
            ))

    fig.update_layout(
        title=f"Embedding Space by Cluster ({method_label})",
        xaxis_title=f"{method_label} 1",
        yaxis_title=f"{method_label} 2",
        legend=dict(title="Cluster"),
    )
    storage.write(key, fig.to_html())


def plot_similarity_histogram(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    storage: StorageBackend,
    key: str,
) -> None:
    """Plot similarity distribution: histogram (left) + per-cluster boxplot (right)."""
    pairs = _compute_proximity_pairs(queries, citations)
    if not pairs:
        return

    sims = [p["similarity"] for p in pairs]
    clusters = sorted({p["cluster_name"] for p in pairs})

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Query-Citation Similarity Distribution", "Similarity by Query Cluster"),
    )

    # Left: histogram of all similarities
    fig.add_trace(
        go.Histogram(x=sims, nbinsx=30, name="Similarities", marker_color="steelblue", opacity=0.7),
        row=1, col=1,
    )
    # Mean line
    mean_sim = float(np.mean(sims))
    fig.add_trace(
        go.Scatter(
            x=[mean_sim, mean_sim],
            y=[0, len(sims) // 3],
            mode="lines",
            name=f"Mean: {mean_sim:.3f}",
            line=dict(color="red", dash="dash", width=2),
        ),
        row=1, col=1,
    )

    # Right: box plot per cluster
    for cluster in clusters:
        cluster_sims = [p["similarity"] for p in pairs if p["cluster_name"] == cluster]
        fig.add_trace(
            go.Box(y=cluster_sims, name=cluster, boxmean=True),
            row=1, col=2,
        )

    fig.update_xaxes(title_text="Cosine Similarity", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_xaxes(title_text="Query Cluster", row=1, col=2)
    fig.update_yaxes(title_text="Cosine Similarity", row=1, col=2)
    fig.update_layout(
        title_text="Query-Citation Similarity Distribution",
        showlegend=True,
        height=500,
        width=1200,
    )
    storage.write(key, fig.to_html())


# ---------------------------------------------------------------------------
# Pre-computed coordinate plotters (accept already-reduced 2D coords)
# ---------------------------------------------------------------------------


def _plot_typed_from_coords(
    coords: np.ndarray,
    meta: List[Dict],
    storage: StorageBackend,
    key: str,
    method: str,
) -> None:
    """Plot typed embedding space from pre-computed 2D coordinates."""
    if len(coords) == 0:
        return
    method_label = "t-SNE" if method == "tsne" else "UMAP"
    fig = go.Figure()
    for point_type in ["Citation", "Company", "Query"]:
        cfg = _TYPE_CONFIG[point_type]
        indices = [i for i, m in enumerate(meta) if m["type"] == point_type]
        if not indices:
            continue
        fig.add_trace(go.Scatter(
            x=coords[indices, 0],
            y=coords[indices, 1],
            mode="markers",
            name=point_type,
            text=[meta[i]["hover_text"] for i in indices],
            hoverinfo="text+name",
            marker=dict(
                color=cfg["color"],
                symbol=cfg["symbol"],
                size=cfg["size"],
                opacity=0.7,
            ),
        ))
    fig.update_layout(
        title=f"Query-Citation-Company Embedding Space ({method_label})",
        xaxis_title=f"{method_label} 1",
        yaxis_title=f"{method_label} 2",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    storage.write(key, fig.to_html())


def _plot_clustered_from_coords(
    coords: np.ndarray,
    meta: List[Dict],
    storage: StorageBackend,
    key: str,
    method: str,
) -> None:
    """Plot cluster-colored embedding space from pre-computed 2D coordinates."""
    if len(coords) == 0:
        return
    method_label = "t-SNE" if method == "tsne" else "UMAP"

    cluster_names = sorted({
        m["cluster_name"] for m in meta if m["type"] != "Company"
    })
    palette = px.colors.qualitative.T10
    cluster_colors = {
        name: palette[i % len(palette)]
        for i, name in enumerate(cluster_names)
    }
    cluster_colors["Company"] = "red"

    fig = go.Figure()
    marker_symbols = {"Query": "circle", "Citation": "square", "Company": "triangle-up"}
    marker_sizes = {"Query": 12, "Citation": 8, "Company": 10}
    seen_legend: set = set()

    for point_type in ["Citation", "Query", "Company"]:
        for cluster in (cluster_names + ["Company"] if point_type == "Company" else cluster_names):
            indices = [
                i for i, m in enumerate(meta)
                if m["type"] == point_type and m["cluster_name"] == cluster
            ]
            if not indices:
                continue
            legend_name = cluster if point_type != "Company" else "Company"
            show_legend = legend_name not in seen_legend
            seen_legend.add(legend_name)
            fig.add_trace(go.Scatter(
                x=coords[indices, 0],
                y=coords[indices, 1],
                mode="markers",
                name=legend_name,
                legendgroup=legend_name,
                showlegend=show_legend,
                text=[meta[i]["hover_text"] for i in indices],
                hoverinfo="text+name",
                marker=dict(
                    color=cluster_colors.get(cluster, "gray"),
                    symbol=marker_symbols[point_type],
                    size=marker_sizes[point_type],
                    opacity=0.7,
                ),
            ))

    fig.update_layout(
        title=f"Embedding Space by Cluster ({method_label})",
        xaxis_title=f"{method_label} 1",
        yaxis_title=f"{method_label} 2",
        legend=dict(title="Cluster"),
    )
    storage.write(key, fig.to_html())


# ---------------------------------------------------------------------------
# JSON projection export for frontend scatter plots
# ---------------------------------------------------------------------------


def _save_embedding_projections(
    coords: np.ndarray,
    meta: List[Dict],
    storage: StorageBackend,
    prefix: str,
    method: str,
) -> None:
    """Save 2D projection coordinates as JSON for frontend scatter plots.

    Output format matches frontend EmbeddingPoint interface:
    {method, point_count, points: [{x, y, type, id, label, cluster, cluster_id, query_id}]}
    """
    if len(coords) == 0:
        return
    q_idx = c_idx = co_idx = 0
    points: List[Dict] = []
    for i, m in enumerate(meta):
        x_val = float(coords[i, 0])
        y_val = float(coords[i, 1])
        if np.isnan(x_val) or np.isnan(y_val) or np.isinf(x_val) or np.isinf(y_val):
            continue
        t = m["type"].lower()
        if t == "query":
            pid = f"q-{q_idx}"
            q_idx += 1
        elif t == "citation":
            pid = f"c-{c_idx}"
            c_idx += 1
        else:
            pid = f"co-{co_idx}"
            co_idx += 1
        points.append({
            "x": round(x_val, 4),
            "y": round(y_val, 4),
            "type": t,
            "id": pid,
            "label": m["hover_text"],
            "cluster": m["cluster_name"],
            "cluster_id": m.get("cluster_id", m["cluster_name"]),
            "query_id": m.get("query_id"),
        })
    payload = {"method": method, "point_count": len(points), "points": points}
    storage.write(f"{prefix}/embedding_projections_{method}.json", json.dumps(payload))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_visualizations(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    analysis: AnalysisResult,
    storage: StorageBackend,
    prefix: str,
) -> Dict[str, str]:
    s7_t0 = time.monotonic()
    storage.mkdir(prefix)
    keys: Dict[str, str] = {
        # Existing Plotly (HTML)
        "embedding_space": f"{prefix}/embedding_space.html",
        "gap_heatmap": f"{prefix}/gap_heatmap.html",
        "gap_distribution": f"{prefix}/gap_distribution.html",
        "citation_treemap": f"{prefix}/citation_treemap.html",
        "cluster_radar": f"{prefix}/cluster_radar.html",
        # Typed + clustered Plotly (HTML)
        "tsne_space": f"{prefix}/tsne_embedding_space.html",
        "umap_space": f"{prefix}/umap_embedding_space.html",
        "tsne_clustered": f"{prefix}/tsne_clustered.html",
        "umap_clustered": f"{prefix}/umap_clustered.html",
        "similarity_distribution": f"{prefix}/similarity_distribution.html",
    }

    succeeded = 0
    failed = 0
    failed_keys: list[str] = []

    def _safe_plot(path_key: str, fn, *args, **kwargs):
        nonlocal succeeded, failed
        try:
            t0 = time.monotonic()
            fn(*args, **kwargs)
            succeeded += 1
            logger.debug("S7 %s: %.1fs", path_key, time.monotonic() - t0)
        except Exception as exc:
            failed += 1
            failed_keys.append(path_key)
            logger.warning("S7 %s FAILED: %s", path_key, exc)

    # Existing plots (use their own internal UMAP/collection)
    _safe_plot("embedding_space", plot_embedding_space, queries, citations, company_units, storage, keys["embedding_space"])
    _safe_plot("gap_heatmap", plot_gap_heatmap, analysis, storage, keys["gap_heatmap"])
    _safe_plot("gap_distribution", plot_gap_distribution, analysis, storage, keys["gap_distribution"])
    _safe_plot("citation_treemap", plot_citation_treemap, analysis, storage, keys["citation_treemap"])
    _safe_plot("cluster_radar", plot_cluster_radar, analysis, storage, keys["cluster_radar"])

    # Compute typed embeddings ONCE, reduce ONCE per method, reuse everywhere
    embeddings_arr, meta_list = _collect_typed_embeddings(queries, citations, company_units)
    if len(embeddings_arr) >= 3:
        umap_coords = _reduce_embeddings(embeddings_arr, "umap")
        tsne_coords = _reduce_embeddings(embeddings_arr, "tsne")

        # HTML plots from pre-computed coords
        _safe_plot("umap_typed", _plot_typed_from_coords, umap_coords, meta_list, storage, keys["umap_space"], "umap")
        _safe_plot("tsne_typed", _plot_typed_from_coords, tsne_coords, meta_list, storage, keys["tsne_space"], "tsne")
        _safe_plot("umap_clustered", _plot_clustered_from_coords, umap_coords, meta_list, storage, keys["umap_clustered"], "umap")
        _safe_plot("tsne_clustered", _plot_clustered_from_coords, tsne_coords, meta_list, storage, keys["tsne_clustered"], "tsne")

        # JSON projections for frontend scatter (same coords — no drift)
        _safe_plot("umap_projections", _save_embedding_projections, umap_coords, meta_list, storage, prefix, "umap")
        _safe_plot("tsne_projections", _save_embedding_projections, tsne_coords, meta_list, storage, prefix, "tsne")
        keys["umap_projections_json"] = f"{prefix}/embedding_projections_umap.json"
        keys["tsne_projections_json"] = f"{prefix}/embedding_projections_tsne.json"

    # Similarity histogram (uses its own proximity pair computation)
    _safe_plot("similarity_histogram", plot_similarity_histogram, queries, citations, storage, keys["similarity_distribution"])

    total_plots = succeeded + failed
    logger.info("S7 complete: %d/%d visualizations succeeded, %d failed, %.1fs", succeeded, total_plots, failed, time.monotonic() - s7_t0)

    # Remove keys for failed plots so downstream doesn't reference missing files
    for fk in failed_keys:
        keys.pop(fk, None)

    return keys
