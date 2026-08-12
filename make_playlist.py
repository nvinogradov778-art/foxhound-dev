import os
import json
from mutagen import File

folder_path = os.getcwd()
output_file = 'playlist.txt'

# 1. Запрашиваем у пользователя метаданные для радиостанции
station_id = input("Введите id (например, laboratory): ").strip()
station_name = input("Введите name (например, CH 3: Лаборатория): ").strip()
station_freq = input("Введите frequency (например, 141.52): ").strip()
station_purp = input("Введите purpose (например, ЧАСТОТА — «ЛАБОРАТОРИЯ»): ").strip()
station_desc = input("Введите desc (например, Пост-панк, индастриал...): ").strip()

# Папка формируется автоматически на основе id
prefix = f"playlist_{station_id}"

valid_extensions = ('.mp3', '.m4a')
# Сортируем список файлов по алфавиту
audio_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(valid_extensions)])

# Создаем чистый Python-словарь (объект)
station_data = {
    "id": station_id,
    "name": station_name,
    "frequency": station_freq,
    "purpose": station_purp,
    "desc": station_desc,
    "tracks": []
}

rename_queue = []

print(f"\nНайдено аудиофайлов для обработки: {len(audio_files)}")

for index, filename in enumerate(audio_files, start=1):
    full_path = os.path.join(folder_path, filename)
    
    # Сохраняем оригинальное расширение (.mp3 или .m4a)
    ext = os.path.splitext(filename)[1].lower()
    new_filename = f"{index}{ext}"
    new_full_path = os.path.join(folder_path, new_filename)
    
    title = ""
    try:
        audio = File(full_path)
        
        # Получаем теги для MP3 и M4A
        track_title_raw = audio.get('TIT2') or audio.get('\xa9nam')
        artist_raw = audio.get('TPE1') or audio.get('\xa9ART')
        
        if not track_title_raw and audio.tags:
            track_title_raw = audio.tags.get('title')
        if not artist_raw and audio.tags:
            artist_raw = audio.tags.get('artist')

        # Очищаем данные от служебных списков Mutagen
        def clean_tag(tag_data):
            if isinstance(tag_data, list) and tag_data:
                return str(tag_data[0])
            elif tag_data:
                return str(tag_data)
            return ""

        track_title = clean_tag(track_title_raw).strip()
        artist = clean_tag(artist_raw).strip()
        
        # Формируем название трека в зависимости от наличия тегов
        if artist and track_title:
            title = f"{track_title} — {artist}"
        elif track_title:
            title = track_title
        else:
            title = os.path.splitext(filename)[0]
    except Exception:
        title = os.path.splitext(filename)[0]
        
    # Добавляем трек в массив в виде мини-словаря
    station_data["tracks"].append({
        "title": title,
        "src": f"{prefix}/{new_filename}"
    })
    
    # Добавляем в очередь на переименование
    rename_queue.append((full_path, new_full_path, filename))

# Безопасное переименование (сначала во временные файлы, чтобы избежать перезаписи)
temp_rename = []
for full_path, new_full_path, old_name in rename_queue:
    if full_path != new_full_path:
        temp_path = full_path + ".tmp"
        try:
            os.rename(full_path, temp_path)
            temp_rename.append((temp_path, new_full_path))
        except Exception as e:
            print(f"Ошибка предварительного переименования {old_name}: {e}")

# Финальное переименование из временных файлов в целевые имена
for temp_path, new_full_path in temp_rename:
    try:
        if os.path.exists(new_full_path):
            os.remove(new_full_path)
        os.rename(temp_path, new_full_path)
    except Exception as e:
        print(f"Ошибка финального переименования в {os.path.basename(new_full_path)}: {e}")

# Превращаем Python-словарь в идеальный, валидный JSON-текст
# indent=4 сделает красивые отступы, ensure_ascii=False сохранит русский текст читаемым
json_output = json.dumps(station_data, indent=4, ensure_ascii=False)

# Записываем готовый JSON в файл
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(json_output)

print(f"\nГотово! Полная структура объекта сохранена в файл {output_file}")
print("Текст внутри файла теперь является 100% валидным JSON-объектом.")
