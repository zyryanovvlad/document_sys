import streamlit as st
import os
import tempfile
import tkinter as tk
from tkinter import filedialog
import re
import shutil
from datetime import datetime

from ocr import extract_text, extract_text_from_doc
from parser import parse_data
from db import (
    save_company, get_companies, get_company_by_id, update_company, delete_company,
    get_invoices_by_company, save_invoice, get_invoices, delete_invoice,
    get_setting, save_setting, get_next_invoice_number, update_invoice  # ← добавить update_invoice
)
from generator import (
    generate_invoice,
    generate_pdf,
    fill_excel_invoice_with_multiple_items,
    fill_excel_invoice_with_markup
)

st.set_page_config(page_title="Документооборот", page_icon="📊", layout="wide")

# ==================== ИНИЦИАЛИЗАЦИЯ SESSION STATE ====================
# Проверяем и инициализируем все переменные состояния

# Для главной страницы
if 'show_upload_card' not in st.session_state:
    st.session_state.show_upload_card = False

if 'selected_company_for_invoice' not in st.session_state:
    st.session_state.selected_company_for_invoice = None

if 'show_product_form' not in st.session_state:
    st.session_state.show_product_form = False

if 'show_upload_in_invoice' not in st.session_state:
    st.session_state.show_upload_in_invoice = False

if 'show_manual_company' not in st.session_state:
    st.session_state.show_manual_company = False

# Для доставки и наценки
if 'delivery_cost' not in st.session_state:
    st.session_state.delivery_cost = 0.0

if 'delivery_type' not in st.session_state:
    st.session_state.delivery_type = "Самовывоз"

if 'markup_percent' not in st.session_state:
    st.session_state.markup_percent = 0.0

# Для списка товаров
if 'product_list' not in st.session_state:
    st.session_state.product_list = [{"name": "", "config": "", "quantity": 1, "price": 0.01}]

# Для базы организаций
if 'editing_company_id' not in st.session_state:
    st.session_state.editing_company_id = None

# Для настроек
if 'show_settings' not in st.session_state:
    st.session_state.show_settings = False

if 'editing_invoice_id' not in st.session_state:
    st.session_state.editing_invoice_id = None

# ==================== КОНЕЦ ИНИЦИАЛИЗАЦИИ ====================

# Создаём временную директорию
temp_dir = "temp"
os.makedirs(temp_dir, exist_ok=True)


def select_folder_via_dialog():
    """
    Открывает стандартное окно Windows для выбора папки.
    ВНИМАНИЕ: Окно открывается на сервере (на вашем компьютере),
    а не в браузере пользователя.
    """
    # Создаём корневое окно tkinter и сразу его прячем
    root = tk.Tk()
    root.withdraw()  # Прячем главное окно

    # Поднимаем окно выбора поверх всех остальных окон
    root.wm_attributes('-topmost', 1)

    # Открываем диалог выбора папки
    # Если пользователь нажмёт "Отмена", вернётся пустая строка
    selected_path = filedialog.askdirectory(master=root, title="Выберите папку для сохранения счетов")

    # Закрываем tkinter
    root.destroy()

    return selected_path if selected_path else ""


# --- Настройки ---
def get_invoice_folder():
    folder = get_setting("invoice_folder", "generated_invoices")
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    return folder


def set_invoice_folder(folder):
    if folder:
        os.makedirs(folder, exist_ok=True)
        save_setting("invoice_folder", folder)


# --- Сайдбар с шестерёнкой ---
with st.sidebar:
    st.title("📊 Документооборот")

    col1, col2 = st.columns([4, 1])
    with col1:
        menu = st.selectbox("Меню", [
            "Главная",
            "База организаций",
            "База счетов"
        ])
    with col2:
        if st.button("⚙️", help="Настройки"):
            st.session_state.show_settings = not st.session_state.get('show_settings', False)

    # --- НАСТРОЙКИ ---
    if st.session_state.get('show_settings', False):
        st.divider()
        st.subheader("⚙️ Настройки")

        # ===== ВЫБОР ПАПКИ ДЛЯ СЧЕТОВ =====
        st.subheader("📁 Папка для сохранения счетов")

        current_folder = get_invoice_folder()
        st.caption(f"📁 Текущая папка: `{current_folder}`")

        # Кнопка для выбора папки через диалоговое окно
        if st.button("🗂️ Выбрать папку на диске", use_container_width=True):
            selected = select_folder_via_dialog()
            if selected:
                set_invoice_folder(selected)
                st.success(f"✅ Папка изменена на: {selected}")
                st.rerun()
            else:
                st.warning("⚠️ Папка не выбрана")

        # Ручной ввод пути (как запасной вариант)
        new_folder = st.text_input("Или введите путь вручную", value=current_folder)
        if st.button("💾 Сохранить путь вручную"):
            if new_folder:
                set_invoice_folder(new_folder)
                st.success(f"✅ Папка сохранена: {new_folder}")
                st.rerun()

        st.divider()

        # ===== ВЫБОР ПУТИ К БАЗЕ ДАННЫХ =====
        st.subheader("🗄️ База данных")

        from db import get_db_path, set_db_path as set_db_path_func

        current_db_path = get_db_path()
        st.caption(f"🗄️ Текущая БД: `{current_db_path}`")

        # Кнопка для выбора папки для БД
        if st.button("🗂️ Выбрать место для БД", use_container_width=True):
            selected = select_folder_via_dialog()
            if selected:
                new_db_path = os.path.join(selected, "data.db")
                try:
                    # Создаём директорию, если её нет
                    os.makedirs(selected, exist_ok=True)
                    save_setting("db_path", new_db_path)
                    set_db_path_func(new_db_path)
                    st.success(f"✅ База данных будет сохранена в: {new_db_path}")
                    st.info("🔄 Перезапустите приложение для применения изменений")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
            else:
                st.warning("⚠️ Папка не выбрана")

        # Ручной ввод пути для БД
        new_db_path_input = st.text_input("Или введите полный путь к файлу БД", value=current_db_path)
        if st.button("💾 Сохранить путь к БД вручную"):
            if new_db_path_input:
                try:
                    db_dir = os.path.dirname(new_db_path_input)
                    if db_dir and not os.path.exists(db_dir):
                        os.makedirs(db_dir, exist_ok=True)
                    save_setting("db_path", new_db_path_input)
                    set_db_path_func(new_db_path_input)
                    st.success(f"✅ Путь к БД сохранён: {new_db_path_input}")
                    st.info("🔄 Перезапустите приложение для применения изменений")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")

        st.divider()

        # ===== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====
        st.subheader("📦 Резервное копирование")

        if st.button("💾 Создать резервную копию БД", use_container_width=True):
            import shutil
            from datetime import datetime

            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = os.path.join(current_folder, backup_name)
            try:
                shutil.copy2(current_db_path, backup_path)
                st.success(f"✅ Резервная копия создана: {backup_path}")
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")

        st.divider()

        # ===== ИНФОРМАЦИЯ О СИСТЕМЕ =====
        st.subheader("ℹ️ О системе")
        from db import get_companies_count, get_invoices_count, get_total_invoices_amount

        st.write(f"**Организаций:** {get_companies_count()}")
        st.write(f"**Счетов:** {get_invoices_count()}")
        st.write(f"**Общая сумма:** {get_total_invoices_amount():,.2f} ₽")

