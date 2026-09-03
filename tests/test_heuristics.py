from linehaul_evaluation import evaluate_solution
from linehaul_heuristics import (
    all_direct_construction,
    greedy_construction,
    hub_and_spoke_construction,
    marginal_cost_construction,
)
from linehaul_network import build_instance
from linehaul_scenario import generate_demand, generate_positions, pairwise_distances


def _random_instance(n_depots, seed, demand_density=0.5, fixed_cost_per_km=10.0, transshipment_cost_per_unit=1.5):
    positions = generate_positions(n_depots, seed)
    demand = generate_demand(n_depots, seed, demand_density, demand_scale=1.0)
    distances = pairwise_distances(positions)
    return build_instance(
        positions=positions,
        demand_matrix=demand,
        distances=distances,
        fixed_cost_base=20.0,
        fixed_cost_per_km=fixed_cost_per_km,
        variable_cost_per_km=0.1,
        truck_capacity=40.0,
        transshipment_cost_per_unit=transshipment_cost_per_unit,
    )


INSTANCE_PARAMS = [
    (4, 1), (5, 2), (6, 3), (6, 7), (7, 11), (8, 42), (5, 99), (6, 2026),
]


def test_all_direct_never_transships():
    for n, seed in INSTANCE_PARAMS:
        instance = _random_instance(n, seed)
        route_choice = all_direct_construction(instance)
        assert all(r.hub is None for r in route_choice.values())
        assert set(route_choice.keys()) == {c.index for c in instance.commodities}


def test_hub_and_spoke_uses_at_most_one_hub_value():
    for n, seed in INSTANCE_PARAMS:
        if n < 3:
            continue
        instance = _random_instance(n, seed)
        route_choice = hub_and_spoke_construction(instance)
        hubs_used = {r.hub for r in route_choice.values() if r.hub is not None}
        assert len(hubs_used) <= 1


def test_hub_and_spoke_picks_the_cheapest_of_all_single_hub_configurations():
    # hub_and_spoke_construction ist eine Best-of-n-Suche über alle möglichen
    # Einzel-Hubs - kein Nie-schlechter-Anspruch ggü. all_direct (ein erzwungener
    # Umweg über EINEN Hub kann bei ungünstiger Geometrie teurer sein als lauter
    # Direktlinien), aber die Suche selbst muss nachweislich das Minimum finden.
    from linehaul_evaluation import evaluate_solution as _eval
    from linehaul_heuristics import _hub_route_choice
    from linehaul_network import candidate_routes

    for n, seed in INSTANCE_PARAMS:
        if n < 3:
            continue
        instance = _random_instance(n, seed)
        routes_by_commodity = candidate_routes(instance)
        best_manual = min(
            _eval(instance, _hub_route_choice(instance, routes_by_commodity, hub))["total_cost"]
            for hub in range(instance.n_depots)
        )
        hub_cost = evaluate_solution(instance, hub_and_spoke_construction(instance))["total_cost"]
        assert abs(hub_cost - best_manual) < 1e-6


def test_greedy_never_worse_than_either_starting_point():
    for n, seed in INSTANCE_PARAMS:
        instance = _random_instance(n, seed)
        direct_cost = evaluate_solution(instance, all_direct_construction(instance))["total_cost"]
        hub_cost = evaluate_solution(instance, hub_and_spoke_construction(instance))["total_cost"]
        greedy_cost = evaluate_solution(instance, greedy_construction(instance))["total_cost"]
        assert greedy_cost <= min(direct_cost, hub_cost) + 1e-6


def test_greedy_finds_known_hand_computed_improvement():
    # Siehe README/Kipppunkt-Abschnitt: 3 Depots kolinear, hohe Fixkosten je Linie
    # machen Bündelung über einen bereits ausgelasteten Hub lohnenswert.
    positions = generate_positions(3, seed=1)
    positions[0] = [0, 0]
    positions[1] = [10, 0]
    positions[2] = [20, 0]
    demand = generate_demand(3, seed=1, demand_density=0, demand_scale=1.0)
    demand[:] = 0
    demand[0, 2] = demand[2, 0] = 5
    demand[1, 2] = demand[2, 1] = 50
    distances = pairwise_distances(positions)
    instance = build_instance(
        positions=positions,
        demand_matrix=demand,
        distances=distances,
        fixed_cost_base=0.0,
        fixed_cost_per_km=10.0,
        variable_cost_per_km=0.1,
        truck_capacity=60.0,
        transshipment_cost_per_unit=1.0,
    )

    direct_cost = evaluate_solution(instance, all_direct_construction(instance))["total_cost"]
    hub_result = hub_and_spoke_construction(instance)
    hub_cost = evaluate_solution(instance, hub_result)["total_cost"]

    assert abs(direct_cost - 360.0) < 1e-6
    assert abs(hub_cost - 265.0) < 1e-6
    assert hub_cost < direct_cost


