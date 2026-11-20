"""
Prämienlogik Version 2.

Liest wahlweise
  - den Papierkram-Export (CSV, ;-getrennt, deutsches Zahlenformat) oder
  - den Odoo-Export (XLSX, Exportvorlage „Prämie“ aus Rechnungsstellung → Kunden → Rechnungen)
und rechnet danach genau wie utils/logic.py (Version 1):
  - Satzdatei: Mitarbeiter | Eigenleistung | Fremdleistung (Prozent)
  - Bezahlte Rechnungen: Zahlungsdatum >= heute − N Monate → Prämienbasis
  - Offene Rechnungen: Vorschau (ohne Datumsfilter, wie V1)
  - Basis: Netto

Odoo-Vorlage „Prämie“ – benötigte Felder:
  Nummer, Referenz, Kunde, Ein-/Ausgangsrechnungsdatum, Typ, Zahlungsstatus, Nettobetrag,
  Abgeglichene Zahlungen/Datum, Rechnungszeilen/Produkt/Produktkategorie,
  Rechnungszeilen/Zwischensumme
"""
from datetime import datetime

import pandas as pd
from pandas.tseries.offsets import DateOffset

ERGEBNIS_SPALTEN = [
    "Mitarbeiter", "Rechnungsnummer", "Kunde", "Projekt", "Netto",
    "Provision", "Zahlungsdatum", "Status", "Ist_Fremdleistung",
]

# Odoo-Spalten
O_NR = "Nummer"
O_REF = "Referenz"
O_KUNDE = "Kunde"
O_TYP = "Typ"
O_STATUS = "Zahlungsstatus"
O_NETTO = "Nettobetrag"
O_ZAHLDATUM = "Abgeglichene Zahlungen/Datum"
O_KATEGORIE = "Rechnungszeilen/Produkt/Produktkategorie"
O_ZEILE_NETTO = "Rechnungszeilen/Zwischensumme"

ODOO_BEZAHLT = {"Bezahlt", "In Zahlung"}
FREMD_KATEGORIE = "Fremdleistung"


# ---------------------------------------------------------------------------
# Einlesen
# ---------------------------------------------------------------------------
def _lese_datei(datei) -> pd.DataFrame:
    name = getattr(datei, "name", str(datei))
    if name.lower().endswith(".xlsx"):
        return pd.read_excel(datei)
    return pd.read_csv(datei, sep=";", encoding="utf-8")


def erkenne_quelle(df: pd.DataFrame) -> str:
    if {O_NR, O_STATUS, O_NETTO}.issubset(df.columns):
        return "odoo"
    if {"Rechnungsnr.", "Netto", "Status"}.issubset(df.columns) or "Rechnungsnummer" in df.columns:
        return "papierkram"
    raise ValueError(
        "Dateiformat nicht erkannt. Erwartet Papierkram-CSV (Rechnungsnr., Netto, Status) "
        "oder Odoo-XLSX (Nummer, Zahlungsstatus, Nettobetrag)."
    )


