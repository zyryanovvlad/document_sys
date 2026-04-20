import streamlit as st
import os
from datetime import datetime
import json

from ocr import extract_text, extract_text_from_doc
from parser import parse_data
from db import (
    save_company, get_companies, save_invoice, get_invoices,
    get_company_by_id, update_company, delete_company,
    get_setting, save_setting, get_next_invoice_number, delete_invoice
)
from invoice_generator import generate_invoice_pdf

st.set_page_config(page_title="Документооборот", layout="wide")
st.title("📊 Документооборот (мини 1С)")

# Инициализация состояния
if 'editing_company_id' not in st.session_state:
    st.session_state.editing_company_id = None
if 'editing_invoice_id' not in st.session_state:
    st.session_state.editing_invoice_id = None
if 'product_list' not in st.session_state:
    st.session_state.product_list = [{"name": "", "quantity": 1, "price": 0.01}]

menu = st.sidebar.selectbox("Меню", [
    "Загрузка карточки",
    "База организаций",
    "Генерация счета",
    "База счетов",
    "Настройки"
])

# --- Загрузка карточки ---
if menu == "Загрузка карточки":
    st.header("📄 Загрузка карточки организации")

    file = st.file_uploader(
        "Загрузите карточку организации",
        type=["png", "jpg", "jpeg", "pdf", "doc", "docx"]
    )

    if file:
        temp_dir = "temp"
        os.makedirs(temp_dir, exist_ok=True)
        ext = file.name.split(".")[-1].lower()
        path = os.path.join(temp_dir, file.name)

        with open(path, "wb") as f:
            f.write(file.read())

        st.success(f"✅ Файл сохранён")

        with st.spinner("Распознаю текст..."):
            if ext in ("png", "jpg", "jpeg"):
                text = extract_text(path)
            elif ext in ("doc", "docx"):
                text = extract_text_from_doc(path)
            else:
                text = ""

        st.subheader("📝 Распознанный текст")
        st.text_area("", text, height=200)

        data = parse_data(text)

        st.subheader("🏢 Извлеченные данные")

        col1, col2 = st.columns(2)
        with col1:
            short_name = st.text_input("Краткое наименование", data.get("Наименование организации", "Не найдено"))
            inn = st.text_input("ИНН", data.get("ИНН", ""))
            kpp = st.text_input("КПП", data.get("КПП", ""))
        with col2:
            address = st.text_area("Юридический адрес", data.get("Юридический адрес", ""), height=100)
            bik = st.text_input("БИК", data.get("БИК", ""))
            rs = st.text_input("Р/С", data.get("Р/С", ""))

        if st.button("💾 Сохранить в базу", type="primary"):
            updated_data = {
                "Наименование организации": short_name,
                "ИНН": inn,
                "КПП": kpp,
                "Юридический адрес": address,
                "БИК": bik,
                "Р/С": rs
            }
            save_company(updated_data)
            st.success("✅ Организация сохранена!")
            st.balloons()

