"""Command-line simulation for the self-healing smart grid."""

from __future__ import annotations

from data_generator import generate_dataset
from grid_model import PowerGrid
from ml_predictor import CongestionPredictor
from astar_router import EnergyRouter
from self_healing import SelfHealingSystem


def main(ticks: int = 5, source: str = "G1", target: str = "C6") -> None:
    dataset = generate_dataset(save=True)
    predictor = CongestionPredictor()
    predictor.train(dataset)

    grid = PowerGrid()
    graph = grid.build_grid()
    router = EnergyRouter()

    reroutes = 0
    for tick in range(1, ticks + 1):
        grid.randomize_loads(hour=tick % 24)
        grid.update_congestion(predictor)
        healer = SelfHealingSystem(grid, router)

        failed = []
        for u, v, score in healer.detect_critical_edges():
            grid.remove_edge(u, v)
            failed.append((u, v, score))

        route = router.find_optimal_route(graph, source, target)
        if failed:
            reroutes += 1

        if route:
            print(
                f"tick={tick} path={' -> '.join(route['path'])} "
                f"cost={route['total_cost']:.4f} failed={len(failed)} reroutes={reroutes}"
            )
        else:
            print(f"tick={tick} destination {target} is isolated failed={len(failed)}")


if __name__ == "__main__":
    main()
