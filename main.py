"""
Predictive Energy Routing — Main Orchestrator
===============================================
Entry point that runs the complete pipeline:
  1. Generate synthetic dataset
  2. Train ML congestion predictor
  3. Build power grid graph
  4. Update edge congestion with ML predictions
  5. Find optimal A* route
  6. Find naive Dijkstra route (comparison)
  7. Run self-healing cycle
  8. Generate visualization dashboard
  9. Print summary report
"""

import sys
import time

from config import OUTPUT_DIR
from data_generator import generate_dataset
from ml_predictor import CongestionPredictor
from grid_model import PowerGrid
from astar_router import EnergyRouter
from self_healing import SelfHealingSystem
from visualizer import generate_dashboard, generate_individual_panels


def print_banner():
    """Print the project banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ⚡ Predictive Energy Routing                               ║
║   🧠 Hybrid ML–A* Optimization                               ║
║                                                              ║
║   Smart Grid • Self-Healing • Intelligent Routing            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def run_pipeline():
    """Execute the full pipeline."""
    start_time = time.time()
    print_banner()

    # ───────────────────────────────────────────
    # Step 1: Generate Synthetic Dataset
    # ───────────────────────────────────────────
    print_section("STEP 1: Data Generation")
    df = generate_dataset()

    # ───────────────────────────────────────────
    # Step 2: Train ML Predictor
    # ───────────────────────────────────────────
    print_section("STEP 2: ML Model Training")
    predictor = CongestionPredictor()
    metrics = predictor.train(df)
    predictor.save_model()

    # ───────────────────────────────────────────
    # Step 3: Build Power Grid
    # ───────────────────────────────────────────
    print_section("STEP 3: Grid Construction")
    grid = PowerGrid()
    G = grid.build_grid()

    # ───────────────────────────────────────────
    # Step 4: Update Congestion with ML
    # ───────────────────────────────────────────
    print_section("STEP 4: ML Congestion Prediction")
    congestion_map = grid.update_congestion(predictor)

    # ───────────────────────────────────────────
    # Step 5: A* Optimal Routing
    # ───────────────────────────────────────────
    print_section("STEP 5: A* Optimal Routing")
    router = EnergyRouter()

    # Route from a generator to a distant consumer
    source = "G1"  # Solar Farm Alpha
    target = "C6"  # Tech Hub F

    print(f"\n   Source: {source} ({G.nodes[source].get('label', '')})")
    print(f"   Target: {target} ({G.nodes[target].get('label', '')})")

    ml_route = router.find_optimal_route(G, source, target)
    router.print_route(ml_route)

    # ───────────────────────────────────────────
    # Step 6: Naive Dijkstra (Comparison)
    # ───────────────────────────────────────────
    print_section("STEP 6: Naive Dijkstra Routing (Baseline)")
    naive_route = router.find_naive_route(G, source, target)
    router.print_route(naive_route)

    # Compare
    router.compare_routes(ml_route, naive_route)

    # ───────────────────────────────────────────
    # Step 7: Self-Healing Cycle
    # ───────────────────────────────────────────
    print_section("STEP 7: Self-Healing Mechanism")
    healer = SelfHealingSystem(grid, router)

    # Find the most congested edge and force a failure scenario
    # (In real-world, threshold-based detection would trigger this automatically)
    congestion_scores = [(u, v, d["congestion_score"])
                         for u, v, d in G.edges(data=True)]
    congestion_scores.sort(key=lambda x: x[2], reverse=True)
    most_congested = congestion_scores[0]

    print(f"\n   Simulating failure on most congested line: "
          f"{most_congested[0]} <-> {most_congested[1]} "
          f"(congestion: {most_congested[2]:.3f})")

    # Get route BEFORE failure
    original_route = router.find_optimal_route(G, source, target)

    # Simulate the failure
    fail_u, fail_v = most_congested[0], most_congested[1]
    failure_report = healer.simulate_failure(fail_u, fail_v)

    # DFS connectivity check
    connectivity = healer.dfs_connectivity_check()
    print(f"\n   DFS Connectivity Check:")
    print(f"      Connected: {'Yes' if connectivity['is_connected'] else 'No'}")
    print(f"      Components: {connectivity['num_components']}")

    # Reroute around the failure
    reroute_result = healer.reroute_after_failure(
        source, target, failed_edge=(fail_u, fail_v)
    )

    # Build the healing result dict for visualization
    healing_result = {
        "critical_edges": [(fail_u, fail_v, most_congested[2])],
        "at_risk_edges": congestion_scores[:5],
        "failed_edge": (fail_u, fail_v, most_congested[2]),
        "original_route": original_route,
        "failure_report": failure_report,
        "reroute_result": reroute_result,
        "healing_success": reroute_result["success"],
    }
    SelfHealingSystem.print_healing_summary(healing_result)

    # Restore the edge after demo (so visualization shows it as dashed)
    # Keep it failed for visualization, restore after
    grid.restore_edge(fail_u, fail_v)
    # Re-mark as failed just for visualization
    grid.remove_edge(fail_u, fail_v)

    # ───────────────────────────────────────────
    # Step 8: Visualization
    # ───────────────────────────────────────────
    print_section("STEP 8: Visualization Dashboard")
    feature_importances = predictor.get_feature_importances()

    dashboard_path = generate_dashboard(
        grid, ml_route, naive_route,
        feature_importances, healing_result
    )

    panel_paths = generate_individual_panels(
        grid, ml_route, naive_route,
        feature_importances, healing_result
    )

    # ───────────────────────────────────────────
    # Final Report
    # ───────────────────────────────────────────
    elapsed = time.time() - start_time
    print_section("FINAL REPORT")
    print(f"""
   📊 Dataset:           5,000 synthetic samples
   🤖 ML Model:          Random Forest (R² = {metrics['r2']:.4f})
   🔌 Grid:              {G.number_of_nodes()} nodes, {G.number_of_edges()} edges
   🗺️  A* Route:          {' → '.join(ml_route['path']) if ml_route else 'N/A'}
   📈 A* Cost:           {ml_route['total_cost']:.4f} (avg cong: {ml_route['avg_congestion']:.3f})
   📉 Dijkstra Cost:     {naive_route['total_cost']:.4f} (avg cong: {naive_route['avg_congestion']:.3f})
   🛡️  Self-Healing:      {'✅ Success' if healing_result['healing_success'] else '⚠️ Needs Attention'}
   🖼️  Output:            {OUTPUT_DIR}
   ⏱️  Total Time:        {elapsed:.2f}s
""")

    print("   ✅ Pipeline complete! Check the output/ folder for visualizations.")
    print(f"   📁 Dashboard: {dashboard_path}")

    return {
        "metrics": metrics,
        "ml_route": ml_route,
        "naive_route": naive_route,
        "healing_result": healing_result,
        "dashboard_path": dashboard_path,
    }


if __name__ == "__main__":
    try:
        results = run_pipeline()
    except KeyboardInterrupt:
        print("\n   ⚠️ Pipeline interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n   ❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
