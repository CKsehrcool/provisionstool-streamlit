import streamlit as st
from io import BytesIO
from zipfile import ZipFile

from utils.logic_v2 import berechne_provisionen
from utils.pdf_generator import exportiere_pdfs_in_memory

st.set_page_config(page_title="Prämientool V2", layout="wide")
st.title("🧾 Prämientool V2 – Papierkram oder Odoo")

rechnungsdatei = st.file_uploader(
    "📂 Rechnungsdatei: Papierkram-CSV oder Odoo-Export (XLSX, Vorlage „Prämie“)",
    type=["csv", "xlsx"],
)
provisionsdatei = st.file_uploader(
    "📂 Prämiensätze je Mitarbeiter (Excel: Mitarbeiter | Eigenleistung | Fremdleistung)",
    type=["xlsx"],
)
monate_rueckblick = st.slider(
    "Zeitraum in Monaten (nur bezahlte Rechnungen ab)", min_value=1, max_value=12, value=1
)
fremd_manuell_txt = st.text_input(
    "Nur Odoo: aus Papierkram übernommene Rechnungen mit Fremdleistung (kommagetrennt)",
    value="R-00297",
    help="Übernommene Altrechnungen haben in Odoo kein Produkt und damit keine Kategorie.",
)

if "provision_df" not in st.session_state:
    st.session_state.provision_df = None

if st.button("✅ Prämien berechnen"):
    if not rechnungsdatei or not provisionsdatei:
        st.error("Bitte beide Dateien hochladen.")
    else:
        try:
            df, quelle = berechne_provisionen(
                rechnungsdatei, provisionsdatei, monate_rueckblick,
                fremd_manuell=fremd_manuell_txt.split(","),
            )
        except ValueError as e:
            st.error(str(e))
            st.stop()

        st.info(f"Erkannte Quelle: **{'Odoo' if quelle == 'odoo' else 'Papierkram'}**")
        if df.empty:
            st.warning("Keine relevanten Rechnungen für diesen Zeitraum gefunden.")
        else:
            st.session_state.provision_df = df
            st.success("Prämien berechnet.")
            st.dataframe(df)

            # Prüfsummen
            bezahlt = df[df["Status"] == "Bezahlt"]
            basis = bezahlt.drop_duplicates(["Rechnungsnummer", "Ist_Fremdleistung"])
            st.subheader("Prüfsummen (bezahlte Rechnungen)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Netto Eigenleistung", f"{basis.loc[~basis['Ist_Fremdleistung'], 'Netto'].sum():,.2f} €")
            c2.metric("Netto Fremdleistung", f"{basis.loc[basis['Ist_Fremdleistung'], 'Netto'].sum():,.2f} €")
            c3.metric("Prämie gesamt", f"{bezahlt['Provision'].sum():,.2f} €")
            st.dataframe(
                bezahlt.groupby("Mitarbeiter")["Provision"].sum().round(2).rename("Prämie €")
            )

if st.session_state.provision_df is not None:
    st.markdown("---")
    st.subheader("📤 PDF-Erzeugung")
    if st.button("📥 ZIP mit allen Mitarbeiter-PDFs erstellen"):
        pdf_dateien = exportiere_pdfs_in_memory(st.session_state.provision_df)
        if not pdf_dateien:
            st.warning("⚠️ Es wurden keine PDF-Dateien erzeugt. Prüfe die Spalte 'Mitarbeiter'.")
        else:
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, "w") as zipf:
                for dateiname, pdf_buffer in pdf_dateien:
                    zipf.writestr(dateiname, pdf_buffer.read())
            zip_buffer.seek(0)
            st.download_button(
                "📥 ZIP herunterladen", data=zip_buffer,
                file_name="praemien_export.zip", mime="application/zip",
            )