def test_greedy_benefits_from_exploring_every_hub_as_starting_point():
    # Regressionstest fuer den Fund, dass eine lokale Verbesserungssuche nur vom BESTEN
    # Einzel-Hub aus gelegentlich in einem schlechteren lokalen Optimum haengen bleibt als
    # dieselbe Suche von einem zunaechst suboptimalen Hub aus - siehe README-Kipppunkt.
    from linehaul_heuristics import _hub_route_choice, _local_search
    from linehaul_network import candidate_routes

    instance = _random_instance(7, seed=2, fixed_cost_per_km=15.0)
    routes_by_commodity = candidate_routes(instance)

    best_hub_start = hub_and_spoke_construction(instance)
    local_search_from_best_hub_only = evaluate_solution(
        instance, _local_search(instance, routes_by_commodity, best_hub_start)
    )["total_cost"]

    full_greedy_cost = evaluate_solution(instance, greedy_construction(instance))["total_cost"]

    assert full_greedy_cost < local_search_from_best_hub_only - 1e-6


def test_greedy_benefits_from_marginal_cost_construction_as_starting_point():
    # Regressionstest fuer den Fund, dass eine sequenzielle Grenzkosten-Konstruktion
    # (First-Fit-Decreasing-artig: Sendungen nach Nachfrage sortiert, je Sendung die
    # Route mit den geringsten Grenzkosten unter Wiederverwendung bereits eroeffneter
    # Linien) eine Luecke schliesst, die weder "Alles direkt" noch die Hub-Startpunkte
    # als lokale Verbesserungssuche finden - siehe README-Kipppunkt.
    from linehaul_heuristics import _local_search
    from linehaul_network import candidate_routes

    instance = _random_instance(7, seed=1, fixed_cost_per_km=15.0)
    routes_by_commodity = candidate_routes(instance)

    starts_without_marginal_cost = [all_direct_construction(instance), hub_and_spoke_construction(instance)]
    best_without = min(
        evaluate_solution(instance, _local_search(instance, routes_by_commodity, start))["total_cost"]
        for start in starts_without_marginal_cost
    )

    full_greedy_cost = evaluate_solution(instance, greedy_construction(instance))["total_cost"]

    assert full_greedy_cost < best_without - 1e-6


def test_marginal_cost_construction_covers_every_commodity_exactly_once():
    for n, seed in INSTANCE_PARAMS:
        instance = _random_instance(n, seed)
        for descending in (True, False):
            route_choice = marginal_cost_construction(instance, descending=descending)
            assert set(route_choice.keys()) == {c.index for c in instance.commodities}


def test_marginal_cost_construction_order_can_change_the_result():
    # Reihenfolgeabhaengigkeit ist beabsichtigt (wie First-Fit-Decreasing beim Bin
    # Packing) - deshalb testet greedy_construction beide Reihenfolgen als Startpunkt.
    found_a_difference = False
    for n, seed in INSTANCE_PARAMS:
        instance = _random_instance(n, seed, fixed_cost_per_km=15.0)
        desc_cost = evaluate_solution(instance, marginal_cost_construction(instance, descending=True))["total_cost"]
        asc_cost = evaluate_solution(instance, marginal_cost_construction(instance, descending=False))["total_cost"]
        if abs(desc_cost - asc_cost) > 1e-6:
            found_a_difference = True
    assert found_a_difference


