
import pandas as pd
from datetime import datetime, timedelta

def berechne_provisionen(rechnungen_file, provisionen_file, monate_rueckblick):
    if rechnungen_file.name.endswith(".xlsx"):
        rechnungen = pd.read_excel(rechnungen_file)
    else:
        rechnungen = pd.read_csv(rechnungen_file)

    provisionen = pd.read_excel(provisionen_file)

    rechnungen["Zahlungsdatum"] = pd.to_datetime(rechnungen["Zahlungsdatum"], errors="coerce")
    cutoff_date = datetime.now() - pd.DateOffset(months=monate_rueckblick)

    # Filter: nur bezahlte Rechnungen im Zeitraum
    rechnungen = rechnungen[
        (rechnungen["Status"] == "Bezahlt") &
        (rechnungen["Zahlungsdatum"] > cutoff_date)
    ]

    merged = rechnungen.merge(provisionen, how="left", on="Mitarbeiter")
    merged["Provision"] = merged["Betrag"] * merged["Provisionssatz"] / 100

    return merged[["Mitarbeiter", "Rechnungsnummer", "Betrag", "Provision", "Zahlungsdatum"]]
