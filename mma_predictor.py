#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MMA PREDICTION v47.0 | РЕЖИМ ПРОГНОЗ + НОВОЕ ПОДМЕНЮ ОБУЧЕНИЯ
================================================================
ИЗМЕНЕНИЯ v47.0:
1. ✅ НОВОЕ подменю режима ОБУЧЕНИЕ (2a, 2b, 0)
2. ✅ Подрежим 2a: Запуск обучения на датасете (direct_test_101.py)
3. ✅ Подрежим 2b: Проверка работы модели (бэктест по дате)
4. ✅ Анализ признаков, упершихся в лимит после обучения
5. ✅ Удален старый блок ручного ввода
6. ✅ Сохранены все улучшения v46.1
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
from espn_parser import ESPNParser
from cryptography.fernet import Fernet

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
    from deep_ai_analyst import DeepAIAnalyst
    from fighters_ids_manager import (
        ensure_both_fighters_exist,
        add_ids_to_fight_in_memory,
        load_fighters_ids,
        get_canonical_name,
        names_match_by_id
    )
    from odds_api_client import OddsAPIClient
    from mystic_calculator import calculate_mystic_factor
    HAS_ALL_IMPORTS = True
    HAS_ODDS_API = True
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    traceback.print_exc()
    HAS_ALL_IMPORTS = False
    HAS_ODDS_API = False
    sys.exit(1)

# ============================================================================
# КОНСТАНТЫ
# ============================================================================
DATASET_DIR = "dataset"
REAL_DATASET_FILE = os.path.join(DATASET_DIR, "real_dataset.json")
FIGHTERS_IDS_FILE = os.path.join(DATASET_DIR, "fighters_ids.json")
MAX_DATASET_SIZE_MB = 2.2
REQUEST_DELAY = 2.5

# ============================================================================
# ✅ v46.1: ФУНКЦИЯ ОЧИСТКИ ИМЁН ОТ РЕЙТИНГОВ
# ============================================================================
def clean_name_for_api(name: str) -> str:
    """
    ✅ v46.1: Удаляет рейтинги типа (#10), (#2), (C) из имени.
    Пример: "Марлон Вера (#10)" → "Марлон Вера"
    """
    if not name:
        return ""
    cleaned = re.sub(r'\s*\([^)]*\)', '', name)
    return cleaned.strip()

# ============================================================================
# ЭТАП 1: ОЧИСТКА ВВОДА
# ============================================================================
def clear_input_buffer():
    try:
        if not WIN32:
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        else:
            while msvcrt.kbhit():
                msvcrt.getwch()
    except Exception:
        pass

def sanitize_fighter_name(raw_name: str) -> str:
    if not raw_name:
        return ""
    cleaned = re.sub(r'\s*\([^)]*\)', '', raw_name)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def clean_user_input(raw_input: str) -> str:
    if not raw_input:
        return ""
    cleaned = ''.join(c for c in raw_input if ord(c) > 31 and c not in '\u200b\u200c\u200d\u00a0\ufeff\u200e\u200f\u202a-\u202e')
    cleaned = cleaned.replace('—', '-').replace('–', '-').replace('−', '-')
    cleaned = cleaned.replace('\t', ' ').replace('\r', ' ')
    import re as re_module
    for _ in range(10):
        new_cleaned = re_module.sub(r'([а-яёa-zA-Z])\s+([а-яёa-zA-Z])(?=\s|[^\wа-яёa-zA-Z]|$)', r'\1\2', cleaned, flags=re_module.IGNORECASE)
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned
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
# ЭТАП 3: НОРМАЛИЗАЦИЯ ИМЁН
# ============================================================================
TRANS_TABLE = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}

def _transliterate(text: str) -> str:
    if not text:
        return ""
    return "".join(TRANS_TABLE.get(ch, ch) for ch in text.lower())

def normalize_fighter_name(name: str) -> str:
    if not name:
        return ""
    latin = _transliterate(name)
    latin = re.sub(r'\s*\([^)]*\)', '', latin)
    latin = re.sub(r',.*$', '', latin)
    return re.sub(r'[^a-z0-9]', '', latin)

def normalize_winner_name(fact_winner: str, f1_clean: str, f2_clean: str, parser=None) -> str:
    if not fact_winner:
        return fact_winner
    if len(f1_clean) > 40 or f1_clean.count(' ') > 5:
        f1_clean = None
    if len(f2_clean) > 40 or f2_clean.count(' ') > 5:
        f2_clean = None
    if f1_clean and names_match(fact_winner, f1_clean):
        return f1_clean
    if f2_clean and names_match(fact_winner, f2_clean):
        return f2_clean
    from fighters_ids_manager import get_canonical_name
    canonical = get_canonical_name(fact_winner)
    if canonical and canonical != fact_winner:
        return canonical
    return fact_winner

