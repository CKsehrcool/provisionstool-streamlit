from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pandas as pd

def _format_eur(value: float) -> str:
    """Zahl als € mit deutschem Dezimalformat."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    s = f"{value:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"

def _format_date(dt) -> str:
    """Datum im Format TT.MM.JJJJ."""
    if pd.isna(dt):
        return ""
    try:
        return pd.to_datetime(dt).strftime("%d.%m.%Y")
    except Exception:
        return str(dt)

def _draw_header(c, width, height, mitarbeiter: str):
    """Seitenkopf + Tabellenkopf zeichnen, gibt neue y-Position und Spalten-X zurück."""
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Provisionsabrechnung")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(40, y, f"Mitarbeiter: {mitarbeiter}")
    y -= 30

    # Tabellenkopf
    c.setFont("Helvetica-Bold", 9)
    headers = ["Re-Nr.", "Kunde", "Projekt", "Datum", "Art", "Netto", "Provision"]
    col_x = [40, 90, 230, 370, 420, 460, 520]

    for x, h in zip(col_x, headers):
        c.drawString(x, y, h)

    y -= 5
    c.line(40, y, width - 40, y)
    y -= 15
    return y, col_x

def exportiere_pdfs_in_memory(df):
    """
    Erwartet ein DataFrame mit mindestens:
      - Mitarbeiter
      - Rechnungsnummer
      - Kunde
      - Projekt
      - Netto
      - Provision
      - Zahlungsdatum
      - Status
      - Ist_Fremdleistung (bool)

    Block A: Bezahlte Rechnungen (Auszahlungsbasis)
    Block B: Offene Rechnungen (Vorschau, nicht in Auszahlungssumme enthalten)
    """
    dateien = []

    if df is None or df.empty:
        return dateien

    required_cols = [
        "Mitarbeiter",
        "Rechnungsnummer",
        "Kunde",
        "Projekt",
        "Netto",
        "Provision",
        "Zahlungsdatum",
        "Status",
        "Ist_Fremdleistung",
    ]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Spalte '{col}' fehlt im DataFrame für die PDF-Erstellung.")

    for mitarbeiter, gruppe in df.groupby("Mitarbeiter"):
        try:
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4

            # nach Datum, dann Rechnungsnummer sortieren
            gruppe = gruppe.sort_values(by=["Zahlungsdatum", "Rechnungsnummer"])

            # in bezahlt / offen splitten
            status = gruppe["Status"].astype(str)
            paid = gruppe[status == "Bezahlt"].copy()
            open_ = gruppe[status != "Bezahlt"].copy()

            # Initiale Seite + Kopf für Block A
            y, col_x = _draw_header(c, width, height, mitarbeiter)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(40, y + 10, "A) Bezahlte Rechnungen (Auszahlungsbasis)")
            c.setFont("Helvetica", 9)
            y -= 15

            total_netto_paid = 0.0
            total_prov_paid = 0.0

            # -------------------------
            # Block A: bezahlte Rechnungen
            # -------------------------
            for _, row in paid.iterrows():
                if y < 60:
                    c.showPage()
                    y, col_x = _draw_header(c, width, height, mitarbeiter)
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(40, y + 10, "A) Bezahlte Rechnungen (Auszahlungsbasis)")
                    c.setFont("Helvetica", 9)
                    y -= 15

                re_nr = str(row.get("Rechnungsnummer", ""))
                kunde = str(row.get("Kunde", ""))[:35]
                projekt = str(row.get("Projekt", ""))[:35]
                datum = _format_date(row.get("Zahlungsdatum"))
                art = "Fremd" if bool(row.get("Ist_Fremdleistung")) else "Eigen"
                netto = float(row.get("Netto", 0.0) or 0.0)
                prov = float(row.get("Provision", 0.0) or 0.0)

                total_netto_paid += netto
                total_prov_paid += prov

                values = [
                    re_nr,
                    kunde,
                    projekt,
                    datum,
                    art,
                    _format_eur(netto),
                    _format_eur(prov),
                ]

                for x, v in zip(col_x, values):
                    c.drawString(x, y, str(v))

                y -= 15

            # Summenzeile für bezahlte Rechnungen
            if y < 80:
                c.showPage()
                y, col_x = _draw_header(c, width, height, mitarbeiter)
                c.setFont("Helvetica-Bold", 11)
                c.drawString(40, y + 10, "A) Bezahlte Rechnungen (Auszahlungsbasis)")
                c.setFont("Helvetica", 9)
                y -= 25

            y -= 5
            c.line(40, y, width - 40, y)
            y -= 15
            c.setFont("Helvetica-Bold", 10)
            c.drawString(40, y, "Summe auszuzahlende Provision:")
            c.drawString(col_x[5], y, _format_eur(total_netto_paid))
            c.drawString(col_x[6], y, _format_eur(total_prov_paid))

            # -------------------------
            # Block B: offene Rechnungen (Vorschau)
            # -------------------------
            if not open_.empty:
                c.showPage()
                y, col_x = _draw_header(c, width, height, mitarbeiter)
                c.setFont("Helvetica-Bold", 11)
                c.drawString(40, y + 10, "B) Offene Rechnungen (Provisionsvorschau – nicht auszahlungsrelevant)")
                c.setFont("Helvetica", 9)
                y -= 15

                total_netto_open = 0.0
                total_prov_open = 0.0

                for _, row in open_.iterrows():
                    if y < 60:
                        c.showPage()
                        y, col_x = _draw_header(c, width, height, mitarbeiter)
                        c.setFont("Helvetica-Bold", 11)
                        c.drawString(40, y + 10, "B) Offene Rechnungen (Provisionsvorschau – nicht auszahlungsrelevant)")
                        c.setFont("Helvetica", 9)
                        y -= 15

                    re_nr = str(row.get("Rechnungsnummer", ""))
                    kunde = str(row.get("Kunde", ""))[:35]
                    projekt = str(row.get("Projekt", ""))[:35]
                    datum = _format_date(row.get("Zahlungsdatum"))
                    art = "Fremd" if bool(row.get("Ist_Fremdleistung")) else "Eigen"
                    netto = float(row.get("Netto", 0.0) or 0.0)
                    prov = float(row.get("Provision", 0.0) or 0.0)

                    total_netto_open += netto
                    total_prov_open += prov

                    values = [
                        re_nr,
                        kunde,
                        projekt,
                        datum,
                        art,
                        _format_eur(netto),
                        _format_eur(prov),
                    ]

                    for x, v in zip(col_x, values):
                        c.drawString(x, y, str(v))

                    y -= 15

                # Summenzeile Vorschau
                if y < 80:
                    c.showPage()
                    y, col_x = _draw_header(c, width, height, mitarbeiter)
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(40, y + 10, "B) Offene Rechnungen (Provisionsvorschau – nicht auszahlungsrelevant)")
                    c.setFont("Helvetica", 9)
                    y -= 25

                y -= 5
                c.line(40, y, width - 40, y)
                y -= 15
                c.setFont("Helvetica-Bold", 10)
                c.drawString(40, y, "Summe Provisionsvorschau (offene Rechnungen):")
                c.drawString(col_x[5], y, _format_eur(total_netto_open))
                c.drawString(col_x[6], y, _format_eur(total_prov_open))

            c.save()
            buffer.seek(0)
            dateiname = f"provision_{str(mitarbeiter).replace(' ', '_')}.pdf"
            dateien.append((dateiname, buffer))

        except Exception as e:
            print(f"❌ Fehler bei PDF für {mitarbeiter}: {e}")

    return dateien
