"""
PowerGrid Web Application
===========================
Flask backend that runs the ML pipeline and serves an interactive
web frontend for visualizing the Predictive Energy Routing system.
"""

import json
import logging
import numpy as np
from flask import Flask, jsonify, request, send_from_directory

from data_generator import generate_dataset
from ml_predictor import CongestionPredictor
from grid_model import PowerGrid
from astar_router import EnergyRouter
from self_healing import SelfHealingSystem
from weather_api import weather_client


app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# ─────────────────────────────────────────────
# Global pipeline state (initialized on startup)
# ─────────────────────────────────────────────
pipeline_data = {
    "source": "G1",
    "target": "C6",
    "live_city": "New York",
    "live_weather": None
}
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
    healing_cycle = healer.full_healing_cycle(source, target)

    rr = healing_cycle.get("reroute_result") or {}
    new_route = rr.get("new_route")
    original_route = healing_cycle.get("original_route")
    failed = healing_cycle.get("failed_edge")

    healing_result = {
        "failed_edge": [failed[0], failed[1]] if failed else [],
        "congestion_at_failure": float(failed[2]) if failed else 0.0,
        "is_connected": healing_cycle.get("failure_report", {}).get("connectivity", {}).get("is_connected", True),
        "num_components": healing_cycle.get("failure_report", {}).get("connectivity", {}).get("num_components", 1),
        "reroute_success": rr.get("success", False),
        "path_changed": rr.get("path_changed", False),
        "destination_isolated": rr.get("destination_isolated", False),
        "explanation": rr.get("explanation", ""),
        "original_path": original_route["path"] if original_route else [],
        "new_path": new_route["path"] if new_route else [],
        "new_cost": float(new_route["total_cost"]) if new_route else 0,
    }

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

    edges = serialize_edges(grid, router)

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
        weight = router._edge_cost(u, v, data)
        if weight == float('inf'):
            weight = 999999.0
        edges.append({
            "source": u,
            "target": v,
            "congestion_score": float(data.get("congestion_score", 0)),
            "current_load": float(data.get("current_load", 0)),
            "transmission_loss": float(data.get("transmission_loss", 0)),
            "resistance": float(data.get("resistance", 0)),
            "edge_weight": float(weight),
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
    """Simulate failure on a route-aware edge and reroute."""
    global reroute_count
    data = request.get_json() or {}
    fail_u = data.get("edge_u")
    fail_v = data.get("edge_v")
    source = data.get("source", "G1")
    target = data.get("target", "C6")
    persist = bool(data.get("persist", False))

    grid = pipeline_data.get("_grid_obj")
    router = pipeline_data.get("_router_obj")
    healer = pipeline_data.get("_healer_obj")

    if not grid or not router:
        return jsonify({"error": "Pipeline not initialized"}), 500

    if not healer:
        healer = SelfHealingSystem(grid, router)

    original_route = router.find_optimal_route(grid.graph, source, target)
    original_path = original_route["path"] if original_route else []

    if fail_u and fail_v:
        cong = grid.graph[fail_u][fail_v].get("congestion_score", 0) if grid.graph.has_edge(fail_u, fail_v) else 0
        failure_report = healer.simulate_failure(fail_u, fail_v)
    else:
        pick = healer.select_failure_edge(original_path)
        if not pick:
            return jsonify({"error": "No congested edges available to heal"}), 400
        fail_u, fail_v, cong = pick
        failure_report = healer.simulate_failure(fail_u, fail_v)

    connectivity = healer.dfs_connectivity_check()
    reroute_result = healer.reroute_after_failure(
        source, target, (fail_u, fail_v), original_path=original_path
    )
    reroute_count += 1

    if not persist:
        grid.restore_edge(fail_u, fail_v)

    new_route = reroute_result.get("new_route")
    result = {
        "failed_edge": [fail_u, fail_v],
        "congestion_at_failure": float(cong),
        "is_connected": connectivity["is_connected"],
        "num_components": connectivity["num_components"],
        "reroute_success": reroute_result["success"],
        "path_changed": reroute_result["path_changed"],
        "destination_isolated": reroute_result["destination_isolated"],
        "explanation": reroute_result["explanation"],
        "original_path": original_path,
        "new_path": new_route["path"] if new_route else [],
        "new_cost": float(new_route["total_cost"]) if new_route else 0,
        "persisted_failure": persist,
        "grid": {"edges": serialize_edges(grid, router)},
        "dashboard": build_dashboard(grid, router, source, target, new_route),
    }
    return jsonify(result)


@app.route("/api/toggle_edge", methods=["POST"])
def toggle_edge():
    """Manually fail or repair a specific edge in the grid graph."""
    global reroute_count
    data = request.get_json()
    u = data.get("edge_u")
    v = data.get("edge_v")
    action = data.get("action")  # "fail" or "restore"
    source = data.get("source", "G1")
    target = data.get("target", "C6")

    grid = pipeline_data.get("_grid_obj")
    router = pipeline_data.get("_router_obj")

    if not grid or not router:
        return jsonify({"error": "Pipeline not initialized"}), 500

    original_route = router.find_optimal_route(grid.graph, source, target)
    original_path = original_route["path"] if original_route else []

    if action == "fail":
        grid.remove_edge(u, v)
        status = "failed"
    else:
        grid.restore_edge(u, v)
        status = "restored"

    healer_temp = SelfHealingSystem(grid, router)
    connectivity = healer_temp.dfs_connectivity_check()

    if status == "failed":
        reroute_result = healer_temp.reroute_after_failure(
            source, target, (u, v), original_path=original_path
        )
        route = reroute_result.get("new_route")
        reroute_count += 1
    else:
        route = router.find_optimal_route(grid.graph, source, target)
        reroute_result = None

    edges = serialize_edges(grid, router)
    return jsonify({
        "status": status,
        "grid": {"edges": edges},
        "connectivity": connectivity,
        "route": {
            "path": route["path"] if route else [],
            "total_cost": float(route["total_cost"]) if route else 0.0,
            "avg_congestion": float(route["avg_congestion"]) if route else 0.0,
            "num_hops": route["num_hops"] if route else 0,
            "edge_details": route["edge_details"] if route else [],
        } if route else None,
        "destination_isolated": route is None,
        "path_changed": reroute_result["path_changed"] if reroute_result else False,
        "explanation": reroute_result["explanation"] if reroute_result else "",
        "dashboard": build_dashboard(grid, router, source, target, route),
        "edges_by_congestion": sorted(edges, key=lambda e: e["congestion_score"], reverse=True),
    })


@app.route("/api/weather", methods=["GET", "POST"])
def get_weather():
    global pipeline_data
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        city = data.get("city", "New York")
        pipeline_data["live_city"] = city
        
    city = pipeline_data.get("live_city", "New York")
    weather_data = weather_client.get_weather(city)
    
    if "error" not in weather_data:
        pipeline_data["live_weather"] = weather_data
        pipeline_data["live_city"] = weather_data.get("city", city)
        
    return jsonify(weather_data)

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
    scenario = data.get("scenario", "normal")
    
    # Pass live weather to grid if scenario is live
    live_weather_data = None
    if scenario == "live":
        live_weather_data = pipeline_data.get("live_weather")
        
    grid.randomize_loads(hour=simulation_tick % 24, scenario=scenario, live_weather_data=live_weather_data)
    grid.update_congestion(predictor)

    healer = SelfHealingSystem(grid, router)
    healing = healer.process_congestion_failures(source, target)
    failed_this_tick = healing["failed_edges"]
    connectivity = healing["connectivity"]
    reroute_result = healing["reroute_result"]
    route = reroute_result.get("new_route")

    if failed_this_tick and route:
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
        "destination_isolated": healing["destination_isolated"],
        "path_changed": healing["path_changed"],
        "explanation": healing["explanation"],
        "original_path": healing["original_path"],
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
