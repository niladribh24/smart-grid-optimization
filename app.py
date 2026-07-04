"""
PowerGrid Web Application
===========================
Flask backend that runs the ML pipeline and serves an interactive
web frontend for visualizing the Predictive Energy Routing system.
"""

import json
import numpy as np
from flask import Flask, jsonify, request, send_from_directory

from data_generator import generate_dataset
from ml_predictor import CongestionPredictor
from grid_model import PowerGrid
from astar_router import EnergyRouter
from self_healing import SelfHealingSystem


app = Flask(__name__, static_folder="static", static_url_path="/static")

# ─────────────────────────────────────────────
# Global pipeline state (initialized on startup)
# ─────────────────────────────────────────────
pipeline_data = {}
simulation_tick = 0
reroute_count = 0


def run_pipeline():
    """Run the full pipeline and cache results."""
    global pipeline_data, simulation_tick, reroute_count
    simulation_tick = 0
    reroute_count = 0

    print("\n⚡ Running PowerGrid pipeline...")

    # Step 1: Generate data
    df = generate_dataset()

    # Step 2: Train ML
    predictor = CongestionPredictor()
    metrics = predictor.train(df)
    predictor.save_model()

    # Step 3: Build grid
    grid = PowerGrid()
    G = grid.build_grid()

    # Step 4: Update congestion
    grid.update_congestion(predictor)

    # Step 5: A* routing
    router = EnergyRouter()
    source, target = "G1", "C6"
    ml_route = router.find_optimal_route(G, source, target)
    router.print_route(ml_route)

    # Step 6: Dijkstra baseline
    naive_route = router.find_naive_route(G, source, target)
    router.print_route(naive_route)
    router.compare_routes(ml_route, naive_route)

    # Step 7: Self-healing demo
    healer = SelfHealingSystem(grid, router)
    congestion_scores = [(u, v, d["congestion_score"])
                         for u, v, d in G.edges(data=True)]
    congestion_scores.sort(key=lambda x: x[2], reverse=True)
    most_congested = congestion_scores[0]
    fail_u, fail_v = most_congested[0], most_congested[1]

    original_route = router.find_optimal_route(G, source, target)
    failure_report = healer.simulate_failure(fail_u, fail_v)
    connectivity = healer.dfs_connectivity_check()
    reroute_result = healer.reroute_after_failure(source, target, (fail_u, fail_v))

    healing_result = {
        "failed_edge": [fail_u, fail_v],
        "congestion_at_failure": float(most_congested[2]),
        "is_connected": connectivity["is_connected"],
        "num_components": connectivity["num_components"],
        "reroute_success": reroute_result["success"],
        "original_path": original_route["path"] if original_route else [],
        "new_path": reroute_result["new_route"]["path"] if reroute_result["new_route"] else [],
        "new_cost": float(reroute_result["new_route"]["total_cost"]) if reroute_result["new_route"] else 0,
    }

    # Restore edge
    grid.restore_edge(fail_u, fail_v)

    # Serialize graph
    nodes = []
    for node_id, data in G.nodes(data=True):
        pos = data.get("pos", (0, 0))
        nodes.append({
            "id": node_id,
            "type": data.get("node_type", "unknown"),
            "x": float(pos[0]),
            "y": float(pos[1]),
            "label": data.get("label", node_id),
        })

    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "congestion_score": float(data.get("congestion_score", 0)),
            "current_load": float(data.get("current_load", 0)),
            "transmission_loss": float(data.get("transmission_loss", 0)),
            "resistance": float(data.get("resistance", 0)),
            "edge_weight": float(router._edge_cost(u, v, data)),
            "length_km": float(data.get("length_km", 0)),
            "age": float(data.get("age", 0)),
            "health_status": data.get("health_status", "Healthy"),
            "capacity": float(data.get("capacity", 0)),
            "is_failed": data.get("is_failed", False),
        })

    # Sort edges by congestion for heatmap
    edges_sorted = sorted(edges, key=lambda e: e["congestion_score"], reverse=True)

    feature_importances = predictor.get_feature_importances()

    pipeline_data = {
        "grid": {"nodes": nodes, "edges": edges},
        "ml_metrics": {
            "r2": float(metrics["r2"]),
            "mse": float(metrics["mse"]),
            "rmse": float(metrics["rmse"]),
            "mae": float(metrics["mae"]),
            "train_samples": int(metrics["train_samples"]),
            "test_samples": int(metrics["test_samples"]),
        },
        "feature_importances": {k: float(v) for k, v in feature_importances.items()},
        "ml_route": {
            "path": ml_route["path"] if ml_route else [],
            "total_cost": float(ml_route["total_cost"]) if ml_route else 0,
            "physical_cost": float(ml_route["total_physical_cost"]) if ml_route else 0,
            "avg_congestion": float(ml_route["avg_congestion"]) if ml_route else 0,
            "num_hops": ml_route["num_hops"] if ml_route else 0,
            "edge_details": ml_route["edge_details"] if ml_route else [],
        },
        "naive_route": {
            "path": naive_route["path"] if naive_route else [],
            "total_cost": float(naive_route["total_cost"]) if naive_route else 0,
            "physical_cost": float(naive_route["total_physical_cost"]) if naive_route else 0,
            "avg_congestion": float(naive_route["avg_congestion"]) if naive_route else 0,
            "num_hops": naive_route["num_hops"] if naive_route else 0,
            "edge_details": naive_route["edge_details"] if naive_route else [],
        },
        "healing": healing_result,
        "edges_by_congestion": edges_sorted,
        "source": source,
        "target": target,
        "dashboard": build_dashboard(grid, router, source, target, ml_route),
    }

    # Store references for interactive use
    pipeline_data["_grid_obj"] = grid
    pipeline_data["_router_obj"] = router
    pipeline_data["_predictor_obj"] = predictor
    pipeline_data["_healer_obj"] = healer

    print("✅ Pipeline complete. Web server ready.")
    return pipeline_data


