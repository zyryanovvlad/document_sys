import streamlit as st
import os

from ocr import extract_text, extract_text_from_doc
from parser import parse_data
from db import save_company, get_companies
from generator import generate_invoice, generate_pdf

st.title("📊 Документооборот (мини 1С)")

menu = st.sidebar.selectbox("Меню", [
    "Загрузка карточки",
    "База организаций",
    "Генерация документов"
])

# --- Загрузка карточки ---
if menu == "Загрузка карточки":
    file = st.file_uploader(
        "Загрузите карточку организации",
        type=["png", "jpg", "pdf", "doc", "docx"]
    )

    if file:
        temp_dir = "temp"
        os.makedirs(temp_dir, exist_ok=True)
        ext = file.name.split(".")[-1].lower()
        path = os.path.join(temp_dir, file.name)

        with open(path, "wb") as f:
            f.write(file.read())

        st.write("Файл сохранён:", path)

        # === извлечение текста в зависимости от формата ===
        if ext in ("png", "jpg"):
            text = extract_text(path)

        elif ext in ("doc", "docx"):
            text = extract_text_from_doc(path)

        else:
            text = ""  # на всякий случай

        st.text_area("Распознанный текст", text)

        data = parse_data(text)
        st.json(data)

        if st.button("Сохранить в базу"):
            save_company(data)
            st.success("Сохранено!")

# --- База ---
elif menu == "База организаций":
    companies = get_companies()

    for c in companies:
        st.write(f"{c.id}: {c.name} | ИНН: {c.inn}")

# --- Генерация ---
elif menu == "Генерация документов":
    companies = get_companies()
    options = {f"{c.id} - {c.name}": c for c in companies}

    choice = st.selectbox("Выберите организацию", list(options.keys()))

    if choice:
        c = options[choice]

        data = {
            "Название": c.name,
            "ИНН": c.inn,
            "КПП": c.kpp,
            "БИК": c.bik,
            "Р/С": c.rs
        }

        if st.button("Сформировать DOCX"):
            file = generate_invoice(data)
            with open(file, "rb") as f:
                st.download_button("Скачать DOCX", f, file_name=file)

        if st.button("Сформировать PDF"):
            file = generate_pdf(data)
            with open(file, "rb") as f:
                st.download_button("Скачать PDF", f, file_name=file)