# --- База организаций ---
elif menu == "База организаций":
    st.header("📋 База организаций")

    companies = get_companies()

    if not companies:
        st.info("📌 База пуста.")
    else:
        if st.button("➕ Добавить организацию вручную"):
            st.session_state.editing_company_id = "new"
            st.rerun()

        st.divider()

        for c in companies:
            if st.session_state.editing_company_id == c.id:
                with st.form(key=f"edit_form_{c.id}"):
                    st.subheader(f"✏️ Редактирование: {c.name}")

                    new_name = st.text_input("Краткое наименование", value=c.name)
                    new_inn = st.text_input("ИНН", value=c.inn or "")
                    new_kpp = st.text_input("КПП", value=c.kpp or "")
                    new_bik = st.text_input("БИК", value=c.bik or "")
                    new_rs = st.text_input("Р/С", value=c.rs or "")
                    new_address = st.text_area("Юридический адрес", value=c.legal_address or "", height=100)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.form_submit_button("✅ Сохранить"):
                            updated_data = {
                                "name": new_name,
                                "inn": new_inn,
                                "kpp": new_kpp,
                                "bik": new_bik,
                                "rs": new_rs,
                                "legal_address": new_address
                            }
                            if update_company(c.id, updated_data):
                                st.success("✅ Данные обновлены!")
                                st.session_state.editing_company_id = None
                                st.rerun()
                    with col2:
                        if st.form_submit_button("❌ Отмена"):
                            st.session_state.editing_company_id = None
                            st.rerun()
                    with col3:
                        if st.form_submit_button("🗑️ Удалить"):
                            if delete_company(c.id):
                                st.success(f"✅ Организация удалена!")
                                st.session_state.editing_company_id = None
                                st.rerun()
            else:
                with st.expander(f"🏢 {c.name}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**ИНН:** {c.inn or '—'}")
                        st.write(f"**КПП:** {c.kpp or '—'}")
                        st.write(f"**Юридический адрес:** {c.legal_address or '—'}")
                    with col2:
                        if st.button("✏️ Редактировать", key=f"edit_btn_{c.id}"):
                            st.session_state.editing_company_id = c.id
                            st.rerun()

        if st.session_state.editing_company_id == "new":
            with st.form(key="add_new_form"):
                st.subheader("➕ Добавление новой организации")

                new_name = st.text_input("Краткое наименование*")
                new_inn = st.text_input("ИНН")
                new_kpp = st.text_input("КПП")
                new_bik = st.text_input("БИК")
                new_rs = st.text_input("Р/С")
                new_address = st.text_area("Юридический адрес", height=100)

                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 Сохранить"):
                        if new_name:
                            data = {
                                "Наименование организации": new_name,
                                "ИНН": new_inn,
                                "КПП": new_kpp,
                                "БИК": new_bik,
                                "Р/С": new_rs,
                                "Юридический адрес": new_address
                            }
                            save_company(data)
                            st.success("✅ Организация добавлена!")
                            st.session_state.editing_company_id = None
                            st.rerun()
                        else:
                            st.error("❌ Наименование обязательно!")
                with col2:
                    if st.form_submit_button("❌ Отмена"):
                        st.session_state.editing_company_id = None
                        st.rerun()

# --- Генерация счета ---
elif menu == "Генерация счета":
    st.header("💰 Генерация счета на оплату")

    companies = get_companies()

    if not companies:
        st.warning("⚠️ Нет организаций в базе.")
    else:
        col1, col2 = st.columns([2, 1])

        with col1:
            company_options = {f"{c.name} (ИНН: {c.inn})": c for c in companies}
            selected = st.selectbox("Выберите организацию (покупателя)", list(company_options.keys()))
            selected_company = company_options[selected]

        with col2:
            # Настройка номера счета
            next_number = get_next_invoice_number()
            invoice_number = st.number_input("Номер счета", min_value=1, value=next_number, step=1)

        st.divider()

        with st.expander("📋 Реквизиты организации", expanded=False):
            st.write(f"**Наименование:** {selected_company.name}")
            st.write(f"**ИНН:** {selected_company.inn}")
            st.write(f"**КПП:** {selected_company.kpp}")
            st.write(f"**Юридический адрес:** {selected_company.legal_address}")

        st.divider()

        # Конфигурация оборудования
        configuration = st.text_area("⚙️ Конфигурация оборудования",
                                     placeholder="Введите технические характеристики, комплектацию и т.д.", height=100)

        st.divider()

        # Список товаров
        st.subheader("📦 Товары/услуги")

        # Отображение списка товаров
        for idx, item in enumerate(st.session_state.product_list):
            col1, col2, col3, col4 = st.columns([4, 1, 1, 0.5])
            with col1:
                item["name"] = st.text_input(f"Наименование", value=item["name"], key=f"name_{idx}")
            with col2:
                item["quantity"] = st.number_input(f"Кол-во", min_value=1, value=item["quantity"], key=f"qty_{idx}")
            with col3:
                current_price = float(item["price"]) if float(item["price"]) >= 0.01 else 0.01
                item["price"] = st.number_input(f"Цена", min_value=0.01, value=current_price, key=f"price_{idx}", format="%.2f")
            with col4:
                if st.button("🗑️", key=f"del_{idx}"):
                    st.session_state.product_list.pop(idx)
                    st.rerun()

        # Кнопка добавления товара
        if st.button("➕ Добавить товар"):
            st.session_state.product_list.append({"name": "", "quantity": 1, "price": 0.01})
            st.rerun()

        # Расчет итога
        total_amount = sum(item["quantity"] * item["price"] for item in st.session_state.product_list if item["name"])
        st.metric("💰 Итого к оплате", f"{total_amount:,.2f} ₽")

        st.divider()

        if st.button("🧾 Сформировать счет", type="primary"):
            # Проверка наличия товаров
            valid_items = [item for item in st.session_state.product_list if item["name"]]
            if not valid_items:
                st.error("❌ Добавьте хотя бы один товар!")
            else:
                invoice_data = {
                    "invoice_number": str(invoice_number),
                    "company_name": selected_company.name,
                    "inn": selected_company.inn,
                    "kpp": selected_company.kpp,
                    "legal_address": selected_company.legal_address,
                    "configuration": configuration,
                    "items": valid_items
                }

                try:
                    with st.spinner("Формирую счет..."):
                        pdf_path = generate_invoice_pdf(invoice_data)

                        # Сохраняем в БД
                        save_invoice({
                            "invoice_number": str(invoice_number),
                            "company_id": selected_company.id,
                            "company_name": selected_company.name,
                            "total_amount": total_amount,
                            "items": json.dumps(valid_items, ensure_ascii=False),
                            "configuration": configuration,
                            "file_path": pdf_path
                        })

                        st.success(f"✅ Счет №{invoice_number} успешно сформирован!")

                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="📥 Скачать PDF",
                                data=f,
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf"
                            )

                        # Очищаем список товаров после успешного создания счета
                        st.session_state.product_list = [{"name": "", "quantity": 1, "price": 0.01}]
                        st.balloons()

                except Exception as e:
                    st.error(f"❌ Ошибка: {str(e)}")