def serialize_edges(grid, router):
    """Return JSON-safe edge data for the current grid state."""
    edges = []
    for u, v, data in grid.graph.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "congestion_score": float(data.get("congestion_score", 0)),
            "current_load": float(data.get("current_load", 0)),
            "transmission_loss": float(data.get("transmission_loss", 0)),
            "resistance": float(data.get("resistance", 0)),
            "edge_weight": float(router._edge_cost(u, v, data)),
            "length_km": float(data.get("length_km", 0)),
            "age": float(data.get("age", 0)),
            "capacity": float(data.get("capacity", 0)),
            "health_status": data.get("health_status", "Healthy"),
            "is_failed": bool(data.get("is_failed", False)),
        })
    return edges


def build_dashboard(grid, router, source, target, route):
    """Compute dashboard KPIs from the live graph state."""
    edges = serialize_edges(grid, router)
    active_edges = [e for e in edges if not e["is_failed"]]
    failed_lines = [e for e in edges if e["is_failed"]]
    overloaded = [e for e in active_edges if e["congestion_score"] >= 0.85]
    return {
        "current_source": source,
        "destination": target,
        "total_transmission_loss": float(sum(e.get("transmission_loss", 0) for e in route.get("edge_details", []))) if route else 0.0,
        "total_route_cost": float(route["total_cost"]) if route else 0.0,
        "failed_lines": len(failed_lines),
        "reroutes": reroute_count,
        "average_congestion": float(np.mean([e["congestion_score"] for e in active_edges])) if active_edges else 0.0,
        "predicted_overloaded_lines": overloaded,
    }


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/pipeline")
def get_pipeline():
    """Return full pipeline results."""
    # Filter out non-serializable objects
    safe_data = {k: v for k, v in pipeline_data.items() if not k.startswith("_")}
    return jsonify(safe_data)


@app.route("/api/reroute", methods=["POST"])
def reroute():
    """Re-run A* with custom source/target."""
    global reroute_count
    data = request.get_json()
    source = data.get("source", "G1")
    target = data.get("target", "C6")

    grid = pipeline_data.get("_grid_obj")
    router = pipeline_data.get("_router_obj")

    if not grid or not router:
        return jsonify({"error": "Pipeline not initialized"}), 500

    G = grid.graph
    ml_route = router.find_optimal_route(G, source, target)
    naive_route = router.find_naive_route(G, source, target)
    reroute_count += 1

    result = {
        "source": source,
        "target": target,
        "ml_route": {
            "path": ml_route["path"] if ml_route else [],
            "total_cost": float(ml_route["total_cost"]) if ml_route else 0,
            "avg_congestion": float(ml_route["avg_congestion"]) if ml_route else 0,
            "num_hops": ml_route["num_hops"] if ml_route else 0,
            "edge_details": ml_route["edge_details"] if ml_route else [],
        } if ml_route else None,
        "naive_route": {
            "path": naive_route["path"] if naive_route else [],
            "total_cost": float(naive_route["total_cost"]) if naive_route else 0,
            "avg_congestion": float(naive_route["avg_congestion"]) if naive_route else 0,
            "num_hops": naive_route["num_hops"] if naive_route else 0,
        } if naive_route else None,
        "dashboard": build_dashboard(grid, router, source, target, ml_route),
    }
    return jsonify(result)


