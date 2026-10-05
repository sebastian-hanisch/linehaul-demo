"""Unabhängiges Orakel für das Hauptlauf-Netzwerkdesign.

Orakel (anderer Rechenweg als SCIP-Modell und Heuristiken): **Vollaufzählung** aller Routenwahlen
(Direkt oder über genau ein Zwischen-Depot je Sendung) auf Mini-Instanzen. Die Kosten jeder Wahl werden hier
von Hand aus Knotenfolgen berechnet (Fluss je Richtung, LKW = Aufrunden je Richtung, das Maximum der beiden
Richtungen zählt), ohne die Route-/Evaluations-Klassen der Demo."""

import itertools
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from linehaul_evaluation import evaluate_solution
from linehaul_heuristics import all_direct_construction, greedy_construction, hub_and_spoke_construction
from linehaul_network import build_instance
from linehaul_scenario import generate_demand, generate_positions, pairwise_distances


def _kosten(par, dist, dem, wahl):
    """wahl: {(i, j): Hub oder None} mit i < j. Rückgabe (Gesamtkosten, LKW je Linie)."""
    fix_basis, fix_km, var_km, kap, umschlag = par
    fluss, var = {}, 0.0
    for (i, j), hub in wahl.items():
        q = dem[i][j]
        pfad = [i, j] if hub is None else [i, hub, j]
        for a, b in zip(pfad, pfad[1:]):
            fluss[(a, b)] = fluss.get((a, b), 0.0) + q
            var += q * var_km * dist[a][b]
        if hub is not None:
            var += q * umschlag
    fix, lkw = 0.0, {}
    for linie in {frozenset(k) for k in fluss}:
        a, b = sorted(linie)
        n = max(math.ceil(fluss.get((a, b), 0.0) / kap - 1e-9), math.ceil(fluss.get((b, a), 0.0) / kap - 1e-9))
        lkw[(a, b)] = n
        fix += n * (fix_basis + fix_km * dist[a][b])
    return fix + var, lkw


def _wahl(inst, route_choice):
    return {(inst.commodities[k].origin, inst.commodities[k].destination): r.hub for k, r in route_choice.items()}


def _instanz(rng, grenzfall=False):
    n = rng.choice([3, 4, 4, 5])
    seed = rng.randrange(10**6)
    pos = generate_positions(n, seed)
    dem = generate_demand(n, seed, rng.choice([0.4, 0.7, 1.0]), rng.choice([0.3, 1.0, 3.0]))
    kap = rng.choice([20.0, 40.0, 100.0])
    if grenzfall:  # Mengen genau auf Vielfachen der LKW-Kapazität: Aufrunden darf keinen Zusatz-LKW erzeugen
        dem = (dem > 0) * kap * rng.choice([0.5, 1.0, 2.0])
    par = (rng.choice([0.0, 20.0, 100.0]), rng.choice([1.0, 15.0, 30.0]), rng.choice([0.02, 0.1, 0.5]), kap,
           rng.choice([0.0, 1.5, 15.0]))
    dist = pairwise_distances(pos)
    inst = build_instance(pos, dem, dist, par[0], par[1], par[2], par[3], par[4])
    return inst, par, dist, dem


def _optimum(inst, par, dist, dem):
    paare = [(c.origin, c.destination) for c in inst.commodities]
    optionen = [[None] + [h for h in range(inst.n_depots) if h not in p] for p in paare]
    return min(_kosten(par, dist, dem, dict(zip(paare, kombi)))[0] for kombi in itertools.product(*optionen))


def _instanzen(zahl, grenzfall=False, seed=24):
    rng = random.Random(seed)
    out = []
    while len(out) < zahl:
        inst, par, dist, dem = _instanz(rng, grenzfall)
        if 0 < len(inst.commodities) <= 6:
            out.append((inst, par, dist, dem))
    return out


@pytest.mark.parametrize("grenzfall", [False, True])
def test_auswertung_und_heuristiken_gegen_vollaufzaehlung(grenzfall):
    for inst, par, dist, dem in _instanzen(30, grenzfall):
        opt = _optimum(inst, par, dist, dem)
        direkt, hub, gier = (f(inst) for f in (all_direct_construction, hub_and_spoke_construction, greedy_construction))
        kosten = {}
        for name, wahl in (("direkt", direkt), ("hub", hub), ("greedy", gier)):
            ev = evaluate_solution(inst, wahl)
            erwartet, lkw = _kosten(par, dist, dem, _wahl(inst, wahl))
            assert ev["total_cost"] == pytest.approx(erwartet, rel=1e-9, abs=1e-6)  # Auswertung = Handrechnung
            assert ev["n_trucks_total"] == sum(lkw.values())
            assert ev["n_lines"] == sum(1 for v in lkw.values() if v > 0)
            assert erwartet >= opt - 1e-6  # keine Heuristik unter dem Optimum
            kosten[name] = erwartet
        assert kosten["greedy"] <= min(kosten["direkt"], kosten["hub"]) + 1e-6
        # Hub-and-Spoke: bester Einzel-Hub (Sendungen mit dem Hub als Endpunkt fahren direkt), unabhängig nachgerechnet
        paare = [(c.origin, c.destination) for c in inst.commodities]
        bester_hub = min(
            _kosten(par, dist, dem, {(i, j): (None if h in (i, j) else h) for i, j in paare})[0] for h in range(inst.n_depots)
        )
        assert kosten["hub"] == pytest.approx(bester_hub, rel=1e-9, abs=1e-6)


def test_exakter_loeser_gegen_vollaufzaehlung():
    pytest.importorskip("ortools")
    from linehaul_reference_solver import solve_exact

    for inst, par, dist, dem in _instanzen(25, seed=7):
        res = solve_exact(inst, 20)
        assert res.optimal
        assert res.objective == pytest.approx(_optimum(inst, par, dist, dem), rel=1e-7, abs=1e-6)
        assert _kosten(par, dist, dem, _wahl(inst, res.route_choice))[0] == pytest.approx(res.objective, rel=1e-7, abs=1e-6)
