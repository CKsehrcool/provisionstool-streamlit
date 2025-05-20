
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def exportiere_pdfs_in_memory(df):
    dateien = []

    for mitarbeiter, gruppe in df.groupby("Mitarbeiter"):
        try:
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4

            y = height - 50
            c.setFont("Helvetica", 14)
            c.drawString(50, y, f"Provisionsabrechnung – {mitarbeiter}")
            y -= 30
            c.setFont("Helvetica", 11)

            for _, row in gruppe.iterrows():
                zeile = f"Rechnung {row['Rechnungsnummer']}: {row['Provision']:.2f} € (Betrag: {row['Betrag']} €)"
                c.drawString(50, y, zeile)
                y -= 20
                if y < 50:
                    c.showPage()
                    y = height - 50

            c.save()
            buffer.seek(0)
            dateiname = f"provision_{mitarbeiter.replace(' ', '_')}.pdf"
            dateien.append((dateiname, buffer))

        except Exception as e:
            print(f"❌ Fehler bei PDF für {mitarbeiter}: {e}")

    return dateien
