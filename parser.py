import re


def parse_data(text):
    data = {}

    # Паттерны для поиска реквизитов
    patterns = {
        "ИНН": r"\b\d{10}\b|\b\d{12}\b",  # ИНН 10 или 12 цифр
        "КПП": r"\b\d{9}\b",  # КПП 9 цифр
        "БИК": r"\b\d{9}\b",  # БИК 9 цифр
        "Р/С": r"\b\d{20}\b",  # Расчетный счет 20 цифр
        "ОГРН": r"\b\d{13}\b|\b\d{15}\b"  # ОГРН 13 или 15 цифр
    }

    for key, pattern in patterns.items():
        matches = re.findall(pattern, text)
        # Фильтруем, чтобы не путать ИНН с другими цифрами
        if key == "ИНН":
            # ИНН не может начинаться с 0
            matches = [m for m in matches if not m.startswith('0')]
        if key == "КПП":
            # КПП обычно не совпадает с БИК, но для простоты берем первый
            pass
        data[key] = matches[0] if matches else "Не найден"

    # Поиск адреса (улица, город, дом, квартира)
    address_patterns = [
        r"(?:г\.?\s*[А-Яа-я\s\-]+|город\s+[А-Яа-я\s\-]+)",  # Город
        r"(?:ул\.?\s*[А-Яа-я\s\-]+|улица\s+[А-Яа-я\s\-]+)",  # Улица
        r"(?:д\.?\s*\d+[а-я]?|дом\s+\d+[а-я]?)",  # Дом
        r"(?:к\.?\s*\d+[а-я]?|корпус\s+\d+[а-я]?)",  # Корпус
        r"(?:кв\.?\s*\d+|квартира\s+\d+)"  # Квартира
    ]

    address_parts = []
    for pattern in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            address_parts.append(match.group(0))

    # Ищем полный адрес после ключевых слов
    full_address_match = re.search(
        r"(?:Адрес|Местонахождение|Юридический адрес)[:\s]*(.+?)(?:\n|ИНН|КПП|$)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if full_address_match:
        address = full_address_match.group(1).strip()
        # Очищаем от лишних пробелов и переносов
        address = re.sub(r'\s+', ' ', address)
        data["Адрес"] = address
    elif address_parts:
        data["Адрес"] = " ".join(address_parts)
    else:
        data["Адрес"] = "Не найден"

    # Поиск названия организации
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    name_patterns = [
        r"(?:ООО|ЗАО|ОАО|ПАО|ИП|АО)\s+[А-Яа-я\s\"\-]+",
        r"(?:Наименование|Название|Организация)[:\s]*(.+?)(?:\n|ИНН|$)"
    ]

    name = "Не найдено"
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(0) if len(match.groups()) == 0 else match.group(1)
            name = name.strip()
            break

    if name == "Не найдено" and lines:
        name = lines[0][:100]  # Первая строка как название

    data["Название"] = name

    return data