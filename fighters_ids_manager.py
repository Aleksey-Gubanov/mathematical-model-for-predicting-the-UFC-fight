#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер fighters_ids.json v2.1 | Рефакторинг: папка dataset/
================================================================
ИЗМЕНЕНИЯ v2.1:
1. ✅ Все файлы перенесены в папку dataset/
2. ✅ Удалены дубликаты функций и комментариев
3. ✅ Исправлена логика ensure_fighter_exists — поиск по aliases ДО создания
4. ✅ Исправлена логика update_after_new_fight — поиск по aliases ДО создания
5. ✅ Добавлены get_canonical_name() и names_match_by_id()
6. ✅ add_ids_to_fight_in_memory использует glob для поиска part-файлов
================================================================
"""
import os
import json
import hashlib
import re
import glob
from pathlib import Path

# ============================================================================
# КОНСТАНТЫ (все пути в папке dataset/)
# ============================================================================
DATASET_DIR = Path("dataset")
FIGHTERS_IDS_FILE = DATASET_DIR / "fighters_ids.json"

# Таблица транслитерации (ЕДИНСТВЕННАЯ версия)
TRANS_TABLE = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


# ============================================================================
# ТРАНСЛИТЕРАЦИЯ И НОРМАЛИЗАЦИЯ
# ============================================================================
def _transliterate(text: str) -> str:
    """Простая транслитерация кириллицы в латиницу."""
    if not text:
        return ""
    return "".join(TRANS_TABLE.get(ch, ch) for ch in text.lower())


def normalize_fighter_name(name: str) -> str:
    """
    Полная нормализация имени бойца.
    Гарантирует, что 'Чарльз Оливейра' и 'Charles Oliveira' получат ОДИН ID.
    """
    if not name:
        return ""
    latin = _transliterate(name)
    return re.sub(r'[^a-z0-9]', '', latin)


# ============================================================================
# ГЕНЕРАЦИЯ ID И РАБОТА С ФАЙЛОМ
# ============================================================================
def generate_fighter_id(name: str) -> str:
    """Генерация детерминированного ID бойца."""
    norm = normalize_fighter_name(name)
    return "F_" + hashlib.md5(norm.encode('utf-8')).hexdigest()[:8]


def load_fighters_ids() -> dict:
    """Загрузка fighters_ids.json из папки dataset/."""
    if not FIGHTERS_IDS_FILE.exists():
        return {}
    try:
        with open(FIGHTERS_IDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"   ⚠️ Ошибка загрузки {FIGHTERS_IDS_FILE}: {e}")
        return {}


def save_fighters_ids(data: dict) -> bool:
    """Сохранение fighters_ids.json в папку dataset/."""
    try:
        # Создаём папку, если её нет
        DATASET_DIR.mkdir(exist_ok=True)
        with open(FIGHTERS_IDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"   ⚠️ Ошибка сохранения {FIGHTERS_IDS_FILE}: {e}")
        return False


# ============================================================================
# ПОИСК ПО ИМЕНИ (КРИТИЧЕСКИ ВАЖНО!)
# ============================================================================
def get_fighter_id_by_name(name: str) -> str:
    """
    Возвращает fighter_id по имени.

    Порядок поиска:
    1. Точное совпадение по детерминированному ID (быстро)
    2. Поиск по aliases (для случая, когда имя записано по-другому)
    3. Поиск по normalized
    """
    if not name or len(name) < 2:
        return None

    fighters = load_fighters_ids()

    # 1. Детерминированный поиск по MD5
    fighter_id = generate_fighter_id(name)
    if fighter_id in fighters:
        return fighter_id

    # 2. Fallback: поиск по aliases
    name_lower = name.lower().strip()
    norm_name = normalize_fighter_name(name)

    for fid, data in fighters.items():
        for alias in data.get("aliases", []):
            if alias.lower().strip() == name_lower:
                return fid
            if normalize_fighter_name(alias) == norm_name:
                return fid

        # 3. Проверка по normalized
        if data.get("normalized", "") == norm_name:
            return fid

    return None


# ============================================================================
# 🆕 КАНОНИЧЕСКОЕ ИМЯ И СРАВНЕНИЕ ЧЕРЕЗ ID
# ============================================================================
def get_canonical_name(name: str) -> str:
    """
    ✅ v2.3: Возвращает каноническое имя бойца.
    Приоритет: первый "чистый" alias на КИРИЛЛИЦЕ (с апострофами).
    """
    if not name or len(name.strip()) < 2:
        return name

    fighter_id = get_fighter_id_by_name(name)
    if not fighter_id:
        return name

    fighters = load_fighters_ids()
    if fighter_id not in fighters:
        return name

    aliases = fighters[fighter_id].get("aliases", [])
    if not aliases:
        return name

    # ✅ v2.3: Ищем первый "чистый" кириллический alias
    # "Чистый" = содержит кириллицу И не содержит мусор (скобки, "No Contest", прозвища)
    for alias in aliases:
        # Проверка: есть ли кириллица
        if not re.search(r'[а-яё]', alias, re.IGNORECASE):
            continue

        # Проверка: нет ли мусора
        if any(x in alias.lower() for x in ['no contest', 'nc', 'the ', 'killer']):
            continue

        # Проверка: есть ли апострофы (для имён типа "Шон О'Мэлли")
        # Это приоритетный alias
        if "'" in alias:
            return alias

    # Fallback: первый кириллический alias
    for alias in aliases:
        if re.search(r'[а-яё]', alias, re.IGNORECASE):
            return alias

    # Fallback: первый alias
    return aliases[0]

def names_match_by_id(name1: str, name2: str) -> bool:
    """
    ✅ v2.1: Сравнивает два имени через fighter_id.
    Решает проблему разночтений (латиница/кириллица).
    """
    if not name1 or not name2:
        return False

    id1 = get_fighter_id_by_name(name1)
    id2 = get_fighter_id_by_name(name2)

    if id1 and id2:
        return id1 == id2

    # Fallback на нормализованное сравнение
    norm1 = normalize_fighter_name(name1)
    norm2 = normalize_fighter_name(name2)
    return norm1 == norm2


# ============================================================================
# СОЗДАНИЕ/ОБНОВЛЕНИЕ БОЙЦА (ИСПРАВЛЕНО!)
# ============================================================================
def ensure_fighter_exists(name: str, fight_date: str = None) -> str:
    """
    ✅ v2.2: ИСПРАВЛЕНА КРИТИЧЕСКАЯ ОШИБКА!
    Сначала ищем по aliases, только потом создаём нового!
    """
    if not name or len(name) < 2:
        return None

    fighters = load_fighters_ids()

    # ✅ v2.2: СНАЧАЛА ищем по aliases через get_fighter_id_by_name
    existing_id = get_fighter_id_by_name(name)

    if existing_id:
        # Боец уже есть — добавляем alias, если его нет
        if name not in fighters[existing_id].get("aliases", []):
            fighters[existing_id].setdefault("aliases", []).append(name)
            save_fighters_ids(fighters)
            print(f"   ➕ Добавлен alias '{name}' к бойцу {existing_id}")
        return existing_id

    # Создаём нового только если не нашли
    fighter_id = generate_fighter_id(name)
    fighters[fighter_id] = {
        "normalized": normalize_fighter_name(name),
        "aliases": [name],
        "first_seen": fight_date,
        "fights_count": 1
    }
    save_fighters_ids(fighters)
    print(f"   🆕 Новый боец: {name} → {fighter_id}")
    return fighter_id

def ensure_both_fighters_exist(name_a: str, name_b: str, fight_date: str = None):
    """Гарантирует наличие обоих бойцов в fighters_ids.json."""
    id_a = ensure_fighter_exists(name_a, fight_date)
    id_b = ensure_fighter_exists(name_b, fight_date)
    return id_a, id_b


def increment_fights_count(fighter_id: str) -> bool:
    """Увеличивает счётчик боёв бойца на 1."""
    if not fighter_id:
        return False

    fighters = load_fighters_ids()
    if fighter_id not in fighters:
        print(f"   ⚠️ Боец {fighter_id} не найден")
        return False

    current_count = fighters[fighter_id].get("fights_count", 0)
    fighters[fighter_id]["fights_count"] = current_count + 1

    result = save_fighters_ids(fighters)
    if result:
        print(f"   📊 Счётчик боёв {fighter_id}: {current_count} → {current_count + 1}")
    return result


def update_after_new_fight(fighter_a_name: str, fighter_b_name: str, fight_date: str = None):
    """
    🎯 ГЛАВНАЯ ФУНКЦИЯ для вызова после train_on_new_fight().

    ✅ v2.1: ИСПРАВЛЕНА КРИТИЧЕСКАЯ ОШИБКА!
    Сначала ищем по aliases, только потом создаём нового.
    """
    fighters = load_fighters_ids()

    # ✅ Используем get_fighter_id_by_name для поиска
    id_a = get_fighter_id_by_name(fighter_a_name)
    id_b = get_fighter_id_by_name(fighter_b_name)

    # ===== Обработка бойца A =====
    if id_a and id_a in fighters:
        fighters[id_a]["fights_count"] = fighters[id_a].get("fights_count", 0) + 1
        if fighter_a_name not in fighters[id_a].get("aliases", []):
            fighters[id_a].setdefault("aliases", []).append(fighter_a_name)
            print(f"   ➕ Новый alias для бойца A: '{fighter_a_name}'")
    else:
        id_a = generate_fighter_id(fighter_a_name)
        fighters[id_a] = {
            "normalized": normalize_fighter_name(fighter_a_name),
            "aliases": [fighter_a_name],
            "first_seen": fight_date,
            "fights_count": 1
        }
        print(f"   🆕 Новый боец A: {fighter_a_name} → {id_a}")

    # ===== Обработка бойца B =====
    if id_b and id_b in fighters:
        fighters[id_b]["fights_count"] = fighters[id_b].get("fights_count", 0) + 1
        if fighter_b_name not in fighters[id_b].get("aliases", []):
            fighters[id_b].setdefault("aliases", []).append(fighter_b_name)
            print(f"   ➕ Новый alias для бойца B: '{fighter_b_name}'")
    else:
        id_b = generate_fighter_id(fighter_b_name)
        fighters[id_b] = {
            "normalized": normalize_fighter_name(fighter_b_name),
            "aliases": [fighter_b_name],
            "first_seen": fight_date,
            "fights_count": 1
        }
        print(f"   🆕 Новый боец B: {fighter_b_name} → {id_b}")

    # ===== Сохранение =====
    if save_fighters_ids(fighters):
        print(f"   ✅ fighters_ids.json обновлён (A={id_a}, B={id_b})")
        return id_a, id_b

    return None, None


# ============================================================================
# ДОБАВЛЕНИЕ ID В ФАЙЛЫ ПАМЯТИ (ИСПОЛЬЗУЕТ GLOB!)
# ============================================================================
def add_ids_to_fight_in_memory(fighter_a_name: str, fighter_b_name: str,
                               target_files: list = None) -> dict:
    """
    ✅ v2.2: Использует ТОЛЬКО part-файлы и кэш.
    Обращение к монолитному датасету УДАЛЕНО (файл разделён на части).
    """
    if target_files is None:
        target_files = [
            str(DATASET_DIR / "ufc_history_cache.json")
        ]
        # ✅ Добавляем ВСЕ part-файлы из dataset/
        for part_file in sorted(glob.glob(str(DATASET_DIR / "real_dataset_part*.json"))):
            target_files.append(part_file)

        # ❌ УДАЛЕНО: обращение к RRRreal_dataset.json / real_dataset.json
        # Файл разделён на части. Монолитного датасета больше не существует.

    id_a = get_fighter_id_by_name(fighter_a_name)
    id_b = get_fighter_id_by_name(fighter_b_name)

    if not id_a or not id_b:
        print(f"   ⚠️ Не удалось найти ID для имён: A={id_a}, B={id_b}")
        return {"updated_files": [], "fighter_a_id": id_a, "fighter_b_id": id_b}

    norm_a = normalize_fighter_name(fighter_a_name)
    norm_b = normalize_fighter_name(fighter_b_name)

    updated_files = []

    for filepath in target_files:
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                dataset = json.load(f)
        except Exception as e:
            print(f"   ⚠️ Ошибка чтения {filepath}: {e}")
            continue

        file_updated = False

        for fight in dataset:
            fa = fight.get("fighter_a", "")
            fb = fight.get("fighter_b", "")

            match_direct = (
                    normalize_fighter_name(fa) == norm_a and
                    normalize_fighter_name(fb) == norm_b
            )
            match_reverse = (
                    normalize_fighter_name(fa) == norm_b and
                    normalize_fighter_name(fb) == norm_a
            )

            if match_direct or match_reverse:
                if "fighter_a_id" not in fight:
                    fight["fighter_a_id"] = id_a if match_direct else id_b
                    file_updated = True

                if "fighter_b_id" not in fight:
                    fight["fighter_b_id"] = id_b if match_direct else id_a
                    file_updated = True

        if file_updated:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(dataset, f, ensure_ascii=False, indent=2)
                updated_files.append(filepath)
                print(f"   ✅ {os.path.basename(filepath)}: добавлены ID к бою {fighter_a_name} vs {fighter_b_name}")
            except Exception as e:
                print(f"   ❌ Ошибка сохранения {filepath}: {e}")

    return {
        "updated_files": updated_files,
        "fighter_a_id": id_a,
        "fighter_b_id": id_b
    }