def test_pairwise_swap_delta_matches_full_recomputation():
    # Der paarweise Politur-Schritt berechnet Kostenaenderungen inkrementell (nur die
    # betroffenen Linien), um bei vielen Sendungen schnell genug zu bleiben - Korrektheit
    # gegen eine vollstaendige Neubewertung auf zufaelligen Kandidaten-Paaren geprueft.
    import random

    from linehaul_heuristics import _build_flow_state, _pair_swap_delta
    from linehaul_network import candidate_routes

    rng = random.Random(0)
    checks = 0
    for n, seed in INSTANCE_PARAMS:
        instance = _random_instance(n, seed, fixed_cost_per_km=15.0)
        routes_by_commodity = candidate_routes(instance)
        route_choice = greedy_construction(instance)
        commodity_by_index = {c.index: c for c in instance.commodities}
        commodities = list(instance.commodities)
        if len(commodities) < 2:
            continue
        forward_flow, backward_flow = _build_flow_state(instance, route_choice)

        for _ in range(10):
            a, b = rng.sample(range(len(commodities)), 2)
            ka, kb = commodities[a].index, commodities[b].index
            ca, cb = commodity_by_index[ka], commodity_by_index[kb]
            ra_old, rb_old = route_choice[ka], route_choice[kb]
            ra_new = rng.choice(routes_by_commodity[ka])
            rb_new = rng.choice(routes_by_commodity[kb])

            delta_incremental, _, _ = _pair_swap_delta(
                instance, forward_flow, backward_flow, ca, ra_old, ra_new, cb, rb_old, rb_new
            )

            base_cost = evaluate_solution(instance, route_choice)["total_cost"]
            trial = dict(route_choice)
            trial[ka] = ra_new
            trial[kb] = rb_new
            trial_cost = evaluate_solution(instance, trial)["total_cost"]

            assert abs(delta_incremental - (trial_cost - base_cost)) < 1e-6
            checks += 1
    assert checks > 20


def test_pairwise_local_search_never_worsens_the_input():
    from linehaul_heuristics import _pairwise_local_search
    from linehaul_network import candidate_routes

    for n, seed in INSTANCE_PARAMS:
        instance = _random_instance(n, seed, fixed_cost_per_km=15.0)
        routes_by_commodity = candidate_routes(instance)
        start = hub_and_spoke_construction(instance)
        start_cost = evaluate_solution(instance, start)["total_cost"]
        polished = _pairwise_local_search(instance, routes_by_commodity, start)
        polished_cost = evaluate_solution(instance, polished)["total_cost"]
        assert polished_cost <= start_cost + 1e-6


def test_greedy_benefits_from_pairwise_swap_polish():
    # Regressionstest fuer den Fund, dass Koordinatenabstieg ueber EINZELNE Sendungen
    # Faelle uebersieht, in denen erst die GEMEINSAME Umroutung zweier Sendungen eine
    # LKW-Kapazitaetsschwelle ueber- oder unterschreitet - siehe README-Kipppunkt.
    from linehaul_heuristics import _local_search, _pairwise_local_search
    from linehaul_network import candidate_routes

    instance = _random_instance(7, seed=7, fixed_cost_per_km=15.0)
    routes_by_commodity = candidate_routes(instance)

    starting_points = [all_direct_construction(instance)]
    for hub in range(instance.n_depots):
        from linehaul_heuristics import _hub_route_choice

        starting_points.append(_hub_route_choice(instance, routes_by_commodity, hub))
    best_without_pairwise = min(
        evaluate_solution(instance, _local_search(instance, routes_by_commodity, start))["total_cost"]
        for start in starting_points
    )

    full_greedy_cost = evaluate_solution(instance, greedy_construction(instance))["total_cost"]

    assert full_greedy_cost < best_without_pairwise - 1e-6


def test_route_choice_covers_every_commodity_exactly_once():
    for n, seed in INSTANCE_PARAMS:
        instance = _random_instance(n, seed)
        for construction in (all_direct_construction, hub_and_spoke_construction, greedy_construction):
            route_choice = construction(instance)
            assert set(route_choice.keys()) == {c.index for c in instance.commodities}


def test_greedy_construction_worst_case_completes_within_budget():
    # Obergrenze des Depot-Reglers (9) UND der Nachfragedichte (1.0) gleichzeitig -
    # der teuerste Fall fuer den paarweisen Politur-Schritt (quadratisch in der
    # Sendungsanzahl). Gemessener Worst Case ~1.8s, Budget grosszuegig auf 4s gesetzt.
    import time

    for seed in range(1, 4):
        instance = _random_instance(9, seed, demand_density=1.0, fixed_cost_per_km=15.0)
        start = time.time()
        greedy_construction(instance)
        assert time.time() - start < 4.0
