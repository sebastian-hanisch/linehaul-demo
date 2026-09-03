"""Wiederverwendbares Panel zur Darstellung einer Methode im Methodenvergleich."""

import streamlit as st

from linehaul_pdf_export import generate_linehaul_plan_pdf
from linehaul_visualization import build_linehaul_map


def render_linehaul_panel(prefix, label, instance, result):
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gesamtkosten", f"{result['total_cost']:.0f} €")
    m2.metric("Aktive Linien", result["n_lines"])
    m3.metric("LKW gesamt", result["n_trucks_total"])
    m4.metric("Sendungen mit Umschlag", f"{result['n_shipments_transshipped']}/{result['n_shipments_total']}")

    fig = build_linehaul_map(instance, result, title=label)
    st.plotly_chart(fig, use_container_width=True, key=f"{prefix}_map")

    pdf_bytes = generate_linehaul_plan_pdf(label, instance, result)
    st.download_button(
        "📄 Netzwerkplan als PDF herunterladen",
        data=pdf_bytes,
        file_name=f"hauptlauf_plan_{prefix}.pdf",
        mime="application/pdf",
        key=f"{prefix}_pdf_download",
    )

    return result
