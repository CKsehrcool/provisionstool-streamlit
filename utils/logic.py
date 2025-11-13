import pandas as pd
from datetime import datetime
from pandas.tseries.offsets import DateOffset

def berechne_provisionen(rechnungen_file, provisionen_file, monate_rueckblick):
    # -------------------------
    # Rechnungen einlesen (CSV ;-getrennt, deutsches Format)
    # -------------------------
    if rechnungen_file.name.endswith(".xlsx"):
        rechnungen = pd.read_excel(rechnungen_file)
    else:
        # WICHTIG: ; als Separator benutzen
        rechnungen = pd.read_csv(rechnungen_file, sep=";", encoding="utf-8")

    # -------------------------
    # Spalten aufräumen / umbenennen
    # -------------------------
    # Rechnungsnummer
    if "Rechnungsnummer" in rechnungen.columns:
        pass
    elif "Rechnungsnr." in rechnungen.columns:
        rechnungen = rechnungen.rename(columns={"Rechnungsnr.": "Rechnungsnummer"})
    else:
        raise ValueError("Spalte 'Rechnungsnummer' bzw. 'Rechnungsnr.' nicht gefunden.")

    # Zahlungsdatum: wir nutzen 'letztes Bezahldatum' als Zahlungsdatum, wenn vorhanden
    if "Zahlungsdatum" in rechnungen.columns:
        pass
    elif "letztes Bezahldatum" in rechnungen.columns:
        rechnungen = rechnungen.rename(columns={"letztes Bezahldatum": "Zahlungsdatum"})
    else:
        raise ValueError("Spalte 'Zahlungsdatum' oder 'letztes Bezahldatum' nicht gefunden.")

    # Status
    if "Status" not in rechnungen.columns:
        raise ValueError("Spalte 'Status' nicht gefunden.")

    # Kunde / Projekt ggf. ergänzen
    for col in ["Kunde", "Projekt"]:
        if col not in rechnungen.columns:
            rechnungen[col] = ""

    # Fremdleistung-Spalte optional (falls du sie später ergänzt)
    if "Fremdleistung" not in rechnungen.columns:
        rechnungen["Fremdleistung"] = ""

    # Netto aus deutschem Format in float bringen
    if "Netto" not in rechnungen.columns:
        raise ValueError("Spalte 'Netto' nicht gefunden.")

    netto_str = (
        rechnungen["Netto"]
        .astype(str)
        .str.replace(".", "", regex=False)   # Tausenderpunkte löschen
        .str.replace(",", ".", regex=False)  # Komma -> Punkt
    )
    rechnungen["Netto"] = pd.to_numeric(netto_str, errors="coerce").fillna(0.0)

    # Datum parsen (deutsches Format)
    rechnungen["Zahlungsdatum"] = pd.to_datetime(
        rechnungen["Zahlungsdatum"], errors="coerce", dayfirst=True
    )

    # Flag Fremdleistung
    rechnungen["Ist_Fremdleistung"] = (
        rechnungen["Fremdleistung"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["ja", "yes", "y"])
    )

    # -------------------------
    # Provisionen einlesen
    # Erwartet: Mitarbeiter, Eigenleistung, Fremdleistung
    # -------------------------
    provisionen = pd.read_excel(provisionen_file)

    # -------------------------
    # Filter: nur bezahlte Rechnungen im Zeitraum
    # -------------------------
    cutoff_date = datetime.now() - DateOffset(months=monate_rueckblick)

    rechnungen = rechnungen[
        (rechnungen["Status"] == "Bezahlt") &
        (rechnungen["Zahlungsdatum"] >= cutoff_date)
    ].copy()

    if rechnungen.empty:
        return pd.DataFrame(
            columns=[
                "Mitarbeiter",
                "Rechnungsnummer",
                "Kunde",
                "Projekt",
                "Netto",
                "Provision",
                "Zahlungsdatum",
                "Ist_Fremdleistung",
            ]
        )

    # -------------------------
    # Provisionslogik pro Mitarbeiter
    # -------------------------
    alle = []

    for _, row in provisionen.iterrows():
        mitarbeiter = row.get("Mitarbeiter")
        prov_eigen = float(row.get("Eigenleistung", 0) or 0)
        prov_fremd = row.get("Fremdleistung")  # kann NaN sein

        df = rechnungen.copy()
        df["Provision"] = 0.0

        # Eigenleistung: alle Rechnungen ohne Fremdleistung
        mask_eigen = ~df["Ist_Fremdleistung"]
        df.loc[mask_eigen, "Provision"] = (
            df.loc[mask_eigen, "Netto"] * (prov_eigen / 100.0)
        )

        # Fremdleistung: nur wenn Satz vorhanden
        if pd.notna(prov_fremd):
            prov_fremd = float(prov_fremd or 0)
            mask_fremd = df["Ist_Fremdleistung"]
            df.loc[mask_fremd, "Provision"] = (
                df.loc[mask_fremd, "Netto"] * (prov_fremd / 100.0)
            )
        else:
            # keine Fremdleistungsprovision für diesen MA → Fremdleistungen raus
            df = df[~df["Ist_Fremdleistung"]]

        # nur Rechnungen mit Provision > 0 behalten
        df = df[df["Provision"] > 0]

        if df.empty:
            continue

        df["Mitarbeiter"] = mitarbeiter
        alle.append(df)

    if not alle:
        return pd.DataFrame(
            columns=[
                "Mitarbeiter",
                "Rechnungsnummer",
                "Kunde",
                "Projekt",
                "Netto",
                "Provision",
                "Zahlungsdatum",
                "Ist_Fremdleistung",
            ]
        )

    result = pd.concat(alle, ignore_index=True)

    return result[
        [
            "Mitarbeiter",
            "Rechnungsnummer",
            "Kunde",
            "Projekt",
            "Netto",
            "Provision",
            "Zahlungsdatum",
            "Ist_Fremdleistung",
        ]
    ]