def _normalisiere_papierkram(r: pd.DataFrame) -> pd.DataFrame:
    """Identisch zur Aufbereitung in V1."""
    r = r.copy()
    if "Rechnungsnr." in r.columns and "Rechnungsnummer" not in r.columns:
        r = r.rename(columns={"Rechnungsnr.": "Rechnungsnummer"})
    if "Rechnungsnummer" not in r.columns:
        raise ValueError("Spalte 'Rechnungsnummer' bzw. 'Rechnungsnr.' nicht gefunden.")
    if "letztes Bezahldatum" in r.columns and "Zahlungsdatum" not in r.columns:
        r = r.rename(columns={"letztes Bezahldatum": "Zahlungsdatum"})
    if "Zahlungsdatum" not in r.columns:
        raise ValueError("Spalte 'Zahlungsdatum' oder 'letztes Bezahldatum' nicht gefunden.")
    for col in ["Status", "Netto"]:
        if col not in r.columns:
            raise ValueError(f"Spalte '{col}' nicht gefunden.")
    for col in ["Kunde", "Projekt", "Fremdleistung"]:
        if col not in r.columns:
            r[col] = ""

    r = r[r["Rechnungsnummer"].notna() & (r["Rechnungsnummer"].astype(str).str.strip() != "")]

    netto = (r["Netto"].astype(str)
             .str.replace(".", "", regex=False)
             .str.replace(",", ".", regex=False))
    r["Netto"] = pd.to_numeric(netto, errors="coerce").fillna(0.0)
    r["Zahlungsdatum"] = pd.to_datetime(r["Zahlungsdatum"], errors="coerce", dayfirst=True)
    r["Status"] = r["Status"].astype(str)
    r["Ist_Fremdleistung"] = (r["Fremdleistung"].fillna("").astype(str)
                              .str.strip().str.lower().isin(["ja", "yes", "y"]))
    return r[["Rechnungsnummer", "Kunde", "Projekt", "Netto",
              "Zahlungsdatum", "Status", "Ist_Fremdleistung"]]


def _normalisiere_odoo(r: pd.DataFrame, fremd_manuell=()) -> pd.DataFrame:
    r = r.copy()
    # Spaltennamen tolerant zuordnen (Leerzeichen, Varianten je Odoo-Version)
    r.columns = [str(c).strip() for c in r.columns]
    if O_ZAHLDATUM not in r.columns:
        kand = [c for c in r.columns if "zahlung" in c.lower() and c.lower().endswith("/datum")]
        if kand:
            r = r.rename(columns={kand[0]: O_ZAHLDATUM})
    # Kategorie kann auch direkt an der Zeile exportiert werden
    if O_KATEGORIE not in r.columns and "Rechnungszeilen/Produktkategorie" in r.columns:
        r = r.rename(columns={"Rechnungszeilen/Produktkategorie": O_KATEGORIE})
    hinweise = []
    for sp in (O_ZAHLDATUM, O_KATEGORIE, O_ZEILE_NETTO, O_REF, O_KUNDE, O_TYP):
        if sp not in r.columns:
            hinweise.append(sp)
            r[sp] = pd.NA
    if O_ZAHLDATUM in hinweise:
        raise ValueError(
            f"Spalte '{O_ZAHLDATUM}' fehlt im Odoo-Export. In der Exportvorlage "
            "'Abgeglichene Zahlungen > Datum' wählen (nicht nur 'Abgeglichene Zahlungen'). "
            f"Gefundene Spalten: {', '.join(c for c in r.columns if c not in hinweise)}"
        )

    # Kopfdaten stehen nur in der ersten Zeile je Rechnung → auffüllen
    kopf = [O_NR, O_REF, O_KUNDE, O_TYP, O_STATUS, O_NETTO]
    r[kopf] = r[kopf].ffill()

    fremd_manuell = {s.strip() for s in fremd_manuell if s and s.strip()}
    r["_fremd"] = r[O_KATEGORIE].astype(str).str.contains(FREMD_KATEGORIE, na=False)
    r["_zeile"] = r[O_ZEILE_NETTO].notna()

    zeilen = []
    for nr, g in r.groupby(O_NR, sort=False):
        k = g.iloc[0]
        status = "Bezahlt" if str(k[O_STATUS]) in ODOO_BEZAHLT else str(k[O_STATUS])
        zahldatum = pd.to_datetime(g[O_ZAHLDATUM], errors="coerce").max()
        vorzeichen = -1 if "gutschrift" in str(k[O_TYP]).lower() else 1
        basis = dict(Rechnungsnummer=nr, Kunde=k[O_KUNDE],
                     Projekt="" if pd.isna(k[O_REF]) else k[O_REF],
                     Zahlungsdatum=zahldatum, Status=status)

        if nr in fremd_manuell:
            zeilen.append({**basis, "Netto": vorzeichen * float(k[O_NETTO]),
                           "Ist_Fremdleistung": True})
            continue

        lz = g[g["_zeile"]]
        if lz.empty:  # Export ohne Zeilen → ganze Rechnung als Eigenleistung
            zeilen.append({**basis, "Netto": vorzeichen * float(k[O_NETTO]),
                           "Ist_Fremdleistung": False})
            continue

        # Je Rechnung getrennt nach Eigen/Fremd summieren (gemischte Rechnungen → 2 Zeilen)
        for ist_fremd, teil in lz.groupby("_fremd"):
            zeilen.append({**basis, "Netto": vorzeichen * float(teil[O_ZEILE_NETTO].sum()),
                           "Ist_Fremdleistung": bool(ist_fremd)})

    out = pd.DataFrame(zeilen)

    # Prüfsumme: Zeilensumme = Kopf-Netto
    kopf_netto = r.groupby(O_NR)[O_NETTO].first().sum()
    zeilen_netto = out["Netto"].abs().sum()
    if abs(kopf_netto - zeilen_netto) > 0.01:
        raise ValueError(f"Prüfsumme stimmt nicht: Kopf-Netto {kopf_netto:.2f} ≠ "
                         f"Zeilen-Netto {zeilen_netto:.2f}")
    return out


