#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIRECT TEST 101 v2.3 | Тестирование и обучение на 101 реальных боях
================================================================
ИЗМЕНЕНИЯ v2.3:
1. ✅ Добавлен параметр SEED для воспроизводимости (по умолчанию None)
2. ✅ Добавлен параметр SKIP_EXISTING для пропуска уже протестированных боёв
3. ✅ Добавлена функция загрузки/сохранения истории тестов
4. ✅ Добавлен параметр FORCE_NEW для принудительного выбора новых боёв
5. ✅ Добавлена поддержка аргументов командной строки
6. ✅ Добавлен параметр OFFSET для смещения выборки
================================================================
"""
import os
import sys
import json
import time
import random
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from math_engine import MMAEngine, Fighter, FightData, Result, FinishType, VerificationStatus
from deep_ai_analyst import DeepAIAnalyst
from parser_worker import ParserWorker
from exchange_protocol import ExchangeProtocol
from secure_neural_channel import SecureNeuralChannel
from mystic_calculator import calculate_mystic_factor

def clear_exchange_queues():
    import glob
    """Очищает папки запросов и ответов перед новым тестом"""
    requests_dir = "mma_exchange/requests"
    responses_dir = "mma_exchange/responses"

    for directory in [requests_dir, responses_dir]:
        if os.path.exists(directory):
            files = glob.glob(os.path.join(directory, "*"))
            for f in files:
                try:
                    os.remove(f)
                except Exception as e:
                    pass
            print(f"✅ Очередь {directory} очищена от старых 'хвостов'")
        else:
            os.makedirs(directory, exist_ok=True)

# ============================================================================
# КОНСТАНТЫ
# ============================================================================
TOTAL_PAIRS = 101
EXCLUDE_COUNT = 145
HISTORY_FILE = "dataset/test_history.json"


# ============================================================================
# ФУНКЦИЯ ОБОГАЩЕНИЯ ЧЕРЕЗ YANDEXGPT (v2.2)
# ============================================================================
def enrich_fighters_via_yandex(fighter_a: str, fighter_b: str,
                               fight_date: str, master_password: str,
                               fighter_a_stats: Dict = None,
                               fighter_b_stats: Dict = None) -> Tuple[Dict, Dict]:
    """Обогащает обоих бойцов через YandexGPT"""
    protocol = ExchangeProtocol()
    worker = ParserWorker(master_password=master_password)

    req_a = protocol.create_request(
        request_type="enrich",
        data={
            "fighter_name": fighter_a,
            "fight_date": fight_date,
            "fighter_stats": fighter_a_stats or {}
        },
        priority=3
    )

    req_b = protocol.create_request(
        request_type="enrich",
        data={
            "fighter_name": fighter_b,
            "fight_date": fight_date,
            "fighter_stats": fighter_b_stats or {}
        },
        priority=3
    )

    worker.run_once()

    response_a = protocol.get_response(req_a, timeout=30)
    response_b = protocol.get_response(req_b, timeout=30)

    enrichment_a = {}
    enrichment_b = {}

    if response_a and response_a.get('status') == 'success':
        enrichment_a = response_a.get('data', {})

    if response_b and response_b.get('status') == 'success':
        enrichment_b = response_b.get('data', {})

    protocol.cleanup_request(req_a)
    protocol.cleanup_request(req_b)

    return enrichment_a, enrichment_b


# ============================================================================
# ФУНКЦИЯ ЗАГРУЗКИ ПАР БОЙЦОВ
# ============================================================================
def load_fight_pairs() -> List[Dict]:
    """Загружает пары бойцов из базы данных"""
    dataset_dir = "dataset"
    pairs = []

    part_files = sorted([f for f in os.listdir(dataset_dir) if f.startswith("real_dataset_part")])

    for part_file in part_files:
        filepath = os.path.join(dataset_dir, part_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                pairs.extend(data)
        except Exception as e:
            print(f"⚠️ Ошибка чтения {part_file}: {e}")

    main_file = os.path.join(dataset_dir, "RRRreal_dataset.json")
    if os.path.exists(main_file):
        try:
            with open(main_file, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                pairs.extend(data)
        except Exception as e:
            print(f"⚠️ Ошибка чтения {main_file}: {e}")

    return pairs


# ============================================================================
# ФУНКЦИЯ ПОИСКА БОЯ
# ============================================================================
def find_fight(fighter_a: str, fighter_b: str, pairs: List[Dict]) -> Optional[Dict]:
    """Ищет бой между двумя бойцами"""
    for fight in pairs:
        fa = fight.get("fighter_a", "")
        fb = fight.get("fighter_b", "")

        if (fa == fighter_a and fb == fighter_b) or (fa == fighter_b and fb == fighter_a):
            return fight

    return None


# ============================================================================
# ФУНКЦИИ РАБОТЫ С ИСТОРИЕЙ ТЕСТОВ
# ============================================================================
def load_test_history() -> Dict:
    """Загружает историю протестированных боёв"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"tested_fights": [], "last_run": None}
    return {"tested_fights": [], "last_run": None}


