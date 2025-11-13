import pandas as pd
from datetime import datetime
from pandas.tseries.offsets import DateOffset

def _read_rechnungen(rechnungen_file):
    """CSV/Excel robust einlesen (deutsches Format, ; als Separator)."""
    if rechnungen_file.name.endswith(".xlsx"):
        rechnungen = pd.read_excel(rechnungen_file)
    else:
        # CSV mit ; getrennt
        try:
            rechnungen = pd.read_csv(rechnungen_file, sep=";", encoding="utf-8")
        except Exception:
            # Fallback, falls das mal anders ist
            rechnungen = pd.read_csv(rechnungen_file)
    return rechnungen


def _prepare_columns(rechnungen: pd.DataFrame) -> pd.DataFrame:
    """Spalten auf die erwarteten Namen/Typen bringen."""
    df = rechnungen.copy()

    # Rechnungsnummer-Spalte ermitteln
    if "Rechnungsnummer" in df.columns:
        re_col = "Rechnungsnummer"
    elif "Rechnungsnr." in df.columns:
        re_col = "Rechnungsnr."
        df = df.rename(columns={"Rechnungsnr.": "Rechnungsnummer"})
    else:
        raise ValueError("Spalte 'Rechnungsnummer' bzw. 'Rechnungsnr.' nicht gefunden.")

    # Zahlungsdatum: wir nutzen 'letztes Bezahldatum' als Zahlungsdatum
    if "Zahlungsdatum" in df.columns:
        date_col = "Zahlungsdatum"
    elif "letztes Bezahldatum" in df.columns:
        date_col = "letztes Bezahldatum"
        df = df.rename(columns={"letztes Bezahldatum": "Zahlungsdatum"})
    else:
        raise ValueError("Spalte 'Zahlungsdatum' oder 'letztes Bezahldatum' nicht gefunden.")

    # Status sicherstellen
    if "Status" not in df.columns:
        raise ValueError("Spalte 'Status' nicht gefunden (erwarte z.B. 'Bezahlt' / 'Unbezahlt').")

    # Fremdleistung-Spalte ggf. anlegen
    if "Fremdleistung" not in df.columns:
        df["Fremdleistung"] = ""

    # Kunde / Projekt ggf. anlegen
    for col in ["Kunde", "Projekt"]:
        if col not in df.columns:
            df[col] = ""

    # Netto in float umwandeln (deutsches Zahlenformat: Punkt = Tausender, Komma = Dezimal)
    if "Netto" not in df.columns:
        raise ValueError("Spalte 'Netto' nicht gefunden.")

    netto_str = (
        df["Netto"]
        .astype(str)
        .str.replace(".", "", regex=False)   # Tausenderpunkt entfernen
        .str.replace(",", ".", regex=False)  # Komma -> Punkt
    )
    df["Netto"] = pd.to_numeric(netto_str, errors="coerce").fillna(0.0)

    # Zahlungsdatum in echtes Datum (Tag zuerst)
    df["Zahlungsdatum"] = pd.to_datetime(df["Zahlungsdatum"], errors="coerce", dayfirst=True)

    # Flag Fremdleistung
    df["Ist_Fremdleistung"] = (
        df["Fremdleistung"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["ja", "yes", "y"])
    )

    return df


def berechne_provisionen(rechnungen_file, provisionen_file, monate_rueckblick):
    # -------------------------
    # Dateien einlesen
    # -------------------------
    rechnungen_raw = _read_rechnungen(rechnungen_file)
    rechnungen = _prepare_columns(rechnungen_raw)

    provisionen = pd.read_excel(provisionen_file)

    # -------------------------
    # Datumslogik / Filter: nur bezahlte Rechnungen im Zeitraum
    # -------------------------
    cutoff_date = datetime.now() - DateOffset(months=monate_rueckblick)

    rechnungen = rechnungen[
        (rechnungen["Status"] == "Bezahlt") &
        (rechnungen["Zahlungsdatum"] >= cutoff_date)
    ].copy()

    # Wenn nach dem Filter nichts übrig ist → leeres Ergebnis
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
    # Ergebnisliste für alle Mitarbeiter
    # -------------------------
    alle = []

    for _, mitarbeiter in provisionen.iterrows():
        name = mitarbeiter.get("Mitarbeiter")
        provision_eigen = mitarbeiter.get("Eigenleistung", 0.0)    # % auf Eigenleistungen
        provision_fremd = mitarbeiter.get("Fremdleistung", float("nan"))  # % auf Fremdleistungen

        df = rechnungen.copy()
        df["Provision"] = 0.0

        # --- Eigenleistungen: jeder bekommt Provision ---
        mask_eigen = ~df["Ist_Fremdleistung"]
        df.loc[mask_eigen, "Provision"] = (
            df.loc[mask_eigen, "Netto"] * (float(provision_eigen) / 100.0)
        )

        # --- Fremdleistungen: nur wenn Satz vorhanden ---
        if pd.notna(provision_fremd):
            mask_fremd = df["Ist_Fremdleistung"]
            df.loc[mask_fremd, "Provision"] = (
                df.loc[mask_fremd, "Netto"] * (float(provision_fremd) / 100.0)
            )
        else:
            # Mitarbeiter bekommt keine Fremdleistungsprovision → Fremdleistungsrechnungen raus
            df = df[~df["Ist_Fremdleistung"]]

        # Nur Rechnungen mit Provision > 0 behalten
        df = df[df["Provision"] > 0]

        if df.empty:
            continue

        # Mitarbeiter setzen
        df["Mitarbeiter"] = name

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

    # Finale Spaltenauswahl
    result = result[
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

    return result
