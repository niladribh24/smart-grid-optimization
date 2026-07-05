"""
Self-Healing Mechanism
=======================
Detects failing transmission lines, verifies network connectivity using DFS,
and triggers A* rerouting to prevent blackouts.
"""

import networkx as nx
from typing import Optional, Tuple

from config import HEALING_CONFIG, CONGESTION_THRESHOLDS


def edges_on_path(path: list) -> list:
    """Return (u, v) tuples for consecutive nodes on a path."""
    if not path or len(path) < 2:
        return []
    return [(path[i], path[i + 1]) for i in range(len(path) - 1)]


def edge_in_path(u: str, v: str, path: list) -> bool:
    """Check whether an undirected edge appears on a path."""
    for a, b in edges_on_path(path):
        if (u, v) == (a, b) or (v, u) == (a, b):
            return True
    return False


class SelfHealingSystem:
    """
    Self-healing module for the power grid.

    Workflow:
      1. Detect edges at risk of failure (congestion > threshold)
      2. Simulate edge removal
      3. Check connectivity via DFS
      4. Reroute energy through alternate paths using A*
      5. Report isolated components if disconnection occurs
    """

    def __init__(self, grid, router):
        """
        Parameters
        ----------
        grid : PowerGrid
            The power grid model.
        router : EnergyRouter
            The A* router for rerouting.
        """
        self.grid = grid
        self.router = router
        self.failure_log = []
        self.reroute_log = []

    def detect_at_risk_edges(self) -> list:
        """
        Identify edges with congestion scores above the warning threshold.

        Returns
        -------
        list of tuples
            List of (u, v, congestion_score) for at-risk edges.
        """
        at_risk = []
        for u, v, data in self.grid.graph.edges(data=True):
            if data.get("is_failed", False):
                continue
            score = data.get("congestion_score", 0.0)
            if score >= HEALING_CONFIG["warning_threshold"]:
                at_risk.append((u, v, score))

        # Sort by congestion (highest first)
        at_risk.sort(key=lambda x: x[2], reverse=True)
        return at_risk

    def detect_critical_edges(self) -> list:
        """
        Identify edges above the failure threshold.

        Returns
        -------
        list of tuples
            List of (u, v, congestion_score) for critical edges.
        """
        critical = []
        for u, v, data in self.grid.graph.edges(data=True):
            if data.get("is_failed", False):
                continue
            score = data.get("congestion_score", 0.0)
            if score >= HEALING_CONFIG["failure_threshold"]:
                critical.append((u, v, score))

        critical.sort(key=lambda x: x[2], reverse=True)
        return critical

    def critical_edges_on_path(self, path: list) -> list:
        """Critical edges (>= failure threshold) that lie on the given path."""
        if not path:
            return []
        return [
            (u, v, score) for u, v, score in self.detect_critical_edges()
            if edge_in_path(u, v, path)
        ]

    def select_failure_edge(self, route_path: list) -> Optional[Tuple[str, str, float]]:
        """
        Pick the edge to fail for healing demos and manual triggers.

        Priority:
          1. Highest-congestion critical edge on the current route
          2. Highest-congestion critical edge anywhere
          3. Highest-congestion edge on the current route (warning level)
        """
        if not route_path:
            return None

        on_route_critical = self.critical_edges_on_path(route_path)
        if on_route_critical:
            return on_route_critical[0]

        on_route = []
        for u, v, score in self.detect_at_risk_edges():
            if edge_in_path(u, v, route_path):
                on_route.append((u, v, score))
        if on_route:
            return on_route[0]

        highest_on_route = self._highest_congestion_on_path(route_path)
        if highest_on_route and highest_on_route[2] >= HEALING_CONFIG["failure_threshold"]:
            return highest_on_route

        critical = self.detect_critical_edges()
        if critical:
            return critical[0]

        return None

    def _highest_congestion_on_path(self, path: list) -> Optional[Tuple[str, str, float]]:
        """Highest-congestion active edge along a path."""
        candidates = []
        for u, v in edges_on_path(path):
            if not self.grid.graph.has_edge(u, v):
                continue
            data = self.grid.graph[u][v]
            if data.get("is_failed", False):
                continue
            candidates.append((u, v, data.get("congestion_score", 0.0)))
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates[0] if candidates else None

    def check_source_target_connected(self, source: str, target: str,
                                      graph: nx.Graph = None) -> bool:
        """Return True when an active path exists between source and target."""
        if graph is None:
            graph = self.grid.get_active_graph()
        if source not in graph or target not in graph:
            return False
        return nx.has_path(graph, source, target)

    def dfs_connectivity_check(self, graph: nx.Graph = None) -> dict:
        """
        Check network connectivity using Depth-First Search.

        Parameters
        ----------
        graph : nx.Graph, optional
            Graph to check. Defaults to active (non-failed) edges.

        Returns
        -------
        dict
            Connectivity report including components and isolated nodes.
        """
        if graph is None:
            graph = self.grid.get_active_graph()

        # DFS-based connected components
        visited = set()
        components = []

        def dfs(node, component):
            """Standard DFS traversal."""
            visited.add(node)
            component.append(node)
            for neighbor in graph.neighbors(node):
                if neighbor not in visited:
                    dfs(node=neighbor, component=component)

        for node in graph.nodes():
            if node not in visited:
                component = []
                dfs(node, component)
                components.append(sorted(component))

        is_connected = len(components) == 1

        # Identify isolated generators and consumers
        generators = self.grid.get_generators()
        consumers = self.grid.get_consumers()
        isolated_gens = []
        isolated_cons = []

        if not components:
            return {
                "is_connected": False,
                "num_components": 0,
                "components": [],
                "isolated_generators": generators,
                "isolated_consumers": consumers,
                "total_nodes": 0,
            }

        if not is_connected:
            # Find which component has the most generators (main grid)
            main_component = max(components, key=len)
            for comp in components:
                if comp != main_component:
                    for node in comp:
                        if node in generators:
                            isolated_gens.append(node)
                        elif node in consumers:
                            isolated_cons.append(node)

        return {
            "is_connected": is_connected,
            "num_components": len(components),
            "components": components,
            "isolated_generators": isolated_gens,
            "isolated_consumers": isolated_cons,
            "total_nodes": graph.number_of_nodes(),
        }

    def simulate_failure(self, u: str, v: str) -> dict:
        """
        Simulate a transmission line failure and assess impact.

        Parameters
        ----------
        u, v : str
            The edge endpoints to fail.

        Returns
        -------
        dict
            Failure report with connectivity analysis.
        """
        print(f"\n   ⚡ Simulating failure of line {u} ↔ {v}...")

        # Store original state
        original_data = dict(self.grid.graph[u][v]) if self.grid.graph.has_edge(u, v) else None
        congestion = original_data.get("congestion_score", 0) if original_data else 0

        # Remove edge
        self.grid.remove_edge(u, v)

        # Check connectivity
        connectivity = self.dfs_connectivity_check()

        failure_report = {
            "failed_edge": (u, v),
            "congestion_at_failure": congestion,
            "connectivity": connectivity,
        }

        self.failure_log.append(failure_report)

        # Print report
        if connectivity["is_connected"]:
            print(f"      ✅ Network remains connected after removing {u}↔{v}")
        else:
            print(f"      ⚠️  Network DISCONNECTED into {connectivity['num_components']} components!")
            if connectivity["isolated_generators"]:
                print(f"      🔴 Isolated generators: {connectivity['isolated_generators']}")
            if connectivity["isolated_consumers"]:
                print(f"      🔵 Isolated consumers: {connectivity['isolated_consumers']}")

        return failure_report

    def reroute_after_failure(self, source: str, target: str,
                              failed_edge: tuple = None,
                              original_path: list = None) -> dict:
        """
        Find an alternate route after a line failure.

        Parameters
        ----------
        source : str
            Source node.
        target : str
            Target node.
        failed_edge : tuple, optional
            The (u, v) edge that failed (for logging).
        original_path : list, optional
            Path before failure (for change detection).

        Returns
        -------
        dict
            Rerouting result with old and new paths.
        """
        print(f"\n   🔄 Rerouting energy from {source} to {target}...")

        if original_path is None:
            original_path = []

        connected = self.check_source_target_connected(source, target)
        if not connected:
            print(f"      ❌ Destination {target} is isolated from {source}!")
            reroute_result = {
                "source": source,
                "target": target,
                "failed_edge": failed_edge,
                "original_path": original_path,
                "new_route": None,
                "success": False,
                "path_changed": False,
                "destination_isolated": True,
                "explanation": (
                    f"Transmission line failure disconnected {target} from the grid. "
                    "No alternate path is available."
                ),
            }
            self.reroute_log.append(reroute_result)
            return reroute_result

        new_route = self.router.find_optimal_route(self.grid.graph, source, target)

        if new_route:
            print(f"      ✅ Alternate route found: {' → '.join(new_route['path'])}")
            print(f"      📊 New route cost: {new_route['total_cost']:.4f}")
        else:
            print(f"      ❌ No alternate route available!")

        new_path = new_route["path"] if new_route else []
        path_changed = bool(original_path) and new_path != original_path
        failed_on_route = (
            failed_edge
            and original_path
            and edge_in_path(failed_edge[0], failed_edge[1], original_path)
        )

        if new_route and path_changed:
            explanation = (
                "The original transmission line became overloaded or failed. "
                "Power was redirected through a safer route with lower expected cost."
            )
        elif new_route and failed_on_route and not path_changed:
            explanation = (
                "The overloaded line was removed, but the optimal A* path "
                "already avoided that segment."
            )
        elif new_route:
            explanation = "Optimal route recalculated on the active grid."
        else:
            explanation = (
                f"Destination {target} is isolated — no path exists from {source}."
            )

        reroute_result = {
            "source": source,
            "target": target,
            "failed_edge": failed_edge,
            "original_path": original_path,
            "new_route": new_route,
            "success": new_route is not None,
            "path_changed": path_changed,
            "destination_isolated": new_route is None,
            "explanation": explanation,
        }

        self.reroute_log.append(reroute_result)
        return reroute_result

    def process_congestion_failures(self, source: str, target: str) -> dict:
        """
        Self-healing cycle for live simulation:
          1. Fail all edges above the congestion threshold
          2. Verify connectivity with DFS
          3. Recalculate route with A*
        """
        original_route = self.router.find_optimal_route(self.grid.graph, source, target)
        original_path = original_route["path"] if original_route else []

        failed_edges = []
        for u, v, score in self.detect_critical_edges():
            self.grid.remove_edge(u, v)
            failed_edges.append({
                "source": u,
                "target": v,
                "congestion_score": float(score),
            })

        connectivity = self.dfs_connectivity_check()
        reroute_result = self.reroute_after_failure(
            source,
            target,
            failed_edge=None,
            original_path=original_path,
        )

        return {
            "failed_edges": failed_edges,
            "original_path": original_path,
            "connectivity": connectivity,
            "reroute_result": reroute_result,
            "destination_isolated": reroute_result["destination_isolated"],
            "healing_success": reroute_result["success"],
            "path_changed": reroute_result["path_changed"],
            "explanation": reroute_result["explanation"],
        }

    def full_healing_cycle(self, source: str, target: str) -> dict:
        """
        Execute a complete self-healing cycle:
        1. Detect critical edges
        2. Simulate worst failure
        3. Check connectivity
        4. Reroute

        Parameters
        ----------
        source, target : str
            Source and target for rerouting.

        Returns
        -------
        dict
            Complete healing cycle report.
        """
        print("\n" + "=" * 60)
        print("   🛡️  SELF-HEALING CYCLE")
        print("=" * 60)

        # Step 1: Detect critical edges
        critical = self.detect_critical_edges()
        at_risk = self.detect_at_risk_edges()

        print(f"\n   📋 Risk Assessment:")
        print(f"      Critical edges (>{HEALING_CONFIG['failure_threshold']}): {len(critical)}")
        print(f"      At-risk edges  (>{HEALING_CONFIG['warning_threshold']}): {len(at_risk)}")

        if at_risk:
            print(f"\n      At-risk edges:")
            for u, v, score in at_risk[:5]:
                status = "🔴 CRITICAL" if score >= HEALING_CONFIG["failure_threshold"] else "🟠 WARNING"
                print(f"         {u} ↔ {v}: {score:.3f} {status}")

        # Step 2: Find the route BEFORE failure
        original_route = self.router.find_optimal_route(self.grid.graph, source, target)
        original_path = original_route["path"] if original_route else []

        # Step 3: Fail the worst edge on the active route (critical first)
        failure_pick = self.select_failure_edge(original_path)
        if failure_pick:
            fail_u, fail_v, fail_score = failure_pick
            failure_report = self.simulate_failure(fail_u, fail_v)

            # Step 4: Reroute
            reroute_result = self.reroute_after_failure(
                source,
                target,
                failed_edge=(fail_u, fail_v),
                original_path=original_path,
            )

            # Step 5: Restore edge for future use (demo only)
            self.grid.restore_edge(fail_u, fail_v)

            return {
                "critical_edges": critical,
                "at_risk_edges": at_risk,
                "failed_edge": (fail_u, fail_v, fail_score),
                "original_route": original_route,
                "failure_report": failure_report,
                "reroute_result": reroute_result,
                "healing_success": reroute_result["success"],
                "path_changed": reroute_result["path_changed"],
                "explanation": reroute_result["explanation"],
            }
        else:
            print("\n   ✅ No edges at risk. Grid is healthy!")
            return {
                "critical_edges": [],
                "at_risk_edges": [],
                "failed_edge": None,
                "original_route": original_route,
                "failure_report": None,
                "reroute_result": None,
                "healing_success": True,
            }

    @staticmethod
    def print_healing_summary(result: dict):
        """Print a formatted summary of the healing cycle."""
        print("\n" + "─" * 60)
        print("   📋 SELF-HEALING SUMMARY")
        print("─" * 60)

        if result["failed_edge"]:
            u, v, score = result["failed_edge"]
            print(f"   Failed Edge:    {u} ↔ {v} (congestion: {score:.3f})")
        else:
            print(f"   No failures detected — grid is healthy")
            return

        if result["failure_report"]:
            conn = result["failure_report"]["connectivity"]
            print(f"   Connected:      {'Yes ✅' if conn['is_connected'] else 'No ⚠️'}")
            print(f"   Components:     {conn['num_components']}")

        if result["reroute_result"]:
            rr = result["reroute_result"]
            print(f"   Reroute:        {'Success ✅' if rr['success'] else 'Failed ❌'}")
            if rr["new_route"]:
                print(f"   New Path:       {' → '.join(rr['new_route']['path'])}")
                print(f"   New Cost:       {rr['new_route']['total_cost']:.4f}")

        print(f"   Overall:        {'HEALED ✅' if result['healing_success'] else 'NEEDS ATTENTION ⚠️'}")
