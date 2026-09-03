"""SETTING_SPECS-Permalink-Muster, Presets und Zufalls-Seed-Button (nach dem in
network-flow-demo/freight_demo etablierten Muster)."""

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import linehaul_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None


SETTING_SPECS = {
    "n_depots_slider": SettingSpec("nd", int, C.N_DEPOTS_DEFAULT, *C.N_DEPOTS_RANGE),
    "demand_density_slider": SettingSpec("dd", float, C.DEMAND_DENSITY_DEFAULT, *C.DEMAND_DENSITY_RANGE),
    "demand_scale_slider": SettingSpec("ds", float, C.DEMAND_SCALE_DEFAULT, *C.DEMAND_SCALE_RANGE),
    "fixed_cost_base_slider": SettingSpec("fb", float, C.FIXED_COST_BASE_DEFAULT, *C.FIXED_COST_BASE_RANGE),
    "fixed_cost_per_km_slider": SettingSpec("fk", float, C.FIXED_COST_PER_KM_DEFAULT, *C.FIXED_COST_PER_KM_RANGE),
    "variable_cost_per_km_slider": SettingSpec("vk", float, C.VARIABLE_COST_PER_KM_DEFAULT, *C.VARIABLE_COST_PER_KM_RANGE),
    "truck_capacity_slider": SettingSpec("cap", float, C.TRUCK_CAPACITY_DEFAULT, *C.TRUCK_CAPACITY_RANGE),
    "transshipment_cost_slider": SettingSpec("tc", float, C.TRANSSHIPMENT_COST_DEFAULT, *C.TRANSSHIPMENT_COST_RANGE),
    "seed_input": SettingSpec("seed", int, C.RANDOM_SEED_DEFAULT, *C.RANDOM_SEED_RANGE),
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default
    if "force_regen" not in st.session_state:
        st.session_state["force_regen"] = False


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                if spec.lo is not None:
                    value = max(spec.lo, value)
                if spec.hi is not None:
                    value = min(spec.hi, value)
                st.session_state[state_key] = value
            except (ValueError, TypeError):
                pass
    st.session_state["permalink_loaded"] = True


def sync_query_params(n_depots, demand_density, demand_scale, fixed_cost_base, fixed_cost_per_km,
                       variable_cost_per_km, truck_capacity, transshipment_cost_per_unit, seed):
    try:
        st.query_params["nd"] = str(int(n_depots))
        st.query_params["dd"] = str(demand_density)
        st.query_params["ds"] = str(demand_scale)
        st.query_params["fb"] = str(fixed_cost_base)
        st.query_params["fk"] = str(fixed_cost_per_km)
        st.query_params["vk"] = str(variable_cost_per_km)
        st.query_params["cap"] = str(truck_capacity)
        st.query_params["tc"] = str(transshipment_cost_per_unit)
        st.query_params["seed"] = str(int(seed))
    except Exception:
        pass


def apply_preset(name):
    p = C.PRESETS[name]
    st.session_state["n_depots_slider"] = p["n_depots"]
    st.session_state["demand_density_slider"] = p["demand_density"]
    st.session_state["demand_scale_slider"] = p["demand_scale"]
    st.session_state["fixed_cost_base_slider"] = p["fixed_cost_base"]
    st.session_state["fixed_cost_per_km_slider"] = p["fixed_cost_per_km"]
    st.session_state["variable_cost_per_km_slider"] = p["variable_cost_per_km"]
    st.session_state["truck_capacity_slider"] = p["truck_capacity"]
    st.session_state["transshipment_cost_slider"] = p["transshipment_cost_per_unit"]
    st.session_state["seed_input"] = p["seed"]
    st.session_state["force_regen"] = True


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, 2_000_000_000)
    st.session_state["force_regen"] = True