def lade_rechnungen(datei, fremd_manuell=()) -> tuple[pd.DataFrame, str]:
    roh = _lese_datei(datei)
    quelle = erkenne_quelle(roh)
    if quelle == "odoo":
        return _normalisiere_odoo(roh, fremd_manuell), quelle
    return _normalisiere_papierkram(roh), quelle


# ---------------------------------------------------------------------------
# Berechnung (Logik wie V1)
# ---------------------------------------------------------------------------
def berechne_aus_df(rechnungen: pd.DataFrame, provisionen: pd.DataFrame,
                    monate_rueckblick: int, stichtag: datetime | None = None) -> pd.DataFrame:
    stichtag = stichtag or datetime.now()
    cutoff = stichtag - DateOffset(months=monate_rueckblick)

    status = rechnungen["Status"].astype(str)
    mask_bezahlt = (status == "Bezahlt") & (rechnungen["Zahlungsdatum"] >= cutoff)
    mask_offen = status != "Bezahlt"
    rechnungen = rechnungen[mask_bezahlt | mask_offen].copy()
    if rechnungen.empty:
        return pd.DataFrame(columns=ERGEBNIS_SPALTEN)

    alle = []
    for _, row in provisionen.iterrows():
        satz_eigen = float(row.get("Eigenleistung", 0) or 0)
        satz_fremd = row.get("Fremdleistung")

        df = rechnungen.copy()
        df["Provision"] = 0.0
        m_eigen = ~df["Ist_Fremdleistung"]
        df.loc[m_eigen, "Provision"] = df.loc[m_eigen, "Netto"] * satz_eigen / 100.0

        if pd.notna(satz_fremd):
            m_fremd = df["Ist_Fremdleistung"]
            df.loc[m_fremd, "Provision"] = df.loc[m_fremd, "Netto"] * float(satz_fremd or 0) / 100.0
        else:
            df = df[~df["Ist_Fremdleistung"]]

        df = df[df["Provision"] != 0]   # V1: > 0; != 0 lässt Gutschriften zu
        if df.empty:
            continue
        df["Mitarbeiter"] = row.get("Mitarbeiter")
        alle.append(df)

    if not alle:
        return pd.DataFrame(columns=ERGEBNIS_SPALTEN)
    return pd.concat(alle, ignore_index=True)[ERGEBNIS_SPALTEN]


def berechne_provisionen(rechnungen_file, provisionen_file, monate_rueckblick,
                         fremd_manuell=()):
    rechnungen, quelle = lade_rechnungen(rechnungen_file, fremd_manuell)
    provisionen = pd.read_excel(provisionen_file)
    return berechne_aus_df(rechnungen, provisionen, monate_rueckblick), quelle
