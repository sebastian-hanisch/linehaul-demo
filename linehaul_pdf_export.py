"""PDF-Export des Hauptlauf-Netzwerkplans (fpdf2, Helvetica-Kernfont)."""

import time


def generate_linehaul_plan_pdf(label, instance, result):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Hauptlauf-Netzwerkplan", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Methode: {label}  -  Erstellt: {time.strftime('%d.%m.%Y %H:%M')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Zusammenfassung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    summary_rows = [
        ("Gesamtkosten", f"{result['total_cost']:.0f} EUR"),
        ("Fixkosten Linien", f"{result['fixed_cost']:.0f} EUR"),
        ("Variable Transportkosten", f"{result['variable_cost']:.0f} EUR"),
        ("Umschlagkosten", f"{result['transshipment_cost']:.0f} EUR"),
        ("Aktive Hauptlauf-Linien", str(result["n_lines"])),
        ("LKW gesamt", str(result["n_trucks_total"])),
        ("Sendungen mit Umschlag", f"{result['n_shipments_transshipped']} von {result['n_shipments_total']}"),
        ("Durchschnittliche Auslastung", f"{result['utilization'] * 100:.0f}%"),
    ]
    for label_text, value_text in summary_rows:
        pdf.cell(80, 7, label_text, border=0)
        pdf.cell(0, 7, value_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Aktive Hauptlauf-Linien", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 9)
    headers = ["Linie", "LKW/Tag", "Fluss hin", "Fluss zurück", "Distanz (km)"]
    widths = [40, 25, 30, 30, 30]
    pdf.set_fill_color(230, 230, 230)
    for header, width in zip(headers, widths):
        pdf.cell(width, 7, header, border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(7)

    pdf.set_font("Helvetica", "", 9)
    for (i, j), n_trucks in sorted(result["trucks"].items()):
        line = instance.line_between(i, j)
        forward = result["forward_flow"].get((i, j), 0.0)
        backward = result["backward_flow"].get((i, j), 0.0)
        row = [f"Depot {i} - Depot {j}", str(n_trucks), f"{forward:.0f}", f"{backward:.0f}", f"{line.distance:.1f}"]
        for value, width in zip(row, widths):
            pdf.cell(width, 7, value, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)

    return bytes(pdf.output())
