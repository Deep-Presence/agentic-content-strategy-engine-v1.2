from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import umap

from core.models.gap_analysis import AnalysisResult, EnrichedCitation, GeneratedQuery, SemanticUnit


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


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
        for match in c.best_paragraphs:
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


def plot_embedding_space(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    output_path: Path,
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
    fig.write_html(output_path)


def plot_gap_heatmap(analysis: AnalysisResult, output_path: Path) -> None:
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
    fig.write_html(output_path)


def plot_similarity_distribution(analysis: AnalysisResult, output_path: Path) -> None:
    gaps = analysis.gaps
    if not gaps:
        return
    data = {
        "cluster": [g.cluster_name or "unknown" for g in gaps],
        "gap": [g.gap or 0.0 for g in gaps],
    }
    fig = px.box(data, x="cluster", y="gap", title="Gap Distribution by Cluster")
    fig.write_html(output_path)


def plot_citation_treemap(analysis: AnalysisResult, output_path: Path) -> None:
    domains = analysis.citation_patterns.get("domains", {})
    if not domains:
        return
    fig = px.treemap(
        names=list(domains.keys()),
        parents=[""] * len(domains),
        values=list(domains.values()),
        title="Citation Domain Treemap",
    )
    fig.write_html(output_path)


def plot_cluster_radar(analysis: AnalysisResult, output_path: Path) -> None:
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
    fig.write_html(output_path)


def generate_visualizations(
    queries: List[GeneratedQuery],
    citations: List[EnrichedCitation],
    company_units: List[SemanticUnit],
    analysis: AnalysisResult,
    output_dir: Path,
) -> Dict[str, str]:
    _ensure_dir(output_dir)
    paths = {
        "embedding_space": output_dir / "embedding_space.html",
        "gap_heatmap": output_dir / "gap_heatmap.html",
        "gap_distribution": output_dir / "gap_distribution.html",
        "citation_treemap": output_dir / "citation_treemap.html",
        "cluster_radar": output_dir / "cluster_radar.html",
    }
    plot_embedding_space(queries, citations, company_units, paths["embedding_space"])
    plot_gap_heatmap(analysis, paths["gap_heatmap"])
    plot_similarity_distribution(analysis, paths["gap_distribution"])
    plot_citation_treemap(analysis, paths["citation_treemap"])
    plot_cluster_radar(analysis, paths["cluster_radar"])
    return {k: str(v) for k, v in paths.items()}
