
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
