"""Plotly-Visualisierungen: Netzwerkkarte je Methode, Kostenaufschlüsselung."""

import plotly.graph_objects as go

DEPOT_COLOR = "#4C78A8"
HUB_COLOR = "#E45756"
LINE_COLOR = "#54A24B"


def build_linehaul_map(instance, result, title=""):
    fig = go.Figure()
    positions = instance.positions
    trucks = result["trucks"]
    hub_usage = result.get("hub_usage", {})
    max_trucks = max(trucks.values()) if trucks else 1

    for (i, j), n_trucks in trucks.items():
        width = 1.5 + 5 * (n_trucks / max_trucks)
        fig.add_trace(
            go.Scatter(
                x=[positions[i][0], positions[j][0]],
                y=[positions[i][1], positions[j][1]],
                mode="lines",
                line=dict(width=width, color=LINE_COLOR),
                hoverinfo="text",
                text=f"Hauptlauf-Linie {i}-{j}: {n_trucks} LKW/Tag",
                showlegend=False,
            )
        )

    node_sizes = []
    node_colors = []
    node_hover = []
    for idx in range(instance.n_depots):
        usage = hub_usage.get(idx, 0.0)
        node_sizes.append(20 + min(usage, 120) * 0.25)
        node_colors.append(HUB_COLOR if usage > 0 else DEPOT_COLOR)
        hover = f"Depot {idx}"
        if usage > 0:
            hover += f"<br>Umschlagmenge: {usage:.0f}"
        node_hover.append(hover)

    fig.add_trace(
        go.Scatter(
            x=positions[:, 0],
            y=positions[:, 1],
            mode="markers+text",
            marker=dict(size=node_sizes, color=node_colors, line=dict(width=1, color="white")),
            text=[str(i) for i in range(instance.n_depots)],
            textposition="middle center",
            textfont=dict(color="white", size=10),
            hovertext=node_hover,
            hoverinfo="text",
            showlegend=False,
        )
    )

    fig.update_layout(
        title=title,
        xaxis=dict(visible=False, showgrid=False),
        yaxis=dict(visible=False, showgrid=False),
        margin=dict(l=10, r=10, t=40, b=10),
        height=430,
    )
    return fig


def build_cost_breakdown_chart(results):
    labels = [r["label"] for r in results]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Fixkosten Linien", x=labels, y=[r["fixed_cost"] for r in results]))
    fig.add_trace(go.Bar(name="Variable Kosten", x=labels, y=[r["variable_cost"] for r in results]))
    fig.add_trace(go.Bar(name="Umschlagkosten", x=labels, y=[r["transshipment_cost"] for r in results]))
    fig.update_layout(
        barmode="stack",
        yaxis_title="Kosten (€)",
        margin=dict(l=10, r=10, t=30, b=10),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig
