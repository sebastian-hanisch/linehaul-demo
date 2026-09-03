"""Heuristiken für das Hauptlauf-Netzwerkdesign.

- all_direct_construction: jede Sendung fährt direkt (Baseline, kein
  Konsolidierungsgedanke).
- hub_and_spoke_construction: alle Sendungen (die nicht ohnehin einen Hub als
  Start/Ziel haben) laufen über einen einzelnen, best gewählten Hub.
- marginal_cost_construction: sequenzielle Konstruktion (analog First-Fit-
  Decreasing beim Bin Packing) - verarbeitet Sendungen in absteigender (oder
  aufsteigender) Nachfragereihenfolge, wählt je Sendung die Route mit den
  geringsten GRENZKOSTEN unter Wiederverwendung bereits eröffneter Linien
  (ein zusätzlicher LKW kostet nur, wenn die bestehende Kapazität nicht
  reicht). Reihenfolgeabhängig, wie FFD beim Packen - deshalb zwei Varianten
  (auf-/absteigend).
- greedy_construction: lokale Verbesserungssuche (Koordinatenabstieg über
  einzelne Sendungen), gestartet von all_direct, JEDEM einzelnen möglichen
  Hub (nicht nur dem besten) UND beiden marginal_cost_construction-Varianten
  - das jeweils beste Endergebnis gewinnt. Dadurch gilt garantiert
  greedy_cost <= min(all_direct_cost, hub_and_spoke_cost). Anschließend ein
  Politur-Schritt mit paarweisen Sendungs-Tauschzügen (siehe
  `_pairwise_local_search` unten) - Koordinatenabstieg über EINZELNE
  Sendungen übersieht Fälle, in denen erst die GEMEINSAME Umroutung zweier
  Sendungen eine LKW-Kapazitätsschwelle über- oder unterschreitet. Empirisch
  schließt jeder zusätzliche Startpunkt/Zug eine Lücke, die die anderen
  übersehen (siehe README: 4,4% -> 3,5% -> 3,0% -> 1,6% mittlere
  Optimalitätslücke über die drei Erweiterungsrunden).
"""

from linehaul_evaluation import evaluate_solution
from linehaul_network import candidate_routes, trucks_needed


def _build_flow_state(instance, route_choice):
    forward_flow = {}
    backward_flow = {}
    commodity_by_index = {c.index: c for c in instance.commodities}
    for k, route in route_choice.items():
        commodity = commodity_by_index[k]
        for leg in route.legs:
            key = (leg.line_i, leg.line_j)
            if leg.forward:
                forward_flow[key] = forward_flow.get(key, 0.0) + commodity.demand
            else:
                backward_flow[key] = backward_flow.get(key, 0.0) + commodity.demand
    return forward_flow, backward_flow


def _line_fixed_cost(instance, key, forward, backward):
    line = instance.line_between(*key)
    n_trucks = max(trucks_needed(forward, instance.truck_capacity), trucks_needed(backward, instance.truck_capacity))
    return n_trucks * line.fixed_cost


def _route_variable_and_transship_cost(instance, commodity, route):
    cost = sum(
        commodity.demand * instance.line_between(leg.line_i, leg.line_j).variable_cost_per_unit for leg in route.legs
    )
    if route.hub is not None:
        cost += commodity.demand * instance.transshipment_cost_per_unit
    return cost


def _pair_swap_delta(instance, forward_flow, backward_flow, ca, ra_old, ra_new, cb, rb_old, rb_new):
    """Kostenänderung, wenn Sendung ca von ra_old auf ra_new UND Sendung cb von
    rb_old auf rb_new wechselt - inkrementell berechnet (nur die betroffenen
    Linien, nicht das gesamte Netzwerk neu ausgewertet). Notwendig für
    akzeptable Rechenzeit: eine vollständige Neubewertung je Kandidatenpaar
    skaliert mit der Sendungsanzahl, das hier nicht."""
    affected_keys = set()
    for route in (ra_old, ra_new, rb_old, rb_new):
        for leg in route.legs:
            affected_keys.add((leg.line_i, leg.line_j))

    old_fixed = sum(
        _line_fixed_cost(instance, key, forward_flow.get(key, 0.0), backward_flow.get(key, 0.0))
        for key in affected_keys
    )

    trial_forward = dict(forward_flow)
    trial_backward = dict(backward_flow)

    def _apply(commodity, route, sign):
        for leg in route.legs:
            key = (leg.line_i, leg.line_j)
            if leg.forward:
                trial_forward[key] = trial_forward.get(key, 0.0) + sign * commodity.demand
            else:
                trial_backward[key] = trial_backward.get(key, 0.0) + sign * commodity.demand

    _apply(ca, ra_old, -1)
    _apply(cb, rb_old, -1)
    _apply(ca, ra_new, 1)
    _apply(cb, rb_new, 1)

    new_fixed = sum(
        _line_fixed_cost(instance, key, trial_forward.get(key, 0.0), trial_backward.get(key, 0.0))
        for key in affected_keys
    )

    delta = (
        (new_fixed - old_fixed)
        + (_route_variable_and_transship_cost(instance, ca, ra_new) - _route_variable_and_transship_cost(instance, ca, ra_old))
        + (_route_variable_and_transship_cost(instance, cb, rb_new) - _route_variable_and_transship_cost(instance, cb, rb_old))
    )
    return delta, trial_forward, trial_backward


