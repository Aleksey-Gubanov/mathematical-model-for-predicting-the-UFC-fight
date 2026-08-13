#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MMA PREDICTION v44.2 | SENIOR PRODUCTION
================================================================
ИСПРАВЛЕНИЯ v44.2:
1. ✅ Все импорты собраны в одном месте с единой обработкой ошибок
2. ✅ The Odds API импортируется сразу (флаг HAS_ODDS_API)
3. ✅ Добавлены недостающие импорты (math, requests, fighters_ids_manager)
4. ✅ Готово для внедрения обогащения YandexGPT и реальных коэффов
================================================================
"""
import sys
import os
import re
import json
import uuid
import platform
import hashlib
import base64
import time
import math
import requests
import traceback
import glob as glob_module
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
from cryptography.fernet import Fernet

# Очистка буфера stdin (Windows)
try:
    import msvcrt
    WIN32 = True
except ImportError:
    WIN32 = False

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 🔑 ЕДИНЫЙ БЛОК ИМПОРТОВ
try:
    from secure_neural_channel import SecureNeuralChannel
    from math_engine import Fighter, FightData, Prediction, Result, FinishType, MMAEngine, names_match
    from ufc_parser import UFCParser
    from deep_ai_analyst import DeepAIAnalyst
    from sports_parser import SportsUFCScheduler
    from exchange_protocol import ExchangeProtocol
    from parser_worker import ParserWorker
    from fighters_ids_manager import (
        ensure_both_fighters_exist,
        add_ids_to_fight_in_memory,
        load_fighters_ids,
        get_canonical_name,
        names_match_by_id
    )
    from odds_api_client import OddsAPIClient
    HAS_ALL_IMPORTS = True
    HAS_ODDS_API = True
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    traceback.print_exc()
    HAS_ALL_IMPORTS = False
    HAS_ODDS_API = False
    sys.exit(1)

# ============================================================================
# КОНСТАНТЫ ПУТЕЙ
# ============================================================================
DATASET_DIR = "dataset"
REAL_DATASET_FILE = os.path.join(DATASET_DIR, "real_dataset.json")
FIGHTERS_IDS_FILE = os.path.join(DATASET_DIR, "fighters_ids.json")
MAX_DATASET_SIZE_MB = 2.2

# ============================================================================
# ЭТАП 1: ОЧИСТКА ВВОДА (ЗАЩИТА ОТ КОНКАТЕНАЦИИ)
# ============================================================================
def clear_input_buffer():
    """
    ✅ v44.3: БЕЗОПАСНАЯ очистка.
    Агрессивная очистка (msvcrt.getch) УДАЛЕНА, так как она уничтожала
    свежевставленный (Ctrl+V) текст в консоли Windows/IDE до того, как input() его считывал.
    """
    try:
        if not WIN32:  # Оставляем очистку только для Linux/Mac, где она работает корректно
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass
def sanitize_fighter_name(raw_name: str) -> str:
    """Удаляет скобки с рейтингами/статусами и лишние пробелы."""
    if not raw_name:
        return ""
    cleaned = re.sub(r'\s*\([^)]*\)', '', raw_name)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def clean_user_input(raw_input: str) -> str:
    """Очищает ввод пользователя от невидимых символов и пробелов между буквами."""
    if not raw_input:
        return ""

    # Шаг 1: Удаление невидимых символов
    cleaned = ''.join(c for c in raw_input if ord(c) > 31 and c not in '\u200b\u200c\u200d\u00a0\ufeff\u200e\u200f\u202a-\u202e')

    # Шаг 2: Нормализация тире
    cleaned = cleaned.replace('—', '-').replace('–', '-').replace('−', '-')

    # Шаг 3: Удаление табов и возвратов каретки
    cleaned = cleaned.replace('\t', ' ').replace('\r', ' ')

    # ✅ ШАГ 4: УДАЛЕНИЕ ПРОБЕЛОВ МЕЖДУ ОДИНОЧНЫМИ БУКВАМИ
    # Паттерн: буква + пробел + буква (где обе буквы одиночные)
    # 'А т е б а' → 'Атеба'
    # 'Атеба Готье' → 'Атеба Готье' (пробел между словами остаётся!)
    import re as re_module

    # Удаляем пробелы между одиночными буквами
    # Ищем паттерн: (буква)(пробелы)(буква), где буква не является частью слова
    for _ in range(10):  # Повторяем несколько раз для цепочек
        # Удаляем пробелы между буквами, если после буквы следует пробел и ещё одна буква
        new_cleaned = re_module.sub(r'([а-яёa-zA-Z])\s+([а-яёa-zA-Z])(?=\s|[^\wа-яёa-zA-Z]|$)', r'\1\2', cleaned, flags=re_module.IGNORECASE)
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned

    # Шаг 5: Удаление множественных пробелов
    cleaned = re_module.sub(r'\s+', ' ', cleaned)

    return cleaned.strip()

# ============================================================================
# ЭТАП 2: БЕЗОПАСНОСТЬ, HWID, ЛИМИТЫ
# ============================================================================
CONFIG_FILE = "mma_secure_config.enc"
DEV_API_KEY = "sk-your-dev-key-here"
MAX_DEV_PREDICTIONS = 100

def get_hwid() -> str:
    return hashlib.sha256(f"{uuid.getnode()}_{platform.platform()}".encode()).hexdigest()

def get_cipher(hwid: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(hwid.encode()).digest()))

def load_config(hwid: str) -> dict:
    default = {"hwid": hwid, "api_key": "", "predictions_used": 0, "is_agreed": False}
    if not os.path.exists(CONFIG_FILE):
        return default
    try:
        config = json.loads(get_cipher(hwid).decrypt(open(CONFIG_FILE, "rb").read()).decode('utf-8'))
        return config if config.get("hwid") == hwid else default
    except Exception:
        return default

def save_config(config: dict, hwid: str):
    with open(CONFIG_FILE, "wb") as f:
        f.write(get_cipher(hwid).encrypt(json.dumps(config).encode('utf-8')))

def check_api_access(config: dict) -> Tuple[str, str]:
    if not config.get("is_agreed"):
        return "", "agreement_required"
    user_key = config.get("api_key", "").strip()
    if user_key and user_key != DEV_API_KEY:
        return user_key, "ok"
    if config.get("predictions_used", 0) >= MAX_DEV_PREDICTIONS:
        return "", "limit_reached"
    return DEV_API_KEY, "ok"

def increment_prediction_count(config: dict, hwid: str):
    if config.get("api_key", "").strip() in ["", DEV_API_KEY]:
        config["predictions_used"] = config.get("predictions_used", 0) + 1
        save_config(config, hwid)

# ============================================================================
# ЭТАП 3: НОРМАЛИЗАЦИЯ ИМЁН (v43.11 — с ТРАНСЛИТЕРАЦИЕЙ!)
# ============================================================================
TRANS_TABLE = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}

def _transliterate(text: str) -> str:
    """Простая транслитерация кириллицы в латиницу."""
    if not text:
        return ""
    return "".join(TRANS_TABLE.get(ch, ch) for ch in text.lower())

def normalize_fighter_name(name: str) -> str:
    """✅ v43.11: Полная нормализация с ТРАНСЛИТЕРАЦИЕЙ."""
    if not name:
        return ""
    latin = _transliterate(name)
    latin = re.sub(r'\s*\([^)]*\)', '', latin)
    latin = re.sub(r',.*$', '', latin)
    return re.sub(r'[^a-z0-9]', '', latin)

def normalize_winner_name(fact_winner: str, f1_clean: str, f2_clean: str, parser: UFCParser) -> str:
    """✅ v43.15: Приводит имя победителя к тому же написанию, что и f1_clean/f2_clean."""
    if not fact_winner:
        return fact_winner

    # ✅ ИСПРАВЛЕНО: Защита от мусорных имён (конкатенация)
    if len(f1_clean) > 40 or f1_clean.count(' ') > 5:
        f1_clean = None
    if len(f2_clean) > 40 or f2_clean.count(' ') > 5:
        f2_clean = None

    # Сначала пытаемся найти точное совпадение
    if f1_clean:
        try:
            if parser._names_match(fact_winner, f1_clean):
                return f1_clean
        except Exception:
            pass

    if f2_clean:
        try:
            if parser._names_match(fact_winner, f2_clean):
                return f2_clean
        except Exception:
            pass

    # Если не нашли — используем каноническое имя
    from fighters_ids_manager import get_canonical_name
    canonical = get_canonical_name(fact_winner)
    if canonical and canonical != fact_winner:
        return canonical

    return fact_winner

# ============================================================================
# ЭТАП 4: ИИ-КОРРЕКЦИЯ ИМЁН
# ============================================================================
def canonicalize_names_with_db(raw_input: str, known_fighters: List[str]) -> Optional[Dict[str, str]]:
    """ИИ сопоставляет ввод пользователя с реальным списком имен."""
    import difflib

    if not known_fighters:
        return None

    expanded_fighters = list(known_fighters)

    try:
        fighters_ids = load_fighters_ids()
        aliases_added = 0
        for fid, data in fighters_ids.items():
            for alias in data.get("aliases", []):
                if alias and len(alias) > 2 and alias not in expanded_fighters:
                    expanded_fighters.append(alias)
                    aliases_added += 1
        print(f"   📚 fighters_ids.json: добавлено {aliases_added} aliases")
    except Exception as e:
        print(f"   ⚠️ Ошибка загрузки fighters_ids.json: {e}")

    # ✅ v44.0: Ищем part-файлы в папке dataset/
    # ✅ v44.3: Ищем part-файлы + кэш парсера в папке dataset/
    files_to_read = sorted(glob_module.glob(os.path.join(DATASET_DIR, "real_dataset_part*.json")))
    if os.path.exists(REAL_DATASET_FILE):
        files_to_read.append(REAL_DATASET_FILE)

    # ✅ v44.3: КРИТИЧНО — добавляем кэш парсера (там есть ВСЕ имена с сайта!)
    cache_file = os.path.join(DATASET_DIR, "ufc_history_cache.json")
    if os.path.exists(cache_file):
        files_to_read.append(cache_file)
    for filename in files_to_read:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                dataset = json.load(f)
            for fight in dataset:
                for field in ['fighter_a', 'fighter_b']:
                    name = fight.get(field, '')
                    if name and len(name) > 2 and re.search(r'[а-яё]', name, re.IGNORECASE):
                        if name not in expanded_fighters:
                            expanded_fighters.append(name)
        except Exception as e:
            print(f"   ⚠️ Ошибка чтения {filename}: {e}")

    print(f"   📊 Расширенная база имён: {len(known_fighters)} → {len(expanded_fighters)} имён")

    parts = None
    for sep in [" - ", " — ", " vs ", " VS ", " против "]:
        if sep in raw_input:
            parts = raw_input.split(sep, 1)
            break

    if not parts or len(parts) != 2:
        words = raw_input.split()
        if len(words) >= 2:
            mid = len(words) // 2
            parts = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            return None

    user_f1, user_f2 = parts[0].strip(), parts[1].strip()

    # ✅ ИСПРАВЛЕНО: Защита от мусорных имён (конкатенация)
    if len(user_f1) > 40 or user_f1.count(' ') > 5:
        print(f"   ⚠️ Первое имя слишком длинное ({len(user_f1)} символов). Возможно, мусор в буфере.")
        return None
    if len(user_f2) > 40 or user_f2.count(' ') > 5:
        print(f"   ⚠️ Второе имя слишком длинное ({len(user_f2)} символов). Возможно, мусор в буфере.")
        return None

    unique_fighters = list(set(expanded_fighters))

    norm_f1 = normalize_fighter_name(user_f1)
    norm_f2 = normalize_fighter_name(user_f2)

    print(f"   🔍 Нормализация ввода:")
    print(f"      • '{user_f1}' → '{norm_f1}'")
    print(f"      • '{user_f2}' → '{norm_f2}'")

    scored_f1 = []
    scored_f2 = []

    for fighter in unique_fighters:
        norm_fighter = normalize_fighter_name(fighter)
        score1 = difflib.SequenceMatcher(None, norm_f1, norm_fighter).ratio()
        score2 = difflib.SequenceMatcher(None, norm_f2, norm_fighter).ratio()
        scored_f1.append((fighter, score1))
        scored_f2.append((fighter, score2))

    scored_f1.sort(key=lambda x: x[1], reverse=True)
    scored_f2.sort(key=lambda x: x[1], reverse=True)

    best_f1_score = scored_f1[0][1] if scored_f1 else 0
    best_f2_score = scored_f2[0][1] if scored_f2 else 0

    print(f"   🔍 Проверка наличия в кэше (после нормализации):")
    print(f"      • '{user_f1}' → лучший матч: '{scored_f1[0][0]}' (сходство: {best_f1_score:.2f})")
    print(f"      • '{user_f2}' → лучший матч: '{scored_f2[0][0]}' (сходство: {best_f2_score:.2f})")

    # ✅ ИСПРАВЛЕНО: Порог снижен до 0.70, чтобы избежать отказа в поиске бойцов с похожей фамилией
    if best_f1_score < 0.70 or best_f2_score < 0.07:
        print(f"   ⚠️ Точное совпадение не найдено (сходство: {best_f1_score:.2f} / {best_f2_score:.2f}).")
        print(f"   💡 Передаем исходные имена парсеру для поиска на сайте...")
        return {"f1": user_f1, "f2": user_f2}


    top_similar = [f[0] for f in scored_f1[:50]] + [f[0] for f in scored_f2[:50]]
    top_similar = list(set(top_similar))[:100]

    fighters_list_str = ", ".join(top_similar)

    print(f"   📊 Fuzzy-matching: оба бойца найдены в кэше")

    prompt = f"""Ты эксперт по ММА. Пользователь ввел строку: "{raw_input}".
