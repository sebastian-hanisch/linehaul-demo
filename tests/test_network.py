import numpy as np

from linehaul_network import build_instance, candidate_routes, trucks_needed
from linehaul_scenario import generate_demand, generate_positions, pairwise_distances


def _random_instance(n_depots=6, seed=1, demand_density=0.5):
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


def test_commodities_match_nonzero_demand_pairs():
    n = 6
    positions = generate_positions(n, seed=3)
    demand = generate_demand(n, seed=3, demand_density=0.6, demand_scale=1.0)
    distances = pairwise_distances(positions)
    instance = build_instance(positions, demand, distances, 10, 5, 0.1, 30, 1.0)

    expected_pairs = {(i, j) for i in range(n) for j in range(i + 1, n) if demand[i, j] > 0}
    actual_pairs = {(min(c.origin, c.destination), max(c.origin, c.destination)) for c in instance.commodities}
    assert actual_pairs == expected_pairs


def test_candidate_lines_cover_all_pairs():
    instance = _random_instance(n_depots=5)
    n = instance.n_depots
    expected = {(i, j) for i in range(n) for j in range(i + 1, n)}
    actual = {(l.i, l.j) for l in instance.candidate_lines}
    assert actual == expected


def test_line_between_is_symmetric_lookup():
    instance = _random_instance(n_depots=5)
    line_a = instance.line_between(2, 4)
    line_b = instance.line_between(4, 2)
    assert line_a is line_b


def test_trucks_needed_edge_cases():
    assert trucks_needed(0, 40) == 0
    assert trucks_needed(40, 40) == 1
    assert trucks_needed(40.0001, 40) == 2
    assert trucks_needed(81, 40) == 3


def test_candidate_routes_include_direct_and_all_hubs():
    instance = _random_instance(n_depots=6)
    routes_by_commodity = candidate_routes(instance)
    for commodity in instance.commodities:
        routes = routes_by_commodity[commodity.index]
        assert routes[0].hub is None  # Direktroute zuerst
        hub_options = {r.hub for r in routes[1:]}
        expected_hubs = set(range(instance.n_depots)) - {commodity.origin, commodity.destination}
        assert hub_options == expected_hubs


def test_route_legs_connect_origin_to_destination():
    instance = _random_instance(n_depots=6)
    routes_by_commodity = candidate_routes(instance)
    for commodity in instance.commodities:
        for route in routes_by_commodity[commodity.index]:
            path = [commodity.origin]
            for leg in route.legs:
                next_node = leg.line_j if leg.forward else leg.line_i
                assert path[-1] in (leg.line_i, leg.line_j)
                path.append(next_node)
            assert path[0] == commodity.origin
            assert path[-1] == commodity.destination


def test_distances_are_symmetric_and_zero_on_diagonal():
    positions = generate_positions(7, seed=9)
    distances = pairwise_distances(positions)
    assert np.allclose(distances, distances.T)
    assert np.allclose(np.diag(distances), 0.0)
