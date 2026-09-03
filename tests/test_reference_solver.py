from linehaul_evaluation import evaluate_solution
from linehaul_heuristics import all_direct_construction, greedy_construction, hub_and_spoke_construction
from linehaul_network import build_instance
from linehaul_reference_solver import solve_exact
from linehaul_scenario import generate_demand, generate_positions, pairwise_distances


def _random_instance(n_depots, seed, demand_density=0.5):
    positions = generate_positions(n_depots, seed)
    demand = generate_demand(n_depots, seed, demand_density, demand_scale=1.0)
    distances = pairwise_distances(positions)
    return build_instance(
        positions=positions,
        demand_matrix=demand,
        distances=distances,
        fixed_cost_base=20.0,
        fixed_cost_per_km=10.0,
        variable_cost_per_km=0.1,
        truck_capacity=40.0,
        transshipment_cost_per_unit=1.5,
    )


SMALL_INSTANCE_PARAMS = [
    (3, 1), (4, 2), (4, 7), (5, 3), (5, 42), (6, 11), (6, 99), (7, 2026),
]


def _tiny_hand_computed_instance():
    positions = generate_positions(3, seed=1)
    positions[0] = [0, 0]
    positions[1] = [10, 0]
    positions[2] = [20, 0]
    demand = generate_demand(3, seed=1, demand_density=0, demand_scale=1.0)
    demand[:] = 0
    demand[0, 2] = demand[2, 0] = 5
    demand[1, 2] = demand[2, 1] = 50
    distances = pairwise_distances(positions)
    return build_instance(
        positions=positions,
        demand_matrix=demand,
        distances=distances,
        fixed_cost_base=0.0,
        fixed_cost_per_km=10.0,
        variable_cost_per_km=0.1,
        truck_capacity=60.0,
        transshipment_cost_per_unit=1.0,
    )


def test_exact_solver_matches_hand_computed_tiny_instance():
    instance = _tiny_hand_computed_instance()
    result = solve_exact(instance)
    assert result.feasible
    assert result.optimal
    assert abs(result.objective - 265.0) < 1e-4

    # Der erwartete optimale Plan: Sendung 1->2 direkt, Sendung 0->2 über Hub 1
    # (Bündelung auf der ohnehin gebauten Linie 1-2, siehe README-Kipppunkt).
    commodity_by_pair = {(c.origin, c.destination): c.index for c in instance.commodities}
    route_a = result.route_choice[commodity_by_pair[(0, 2)]]
    route_b = result.route_choice[commodity_by_pair[(1, 2)]]
    assert route_a.hub == 1
    assert route_b.hub is None


def test_heuristics_never_beat_the_exact_optimum():
    for n, seed in SMALL_INSTANCE_PARAMS:
        instance = _random_instance(n, seed)
        result = solve_exact(instance)
        assert result.feasible, f"MIP nicht loesbar bei n={n}, seed={seed}"

        for construction in (all_direct_construction, hub_and_spoke_construction, greedy_construction):
            heuristic_cost = evaluate_solution(instance, construction(instance))["total_cost"]
            assert heuristic_cost >= result.objective - 1e-4, (
                f"{construction.__name__} unterbietet das Optimum bei n={n}, seed={seed}: "
                f"{heuristic_cost} < {result.objective}"
            )


def test_greedy_matches_or_nearly_matches_optimum_on_small_instances():
    gaps = []
    for n, seed in SMALL_INSTANCE_PARAMS:
        instance = _random_instance(n, seed)
        result = solve_exact(instance)
        greedy_cost = evaluate_solution(instance, greedy_construction(instance))["total_cost"]
        gap_pct = (greedy_cost - result.objective) / result.objective * 100 if result.objective > 0 else 0.0
        gaps.append(gap_pct)
        assert gap_pct < 10.0, f"Greedy-Lücke zu groß bei n={n}, seed={seed}: {gap_pct:.1f}%"
    assert sum(gaps) / len(gaps) < 3.0


def test_exact_solve_respects_its_time_budget_at_worst_case_ui_settings():
    # Regressionstest fuer den Fund, dass der exakte Loeser bei 9 Depots UND hoher
    # Nachfragedichte (beides innerhalb der Reglergrenzen) bis zu 20s brauchte, ohne
    # das Optimum zu beweisen - ein 15s-Zeitlimit liess die App entsprechend haengen.
    # C.EXACT_SOLVE_TIME_LIMIT_SECONDS (app.py) wurde auf 4s reduziert; hier direkt am
    # Loeser geprueft, mit grosszuegigem Sicherheitsabstand fuer OR-Tools' eigenen
    # Zeitlimit-Overhead (siehe README: gemessener Overhead ~0.0-0.1s).
    import time

    for seed in range(1, 4):
        instance = _random_instance(9, seed, demand_density=1.0)
        start = time.time()
        result = solve_exact(instance, time_limit_seconds=4)
        elapsed = time.time() - start
        assert result.feasible
        assert elapsed < 6.0, f"solve_exact ueberschreitet sein Zeitbudget deutlich: {elapsed:.1f}s bei seed={seed}"