Вот официальный список имен бойцов из расписания: [{fighters_list_str}].
Твоя задача: найти в этом списке РОВНО ДВА имени, которые соответствуют вводу пользователя (исправь опечатки, транслит, игнорируй отсутствие тире).
Верни СТРОГО валидный JSON без markdown:
{{"f1": "Точное имя из списка", "f2": "Точное имя из списка"}}
Если не можешь найти два имени, верни: {{"f1": null, "f2": null}}"""

    try:
        response = SecureNeuralChannel.query(prompt, "CanonicalizeNamesWithDB")

        if isinstance(response, dict):
            data = response
        else:
            clean_response = str(response).replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', clean_response, re.DOTALL)
            try:
                data = json.loads(match.group()) if match else {}
            except json.JSONDecodeError:
                print(f"   ⚠️ Ошибка парсинга JSON от ИИ")
                data = {}

        f1 = data.get("f1")
        f2 = data.get("f2")

        if f1 and f2 and str(f1).lower() != "null" and str(f2).lower() != "null":
            f1_clean = str(f1).strip()
            f2_clean = str(f2).strip()

            fighters_lower = {f.lower(): f for f in top_similar}

            if f1_clean.lower() in fighters_lower and f2_clean.lower() in fighters_lower:
                norm_f1_ai = normalize_fighter_name(f1_clean)
                norm_f2_ai = normalize_fighter_name(f2_clean)

                score1_ai = difflib.SequenceMatcher(None, norm_f1, norm_f1_ai).ratio()
                score2_ai = difflib.SequenceMatcher(None, norm_f2, norm_f2_ai).ratio()

                score1_ai_rev = difflib.SequenceMatcher(None, norm_f2, norm_f1_ai).ratio()
                score2_ai_rev = difflib.SequenceMatcher(None, norm_f1, norm_f2_ai).ratio()

                direct_match = (score1_ai >= 0.70 and score2_ai >= 0.70)
                reverse_match = (score1_ai_rev >= 0.70 and score2_ai_rev >= 0.70)

                if direct_match or reverse_match:
                    print(f"   ✅ ИИ вернул валидные имена: '{f1_clean}' vs '{f2_clean}'")
                    return {
                        "f1": fighters_lower[f1_clean.lower()],
                        "f2": fighters_lower[f2_clean.lower()]
                    }
                else:
                    print(f"   ⚠️ ИИ вернул имена с низким сходством:")
                    print(f"      • '{f1_clean}' vs '{user_f1}': {score1_ai:.2f}")
                    print(f"      • '{f2_clean}' vs '{user_f2}': {score2_ai:.2f}")
                    print(f"   💡 Используем fuzzy-matching напрямую...")
        else:
            print(f"   ⚠️ ИИ вернул null или невалидные данные.")
            # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Запрет на подмену имен!
            # Если сходство низкое и ИИ не помог, возвращаем исходные имена пользователя.
            # Это позволит парсеру попробовать найти их на сайте по оригинальному написанию.
            print(f"   💡 Используем исходные имена для поиска на сайте: '{user_f1}' vs '{user_f2}'")
            return {"f1": user_f1, "f2": user_f2}

    except Exception as e:
        print(f"   ⚠️ Ошибка ИИ при коррекции имен: {e}")
        print(f"   ✅ Fallback после ошибки: '{scored_f1[0][0]}' vs '{scored_f2[0][0]}'")
        return {"f1": scored_f1[0][0], "f2": scored_f2[0][0]}

# ============================================================================
# ЭТАП 5: ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================
def extract_fighter_names(data) -> List[str]:
    names = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for field in ['fighter_a', 'fighter_b', 'fighter1', 'fighter2', 'name']:
                    name = item.get(field, '')
                    if name and len(name) > 2:
                        names.append(name)
    elif isinstance(data, dict):
        for key in ['fighter_a', 'fighter_b', 'fighter1', 'fighter2', 'name']:
            name = data.get(key, '')
            if name and len(name) > 2:
                names.append(name)
    return names

def strict_out(pred: Prediction, res: Optional[Result], fd: FightData, mode: str,
               matchup: dict, a: str, b: str,
               acc_win: float = 0.0, acc_rnd: float = 0.0, acc_mth: float = 0.0) -> str:
    """✅ v44.0: Единый кириллический вывод для ВСЕХ полей таблицы."""
    from fighters_ids_manager import get_canonical_name, names_match_by_id

    try:
        odds_a_val, odds_b_val = float(matchup.get('odds_a', 1.85)), float(matchup.get('odds_b', 1.85))
    except (ValueError, TypeError):
        odds_a_val, odds_b_val = 1.85, 1.85

    book = str(matchup.get('bookmaker', '—'))

    if book in ['—', 'Нейтрально'] or (odds_a_val == 1.85 and odds_b_val == 1.85):
        odds_a_str, odds_b_str, book_str = "Уточняется", "Уточняется", "—"
    else:
        odds_a_str, odds_b_str, book_str = str(odds_a_val), str(odds_b_val), book

    pred_winner_canonical = get_canonical_name(pred.winner)

    win_txt = "НИЧЬЯ" if pred.method == FinishType.DRAW else pred_winner_canonical

    pred_rnd = getattr(pred, 'rnd', getattr(pred, 'round', '?'))

    if res:
        real_win = 100.0 if names_match_by_id(pred.winner, res.winner) else 0.0
        res_w_canonical = get_canonical_name(res.winner)
        res_r = str(res.rnd)
        res_m = res.method.value
        pred_rnd_txt = f"{pred_rnd} (предпол.)"
        pred_mth_txt = f"{pred.method.value} (предпол.)"
        acc_win_display = real_win
        acc_rnd_display = 0.0
        acc_mth_display = 0.0
    else:
        res_w_canonical = 'Ожидание'
        res_r = 'Ожидание'
        res_m = 'Ожидание'
        pred_rnd_txt = f"{pred_rnd} (предпол.)"
        pred_mth_txt = f"{pred.method.value} (предпол.)"
        acc_win_display = 0.0
        acc_rnd_display = 0.0
        acc_mth_display = 0.0

    a_canonical = get_canonical_name(a)
    b_canonical = get_canonical_name(b)

    high_dispersion_flag = ""
    if res is None and 0.45 <= pred.prob <= 0.55:
        high_dispersion_flag = " ⚠️ ВЫСОКАЯ ДИСПЕРСИЯ"

    lines = [
        "=" * 78,
        f"🔮 ПРОГНОЗ: {win_txt} — {int(pred.prob * 100)}% ±{int((pred.ci_hi - pred.ci_lo) * 100)}%{high_dispersion_flag}",
        f"   Раунд {pred_rnd_txt} | {pred_mth_txt}",
        "-" * 78,
        "📊 СРАВНЕНИЕ: Прогноз vs Факт",
        f"| Параметр | Прогноз модели | Реальный Факт | Точность |",
        f"|-|-|-|-|",
        f"| Победитель | {win_txt:<19} | {res_w_canonical:<17} | {acc_win_display:>5.1f}% |",
        f"| Раунд | {pred_rnd_txt:<19} | {res_r:<17} | — |",
        f"| Способ | {pred_mth_txt:<19} | {res_m:<17} | — |",
        f"| Коэфф. {a_canonical:<10} | 1/{pred.prob:.2f} (Модель) | {odds_a_str} ({book_str}) |",
        f"| Коэфф. {b_canonical:<10} | 1/{1 - pred.prob:.2f} (Модель) | {odds_b_str} ({book_str}) |",
        "=" * 78
    ]

    if high_dispersion_flag:
        lines.append("⚠️ СЦЕНАРНОЕ ДЕРЕВО (высокая неопределённость):")
        lines.append(f"   • Сценарий A (60%): {win_txt} побеждает решением")
        lines.append(f"   • Сценарий B (25%): {b_canonical if win_txt == a_canonical else a_canonical} побеждает нокаутом")
        lines.append(f"   • Сценарий C (15%): Ничья / нестандартный исход")
        lines.append("=" * 78)

    return "\n".join(lines)

def load_accuracy_metrics(engine: MMAEngine) -> Tuple[float, float, float]:
    """✅ v44.0: Загружает метрики точности из всех part-файлов в dataset/"""
    try:
        dataset = []
        part_files = sorted(glob_module.glob(os.path.join(DATASET_DIR, "real_dataset_part*.json")))

        for part_file in part_files:
            try:
                with open(part_file, "r", encoding="utf-8") as f:
                    dataset.extend(json.load(f))
            except Exception as e:
                print(f"   ⚠️ Ошибка чтения {part_file}: {e}")

        if os.path.exists(REAL_DATASET_FILE):
            try:
                with open(REAL_DATASET_FILE, "r", encoding="utf-8") as f:
                    dataset.extend(json.load(f))
            except Exception as e:
                print(f"   ⚠️ Ошибка чтения {REAL_DATASET_FILE}: {e}")

        if not dataset:
            return 0.0, 0.0, 0.0

        return engine.get_recent_accuracies(dataset)

    except Exception as e:
        print(f"   ⚠️ Не удалось загрузить метрики точности: {e}")
        return 0.0, 0.0, 0.0

# ============================================================================
# ЭТАП 6: ОБРАБОТКА КОМАНД КАЛИБРОВКИ
# ============================================================================
def handle_calibration_command(subcommand: str, engine: MMAEngine):
    try:
        if subcommand == "3a":
            print("⏳ Проверка точности...")
            try:
                dataset = engine.load_full_dataset()
                if len(dataset) < 5:
                    print("⚠️ Недостаточно данных для проверки")
                else:
                    acc_win, acc_rnd, acc_mth = engine.get_recent_accuracies(dataset)

                    print(f"📊 ТОЧНОСТЬ (все бои):")
                    print(f"   Победитель: {acc_win:.1f}%")
                    print(f"   Раунд: {acc_rnd:.1f}%")
                    print(f"   Метод: {acc_mth:.1f}%")

                    print(f"📊 СРАВНЕНИЕ С ЭТАЛОНАМИ:")
                    print(f"   🛡️ Эталон: {engine.baseline_accuracy * 100:.1f}%")
                    print(f"   🏆 Лучшие веса: {engine.best_accuracy * 100:.1f}%")

                    acc_win_ratio = acc_win / 100.0

                    if acc_win_ratio < engine.best_accuracy - 0.03:
                        print(f"⚠️ Деградация! Точность ниже лучших весов на {(engine.best_accuracy - acc_win_ratio) * 100:.1f}%!")
                        print("   Рекомендуется откат к лучшим весам (команда 3b)")
                    elif acc_win_ratio < engine.baseline_accuracy - 0.05:
                        print(f"🔴 Критическая деградация!")
                        print("   Рекомендуется откат к эталону (команда 3c)")
                    else:
                        print("✅ Модель в норме. Деградации не обнаружено.")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                traceback.print_exc()

        elif subcommand == "3b":
            print("🔄 Откат к лучшим весам...")
            engine.rollback_to_best()

        elif subcommand == "3c":
            print("🛡️ Откат к эталону...")
            confirm = input("   ⚠️ Это сбросит все накопленные знания! Продолжить? (y/n): ").strip().lower()
            if confirm == 'y':
                engine.rollback_to_baseline()
            else:
                print("   ❌ Отменено")

        elif subcommand == "3d":
            print(f"📊 СТАТУС ВЕСОВ:")
            print(f"   🛡️ Эталон: {engine.baseline_accuracy * 100:.1f}% (weights_baseline.json)")
            print(f"   🏆 Лучшие веса: {engine.best_accuracy * 100:.1f}% (weights_best.json)")
            print(f"   ⚙️ Стабильность: {engine.stability_score:.1f}")
            print(f"   ✅ Успехи подряд: {engine.success_counter}")
            print(f"   ❌ Ошибки подряд: {engine.fail_counter}")

            print(f"📁 ФАЙЛЫ:")
            files_to_check = [
                "mma_weights_v21.json",
                "weights_baseline.json",
                "weights_best.json",
                os.path.join(DATASET_DIR, "fighters_ids.json"),
                REAL_DATASET_FILE
            ]

            for f in files_to_check:
                exists = "✅" if os.path.exists(f) else "❌"
                print(f"   {exists} {f}")

            part_files = sorted(glob_module.glob(os.path.join(DATASET_DIR, "real_dataset_part*.json")))
            if part_files:
                print(f"📁 PART-ФАЙЛЫ ({len(part_files)} шт):")
                for pf in part_files:
                    size_mb = os.path.getsize(pf) / (1024 * 1024)
                    print(f"   ✅ {pf} ({size_mb:.2f} МБ)")
        else:
            print("❌ Неверная команда")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()

# ============================================================================
# ЭТАП 7: ОБОГАЩЕНИЕ ДАННЫХ ЧЕРЕЗ YANDEXGPT 5.1
# ============================================================================
def enrich_fighters_via_yandex(f1_clean: str, f2_clean: str, target_date: str, pwd: str,
                               fighter_a_stats: Dict = None, fighter_b_stats: Dict = None) -> Tuple[Dict, Dict]:
    protocol = ExchangeProtocol()

    old_pending = protocol.get_pending_requests()
    if old_pending:
        print(f"   🧹 Очистка {len(old_pending)} старых запросов...")
        for req in old_pending:
            try:
                protocol.cleanup_request(req['id'])
            except Exception:
                pass

    req_id_a = protocol.create_request(
        request_type="enrich",
        data={"fighter_name": f1_clean, "fight_date": target_date, "fighter_stats": fighter_a_stats or {}},
        priority=5
    )

    req_id_b = protocol.create_request(
        request_type="enrich",
        data={"fighter_name": f2_clean, "fight_date": target_date, "fighter_stats": fighter_b_stats or {}},
        priority=5
    )

    print(f"   📤 Созданы запросы: {req_id_a}, {req_id_b}")

    abs_responses_dir = os.path.abspath(protocol.RESPONSES_DIR)
    print(f"   📂 Папка ответов (абс. путь): {abs_responses_dir}")

    worker = ParserWorker(master_password=pwd)

    pending = protocol.get_pending_requests()
    our_requests = [r for r in pending if r['id'] in [req_id_a, req_id_b]]
    print(f"   🔍 Найдено наших запросов: {len(our_requests)}")

    for our_req in our_requests:
        try:
            fighter_name = our_req['data'].get('fighter_name')
            print(f"   🔄 Обработка: {our_req['id']} ({fighter_name})")

            result = worker._handle_enrich(our_req['data'])
            result_data = result.get("data", {})

            for k, v in result_data.items():
                try:
                    json.dumps({k: v})
                except (TypeError, ValueError):
                    result_data[k] = str(v)

            protocol.write_response(
                request_id=our_req['id'],
                status=result.get("status", "error"),
                data=result_data,
                error=result.get("error"),
                validation=result.get("validation", {"complete": False})
            )

            expected_file = os.path.join(protocol.RESPONSES_DIR, f"res_{our_req['id']}.json")
            if os.path.exists(expected_file):
                file_size = os.path.getsize(expected_file)
                print(f"   ✅ Файл ответа создан: {os.path.basename(expected_file)} ({file_size} байт)")
            else:
                print(f"   🔴 КРИТИЧНО: Файл ответа НЕ СОЗДАН: {expected_file}")

            if hasattr(protocol, 'cleanup_request_only'):
                protocol.cleanup_request_only(our_req['id'])

            print(f"   ✅ Обработано: {result.get('status')}")

        except Exception as e:
            print(f"   ❌ Ошибка обработки {our_req['id']}: {e}")
            traceback.print_exc()
            try:
                protocol.cleanup_request_only(our_req['id'])
            except Exception:
                pass

    print(f"   📥 Чтение ответов...")

    def wait_for_response(req_id, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = protocol.get_response(req_id, timeout=1)
                if response and response.get("status") == "success":
                    return response
            except Exception:
                pass
            time.sleep(0.5)
        return None

    response_a = wait_for_response(req_id_a, timeout=30)
    response_b = wait_for_response(req_id_b, timeout=30)

    enrichment_a = response_a.get("data", {}) if response_a and response_a.get("status") == "success" else {}
    enrichment_b = response_b.get("data", {}) if response_b and response_b.get("status") == "success" else {}

    try:
        protocol.cleanup_request(req_id_a)
        protocol.cleanup_request(req_id_b)
    except Exception as e:
        print(f"   ⚠️ Ошибка очистки: {e}")

    return enrichment_a, enrichment_b

# ============================================================================
# ЭТАП 8: ЗАГРУЗКА/СОХРАНЕНИЕ КЭША БОЙЦОВ
# ============================================================================
def load_known_fighters_cache() -> List[str]:
    cache_file = "known_fighters_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_known_fighters_cache(fighters_list: List[str]):
    cache_file = "known_fighters_cache.json"
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(fighters_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"   ⚠️ Не удалось сохранить кэш бойцов: {e}")

# ============================================================================
# ЭТАП 9: ГЛАВНЫЙ ЦИКЛ (v44.1 — с внедрением коэффициентов)
# ============================================================================
if __name__ == "__main__":
    try:
        print("=" * 70)
        print("🔵 MMA PREDICTION v44.1 | SENIOR PRODUCTION")
        print("=" * 70)

        current_hwid = get_hwid()
        config = load_config(current_hwid)

        if not config.get("is_agreed"):
            print("\n" + "=" * 70)
            print("⚖️ ЮРИДИЧЕСКОЕ СОГЛАШЕНИЕ")
            print("1. Прогнозы носят исключительно информационный характер.")
            print("2. Они не являются финансовой рекомендацией или призывом к ставкам.")
            print("3. Используя модель, вы принимаете полную ответственность за свои решения.")
            print("4. Ваш API-ключ будет зашифрован и привязан к этому устройству (HWID).")
            print("=" * 70)

            clear_input_buffer()
            agree = input("Введите 'Y' для принятия соглашения: ").strip().upper()

            if agree == 'Y':
                config["is_agreed"] = True
                save_config(config, current_hwid)
                print("✅ Соглашение принято.")
            else:
                print("❌ Доступ запрещен. Выход.")
                sys.exit(0)

        api_key, status = check_api_access(config)

        if status == "limit_reached":
            print("⚠️ Лимит бесплатных прогнозов разработчика (100) исчерпан.")
            clear_input_buffer()
            new_key = input("🔑 Введите ваш личный API ключ DeepSeek (или Enter для выхода): ").strip()

            if new_key:
                config["api_key"] = new_key
                save_config(config, current_hwid)
                print("✅ Ключ сохранен. Доступ восстановлен.")
            else:
                sys.exit(0)

        if config.get("api_key") and config["api_key"] != DEV_API_KEY:
            SecureNeuralChannel.set_custom_api_key(config["api_key"])

        pwd = ""
        try:
            clear_input_buffer()
            pwd = input("🔐 Мастер-пароль: ")

            if not SecureNeuralChannel.init(pwd):
                sys.exit(1)

            # ✅ v2.0: Инициализация SecureKeys для The Odds API
            try:
                from secure_keys import SecureKeys
                if not SecureKeys.init(pwd):
                    print("⚠️ SecureKeys не инициализирован. Коэффициенты будут недоступны.")
            except ImportError:
                print("⚠️ SecureKeys не найден. Коэффициенты будут недоступны.")

        except Exception as e:
            print(f"❌ Ошибка инициализации канала: {e}")
            sys.exit(1)

        print("⏳ Проверка ИИ...")
        try:
            if SecureNeuralChannel.query('Верни JSON: {"status":"ok"}', "Тест").get("status") == "ok":
                print("✅ ИИ работает.")
        except Exception:
            print("⚠️ ИИ не ответил, но продолжаем.")

        print("⚙️ Инициализация модулей...")

        engine = MMAEngine()
        parser = UFCParser()
        analyst = DeepAIAnalyst()
        scheduler = SportsUFCScheduler()

        print("   📥 Загрузка базы имён из sports.ru для ПРОГНОЗА...")
        try:
            all_fights = scheduler.parse_schedule()
            known_fighters_forecast = []
            for f in all_fights:
                if f.get('fighter1'):
                    known_fighters_forecast.append(f['fighter1'])
                if f.get('fighter2'):
                    known_fighters_forecast.append(f['fighter2'])
            print(f"   ✅ Загружено {len(set(known_fighters_forecast))} уникальных имён для ПРОГНОЗА.")
        except Exception as e:
            print(f"   ❌ Не удалось загрузить расписание: {e}")
            known_fighters_forecast = []

        print("   📥 Загрузка базы имён для ОБУЧЕНИЯ...")
        known_fighters_training = load_known_fighters_cache()

        if not known_fighters_training:
            print("   ⚠️ Кэш пуст, загрузка из championat.com...")
            try:
                known_fighters_training = parser.get_all_known_fighters()
                save_known_fighters_cache(known_fighters_training)
            except Exception as e:
                print(f"   ❌ Не удалось загрузить историю: {e}")
                known_fighters_training = []
        else:
            print(f"   ✅ Загружено {len(set(known_fighters_training))} уникальных имён из кэша.")

        if not known_fighters_training:
            print("   ⚠️ База бойцов пуста! Загрузка из резервных источников...")
            backup_sources = [
                REAL_DATASET_FILE,
                FIGHTERS_IDS_FILE,
                "ufc_fighters.json"
            ]

            for source in backup_sources:
                if os.path.exists(source):
                    try:
                        with open(source, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        fighters = extract_fighter_names(data)
                        if fighters:
                            known_fighters_training = list(set(fighters))
                            save_known_fighters_cache(known_fighters_training)
                            print(f"   ✅ Загружено {len(known_fighters_training)} имён из {source}")
                            break
                    except Exception as e:
                        print(f"   ⚠️ Ошибка загрузки из {source}: {e}")
                        continue

        print("   📥 Загрузка fighters_ids.json...")
        try:
            fighters_ids_data = load_fighters_ids()
            print(f"   ✅ Загружено {len(fighters_ids_data)} бойцов с ID.")
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки fighters_ids.json: {e}")
            fighters_ids_data = {}

        mode = "ПРОГНОЗ"

        print("✅ Готово к работе.")

        # 4. Основной цикл
        while True:
            try:
                print(f"{'=' * 70}")
                print(f"📊 Режим: {mode}")
                print("Команды: 1 - Прогноз | 2 - Обучение | 3 - Калибровка | 3a/3b/3c/3d - Быстрые команды | 0 - Выход")
                print(f"{'=' * 70}")

                clear_input_buffer()
                raw_input_str = input("📥 Введите бойцов (Имя1 - Имя2) или команду: ")

                user_in = clean_user_input(raw_input_str)

                if not user_in:
                    continue

                if user_in == "0":
                    print("👋 Выход.")
                    break

                if user_in == "1":
                    mode = "ПРОГНОЗ"
                    print("✅ Режим: ПРОГНОЗ")
                    continue

                if user_in == "2":
                    mode = "ОБУЧЕНИЕ"
                    print("✅ Режим: ОБУЧЕНИЕ")
                    continue

                if user_in == "3":
                    print("\n" + "=" * 70)
                    print("📊 КАЛИБРОВКА И ЗАЩИТА МОДЕЛИ")
                    print("=" * 70)
                    print("   3a - Быстрая проверка точности (2-3 сек)")
                    print("   3b - Откат к лучшим весам (1 сек)")
                    print("   3c - Откат к эталону (1 сек)")
                    print("   3d - Показать статус весов")
                    print("   0 - Назад в главное меню")
                    print("=" * 70)

                    clear_input_buffer()
                    subcommand = input("Ваш выбор: ").strip()

                    if subcommand == "0":
                        print("↩️ Возврат в главное меню")
                    else:
                        handle_calibration_command(subcommand, engine)

                    continue

                if user_in in ["3a", "3b", "3c", "3d"]:
                    handle_calibration_command(user_in, engine)
                    continue

                print(f"🔍 ИИ анализирует ввод: '{user_in}'...")

                current_db = known_fighters_training if mode == "ОБУЧЕНИЕ" else known_fighters_forecast

                names = canonicalize_names_with_db(user_in, current_db)

                if not names:
                    print("❌ Не верный ввод. Модель не может сопоставить имена с базой парсера.")
                    continue

                f1_clean = names["f1"]
                f2_clean = names["f2"]

                print(f"   ✅ ИИ успешно сопоставил: '{f1_clean}' vs '{f2_clean}'")

                try:
                    if mode == "ОБУЧЕНИЕ":
                        print("📄 Шаг 1: Поиск исторического факта в локальном архиве...")

                        fact = parser.get_fight_result(f1_clean, f2_clean)

                        if not fact or 'winner' not in fact:
                            print("   ❌ Бой не найден в архиве парсера.")
                            print("   ⚠️ ИИ не используется для получения фактов боя (защита от галлюцинаций).")
                            print("   💡 Проверьте правильность написания имен или используйте режим ПРОГНОЗ для будущих боев.")
                            continue

                        print(f"   ✅ ФАКТ найден: {fact['date'].strftime('%d.%m.%Y')} | {fact['winner']} ({fact['method']}, R{fact['round']})")

                        target_date = (fact['date'] - timedelta(days=1)).strftime("%Y-%m-%d")

                        fact_winner_normalized = normalize_winner_name(fact['winner'], f1_clean, f2_clean, parser)

                        if fact_winner_normalized != fact['winner']:
                            print(f"   🔄 v43.10: Имя победителя нормализовано: '{fact['winner']}' → '{fact_winner_normalized}'")

                        print(f"   🧠 Шаг 2: ИИ собирает предматчевую статистику на {target_date}...")

                        fa = analyst.get_fighter_deep_stats(f1_clean, target_date)
                        fb = analyst.get_fighter_deep_stats(f2_clean, target_date)

                        print(f"   🧠 Шаг 3: Обогащение данных через YandexGPT 5.1...")

                        enrichment_a, enrichment_b = enrich_fighters_via_yandex(
                            f1_clean, f2_clean, target_date, pwd,
                            fighter_a_stats={
                                "age": fa.age,
                                "wins": fa.wins,
                                "losses": fa.losses,
                                "country": fa.flag,
                                "opponent_name": f2_clean,
                                "opponent_record": f"{fb.wins}-{fb.losses}",
                                "fight_context": "regular",
                                "recent_form": fa.form
                            },
                            fighter_b_stats={
                                "age": fb.age,
                                "wins": fb.wins,
                                "losses": fb.losses,
                                "country": fb.flag,
                                "opponent_name": f1_clean,
                                "opponent_record": f"{fa.wins}-{fa.losses}",
                                "fight_context": "regular",
                                "recent_form": fb.form
                            }
                        )

                        print(f"   ✅ Обогащение получено:")
                        if enrichment_a:
                            print(f"      {f1_clean}: stress={enrichment_a.get('stress_factor', 0.5):.2f}, motivation={enrichment_a.get('motivation_index', 0.5):.2f}, mystic_v2={enrichment_a.get('mystic_v2', 0.5):.2f}")
                        else:
                            print(f"      {f1_clean}: ❌ Данные не получены!")

                        if enrichment_b:
                            print(f"      {f2_clean}: stress={enrichment_b.get('stress_factor', 0.5):.2f}, motivation={enrichment_b.get('motivation_index', 0.5):.2f}, mystic_v2={enrichment_b.get('mystic_v2', 0.5):.2f}")
                        else:
                            print(f"      {f2_clean}: ❌ Данные не получены!")

                        # ✅ КРИТИЧЕСКИ ВАЖНО: Явное присвоение всех 6 параметров, включая mystic_v2
                        if enrichment_a:
                            fa.stress_factor = enrichment_a.get('stress_factor', fa.stress_factor)
                            fa.motivation_index = enrichment_a.get('motivation_index', fa.motivation_index)
                            fa.biorythm_score = enrichment_a.get('biorythm_score', fa.biorythm_score)
                            fa.camp_quality = enrichment_a.get('camp_quality', fa.camp_quality)
                            fa.mystic_factor = enrichment_a.get('mystic_factor', fa.mystic_factor)
                            fa.mystic_v2 = enrichment_a.get('mystic_v2', getattr(fa, 'mystic_v2', 0.5))

                        if enrichment_b:
                            fb.stress_factor = enrichment_b.get('stress_factor', fb.stress_factor)
                            fb.motivation_index = enrichment_b.get('motivation_index', fb.motivation_index)
                            fb.biorythm_score = enrichment_b.get('biorythm_score', fb.biorythm_score)
                            fb.camp_quality = enrichment_b.get('camp_quality', fb.camp_quality)
                            fb.mystic_factor = enrichment_b.get('mystic_factor', fb.mystic_factor)
                            fb.mystic_v2 = enrichment_b.get('mystic_v2', getattr(fb, 'mystic_v2', 0.5))

                        matchup = {"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85}

                        fd = FightData(
                            a=fa, b=fb,
                            date=fact['date'],
                            wc="Auto",
                            rounds=int(fact.get('round', 3)),
                            location=fact.get('tournament', 'UFC')
                        )

                        meth_map = {
                            'UD': FinishType.DECISION_UNANIMOUS,
                            'SD': FinishType.DECISION_SPLIT,
                            'MD': FinishType.DECISION_UNANIMOUS,
                            'DEC': FinishType.DECISION_UNANIMOUS,
                            'TKO': FinishType.TKO,
                            'KO': FinishType.KO,
                            'SUB': FinishType.SUBMISSION
                        }

                        res = Result(
                            winner=fact_winner_normalized,
                            rnd=int(fact['round']),
                            method=meth_map.get(str(fact['method']).upper(), FinishType.DECISION_UNANIMOUS)
                        )

                        print("\n⚙️ Шаг 4: Расчет прогноза моделью и инкрементальное обучение...")

                        pred = engine.predict(fd)
                        print("🔄 ДОБАВЛЕНИЕ НОВОГО БОЯ И ОБУЧЕНИЕ...")

                        train_result = engine.train_on_new_fight(fd, res, f1_clean, f2_clean)

                        if train_result and train_result.get("status") in ["updated", "trained"]:
                            status_text = train_result.get("status_text", "✅ Обучение")
                            print(f"   {status_text}")
                            print(f"   ✅ {train_result.get('corrections', '0')}")
                            print(f"   📊 {train_result.get('accuracy_str', 'Точность обновлена')}")
                            print("   💾 Веса и датасет сохранены.")

                            fight_date_str = fd.date.strftime("%Y-%m-%d")
                            id_a, id_b = ensure_both_fighters_exist(f1_clean, f2_clean, fight_date_str)

                            if id_a and id_b:
                                print(f"   🔗 Добавление ID в файлы памяти...")
                                id_result = add_ids_to_fight_in_memory(f1_clean, f2_clean)
                                if id_result.get("updated_files"):
                                    print(f"   ✅ ID добавлены в: {', '.join(id_result['updated_files'])}")

                            updated = False
                            if f1_clean not in known_fighters_training:
                                known_fighters_training.append(f1_clean)
                                updated = True
                            if f2_clean not in known_fighters_training:
                                known_fighters_training.append(f2_clean)
                                updated = True

                            if updated:
                                save_known_fighters_cache(known_fighters_training)
                                print(f"   💾 Кэш бойцов обновлён ({len(known_fighters_training)} имён)")

                        elif train_result and train_result.get("status") == "rollback_best":
                            print(f"   ⚠️ Откат к лучшим весам: {train_result.get('accuracy', 0)*100:.1f}%")
                        elif train_result and train_result.get("status") == "rollback_baseline":
                            print(f"   🔴 Откат к эталону: {train_result.get('accuracy', 0)*100:.1f}%")

                        from fighters_ids_manager import names_match_by_id
                        real_win = 100.0 if names_match_by_id(pred.winner, res.winner) else 0.0
                        real_rnd = 100.0 if pred.rnd == res.rnd else 0.0
                        real_mth = 100.0 if pred.method == res.method else 0.0

                        print("\n" + strict_out(pred, res, fd, mode, matchup, f1_clean, f2_clean, real_win, real_rnd, real_mth))
                        print("\n" + "=" * 70)
                        print("✅ Операция завершена. Ожидание следующей команды...")
                        print("=" * 70)
                        continue

                    else:  # РЕЖИМ ПРОГНОЗ
                        print("🧠 Шаг 1: ИИ собирает текущую статистику бойцов...")
                        target = datetime.now().strftime("%Y-%m-%d")

                        f1_clean_for_ai = sanitize_fighter_name(f1_clean)
                        f2_clean_for_ai = sanitize_fighter_name(f2_clean)

                        fa = analyst.get_fighter_deep_stats(f1_clean_for_ai, target)
                        fb = analyst.get_fighter_deep_stats(f2_clean_for_ai, target)

                        if not fa or not fb:
                            print("   ❌ ОШИБКА: ИИ-аналитик не смог собрать статистику (вернул None).")
                            continue

                        print("🧠 Шаг 1.5: Обогащение данных через YandexGPT 5.1...")
                        enrichment_a, enrichment_b = enrich_fighters_via_yandex(
                            f1_clean_for_ai, f2_clean_for_ai, target, pwd,
                            fighter_a_stats={"age": fa.age, "wins": fa.wins, "losses": fa.losses, "country": fa.flag},
                            fighter_b_stats={"age": fb.age, "wins": fb.wins, "losses": fb.losses, "country": fb.flag}
                        )

                        print(f"   ✅ Обогащение получено:")
                        if enrichment_a:
                            print(f"      {f1_clean_for_ai}: stress={enrichment_a.get('stress_factor', 0.5):.2f}, mystic_v2={enrichment_a.get('mystic_v2', 0.5):.2f}")
                            fa.stress_factor = enrichment_a.get('stress_factor', fa.stress_factor)
                            fa.motivation_index = enrichment_a.get('motivation_index', fa.motivation_index)
                            fa.biorythm_score = enrichment_a.get('biorythm_score', fa.biorythm_score)
                            fa.camp_quality = enrichment_a.get('camp_quality', fa.camp_quality)
                            fa.mystic_factor = enrichment_a.get('mystic_factor', fa.mystic_factor)
                            fa.mystic_v2 = enrichment_a.get('mystic_v2', getattr(fa, 'mystic_v2', 0.5))
                        else:
                            print(f"      {f1_clean_for_ai}: ❌ Данные не получены")

                        if enrichment_b:
                            print(f"      {f2_clean_for_ai}: stress={enrichment_b.get('stress_factor', 0.5):.2f}, mystic_v2={enrichment_b.get('mystic_v2', 0.5):.2f}")
                            fb.stress_factor = enrichment_b.get('stress_factor', fb.stress_factor)
                            fb.motivation_index = enrichment_b.get('motivation_index', fb.motivation_index)
                            fb.biorythm_score = enrichment_b.get('biorythm_score', fb.biorythm_score)
                            fb.camp_quality = enrichment_b.get('camp_quality', fb.camp_quality)
                            fb.mystic_factor = enrichment_b.get('mystic_factor', fb.mystic_factor)
                            fb.mystic_v2 = enrichment_b.get('mystic_v2', getattr(fb, 'mystic_v2', 0.5))
                        else:
                            print(f"      {f2_clean_for_ai}: ❌ Данные не получены")

                        print("   📅 Шаг 2: Поиск боя в расписании sports.ru...")
                        fight_info = scheduler.find_fight(f1_clean_for_ai, f2_clean_for_ai)

                        if fight_info:
                            print(f"   ✅ БОЙ ПОДТВЕРЖДЕН: {fight_info['event_name']} ({fight_info['event_date']})")
                            ev_date = datetime.strptime(fight_info['event_date'], "%d.%m.%Y")
                            rounds = int(fight_info.get('rounds', 3))
                            event_name = fight_info['event_name']
                            location = fight_info.get('location', 'UFC')
                        else:
                            print("   ⚠️ Бой не найден в расписании. Используем данные по умолчанию.")
                            ev_date = datetime.now()
                            rounds = 3
                            event_name = 'UFC Fight Night'
                            location = 'UFC'

                        print("   💰 Шаг 3: Запрос реальных коэффициентов...")
                        odds_a_num, odds_b_num, bookmaker = 1.85, 1.85, 'Нейтрально'

                        if HAS_ODDS_API:
                            try:
                                odds_client = OddsAPIClient()
                                odds_result = odds_client.get_fight_odds(f1_clean_for_ai, f2_clean_for_ai)
                                if odds_result:
                                    print(f"   ✅ РЕАЛЬНЫЕ коэффициенты: {odds_result['odds_a']:.2f} / {odds_result['odds_b']:.2f} ({odds_result['bookmaker']})")
                                    odds_a_num = odds_result['odds_a']
                                    odds_b_num = odds_result['odds_b']
                                    bookmaker = odds_result['bookmaker']
                            except Exception as e:
                                print(f"   ⚠️ Ошибка запроса коэффициентов: {e}")

                        matchup = {"bookmaker": bookmaker, "odds_a": odds_a_num, "odds_b": odds_b_num}

                        fd = FightData(
                            a=fa, b=fb, date=ev_date, wc="Auto", rounds=rounds, location=location,
                            odds_a=odds_a_num, matchup_odds=matchup
                        )
                        res = None

                        print(f"🥊 Контекст: {event_name} | {rounds} раунд(ов)")
                        print("   ⚙️ Расчет вероятностей (Math Engine)...")
                        pred = engine.predict(fd)
                        acc_win, acc_rnd, acc_mth = load_accuracy_metrics(engine)

                        print("\n" + strict_out(pred, res, fd, mode, matchup, f1_clean, f2_clean, acc_win, acc_rnd, acc_mth))
                        increment_prediction_count(config, current_hwid)

                        print("\n" + "=" * 70)
                        print("✅ Операция завершена. Ожидание следующей команды...")
                        print("=" * 70)
                        continue

                except Exception as e:
                    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
                    traceback.print_exc()
                    print("⚠️ Возврат в главное меню...")
                    continue

            except KeyboardInterrupt:
                print("👋 Программа прервана пользователем.")
                sys.exit(0)

    except KeyboardInterrupt:
        print("👋 Программа прервана пользователем.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        traceback.print_exc()
        sys.exit(1)