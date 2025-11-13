import pandas as pd
from datetime import datetime
from pandas.tseries.offsets import DateOffset

def berechne_provisionen(rechnungen_file, provisionen_file, monate_rueckblick):
    # -------------------------
    # Dateien einlesen
    # -------------------------
    if rechnungen_file.name.endswith(".xlsx"):
        rechnungen = pd.read_excel(rechnungen_file)
    else:
        rechnungen = pd.read_csv(rechnungen_file, sep=",", decimal=".")

    provisionen = pd.read_excel(provisionen_file)

    # -------------------------
    # Datumslogik
    # -------------------------
    rechnungen["Zahlungsdatum"] = pd.to_datetime(rechnungen["Zahlungsdatum"], errors="coerce")
    cutoff_date = datetime.now() - DateOffset(months=monate_rueckblick)

    # -------------------------
    # Filter: Nur bezahlte Rechnungen im Zeitraum
    # -------------------------
    rechnungen = rechnungen[
        (rechnungen["Status"] == "Bezahlt") &
        (rechnungen["Zahlungsdatum"] >= cutoff_date)
    ]

    # -------------------------
    # Fremdleistung / Eigenleistung
    # -------------------------
    rechnungen["Ist_Fremdleistung"] = rechnungen["Fremdleistung"].fillna("").str.lower() == "ja"

    # Netto-Basis
    rechnungen["Netto"] = pd.to_numeric(rechnungen["Netto"], errors="coerce").fillna(0)

    # -------------------------
    # Ergebnisliste für alle Mitarbeiter
    # -------------------------
    alle = []

    for _, mitarbeiter in provisionen.iterrows():
        name = mitarbeiter["Mitarbeiter"]

        provision_eigen = mitarbeiter["Eigenleistung"]       # % auf Eigenleistungen
        provision_fremd = mitarbeiter["Fremdleistung"]       # % auf Fremdleistungen (oder NaN)

        df = rechnungen.copy()
        df["Provision"] = 0.0

        # --- Eigenleistungen: jeder bekommt Provision ---
        df.loc[~df["Ist_Fremdleistung"], "Provision"] = (
            df.loc[~df["Ist_Fremdleistung"], "Netto"] * (provision_eigen / 100)
        )

        # --- Fremdleistungen: nur wenn Satz vorhanden ---
        if pd.notna(provision_fremd):
            df.loc[df["Ist_Fremdleistung"], "Provision"] = (
                df.loc[df["Ist_Fremdleistung"], "Netto"] * (provision_fremd / 100)
            )
        else:
            # Mitarbeiter bekommt keine Fremdleistungsprovision
            df = df[~df["Ist_Fremdleistung"]]

        # Nur Rechnungen mit Provision behalten
        df = df[df["Provision"] > 0]

        # Mitarbeiter zuordnen
        df["Mitarbeiter"] = name

        alle.append(df)

    # Gesamttabelle
    if len(alle) > 0:
        result = pd.concat(alle, ignore_index=True)
    else:
        result = pd.DataFrame()

    # -------------------------
    # Finale Auswahl + neue Felder Kunde & Projekt
    # -------------------------
    spalten = [
        "Mitarbeiter",
        "Rechnungsnummer",
        "Kunde",
        "Projekt",
        "Netto",
        "Provision",
        "Zahlungsdatum",
        "Ist_Fremdleistung"
    ]

    # Prüfen, ob Kunde/Projekt wirklich existieren – sonst sauber auffüllen
    for s in ["Kunde", "Projekt"]:
        if s not in result.columns:
            result[s] = ""

    return result[spalten]
