
import streamlit as st
import pandas as pd
from utils.logic import berechne_provisionen
from utils.pdf_generator import exportiere_pdfs_in_memory
from io import BytesIO
from zipfile import ZipFile

st.set_page_config(page_title="Provisionstool", layout="wide")
st.title("🧾 Provisionstool für Mitarbeiter")

rechnungsdatei = st.file_uploader("📂 Rechnungsdatei (CSV oder Excel)", type=["csv", "xlsx"])
provisionsdatei = st.file_uploader("📂 Provisionssätze je Mitarbeiter (Excel)", type=["xlsx"])
monate_rueckblick = st.slider("Zeitraum in Monaten (nur bezahlte Rechnungen ab)", min_value=1, max_value=12, value=1)

if "provision_df" not in st.session_state:
    st.session_state.provision_df = None

if st.button("✅ Provisionen berechnen"):
    if not rechnungsdatei or not provisionsdatei:
        st.error("Bitte beide Dateien hochladen.")
    else:
        df_provision = berechne_provisionen(rechnungsdatei, provisionsdatei, monate_rueckblick)
        if df_provision.empty:
            st.warning("Keine relevanten Rechnungen für diesen Zeitraum gefunden.")
        else:
            st.session_state.provision_df = df_provision
            st.success("Provisionen erfolgreich berechnet.")
            st.dataframe(df_provision)

# Unabhängiger PDF-Export-Button
if st.session_state.provision_df is not None:
    st.markdown("---")
    st.subheader("📤 PDF-Erzeugung")
    if st.button("📥 ZIP mit allen Mitarbeiter-PDFs herunterladen"):
        pdf_dateien = exportiere_pdfs_in_memory(st.session_state.provision_df)

        st.info(f"DEBUG: Anzahl erzeugter PDF-Dateien: {len(pdf_dateien)}")
        for name, pdf in pdf_dateien:
            st.text(f"{name}: {len(pdf.getvalue())} Bytes")

        if len(pdf_dateien) == 0:
            st.warning("⚠️ Es wurden keine PDF-Dateien erzeugt. Prüfe die Spalte 'Mitarbeiter'.")
        else:
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, "w") as zipf:
                for dateiname, pdf_buffer in pdf_dateien:
                    zipf.writestr(dateiname, pdf_buffer.read())
            zip_buffer.seek(0)

            st.download_button(
                label="📥 ZIP herunterladen",
                data=zip_buffer,
                file_name="provisionen_export.zip",
                mime="application/zip"
            )
