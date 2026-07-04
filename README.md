# ⚡ Predictive Energy Routing using Hybrid ML–A* Optimization

A smart, self-healing energy grid system that combines **Machine Learning** and **graph-based A\* pathfinding** to improve power distribution efficiency.

---

## 🎯 Overview

Traditional electrical grids use fixed routing paths. During demand spikes or renewable energy fluctuations, transmission lines may become overloaded — causing congestion, overheating, or outages.

This system **predicts** these issues in advance and **dynamically reroutes** power through healthier transmission paths.

---

## 🏗️ Architecture

```
┌──────────────────┐     ┌──────────────────┐
│  Data Generator   │ ──▶ │   ML Predictor    │
│ (Synthetic Grid)  │     │ (Random Forest)   │
└──────────────────┘     └───────┬──────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Grid Model          │
                    │ (NetworkX Graph)        │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
     ┌────────▼──────┐  ┌───────▼───────┐  ┌───────▼───────┐
     │  A* Router    │  │ Self-Healing  │  │  Visualizer   │
     │ (ML-Informed) │  │ (DFS + Reroute│  │ (Dashboard)   │
     └───────────────┘  └───────────────┘  └───────────────┘
```

---

## 🧩 Components

### 1. ML Congestion Predictor (`ml_predictor.py`)
- **Model**: Random Forest Regressor (scikit-learn)
- **Input**: Time, weather, historical load, renewable generation, infrastructure age
- **Output**: Congestion score (0.0–1.0)

### 2. A* Optimization Router (`astar_router.py`)
- **Cost function**: `f(n) = g(n) + h(n)`
  - `g(n)` = physical resistance × line length
  - `h(n)` = Euclidean distance + ML congestion penalty
- Compared against naive Dijkstra routing

### 3. Self-Healing System (`self_healing.py`)
- Detects at-risk edges via ML predictions
- DFS connectivity verification after failures
- Automatic rerouting through alternate paths

### 4. Visualization Dashboard (`visualizer.py`)
- 6-panel dark-themed dashboard:
  - Grid topology with congestion coloring
  - A* optimal route visualization
  - ML feature importance chart
  - Edge congestion heatmap
  - A* vs Dijkstra route comparison
  - Self-healing demonstration

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip

### Installation

```bash
cd PowerGrid
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

This executes the full pipeline:
1. Generates 5,000 synthetic grid data samples
2. Trains the Random Forest model
3. Constructs the 18-node power grid graph
4. Predicts edge congestion using the ML model
5. Finds optimal A* route (ML-informed)
6. Finds baseline Dijkstra route (comparison)
7. Runs self-healing cycle (failure → reroute)
8. Generates visualization dashboard

### Output
All visualizations are saved to the `output/` folder:
- `dashboard.png` — Full 6-panel dashboard
- `01_grid_topology.png` – `06_self_healing.png` — Individual panels

---

## 📁 Project Structure

```
PowerGrid/
├── main.py               # Entry point — runs the full pipeline
├── config.py              # Configuration and constants
├── data_generator.py      # Synthetic dataset generation
├── ml_predictor.py        # Random Forest congestion predictor
├── grid_model.py          # NetworkX graph model
├── astar_router.py        # A* routing with hybrid cost function
├── self_healing.py        # DFS connectivity + rerouting
├── visualizer.py          # Matplotlib dashboard generator
├── requirements.txt       # Python dependencies
├── data/                  # Generated datasets
├── models/                # Saved ML models
└── output/                # Visualization outputs
```

---

## 🌍 SDG Alignment

- **SDG 7** — Affordable and Clean Energy: Optimizes renewable energy utilization
- **SDG 9** — Industry, Innovation and Infrastructure: Intelligent adaptive grid infrastructure

---

## 📜 License

This project is for educational and research purposes.
