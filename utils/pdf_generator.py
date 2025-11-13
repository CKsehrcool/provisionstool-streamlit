from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
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

def _draw_header(c, width, height, mitarbeiter: str, title_suffix: str = ""):
    """
    Seitenkopf + Tabellenkopf zeichnen.
    title_suffix: "" / "A) ..." / "B) ..."
    Gibt neue y-Position und Spalten-X zurück.
    """
    y = height - 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Prämienabrechnung")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(40, y, f"Mitarbeiter: {mitarbeiter}")
    y -= 25

    if title_suffix:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, title_suffix)
        y -= 20

    # Tabellenkopf
    c.setFont("Helvetica-Bold", 9)

    # Querformat → mehr Breite nutzen
    # [Re-Nr., Kunde, Projekt, Datum, Art, Netto, Prämie]
    col_x = [
        40,    # Rechnungsnummer
        120,   # Kunde
        280,   # Projekt
        480,   # Datum
        540,   # Art
        600,   # Netto
        700,   # Prämie
    ]
    headers = ["Re-Nr.", "Kunde", "Projekt", "Datum", "Art", "Netto", "Prämie"]

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
      - Provision  (wird als Prämie ausgegeben)
      - Zahlungsdatum
      - Status
      - Ist_Fremdleistung (bool)

    Block A: Bezahlte Rechnungen (Auszahlungsbasis)
    Block B: Offene Rechnungen (Prämienvorschau, nicht in Auszahlungssumme)
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
            # Querformat A4
            c = canvas.Canvas(buffer, pagesize=landscape(A4))
            width, height = landscape(A4)

            # nach Datum, dann Rechnungsnummer sortieren
            gruppe = gruppe.sort_values(by=["Zahlungsdatum", "Rechnungsnummer"])

            # in bezahlt / offen splitten
            status = gruppe["Status"].astype(str)
            paid = gruppe[status == "Bezahlt"].copy()
            open_ = gruppe[status != "Bezahlt"].copy()

            # -------------------------
            # Block A: bezahlte Rechnungen
            # -------------------------
            y, col_x = _draw_header(
                c, width, height, mitarbeiter,
                "A) Bezahlte Rechnungen – Prämienbasis"
            )
            c.setFont("Helvetica", 9)

            total_netto_paid = 0.0
            total_praemie_paid = 0.0

            for _, row in paid.iterrows():
                if y < 60:
                    c.showPage()
                    y, col_x = _draw_header(
                        c, width, height, mitarbeiter,
                        "A) Bezahlte Rechnungen – Prämienbasis"
                    )
                    c.setFont("Helvetica", 9)

                re_nr = str(row.get("Rechnungsnummer", ""))
                kunde = str(row.get("Kunde", ""))[:35]
                projekt = str(row.get("Projekt", ""))[:35]
                datum = _format_date(row.get("Zahlungsdatum"))
                art = "Fremd" if bool(row.get("Ist_Fremdleistung")) else "Eigen"
                netto = float(row.get("Netto", 0.0) or 0.0)
                praemie = float(row.get("Provision", 0.0) or 0.0)

                total_netto_paid += netto
                total_praemie_paid += praemie

                values = [
                    re_nr,
                    kunde,
                    projekt,
                    datum,
                    art,
                    _format_eur(netto),
                    _format_eur(praemie),
                ]

                for x, v in zip(col_x, values):
                    c.drawString(x, y, str(v))

                y -= 15

            # Summenzeile für bezahlte Rechnungen
            if y < 80:
                c.showPage()
                y, col_x = _draw_header(
                    c, width, height, mitarbeiter,
                    "A) Bezahlte Rechnungen – Prämienbasis"
                )
                c.setFont("Helvetica", 9)
                y -= 10

            y -= 5
            c.line(40, y, width - 40, y)
            y -= 15
            c.setFont("Helvetica-Bold", 10)
            c.drawString(40, y, "Summe auszuzahlende Prämie:")
            c.drawString(col_x[5], y, _format_eur(total_netto_paid))
            c.drawString(col_x[6], y, _format_eur(total_praemie_paid))

            # -------------------------
            # Block B: offene Rechnungen (Prämienvorschau)
            # -------------------------
            if not open_.empty:
                c.showPage()
                y, col_x = _draw_header(
                    c, width, height, mitarbeiter,
                    "B) Offene Rechnungen – Prämienvorschau (nicht auszahlungsrelevant)"
                )
                c.setFont("Helvetica", 9)

                total_netto_open = 0.0
                total_praemie_open = 0.0

                for _, row in open_.iterrows():
                    if y < 60:
                        c.showPage()
                        y, col_x = _draw_header(
                            c, width, height, mitarbeiter,
                            "B) Offene Rechnungen – Prämienvorschau (nicht auszahlungsrelevant)"
                        )
                        c.setFont("Helvetica", 9)

                    re_nr = str(row.get("Rechnungsnummer", ""))
                    kunde = str(row.get("Kunde", ""))[:35]
                    projekt = str(row.get("Projekt", ""))[:35]
                    datum = _format_date(row.get("Zahlungsdatum"))
                    art = "Fremd" if bool(row.get("Ist_Fremdleistung")) else "Eigen"
                    netto = float(row.get("Netto", 0.0) or 0.0)
                    praemie = float(row.get("Provision", 0.0) or 0.0)

                    total_netto_open += netto
                    total_praemie_open += praemie

                    values = [
                        re_nr,
                        kunde,
                        projekt,
                        datum,
                        art,
                        _format_eur(netto),
                        _format_eur(praemie),
                    ]

                    for x, v in zip(col_x, values):
                        c.drawString(x, y, str(v))

                    y -= 15

                # Summenzeile Vorschau
                if y < 80:
                    c.showPage()
                    y, col_x = _draw_header(
                        c, width, height, mitarbeiter,
                        "B) Offene Rechnungen – Prämienvorschau (nicht auszahlungsrelevant)"
                    )
                    c.setFont("Helvetica", 9)
                    y -= 10

                y -= 5
                c.line(40, y, width - 40, y)
                y -= 15
                c.setFont("Helvetica-Bold", 10)
                c.drawString(40, y, "Summe Prämienvorschau (offene Rechnungen):")
                c.drawString(col_x[5], y, _format_eur(total_netto_open))
                c.drawString(col_x[6], y, _format_eur(total_praemie_open))

            c.save()
            buffer.seek(0)
            dateiname = f"praemie_{str(mitarbeiter).replace(' ', '_')}.pdf"
            dateien.append((dateiname, buffer))

        except Exception as e:
            print(f"❌ Fehler bei PDF für {mitarbeiter}: {e}")

    return dateien
