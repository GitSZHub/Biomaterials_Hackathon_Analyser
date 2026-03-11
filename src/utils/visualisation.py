"""
Visualisation Utilities
========================
Shared Plotly and Matplotlib helper functions used across modules.
Provides consistent styling, colour palettes, and common chart types.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

logger = logging.getLogger(__name__)


# ── Colour palettes ──────────────────────────────────────────

# Biomaterials-themed colour palette (12 colours)
PALETTE = [
    "#2196F3",  # blue
    "#FF5722",  # deep orange
    "#4CAF50",  # green
    "#9C27B0",  # purple
    "#FF9800",  # orange
    "#00BCD4",  # cyan
    "#E91E63",  # pink
    "#795548",  # brown
    "#607D8B",  # blue-grey
    "#CDDC39",  # lime
    "#3F51B5",  # indigo
    "#009688",  # teal
]

# Semantic colours
COLORS = {
    "positive": "#4CAF50",
    "negative": "#F44336",
    "neutral": "#9E9E9E",
    "warning": "#FF9800",
    "info": "#2196F3",
    "highlight": "#FFD600",
    "upregulated": "#D32F2F",
    "downregulated": "#1565C0",
    "significant": "#FF5722",
    "not_significant": "#BDBDBD",
}


# ── Matplotlib helpers ───────────────────────────────────────

def style_axis(ax, title: str = "", xlabel: str = "", ylabel: str = "",
               grid: bool = True, legend: bool = False):
    """Apply consistent styling to a matplotlib axis."""
    if title:
        ax.set_title(title, fontsize=11, fontweight="bold")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9)
    if grid:
        ax.grid(True, alpha=0.3, linestyle="--")
    if legend:
        ax.legend(fontsize=8, framealpha=0.8)
    ax.tick_params(labelsize=8)


def add_threshold_line(ax, value: float, direction: str = "horizontal",
                       color: str = "#666", linestyle: str = "--",
                       label: str = ""):
    """Add a threshold line to a plot."""
    if direction == "horizontal":
        ax.axhline(y=value, color=color, linestyle=linestyle,
                   linewidth=1, alpha=0.7, label=label)
    else:
        ax.axvline(x=value, color=color, linestyle=linestyle,
                   linewidth=1, alpha=0.7, label=label)


def make_radar_chart(ax, categories: List[str], values: List[float],
                     label: str = "", color: str = "#2196F3",
                     fill_alpha: float = 0.25):
    """Draw a radar/spider chart on a polar axis.

    Parameters
    ----------
    ax : matplotlib polar axis
        Created via fig.add_subplot(111, polar=True).
    categories : list of str
        Category labels.
    values : list of float
        Values (0-1 normalised recommended).
    label : str
        Legend label.
    color : str
        Line/fill colour.
    fill_alpha : float
        Fill transparency.
    """
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    values_plot = values + [values[0]]  # close the polygon
    angles += angles[:1]

    ax.plot(angles, values_plot, "o-", color=color, linewidth=2, label=label)
    ax.fill(angles, values_plot, alpha=fill_alpha, color=color)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=8)
    ax.set_ylim(0, max(values) * 1.2 if values else 1)
    if label:
        ax.legend(loc="upper right", fontsize=8)


def make_bar_chart(ax, labels: List[str], values: List[float],
                   colors: Optional[List[str]] = None,
                   horizontal: bool = False, title: str = ""):
    """Draw a bar chart with consistent styling."""
    if colors is None:
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]

    if horizontal:
        ax.barh(labels, values, color=colors)
    else:
        ax.bar(labels, values, color=colors)

    style_axis(ax, title=title)
    ax.tick_params(axis="x" if not horizontal else "y", rotation=45 if len(labels) > 5 else 0)


# ── Plotly helpers (for interactive HTML export) ─────────────

def make_plotly_volcano(
    genes: List[str],
    log2fc: List[float],
    neg_log10p: List[float],
    fc_threshold: float = 1.0,
    p_threshold: float = 1.3,   # -log10(0.05)
    title: str = "Volcano Plot",
) -> Optional[str]:
    """Create an interactive Plotly volcano plot HTML string.

    Returns None if plotly is not installed.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    colors = []
    for fc, p in zip(log2fc, neg_log10p):
        if abs(fc) >= fc_threshold and p >= p_threshold:
            colors.append(COLORS["upregulated"] if fc > 0 else COLORS["downregulated"])
        else:
            colors.append(COLORS["not_significant"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=log2fc,
        y=neg_log10p,
        mode="markers",
        text=genes,
        marker=dict(color=colors, size=5, opacity=0.7),
        hovertemplate="<b>%{text}</b><br>log2FC: %{x:.2f}<br>-log10(p): %{y:.2f}",
    ))

    fig.add_hline(y=p_threshold, line_dash="dash", line_color="#666", opacity=0.5)
    fig.add_vline(x=fc_threshold, line_dash="dash", line_color="#666", opacity=0.5)
    fig.add_vline(x=-fc_threshold, line_dash="dash", line_color="#666", opacity=0.5)

    fig.update_layout(
        title=title,
        xaxis_title="log2 Fold Change",
        yaxis_title="-log10(p-value)",
        template="plotly_white",
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def make_plotly_heatmap(
    data: np.ndarray,
    row_labels: List[str],
    col_labels: List[str],
    title: str = "Heatmap",
    colorscale: str = "RdBu_r",
) -> Optional[str]:
    """Create an interactive Plotly heatmap HTML string."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    fig = go.Figure(data=go.Heatmap(
        z=data,
        x=col_labels,
        y=row_labels,
        colorscale=colorscale,
    ))
    fig.update_layout(title=title, template="plotly_white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def make_plotly_bar(
    labels: List[str],
    values: List[float],
    title: str = "Bar Chart",
    color: str = "#2196F3",
    horizontal: bool = True,
) -> Optional[str]:
    """Create an interactive Plotly bar chart HTML string."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    if horizontal:
        fig = go.Figure(go.Bar(y=labels, x=values, orientation="h",
                               marker_color=color))
    else:
        fig = go.Figure(go.Bar(x=labels, y=values, marker_color=color))

    fig.update_layout(title=title, template="plotly_white")
    return fig.to_html(full_html=False, include_plotlyjs="cdn")
