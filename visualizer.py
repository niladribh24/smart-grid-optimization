"""
Grid Visualizer
================
Multi-panel matplotlib dashboard for the Predictive Energy Routing system.
Produces publication-quality visualizations of the grid, routes, ML analysis,
and self-healing demonstrations.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import networkx as nx

from config import (
    VIZ_CONFIG, NODE_STYLES, NodeType, CONGESTION_COLORS,
    CONGESTION_THRESHOLDS, OUTPUT_DIR
)


# ─────────────────────────────────────────────
# Custom dark theme setup
# ─────────────────────────────────────────────
def setup_dark_theme():
    """Configure matplotlib for a dark, modern aesthetic."""
    plt.rcParams.update({
        "figure.facecolor": VIZ_CONFIG["background_color"],
        "axes.facecolor": VIZ_CONFIG["background_color"],
        "axes.edgecolor": VIZ_CONFIG["grid_color"],
        "axes.labelcolor": VIZ_CONFIG["text_color"],
        "text.color": VIZ_CONFIG["text_color"],
        "xtick.color": VIZ_CONFIG["text_color"],
        "ytick.color": VIZ_CONFIG["text_color"],
        "font.family": VIZ_CONFIG["font_family"],
        "font.size": 10,
        "axes.grid": False,
    })


def get_congestion_color(score: float) -> str:
    """Map a congestion score to a color."""
    if score >= CONGESTION_THRESHOLDS["critical"]:
        return CONGESTION_COLORS["critical"]
    elif score >= CONGESTION_THRESHOLDS["high"]:
        return CONGESTION_COLORS["high"]
    elif score >= CONGESTION_THRESHOLDS["medium"]:
        return CONGESTION_COLORS["medium"]
    else:
        return CONGESTION_COLORS["low"]


def get_edge_colors(graph: nx.Graph) -> list:
    """Get colors for all edges based on congestion scores."""
    colors = []
    for u, v, data in graph.edges(data=True):
        if data.get("is_failed", False):
            colors.append(VIZ_CONFIG["failed_edge_color"])
        else:
            colors.append(get_congestion_color(data.get("congestion_score", 0)))
    return colors


def get_edge_widths(graph: nx.Graph) -> list:
    """Get widths for edges (thicker = more congested)."""
    widths = []
    for u, v, data in graph.edges(data=True):
        score = data.get("congestion_score", 0)
        widths.append(1.0 + score * 3.5)
    return widths


# ─────────────────────────────────────────────
# Panel Drawing Functions
# ─────────────────────────────────────────────

def draw_grid_topology(ax, grid, title="Power Grid Topology"):
    """
    Draw the grid with color-coded nodes and congestion-colored edges.
    """
    G = grid.graph
    pos = grid.positions

    # Draw edges with congestion coloring
    edge_colors = get_edge_colors(G)
    edge_widths = get_edge_widths(G)
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color=edge_colors,
        width=edge_widths,
        alpha=0.8,
        style=["--" if G[u][v].get("is_failed", False) else "-" for u, v in G.edges()]
    )

    # Draw nodes by type
    for node_type, style in NODE_STYLES.items():
        nodes = [n for n in G.nodes() if G.nodes[n].get("node_type") == node_type]
        if nodes:
            nx.draw_networkx_nodes(
                G, pos, nodelist=nodes, ax=ax,
                node_color=style["color"],
                node_size=style["size"],
                node_shape=style["marker"],
                alpha=0.95,
                edgecolors="white",
                linewidths=1.5,
            )

    # Draw labels
    nx.draw_networkx_labels(
        G, pos, ax=ax,
        font_size=8,
        font_color="white",
        font_weight="bold",
    )

    # Legend
    legend_patches = [
        mpatches.Patch(color=style["color"], label=style["label"])
        for style in NODE_STYLES.values()
    ]
    legend_patches.extend([
        mpatches.Patch(color=CONGESTION_COLORS["low"], label="Low Congestion"),
        mpatches.Patch(color=CONGESTION_COLORS["medium"], label="Medium"),
        mpatches.Patch(color=CONGESTION_COLORS["high"], label="High"),
        mpatches.Patch(color=CONGESTION_COLORS["critical"], label="Critical"),
    ])
    ax.legend(handles=legend_patches, loc="lower left", fontsize=7,
              facecolor="#1a1e3a", edgecolor="#333", labelcolor="white",
              framealpha=0.9)

    ax.set_title(title, fontsize=14, fontweight="bold",
                 color=VIZ_CONFIG["accent_color"], pad=10)
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(0.5, 10.0)
    ax.set_aspect("equal")
    ax.axis("off")


def draw_route(ax, grid, route, title="Optimal Energy Route",
               route_color=None, show_labels=True):
    """
    Draw the grid with a highlighted route path.
    """
    if route is None:
        ax.text(0.5, 0.5, "No route found", ha="center", va="center",
                fontsize=14, color="red", transform=ax.transAxes)
        ax.set_title(title, fontsize=14, fontweight="bold",
                     color=VIZ_CONFIG["accent_color"])
        ax.axis("off")
        return

    G = grid.graph
    pos = grid.positions
    path = route["path"]
    color = route_color or VIZ_CONFIG["path_color"]

    # Draw all edges dimmed
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color="#1a2a4a",
        width=1.0,
        alpha=0.4,
    )

    # Draw failed edges
    failed_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("is_failed", False)]
    if failed_edges:
        nx.draw_networkx_edges(
            G, pos, edgelist=failed_edges, ax=ax,
            edge_color=VIZ_CONFIG["failed_edge_color"],
            width=2.5,
            style="--",
            alpha=0.8,
        )

    # Draw route path (highlighted)
    path_edges = [(path[i], path[i + 1]) for i in range(len(path) - 1)]
    nx.draw_networkx_edges(
        G, pos, edgelist=path_edges, ax=ax,
        edge_color=color,
        width=4.0,
        alpha=0.95,
        arrows=True,
        arrowsize=15,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.05",
    )

    # Draw nodes
    for node_type, style in NODE_STYLES.items():
        nodes = [n for n in G.nodes() if G.nodes[n].get("node_type") == node_type]
        if nodes:
            # Highlight nodes in path
            path_nodes = [n for n in nodes if n in path]
            other_nodes = [n for n in nodes if n not in path]

            if other_nodes:
                nx.draw_networkx_nodes(
                    G, pos, nodelist=other_nodes, ax=ax,
                    node_color=style["color"], node_size=style["size"] * 0.7,
                    node_shape=style["marker"], alpha=0.4,
                    edgecolors="#555", linewidths=1,
                )
            if path_nodes:
                nx.draw_networkx_nodes(
                    G, pos, nodelist=path_nodes, ax=ax,
                    node_color=style["color"], node_size=style["size"] * 1.2,
                    node_shape=style["marker"], alpha=1.0,
                    edgecolors="white", linewidths=2.5,
                )

    if show_labels:
        nx.draw_networkx_labels(
            G, pos, ax=ax, font_size=8,
            font_color="white", font_weight="bold",
        )

    # Route info text
    info = (f"Path: {' → '.join(path)}\n"
            f"Hops: {route['num_hops']}  |  "
            f"Cost: {route['total_cost']:.3f}  |  "
            f"Avg Cong: {route['avg_congestion']:.3f}")
    ax.text(0.02, 0.02, info, transform=ax.transAxes,
            fontsize=7, color="#aaa", va="bottom",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#111", alpha=0.8))

    ax.set_title(title, fontsize=14, fontweight="bold",
                 color=VIZ_CONFIG["accent_color"], pad=10)
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(0.5, 10.0)
    ax.set_aspect("equal")
    ax.axis("off")


def draw_feature_importance(ax, feature_importances: dict):
    """Draw a horizontal bar chart of ML feature importances."""
    features = list(reversed(list(feature_importances.keys())))
    importances = list(reversed(list(feature_importances.values())))

    # Gradient colors
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(features)))

    bars = ax.barh(features, importances, color=colors, edgecolor="white",
                   linewidth=0.5, height=0.6)

    # Add value labels
    for bar, val in zip(bars, importances):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}", va="center", fontsize=8, color="#aaa")

    ax.set_xlabel("Importance Score", fontsize=10, color="#aaa")
    ax.set_title("🔑 ML Feature Importances", fontsize=14, fontweight="bold",
                 color=VIZ_CONFIG["accent_color"], pad=10)
    ax.tick_params(axis="y", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#333")
    ax.spines["left"].set_color("#333")


def draw_congestion_heatmap(ax, grid):
    """Draw edge congestion as a bar chart heatmap."""
    edges = []
    scores = []
    for u, v, data in grid.graph.edges(data=True):
        edges.append(f"{u}↔{v}")
        scores.append(data.get("congestion_score", 0))

    # Sort by congestion
    sorted_pairs = sorted(zip(scores, edges), reverse=True)
    scores, edges = zip(*sorted_pairs) if sorted_pairs else ([], [])

    colors = [get_congestion_color(s) for s in scores]

    bars = ax.barh(list(reversed(edges)), list(reversed(scores)),
                   color=list(reversed(colors)), edgecolor="none", height=0.7)

    # Threshold lines
    for thresh_name, thresh_val in CONGESTION_THRESHOLDS.items():
        ax.axvline(x=thresh_val, color="#555", linestyle=":", linewidth=0.8, alpha=0.6)
        ax.text(thresh_val, len(edges) - 0.5, f" {thresh_name}",
                fontsize=6, color="#777", va="bottom")

    ax.set_xlabel("Congestion Score", fontsize=10, color="#aaa")
    ax.set_title("📊 Edge Congestion Map", fontsize=14, fontweight="bold",
                 color=VIZ_CONFIG["accent_color"], pad=10)
    ax.set_xlim(0, 1.05)
    ax.tick_params(axis="y", labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#333")
    ax.spines["left"].set_color("#333")


def draw_route_comparison(ax, grid, ml_route, naive_route):
    """Draw both routes overlaid for comparison."""
    G = grid.graph
    pos = grid.positions

    # Draw base edges dimmed
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#1a2a4a", width=0.8, alpha=0.3)

    # Draw naive route (red/orange)
    if naive_route:
        naive_path = naive_route["path"]
        naive_edges = [(naive_path[i], naive_path[i + 1]) for i in range(len(naive_path) - 1)]
        nx.draw_networkx_edges(
            G, pos, edgelist=naive_edges, ax=ax,
            edge_color="#ff6644", width=3.5, alpha=0.7,
            style="--", label="Dijkstra (Naive)"
        )

    # Draw ML route (green/cyan)
    if ml_route:
        ml_path = ml_route["path"]
        ml_edges = [(ml_path[i], ml_path[i + 1]) for i in range(len(ml_path) - 1)]
        nx.draw_networkx_edges(
            G, pos, edgelist=ml_edges, ax=ax,
            edge_color="#00ff88", width=3.5, alpha=0.9,
            label="A* (ML-Informed)"
        )

    # Draw nodes
    for node_type, style in NODE_STYLES.items():
        nodes = [n for n in G.nodes() if G.nodes[n].get("node_type") == node_type]
        if nodes:
            nx.draw_networkx_nodes(
                G, pos, nodelist=nodes, ax=ax,
                node_color=style["color"], node_size=style["size"] * 0.8,
                node_shape=style["marker"], alpha=0.8,
                edgecolors="white", linewidths=1,
            )

    nx.draw_networkx_labels(G, pos, ax=ax, font_size=7, font_color="white", font_weight="bold")

    # Legend
    legend_patches = [
        mpatches.Patch(color="#00ff88", label=f"A* (ML): cong={ml_route['avg_congestion']:.3f}" if ml_route else "A* (ML)"),
        mpatches.Patch(color="#ff6644", label=f"Dijkstra: cong={naive_route['avg_congestion']:.3f}" if naive_route else "Dijkstra"),
    ]
    ax.legend(handles=legend_patches, loc="lower left", fontsize=8,
              facecolor="#1a1e3a", edgecolor="#333", labelcolor="white")

    ax.set_title("🔀 Route Comparison: A* vs Dijkstra", fontsize=14,
                 fontweight="bold", color=VIZ_CONFIG["accent_color"], pad=10)
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(0.5, 10.0)
    ax.set_aspect("equal")
    ax.axis("off")


def draw_self_healing(ax, grid, healing_result):
    """Draw the self-healing scenario: failure + reroute."""
    G = grid.graph
    pos = grid.positions

    # Draw base edges dimmed
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#1a2a4a", width=0.8, alpha=0.3)

    # Draw the failed edge
    if healing_result.get("failed_edge"):
        fu, fv = healing_result["failed_edge"][0], healing_result["failed_edge"][1]
        if G.has_edge(fu, fv):
            nx.draw_networkx_edges(
                G, pos, edgelist=[(fu, fv)], ax=ax,
                edge_color=VIZ_CONFIG["failed_edge_color"],
                width=4, style="--", alpha=0.9,
            )
            # X mark on failed edge
            mid_x = (pos[fu][0] + pos[fv][0]) / 2
            mid_y = (pos[fu][1] + pos[fv][1]) / 2
            ax.text(mid_x, mid_y, "✕", fontsize=16, color="red",
                    ha="center", va="center", fontweight="bold",
                    bbox=dict(boxstyle="circle,pad=0.2", facecolor="black", alpha=0.8))

    # Draw original route (dimmed)
    if healing_result.get("original_route"):
        orig_path = healing_result["original_route"]["path"]
        orig_edges = [(orig_path[i], orig_path[i+1]) for i in range(len(orig_path)-1)]
        nx.draw_networkx_edges(
            G, pos, edgelist=orig_edges, ax=ax,
            edge_color="#ffaa00", width=2.5, alpha=0.4, style=":"
        )

    # Draw rerouted path
    if healing_result.get("reroute_result") and healing_result["reroute_result"]["new_route"]:
        new_path = healing_result["reroute_result"]["new_route"]["path"]
        new_edges = [(new_path[i], new_path[i+1]) for i in range(len(new_path)-1)]
        nx.draw_networkx_edges(
            G, pos, edgelist=new_edges, ax=ax,
            edge_color="#00ff88", width=3.5, alpha=0.95,
            arrows=True, arrowsize=12, arrowstyle="-|>",
        )

    # Nodes
    for node_type, style in NODE_STYLES.items():
        nodes = [n for n in G.nodes() if G.nodes[n].get("node_type") == node_type]
        if nodes:
            nx.draw_networkx_nodes(
                G, pos, nodelist=nodes, ax=ax,
                node_color=style["color"], node_size=style["size"] * 0.8,
                node_shape=style["marker"], alpha=0.8,
                edgecolors="white", linewidths=1,
            )

    nx.draw_networkx_labels(G, pos, ax=ax, font_size=7, font_color="white", font_weight="bold")

    # Legend
    legend_patches = [
        mpatches.Patch(color=VIZ_CONFIG["failed_edge_color"], label="Failed Line"),
        mpatches.Patch(color="#ffaa00", label="Original Route"),
        mpatches.Patch(color="#00ff88", label="Rerouted Path"),
    ]
    ax.legend(handles=legend_patches, loc="lower left", fontsize=8,
              facecolor="#1a1e3a", edgecolor="#333", labelcolor="white")

    status = "✅ HEALED" if healing_result.get("healing_success") else "⚠️ ATTENTION"
    ax.set_title(f"🛡️ Self-Healing Demo [{status}]", fontsize=14,
                 fontweight="bold", color=VIZ_CONFIG["accent_color"], pad=10)
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(0.5, 10.0)
    ax.set_aspect("equal")
    ax.axis("off")


# ─────────────────────────────────────────────
# Main Dashboard
# ─────────────────────────────────────────────

def generate_dashboard(grid, ml_route, naive_route, feature_importances,
                       healing_result, save=True) -> str:
    """
    Generate the full 6-panel visualization dashboard.

    Returns
    -------
    str
        Path to the saved dashboard image.
    """
    setup_dark_theme()

    fig, axes = plt.subplots(2, 3, figsize=VIZ_CONFIG["figure_size"])
    fig.patch.set_facecolor(VIZ_CONFIG["background_color"])

    # Add main title
    fig.suptitle(
        "⚡ Predictive Energy Routing — Hybrid ML–A* Optimization",
        fontsize=18, fontweight="bold",
        color=VIZ_CONFIG["accent_color"],
        y=0.98,
    )

    # Panel 1: Grid Topology
    draw_grid_topology(axes[0, 0], grid, "🔌 Grid Topology & Congestion")

    # Panel 2: Optimal Route (A*)
    draw_route(axes[0, 1], grid, ml_route, "🗺️ A* Optimal Route (ML-Informed)")

    # Panel 3: Feature Importance
    draw_feature_importance(axes[0, 2], feature_importances)

    # Panel 4: Congestion Heatmap
    draw_congestion_heatmap(axes[1, 0], grid)

    # Panel 5: Route Comparison
    draw_route_comparison(axes[1, 1], grid, ml_route, naive_route)

    # Panel 6: Self-Healing
    draw_self_healing(axes[1, 2], grid, healing_result)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    filepath = ""
    if save:
        filepath = os.path.join(OUTPUT_DIR, "dashboard.png")
        fig.savefig(filepath, dpi=VIZ_CONFIG["dpi"],
                    facecolor=VIZ_CONFIG["background_color"],
                    bbox_inches="tight", pad_inches=0.3)
        print(f"\n   🖼️  Dashboard saved to {filepath}")

    plt.close(fig)
    return filepath


def generate_individual_panels(grid, ml_route, naive_route,
                                feature_importances, healing_result):
    """Generate and save each panel as a separate high-res image."""
    setup_dark_theme()

    panels = {
        "01_grid_topology": lambda ax: draw_grid_topology(ax, grid),
        "02_optimal_route": lambda ax: draw_route(ax, grid, ml_route),
        "03_feature_importance": lambda ax: draw_feature_importance(ax, feature_importances),
        "04_congestion_heatmap": lambda ax: draw_congestion_heatmap(ax, grid),
        "05_route_comparison": lambda ax: draw_route_comparison(ax, grid, ml_route, naive_route),
        "06_self_healing": lambda ax: draw_self_healing(ax, grid, healing_result),
    }

    saved_files = []
    for name, draw_fn in panels.items():
        fig, ax = plt.subplots(1, 1, figsize=(10, 7))
        fig.patch.set_facecolor(VIZ_CONFIG["background_color"])
        draw_fn(ax)
        plt.tight_layout()

        filepath = os.path.join(OUTPUT_DIR, f"{name}.png")
        fig.savefig(filepath, dpi=VIZ_CONFIG["dpi"],
                    facecolor=VIZ_CONFIG["background_color"],
                    bbox_inches="tight", pad_inches=0.3)
        plt.close(fig)
        saved_files.append(filepath)

    print(f"   🖼️  {len(saved_files)} individual panels saved to {OUTPUT_DIR}/")
    return saved_files
