"""
A* Energy Router
=================
Implements A* pathfinding with a hybrid cost function that combines
physical transmission costs with ML-predicted congestion scores.
Also provides naive Dijkstra routing for comparison.
"""

import numpy as np
import networkx as nx
from typing import Optional

from config import ROUTING_CONFIG, CONGESTION_THRESHOLDS


class EnergyRouter:
    """
    A* router for optimal energy path selection.

    Cost function: f(n) = g(n) + h(n)
      g(n) = cumulative real cost (resistance + transmission loss)
      h(n) = heuristic (Euclidean distance + ML congestion penalty)

    The alpha parameter controls the balance between physical cost
    and predicted congestion:
      total_edge_cost = beta * physical_cost + alpha * congestion_penalty
    """

    def __init__(self, alpha: float = None, beta: float = None):
        """
        Parameters
        ----------
        alpha : float
            Weight for congestion penalty (default from config).
        beta : float
            Weight for physical cost (default from config).
        """
        self.alpha = alpha or ROUTING_CONFIG["alpha"]
        self.beta = beta or ROUTING_CONFIG["beta"]
        self.congestion_penalty = ROUTING_CONFIG["congestion_penalty"]
        self._max_resistance = 1.0

    def _set_resistance_scale(self, graph: nx.Graph) -> None:
        """Cache max resistance so edge costs stay on a comparable 0–1 scale."""
        resistances = [
            data.get("resistance", 0.1)
            for _, _, data in graph.edges(data=True)
            if not data.get("is_failed", False)
        ]
        self._max_resistance = max(resistances) if resistances else 1.0

    def _normalized_resistance(self, resistance: float) -> float:
        if self._max_resistance <= 0:
            return resistance
        return resistance / self._max_resistance

    def _edge_cost(self, u, v, data: dict) -> float:
        """
        Compute the traversal cost for an edge.

        Combines physical resistance/loss with ML-predicted congestion.
        """
        resistance = self._normalized_resistance(data.get("resistance", 0.1))
        congestion = data.get("congestion_score", 0.0)
        transmission_loss = min(float(data.get("transmission_loss", 0.0)), 1.0)

        # Skip failed edges entirely
        if data.get("is_failed", False):
            return float("inf")

        total = (
            ROUTING_CONFIG["loss_weight"] * transmission_loss
            + ROUTING_CONFIG["congestion_weight"] * congestion
            + ROUTING_CONFIG["resistance_weight"] * resistance
        )
        return max(total, 0.001)  # Ensure positive cost

    def _heuristic(self, node, target, graph: nx.Graph) -> float:
        """
        A* heuristic: Euclidean distance to target.
        Admissible because straight-line distance never overestimates
        the true shortest path in a geographic network.
        """
        pos_node = graph.nodes[node].get("pos", (0, 0))
        pos_target = graph.nodes[target].get("pos", (0, 0))
        dx = pos_node[0] - pos_target[0]
        dy = pos_node[1] - pos_target[1]
        return np.sqrt(dx**2 + dy**2) * ROUTING_CONFIG["resistance_base"]

    def find_optimal_route(self, graph: nx.Graph, source: str,
                           target: str) -> Optional[dict]:
        """
        Find the optimal energy route using A* with hybrid cost.

        Parameters
        ----------
        graph : nx.Graph
            The power grid graph.
        source : str
            Source node ID (typically a generator).
        target : str
            Target node ID (typically a consumer).

        Returns
        -------
        dict or None
            Route information including path, costs, and per-edge details.
        """
        # Build working graph (exclude failed edges)
        self._set_resistance_scale(graph)
        working_graph = nx.Graph()
        for u, v, data in graph.edges(data=True):
            if not data.get("is_failed", False):
                cost = self._edge_cost(u, v, data)
                working_graph.add_edge(u, v, weight=cost, **data)

        # Copy node attributes
        for node, data in graph.nodes(data=True):
            if node in working_graph:
                working_graph.nodes[node].update(data)

        if source not in working_graph or target not in working_graph:
            print(f"   ❌ Source ({source}) or target ({target}) not in active graph")
            return None

        try:
            # A* pathfinding
            path = nx.astar_path(
                working_graph, source, target,
                heuristic=lambda n, t: self._heuristic(n, t, working_graph),
                weight="weight"
            )

            # Compute detailed cost breakdown
            total_cost = 0
            total_physical = 0
            total_congestion = 0
            edge_details = []

            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                data = graph[u][v]

                physical = data.get("transmission_loss", 0.0)
                cong = data.get("congestion_score", 0.0)
                edge_cost = self._edge_cost(u, v, data)

                total_cost += edge_cost
                total_physical += physical
                total_congestion += cong

                edge_details.append({
                    "from": u,
                    "to": v,
                    "physical_cost": physical,
                    "transmission_loss": data.get("transmission_loss", 0.0),
                    "congestion_score": cong,
                    "total_cost": edge_cost,
                    "length_km": data.get("length_km", 0),
                })

            return {
                "path": path,
                "total_cost": total_cost,
                "total_physical_cost": total_physical,
                "total_congestion": total_congestion,
                "avg_congestion": total_congestion / max(len(path) - 1, 1),
                "num_hops": len(path) - 1,
                "edge_details": edge_details,
                "algorithm": "A* (ML-Informed)",
            }

        except nx.NetworkXNoPath:
            print(f"   ❌ No path found from {source} to {target}")
            return None

    def find_naive_route(self, graph: nx.Graph, source: str,
                         target: str) -> Optional[dict]:
        """
        Find route using Dijkstra WITHOUT ML congestion awareness.
        Uses only physical resistance as edge weight.
        This serves as a baseline comparison.
        """
        # Build graph with only physical costs (same weights, no congestion term)
        self._set_resistance_scale(graph)
        working_graph = nx.Graph()
        for u, v, data in graph.edges(data=True):
            if not data.get("is_failed", False):
                physical_cost = (
                    ROUTING_CONFIG["loss_weight"] * min(float(data.get("transmission_loss", 0.0)), 1.0)
                    + ROUTING_CONFIG["resistance_weight"] * self._normalized_resistance(data.get("resistance", 0.1))
                )
                working_graph.add_edge(u, v, weight=physical_cost, **data)

        for node, data in graph.nodes(data=True):
            if node in working_graph:
                working_graph.nodes[node].update(data)

        if source not in working_graph or target not in working_graph:
            return None

        try:
            path = nx.dijkstra_path(working_graph, source, target, weight="weight")

            total_cost = 0
            total_congestion = 0
            edge_details = []

            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                data = graph[u][v]

                physical = data.get("transmission_loss", 0.0) + data.get("resistance", 0.1)
                cong = data.get("congestion_score", 0.0)

                total_cost += physical
                total_congestion += cong

                edge_details.append({
                    "from": u,
                    "to": v,
                    "physical_cost": physical,
                    "transmission_loss": data.get("transmission_loss", 0.0),
                    "congestion_score": cong,
                    "total_cost": physical,
                    "length_km": data.get("length_km", 0),
                })

            return {
                "path": path,
                "total_cost": total_cost,
                "total_physical_cost": total_cost,
                "total_congestion": total_congestion,
                "avg_congestion": total_congestion / max(len(path) - 1, 1),
                "num_hops": len(path) - 1,
                "edge_details": edge_details,
                "algorithm": "Dijkstra (Naive)",
            }

        except nx.NetworkXNoPath:
            return None

    @staticmethod
    def print_route(route: dict):
        """Print a formatted route summary."""
        if route is None:
            print("   ❌ No route found.")
            return

        print(f"\n   🗺️  Route ({route['algorithm']}):")
        print(f"      Path: {' → '.join(route['path'])}")
        print(f"      Hops: {route['num_hops']}")
        print(f"      Total Cost:       {route['total_cost']:.4f}")
        print(f"      Physical Cost:    {route['total_physical_cost']:.4f}")
        print(f"      Avg Congestion:   {route['avg_congestion']:.4f}")
        print(f"\n      Edge Breakdown:")
        print(f"      {'From':>6} → {'To':<6}  {'Phys':>8}  {'Cong':>8}  {'Total':>8}")
        print(f"      {'─'*46}")
        for edge in route["edge_details"]:
            print(f"      {edge['from']:>6} → {edge['to']:<6}  "
                  f"{edge['physical_cost']:>8.4f}  "
                  f"{edge['congestion_score']:>8.4f}  "
                  f"{edge['total_cost']:>8.4f}")

    @staticmethod
    def compare_routes(ml_route: dict, naive_route: dict):
        """Print a comparison between ML-informed and naive routes."""
        if ml_route is None or naive_route is None:
            print("   ⚠️  Cannot compare — one or both routes not found.")
            return

        print("\n" + "=" * 60)
        print("   📊 ROUTE COMPARISON: A* (ML) vs Dijkstra (Naive)")
        print("=" * 60)

        same_path = ml_route["path"] == naive_route["path"]

        print(f"   {'Metric':<25} {'A* (ML)':>12} {'Dijkstra':>12} {'Winner':>10}")
        print(f"   {'─'*59}")

        # Total cost comparison
        ml_cost = ml_route["total_cost"]
        nv_cost = naive_route["total_cost"]
        winner = "A*" if ml_cost <= nv_cost else "Dijkstra"
        print(f"   {'Total Cost':<25} {ml_cost:>12.4f} {nv_cost:>12.4f} {winner:>10}")

        # Congestion comparison
        ml_cong = ml_route["avg_congestion"]
        nv_cong = naive_route["avg_congestion"]
        winner = "A*" if ml_cong <= nv_cong else "Dijkstra"
        print(f"   {'Avg Congestion':<25} {ml_cong:>12.4f} {nv_cong:>12.4f} {winner:>10}")

        # Hops
        print(f"   {'Hops':<25} {ml_route['num_hops']:>12} {naive_route['num_hops']:>12}")

        # Path similarity
        print(f"   {'Same Path?':<25} {'Yes' if same_path else 'No':>25}")

        if not same_path:
            print(f"\n   A* path:      {' → '.join(ml_route['path'])}")
            print(f"   Dijkstra path: {' → '.join(naive_route['path'])}")

            # Congestion advantage
            if ml_cong < nv_cong:
                improvement = ((nv_cong - ml_cong) / nv_cong) * 100
                print(f"\n   🎯 A* reduces congestion by {improvement:.1f}% vs naive routing!")
