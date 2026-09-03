"""Problem-Instanz für das Hauptlauf-Netzwerkdesign.

Modell: gegeben Depots und paarweise Sendungsnachfrage (Commodities), welche
Depot-Paare bekommen eine feste tägliche Hauptlauf-Linie (LKW-Fixkosten +
variable Kosten je Einheit, Kapazität je LKW), und wie wird Nachfrage ohne
Direktlinie über ein Zwischen-Depot umgeschlagen (Umschlagkosten je Einheit)?

Vereinfachung (bewusst, siehe README): jede Sendung nutzt höchstens EIN
Zwischen-Depot (Direktversand oder Versand über genau einen Hub) - realistisch
für Stückgutspedition, wo mehr als ein Umschlag pro Sendung unüblich ist, und
macht aus dem Problem eine diskrete Routenwahl je Sendung (statt allgemeinem
Mehrgüter-Fluss mit beliebig langen Pfaden): für jede Sendung k wird GENAU EINE
Route aus einem festen Kandidatensatz gewählt (Direkt, oder via Hub h für jedes
mögliche Zwischen-Depot h). Mehrere Sendungen können sich dieselbe Hauptlauf-
Linie teilen - das ist der Konsolidierungs-Hebel.

Ein LKW auf einer Linie {i,j} bedient beide Richtungen mit je voller Kapazität
(vereinfachende Annahme: derselbe LKW-Pool deckt Hin- und Rückrichtung ab).
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Commodity:
    index: int
    origin: int
    destination: int
    demand: float


@dataclass(frozen=True)
class CandidateLine:
    i: int
    j: int
    distance: float
    fixed_cost: float
    variable_cost_per_unit: float


@dataclass(frozen=True)
class RouteLeg:
    line_i: int
    line_j: int
    forward: bool  # True: Fahrt von line_i nach line_j, False: umgekehrt


@dataclass(frozen=True)
class Route:
    commodity_index: int
    hub: object  # int oder None (Direktroute)
    legs: tuple


@dataclass
class ProblemInstance:
    n_depots: int
    positions: np.ndarray
    distances: np.ndarray
    commodities: list
    candidate_lines: list
    truck_capacity: float
    transshipment_cost_per_unit: float

    def line_key(self, i, j):
        return (i, j) if i < j else (j, i)

    def line_between(self, i, j):
        return self._line_lookup[self.line_key(i, j)]

    def __post_init__(self):
        self._line_lookup = {self.line_key(l.i, l.j): l for l in self.candidate_lines}


def build_instance(
    positions,
    demand_matrix,
    distances,
    fixed_cost_base,
    fixed_cost_per_km,
    variable_cost_per_km,
    truck_capacity,
    transshipment_cost_per_unit,
):
    n = len(positions)

    commodities = []
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            d = demand_matrix[i, j]
            if d > 0:
                commodities.append(Commodity(index=idx, origin=i, destination=j, demand=float(d)))
                idx += 1

    candidate_lines = []
    for i in range(n):
        for j in range(i + 1, n):
            dist = distances[i, j]
            candidate_lines.append(
                CandidateLine(
                    i=i,
                    j=j,
                    distance=dist,
                    fixed_cost=fixed_cost_base + fixed_cost_per_km * dist,
                    variable_cost_per_unit=variable_cost_per_km * dist,
                )
            )

    return ProblemInstance(
        n_depots=n,
        positions=positions,
        distances=distances,
        commodities=commodities,
        candidate_lines=candidate_lines,
        truck_capacity=truck_capacity,
        transshipment_cost_per_unit=transshipment_cost_per_unit,
    )


def _direct_route(commodity):
    o, d = commodity.origin, commodity.destination
    forward = o < d
    leg = RouteLeg(line_i=min(o, d), line_j=max(o, d), forward=forward)
    return Route(commodity_index=commodity.index, hub=None, legs=(leg,))


def _hub_route(commodity, hub):
    o, d = commodity.origin, commodity.destination
    leg1 = RouteLeg(line_i=min(o, hub), line_j=max(o, hub), forward=o < hub)
    leg2 = RouteLeg(line_i=min(hub, d), line_j=max(hub, d), forward=hub < d)
    return Route(commodity_index=commodity.index, hub=hub, legs=(leg1, leg2))


def candidate_routes(instance):
    """Liefert je Sendung die Liste möglicher Routen: [Direkt, via Hub 1, via Hub 2, ...]."""
    routes_by_commodity = {}
    for commodity in instance.commodities:
        routes = [_direct_route(commodity)]
        for hub in range(instance.n_depots):
            if hub != commodity.origin and hub != commodity.destination:
                routes.append(_hub_route(commodity, hub))
        routes_by_commodity[commodity.index] = routes
    return routes_by_commodity


def trucks_needed(demand, capacity):
    if demand <= 1e-9:
        return 0
    return int(np.ceil(demand / capacity - 1e-9))
