import streamlit as st

import linehaul_constants as C
from linehaul_evaluation import comparison_table, evaluate_solution
from linehaul_heuristics import all_direct_construction, greedy_construction, hub_and_spoke_construction
from linehaul_network import build_instance
from linehaul_pdf_export import generate_linehaul_plan_pdf
from linehaul_presets import (
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sync_query_params,
)
from linehaul_reference_solver import solve_exact
from linehaul_scenario import generate_demand, generate_positions, pairwise_distances
from linehaul_ui_panel import render_linehaul_panel
from linehaul_visualization import build_cost_breakdown_chart, build_linehaul_map

st.set_page_config(page_title="Hauptlauf-Netzwerkdesign – Sebastian Hanisch", layout="wide")


def _build_instance(
    n_depots, demand_density, demand_scale, fixed_cost_base, fixed_cost_per_km,
    variable_cost_per_km, truck_capacity, transshipment_cost_per_unit, seed,
):
    positions = generate_positions(n_depots, seed)
    demand = generate_demand(n_depots, seed, demand_density, demand_scale)
    distances = pairwise_distances(positions)
    return build_instance(
        positions,
        demand,
        distances,
        fixed_cost_base,
        fixed_cost_per_km,
        variable_cost_per_km,
        truck_capacity,
        transshipment_cost_per_unit,
    )


@st.cache_data(show_spinner=False)
def _compute_heuristics(
    n_depots, demand_density, demand_scale, fixed_cost_base, fixed_cost_per_km,
    variable_cost_per_km, truck_capacity, transshipment_cost_per_unit, seed,
):
    instance = _build_instance(
        n_depots, demand_density, demand_scale, fixed_cost_base, fixed_cost_per_km,
        variable_cost_per_km, truck_capacity, transshipment_cost_per_unit, seed,
    )
    results = [
        evaluate_solution(instance, all_direct_construction(instance), label="Alles direkt"),
        evaluate_solution(instance, hub_and_spoke_construction(instance), label="Hub-and-Spoke"),
        evaluate_solution(instance, greedy_construction(instance), label="Greedy-Verbesserung"),
    ]
    return instance, results


@st.cache_data(show_spinner=False)
def _compute_exact(
    n_depots, demand_density, demand_scale, fixed_cost_base, fixed_cost_per_km,
    variable_cost_per_km, truck_capacity, transshipment_cost_per_unit, seed,
):
    """Getrennt von `_compute_heuristics`, damit der exakte Löser NICHT automatisch bei jeder
    Regler-Änderung mitläuft - läuft nur, wenn der Nutzer explizit den Button klickt (siehe
    unten). Vorausgesetzt wird, dass die aktuelle Instanz Sendungen hat (`instance.commodities`)
    - der Aufrufer prüft das bereits vor jedem Aufruf, hier nicht wiederholt."""
    instance = _build_instance(
        n_depots, demand_density, demand_scale, fixed_cost_base, fixed_cost_per_km,
        variable_cost_per_km, truck_capacity, transshipment_cost_per_unit, seed,
    )
    solve = solve_exact(instance, time_limit_seconds=C.EXACT_SOLVE_TIME_LIMIT_SECONDS)
    if not solve.feasible:
        return None
    exact_label = "Exakt (OR-Tools)" if solve.optimal else "Exakt (OR-Tools, Zeitlimit)"
    exact_eval = evaluate_solution(instance, solve.route_choice, label=exact_label)
    return {"eval": exact_eval, "optimal": solve.optimal, "wall_time_ms": solve.wall_time_ms}