# ==================== ГЛАВНАЯ ====================
if menu == "Главная":
    st.header("💰 Выставление счета")

    # Кнопки выбора действия
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("📄 Сканировать карточку", use_container_width=True):
            st.session_state.show_upload_in_invoice = True
            st.session_state.show_product_form = False
            st.session_state.selected_company_for_invoice = None
            st.session_state.show_manual_company = False

    with col2:
        if st.button("✏️ Добавить вручную", use_container_width=True):
            st.session_state.show_manual_company = True
            st.session_state.show_product_form = False
            st.session_state.selected_company_for_invoice = None
            st.session_state.show_upload_in_invoice = False

    with col3:
        # Показываем выбранную организацию, если есть
        if st.session_state.selected_company_for_invoice:
            company = st.session_state.selected_company_for_invoice
            st.success(f"✅ Выбрана: {company.name}")
            if st.button("🔄 Сменить", key="change_company_main"):
                st.session_state.selected_company_for_invoice = None
                st.session_state.show_product_form = False
                st.rerun()

    st.divider()

    # --- Сканирование карточки организации ---
    if st.session_state.get('show_upload_in_invoice', False):
        st.subheader("📄 Сканирование карточки организации")

        if st.button("◀ Назад к выбору"):
            st.session_state.show_upload_in_invoice = False
            st.rerun()

        file = st.file_uploader(
            "Загрузите карточку организации (изображение, PDF или DOC/DOCX)",
            type=["png", "jpg", "jpeg", "pdf", "doc", "docx"],
            key="invoice_upload"
        )

        if file:
            ext = file.name.split(".")[-1].lower()
            path = os.path.join(temp_dir, file.name)

            with open(path, "wb") as f:
                f.write(file.read())

            with st.spinner("Распознавание текста..."):
                if ext in ("png", "jpg", "jpeg"):
                    text = extract_text(path)
                elif ext in ("doc", "docx"):
                    text = extract_text_from_doc(path)
                else:
                    text = ""

            if text:
                data = parse_data(text)

                st.subheader("🏢 Извлеченные данные")

                col1, col2 = st.columns(2)
                with col1:
                    edited_name = st.text_input("Название организации", value=data.get("Название", ""))
                    edited_inn = st.text_input("ИНН", value=data.get("ИНН", ""))
                    edited_kpp = st.text_input("КПП", value=data.get("КПП", ""))
                with col2:
                    edited_address = st.text_area("Адрес", value=data.get("Адрес", ""), height=68)
                    edited_ogrn = st.text_input("ОГРН", value=data.get("ОГРН", ""))
                    edited_bik = st.text_input("БИК", value=data.get("БИК", ""))
                    edited_rs = st.text_input("Р/С", value=data.get("Р/С", ""))

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Сохранить и продолжить", type="primary"):
                        if edited_name:
                            company_data = {
                                "name": edited_name,
                                "inn": edited_inn,
                                "kpp": edited_kpp,
                                "bik": edited_bik,
                                "rs": edited_rs,
                                "legal_address": edited_address,
                                "ogrn": edited_ogrn
                            }
                            save_company(company_data)

                            companies = get_companies()
                            for c in companies:
                                if c.name == edited_name and c.inn == edited_inn:
                                    st.session_state.selected_company_for_invoice = c
                                    break

                            st.session_state.show_upload_in_invoice = False
                            st.session_state.show_product_form = True
                            st.rerun()
                        else:
                            st.error("❌ Название организации обязательно!")
                with col2:
                    if st.button("❌ Отмена"):
                        st.session_state.show_upload_in_invoice = False
                        st.rerun()

    # --- Добавление организации вручную ---
    if st.session_state.get('show_manual_company', False):
        st.subheader("✏️ Добавление организации вручную")

        if st.button("◀ Назад к выбору"):
            st.session_state.show_manual_company = False
            st.rerun()

        with st.form(key="manual_company_form"):
            st.info("📝 Заполните реквизиты организации")

            col1, col2 = st.columns(2)
            with col1:
                manual_name = st.text_input("Название организации*", placeholder="ООО 'Ромашка'")
                manual_inn = st.text_input("ИНН*", placeholder="1234567890")
                manual_kpp = st.text_input("КПП", placeholder="123456789")
                manual_ogrn = st.text_input("ОГРН", placeholder="1234567890123")
            with col2:
                manual_address = st.text_area("Юридический адрес*", placeholder="г. Москва, ул. Ленина, д. 1",
                                              height=100)
                manual_bik = st.text_input("БИК", placeholder="044525092")
                manual_rs = st.text_input("Р/С", placeholder="40802810670010126825")

            st.caption("* - обязательные поля")

            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Сохранить и продолжить", type="primary"):
                    if not manual_name:
                        st.error("❌ Название организации обязательно!")
                    elif not manual_inn:
                        st.error("❌ ИНН обязателен!")
                    elif not manual_address:
                        st.error("❌ Юридический адрес обязателен!")
                    else:
                        company_data = {
                            "name": manual_name,
                            "inn": manual_inn,
                            "kpp": manual_kpp,
                            "bik": manual_bik,
                            "rs": manual_rs,
                            "legal_address": manual_address,
                            "ogrn": manual_ogrn
                        }
                        save_company(company_data)

                        companies = get_companies()
                        for c in companies:
                            if c.name == manual_name:
                                st.session_state.selected_company_for_invoice = c
                                break

                        st.session_state.show_manual_company = False
                        st.session_state.show_product_form = True
                        st.rerun()
            with col2:
                if st.form_submit_button("❌ Отмена"):
                    st.session_state.show_manual_company = False
                    st.rerun()

    # --- Выбор организации из существующих ---
    if (not st.session_state.get('show_upload_in_invoice', False) and
            not st.session_state.get('show_manual_company', False) and
            not st.session_state.show_product_form):

        st.subheader("🏢 Или выберите из существующих")

        companies = get_companies()

        if companies:
            company_options = {}
            for c in companies:
                invoices_count = len(get_invoices_by_company(c.id))
                company_options[f"{c.name} (ИНН: {c.inn}) - Счетов: {invoices_count}"] = c

            selected_company_name = st.selectbox(
                "Выберите организацию",
                list(company_options.keys()),
                key="select_existing_company"
            )

            if st.button("✅ Выбрать эту организацию", use_container_width=True):
                st.session_state.selected_company_for_invoice = company_options[selected_company_name]
                st.session_state.show_product_form = True
                st.rerun()
        else:
            st.info("📌 Нет сохранённых организаций. Добавьте первую через сканирование или вручную.")

    # --- Форма ввода товара ---
    if st.session_state.show_product_form and st.session_state.selected_company_for_invoice:
        buyer = st.session_state.selected_company_for_invoice

        st.success(f"🏢 Организация: **{buyer.name}**")

        if st.button("🔄 Сменить организацию"):
            st.session_state.selected_company_for_invoice = None
            st.session_state.show_product_form = False
            st.rerun()

        st.divider()

        with st.expander("📋 Реквизиты покупателя (можно отредактировать)", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                edited_address = st.text_area("📍 Адрес", value=buyer.legal_address or "", height=68)
                edited_inn = st.text_input("🆔 ИНН", value=buyer.inn or "")
            with col2:
                edited_kpp = st.text_input("🔢 КПП", value=buyer.kpp or "")
                edited_ogrn = st.text_input("📌 ОГРН", value=buyer.ogrn or "")
                edited_bik = st.text_input("🏦 БИК", value=buyer.bik or "")
                edited_rs = st.text_input("💳 Р/С", value=buyer.rs or "")

        st.divider()

        # ========== ТОВАР ==========
        st.subheader("📦 Товар")

        col1, col2 = st.columns(2)

        with col1:
            # ТИП ТОВАРА (выпадающий список) -> в ячейку C24
            product_type_options = ["Ноутбук б/у", "Неттоп б/у", "Док-станция б/у"]

            selected_product_type = st.selectbox(
                "📌 Тип товара",
                options=product_type_options,
                index=0,
                key="product_type_select"
            )

            # Количество
            quantity = st.number_input(
                "🔢 Количество",
                min_value=1,
                value=1,
                step=1,
                key="product_quantity"
            )

        with col2:
            # НАИМЕНОВАНИЕ ТОВАРА (произвольный ввод) -> в ячейку D24
            product_name = st.text_input(
                "📝 Наименование товара",
                value="",
                placeholder="Введите наименование товара",
                key="product_name_input"
            )

            # Цена за единицу
            price_per_unit = st.number_input(
                "💰 Цена за единицу (руб.)",
                min_value=0.01,
                value=26400.0,
                step=100.0,
                format="%.2f",
                key="product_price"
            )

        # Конфигурация товара (записывается в C25)
        product_config = st.text_area(
            "⚙️ Конфигурация товара",
            value="",
            placeholder="Введите технические характеристики, комплектацию и т.д.",
            height=100,
            key="product_config_input"
        )

        st.divider()

        # --- Наценка ---
        st.subheader("💰 Наценка")
        markup_percent = st.number_input(
            "Наценка (%)",
            min_value=0.0,
            max_value=1000.0,
            value=st.session_state.markup_percent,
            step=1.0,
            help="Процент наценки на товар (доставка учитывается до наценки)"
        )
        st.session_state.markup_percent = markup_percent

        st.divider()

        # --- Доставка / Самовывоз ---
        st.subheader("🚚 Доставка")

        delivery_type = st.radio(
            "Способ получения",
            options=["Самовывоз", "Доставка"],
            horizontal=True,
            index=0 if st.session_state.delivery_type == "Самовывоз" else 1
        )
        st.session_state.delivery_type = delivery_type

        delivery_cost = 0.0
        if delivery_type == "Доставка":
            delivery_cost = st.number_input(
                "Стоимость доставки (руб.)",
                min_value=0.0,
                value=st.session_state.delivery_cost,
                step=100.0,
                format="%.2f"
            )
            st.session_state.delivery_cost = delivery_cost

        st.divider()

        # --- Расчёт итога ---
        # Цена с доставкой (до наценки)
        price_with_delivery = price_per_unit + delivery_cost
        # Цена с наценкой
        final_price = price_with_delivery * (1 + markup_percent / 100)
        # Общая сумма
        total_amount = quantity * final_price

        st.subheader("📊 Расчёт итоговой суммы")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Цена за ед.", f"{price_per_unit:,.2f} ₽")
        with col2:
            if delivery_cost > 0:
                st.metric("🚚 Доставка (на ед.)", f"{delivery_cost:,.2f} ₽")
            if markup_percent > 0:
                st.metric(f"📈 Наценка ({markup_percent:.0f}%)",
                          f"{final_price - price_per_unit - delivery_cost:,.2f} ₽")
        with col3:
            st.metric("💵 Итоговая цена за ед.", f"{final_price:,.2f} ₽")

        st.metric("💰 Итого к оплате", f"{total_amount:,.2f} ₽",
                  delta=f"+{((final_price / price_per_unit) - 1) * 100:.1f}%" if price_per_unit > 0 else None)

        st.divider()

        # Номер счета
        next_number = get_next_invoice_number()
        invoice_number = st.number_input("Номер счета", min_value=1, value=next_number, step=1)

        # Кнопка формирования счета
        if st.button("🎯 Сформировать счет Excel", type="primary", use_container_width=True):
            if not product_name:
                st.error("❌ Введите наименование товара!")
            else:
                template_path = "24044.xlsx"
                if not os.path.exists(template_path):
                    st.error(f"❌ Шаблон '{template_path}' не найден!")
                else:
                    try:
                        with st.spinner("Заполнение шаблона..."):
                            # Собираем данные
                            company_data = {
                                "Название": buyer.name,
                                "Адрес": edited_address,
                                "legal_address": edited_address,
                                "ИНН": edited_inn,
                                "inn": edited_inn,
                                "КПП": edited_kpp,
                                "kpp": edited_kpp,
                                "ОГРН": edited_ogrn,
                                "БИК": edited_bik,
                                "Р/С": edited_rs
                            }

                            # Формируем данные товара
                            # Тип товара -> C24
                            # Наименование товара -> D24
                            # Конфигурация -> C25
                            items_list = [{
                                "product_type": selected_product_type,  # Тип товара (в C24)
                                "name": product_name,  # Наименование (в D24)
                                "config": product_config,  # Конфигурация (в C25)
                                "quantity": quantity,
                                "price": price_per_unit
                            }]

                            output_folder = get_invoice_folder()
                            output_filename = f"счет_{buyer.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                            output_path = os.path.join(output_folder, output_filename)

                            # Заполняем шаблон
                            fill_excel_invoice_with_markup(
                                company_data, items_list, product_config,
                                invoice_number, markup_percent, delivery_cost,
                                template_path, output_path
                            )

                            # Сохраняем в БД
                            invoice_data = {
                                "invoice_number": str(invoice_number),
                                "company_id": buyer.id,
                                "company_name": buyer.name,
                                "total_amount": total_amount,
                                "items": str(items_list),
                                "configuration": product_config,
                                "file_path": output_path,
                                "markup_percent": markup_percent,
                                "delivery_cost": delivery_cost
                            }
                            save_invoice(invoice_data)

                        st.success(f"✅ Счет №{invoice_number} успешно сформирован!")

                        with open(output_path, "rb") as f:
                            st.download_button(
                                label="📥 Скачать заполненный счет (Excel)",
                                data=f,
                                file_name=output_filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

                        # Сбрасываем форму
                        st.session_state.markup_percent = 0.0
                        st.session_state.delivery_cost = 0.0
                        st.session_state.delivery_type = "Самовывоз"
                        st.session_state.show_product_form = False
                        st.session_state.selected_company_for_invoice = None
                        st.balloons()

                    except Exception as e:
                        st.error(f"❌ Ошибка: {str(e)}")
# --- База организаций ---
elif menu == "База организаций":
    st.header("🏛️ База организаций")

    if st.button("➕ Добавить организацию вручную"):
        st.session_state.editing_company_id = "new"
        st.rerun()

    st.divider()

    companies = get_companies()

    if not companies:
        st.info("📌 База пуста. Загрузите карточки организаций через 'Главная'")
    else:
        for c in companies:
            # Получаем количество счетов для этой организации
            invoices_count = len(get_invoices_by_company(c.id))

            if st.session_state.editing_company_id == c.id:
                with st.form(key=f"edit_form_{c.id}"):
                    st.subheader(f"✏️ Редактирование: {c.name}")

                    new_name = st.text_input("Название", value=c.name)
                    new_inn = st.text_input("ИНН", value=c.inn or "")
                    new_kpp = st.text_input("КПП", value=c.kpp or "")
                    new_bik = st.text_input("БИК", value=c.bik or "")
                    new_rs = st.text_input("Р/С", value=c.rs or "")
                    new_address = st.text_area("Юридический адрес", value=c.legal_address or "", height=100)
                    new_ogrn = st.text_input("ОГРН", value=c.ogrn or "")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.form_submit_button("✅ Сохранить"):
                            updated_data = {
                                "name": new_name,
                                "inn": new_inn,
                                "kpp": new_kpp,
                                "bik": new_bik,
                                "rs": new_rs,
                                "legal_address": new_address,
                                "ogrn": new_ogrn
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
                with st.expander(f"🏢 {c.name} (Счетов: {invoices_count})"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**ИНН:** {c.inn or '—'}")
                        st.write(f"**КПП:** {c.kpp or '—'}")
                        st.write(f"**ОГРН:** {c.ogrn or '—'}")
                        st.write(f"**БИК:** {c.bik or '—'}")
                        st.write(f"**Р/С:** {c.rs or '—'}")
                        st.text_area("**Адрес:**", value=c.legal_address or '—', height=68, disabled=True)
                    with col2:
                        if st.button("✏️ Редактировать", key=f"edit_btn_{c.id}"):
                            st.session_state.editing_company_id = c.id
                            st.rerun()

# --- Выставление счета ---
elif menu == "Выставление счета":
    st.header("💰 Выставление счета")

    # Инициализация состояния для выбора организации
    if 'selected_company_for_invoice' not in st.session_state:
        st.session_state.selected_company_for_invoice = None
    if 'show_product_form' not in st.session_state:
        st.session_state.show_product_form = False
    if 'delivery_cost' not in st.session_state:
        st.session_state.delivery_cost = 0.0
    if 'delivery_type' not in st.session_state:
        st.session_state.delivery_type = "Самовывоз"  # "Самовывоз" или "Доставка"
    if 'markup_percent' not in st.session_state:
        st.session_state.markup_percent = 0.0

    # Кнопки выбора действия
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("📄 Сканировать карточку", use_container_width=True):
            st.session_state.show_upload_in_invoice = True
            st.session_state.show_product_form = False
            st.session_state.selected_company_for_invoice = None

    with col2:
        if st.button("✏️ Добавить вручную", use_container_width=True):
            st.session_state.show_manual_company = True
            st.session_state.show_product_form = False
            st.session_state.selected_company_for_invoice = None

    with col3:
        if st.session_state.selected_company_for_invoice:
            company = st.session_state.selected_company_for_invoice
            st.success(f"✅ Выбрана: {company.name}")

    st.divider()

    # --- Сканирование карточки организации ---
    if st.session_state.get('show_upload_in_invoice', False):
        st.subheader("📄 Сканирование карточки организации")

        file = st.file_uploader(
            "Загрузите карточку организации (изображение, PDF или DOC/DOCX)",
            type=["png", "jpg", "jpeg", "pdf", "doc", "docx"],
            key="invoice_upload"
        )

        if file:
            ext = file.name.split(".")[-1].lower()
            path = os.path.join(temp_dir, file.name)

            with open(path, "wb") as f:
                f.write(file.read())

            with st.spinner("Распознавание текста..."):
                if ext in ("png", "jpg", "jpeg"):
                    text = extract_text(path)
                elif ext in ("doc", "docx"):
                    text = extract_text_from_doc(path)
                else:
                    text = ""

            if text:
                data = parse_data(text)

                st.subheader("🏢 Извлеченные данные")

                col1, col2 = st.columns(2)
                with col1:
                    edited_name = st.text_input("Название организации", value=data.get("Название", ""))
                    edited_inn = st.text_input("ИНН", value=data.get("ИНН", ""))
                    edited_kpp = st.text_input("КПП", value=data.get("КПП", ""))
                with col2:
                    edited_address = st.text_area("Адрес", value=data.get("Адрес", ""), height=68)
                    edited_ogrn = st.text_input("ОГРН", value=data.get("ОГРН", ""))
                    edited_bik = st.text_input("БИК", value=data.get("БИК", ""))
                    edited_rs = st.text_input("Р/С", value=data.get("Р/С", ""))

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Сохранить и продолжить", type="primary"):
                        # Сохраняем в базу
                        company_data = {
                            "name": edited_name,
                            "inn": edited_inn,
                            "kpp": edited_kpp,
                            "bik": edited_bik,
                            "rs": edited_rs,
                            "legal_address": edited_address,
                            "ogrn": edited_ogrn
                        }
                        save_company(company_data)

                        # Получаем сохранённую компанию
                        companies = get_companies()
                        for c in companies:
                            if c.name == edited_name and c.inn == edited_inn:
                                st.session_state.selected_company_for_invoice = c
                                break

                        st.session_state.show_upload_in_invoice = False
                        st.session_state.show_product_form = True
                        st.rerun()
                with col2:
                    if st.button("❌ Отмена"):
                        st.session_state.show_upload_in_invoice = False
                        st.rerun()

    # --- Добавление организации вручную ---
    if st.session_state.get('show_manual_company', False):
        st.subheader("✏️ Добавление организации вручную")

        with st.form(key="manual_company_form"):
            col1, col2 = st.columns(2)
            with col1:
                manual_name = st.text_input("Название организации*")
                manual_inn = st.text_input("ИНН")
                manual_kpp = st.text_input("КПП")
            with col2:
                manual_address = st.text_area("Юридический адрес", height=100)
                manual_ogrn = st.text_input("ОГРН")
                manual_bik = st.text_input("БИК")
                manual_rs = st.text_input("Р/С")

            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Сохранить и продолжить", type="primary"):
                    if manual_name:
                        company_data = {
                            "name": manual_name,
                            "inn": manual_inn,
                            "kpp": manual_kpp,
                            "bik": manual_bik,
                            "rs": manual_rs,
                            "legal_address": manual_address,
                            "ogrn": manual_ogrn
                        }
                        save_company(company_data)

                        # Получаем сохранённую компанию
                        companies = get_companies()
                        for c in companies:
                            if c.name == manual_name:
                                st.session_state.selected_company_for_invoice = c
                                break

                        st.session_state.show_manual_company = False
                        st.session_state.show_product_form = True
                        st.rerun()
                    else:
                        st.error("❌ Название организации обязательно!")
            with col2:
                if st.form_submit_button("❌ Отмена"):
                    st.session_state.show_manual_company = False
                    st.rerun()

    # --- Форма ввода товара (показывается после выбора организации) ---
    if st.session_state.show_product_form and st.session_state.selected_company_for_invoice:
        buyer = st.session_state.selected_company_for_invoice

        st.success(f"🏢 Организация: **{buyer.name}**")

        # Кнопка смены организации
        if st.button("🔄 Сменить организацию"):
            st.session_state.selected_company_for_invoice = None
            st.session_state.show_product_form = False
            st.rerun()

        st.divider()

        # Редактируемые реквизиты
        with st.expander("📋 Реквизиты покупателя (можно отредактировать)", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                edited_address = st.text_area("📍 Адрес", value=buyer.legal_address or "", height=68)
                edited_inn = st.text_input("🆔 ИНН", value=buyer.inn or "")
            with col2:
                edited_kpp = st.text_input("🔢 КПП", value=buyer.kpp or "")
                edited_ogrn = st.text_input("📌 ОГРН", value=buyer.ogrn or "")
                edited_bik = st.text_input("🏦 БИК", value=buyer.bik or "")
                edited_rs = st.text_input("💳 Р/С", value=buyer.rs or "")

        st.divider()

        # Конфигурация оборудования
        configuration = st.text_area("⚙️ Конфигурация оборудования",
                                     placeholder="Введите технические характеристики, комплектацию и т.д.",
                                     height=100)

        st.divider()

        # Список товаров
        st.subheader("📦 Товары/услуги")

        # Отображение списка товаров
        for idx, item in enumerate(st.session_state.product_list):
            col1, col2, col3, col4, col5 = st.columns([4, 2, 1, 1, 0.5])
            with col1:
                item["name"] = st.text_input(f"Наименование", value=item["name"], key=f"name_{idx}")
            with col2:
                item["config"] = st.text_input(f"Конфигурация", value=item["config"], key=f"config_{idx}")
            with col3:
                item["quantity"] = st.number_input(f"Кол-во", min_value=1, value=item["quantity"], key=f"qty_{idx}")
            with col4:
                current_price = float(item["price"]) if float(item["price"]) >= 0.01 else 0.01
                item["price"] = st.number_input(f"Цена", min_value=0.01, value=current_price, key=f"price_{idx}",
                                                format="%.2f")
            with col5:
                if st.button("🗑️", key=f"del_{idx}"):
                    st.session_state.product_list.pop(idx)
                    st.rerun()

        # Кнопка добавления товара
        if st.button("➕ Добавить товар"):
            st.session_state.product_list.append({"name": "", "config": "", "quantity": 1, "price": 0.01})
            st.rerun()

        st.divider()

        # --- Наценка ---
        st.subheader("💰 Наценка")
        markup_percent = st.number_input(
            "Наценка (%)",
            min_value=0.0,
            max_value=1000.0,
            value=st.session_state.markup_percent,
            step=1.0,
            help="Процент наценки на товары (без учёта доставки)"
        )
        st.session_state.markup_percent = markup_percent

        st.divider()

        # --- Доставка / Самовывоз ---
        st.subheader("🚚 Доставка")

        delivery_type = st.radio(
            "Способ получения",
            options=["Самовывоз", "Доставка"],
            horizontal=True,
            index=0 if st.session_state.delivery_type == "Самовывоз" else 1
        )
        st.session_state.delivery_type = delivery_type

        delivery_cost = 0.0
        if delivery_type == "Доставка":
            delivery_cost = st.number_input(
                "Стоимость доставки (руб.)",
                min_value=0.0,
                value=st.session_state.delivery_cost,
                step=100.0,
                format="%.2f"
            )
            st.session_state.delivery_cost = delivery_cost

        st.divider()

        # --- Расчёт итога с учётом наценки и доставки ---
        # Сумма товаров без наценки
        subtotal = sum(item["quantity"] * item["price"] for item in st.session_state.product_list if item["name"])

        # Сумма с доставкой (до наценки)
        amount_with_delivery = subtotal + delivery_cost

        # Наценка применяется к сумме с доставкой
        markup_amount = amount_with_delivery * (markup_percent / 100)
        total_amount = amount_with_delivery + markup_amount

        # Показываем детали расчёта
        st.subheader("📊 Расчёт итоговой суммы")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Сумма товаров", f"{subtotal:,.2f} ₽")
        with col2:
            if delivery_cost > 0:
                st.metric("🚚 Доставка", f"{delivery_cost:,.2f} ₽")
            if markup_percent > 0:
                st.metric(f"📈 Наценка ({markup_percent:.0f}%)", f"{markup_amount:,.2f} ₽")
        with col3:
            st.metric("💵 Итого к оплате", f"{total_amount:,.2f} ₽",
                      delta=f"+{((total_amount / subtotal) - 1) * 100:.1f}%" if subtotal > 0 else None)

        st.divider()

        # Номер счета
        from db import get_next_invoice_number

        next_number = get_next_invoice_number()
        invoice_number = st.number_input("Номер счета", min_value=1, value=next_number, step=1)

        # Кнопка формирования счета
        if st.button("🎯 Сформировать счет Excel", type="primary", use_container_width=True):
            valid_items = [item for item in st.session_state.product_list if item["name"]]
            if not valid_items:
                st.error("❌ Добавьте хотя бы один товар!")
            else:
                # Собираем данные
                company_data = {
                    "Адрес": edited_address,
                    "ИНН": edited_inn,
                    "КПП": edited_kpp,
                    "ОГРН": edited_ogrn,
                    "БИК": edited_bik,
                    "Р/С": edited_rs,
                    "Название": buyer.name
                }

                # Добавляем доставку как отдельный товар, если она есть
                items_for_excel = valid_items.copy()
                if delivery_cost > 0:
                    items_for_excel.append({
                        "name": "Доставка",
                        "config": f"Доставка до адреса: {edited_address[:50]}",
                        "quantity": 1,
                        "price": delivery_cost
                    })

                template_path = "24044.xlsx"
                if not os.path.exists(template_path):
                    st.error(f"❌ Шаблон '{template_path}' не найден!")
                else:
                    try:
                        with st.spinner("Заполнение шаблона..."):
                            output_folder = get_invoice_folder()
                            output_filename = f"счет_{buyer.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                            output_path = os.path.join(output_folder, output_filename)

                            # Передаём наценку в функцию
                            fill_excel_invoice_with_markup(
                                company_data, items_for_excel, configuration,
                                invoice_number, markup_percent, delivery_cost,
                                template_path, output_path
                            )

                            # Сохраняем в БД
                            invoice_data = {
                                "invoice_number": str(invoice_number),
                                "company_id": buyer.id,
                                "company_name": buyer.name,
                                "total_amount": total_amount,
                                "items": str(items_for_excel),
                                "configuration": configuration,
                                "file_path": output_path,
                                "markup_percent": markup_percent,
                                "delivery_cost": delivery_cost
                            }
                            save_invoice(invoice_data)

                        st.success(f"✅ Счет №{invoice_number} успешно сформирован!")

                        with open(output_path, "rb") as f:
                            st.download_button(
                                label="📥 Скачать заполненный счет (Excel)",
                                data=f,
                                file_name=output_filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

                        # Очищаем список товаров, но оставляем один пустой
                        st.session_state.product_list = [{"name": "", "config": "", "quantity": 1, "price": 0.01}]
                        st.session_state.delivery_cost = 0.0
                        st.session_state.delivery_type = "Самовывоз"
                        st.session_state.markup_percent = 0.0
                        st.session_state.show_product_form = False
                        st.session_state.selected_company_for_invoice = None
                        st.balloons()

                    except Exception as e:
                        st.error(f"❌ Ошибка: {str(e)}")
# ==================== БАЗА СЧЕТОВ ====================
elif menu == "База счетов":
    st.header("📜 База выставленных счетов")

    invoices = get_invoices()

    if not invoices:
        st.info("📌 Счета еще не выставлялись.")
    else:
        # ========== СТАТИСТИКА ==========
        total_sum = sum(inv.total_amount for inv in invoices)
        avg_amount = total_sum / len(invoices) if invoices else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Всего счетов", len(invoices))
        with col2:
            st.metric("💰 Общая сумма", f"{total_sum:,.2f} ₽")
        with col3:
            st.metric("📈 Средняя сумма", f"{avg_amount:,.2f} ₽")

        st.divider()

        # ========== ПОИСК ==========
        st.subheader("🔍 Поиск по счетам")

        col1, col2 = st.columns([3, 1])
        with col1:
            search_text = st.text_input(
                "Поиск по номеру счета, организации или сумме",
                placeholder="Введите номер, название или сумму (например: 24045, ООО, 5000)"
            )
        with col2:
            search_by_amount = st.checkbox("Искать по сумме",
                                           help="Искать счета по сумме (можно вводить без запятых, например: 5000)")

        # ========== ФИЛЬТРАЦИЯ ==========
        filtered_invoices = invoices

        if search_text:
            if search_by_amount:
                import re

                clean_search = re.sub(r'[^\d]', '', search_text)

                if clean_search:
                    try:
                        amount_search = float(clean_search)
                        filtered_invoices = [inv for inv in invoices if abs(inv.total_amount - amount_search) < 0.01]

                        if filtered_invoices:
                            st.success(f"✅ Найдено {len(filtered_invoices)} счет(ов) на сумму {amount_search:,.2f} ₽")
                        else:
                            st.warning(f"❌ Счета на сумму {amount_search:,.2f} ₽ не найдены")
                    except ValueError:
                        st.warning("⚠️ Введите корректную сумму для поиска")
                        filtered_invoices = []
                else:
                    st.warning("⚠️ Введите сумму для поиска")
                    filtered_invoices = []
            else:
                search_lower = search_text.lower()
                filtered_invoices = [
                    inv for inv in invoices
                    if search_lower in inv.invoice_number.lower()
                       or search_lower in inv.company_name.lower()
                ]

                if filtered_invoices:
                    st.success(f"🔎 Найдено {len(filtered_invoices)} из {len(invoices)} счетов")
                else:
                    st.warning("❌ Счета по вашему запросу не найдены")

        st.divider()

        # ========== ОТОБРАЖЕНИЕ СЧЕТОВ ==========
        for inv in filtered_invoices:
            # Разбираем данные товаров (это строка, не требует доступа к связанным объектам)
            try:
                items_list = eval(inv.items) if isinstance(inv.items, str) else inv.items
            except:
                items_list = []

            # Сумма с наценкой
            total_with_markup = inv.total_amount

            # Заголовок слайдера
            with st.expander(
                    f"🧾 Счет №{inv.invoice_number} - {inv.company_name} | 💰 {total_with_markup:,.2f} ₽ | 📅 {inv.created_at.strftime('%d.%m.%Y')}"
            ):
                # Кнопки действий
                col_actions1, col_actions2, col_actions3 = st.columns(3)

                with col_actions1:
                    if st.button("✏️ Редактировать", key=f"edit_btn_{inv.id}", use_container_width=True):
                        st.session_state.editing_invoice_id = inv.id
                        st.rerun()

                with col_actions2:
                    if inv.file_path and os.path.exists(inv.file_path):
                        with open(inv.file_path, "rb") as f:
                            st.download_button(
                                label="📄 Скачать",
                                data=f,
                                file_name=os.path.basename(inv.file_path),
                                key=f"download_inv_{inv.id}",
                                use_container_width=True
                            )

                with col_actions3:
                    if st.button("🗑️ Удалить", key=f"del_inv_{inv.id}", use_container_width=True):
                        if delete_invoice(inv.id):
                            st.success(f"✅ Счет №{inv.invoice_number} удален!")
                            st.rerun()

                # ========== ФОРМА РЕДАКТИРОВАНИЯ ==========
                if st.session_state.get('editing_invoice_id') == inv.id:
                    st.divider()
                    st.subheader(f"✏️ Редактирование счета №{inv.invoice_number}")

                    with st.form(key=f"edit_invoice_form_{inv.id}"):
                        current_item = items_list[0] if items_list else {}

                        # Тип товара
                        product_type_options = ["Ноутбук б/у", "Неттоп б/у", "Док-станция б/у"]
                        current_product_type = current_item.get("product_type", "")
                        if current_product_type not in product_type_options:
                            current_product_type = product_type_options[0]

                        new_product_type = st.selectbox(
                            "📌 Тип товара",
                            options=product_type_options,
                            index=product_type_options.index(
                                current_product_type) if current_product_type in product_type_options else 0,
                            key=f"edit_type_{inv.id}"
                        )

                        col1, col2 = st.columns(2)
                        with col1:
                            new_product_name = st.text_input(
                                "📝 Наименование товара",
                                value=current_item.get("name", ""),
                                key=f"edit_name_{inv.id}"
                            )

                            new_quantity = st.number_input(
                                "🔢 Количество",
                                min_value=1,
                                value=int(current_item.get("quantity", 1)),
                                step=1,
                                key=f"edit_qty_{inv.id}"
                            )

                        with col2:
                            new_price = st.number_input(
                                "💰 Цена за единицу (руб.)",
                                min_value=0.01,
                                value=float(current_item.get("price", 0)),
                                step=100.0,
                                format="%.2f",
                                key=f"edit_price_{inv.id}"
                            )

                            new_config = st.text_area(
                                "⚙️ Конфигурация",
                                value=current_item.get("config", inv.configuration or ""),
                                height=80,
                                key=f"edit_config_{inv.id}"
                            )

                        st.divider()

                        col1, col2 = st.columns(2)
                        with col1:
                            new_markup = st.number_input(
                                "📈 Наценка (%)",
                                min_value=0.0,
                                max_value=1000.0,
                                value=float(inv.markup_percent or 0),
                                step=1.0,
                                format="%.0f",
                                key=f"edit_markup_{inv.id}"
                            )

                        with col2:
                            new_delivery = st.number_input(
                                "🚚 Доставка (руб.)",
                                min_value=0.0,
                                value=float(inv.delivery_cost or 0),
                                step=100.0,
                                format="%.2f",
                                key=f"edit_delivery_{inv.id}"
                            )

                        st.divider()

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.form_submit_button("💾 Сохранить", type="primary"):
                                try:
                                    price_with_delivery = new_price + new_delivery
                                    final_price = price_with_delivery * (1 + new_markup / 100)
                                    new_total = new_quantity * final_price

                                    updated_items = [{
                                        "product_type": new_product_type,
                                        "name": new_product_name,
                                        "config": new_config,
                                        "quantity": new_quantity,
                                        "price": new_price
                                    }]

                                    # Обновляем счёт в БД (без обращения к company)
                                    update_data = {
                                        "company_name": inv.company_name,
                                        "total_amount": new_total,
                                        "items": str(updated_items),
                                        "configuration": new_config,
                                        "markup_percent": new_markup,
                                        "delivery_cost": new_delivery
                                    }

                                    if update_invoice(inv.id, update_data):
                                        # Пересоздаём Excel файл
                                        company_data = {
                                            "Название": inv.company_name,
                                            "Адрес": "",
                                            "ИНН": "",
                                            "КПП": ""
                                        }

                                        output_folder = get_invoice_folder()
                                        new_filename = f"счет_{inv.company_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                                        new_output_path = os.path.join(output_folder, new_filename)

                                        fill_excel_invoice_with_markup(
                                            company_data, updated_items, new_config,
                                            inv.invoice_number, new_markup, new_delivery,
                                            "24044.xlsx", new_output_path
                                        )

                                        update_invoice(inv.id, {"file_path": new_output_path})

                                        st.success(f"✅ Счет №{inv.invoice_number} обновлен!")
                                        st.session_state.editing_invoice_id = None
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Ошибка: {str(e)}")

                        with col2:
                            if st.form_submit_button("❌ Отмена"):
                                st.session_state.editing_invoice_id = None
                                st.rerun()

                else:
                    # ========== ПРОСМОТР (БЕЗ ОБРАЩЕНИЯ К СВЯЗАННЫМ ОБЪЕКТАМ) ==========
                    st.divider()

                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.write(f"**💰 Стоимость с наценкой:** {total_with_markup:,.2f} ₽")

                        if inv.markup_percent > 0:
                            st.write(f"**📈 Наценка:** {inv.markup_percent:.0f}%")
                        if inv.delivery_cost > 0:
                            st.write(f"**🚚 Доставка:** {inv.delivery_cost:,.2f} ₽")

                        st.write("**📦 Товары:**")
                        for item in items_list:
                            qty = item.get("quantity", 0)
                            price = item.get("price", 0)
                            st.write(f"  • **{item.get('product_type', '—')}** - {item.get('name', '—')}")
                            st.write(f"    {qty} шт x {price:,.2f} ₽ = {qty * price:,.2f} ₽")
                            if item.get('config'):
                                st.write(f"    *Конфигурация:* {item.get('config')}")

                        st.write(f"**📅 Дата:** {inv.created_at.strftime('%d.%m.%Y %H:%M')}")

                    with col2:
                        st.info(f"**№:** {inv.invoice_number}\n\n**Клиент:** {inv.company_name}")