"""
Self-Healing Mechanism
=======================
Detects failing transmission lines, verifies network connectivity using DFS,
and triggers A* rerouting to prevent blackouts.
"""

import networkx as nx

from config import HEALING_CONFIG, CONGESTION_THRESHOLDS


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
                              failed_edge: tuple = None) -> dict:
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

        Returns
        -------
        dict
            Rerouting result with old and new paths.
        """
        print(f"\n   🔄 Rerouting energy from {source} to {target}...")

        # Find new route on the active graph
        active_graph = self.grid.get_active_graph()
        new_route = self.router.find_optimal_route(active_graph, source, target)

        if new_route:
            print(f"      ✅ Alternate route found: {' → '.join(new_route['path'])}")
            print(f"      📊 New route cost: {new_route['total_cost']:.4f}")
        else:
            print(f"      ❌ No alternate route available!")

        reroute_result = {
            "source": source,
            "target": target,
            "failed_edge": failed_edge,
            "new_route": new_route,
            "success": new_route is not None,
        }

        self.reroute_log.append(reroute_result)
        return reroute_result

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

        # Step 3: Simulate failure of the most congested edge
        if at_risk:
            fail_u, fail_v, fail_score = at_risk[0]
            failure_report = self.simulate_failure(fail_u, fail_v)

            # Step 4: Reroute
            reroute_result = self.reroute_after_failure(
                source, target, failed_edge=(fail_u, fail_v)
            )

            # Step 5: Restore edge for future use
            self.grid.restore_edge(fail_u, fail_v)

            return {
                "critical_edges": critical,
                "at_risk_edges": at_risk,
                "failed_edge": (fail_u, fail_v, fail_score),
                "original_route": original_route,
                "failure_report": failure_report,
                "reroute_result": reroute_result,
                "healing_success": reroute_result["success"],
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
