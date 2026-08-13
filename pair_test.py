#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAIR TEST v1.1 | ПОПАРНОЕ ТЕСТИРОВАНИЕ ПРИЗНАКОВ
================================================================
ИСПРАВЛЕНИЯ v1.1:
1. ✅ ДОБАВЛЕН вызов DeepAIAnalyst.get_fighter_deep_stats() перед enrich_fighters_via_yandex()
2. ✅ Передача полученных stats в enrich_fighters (как в direct_test_101.py)
3. ✅ Передача recent_form для корректного расчёта stress/motivation/biorythm
4. ✅ Все остальные улучшения v1.0 сохранены
================================================================
"""
import os
import sys
import json
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Callable

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from math_engine import (
    MMAEngine, Fighter, FightData, Result, FinishType,
    VerificationStatus, AdvancedMathEngine
)
from deep_ai_analyst import DeepAIAnalyst
from parser_worker import ParserWorker
from exchange_protocol import ExchangeProtocol
from secure_neural_channel import SecureNeuralChannel

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================
FIGHTS_PER_TEST = 50
RESULTS_FILE = f"dataset/pair_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
MASTER_PASSWORD = None

# 10 пар признаков для тестирования
TEST_PAIRS = [
    {
        "name": "recent_wins + activity",
        "features": ["recent_wins_diff", "activity_diff"],
        "indices": [0, 7]
    },
    {
        "name": "fin_rate + sub_rate",
        "features": ["fin_rate_diff", "sub_rate_diff"],
        "indices": [1, 2]
    },
    {
        "name": "td_def + grap_def",
        "features": ["td_def_diff", "grap_def_diff"],
        "indices": [3, 4]
    },
    {
        "name": "age + exp",
        "features": ["age_diff", "exp_diff"],
        "indices": [5, 6]
    },
    {
        "name": "stress + motivation",
        "features": ["stress_diff", "motivation_diff"],
        "indices": [11, 12]
    },
    {
        "name": "biorythm + camp",
        "features": ["biorythm_diff", "camp_diff"],
        "indices": [13, 14]
    },
    {
        "name": "mystic + mystic_v2",
        "features": ["mystic_diff", "mystic_v2_diff"],
        "indices": [15, 20]
    },
    {
        "name": "wp_diff + log_odds",
        "features": ["wp_diff", "log_odds_ratio"],
        "indices": [10, 9]
    },
    {
        "name": "fin_x_td + sub_x_grap",
        "features": ["fin_x_td", "sub_x_grap"],
        "indices": [16, 17]
    },
    {
        "name": "rust_x_exp + stress_x_camp",
        "features": ["rust_x_exp", "stress_x_camp"],
        "indices": [18, 19]
    }
]

# ============================================================================
# ФУНКЦИЯ ЗАГРУЗКИ ПАР
# ============================================================================
def load_fight_pairs() -> List[Dict]:
    """Загружает пары бойцов из базы"""
    dataset_dir = "dataset"
    all_pairs = []

    part_files = sorted([f for f in os.listdir(dataset_dir) if f.startswith("real_dataset_part")])
    for part_file in part_files:
        filepath = os.path.join(dataset_dir, part_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                all_pairs.extend(json.load(f))
        except Exception as e:
            print(f"⚠️ Ошибка чтения {part_file}: {e}")

    main_file = os.path.join(dataset_dir, "RRRreal_dataset.json")
    if os.path.exists(main_file):
        try:
            with open(main_file, 'r', encoding='utf-8-sig') as f:
                all_pairs.extend(json.load(f))
        except Exception as e:
            print(f"⚠️ Ошибка чтения {main_file}: {e}")

    # Фильтрация по дате
    valid_pairs = []
    for pair in all_pairs:
        date_str = pair.get("date", "")
        if date_str >= "2022-08-01":
            valid_pairs.append(pair)

    print(f"✅ Отфильтровано: {len(valid_pairs)} боев с 2022-08-01")
    return valid_pairs


# ============================================================================
# ФУНКЦИЯ ОБОГАЩЕНИЯ (ИСПРАВЛЕННАЯ v1.1)
# ============================================================================
def enrich_fighters(fighter_a: str, fighter_b: str, fight_date: str):
    """
    ✅ v1.1: Обогащает бойцов через DeepSeek + YandexGPT
    КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: вызов DeepAIAnalyst.get_fighter_deep_stats() ПЕРЕД enrich_fighters_via_yandex()
    """
    try:
        # ✅ ШАГ 1: Получаем статистику от DeepSeek (как в direct_test_101.py)
        fa_stats = DeepAIAnalyst.get_fighter_deep_stats(fighter_a, fight_date)
        fb_stats = DeepAIAnalyst.get_fighter_deep_stats(fighter_b, fight_date)

        # ✅ ШАГ 2: Формируем контекст для YandexGPT (передаём recent_form!)
        fighter_a_stats = {
            "age": fa_stats.age, "wins": fa_stats.wins, "losses": fa_stats.losses,
            "country": fa_stats.flag, "dob": getattr(fa_stats, 'dob', None),
            "opponent_name": fighter_b, "opponent_record": f"{fb_stats.wins}-{fb_stats.losses}",
            "fight_context": "regular", "recent_form": getattr(fa_stats, 'form', [])
        }
        fighter_b_stats = {
            "age": fb_stats.age, "wins": fb_stats.wins, "losses": fb_stats.losses,
            "country": fb_stats.flag, "dob": getattr(fb_stats, 'dob', None),
            "opponent_name": fighter_a, "opponent_record": f"{fa_stats.wins}-{fa_stats.losses}",
            "fight_context": "regular", "recent_form": getattr(fb_stats, 'form', [])
        }

        # ✅ ШАГ 3: Вызов YandexGPT через ParserWorker
        protocol = ExchangeProtocol()
        worker = ParserWorker(master_password=MASTER_PASSWORD)

        req_a = protocol.create_request(
            request_type="enrich",
            data={"fighter_name": fighter_a, "fight_date": fight_date, "fighter_stats": fighter_a_stats},
            priority=3
        )
        req_b = protocol.create_request(
            request_type="enrich",
            data={"fighter_name": fighter_b, "fight_date": fight_date, "fighter_stats": fighter_b_stats},
            priority=3
        )

        worker.run_once()

        response_a = protocol.get_response(req_a, timeout=30)
        response_b = protocol.get_response(req_b, timeout=30)

        enrichment_a = response_a.get('data', {}) if response_a and response_a.get('status') == 'success' else {}
        enrichment_b = response_b.get('data', {}) if response_b and response_b.get('status') == 'success' else {}

        protocol.cleanup_request(req_a)
        protocol.cleanup_request(req_b)

        # ✅ ШАГ 4: Применяем обогащение к stats от DeepSeek
        if enrichment_a:
            fa_stats.stress_factor = enrichment_a.get('stress_factor', fa_stats.stress_factor)
            fa_stats.motivation_index = enrichment_a.get('motivation_index', fa_stats.motivation_index)
            fa_stats.biorythm_score = enrichment_a.get('biorythm_score', fa_stats.biorythm_score)
            fa_stats.camp_quality = enrichment_a.get('camp_quality', fa_stats.camp_quality)
            fa_stats.mystic_factor = enrichment_a.get('mystic_factor', fa_stats.mystic_factor)
            fa_stats.mystic_v2 = enrichment_a.get('mystic_v2', getattr(fa_stats, 'mystic_v2', 0.5))

        if enrichment_b:
            fb_stats.stress_factor = enrichment_b.get('stress_factor', fb_stats.stress_factor)
            fb_stats.motivation_index = enrichment_b.get('motivation_index', fb_stats.motivation_index)
            fb_stats.biorythm_score = enrichment_b.get('biorythm_score', fb_stats.biorythm_score)
            fb_stats.camp_quality = enrichment_b.get('camp_quality', fb_stats.camp_quality)
            fb_stats.mystic_factor = enrichment_b.get('mystic_factor', fb_stats.mystic_factor)
            fb_stats.mystic_v2 = enrichment_b.get('mystic_v2', getattr(fb_stats, 'mystic_v2', 0.5))

        return fa_stats, fb_stats
    except Exception as e:
        print(f"   ⚠️ Ошибка обогащения: {e}")
        return None, None


# ============================================================================
# MONKEY-PATCH: изоляция признаков
# ============================================================================
def create_isolated_engine(active_indices: List[int], base_engine: MMAEngine) -> MMAEngine:
    """
    Создаёт MMAEngine с monkey-patch метода _extract_features.
    Все признаки, кроме active_indices, обнуляются.
    """
    isolated_engine = MMAEngine()
    # Копируем веса из базового движка
    isolated_engine.model.weights = base_engine.model.weights.copy()
    isolated_engine.model.bias = base_engine.model.bias
    isolated_engine.model.feature_means = base_engine.model.feature_means.copy()
    isolated_engine.model.feature_stds = base_engine.model.feature_stds.copy()

    # Сохраняем оригинальный метод
    original_extract = isolated_engine.model._extract_features

    def isolated_extract(a, b, odds_a, odds_b):
        # Вызываем оригинальный метод
        features, names = original_extract(a, b, odds_a, odds_b)
        # Обнуляем неактивные признаки
        isolated_features = [
            features[i] if i in active_indices else 0.0
            for i in range(len(features))
        ]
        return isolated_features, names

    # Monkey-patch
    isolated_engine.model._extract_features = isolated_extract

    return isolated_engine


# ============================================================================
# ТЕСТ ОДНОЙ ПАРЫ
# ============================================================================
def run_pair_test(pair_config: Dict, pairs: List[Dict], base_engine: MMAEngine) -> Dict:
    """Запускает тест одной пары признаков на 50 боях"""
    pair_name = pair_config["name"]
    active_indices = pair_config["indices"]
    features = pair_config["features"]

    print(f"\n{'='*70}")
    print(f"🧪 ТЕСТ: {pair_name}")
    print(f"📋 Признаки: {', '.join(features)}")
    print(f"📊 Индексы: {active_indices}")
    print(f"{'='*70}")

    # Создаём изолированный движок
    isolated_engine = create_isolated_engine(active_indices, base_engine)

    # Выбираем 50 случайных боёв
    test_pairs = random.sample(pairs, min(FIGHTS_PER_TEST, len(pairs)))

    correct = 0
    total = 0
    failed = 0
    battles = []

    for idx, pair in enumerate(test_pairs, 1):
        fighter_a = pair.get("fighter_a", "")
        fighter_b = pair.get("fighter_b", "")
        fight_date = pair.get("date", "")
        winner = pair.get("winner", "")

        print(f"  [{idx}/{len(test_pairs)}] {fighter_a} vs {fighter_b}", end="")

        try:
            # ✅ v1.1: Вызов обогащения с DeepSeek + YandexGPT
            fa_stats, fb_stats = enrich_fighters(fighter_a, fighter_b, fight_date)

            if fa_stats is None or fb_stats is None:
                print(" ❌ (обогащение)")
                failed += 1
                continue

            fd = FightData(
                a=fa_stats, b=fb_stats,
                date=datetime.strptime(fight_date, "%Y-%m-%d"),
                wc="Auto", rounds=3, location="UFC",
                odds_a=1.85, matchup_odds={"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85}
            )

            prediction = isolated_engine.predict(fd)
            is_correct = (prediction.winner == winner)

            if is_correct:
                correct += 1
                print(f" ✅ ({prediction.prob*100:.0f}%)")
            else:
                print(f" ❌ ({prediction.prob*100:.0f}%)")

            total += 1
            battles.append({
                "fighter_a": fighter_a,
                "fighter_b": fighter_b,
                "winner": winner,
                "predicted": prediction.winner,
                "confidence": prediction.prob,
                "correct": is_correct
            })

        except Exception as e:
            print(f" ⚠️ ({e})")
            failed += 1

    accuracy = (correct / total * 100) if total > 0 else 0.0

    print(f"\n📊 РЕЗУЛЬТАТ: {correct}/{total} ({accuracy:.1f}%)")

    return {
        "pair_name": pair_name,
        "features": features,
        "indices": active_indices,
        "correct": correct,
        "total": total,
        "failed": failed,
        "accuracy": accuracy,
        "battles": battles
    }


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================
def main():
    global MASTER_PASSWORD

    print("="*70)
    print("🧪 PAIR TEST v1.1 | ПОПАРНОЕ ТЕСТИРОВАНИЕ ПРИЗНАКОВ")
    print("="*70)

    # Запрос пароля
    print("🔐 Мастер-пароль: ", end="", flush=True)
    MASTER_PASSWORD = input().strip()

    if not MASTER_PASSWORD:
        print("❌ Пароль не введён")
        return

    # Инициализация SecureNeuralChannel
    if not SecureNeuralChannel.init(MASTER_PASSWORD):
        print("❌ Неверный пароль")
        return

    print("⏳ Проверка ИИ...")
    if SecureNeuralChannel.query('{"status":"ok"}', "Тест", use_cache=False):
        print("✅ ИИ работает")

    # Загрузка пар
    print("\n📊 Загрузка пар...")
    pairs = load_fight_pairs()

    if len(pairs) < FIGHTS_PER_TEST:
        print(f"❌ Недостаточно пар ({len(pairs)} < {FIGHTS_PER_TEST})")
        return

    # Создаём базовый движок
    base_engine = MMAEngine()
    print(f"✅ Базовый движок создан (весов: {len(base_engine.model.weights)})")

    # Запуск тестов
    results = []
    start_time = time.time()

    for pair_config in TEST_PAIRS:
        result = run_pair_test(pair_config, pairs, base_engine)
        results.append(result)
        time.sleep(1)  # Пауза между тестами

    # Итоговый анализ
    duration = time.time() - start_time

    print("\n" + "="*70)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("="*70)
    print(f"{'Пара признаков':<35} {'Точность':>10} {'Верных':>8} {'Всего':>8}")
    print("-"*70)

    # Сортировка по точности
    sorted_results = sorted(results, key=lambda x: x["accuracy"], reverse=True)

    for r in sorted_results:
        print(f"{r['pair_name']:<35} {r['accuracy']:>9.1f}% {r['correct']:>8} {r['total']:>8}")

    print("="*70)

    # Топ-3 лучших пар
    print("\n🏆 ТОП-3 ЛУЧШИХ ПАР:")
    for i, r in enumerate(sorted_results[:3], 1):
        print(f"   {i}. {r['pair_name']} → {r['accuracy']:.1f}%")

    # Топ-3 худших пар
    print("\n💀 ТОП-3 ХУДШИХ ПАР:")
    for i, r in enumerate(sorted_results[-3:], 1):
        print(f"   {i}. {r['pair_name']} → {r['accuracy']:.1f}%")

    print("="*70)
    print(f"⏱️  Длительность: {duration:.1f} сек ({duration/60:.1f} мин)")

    # Сохранение результатов
    try:
        os.makedirs("dataset", exist_ok=True)
        report = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration,
            "fights_per_test": FIGHTS_PER_TEST,
            "total_tests": len(results),
            "results": sorted_results
        }
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n📄 Результаты сохранены: {RESULTS_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")

    print("\n✅ ТЕСТ ЗАВЕРШЁН")


if __name__ == "__main__":
    main()