st.title("🚛 Hauptlauf-Netzwerkdesign")
st.markdown(
    """
Welche Depot-Paare bekommen eine feste, tägliche **Hauptlauf**-Linie - und welche Sendungen
werden stattdessen über ein Zwischen-Depot umgeschlagen, um sich eine ohnehin fahrende Linie
zu teilen? Ein Fixed-Charge-Netzwerkdesign-Problem aus der Straßenlogistik (Vorlauf →
**Hauptlauf** → Nachlauf). Wie das Modell und die vier Verfahren im Detail funktionieren,
steht im Expander "Wie funktioniert diese Demo?" weiter unten, die formale Herleitung im
Expander "📐 Mathematische Formulierung".
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
PRESET_HELP = {
    "Normalfall": "Ausgewogene Fixkosten und Umschlagkosten - Greedy bündelt spürbar gegenüber Direktversand.",
    "Geringe Fixkosten (Hub schadet)": "Niedrige Linienfixkosten - ein erzwungener Umweg über einen einzigen "
    "Hub kostet hier mehr, als er an Bündelung spart.",
    "Hohe Fixkosten (starke Bündelung)": "Hohe Linienfixkosten - Bündelung über Hubs lohnt sich besonders stark.",
    "Teurer Umschlag": "Hohe Umschlagkosten je Einheit - Hub-and-Spoke verschlechtert sich deutlich schneller "
    "als die flexiblere Greedy-Lösung.",
}
preset_cols = st.columns(len(C.PRESETS))
for i, name in enumerate(C.PRESETS.keys()):
    with preset_cols[i]:
        st.button(name, use_container_width=True, on_click=apply_preset, args=(name,), help=PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    n_depots = st.slider("Anzahl Depots", *bounds("n_depots_slider"), key="n_depots_slider")
    demand_density = st.slider(
        "Nachfragedichte (Anteil Depot-Paare mit Sendungen)",
        *bounds("demand_density_slider"),
        key="demand_density_slider",
    )
    demand_scale = st.slider(
        "Nachfragemenge (Skalierung)", *bounds("demand_scale_slider"), key="demand_scale_slider"
    )
    seed = st.number_input("Zufalls-Seed", *bounds("seed_input"), key="seed_input", step=1)

    st.markdown("**Kosten & Kapazität**")
    fixed_cost_base = st.slider(
        "Fixkosten je Linie, Basis (€)", *bounds("fixed_cost_base_slider"), key="fixed_cost_base_slider"
    )
    fixed_cost_per_km = st.slider(
        "Fixkosten je Linie und km (€/km)", *bounds("fixed_cost_per_km_slider"), key="fixed_cost_per_km_slider"
    )
    variable_cost_per_km = st.slider(
        "Variable Transportkosten (€/Einheit·km)",
        *bounds("variable_cost_per_km_slider"),
        key="variable_cost_per_km_slider",
    )
    truck_capacity = st.slider(
        "LKW-Kapazität (Einheiten)", *bounds("truck_capacity_slider"), key="truck_capacity_slider"
    )
    transshipment_cost = st.slider(
        "Umschlagkosten (€/Einheit)", *bounds("transshipment_cost_slider"), key="transshipment_cost_slider"
    )

    st.markdown("**Referenz**")
    run_exact_clicked = st.button(
        "🎯 Exakte Lösung berechnen (OR-Tools)",
        use_container_width=True,
        help="Löst das vollständige gemischt-ganzzahlige Modell exakt - dient als Cross-Check "
        f"für die Heuristiken. Auf {C.EXACT_SOLVE_TIME_LIMIT_SECONDS}s begrenzt (bei vielen "
        "Depots/hoher Nachfragedichte manchmal nur die beste gefundene, nicht bewiesen "
        "optimale Lösung - wird dann so gekennzeichnet). Läuft bewusst nur auf Klick, nicht "
        "automatisch bei jeder Änderung - kann bei großen Szenarien mehrere Sekunden dauern.",
    )

    st.button(
        "🎲 Neues Zufallsnetzwerk",
        use_container_width=True,
        on_click=randomize_seed,
        help="Würfelt einen neuen Zufalls-Seed für Depotpositionen und Nachfrage.",
    )

sync_query_params(
    n_depots,
    demand_density,
    demand_scale,
    fixed_cost_base,
    fixed_cost_per_km,
    variable_cost_per_km,
    truck_capacity,
    transshipment_cost,
    seed,
)

scenario_key = (
    int(n_depots), demand_density, demand_scale, fixed_cost_base, fixed_cost_per_km,
    variable_cost_per_km, truck_capacity, transshipment_cost, int(seed),
)

with st.spinner("Berechne Netzwerk..."):
    instance, results = _compute_heuristics(*scenario_key)

if not instance.commodities:
    st.warning("Bei dieser Nachfragedichte gibt es keine Sendungen. Regler erhöhen oder neues Netzwerk würfeln.")
    st.stop()

best = min(results, key=lambda r: r["total_cost"])
baseline = max(results, key=lambda r: r["total_cost"])
cost_saved = baseline["total_cost"] - best["total_cost"]
pct_saved = (cost_saved / baseline["total_cost"] * 100) if baseline["total_cost"] > 0 else 0.0

if run_exact_clicked:
    st.session_state["exact_scenario_key"] = scenario_key

exact_result = None
exact_stale = False
if st.session_state.get("exact_scenario_key") == scenario_key:
    with st.spinner(f"Berechne exakte Lösung (OR-Tools, bis zu {C.EXACT_SOLVE_TIME_LIMIT_SECONDS}s)..."):
        exact_result = _compute_exact(*scenario_key)
elif "exact_scenario_key" in st.session_state:
    # Einstellungen haben sich seit der letzten exakten Berechnung geändert - die alte Lösung
    # gehört zu einem anderen Szenario und wird bewusst NICHT mehr angezeigt, statt irreführend
    # stehen zu bleiben.
    exact_stale = True

st.markdown("## 🎯 Ihr kostenoptimiertes Hauptlauf-Netzwerk")
st.caption(f"Methode: **{best['label']}** - wird bei jedem Lauf neu anhand der Gesamtkosten bestimmt.")

m1, m2, m3, m4 = st.columns(4)
m1.metric(
    "Gesamtkosten",
    f"{best['total_cost']:.0f} €",
    delta=f"-{cost_saved:.0f} € ggü. {baseline['label']}",
    delta_color="inverse",
)
m2.metric("Aktive Hauptlauf-Linien", best["n_lines"])
m3.metric("LKW gesamt", best["n_trucks_total"])
m4.metric("Sendungen mit Umschlag", f"{best['n_shipments_transshipped']}/{best['n_shipments_total']}")

if cost_saved > 1:
    st.success(
        f"💶 **{best['label']}** spart hier ca. **{cost_saved:.0f} €** ({pct_saved:.1f}%) "
        f"gegenüber '{baseline['label']}'."
    )

if exact_result is not None:
    exact_eval = exact_result["eval"]
    gap = best["total_cost"] - exact_eval["total_cost"]
    gap_pct = (gap / exact_eval["total_cost"] * 100) if exact_eval["total_cost"] > 0 else 0.0

    if exact_result["optimal"]:
        # Bewiesenes Optimum - der Solver hat garantiert keine bessere Lösung übersehen,
        # gap ist (bis auf Rundung) immer >= 0.
        if gap < 1:
            st.info(
                f"✅ Exakter Referenzlöser (OR-Tools, optimal gelöst, "
                f"{exact_result['wall_time_ms']:.0f} ms): **{best['label']}** erreicht bereits "
                f"das Optimum ({exact_eval['total_cost']:.0f} €)."
            )
        else:
            st.info(
                f"📐 Exakter Referenzlöser (OR-Tools, optimal gelöst, "
                f"{exact_result['wall_time_ms']:.0f} ms): Optimum liegt bei "
                f"{exact_eval['total_cost']:.0f} € - Lücke zur besten Heuristik: {gap:.0f} € "
                f"({gap_pct:.1f}%)."
            )
    else:
        # Zeitlimit erreicht: exact_eval ist nur die beste bislang GEFUNDENE Lösung, kein
        # bewiesenes Optimum - eine Heuristik kann sie unter- oder überbieten, "das Optimum
        # erreicht" wäre hier eine falsche Behauptung (das wahre Optimum ist unbekannt).
        if gap <= 1:
            st.warning(
                f"⏱️ Exakter Referenzlöser (OR-Tools, Zeitlimit erreicht, kein Optimalitäts-"
                f"beweis, {exact_result['wall_time_ms']:.0f} ms): **{best['label']}** "
                f"({best['total_cost']:.0f} €) erreicht oder unterbietet sogar die beste vom "
                f"Solver gefundene Lösung ({exact_eval['total_cost']:.0f} €) - das tatsächliche "
                f"Optimum könnte noch darunter liegen."
            )
        else:
            st.warning(
                f"⏱️ Exakter Referenzlöser (OR-Tools, Zeitlimit erreicht, kein Optimalitäts-"
                f"beweis, {exact_result['wall_time_ms']:.0f} ms): beste bislang gefundene "
                f"Lösung liegt bei {exact_eval['total_cost']:.0f} € - {gap:.0f} € ({gap_pct:.1f}%) "
                f"unter der besten Heuristik, aber ohne Optimalitätsgarantie."
            )
elif exact_stale:
    st.info(
        "ℹ️ Die zuletzt berechnete exakte Lösung bezog sich auf ein anderes Szenario - "
        "Einstellungen links geändert? Erneut auf '🎯 Exakte Lösung berechnen' klicken, um sie "
        "für die aktuelle Konfiguration zu erhalten."
    )
else:
    st.caption(
        "💡 Exaktes Optimum als Cross-Check sehen? Button '🎯 Exakte Lösung berechnen' in der "
        "Seitenleiste - läuft nur auf Klick, da es bei großen Szenarien einige Sekunden dauern kann."
    )

fig_best = build_linehaul_map(instance, best, title=best["label"])
st.plotly_chart(fig_best, use_container_width=True, key="primary_map")

pdf_bytes_best = generate_linehaul_plan_pdf(best["label"], instance, best)
st.download_button(
    "📄 Netzwerkplan als PDF herunterladen",
    data=pdf_bytes_best,
    file_name="hauptlauf_plan_optimiert.pdf",
    mime="application/pdf",
    key="primary_pdf_download",
)

st.caption(
    "Ermittelt mit der besten von drei eigenen Optimierungsmethoden für dieses Szenario. "
    "Details zu allen Methoden und dem Vergleich mit Google OR-Tools unten."
)

st.markdown("---")

st.subheader("📐 Wann lohnt sich Bündelung über einen Hub?")
st.markdown(
    """
Kernfrage dieser Demo: Hauptlauf-Linien haben hohe **Fixkosten** (LKW-Bereitstellung,
unabhängig von der Auslastung) und geringe **variable Kosten**. Bündelung mehrerer Sendungen
über einen gemeinsamen Hub spart Fixkosten, kostet aber **Umschlaggebühren**. Ob sich das
lohnt, hängt vom Verhältnis dieser beiden Kostenarten ab - hier live für Ihre aktuelle
Konfiguration geprüft, nicht nur behauptet.
"""
)

direct_result = next(r for r in results if r["label"] == "Alles direkt")
hub_result = next(r for r in results if r["label"] == "Hub-and-Spoke")
hub_vs_direct = hub_result["total_cost"] - direct_result["total_cost"]

core_col1, core_col2, core_col3 = st.columns(3)
core_col1.metric("Alles direkt", f"{direct_result['total_cost']:.0f} €")
core_col2.metric(
    "Hub-and-Spoke",
    f"{hub_result['total_cost']:.0f} €",
    delta=f"{hub_vs_direct:.0f} € ggü. Alles direkt",
    delta_color="inverse",
)
core_col3.metric(
    "Aktive Linien (Hub-and-Spoke)",
    hub_result["n_lines"],
    delta=f"{hub_result['n_lines'] - direct_result['n_lines']} ggü. Alles direkt",
    delta_color="off",
)

if hub_vs_direct < -1:
    st.success(
        f"✅ Bei diesen Einstellungen lohnt sich Bündelung über einen einzigen Hub: "
        f"**{-hub_vs_direct:.0f} €** günstiger als lauter Direktlinien."
    )
elif hub_vs_direct > 1:
    st.warning(
        f"⚠️ Bei diesen Einstellungen SCHADET die starre Bündelung über einen einzigen Hub: "
        f"**{hub_vs_direct:.0f} €** teurer als lauter Direktlinien - der erzwungene Umweg über "
        f"einen einzigen Hub kostet mehr, als er an Fixkosten spart. Genau deshalb sucht Greedy "
        f"gezielt nach der besseren Mischung aus Direkt- und Hub-Routen (siehe oben)."
    )
else:
    st.info("Bei diesen Einstellungen sind Hub-and-Spoke und Alles direkt fast gleich teuer - ein echter Kipppunkt.")

st.markdown("---")

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    all_results = list(results)
    if exact_result is not None:
        all_results.append(exact_result["eval"])

    st.dataframe(comparison_table(all_results), use_container_width=True, hide_index=True)
    st.plotly_chart(build_cost_breakdown_chart(all_results), use_container_width=True)

    prefixes = ["direct", "hub", "greedy", "exact"]
    tabs = st.tabs([r["label"] for r in all_results])
    for tab, r, prefix in zip(tabs, all_results, prefixes):
        with tab:
            render_linehaul_panel(prefix, r["label"], instance, r)

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
Mehrere Depots versenden täglich Sendungen aneinander. Für jedes Depot-Paar mit Nachfrage
kann eine **Hauptlauf-Linie** betrieben werden: ein oder mehrere LKW, die täglich fest
zwischen den beiden Depots pendeln. Jede Linie kostet **Fixkosten** (LKW-Bereitstellung,
unabhängig von der Auslastung) plus geringe **variable Kosten** je transportierter Einheit.

Eine Sendung muss nicht direkt fahren: sie kann stattdessen über **ein** Zwischen-Depot
umgeschlagen werden (maximal ein Umschlag - realistisch für Stückgutspedition) und sich so
eine Linie mit anderen Sendungen teilen, die ohnehin dorthin fahren. Das spart Fixkosten,
kostet aber **Umschlaggebühren** je Einheit. Genau dieser Zielkonflikt ist die Kernfrage der
Demo: **wann lohnt sich Bündelung über einen Hub, und wann ist der direkte Weg günstiger?**

Drei selbst gebaute Verfahren stehen zur Auswahl (im Expander "Wie wir das erreichen" alle
nebeneinander), zusätzlich eine **exakte Referenzlösung** (Google OR-Tools, gemischt-
ganzzahliges Programm):

- **Alles direkt**: jede Sendung fährt direkt - keine Bündelung, Referenzpunkt.
- **Hub-and-Spoke**: alle Sendungen laufen über einen einzigen, best gewählten Hub.
- **Greedy-Verbesserung**: sucht lokal die besten Einzeländerungen, gestartet von mehreren
  Startlösungen und einem abschließenden paarweisen Politur-Schritt - nachweislich nie
  schlechter als die beste Startlösung.

Die Primäransicht zeigt **dynamisch** die bei den aktuellen Einstellungen tatsächlich
günstigste Heuristik - kein Verfahren wird pauschal bevorzugt.
        """
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        """
**Fixed-Charge (Multicommodity) Network Design Problem**, NP-schwer (Magnanti & Wong, 1984;
Crainic, *Service Network Design in Freight Transportation*, 2000).

Gegeben Depots $V$, Sendungen (Commodities) $k \\in K$ mit Ursprung $o_k$, Ziel $d_k$ und
Menge $q_k$, Kandidatenlinien $\\{i,j\\}$ mit Fixkosten $F_{ij}$, variablen Kosten $c_{ij}$
je Einheit und Kapazität $\\mathrm{cap}$ je LKW, sowie Umschlagkosten $h$ je Einheit.

Vereinfachung (siehe [linehaul_network.py](linehaul_network.py)): jede Sendung nutzt
höchstens einen Umschlagpunkt - die Routenwahl ist damit eine **diskrete Auswahl** aus
Direktroute oder Route über genau einen Hub $m$, statt eines allgemeinen Mehrgüterflusses
mit beliebig langen Pfaden. Bei Bedarf ließe sich das zu einem allgemeinen Min-Cost-Flow mit
Knoten-Split-Kosten (wie in der Liniennetz-Design-Demo für Kapazität verwendet) erweitern.

Binäre Variable $z_{k,r} \\in \\{0,1\\}$: Sendung $k$ nutzt Route $r$ (genau eine Route je
Sendung). Ganzzahlige Variable $y_{ij} \\ge 0$: Anzahl LKW auf Linie $\\{i,j\\}$.

$$
\\min \\sum_{\\{i,j\\}} F_{ij}\\, y_{ij} \\;+\\; \\sum_{k}\\sum_{r} \\Big(q_k \\sum_{(i,j)\\in r} c_{ij} \\;+\\; \\mathbb{1}[r \\text{ nutzt Hub}]\\, q_k h\\Big)\\, z_{k,r}
$$

unter $\\sum_r z_{k,r} = 1 \\;\\forall k$ und, je Linie $\\{i,j\\}$ und Richtung,

$$
\\sum_{k,r:\\, (i,j) \\in r} q_k\\, z_{k,r} \\;\\le\\; \\mathrm{cap} \\cdot y_{ij}.
$$

Kein explizites Hop-Limit über die Konstruktion hinaus nötig: die Umschlagkosten $h$
disziplinieren die Pfadlänge bereits ökonomisch - mehr Umschläge lohnen sich nur, wenn die
dadurch eingesparten Fixkosten die zusätzlichen Umschlaggebühren übersteigen.

Gelöst mit Google OR-Tools (`pywraplp`, SCIP-Backend) in
[linehaul_reference_solver.py](linehaul_reference_solver.py), auf 4 Sekunden
Rechenzeit begrenzt - bei wenigen Depots/geringer Nachfragedichte fast immer
das bewiesene Optimum, bei vielen Depots UND hoher Nachfragedichte gleichzeitig
manchmal nur die beste innerhalb des Zeitlimits gefundene Lösung (dann klar als
"Zeitlimit erreicht" gekennzeichnet, siehe README für die Laufzeitmessung).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
