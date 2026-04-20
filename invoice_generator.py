from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from datetime import datetime
import os


def generate_invoice_pdf(data, filename=None):
    """
    Генерирует счет на оплату в формате PDF

    data: {
        "invoice_number": "24044",
        "company_name": "ООО Ромашка",
        "inn": "1234567890",
        "kpp": "123456789",
        "legal_address": "г. Москва, ул. Ленина, 1",
        "configuration": "конфигурация оборудования",
        "items": [
            {"name": "Товар 1", "quantity": 2, "price": 1000},
            {"name": "Товар 2", "quantity": 1, "price": 500}
        ]
    }
    """

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = data.get('company_name', 'unknown').replace(' ', '_').replace('/', '_')
        filename = f"Счет_{safe_name}_{data.get('invoice_number', 'unknown')}_{timestamp}.pdf"

    os.makedirs("generated_invoices", exist_ok=True)
    filepath = os.path.join("generated_invoices", filename)

    # Создаем документ
    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            topMargin=20 * mm, bottomMargin=20 * mm,
                            leftMargin=20 * mm, rightMargin=20 * mm)

    styles = getSampleStyleSheet()

    # Стили
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        fontName='Helvetica'
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica'
    )

    bold_style = ParagraphStyle(
        'Bold',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold'
    )

    # Содержимое документа
    story = []

    # Заголовок
    story.append(Paragraph("СЧЕТ НА ОПЛАТУ", title_style))
    story.append(Spacer(1, 10))

    # Шапка с номером и датой
    header_data = [
        [Paragraph(f"<b>Номер счета:</b> {data.get('invoice_number', '')}", normal_style),
         Paragraph(f"<b>Дата:</b> {datetime.now().strftime('%d.%m.%Y')}", header_style)]
    ]
    header_table = Table(header_data, colWidths=[100 * mm, 80 * mm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))

    # Информация о поставщике
    story.append(Paragraph("<b>Поставщик:</b>", bold_style))
    story.append(Paragraph("Индивидуальный предприниматель Волков Сергей Владимирович", normal_style))
    story.append(Paragraph("ИНН 290503806858 | ОГРНИП 314290401400010", normal_style))
    story.append(Paragraph("195113 Санкт-Петербург, Аллея Евгения Шварца, д. 13, к.1, стр. 1, кв. 16", normal_style))
    story.append(Spacer(1, 10))

    # Банковские реквизиты
    story.append(Paragraph("<b>Банк получателя:</b>", bold_style))
    story.append(Paragraph("МОСКОВСКИЙ ФИЛИАЛ АО КБ 'МОДУЛЬБАНК'", normal_style))
    story.append(Paragraph("БИК 044525092 | Сч. № 30101810645250000092", normal_style))
    story.append(Paragraph("Сч. № получателя: 40802810670010126825", normal_style))
    story.append(Spacer(1, 15))

    # Информация о покупателе
    story.append(Paragraph("<b>Покупатель:</b>", bold_style))
    story.append(Paragraph(data.get('company_name', ''), normal_style))
    story.append(Paragraph(data.get('legal_address', ''), normal_style))
    story.append(Paragraph(f"ИНН {data.get('inn', '')} / КПП {data.get('kpp', '')}", normal_style))
    story.append(Spacer(1, 15))

    # Конфигурация оборудования
    if data.get('configuration'):
        story.append(Paragraph("<b>Конфигурация оборудования:</b>", bold_style))
        story.append(Paragraph(data.get('configuration', ''), normal_style))
        story.append(Spacer(1, 15))

    # Таблица товаров
    items = data.get('items', [])
    total_amount = sum(item.get('quantity', 0) * item.get('price', 0) for item in items)

    # Заголовки таблицы
    table_data = [
        ['№', 'Наименование товара/услуги', 'Кол-во', 'Цена', 'Сумма']
    ]

    # Добавляем товары
    for idx, item in enumerate(items, 1):
        table_data.append([
            str(idx),
            item.get('name', ''),
            str(item.get('quantity', 0)),
            f"{item.get('price', 0):,.2f}",
            f"{item.get('quantity', 0) * item.get('price', 0):,.2f}"
        ])

    # Итог
    table_data.append(['', '', '', '<b>Итого:</b>', f'<b>{total_amount:,.2f}</b>'])

    # Создаем таблицу
    col_widths = [15 * mm, 90 * mm, 25 * mm, 30 * mm, 30 * mm]
    item_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Стили таблицы
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
        ('SPAN', (0, -1), (3, -1)),
        ('ALIGN', (3, -1), (4, -1), 'RIGHT'),
        ('FONTNAME', (3, -1), (4, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
    ]))

    story.append(item_table)
    story.append(Spacer(1, 15))

    # Сумма прописью
    story.append(Paragraph(f"<b>Всего к оплате:</b> {amount_to_words(total_amount)}", bold_style))
    story.append(Spacer(1, 30))

    # Подписи
    signature_data = [
        ['', ''],
        ['Руководитель:', '_________________ /Волков С.В./'],
        ['', ''],
        ['М.П.', '']
    ]
    signature_table = Table(signature_data, colWidths=[80 * mm, 100 * mm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(signature_table)

    # Строим документ
    doc.build(story)

    return filepath


def amount_to_words(amount):
    """Преобразует сумму в текст прописью"""
    if not amount or amount == 0:
        return "Ноль рублей 00 копеек"

    rubles = int(amount)
    kopecks = int(round((amount - rubles) * 100))

    units = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
    units_female = ['', 'одна', 'две', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
    tens = ['', 'десять', 'двадцать', 'тридцать', 'сорок', 'пятьдесят',
            'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
    hundreds = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот',
                'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']
    teens = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать',
             'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']

    def num_to_words(n, female=False):
        if n == 0:
            return ''

        result = []

        if n >= 100:
            result.append(hundreds[n // 100])
            n %= 100

        if n >= 20:
            result.append(tens[n // 10])
            n %= 10
            if n > 0:
                result.append(units_female[n] if female else units[n])
        elif 10 <= n < 20:
            result.append(teens[n - 10])
        elif n > 0:
            result.append(units_female[n] if female else units[n])

        return ' '.join(result)

    result_parts = []

    thousands = rubles // 1000
    if thousands > 0:
        thousand_str = num_to_words(thousands, female=True)
        if thousands == 1:
            thousand_str += ' тысяча'
        elif 2 <= thousands <= 4:
            thousand_str += ' тысячи'
        else:
            thousand_str += ' тысяч'
        result_parts.append(thousand_str)
        rubles %= 1000

    ruble_str = num_to_words(rubles)
    if rubles == 1:
        ruble_str += ' рубль'
    elif 2 <= rubles <= 4:
        ruble_str += ' рубля'
    else:
        ruble_str += ' рублей'
    result_parts.append(ruble_str)

    kopecks_str = f"{kopecks:02d} копеек"
    result_parts.append(kopecks_str)

    result = ' '.join(result_parts)
    return result[0].upper() + result[1:]