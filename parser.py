import re

def parse_data(text):
    data = {}

    patterns = {
        "ИНН": r"\b\d{10}\b",
        "КПП": r"\b\d{9}\b",
        "БИК": r"\b\d{9}\b",
        "Р/С": r"\b\d{20}\b"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        data[key] = match.group(0) if match else "Не найден"

    lines = text.split("\n")
    data["Название"] = lines[0] if lines else "Не найдено"

    return data