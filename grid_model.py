"""
Grid Model
===========
NetworkX-based power grid graph construction and management.
Nodes represent generators, substations, and consumers.
Edges represent transmission lines with physical and predicted attributes.
"""

import numpy as np
import networkx as nx

from config import (
    GRID_CONFIG, NodeType, RANDOM_SEED,
    ROUTING_CONFIG, CONGESTION_THRESHOLDS
)


# ─────────────────────────────────────────────
# Predefined grid layout for reproducible demos
# ─────────────────────────────────────────────
# Each node: (id, type, x, y, label)
GRID_NODES = [
    # Generators (power sources)
    ("G1", NodeType.GENERATOR, 1.0, 8.0, "Solar Farm Alpha"),
    ("G2", NodeType.GENERATOR, 5.0, 9.0, "Wind Plant Beta"),
    ("G3", NodeType.GENERATOR, 9.0, 8.5, "Thermal Station Gamma"),
    ("G4", NodeType.GENERATOR, 3.0, 5.0, "Hydro Plant Delta"),

    # Substations (transformers / relay points)
    ("S1", NodeType.SUBSTATION, 2.5, 7.0, "Substation North-West"),
    ("S2", NodeType.SUBSTATION, 5.0, 7.0, "Substation North"),
    ("S3", NodeType.SUBSTATION, 7.5, 7.0, "Substation North-East"),
    ("S4", NodeType.SUBSTATION, 3.0, 3.5, "Substation West"),
    ("S5", NodeType.SUBSTATION, 6.0, 4.0, "Substation Central"),
    ("S6", NodeType.SUBSTATION, 8.0, 4.5, "Substation East"),

    # Consumers (demand points)
    ("C1", NodeType.CONSUMER, 1.5, 5.5, "Residential Zone A"),
    ("C2", NodeType.CONSUMER, 4.0, 6.0, "Commercial District B"),
    ("C3", NodeType.CONSUMER, 6.5, 5.5, "Industrial Park C"),
    ("C4", NodeType.CONSUMER, 2.0, 2.0, "Township D"),
    ("C5", NodeType.CONSUMER, 4.5, 1.5, "Smart Village E"),
    ("C6", NodeType.CONSUMER, 7.0, 2.0, "Tech Hub F"),
    ("C7", NodeType.CONSUMER, 9.0, 3.0, "Data Center G"),
    ("C8", NodeType.CONSUMER, 5.5, 2.5, "University Campus H"),
]

# Each edge: (from, to) — the system computes attributes automatically
GRID_EDGES = [
    # Generator → Substation connections
    ("G1", "S1"), ("G2", "S2"), ("G3", "S3"),
    ("G4", "S4"), ("G4", "S1"),
    ("G1", "C1"), ("G2", "S5"),

    # Substation backbone (inter-substation links)
    ("S1", "S2"), ("S2", "S3"), ("S1", "S4"),
    ("S4", "S5"), ("S5", "S6"), ("S3", "S6"),
    ("S2", "S5"),

    # Substation → Consumer distribution
    ("S1", "C1"), ("S1", "C2"), ("S2", "C2"),
    ("S2", "C3"), ("S3", "C3"), ("S3", "C7"),
    ("S4", "C4"), ("S4", "C5"), ("S5", "C5"),
    ("S5", "C8"), ("S5", "C3"), ("S6", "C6"),
    ("S6", "C7"),

    # Consumer cross-connections (local distribution)
    ("C4", "C5"), ("C5", "C8"), ("C6", "C7"),
    ("C2", "C3"),
]


