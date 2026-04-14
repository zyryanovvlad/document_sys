import os
import cv2
import easyocr

path = "C:\\Users\\Admin\\Downloads\\resultat.png"
print("Файл существует:", os.path.exists(path))

img = cv2.imread(path)
print("img:", img)

if img is None:
    print("❗ Ошибка загрузки изображения")
else:
    print("Сохранённый файл успешно загружается")