# ============================================================================
# ЭТАП 4: ИИ-КОРРЕКЦИЯ ИМЁН (используется ТОЛЬКО в режиме ОБУЧЕНИЕ)
# ============================================================================
def canonicalize_names_with_db(raw_input: str, known_fighters: List[str]) -> Optional[Dict[str, str]]:
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

    files_to_read = sorted(glob_module.glob(os.path.join(DATASET_DIR, "real_dataset_part*.json")))
    if os.path.exists(REAL_DATASET_FILE):
        files_to_read.append(REAL_DATASET_FILE)

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

    if len(user_f1) > 40 or user_f1.count(' ') > 5:
        print(f"   ⚠️ Первое имя слишком длинное ({len(user_f1)} символов).")
        return None
    if len(user_f2) > 40 or user_f2.count(' ') > 5:
        print(f"   ⚠️ Второе имя слишком длинное ({len(user_f2)} символов).")
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

    print(f"   🔍 Проверка наличия в кэше:")
    print(f"      • '{user_f1}' → лучший матч: '{scored_f1[0][0]}' (сходство: {best_f1_score:.2f})")
    print(f"      • '{user_f2}' → лучший матч: '{scored_f2[0][0]}' (сходство: {best_f2_score:.2f})")

    if best_f1_score < 0.70 or best_f2_score < 0.07:
        print(f"   ⚠️ Точное совпадение не найдено.")
        return {"f1": user_f1, "f2": user_f2}

    top_similar = [f[0] for f in scored_f1[:50]] + [f[0] for f in scored_f2[:50]]
    top_similar = list(set(top_similar))[:100]

    fighters_list_str = ", ".join(top_similar)

    prompt = f"""Ты эксперт по ММА. Пользователь ввел строку: "{raw_input}".
Вот официальный список имен бойцов: [{fighters_list_str}].
Найди РОВНО ДВА имени. Верни СТРОГО JSON без markdown:
{{"f1": "Точное имя", "f2": "Точное имя"}}"""

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
                data = {}

        f1 = data.get("f1")
        f2 = data.get("f2")

        if f1 and f2 and str(f1).lower() != "null" and str(f2).lower() != "null":
            f1_clean = str(f1).strip()
            f2_clean = str(f2).strip()

            fighters_lower = {f.lower(): f for f in top_similar}

            if f1_clean.lower() in fighters_lower and f2_clean.lower() in fighters_lower:
                print(f"   ✅ ИИ вернул валидные имена: '{f1_clean}' vs '{f2_clean}'")
                return {
                    "f1": fighters_lower[f1_clean.lower()],
                    "f2": fighters_lower[f2_clean.lower()]
                }

        return {"f1": user_f1, "f2": user_f2}

    except Exception as e:
        print(f"   ⚠️ Ошибка ИИ: {e}")
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
               matchup: dict, a: str, b: str, raw_prob: float,
               acc_win: float = 0.0, acc_rnd: float = 0.0, acc_mth: float = 0.0) -> str:
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
    else:
        res_w_canonical = 'Ожидание'
        res_r = 'Ожидание'
        res_m = 'Ожидание'
        pred_rnd_txt = f"{pred_rnd} (предпол.)"
        pred_mth_txt = f"{pred.method.value} (предпол.)"
        acc_win_display = 0.0

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
        f"|{'-'*10}|{'-'*19}|{'-'*17}|{'-'*8}|",
        f"| Победитель | {win_txt:<19} | {res_w_canonical:<17} | {acc_win_display:>5.1f}% |",
        f"| Раунд      | {pred_rnd_txt:<19} | {res_r:<17} | — |",
        f"| Способ     | {pred_mth_txt:<19} | {res_m:<17} | — |",
        f"| Коэфф. {a_canonical:<10} | 1/{pred.prob:.2f} (Модель) | {odds_a_str} ({book_str}) |",
        f"| Коэфф. {b_canonical:<10} | 1/{1 - pred.prob:.2f} (Модель) | {odds_b_str} ({book_str}) |",
        ]

    if high_dispersion_flag:
        lines.append("⚠️ СЦЕНАРНОЕ ДЕРЕВО (высокая неопределённость):")
        lines.append(f"   • Сценарий A (60%): {win_txt} побеждает решением")
        lines.append(f"   • Сценарий B (25%): {b_canonical if win_txt == a_canonical else a_canonical} побеждает нокаутом")
        lines.append(f"   • Сценарий C (15%): Ничья / нестандартный исход")

    # =========================================================================
    # ✅ v46.1: БИНАРНЫЙ ВЕРДИКТ С ЗАЩИТОЙ ОТ ДЕФОЛТНЫХ КОЭФФИЦИЕНТОВ
    # =========================================================================
    model_prob_a = raw_prob
    model_prob_b = 1.0 - raw_prob

    model_favored = a if model_prob_a >= 0.50 else b
    model_favored_prob = model_prob_a if model_favored == a else model_prob_b

    bk_favored = a if odds_a_val <= odds_b_val else b
    bk_favored_odds = odds_a_val if bk_favored == a else odds_b_val

    MIN_SAFE_ODDS = 1.10

    is_default_odds = (abs(odds_a_val - 1.85) < 0.01 and abs(odds_b_val - 1.85) < 0.01)

    if is_default_odds:
        verdict = "⚠️ РЕШЕНИЕ: НЕТ ДАННЫХ БК"
        reason = f"💡 Коэффициенты не найдены в API. Невозможно определить двойное подтверждение. Пропускаем."
    elif model_favored == bk_favored:
        if bk_favored_odds < MIN_SAFE_ODDS:
            verdict = "⚠️ РЕШЕНИЕ: СЛИШКОМ МАЛО"
            reason = f"💡 Модель и БК согласны на {model_favored}, но коэффициент {bk_favored_odds} слишком низкий."
        else:
            verdict = "✅ РЕШЕНИЕ: РЕКОМЕНДУЮ"
            reason = f"💡 Двойное подтверждение: Модель и БК сходятся на фаворите ({model_favored})."
    else:
        verdict = "❌ РЕШЕНИЕ: ПРОПУСКАЕМ"
        reason = f"💡 Расхождение мнений: Модель за {model_favored}, БК за {bk_favored}."

    lines.extend([
        "=" * 78,
        f"📊 Мнение модели (сырое): {model_favored} {model_favored_prob*100:.0f}% | Коэф БК: {bk_favored_odds}",
        verdict,
        reason,
        "=" * 78
    ])

    return "\n".join(lines)

