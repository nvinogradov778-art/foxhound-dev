import os
import subprocess
from pathlib import Path

# ---------- НАСТРОЙКИ ----------
OUTPUT_DIR_NAME = "compressed"   # имя папки, куда будут складываться сжатые копии
BITRATE = "128k"                 # желаемый битрейт
RECURSIVE = True                 # обрабатывать вложенные папки
OVERWRITE = False                # True - перезаписывать существующие файлы, False - пропускать
DRY_RUN = False                  # True - только показать, что будет сделано
# ------------------------------

def get_output_path(original: Path, root_dir: Path) -> Path:
    """
    Возвращает путь для сжатой копии внутри папки compressed.
    Сохраняет относительную структуру подпапок.
    """
    # Относительный путь от корневой папки
    rel_path = original.relative_to(root_dir)
    # Новый путь внутри папки compressed
    out_path = root_dir / OUTPUT_DIR_NAME / rel_path
    return out_path

def convert_to_128k(original: Path, output: Path, dry_run=False):
    """Перекодирует MP3 в 128 кбит/с и сохраняет в output."""
    if output.exists() and not OVERWRITE:
        print(f"⚠️  {output} уже существует, пропускаем")
        return False

    if dry_run:
        print(f"[DRY-RUN] {original} -> {output}")
        return True

    # Создаём родительские папки для output
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        'ffmpeg',
        '-i', str(original),
        '-b:a', BITRATE,
        '-map_metadata', '0',      # копируем все метаданные
        '-id3v2_version', '3',     # совместимый ID3v2.3
        '-y',                      # перезаписывать (если нужно, но мы уже проверили)
        str(output)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"❌ Ошибка при обработке {original.name}:")
            print(result.stderr)
            # удаляем возможно созданный, но битый файл
            if output.exists():
                output.unlink()
            return False
        print(f"✅ {original} -> {output}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def process_directory(root_dir: Path):
    """Обрабатывает все MP3 в директории рекурсивно."""
    if not root_dir.is_dir():
        print(f"❌ {root_dir} не является папкой")
        return

    # Собираем все MP3-файлы
    if RECURSIVE:
        files = list(root_dir.rglob('*.mp3'))
    else:
        files = list(root_dir.glob('*.mp3'))

    # Исключаем файлы, которые уже лежат внутри папки compressed
    files = [f for f in files if OUTPUT_DIR_NAME not in f.parts]

    if not files:
        print("⚠️ MP3-файлы не найдены.")
        return

    print(f"Найдено {len(files)} MP3-файлов. Начинаем сжатие в папку '{OUTPUT_DIR_NAME}'...")
    success = 0
    for i, f in enumerate(files, 1):
        out = get_output_path(f, root_dir)
        print(f"[{i}/{len(files)}] Обработка {f}")
        if convert_to_128k(f, out, DRY_RUN):
            success += 1

    print(f"\n✅ Готово! Сжато {success} файлов из {len(files)}.")

if __name__ == '__main__':
    # Папка, в которой находится скрипт
    script_dir = Path(__file__).parent
    process_directory(script_dir)