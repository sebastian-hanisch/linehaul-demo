"""Defaults, Regler-Grenzen, Farben und Beispielszenarien."""

N_DEPOTS_DEFAULT = 7
N_DEPOTS_RANGE = (4, 9)  # exakter MIP-Löser bleibt hier durch EXACT_SOLVE_TIME_LIMIT_SECONDS
# gedeckelt, siehe README ("Laufzeit des exakten Lösers") - Härte einer MIP-Instanz
# korreliert NICHT sauber mit Depot-/Sendungsanzahl (siehe README), deshalb harte
# Zeitschranke statt eines größenbasierten Cutoffs

DEMAND_DENSITY_DEFAULT = 0.5
DEMAND_DENSITY_RANGE = (0.2, 1.0)

DEMAND_SCALE_DEFAULT = 1.0
DEMAND_SCALE_RANGE = (0.3, 3.0)

FIXED_COST_BASE_DEFAULT = 20.0
FIXED_COST_BASE_RANGE = (0.0, 100.0)

FIXED_COST_PER_KM_DEFAULT = 15.0
FIXED_COST_PER_KM_RANGE = (1.0, 30.0)

VARIABLE_COST_PER_KM_DEFAULT = 0.1
VARIABLE_COST_PER_KM_RANGE = (0.02, 0.5)

TRUCK_CAPACITY_DEFAULT = 40.0
TRUCK_CAPACITY_RANGE = (20.0, 100.0)

TRANSSHIPMENT_COST_DEFAULT = 1.5
TRANSSHIPMENT_COST_RANGE = (0.0, 15.0)

RANDOM_SEED_DEFAULT = 7
RANDOM_SEED_RANGE = (0, 2_000_000_000)

EXACT_SOLVE_TIME_LIMIT_SECONDS = 4  # siehe README: 15s liess die App bei hoher
# Nachfragedichte + 9 Depots bis zu 20s haengen, ohne das Optimum zu beweisen -
# 4s begrenzt die Wartezeit robust, die App kennzeichnet "Zeitlimit erreicht"-
# Ergebnisse ohnehin bereits korrekt als nicht bewiesen optimal (app.py)

PRESETS = {
    "Normalfall": dict(
        n_depots=7, demand_density=0.5, demand_scale=1.0, fixed_cost_base=20.0,
        fixed_cost_per_km=15.0, variable_cost_per_km=0.1, truck_capacity=40.0,
        transshipment_cost_per_unit=1.5, seed=7,
    ),
    "Geringe Fixkosten (Hub schadet)": dict(
        n_depots=7, demand_density=0.5, demand_scale=1.0, fixed_cost_base=20.0,
        fixed_cost_per_km=2.0, variable_cost_per_km=0.1, truck_capacity=40.0,
        transshipment_cost_per_unit=1.5, seed=7,
    ),
    "Hohe Fixkosten (starke Bündelung)": dict(
        n_depots=7, demand_density=0.5, demand_scale=1.0, fixed_cost_base=20.0,
        fixed_cost_per_km=30.0, variable_cost_per_km=0.1, truck_capacity=40.0,
        transshipment_cost_per_unit=1.5, seed=7,
    ),
    "Teurer Umschlag": dict(
        n_depots=7, demand_density=0.5, demand_scale=1.0, fixed_cost_base=20.0,
        fixed_cost_per_km=15.0, variable_cost_per_km=0.1, truck_capacity=40.0,
        transshipment_cost_per_unit=12.0, seed=7,
    ),
}
