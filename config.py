"""
PowerGrid Configuration
========================
Central configuration for the Predictive Energy Routing system.
Contains grid parameters, ML settings, thresholds, and visualization config.
"""

import os
import sys

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

# ─────────────────────────────────────────────
# Directory paths
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
MODEL_DIR = os.path.join(BASE_DIR, "models")

# Ensure directories exist
for d in [DATA_DIR, OUTPUT_DIR, MODEL_DIR]:
    os.makedirs(d, exist_ok=True)

# ─────────────────────────────────────────────
# Grid Topology
# ─────────────────────────────────────────────
GRID_CONFIG = {
    "num_generators": 4,
    "num_substations": 6,
    "num_consumers": 8,
    "edge_density": 0.35,       # Probability of edge between nearby nodes
    "max_connection_distance": 4.0,  # Max Euclidean distance for edge creation
}

# Node type definitions
class NodeType:
    GENERATOR = "generator"
    SUBSTATION = "substation"
    CONSUMER = "consumer"

# Node display properties
NODE_STYLES = {
    NodeType.GENERATOR: {
        "color": "#FF4444",
        "marker": "s",     # square
        "size": 700,
        "label": "⚡ Generator",
    },
    NodeType.SUBSTATION: {
        "color": "#FFD700",
        "marker": "D",     # diamond
        "size": 500,
        "label": "🔄 Substation",
    },
    NodeType.CONSUMER: {
        "color": "#4488FF",
        "marker": "o",     # circle
        "size": 400,
        "label": "🏠 Consumer",
    },
}

# ─────────────────────────────────────────────
# Machine Learning Configuration
# ─────────────────────────────────────────────
ML_CONFIG = {
    "n_estimators": 150,
    "max_depth": 12,
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "random_state": 42,
    "test_size": 0.2,
    "n_samples": 5000,      # Number of synthetic samples to generate
}

# Feature names for the ML model
FEATURE_NAMES = [
    "hour",
    "temperature",
    "weather",
    "historical_load",
    "renewable_generation",
    "voltage",
    "current",
    "previous_congestion",
]

TARGET_NAME = "congestion_score"

# ─────────────────────────────────────────────
# Congestion Thresholds
# ─────────────────────────────────────────────
CONGESTION_THRESHOLDS = {
    "low": 0.3,
    "medium": 0.5,
    "high": 0.7,
    "critical": 0.85,
}

# ─────────────────────────────────────────────
# A* Routing Configuration
# ─────────────────────────────────────────────
ROUTING_CONFIG = {
    "loss_weight": 0.4,
    "congestion_weight": 0.4,
    "resistance_weight": 0.2,
    "alpha": 0.6,           # Weight for ML congestion in cost function (0–1)
    "beta": 0.4,            # Weight for physical resistance (1 - alpha)
    "congestion_penalty": 5.0,   # Multiplier for congestion in heuristic
    "resistance_base": 0.01,     # Base resistance per km
}

# ─────────────────────────────────────────────
# Visualization
# ─────────────────────────────────────────────
VIZ_CONFIG = {
    "figure_size": (20, 14),
    "dpi": 150,
    "background_color": "#0a0e27",
    "text_color": "#e0e0e0",
    "grid_color": "#1a1e3a",
    "accent_color": "#00d4ff",
    "congestion_cmap": "RdYlGn_r",   # Red = high congestion, Green = low
    "path_color": "#00ff88",
    "failed_edge_color": "#ff0055",
    "font_family": "sans-serif",
}

# Congestion color mapping for edges
CONGESTION_COLORS = {
    "low": "#00ff88",       # Green
    "medium": "#ffdd00",    # Yellow
    "high": "#ff8800",      # Orange
    "critical": "#ff0044",  # Red
}

# ─────────────────────────────────────────────
# Self-Healing
# ─────────────────────────────────────────────
HEALING_CONFIG = {
    "failure_threshold": 0.85,     # Congestion score above which line "fails"
    "warning_threshold": 0.70,     # Score triggering preventive rerouting
    "max_reroute_attempts": 5,
}

# ─────────────────────────────────────────────
# Random seed for reproducibility
# ─────────────────────────────────────────────
RANDOM_SEED = 42