class PowerGrid:
    """
    Manages the power grid as a NetworkX graph.

    Nodes have attributes: type, position, label.
    Edges have attributes: length, resistance, capacity, age,
                          congestion_score, features (for ML).
    """

    def __init__(self):
        self.graph = nx.Graph()
        self.positions = {}
        self.node_types = {}
        self.rng = np.random.default_rng(RANDOM_SEED)

    def build_grid(self) -> nx.Graph:
        """
        Construct the power grid graph with nodes and edges.

        Returns
        -------
        nx.Graph
            The constructed grid graph.
        """
        print("\n🔌 Building power grid graph...")

        # Add nodes
        for node_id, node_type, x, y, label in GRID_NODES:
            self.graph.add_node(
                node_id,
                node_type=node_type,
                pos=(x, y),
                label=label,
            )
            self.positions[node_id] = (x, y)
            self.node_types[node_id] = node_type

        # Add edges with computed attributes
        for u, v in GRID_EDGES:
            if u in self.graph.nodes and v in self.graph.nodes:
                attrs = self._compute_edge_attributes(u, v)
                self.graph.add_edge(u, v, **attrs)

        n_gen = sum(1 for _, t in self.node_types.items() if t == NodeType.GENERATOR)
        n_sub = sum(1 for _, t in self.node_types.items() if t == NodeType.SUBSTATION)
        n_con = sum(1 for _, t in self.node_types.items() if t == NodeType.CONSUMER)

        print(f"   ✅ Grid built: {self.graph.number_of_nodes()} nodes, "
              f"{self.graph.number_of_edges()} edges")
        print(f"      ⚡ Generators: {n_gen}  |  🔄 Substations: {n_sub}  |  🏠 Consumers: {n_con}")
        print(f"      📡 Connected: {nx.is_connected(self.graph)}")

        return self.graph

    def _compute_edge_attributes(self, u: str, v: str) -> dict:
        """Compute physical attributes for an edge based on node positions."""
        pos_u = self.positions[u]
        pos_v = self.positions[v]

        # Euclidean distance as line length (scaled to km)
        length = np.sqrt((pos_u[0] - pos_v[0])**2 + (pos_u[1] - pos_v[1])**2)
        length_km = length * 15  # Scale factor: 1 unit ≈ 15 km

        # Resistance proportional to length
        resistance = ROUTING_CONFIG["resistance_base"] * length_km

        # Random infrastructure attributes
        age = float(self.rng.integers(3, 45))
        capacity = float(self.rng.integers(100, 500))

        # Initial congestion (will be updated by ML)
        congestion_score = 0.0

        # Generate feature dict for ML predictions
        # Some edges get "stressed" conditions to demonstrate self-healing
        stressed_edges = {
            ("S2", "S3"): {"hour": 14.0, "temperature": 42.0, "humidity": 85.0,
                           "wind_speed": 5.0, "solar_irradiance": 200.0,
                           "historical_load": 480.0, "renewable_ratio": 0.05},
            ("S5", "C3"): {"hour": 19.0, "temperature": 38.0, "humidity": 75.0,
                           "wind_speed": 8.0, "solar_irradiance": 50.0,
                           "historical_load": 460.0, "renewable_ratio": 0.08},
            ("S3", "C7"): {"hour": 13.0, "temperature": 40.0, "humidity": 80.0,
                           "wind_speed": 3.0, "solar_irradiance": 150.0,
                           "historical_load": 450.0, "renewable_ratio": 0.1},
            ("S6", "C7"): {"hour": 18.0, "temperature": 36.0, "humidity": 70.0,
                           "wind_speed": 10.0, "solar_irradiance": 100.0,
                           "historical_load": 420.0, "renewable_ratio": 0.12},
            ("C6", "C7"): {"hour": 20.0, "temperature": 35.0, "humidity": 72.0,
                           "wind_speed": 6.0, "solar_irradiance": 0.0,
                           "historical_load": 440.0, "renewable_ratio": 0.07},
        }

        edge_key = (u, v)
        edge_key_rev = (v, u)
        stressed = stressed_edges.get(edge_key) or stressed_edges.get(edge_key_rev)

        if stressed:
            # Use stressed conditions — old line under heavy load
            features = {
                **stressed,
                "line_age_years": max(age, 35.0),  # Force old line
                "line_length_km": length_km,
            }
            age = max(age, 35.0)
        else:
            hour = float(self.rng.integers(0, 24))
            features = {
                "hour": hour,
                "temperature": float(self.rng.normal(25, 8)),
                "humidity": float(self.rng.normal(60, 15)),
                "wind_speed": float(self.rng.exponential(15)),
                "solar_irradiance": float(max(0, self.rng.normal(400, 200))),
                "historical_load": float(self.rng.normal(250, 80)),
                "renewable_ratio": float(self.rng.beta(2, 3)),
                "line_age_years": age,
                "line_length_km": length_km,
            }

        return {
            "length": length,
            "length_km": length_km,
            "resistance": resistance,
            "capacity": capacity,
            "age": age,
            "congestion_score": congestion_score,
            "features": features,
            "is_failed": False,
        }

    def update_congestion(self, predictor) -> dict:
        """
        Update edge congestion scores using the ML predictor.

        Parameters
        ----------
        predictor : CongestionPredictor
            Trained ML model.

        Returns
        -------
        dict
            Edge → congestion_score mapping.
        """
        print("\n🔮 Updating edge congestion with ML predictions...")

        congestion_map = {}
        for u, v, data in self.graph.edges(data=True):
            if not data.get("is_failed", False):
                score = predictor.predict_congestion(data["features"])
                self.graph[u][v]["congestion_score"] = score
                congestion_map[(u, v)] = score

        # Print summary
        scores = list(congestion_map.values())
        print(f"   📊 Congestion Summary:")
        print(f"      Mean:     {np.mean(scores):.3f}")
        print(f"      Max:      {np.max(scores):.3f}")
        print(f"      Critical: {sum(1 for s in scores if s > CONGESTION_THRESHOLDS['critical'])} edges")
        print(f"      High:     {sum(1 for s in scores if s > CONGESTION_THRESHOLDS['high'])} edges")

        return congestion_map

    def get_generators(self) -> list:
        """Return list of generator node IDs."""
        return [n for n, t in self.node_types.items() if t == NodeType.GENERATOR]

    def get_consumers(self) -> list:
        """Return list of consumer node IDs."""
        return [n for n, t in self.node_types.items() if t == NodeType.CONSUMER]

    def get_substations(self) -> list:
        """Return list of substation node IDs."""
        return [n for n, t in self.node_types.items() if t == NodeType.SUBSTATION]

    def remove_edge(self, u: str, v: str):
        """Mark an edge as failed (remove from active graph)."""
        if self.graph.has_edge(u, v):
            self.graph[u][v]["is_failed"] = True
            self.graph[u][v]["original_congestion"] = self.graph[u][v]["congestion_score"]
            self.graph[u][v]["congestion_score"] = 1.0

    def restore_edge(self, u: str, v: str):
        """Restore a previously failed edge."""
        if self.graph.has_edge(u, v):
            self.graph[u][v]["is_failed"] = False
            if "original_congestion" in self.graph[u][v]:
                self.graph[u][v]["congestion_score"] = self.graph[u][v]["original_congestion"]

    def get_active_graph(self) -> nx.Graph:
        """Return a subgraph containing only non-failed edges."""
        active_edges = [
            (u, v) for u, v, d in self.graph.edges(data=True)
            if not d.get("is_failed", False)
        ]
        return self.graph.edge_subgraph(active_edges).copy()

    def get_edge_congestion_level(self, u: str, v: str) -> str:
        """Return the congestion level category for an edge."""
        if not self.graph.has_edge(u, v):
            return "unknown"
        score = self.graph[u][v]["congestion_score"]
        if score >= CONGESTION_THRESHOLDS["critical"]:
            return "critical"
        elif score >= CONGESTION_THRESHOLDS["high"]:
            return "high"
        elif score >= CONGESTION_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "low"


if __name__ == "__main__":
    grid = PowerGrid()
    G = grid.build_grid()
    print(f"\nNodes: {list(G.nodes())}")
    print(f"Edges: {G.number_of_edges()}")
    print(f"Generators: {grid.get_generators()}")
    print(f"Consumers: {grid.get_consumers()}")
