"""Zufällige Szenario-Erzeugung: Depotpositionen und Sendungsnachfrage."""

import numpy as np


def generate_positions(n_depots, seed):
    rng = np.random.default_rng(seed)
    xs = rng.uniform(0, 100, size=n_depots)
    ys = rng.uniform(0, 100, size=n_depots)
    return np.column_stack([xs, ys])


def generate_demand(n_depots, seed, demand_density, demand_scale):
    """Erzeugt eine symmetrische Nachfragematrix (Palettenäquivalent/Tag).

    demand_density: Anteil der Depot-Paare mit Nachfrage > 0 (0..1).
    demand_scale: multiplikativer Skalierungsfaktor auf die Nachfragemenge.
    """
    rng = np.random.default_rng(seed + 1)
    demand = np.zeros((n_depots, n_depots))
    for i in range(n_depots):
        for j in range(i + 1, n_depots):
            if rng.uniform() < demand_density:
                qty = rng.uniform(5, 40) * demand_scale
                demand[i, j] = qty
                demand[j, i] = qty
    return demand


def pairwise_distances(positions):
    n = len(positions)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            dist[i, j] = np.linalg.norm(positions[i] - positions[j])
    return dist