@app.route("/api/heal", methods=["POST"])
def heal():
    """Simulate failure on a specific edge and reroute."""
    global reroute_count
    data = request.get_json()
    fail_u = data.get("edge_u")
    fail_v = data.get("edge_v")
    source = data.get("source", "G1")
    target = data.get("target", "C6")

    grid = pipeline_data.get("_grid_obj")
    router = pipeline_data.get("_router_obj")
    healer = pipeline_data.get("_healer_obj")

    if not grid or not router:
        return jsonify({"error": "Pipeline not initialized"}), 500

    G = grid.graph

    # Get original route
    original_route = router.find_optimal_route(G, source, target)

    # Get congestion of failing edge
    cong = 0
    if G.has_edge(fail_u, fail_v):
        cong = G[fail_u][fail_v].get("congestion_score", 0)

    # Simulate failure
    grid.remove_edge(fail_u, fail_v)

    # DFS check
    healer_temp = SelfHealingSystem(grid, router)
    connectivity = healer_temp.dfs_connectivity_check()

    # Reroute
    reroute_result = healer_temp.reroute_after_failure(source, target, (fail_u, fail_v))
    reroute_count += 1

    # Restore
    grid.restore_edge(fail_u, fail_v)

    result = {
        "failed_edge": [fail_u, fail_v],
        "congestion_at_failure": float(cong),
        "is_connected": connectivity["is_connected"],
        "num_components": connectivity["num_components"],
        "reroute_success": reroute_result["success"],
        "original_path": original_route["path"] if original_route else [],
        "new_path": reroute_result["new_route"]["path"] if reroute_result["new_route"] else [],
        "new_cost": float(reroute_result["new_route"]["total_cost"]) if reroute_result["new_route"] else 0,
        "dashboard": build_dashboard(grid, router, source, target, reroute_result["new_route"]),
    }
    return jsonify(result)


@app.route("/api/simulate", methods=["POST"])
def simulate_tick():
    """Advance simulation: change loads, update ML predictions, heal if needed, reroute."""
    global simulation_tick, reroute_count

    data = request.get_json(silent=True) or {}
    source = data.get("source", pipeline_data.get("source", "G1"))
    target = data.get("target", pipeline_data.get("target", "C6"))

    grid = pipeline_data.get("_grid_obj")
    router = pipeline_data.get("_router_obj")
    predictor = pipeline_data.get("_predictor_obj")

    if not grid or not router or not predictor:
        return jsonify({"error": "Pipeline not initialized"}), 500

    simulation_tick += 1
    grid.randomize_loads(hour=simulation_tick % 24)
    grid.update_congestion(predictor)

    healer = SelfHealingSystem(grid, router)
    failed_this_tick = []
    for u, v, score in healer.detect_critical_edges():
        grid.remove_edge(u, v)
        failed_this_tick.append({"source": u, "target": v, "congestion_score": float(score)})

    connectivity = healer.dfs_connectivity_check()
    route = router.find_optimal_route(grid.graph, source, target)
    if failed_this_tick:
        reroute_count += 1

    edges = serialize_edges(grid, router)
    return jsonify({
        "tick": simulation_tick,
        "source": source,
        "target": target,
        "grid": {"edges": edges},
        "failed_this_tick": failed_this_tick,
        "connectivity": connectivity,
        "route": {
            "path": route["path"] if route else [],
            "total_cost": float(route["total_cost"]) if route else 0.0,
            "avg_congestion": float(route["avg_congestion"]) if route else 0.0,
            "num_hops": route["num_hops"] if route else 0,
            "edge_details": route["edge_details"] if route else [],
        } if route else None,
        "destination_isolated": route is None,
        "dashboard": build_dashboard(grid, router, source, target, route),
        "edges_by_congestion": sorted(edges, key=lambda e: e["congestion_score"], reverse=True),
    })


# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────

if __name__ == "__main__":
    run_pipeline()
    print("\n🌐 Starting web server at http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