def print_all_features(engine: MMAEngine, fighter_a: Fighter, fighter_b: Fighter,
                       odds_a: float, odds_b: float, fighter_a_name: str) -> float:
    """Выводит ВСЕ признаки и ВОЗВРАЩАЕТ сырую вероятность."""
    features, feature_names = engine.model._extract_features(fighter_a, fighter_b, odds_a, odds_b)
    raw_prob = engine.model.predict_proba(features)

    print(f"   📊 Сырая вероятность победы {fighter_a_name}: {raw_prob:.3f}")

    num_features = min(len(features), len(engine.model.weights))
    contributions = []
    for i in range(num_features):
        name = feature_names[i] if i < len(feature_names) else f"feature_{i}"
        val = engine.model.weights[i] * features[i]
        if abs(val) > 0.0001:
            contributions.append((name, val, features[i]))

    contributions.sort(key=lambda x: abs(x[1]), reverse=True)

    print(f"   📊 Всего значимых признаков: {len(contributions)} из {num_features}")
    print("   📊 Признаки (вклад → значение признака):")
    for name, val, raw_val in contributions:
        print(f"      {name}: {val:+.4f} (raw={raw_val:.4f})")

    return raw_prob

def load_accuracy_metrics(engine: MMAEngine) -> Tuple[float, float, float]:
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
                dataset = []
                part_files = sorted(glob_module.glob(os.path.join(DATASET_DIR, "real_dataset_part*.json")))
                for part_file in part_files:
                    try:
                        with open(part_file, "r", encoding="utf-8") as f:
                            dataset.extend(json.load(f))
                    except Exception as e:
                        print(f"   ⚠️ Ошибка чтения {part_file}: {e}")

                if len(dataset) < 5:
                    print("⚠️ Недостаточно данных для проверки")
                else:
                    acc_win, acc_rnd, acc_mth = engine.get_recent_accuracies(dataset)
                    print(f"📊 ТОЧНОСТЬ (все бои): Победитель: {acc_win:.1f}%")
                    print(f"📊 Лучшие веса: {engine.best_accuracy * 100:.1f}%")

                    acc_win_ratio = acc_win / 100.0

                    if acc_win_ratio < engine.best_accuracy - 0.03:
                        print(f"⚠️ Деградация. Авто-возврат к best выполнится при следующем старте.")
                    else:
                        print("✅ Модель в норме.")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                traceback.print_exc()

        # elif subcommand == "3b":
        #     print("🔄 Откат к лучшим весам...")
        #     engine.rollback_to_best()
        #
        # elif subcommand == "3c":
        #     print("🛡️ Откат к эталону...")
        #     confirm = input("   ⚠️ Это сбросит все накопленные знания! Продолжить? (y/n): ").strip().lower()
        #     if confirm == 'y':
        #         engine.rollback_to_baseline()
        #     else:
        #         print("   ❌ Отменено")

        elif subcommand == "3d":
            print(f"📊 СТАТУС ВЕСОВ:")

            # print(f"   🛡️ Эталон: {engine.baseline_accuracy * 100:.1f}%")
            print(f"   🏆 Лучшие веса (глоб.макс): {engine.best_accuracy * 100:.1f}%")

            print(f"   ⚙️ Стабильность: {engine.stability_score:.1f}")
            print(f"   📦 Буфер: {len(engine.pending_fights)}/{engine.BATCH_TRAIN_SIZE}")

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
# ЭТАП 7: ПОЛУЧЕНИЕ ДАННЫХ БОЙЦА (ОБОГАЩЕНИЕ)
# ============================================================================
def get_fighter_data(fighter_name: str, fight_date: str,
                     opponent_name: str = None,
                     opponent_record: str = None,
                     fight_context: str = "regular",
                     recent_form: List[str] = None,
                     weight_class: str = None,
                     fighter_dob: str = None) -> Fighter:
    print(f"      🤖 Запрос полных данных для: {fighter_name}")

    data = DeepAIAnalyst.enrich_fighter(
        fighter_name=fighter_name,
        fight_date=fight_date,
        opponent_name=opponent_name,
        opponent_record=opponent_record,
        fight_context=fight_context,
        recent_form=recent_form or [],
        weight_class=weight_class
    )

    if not data:
        print(f"      ⚠️ Нет данных для {fighter_name}, используем дефолты")
        data = {}

    mystic_result = calculate_mystic_factor(fighter_dob, fight_date)
    mystic_factor = mystic_result.get('mystic_factor', 0.5)

    camp_name = data.get('camp_name', data.get('camp', 'Independent'))
    wins = data.get('wins', 0)
    losses = data.get('losses', 0)
    exp = data.get('exp', wins + losses)

    fighter = Fighter(
        name=fighter_name,
        age=data.get('age', 30),
        wins=wins,
        losses=losses,
        recent_wins=data.get('recent_wins', 0),
        form=recent_form or [],
        fin_rate=data.get('fin_rate', 0.5),
        sub_rate=data.get('sub_rate', 0.0),
        td_def=data.get('td_def', 0.5),
        grap_def=data.get('grap_def', 0.5),
        months_off=data.get('months_off', 0),
        fights_12m=data.get('fights_12m', 0),
        exp=exp,
        reach_cm=data.get('reach_cm', 180),
        height_cm=data.get('height_cm', 175),
        stress_factor=data.get('stress_factor', 0.5),
        motivation_index=data.get('motivation_index', 0.5),
        biorythm_score=data.get('biorythm_score', 0.5),
        camp_quality=data.get('camp_quality', 0.5),
        camp_name=camp_name,
        mystic_factor=mystic_factor,
        mystic_v2=data.get('mystic_v2', 0.62)
    )

    print(f"      📥 {fighter_name}: {fighter.wins}-{fighter.losses}, "
          f"reach={fighter.reach_cm}, stress={fighter.stress_factor:.2f}, "
          f"mystic={fighter.mystic_factor:.2f}, mystic_v2={fighter.mystic_v2:.2f}, "
          f"camp={camp_name}")

    time.sleep(REQUEST_DELAY)
    return fighter

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
# ✅ v47.0: ПОДРЕЖИМЫ РЕЖИМА ОБУЧЕНИЕ
# ============================================================================
def run_dataset_training():
    """
    Подрежим 2a: Запуск обучения на датасете (вызов direct_test_101.py)
    """
    print("\n" + "=" * 70)
    print("🚀 ЗАПУСК ОБУЧЕНИЯ НА ДАТАСЕТЕ (100 боёв)")
    print("=" * 70)

    import subprocess

    # Сохраняем снапшот весов ДО запуска
    weights_before = None
    weights_file = "mma_weights_v21.json"
    if os.path.exists(weights_file):
        try:
            with open(weights_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                weights_before = data.get("weights", [])
        except Exception:
            pass

    try:
        result = subprocess.run(
            [sys.executable, "direct_test_101.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        if result.returncode == 0:
            print("\n✅ Обучение завершено успешно")

            # Сравниваем веса ПОСЛЕ обучения
            if weights_before and os.path.exists(weights_file):
                try:
                    with open(weights_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        weights_after = data.get("weights", [])

                    # Ищем признаки, которые уперлись в лимит
                    hit_limits = _check_weight_limits(weights_after)

                    if hit_limits:
                        print("\n" + "=" * 70)
                        print("🔒 ПРИЗНАКИ, УПЕРШИЕСЯ В ЛИМИТ:")
                        for name in hit_limits:
                            print(f"   • {name}")
                        print("=" * 70)
                    else:
                        print("\n✅ Ни один признак не упёрся в лимит")

                except Exception as e:
                    print(f"⚠️ Не удалось сравнить веса: {e}")
        else:
            print(f"\n⚠️ Обучение завершено с кодом {result.returncode}")

    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

    input("\n[Нажмите Enter для возврата в меню...]")


def _check_weight_limits(weights: List[float]) -> List[str]:
    """
    Проверяет, какие признаки достигли своих лимитов.
    Возвращает список имён признаков (только имена, без значений).
    """
    feature_names = [
        "a_recent_wins", "a_fin_rate", "a_sub_rate", "a_td_def", "a_grap_def",
        "a_age", "a_exp", "a_fights_12m", "a_months_off", "a_wins", "a_losses",
        "a_stress_factor", "a_motivation_index", "a_biorythm_score", "a_camp_quality",
        "a_mystic_factor", "a_mystic_v2",
        "b_recent_wins", "b_fin_rate", "b_sub_rate", "b_td_def", "b_grap_def",
        "b_age", "b_exp", "b_fights_12m", "b_months_off", "b_wins", "b_losses",
        "b_stress_factor", "b_motivation_index", "b_biorythm_score", "b_camp_quality",
        "b_mystic_factor", "b_mystic_v2",
        "fin_x_td_A", "sub_x_grap_A", "rust_x_exp_A", "stress_x_camp_A",
        "a_reach_cm", "a_height_cm", "b_reach_cm", "b_height_cm",
        "a_camp_name_encoded", "b_camp_name_encoded",
        "a_children_factor", "b_children_factor"
    ]

    # Специфические лимиты из math_engine.py (v55.7)
    specific_limits = {
        17: 0.040,  # B_RECENT_WINS_MAX_ABS
        32: 0.030,  # B_MYSTIC_FACTOR_MAX_ABS
        10: 0.060,  # A_LOSSES_MAX_ABS
        25: 0.060,  # B_MONTHS_OFF_MAX_ABS
        27: 0.100,  # B_LOSSES_MAX_ABS
    }

    MAX_ABS_WEIGHT = 0.1
    hit_limits = []

    # Проверяем специфические лимиты
    for idx, limit in specific_limits.items():
        if idx < len(weights):
            if abs(weights[idx]) >= limit - 0.0001:
                if idx < len(feature_names):
                    hit_limits.append(feature_names[idx])

    # Проверяем общий лимит MAX_ABS_WEIGHT
    for idx, weight in enumerate(weights):
        if abs(weight) >= MAX_ABS_WEIGHT - 0.0001:
            if idx < len(feature_names) and feature_names[idx] not in hit_limits:
                hit_limits.append(feature_names[idx])

    return hit_limits


def run_backtest_session(engine: MMAEngine, known_fighters_training: List[str]):
    """
    Подрежим 2b: Проверка работы модели (бэктест по дате)
    ТОЛЬКО парсинг сайта. Никаких датасетов.
    """
    print("\n" + "=" * 70)
    print("🔍 ПРОВЕРКА РАБОТЫ МОДЕЛИ (БЭКТЕСТ ПО ДАТЕ)")
    print("=" * 70)

    # 1. Запрос даты с валидацией
    print("\n📅 Введите дату турнира (ДД.ММ.ГГГГ):")
    print("   ⚠️ Дата должна быть не позже, чем 30 дней назад")
    clear_input_buffer()
    date_input = input("> ").strip()

    try:
        target_date = datetime.strptime(date_input, "%d.%m.%Y")
        max_date = datetime.now() - timedelta(days=30)

        if target_date > max_date:
            print(f"❌ Дата должна быть не позже {max_date.strftime('%d.%m.%Y')}")
            input("\n[Нажмите Enter для продолжения...]")
            return
    except ValueError:
        print("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
        input("\n[Нажмите Enter для продолжения...]")
        return

    # 2. Парсим сайт для получения боёв на эту дату
    print(f"\n⏳ Загрузка боёв из ESPN API на {date_input}...")
    card_fights = espn.get_fights_by_date(date_input)

    if not card_fights:
        print(f"⚠️ Бои на {date_input} не найдены на сайте.")
        input("\n[Нажмите Enter для продолжения...]")
        return

    print(f"✅ Найдено боев: {len(card_fights)}")

    # 3. Цикл выбора боёв
    predicted_indices = set()
    session_stats = {"total": 0, "correct": 0, "incorrect": 0, "errors": []}

    while True:
        print("\n" + "=" * 70)
        print(f"📋 БОИ НА {date_input}")
        # ✅ v47.1: Название турнира и место проведения — из первого боя
        if card_fights:
            event_title = card_fights[0].get('event', '')
            if event_title and event_title != 'UFC':
                print(f"🏟️ {event_title}")
        print("\n" + "=" * 70)
        print(f"📋 БОИ НА {date_input}")
        # ✅ v47.1: Название турнира и место проведения — из первого боя
        if card_fights:
            event_title = card_fights[0].get('event', '')
            if event_title and event_title != 'UFC':
                print(f"🏟️ {event_title}")
        print("=" * 70)

        for idx, fight in enumerate(card_fights, start=1):
            status = "✅" if idx in predicted_indices else "  "
            f1 = fight.get('fighter_a', 'Неизвестно')
            f2 = fight.get('fighter_b', 'Неизвестно')
            winner = fight.get('winner', 'Неизвестно')
            method = fight.get('method', 'DEC')
            rnd = fight.get('round', 3)
            # ✅ v47.1: время НЕ выводим
            print(f"[{status}] {idx:>2}. {f1} vs {f2}")


        print("-" * 70)
        print("Введите номер боя для проверки (или 0 для выхода):")


        choice = input("> ").strip()
        if not choice:
            continue          # пустой/остаточный Enter — тихо перерисовать кард

        if choice == '0':
            # Показываем статистику сессии
            print("\n" + "=" * 70)
            print("📊 СТАТИСТИКА СЕССИИ")
            print("=" * 70)
            print(f"   Всего проверено: {session_stats['total']}")
            print(f"   ✅ Верно: {session_stats['correct']}")
            print(f"   ❌ Неверно: {session_stats['incorrect']}")

            if session_stats['total'] > 0:
                accuracy = (session_stats['correct'] / session_stats['total']) * 100
                print(f"   🎯 Точность: {accuracy:.1f}%")

            if session_stats['errors']:
                print(f"\n   📋 Ошибки модели:")
                for err in session_stats['errors'][:5]:
                    print(f"      • {err['f1']} vs {err['f2']}: прогноз {err['pred']}, факт {err['fact']}")

            print("=" * 70)
            input("\n[Нажмите Enter для возврата в меню...]")
            return

        try:
            fight_idx = int(choice) - 1
            if 0 <= fight_idx < len(card_fights):
                if (fight_idx + 1) in predicted_indices:
                    print("⚠️ Этот бой уже был проверен.")
                    clear_input_buffer()
                    input("\n[Нажмите Enter для продолжения...]")
                    continue

                fight = card_fights[fight_idx]
                f1_clean = fight['fighter_a']
                f2_clean = fight['fighter_b']
                fact_winner = fight['winner']
                fact_method = fight.get('method', 'DEC')
                fact_round = fight.get('round', 3)
                fight_date = fight['date']

                print(f"\n🥊 Проверка: {f1_clean} vs {f2_clean}")
                #print(f"   Факт: {fact_winner} ({fact_method}, R{fact_round})")

                # ✅ КРИТИЧНО: Дата обогащения = дата боя - 1 день
                target_date_str = (fight_date - timedelta(days=1)).strftime("%Y-%m-%d")

                # Обогащение данных
                print(f"\n🧠 Сбор данных бойцов на {target_date_str}...")
                fa = get_fighter_data(
                    fighter_name=f1_clean,
                    fight_date=target_date_str,
                    opponent_name=f2_clean
                )
                fb = get_fighter_data(
                    fighter_name=f2_clean,
                    fight_date=target_date_str,
                    opponent_name=f1_clean
                )

                if not fa or not fb:
                    print("❌ Ошибка сбора данных. Пропускаем бой.")
                    clear_input_buffer()
                    input("\n[Нажмите Enter для продолжения...]")
                    continue

                # Прогноз БЕЗ коэффициентов
                print("\n⚙️ Расчет вероятностей (Math Engine, БЕЗ коэффициентов)...")
                fd = FightData(
                    a=fa, b=fb,
                    date=fight_date,
                    wc="Auto",
                    rounds=fact_round,
                    location=fight.get('event', 'UFC'),
                    odds_a=1.85,
                    matchup_odds={"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85}
                )

                pred = engine.predict(fd)

                # ✅ Нормализация имени победителя
                fact_winner_normalized = normalize_winner_name(fact_winner, f1_clean, f2_clean)
                if fact_winner_normalized != fact_winner:
                    print(f"   🔄 Имя победителя нормализовано: '{fact_winner}' → '{fact_winner_normalized}'")

                # Сравнение с фактом
                is_correct = names_match(pred.winner, fact_winner_normalized)

                print("\n" + "=" * 78)
                print(f"📊 РЕЗУЛЬТАТ ПРОВЕРКИ")
                print("=" * 78)
                print(f"   Прогноз модели: {pred.winner} ({pred.prob*100:.0f}%)")
                print(f"   🔓 Факт (после расчёта): {fact_winner_normalized} ({fact_method}, R{fact_round})")
                #print(f"   Реальный факт:  {fact_winner_normalized}")

                if is_correct:
                    print(f"   ✅ ВЕРНО!")
                    session_stats['correct'] += 1
                else:
                    print(f"   ❌ НЕВЕРНО!")
                    session_stats['incorrect'] += 1
                    session_stats['errors'].append({
                        'f1': f1_clean,
                        'f2': f2_clean,
                        'pred': pred.winner,
                        'fact': fact_winner_normalized
                    })

                session_stats['total'] += 1
                print("=" * 78)

                # Добавление в буфер обучения
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
                    rnd=fact_round,
                    method=meth_map.get(fact_method, FinishType.DECISION_UNANIMOUS)
                )
                print("\n🔄 Добавление в буфер обучения...")
                train_result = engine.train_on_new_fight(fd, res, f1_clean, f2_clean)

                # ✅ v47.2: НЕМЕДЛЕННО дописываем бой в part-файл.
                # Факт реальный (ESPN) — не должен теряться при выходе.
                # Буфер остаётся ТОЛЬКО для обучения (process_batch сделает dedup по ключу).
                try:
                    fight_dict = engine._fight_to_dict(fd, res, f1_clean, f2_clean)
                    active_part = engine._get_active_part_file()
                    with open(active_part, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    key = f"{fight_dict['fighter_a']}_{fight_dict['fighter_b']}_{fight_dict['date']}"
                    if not any(
                            f"{d.get('fighter_a')}_{d.get('fighter_b')}_{d.get('date')}" == key
                            for d in existing
                    ):
                        existing.append(fight_dict)
                        with open(active_part, "w", encoding="utf-8") as f:
                            json.dump(existing, f, indent=2, ensure_ascii=False)
                        print(f"   💾 Бой сохранён в {os.path.basename(active_part)}")
                except Exception as e:
                    print(f"   ⚠️ Ошибка сохранения боя в датасет: {e}")
                # ✅ Детальная обработка статуса обучения
                if train_result:
                    status_val = train_result.get("status", "")
                    if status_val == "buffered":
                        print(f"   📦 {train_result.get('status_text')}")
                    elif status_val == "trained":
                        print(f"   ✅ {train_result.get('status_text')}")
                        print(f"   📊 {train_result.get('accuracy_str')}")
                        print("   💾 Веса и датасет сохранены.")
                    elif status_val == "rollback_best":
                        print(f"   ⚠️ Откат к лучшим весам: {train_result.get('accuracy', 0)*100:.1f}%")
                    elif status_val == "rollback_baseline":
                        print(f"   🔴 Откат к эталону: {train_result.get('accuracy', 0)*100:.1f}%")
                    elif status_val == "predict_only":
                        print("   ⏸️ Режим только прогноз")
                    elif status_val == "empty":
                        print("   ⚠️ Буфер пуст")

                # ✅ Добавление ID в файлы памяти
                fight_date_str = fd.date.strftime("%Y-%m-%d")
                id_a, id_b = ensure_both_fighters_exist(f1_clean, f2_clean, fight_date_str)
                if id_a and id_b:
                    print(f"   🔗 Добавление ID в файлы памяти...")
                    id_result = add_ids_to_fight_in_memory(f1_clean, f2_clean)
                    if id_result.get("updated_files"):
                        print(f"   ✅ ID добавлены в: {', '.join(id_result['updated_files'])}")

                # ✅ Обновление кэша бойцов
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

                predicted_indices.add(fight_idx + 1)
                clear_input_buffer()
                input("\n[Нажмите Enter для продолжения...]")
            else:
                print("❌ Неверный номер. Попробуйте снова.")
        except ValueError:
            print("❌ Введите число.")

# ============================================================================
# ЭТАП 9: ГЛАВНЫЙ ЦИКЛ (ЕДИНСТВЕННЫЙ!)
# ============================================================================
if __name__ == "__main__":
    try:
        print("=" * 70)
        print("🔵 MMA PREDICTION v47.0 | НОВОЕ ПОДМЕНЮ ОБУЧЕНИЯ")
        print("=" * 70)

        current_hwid = get_hwid()
        config = load_config(current_hwid)

        if not config.get("is_agreed"):
            print("\n" + "=" * 70)
            print("⚖️ ЮРИДИЧЕСКОЕ СОГЛАШЕНИЕ")
            print("1. Прогнозы носят исключительно информационный характер.")
            print("2. Они не являются финансовой рекомендацией.")
            print("3. Используя модель, вы принимаете ответственность за решения.")
            print("4. Ваш API-ключ будет зашифрован и привязан к HWID.")
            print("=" * 70)
            clear_input_buffer()
            agree = input("Введите 'Y' для принятия соглашения: ").strip().upper()
            if agree == 'Y':
                config["is_agreed"] = True
                save_config(config, current_hwid)
                print("✅ Соглашение принято.")
            else:
                print("❌ Доступ запрещен.")
                sys.exit(0)

        api_key, status = check_api_access(config)
        if status == "limit_reached":
            print("⚠️ Лимит бесплатных прогнозов исчерпан.")
            clear_input_buffer()
            new_key = input("🔑 Введите ваш API ключ (или Enter для выхода): ").strip()
            if new_key:
                config["api_key"] = new_key
                save_config(config, current_hwid)
                print("✅ Ключ сохранен.")
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

            try:
                from secure_keys import SecureKeys
                if not SecureKeys.init(pwd):
                    print("⚠️ SecureKeys не инициализирован.")
            except ImportError:
                print("⚠️ SecureKeys не найден.")

        except Exception as e:
            print(f"❌ Ошибка инициализации: {e}")
            sys.exit(1)

        print("⏳ Проверка ИИ...")
        try:
            if SecureNeuralChannel.query('Верни JSON: {"status":"ok"}', "Тест").get("status") == "ok":
                print("✅ ИИ работает.")
        except Exception:
            print("⚠️ ИИ не ответил, но продолжаем.")

        print("⚙️ Инициализация модулей...")
        engine = MMAEngine()
        print("🔄 Перекалибровка нормализатора...")
        engine.recalibrate_scaler()
        analyst = DeepAIAnalyst()
        espn = ESPNParser()

        print("   📥 Загрузка базы имён для ОБУЧЕНИЯ...")
        known_fighters_training = load_known_fighters_cache()
        if not known_fighters_training:
            print(f"   ✅ Загружено {len(set(known_fighters_training))} имён из кэша.")

        if not known_fighters_training:
            print("   ⚠️ База бойцов пуста! Загрузка из резервных источников...")
            backup_sources = [REAL_DATASET_FILE, FIGHTERS_IDS_FILE, "ufc_fighters.json"]
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

        # =========================================================================
        # ОСНОВНОЙ ЦИКЛ (ЕДИНСТВЕННЫЙ!)
        # =========================================================================
        while True:
            try:
                print(f"{'=' * 70}")
                print(f"📊 Режим: {mode}")
                print("Команды: 1 - Прогноз | 2 - Обучение | 3 - Калибровка | 0 - Выход")
                print("💡 Подсказка: введите дату (ДД.ММ.ГГГГ) для быстрого прогноза")
                print(f"{'=' * 70}")

                clear_input_buffer()
                raw_input_str = input("📥 Введите команду: ")
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
                    # ✅ v47.0: НЕТ continue! Программа идет дальше к подменю

                if user_in == "3":
                    print("\n" + "=" * 70)
                    print("📊 КАЛИБРОВКА И ЗАЩИТА МОДЕЛИ")
                    print("=" * 70)
                    print("   3a - Быстрая проверка точности")
                    print("   3d - Показать статус весов")
                    print("   0 - Назад")
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

                # =========================================================================
                # ✅ v46.1: АВТООПРЕДЕЛЕНИЕ ДАТЫ В ГЛАВНОМ МЕНЮ
                # =========================================================================
                preselected_date = None
                date_match = re.match(r'^(\d{1,2})[./](\d{1,2})[./](\d{4})$', user_in)
                if date_match:
                    preselected_date = f"{date_match.group(1).zfill(2)}.{date_match.group(2).zfill(2)}.{date_match.group(3)}"
                    mode = "ПРОГНОЗ"
                    print(f"✅ Автоматически выбран режим ПРОГНОЗ на дату {preselected_date}")

                # =================================================================
                # ✅ v47.0: РЕЖИМ: ОБУЧЕНИЕ (НОВОЕ ПОДМЕНЮ)
                # =================================================================
                if mode == "ОБУЧЕНИЕ":
                    print("\n" + "=" * 70)
                    print("📊 РЕЖИМ: ОБУЧЕНИЕ")
                    print("=" * 70)
                    print("   2a - Обучение на датасете (100 боёв, ~10 минут)")
                    print("   2b - Проверка работы модели (бэктест по дате)")
                    print("   0  - Назад в главное меню")
                    print("=" * 70)
                    clear_input_buffer()
                    sub_mode = input("Ваш выбор: ").strip()

                    if sub_mode == "0":
                        print("↩️ Возврат в главное меню")
                        mode = "ПРОГНОЗ"
                        continue

                    elif sub_mode == "2a":
                        run_dataset_training()
                        continue

                    elif sub_mode == "2b":
                        run_backtest_session(engine, known_fighters_training)
                        continue

                    else:
                        print("❌ Неверный выбор")
                        continue

                # =================================================================
                # РЕЖИМ: ПРОГНОЗ (КАРД ПО ДАТЕ + ВСЕ 6 ИСПРАВЛЕНИЙ)
                # =================================================================
                else:  # mode == "ПРОГНОЗ"
                    # 1. Запрашиваем дату (или используем предвыбранную)
                    if preselected_date:
                        target_date = preselected_date
                        print(f"📅 Используется дата: {target_date}")
                    else:
                        print("\n📅 Введите дату турнира (ДД.ММ.ГГГГ) или 'сегодня':")
                        clear_input_buffer()
                        date_input = input("> ").strip().lower()

                        if date_input in ['сегодня', 'today', '']:
                            target_date = datetime.now().strftime("%d.%m.%Y")
                        else:
                            try:
                                datetime.strptime(date_input, "%d.%m.%Y")
                                target_date = date_input
                            except ValueError:
                                print("❌ Неверный формат. Используйте ДД.ММ.ГГГГ")
                                continue

                    print(f"\n⏳ Загрузка карда на {target_date}...")
                    card_fights = espn.get_fights_by_date(target_date)

                    if not card_fights:
                        print(f"⚠️ Бои на {target_date} не найдены в расписании.")
                        clear_input_buffer()
                        input("\n[Нажмите Enter для продолжения...]")
                        continue

                    print(f"✅ Найдено боев: {len(card_fights)}")

                    predicted_indices = set()

                    while True:
                        print("\n" + "=" * 70)
                        print(f"📋 КАРД ТУРНИРА: {target_date}")
                        print("=" * 70)

                        for idx, fight in enumerate(card_fights, start=1):
                            status = "✅" if idx in predicted_indices else "  "
                            # ✅ v46.1: Очищаем имена от рейтингов для вывода
                            f1 = clean_name_for_api(fight.get('fighter1', 'Неизвестно'))
                            f2 = clean_name_for_api(fight.get('fighter2', 'Неизвестно'))
                            rounds = fight.get('rounds', 3)
                            is_me = "ME" if fight.get('is_main_event') else ""

                            me_marker = f" [{is_me}]" if is_me else ""
                            print(f"[{status}] {idx:>2}. {f1} vs {f2} ({rounds} раунд.{me_marker})")

                        print("-" * 70)
                        print("Введите номер боя для прогноза (или 0 для смены даты):")

                        # ✅ v46.1: Очистка буфера перед вводом

                        choice = input("> ").strip()
                        if not choice:
                            continue

                        if choice == '0':
                            print("↩️ Возврат к выбору даты...")
                            break

                        try:
                            fight_idx = int(choice) - 1
                            if 0 <= fight_idx < len(card_fights):
                                if (fight_idx + 1) in predicted_indices:
                                    print("⚠️ Этот бой уже был спрогнозирован.")
                                    clear_input_buffer()
                                    input("\n[Нажмите Enter для продолжения...]")
                                    continue

                                fight = card_fights[fight_idx]
                                # ✅ v46.1: Очищаем имена от рейтингов ПЕРЕД использованием
                                f1_clean = clean_name_for_api(fight['fighter1'])
                                f2_clean = clean_name_for_api(fight['fighter2'])
                                rounds = int(fight.get('rounds', 3))
                                event_name = fight.get('event_name', 'UFC Event')
                                location = fight.get('location', 'UFC')
                                is_main_event = fight.get('is_main_event', False)

                                print(f"\n🥊 Выбран бой: {f1_clean} vs {f2_clean}")
                                print(f"🏟️ Турнир: {event_name} | {rounds} раунд(ов)")

                                print("\n🧠 Шаг 1: Сбор данных бойцов...")
                                fa = get_fighter_data(
                                    fighter_name=f1_clean,
                                    fight_date=target_date,
                                    opponent_name=f2_clean,
                                    fight_context="title" if is_main_event else "regular"
                                )
                                fb = get_fighter_data(
                                    fighter_name=f2_clean,
                                    fight_date=target_date,
                                    opponent_name=f1_clean,
                                    fight_context="title" if is_main_event else "regular"
                                )

                                if not fa or not fb:
                                    print("❌ Ошибка сбора данных. Пропускаем бой.")
                                    clear_input_buffer()
                                    input("\n[Нажмите Enter для продолжения...]")
                                    continue

                                print("\n💰 Шаг 2: Запрос коэффициентов...")
                                odds_a_num, odds_b_num, bookmaker = 1.85, 1.85, 'Нейтрально'

                                if HAS_ODDS_API:
                                    try:
                                        odds_client = OddsAPIClient()
                                        # ✅ v46.1: Передаём очищенные имена в API
                                        odds_result = odds_client.get_fight_odds(f1_clean, f2_clean)
                                        if odds_result:
                                            print(f"   ✅ РЕАЛЬНЫЕ коэффициенты: {odds_result['odds_a']:.2f} / "
                                                  f"{odds_result['odds_b']:.2f} ({odds_result['bookmaker']})")
                                            odds_a_num = odds_result['odds_a']
                                            odds_b_num = odds_result['odds_b']
                                            bookmaker = odds_result['bookmaker']
                                        else:
                                            print(f"   ⚠️ Бой не найден в API. Используются дефолтные коэффициенты.")
                                    except Exception as e:
                                        print(f"   ⚠️ Ошибка запроса коэффициентов: {e}")

                                matchup = {"bookmaker": bookmaker, "odds_a": odds_a_num, "odds_b": odds_b_num}

                                try:
                                    ev_date = datetime.strptime(target_date, "%d.%m.%Y")
                                except ValueError:
                                    ev_date = datetime.now()

                                fd = FightData(
                                    a=fa, b=fb, date=ev_date, wc="Auto", rounds=rounds,
                                    location=location, odds_a=odds_a_num, matchup_odds=matchup
                                )
                                res = None

                                print("\n⚙️ Шаг 3: Расчет вероятностей (Math Engine)...")
                                pred = engine.predict(fd)

                                odds_b_val_pred = fd.matchup_odds.get("odds_b", 1.85) if fd.matchup_odds else 1.85
                                raw_prob_pred = print_all_features(engine, fa, fb, fd.odds_a, odds_b_val_pred, f1_clean)

                                acc_win, acc_rnd, acc_mth = load_accuracy_metrics(engine)

                                print("\n" + strict_out(pred, res, fd, mode, matchup, f1_clean, f2_clean, raw_prob_pred, acc_win, acc_rnd, acc_mth))

                                predicted_indices.add(fight_idx + 1)
                                increment_prediction_count(config, current_hwid)

                                clear_input_buffer()
                                input("\n[Нажмите Enter, чтобы вернуться к карду...]")
                            else:
                                print("❌ Неверный номер. Попробуйте снова.")
                        except ValueError:
                            print("❌ Введите число.")
                    continue

            except KeyboardInterrupt:
                print("\n👋 Программа прервана пользователем.")
                sys.exit(0)

    except KeyboardInterrupt:
        print("\n👋 Программа прервана пользователем.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        traceback.print_exc()
        sys.exit(1)