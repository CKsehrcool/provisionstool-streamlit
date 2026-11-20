
# Provisionstool für Mitarbeiter

Dieses Tool berechnet monatliche Provisionen auf Basis gezahlter Rechnungen und erstellt automatisch PDF-Abrechnungen je Mitarbeiter. Die PDFs können als ZIP-Datei heruntergeladen werden.

## Inhalte

- `app.py`: Streamlit-Webanwendung
- `utils/pdf_generator.py`: PDF-Erzeugung in Memory (kompatibel mit Streamlit Cloud)
- `utils/logic.py`: Berechnungslogik der Provisionen
- `beispiel/`: Beispielhafte Input-Dateien (Rechnungen und Provisionssätze)
- `requirements.txt`: Abhängigkeiten zur Installation

## Installation

```bash
pip install -r requirements.txt
```

## Start der Anwendung

```bash
streamlit run app.py
```

## Hinweise

- Die PDF-Dateien werden in Memory erzeugt und direkt als ZIP-Datei zum Download bereitgestellt.
- Lokale Speicherung ist nicht erforderlich.

## Version 2 (Papierkram oder Odoo)

```bash
streamlit run app_v2.py
```

- `app.py` / `utils/logic.py` (V1) bleiben unverändert und laufen parallel.
- `app_v2.py` / `utils/logic_v2.py` erkennen die Quelle automatisch:
  - **Papierkram:** CSV-Export wie bisher (`;`, deutsches Zahlenformat).
  - **Odoo:** XLSX-Export aus *Rechnungsstellung → Kunden → Rechnungen*, Exportvorlage „Prämie“ mit den Feldern
    Nummer, Referenz, Kunde, Ein-/Ausgangsrechnungsdatum, Typ, Zahlungsstatus, Nettobetrag,
    **Abgeglichene Zahlungen > Datum**, **Rechnungszeilen > Produkt > Produktkategorie**, Rechnungszeilen > Zwischensumme.
- Fremdleistung in Odoo = Produktkategorie „Dienstleistungen / Fremdleistung“ (Produkte „… - Kooperationsprojekt“).
  Gemischte Rechnungen werden zeilengenau in Eigen- und Fremdanteil getrennt.
- Aus Papierkram übernommene Altrechnungen haben kein Produkt: Fremdleistung im Feld „übernommene Rechnungen mit Fremdleistung“ eintragen (Standard: R-00297).
- „In Zahlung“ zählt als bezahlt; Gutschriften gehen negativ ein.
- Prüfsumme: Netto aller Rechnungszeilen = Netto der Rechnungsköpfe, sonst Abbruch mit Meldung.
- Rechenlogik (Sätze, Zeitraum, offene Rechnungen als Vorschau) identisch zu V1; mit dem Papierkram-Export getestet: V1 = V2.