# --- База счетов ---
elif menu == "База счетов":
    st.header("📜 База выставленных счетов")

    invoices = get_invoices()

    if not invoices:
        st.info("📌 Счета еще не выставлялись.")
    else:
        # Статистика
        total_sum = sum(inv.total_amount for inv in invoices)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Всего счетов", len(invoices))
        with col2:
            st.metric("Общая сумма", f"{total_sum:,.2f} ₽")
        with col3:
            avg_amount = total_sum / len(invoices) if invoices else 0
            st.metric("Средняя сумма", f"{avg_amount:,.2f} ₽")

        st.divider()

        # Поиск
        search = st.text_input("🔍 Поиск по номеру счета или организации", placeholder="Введите номер или название...")

        # Фильтрация
        filtered_invoices = invoices
        if search:
            filtered_invoices = [inv for inv in invoices if
                                 search.lower() in inv.invoice_number.lower() or search.lower() in inv.company_name.lower()]

        # Отображение счетов
        for inv in filtered_invoices:
            items_list = json.loads(inv.items) if inv.items else []
            total = sum(item.get("quantity", 0) * item.get("price", 0) for item in items_list)

            with st.expander(
                    f"🧾 Счет №{inv.invoice_number} - {inv.company_name} от {inv.created_at.strftime('%d.%m.%Y %H:%M')}"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.write(f"**Сумма:** {total:,.2f} ₽")
                    st.write(f"**Товары:**")
                    for item in items_list:
                        st.write(
                            f"  • {item.get('name', '')} - {item.get('quantity', 0)} шт x {item.get('price', 0):,.2f} ₽ = {item.get('quantity', 0) * item.get('price', 0):,.2f} ₽")

                    if inv.configuration:
                        st.write(f"**Конфигурация:** {inv.configuration}")

                with col2:
                    if inv.file_path and os.path.exists(inv.file_path):
                        with open(inv.file_path, "rb") as f:
                            st.download_button(
                                label="📥 Скачать PDF",
                                data=f,
                                file_name=os.path.basename(inv.file_path),
                                key=f"download_{inv.id}"
                            )

                    if st.button("🗑️ Удалить счет", key=f"del_inv_{inv.id}"):
                        if delete_invoice(inv.id):
                            st.success(f"✅ Счет №{inv.invoice_number} удален!")
                            st.rerun()

        if search:
            st.caption(f"Найдено {len(filtered_invoices)} из {len(invoices)} счетов")

# --- Настройки ---
elif menu == "Настройки":
    st.header("⚙️ Настройки системы")

    st.subheader("Нумерация счетов")

    current_start = get_setting("invoice_start_number", "24044")
    new_start = st.number_input("Начальный номер счета", min_value=1, value=int(current_start), step=1)

    if st.button("💾 Сохранить настройки"):
        save_setting("invoice_start_number", str(new_start))
        st.success("✅ Настройки сохранены!")
        st.balloons()

    st.divider()
    st.subheader("Информация о системе")
    st.write(f"**Всего организаций в базе:** {len(get_companies())}")
    st.write(f"**Всего счетов выставлено:** {len(get_invoices())}")