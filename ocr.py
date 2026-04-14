import os
import cv2
import easyocr
from win32com.client import Dispatch


# --- для DOC/DOCX ---
from docx import Document as DocxDocument
import docx2txt  # легче всего для .docx

reader = easyocr.Reader(['ru', 'en'])


def extract_text(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Файл не найден: {image_path}")

    img = cv2.imread(image_path)
    if img is None:
        raise RuntimeError(f"OpenCV не смог загрузить изображение: {image_path}")

    result = reader.readtext(image_path, detail=0)
    return "\n".join(result or [])


def extract_text_from_doc(doc_path):
    ext = doc_path.split(".")[-1].lower()

    if ext == "docx":
        try:
            text = docx2txt.process(doc_path)
            if text:
                return text
        except Exception:
            pass

        doc = DocxDocument(doc_path)
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs)

    elif ext == "doc":
        word = Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        doc = word.Documents.Open(os.path.abspath(doc_path))
        text = doc.Content.Text
        doc.Close()
        word.Quit()
        return text

    raise ValueError(f"Неподдерживаемый формат: {ext}")