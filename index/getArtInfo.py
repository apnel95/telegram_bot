import requests
import json

API_KEY = "ключ"
PAINTING_IDS = [
#Список
]

def fetch_painting_details(object_number):
    url = f"https://www.rijksmuseum.nl/api/en/collection/{object_number}"
    params = {
        "key": API_KEY,
        "format": "json"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

paintings_data = []

for obj_number in PAINTING_IDS:
    try:
        data = fetch_painting_details(obj_number)
        art_obj = data.get("artObject", {})

        painting = {
            "title": art_obj.get("title"),
            "principalOrFirstMaker": art_obj.get("principalOrFirstMaker"),
            "dating": art_obj.get("dating", {}),
            "productionPlaces": art_obj.get("productionPlaces", []),
            "description": "",
            "googleArtsUrl": "",
            "image": art_obj.get("webImage", {}).get("url"),
            "location": art_obj.get("location"),
        }

        paintings_data.append(painting)
    except Exception as e:
        print(f"Ошибка {obj_number}: {e}")

# Сохранение в файл
with open("selected_paintings.json", "w", encoding="utf-8") as f:
    json.dump(paintings_data, f, ensure_ascii=False, indent=2)
