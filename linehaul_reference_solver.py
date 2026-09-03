"""Exakter Referenzlöser (gemischt-ganzzahliges Programm, OR-Tools SCIP).

Für jede Sendung: binäre Auswahl genau einer Route (Direkt oder via Hub h).
Für jede Kandidatenlinie: ganzzahlige LKW-Anzahl, gekoppelt an die Kapazität
je Richtung. Für kleine Instanzen (siehe Größen-Guard in app.py) in <1s exakt
lösbar - Cross-Check-Referenz für die Heuristiken in linehaul_heuristics.py.
"""

from collections import defaultdict, namedtuple

from ortools.linear_solver import pywraplp

from linehaul_network import candidate_routes

SolveResult = namedtuple("SolveResult", ["feasible", "optimal", "route_choice", "objective", "wall_time_ms"])


def solve_exact(instance, time_limit_seconds=10):
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise RuntimeError("SCIP-Solver nicht verfügbar")
    solver.SetTimeLimit(int(time_limit_seconds * 1000))

    routes_by_commodity = candidate_routes(instance)
    commodity_by_index = {c.index: c for c in instance.commodities}

    z = {}
    for k, routes in routes_by_commodity.items():
        for r_idx in range(len(routes)):
            z[(k, r_idx)] = solver.BoolVar(f"z_{k}_{r_idx}")
        solver.Add(solver.Sum(z[(k, r_idx)] for r_idx in range(len(routes))) == 1)

    y = {}
    for line in instance.candidate_lines:
        key = (line.i, line.j)
        y[key] = solver.IntVar(0, solver.infinity(), f"y_{key[0]}_{key[1]}")

    forward_terms = defaultdict(list)
    backward_terms = defaultdict(list)
    for k, routes in routes_by_commodity.items():
        demand = commodity_by_index[k].demand
        for r_idx, route in enumerate(routes):
            for leg in route.legs:
                key = (leg.line_i, leg.line_j)
                term = demand * z[(k, r_idx)]
                if leg.forward:
                    forward_terms[key].append(term)
                else:
                    backward_terms[key].append(term)

    for line in instance.candidate_lines:
        key = (line.i, line.j)
        if forward_terms[key]:
            solver.Add(solver.Sum(forward_terms[key]) <= instance.truck_capacity * y[key])
        if backward_terms[key]:
            solver.Add(solver.Sum(backward_terms[key]) <= instance.truck_capacity * y[key])

    objective_terms = []
    for line in instance.candidate_lines:
        key = (line.i, line.j)
        objective_terms.append(line.fixed_cost * y[key])
    for k, routes in routes_by_commodity.items():
        demand = commodity_by_index[k].demand
        for r_idx, route in enumerate(routes):
            leg_cost = sum(
                instance.line_between(leg.line_i, leg.line_j).variable_cost_per_unit for leg in route.legs
            )
            var_cost = demand * leg_cost
            if route.hub is not None:
                var_cost += demand * instance.transshipment_cost_per_unit
            objective_terms.append(var_cost * z[(k, r_idx)])

    solver.Minimize(solver.Sum(objective_terms))
    status = solver.Solve()

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return SolveResult(feasible=False, optimal=False, route_choice=None, objective=None, wall_time_ms=solver.wall_time())

    route_choice = {}
    for k, routes in routes_by_commodity.items():
        for r_idx, route in enumerate(routes):
            if z[(k, r_idx)].solution_value() > 0.5:
                route_choice[k] = route
                break

    return SolveResult(
        feasible=True,
        optimal=(status == pywraplp.Solver.OPTIMAL),
        route_choice=route_choice,
        objective=solver.Objective().Value(),
        wall_time_ms=solver.wall_time(),
    )