def save_test_history(history: Dict):
    """Сохраняет историю протестированных боёв"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================
def main():
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='DIRECT TEST 101 v2.3')
    parser.add_argument('--seed', type=int, default=None,
                        help='Seed для воспроизводимости (по умолчанию: случайный)')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                        help='Пропускать уже протестированные бои (по умолчанию: True)')
    parser.add_argument('--force-new', action='store_true', default=False,
                        help='Принудительно выбрать только новые бои')
    parser.add_argument('--offset', type=int, default=0,
                        help='Смещение выборки (для получения разных наборов)')
    parser.add_argument('--no-skip', action='store_true', default=False,
                        help='Не пропускать уже протестированные бои')
    args = parser.parse_args()

    # Настройка seed
    if args.seed is not None:
        random.seed(args.seed)
        print(f"🎲 Используется seed: {args.seed}")
    else:
        # Генерируем случайный seed на основе времени
        seed = int(time.time()) % 1000000
        random.seed(seed)
        print(f"🎲 Случайный seed: {seed}")

    print("=" * 70)
    print(f"🧪 DIRECT TEST 101 v2.3 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Шаг 1: Инициализация SecureNeuralChannel
    master_password = input("🔐 Мастер-пароль: ").strip()
    if not SecureNeuralChannel.init(master_password):
        print("❌ Неверный пароль")
        return

    # Шаг 2: Проверка ИИ
    print("⏳ Проверка ИИ...")
    test_response = SecureNeuralChannel.query(
        prompt='{"status":"ok"}',
        system_prompt="Ты полезный ассистент. Отвечай только в JSON.",
        use_cache=False
    )

    if test_response and isinstance(test_response, dict):
        print("✅ ИИ работает")
    else:
        print("⚠️ ИИ не ответил корректно")

    # Шаг 3: Загрузка пар бойцов
    print("\n📊 Загрузка реальных пар из базы...")
    all_pairs = load_fight_pairs()
    print(f"✅ Загружено {len(all_pairs)} боёв из базы")

    # Исключаем пары из оригинального теста
    unique_pairs = []
    seen = set()
    for pair in all_pairs:
        key = f"{pair.get('fighter_a')}_{pair.get('fighter_b')}_{pair.get('date')}"
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)

    print(f"📋 Исключаем {EXCLUDE_COUNT} пар из оригинального теста")

    # Исключаем первые EXCLUDE_COUNT пар
    if len(unique_pairs) > EXCLUDE_COUNT:
        unique_pairs = unique_pairs[EXCLUDE_COUNT:]

    print(f"✅ Доступно {len(unique_pairs)} уникальных пар для теста")

    # Загружаем историю тестов
    history = load_test_history()
    tested_keys = set(history.get("tested_fights", []))

    # Фильтруем уже протестированные бои
    skip_existing = args.skip_existing and not args.no_skip

    if skip_existing or args.force_new:
        filtered_pairs = []
        for pair in unique_pairs:
            key = f"{pair.get('fighter_a')}_{pair.get('fighter_b')}_{pair.get('date')}"
            if key not in tested_keys:
                filtered_pairs.append(pair)

        if args.force_new and len(filtered_pairs) < TOTAL_PAIRS:
            print(f"⚠️ Недостаточно новых боёв: нужно {TOTAL_PAIRS}, доступно {len(filtered_pairs)}")
            print(f"   Добавляем уже протестированные для заполнения...")
            # Добавляем уже протестированные бои для заполнения
            remaining = TOTAL_PAIRS - len(filtered_pairs)
            already_tested = [p for p in unique_pairs if f"{p.get('fighter_a')}_{p.get('fighter_b')}_{p.get('date')}" in tested_keys]
            filtered_pairs.extend(random.sample(already_tested, min(remaining, len(already_tested))))

        print(f"📋 Исключено {len(unique_pairs) - len(filtered_pairs)} уже протестированных боёв")
        unique_pairs = filtered_pairs
    else:
        print(f"📋 Пропуск уже протестированных боёв: ОТКЛЮЧЁН")

    # Применяем смещение
    if args.offset > 0 and len(unique_pairs) > TOTAL_PAIRS + args.offset:
        unique_pairs = unique_pairs[args.offset:] + unique_pairs[:args.offset]

    # Выбираем TOTAL_PAIRS пар
    if len(unique_pairs) < TOTAL_PAIRS:
        print(f"⚠️ Недостаточно пар (нужно {TOTAL_PAIRS}, есть {len(unique_pairs)})")
        test_pairs = unique_pairs
    else:
        test_pairs = random.sample(unique_pairs, TOTAL_PAIRS)

    print(f"📋 Тестируем {len(test_pairs)} пар бойцов...")

    # Сохраняем текущие ключи в историю
    current_keys = []
    for pair in test_pairs:
        key = f"{pair.get('fighter_a')}_{pair.get('fighter_b')}_{pair.get('date')}"
        current_keys.append(key)

    # Обновляем историю
    history["tested_fights"] = list(set(history.get("tested_fights", []) + current_keys))
    history["last_run"] = datetime.now().isoformat()
    history["last_count"] = len(test_pairs)
    history["last_seed"] = args.seed
    save_test_history(history)

    # Шаг 4: Инициализация MMAEngine v46.0 (с пакетным обучением)
    engine = MMAEngine()
    initial_accuracy = engine.best_accuracy
    print(f"\n📊 Начальная точность модели: {initial_accuracy*100:.1f}%")

    # ✅ НОВОЕ: Однократная перекалибровка нормализатора перед тестом
    print("🔄 Однократная перекалибровка нормализатора перед тестом...")
    engine.recalibrate_scaler()
    print("✅ Перекалибровка завершена!")

    print("=" * 70)

    # Шаг 5: Основной цикл теста
    correct_predictions = 0
    total_predictions = 0
    report_lines = []
    start_time = time.time()

    for idx, pair in enumerate(test_pairs, 1):
        fighter_a = pair.get("fighter_a", "")
        fighter_b = pair.get("fighter_b", "")
        fight_date = pair.get("date", "")
        winner = pair.get("winner", "")

        print(f"\n[{idx}/{len(test_pairs)}] 🔍 {fighter_a} vs {fighter_b}")
        print(f"   ✅ ФАКТ: {fight_date} | {winner}")

        # Поиск боя
        fight = find_fight(fighter_a, fighter_b, all_pairs)
        if not fight:
            print(f"   ❌ Бой не найден")
            continue

        # Получаем статистику от DeepSeek
        print(f"   🧠 Получение статистики от DeepSeek...")
        try:
            fa_stats = DeepAIAnalyst.get_fighter_deep_stats(fighter_a, fight_date)
            fb_stats = DeepAIAnalyst.get_fighter_deep_stats(fighter_b, fight_date)
        except Exception as e:
            print(f"   ❌ Ошибка DeepSeek: {e}")
            continue

        # Формируем ПОЛНУЮ статистику для YandexGPT
        fighter_a_stats = {
            "age": fa_stats.age,
            "wins": fa_stats.wins,
            "losses": fa_stats.losses,
            "country": fa_stats.flag,
            "fin_rate": fa_stats.fin_rate,
            "sub_rate": fa_stats.sub_rate,
            "td_def": fa_stats.td_def,
            "grap_def": fa_stats.grap_def,
            "recent_wins": fa_stats.recent_wins,
            "months_off": fa_stats.months_off,
            "fights_12m": fa_stats.fights_12m,
            "dob": getattr(fa_stats, 'dob', None),
            "opponent_name": fighter_b,
            "opponent_record": f"{fb_stats.wins}-{fb_stats.losses}",
            "fight_context": "regular",
            "recent_form": fa_stats.form if hasattr(fa_stats, 'form') else []
        }

        fighter_b_stats = {
            "age": fb_stats.age,
            "wins": fb_stats.wins,
            "losses": fb_stats.losses,
            "country": fb_stats.flag,
            "fin_rate": fb_stats.fin_rate,
            "sub_rate": fb_stats.sub_rate,
            "td_def": fb_stats.td_def,
            "grap_def": fb_stats.grap_def,
            "recent_wins": fb_stats.recent_wins,
            "months_off": fb_stats.months_off,
            "fights_12m": fb_stats.fights_12m,
            "dob": getattr(fb_stats, 'dob', None),
            "opponent_name": fighter_a,
            "opponent_record": f"{fa_stats.wins}-{fa_stats.losses}",
            "fight_context": "regular",
            "recent_form": fb_stats.form if hasattr(fb_stats, 'form') else []
        }

        # Обогащение через YandexGPT
        print(f"   🧠 Обогащение через YandexGPT...")
        try:
            enrichment_a, enrichment_b = enrich_fighters_via_yandex(
                fighter_a, fighter_b, fight_date, master_password,
                fighter_a_stats=fighter_a_stats,
                fighter_b_stats=fighter_b_stats
            )
        except Exception as e:
            print(f"   ❌ Ошибка обогащения: {e}")
            continue

        # Применяем обогащение
        if enrichment_a:
            fa_stats.stress_factor = enrichment_a.get('stress_factor', 0.5)
            fa_stats.motivation_index = enrichment_a.get('motivation_index', 0.5)
            fa_stats.biorythm_score = enrichment_a.get('biorythm_score', 0.5)
            fa_stats.camp_quality = enrichment_a.get('camp_quality', 0.5)
            fa_stats.mystic_factor = enrichment_a.get('mystic_factor', 0.5)

        if enrichment_b:
            fb_stats.stress_factor = enrichment_b.get('stress_factor', 0.5)
            fb_stats.motivation_index = enrichment_b.get('motivation_index', 0.5)
            fb_stats.biorythm_score = enrichment_b.get('biorythm_score', 0.5)
            fb_stats.camp_quality = enrichment_b.get('camp_quality', 0.5)
            fb_stats.mystic_factor = enrichment_b.get('mystic_factor', 0.5)

        # Формируем FightData
        try:
            fd = FightData(
                a=fa_stats,
                b=fb_stats,
                date=datetime.strptime(fight_date, "%Y-%m-%d"),
                wc="Auto",
                rounds=3,
                location="UFC",
                odds_a=1.85,
                matchup_odds={"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85}
            )
        except Exception as e:
            print(f"   ❌ Ошибка создания FightData: {e}")
            continue

        # Прогноз
        prediction = engine.predict(fd)
        print(f"   🎯 Прогноз: {prediction.winner} ({prediction.prob*100:.0f}%)")

        # Обучение
        result = Result(
            winner=winner,
            rnd=3,
            method=FinishType.DECISION_UNANIMOUS,
            verification=VerificationStatus.VERIFIED_DUAL
        )

        train_result = engine.train_on_new_fight(fd, result, fighter_a, fighter_b)

        # Подсчёт точности
        is_correct = (prediction.winner == winner)
        if is_correct:
            correct_predictions += 1
            print(f"   ✅ Прогноз ВЕРНЫЙ!")
        else:
            print(f"   ❌ Прогноз НЕВЕРНЫЙ (факт: {winner})")

        total_predictions += 1

        # Сохраняем в отчёт
        report_lines.append({
            "fighter_a": fighter_a,
            "fighter_b": fighter_b,
            "date": fight_date,
            "prediction": prediction.winner,
            "confidence": prediction.prob,
            "fact": winner,
            "correct": is_correct
        })

    # Финальная статистика
    end_time = time.time()
    duration = end_time - start_time

    final_accuracy = engine.best_accuracy

    print("\n" + "=" * 70)
    print("📊 КРАТКАЯ СВОДКА")
    print("=" * 70)
    print(f"⏱️  Длительность: {duration:.1f} сек ({duration/60:.1f} мин)")
    print(f"📊 Всего пар: {len(test_pairs)}")
    print(f"✅ Верных: {correct_predictions}")
    print(f"❌ Неверных: {total_predictions - correct_predictions}")

    if total_predictions > 0:
        accuracy_pct = (correct_predictions / total_predictions) * 100
        print(f"🎯 Точность на тесте: {accuracy_pct:.1f}%")
    else:
        print(f"🎯 Точность на тесте: N/A (нет прогнозов)")

    print(f"\n📈 ТОЧНОСТЬ МОДЕЛИ:")
    print(f"   Начальная: {initial_accuracy*100:.1f}%")
    print(f"   Финальная: {final_accuracy*100:.1f}%")
    print(f"   Изменение: {(final_accuracy-initial_accuracy)*100:+.1f}%")
    print("=" * 70)

    # Сохраняем отчёт
    report_file = f"dataset/direct_test_report_101_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write(f"📊 DIRECT TEST 101 v2.3 ОТЧЁТ\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"🕐 Время теста: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"🎲 Seed: {args.seed or 'random'}\n")
        f.write(f"⏱️  Длительность: {duration:.1f} сек ({duration/60:.1f} мин)\n")
        f.write(f"📋 Пропуск уже тестированных: {'Да' if skip_existing else 'Нет'}\n\n")
        f.write("=" * 70 + "\n")
        f.write("📈 ТОЧНОСТЬ МОДЕЛИ\n")
        f.write("=" * 70 + "\n")
        f.write(f"📊 Начальная точность: {initial_accuracy*100:.1f}%\n")
        f.write(f"📊 Финальная точность: {final_accuracy*100:.1f}%\n")
        f.write(f"➡️  Изменение: {(final_accuracy-initial_accuracy)*100:+.1f}%\n\n")
        f.write("=" * 70 + "\n")
        f.write("📊 СТАТИСТИКА\n")
        f.write("=" * 70 + "\n")
        f.write(f"Всего пар:          {len(test_pairs)}\n")
        f.write(f"Прогнозов верных:   {correct_predictions}\n")
        f.write(f"Прогнозов неверных: {total_predictions - correct_predictions}\n")
        if total_predictions > 0:
            f.write(f"🎯 Точность на тесте: {(correct_predictions/total_predictions)*100:.1f}%\n")
        else:
            f.write(f"🎯 Точность на тесте: N/A (нет прогнозов)\n")
        f.write("=" * 70 + "\n")
        f.write("🥊 ДЕТАЛИ\n")
        f.write("=" * 70 + "\n\n")

        for line in report_lines:
            f.write(f"{line['fighter_a']} vs {line['fighter_b']} ({line['date']})\n")
            f.write(f"   Прогноз: {line['prediction']} ({line['confidence']*100:.0f}%)\n")
            f.write(f"   Факт: {line['fact']}\n")
            f.write(f"   Верно: {'✅' if line['correct'] else '❌'}\n\n")

    print(f"\n📄 Отчёт сохранён: {report_file}")
    print(f"📋 История тестов сохранена в: {HISTORY_FILE}")
    print(f"📊 Всего протестировано боёв: {len(history['tested_fights'])}")


if __name__ == "__main__":
    main()