"""Kostenauswertung einer Routenwahl (route_choice: commodity_index -> Route)."""

from collections import defaultdict

from linehaul_network import trucks_needed


def evaluate_solution(instance, route_choice, label=""):
    forward_flow = defaultdict(float)
    backward_flow = defaultdict(float)
    transshipment_cost = 0.0
    variable_cost = 0.0
    hub_usage = defaultdict(float)
    commodity_by_index = {c.index: c for c in instance.commodities}

    for commodity_index, route in route_choice.items():
        commodity = commodity_by_index[commodity_index]
        for leg in route.legs:
            key = (leg.line_i, leg.line_j)
            if leg.forward:
                forward_flow[key] += commodity.demand
            else:
                backward_flow[key] += commodity.demand
            line = instance.line_between(leg.line_i, leg.line_j)
            variable_cost += commodity.demand * line.variable_cost_per_unit
        if route.hub is not None:
            transshipment_cost += commodity.demand * instance.transshipment_cost_per_unit
            hub_usage[route.hub] += commodity.demand

    trucks = {}
    fixed_cost = 0.0
    active_lines = []
    for line in instance.candidate_lines:
        key = (line.i, line.j)
        f = forward_flow.get(key, 0.0)
        b = backward_flow.get(key, 0.0)
        if f > 1e-9 or b > 1e-9:
            n_trucks = max(trucks_needed(f, instance.truck_capacity), trucks_needed(b, instance.truck_capacity))
            if n_trucks > 0:
                trucks[key] = n_trucks
                fixed_cost += n_trucks * line.fixed_cost
                active_lines.append(key)

    total_cost = fixed_cost + variable_cost + transshipment_cost
    n_transshipped = sum(1 for r in route_choice.values() if r.hub is not None)

    total_line_capacity = sum(trucks[k] * instance.truck_capacity for k in trucks)
    total_flow_on_lines = sum(forward_flow.get(k, 0.0) + backward_flow.get(k, 0.0) for k in trucks)
    utilization = (total_flow_on_lines / total_line_capacity) if total_line_capacity > 0 else 0.0

    return {
        "label": label,
        "route_choice": route_choice,
        "total_cost": total_cost,
        "fixed_cost": fixed_cost,
        "variable_cost": variable_cost,
        "transshipment_cost": transshipment_cost,
        "trucks": trucks,
        "active_lines": active_lines,
        "n_lines": len(active_lines),
        "n_trucks_total": sum(trucks.values()),
        "forward_flow": dict(forward_flow),
        "backward_flow": dict(backward_flow),
        "hub_usage": dict(hub_usage),
        "n_shipments_transshipped": n_transshipped,
        "n_shipments_total": len(route_choice),
        "utilization": utilization,
    }


def comparison_table(results):
    import pandas as pd

    rows = []
    for r in results:
        rows.append(
            {
                "Methode": r["label"],
                "Gesamtkosten (€)": round(r["total_cost"], 0),
                "Fixkosten Linien (€)": round(r["fixed_cost"], 0),
                "Variable Kosten (€)": round(r["variable_cost"], 0),
                "Umschlagkosten (€)": round(r["transshipment_cost"], 0),
                "Aktive Linien": r["n_lines"],
                "LKW gesamt": r["n_trucks_total"],
                "Sendungen mit Umschlag": f"{r['n_shipments_transshipped']}/{r['n_shipments_total']}",
                "Ø Auslastung": f"{r['utilization'] * 100:.0f}%",
            }
        )
    return pd.DataFrame(rows)
