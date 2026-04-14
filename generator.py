from docx import Document
from reportlab.pdfgen import canvas

def generate_invoice(data):
    doc = Document()
    doc.add_heading('СЧЕТ НА ОПЛАТУ', 0)

    for k, v in data.items():
        doc.add_paragraph(f"{k}: {v}")

    file = "invoice.docx"
    doc.save(file)
    return file


def generate_pdf(data, filename="output.pdf"):
    c = canvas.Canvas(filename)

    y = 800
    for k, v in data.items():
        c.drawString(100, y, f"{k}: {v}")
        y -= 20

    c.save()
    return filename