def _pairwise_local_search(instance, routes_by_commodity, route_choice, max_rounds=2):
    route_choice = dict(route_choice)
    commodities = list(instance.commodities)
    commodity_by_index = {c.index: c for c in commodities}
    forward_flow, backward_flow = _build_flow_state(instance, route_choice)

    for _ in range(max_rounds):
        improved = False
        for a in range(len(commodities)):
            for b in range(a + 1, len(commodities)):
                ka, kb = commodities[a].index, commodities[b].index
                ca, cb = commodity_by_index[ka], commodity_by_index[kb]
                ra_old, rb_old = route_choice[ka], route_choice[kb]
                best_delta = -1e-9
                best_pair = None
                best_flows = None
                for ra_new in routes_by_commodity[ka]:
                    for rb_new in routes_by_commodity[kb]:
                        if ra_new is ra_old and rb_new is rb_old:
                            continue
                        delta, trial_forward, trial_backward = _pair_swap_delta(
                            instance, forward_flow, backward_flow, ca, ra_old, ra_new, cb, rb_old, rb_new
                        )
                        if delta < best_delta:
                            best_delta = delta
                            best_pair = (ra_new, rb_new)
                            best_flows = (trial_forward, trial_backward)
                if best_pair is not None:
                    route_choice[ka], route_choice[kb] = best_pair
                    forward_flow, backward_flow = best_flows
                    improved = True
        if not improved:
            break
    return route_choice


def all_direct_construction(instance):
    routes_by_commodity = candidate_routes(instance)
    route_choice = {k: routes[0] for k, routes in routes_by_commodity.items()}
    return route_choice


def marginal_cost_construction(instance, descending=True):
    routes_by_commodity = candidate_routes(instance)
    order = sorted(instance.commodities, key=lambda c: c.demand, reverse=descending)

    forward_flow = {}
    backward_flow = {}
    trucks = {}
    route_choice = {}

    for commodity in order:
        best_route = None
        best_marginal_cost = None
        for route in routes_by_commodity[commodity.index]:
            marginal = 0.0
            for leg in route.legs:
                key = (leg.line_i, leg.line_j)
                line = instance.line_between(leg.line_i, leg.line_j)
                current_forward = forward_flow.get(key, 0.0)
                current_backward = backward_flow.get(key, 0.0)
                if leg.forward:
                    new_forward, new_backward = current_forward + commodity.demand, current_backward
                else:
                    new_forward, new_backward = current_forward, current_backward + commodity.demand
                needed_trucks = max(
                    trucks_needed(new_forward, instance.truck_capacity),
                    trucks_needed(new_backward, instance.truck_capacity),
                )
                marginal += max(0, needed_trucks - trucks.get(key, 0)) * line.fixed_cost
                marginal += commodity.demand * line.variable_cost_per_unit
            if route.hub is not None:
                marginal += commodity.demand * instance.transshipment_cost_per_unit
            if best_marginal_cost is None or marginal < best_marginal_cost - 1e-9:
                best_marginal_cost = marginal
                best_route = route

        route_choice[commodity.index] = best_route
        for leg in best_route.legs:
            key = (leg.line_i, leg.line_j)
            if leg.forward:
                forward_flow[key] = forward_flow.get(key, 0.0) + commodity.demand
            else:
                backward_flow[key] = backward_flow.get(key, 0.0) + commodity.demand
            trucks[key] = max(
                trucks_needed(forward_flow.get(key, 0.0), instance.truck_capacity),
                trucks_needed(backward_flow.get(key, 0.0), instance.truck_capacity),
            )

    return route_choice


def _hub_route_choice(instance, routes_by_commodity, hub):
    route_choice = {}
    for commodity in instance.commodities:
        k = commodity.index
        if commodity.origin == hub or commodity.destination == hub:
            route_choice[k] = routes_by_commodity[k][0]  # direct
        else:
            hub_route = next(r for r in routes_by_commodity[k] if r.hub == hub)
            route_choice[k] = hub_route
    return route_choice


def hub_and_spoke_construction(instance):
    if instance.n_depots < 3 or not instance.commodities:
        return all_direct_construction(instance)

    routes_by_commodity = candidate_routes(instance)
    best_choice = None
    best_cost = None
    for hub in range(instance.n_depots):
        route_choice = _hub_route_choice(instance, routes_by_commodity, hub)
        cost = evaluate_solution(instance, route_choice)["total_cost"]
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_choice = route_choice
    return best_choice


def _local_search(instance, routes_by_commodity, route_choice, max_rounds=20):
    route_choice = dict(route_choice)
    for _ in range(max_rounds):
        improved = False
        for commodity in instance.commodities:
            k = commodity.index
            current_cost = evaluate_solution(instance, route_choice)["total_cost"]
            best_route = route_choice[k]
            best_cost = current_cost
            for candidate in routes_by_commodity[k]:
                if candidate is route_choice[k]:
                    continue
                trial = dict(route_choice)
                trial[k] = candidate
                trial_cost = evaluate_solution(instance, trial)["total_cost"]
                if trial_cost < best_cost - 1e-9:
                    best_cost = trial_cost
                    best_route = candidate
            if best_route is not route_choice[k]:
                route_choice[k] = best_route
                improved = True
        if not improved:
            break
    return route_choice


def greedy_construction(instance):
    routes_by_commodity = candidate_routes(instance)

    starting_points = [
        all_direct_construction(instance),
        marginal_cost_construction(instance, descending=True),
        marginal_cost_construction(instance, descending=False),
    ]
    for hub in range(instance.n_depots):
        starting_points.append(_hub_route_choice(instance, routes_by_commodity, hub))

    best_choice = None
    best_cost = None
    for start in starting_points:
        result = _local_search(instance, routes_by_commodity, start)
        cost = evaluate_solution(instance, result)["total_cost"]
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_choice = result

    polished = _pairwise_local_search(instance, routes_by_commodity, best_choice)
    polished = _local_search(instance, routes_by_commodity, polished, max_rounds=3)
    polished_cost = evaluate_solution(instance, polished)["total_cost"]
    if polished_cost < best_cost - 1e-9:
        best_choice = polished

    return best_choice
