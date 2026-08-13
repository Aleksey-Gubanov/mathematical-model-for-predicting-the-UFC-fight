#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIRECT TEST 100 v5.6.1 | ПРОТОКОЛ БЕЗ ParserWorker
+ СОХРАНЕНИЕ ОШИБОК В CSV С 46 ПРИЗНАКАМИ
================================================================
ИЗМЕНЕНИЯ:
1. ✅ Добавлено сохранение всех 46 признаков для неверных прогнозов в CSV
2. ✅ CSV создаётся при каждом запуске (перезаписывается)
3. ✅ Добавлен аргумент --seed для воспроизводимости
4. ✅ Код адаптирован для анализа ошибок
================================================================
"""
import os
import sys
import csv
import json
import time
import random
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from math_engine import MMAEngine, Fighter, FightData, Result, FinishType, VerificationStatus
from deep_ai_analyst import DeepAIAnalyst
from secure_neural_channel import SecureNeuralChannel
from mystic_calculator import calculate_mystic_factor
from exchange_protocol import ExchangeProtocol

# ============================================================================
# КОНСТАНТЫ
# ============================================================================
TOTAL_PAIRS = 200
EXCLUDE_COUNT = 145
HISTORY_FILE = "dataset/test_history.json"
MIN_DATE = "2022-08-01"
REQUEST_DELAY = 2.5
REQUEST_TIMEOUT = 30
USE_PROTOCOL = False
ERRORS_CSV_FILE = "errors_full_data.csv"   # файл для ошибок

# ============================================================================
# ФУНКЦИЯ: ПОЛУЧИТЬ ВСЕ ДАННЫЕ БОЙЦА (БЕЗ ИЗМЕНЕНИЙ)
# ============================================================================
def get_fighter_data(fighter_name: str, fight_date: str,
                     opponent_name: str = None,
                     opponent_record: str = None,
                     fight_context: str = "regular",
                     recent_form: List[str] = None,
                     weight_class: str = None,
                     fighter_dob: str = None) -> Fighter:
    """
    ✅ v5.6.1: Прямой вызов DeepAIAnalyst с опциональным протоколом.
    """
    print(f"      🤖 Запрос полных данных для: {fighter_name}")

    data = None
    used_protocol = False

    if USE_PROTOCOL:
        try:
            protocol = ExchangeProtocol()
            req_id = protocol.create_request(
                request_type="enrich_deepseek",
                data={
                    "fighter_name": fighter_name,
                    "fight_date": fight_date,
                    "fighter_stats": {
                        "opponent_name": opponent_name,
                        "opponent_record": opponent_record,
                        "fight_context": fight_context,
                        "recent_form": recent_form or [],
                        "weight_class": weight_class
                    }
                },
                priority=3
            )
            response = protocol.get_response(req_id, timeout=5)
            if response and response.get('status') == 'success':
                data = response.get('data', {})
                used_protocol = True
                print(f"      ✅ Данные получены через протокол для: {fighter_name}")
            protocol.cleanup_request(req_id)
        except Exception as e:
            print(f"      ⚠️ Протокол недоступен: {e}")

    if not data:
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
    mystic_v2 = data.get('mystic_v2', 0.62)

    fighter = Fighter(
        name=fighter_name,
        age=data.get('age', 30),
        wins=data.get('wins', 0),
        losses=data.get('losses', 0),
        recent_wins=data.get('recent_wins', 0),
        form=recent_form or [],
        fin_rate=data.get('fin_rate', 0.5),
        sub_rate=data.get('sub_rate', 0.0),
        td_def=data.get('td_def', 0.5),
        grap_def=data.get('grap_def', 0.5),
        months_off=data.get('months_off', 0),
        fights_12m=data.get('fights_12m', 0),
        exp=data.get('wins', 0) + data.get('losses', 0),
        reach_cm=data.get('reach_cm', 180),
        height_cm=data.get('height_cm', 175),
        stress_factor=data.get('stress_factor', 0.5),
        motivation_index=data.get('motivation_index', 0.5),
        biorythm_score=data.get('biorythm_score', 0.5),
        camp_quality=data.get('camp_quality', 0.5),
        mystic_factor=mystic_factor,
        mystic_v2=mystic_v2
    )

    status = "📥 (протокол)" if used_protocol else "📥"
    print(f"      {status} {fighter_name}: {fighter.wins}-{fighter.losses}, "
          f"reach={fighter.reach_cm}, stress={fighter.stress_factor:.2f}, "
          f"mystic={fighter.mystic_factor:.2f}, mystic_v2={fighter.mystic_v2:.2f}")

    time.sleep(REQUEST_DELAY)
    return fighter


# ============================================================================
# ОСТАЛЬНЫЕ ФУНКЦИИ (БЕЗ ИЗМЕНЕНИЙ)
# ============================================================================
def load_fight_pairs() -> List[Dict]:
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

    valid_pairs = []
    for pair in all_pairs:
        date_str = pair.get("date", "")
        if date_str >= MIN_DATE:
            valid_pairs.append(pair)

    print(f"✅ Отфильтровано: оставлено {len(valid_pairs)} боев с {MIN_DATE} из {len(all_pairs)}")
    return valid_pairs

def load_test_history() -> Dict:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"tested_fights": [], "last_run": None}
    return {"tested_fights": [], "last_run": None}

def save_test_history(history: Dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description='DIRECT TEST 100 v5.6.1 + CSV errors')
    parser.add_argument('--seed', type=int, default=42, help='Seed для воспроизводимости (по умолчанию 42)')
    parser.add_argument('--no-skip', action='store_true', default=False, help='Не пропускать протестированные')
    parser.add_argument('--protocol', action='store_true', default=False, help='Использовать ExchangeProtocol (экспериментально)')
    args = parser.parse_args()

    global USE_PROTOCOL
    if args.protocol:
        USE_PROTOCOL = True
        print("⚠️ Включён экспериментальный режим ExchangeProtocol")

    random.seed(args.seed)
    print(f"🎲 Используется seed: {args.seed}")

    print("=" * 70)
    print(f"🧪 DIRECT TEST 100 v5.6.1 (Date >= {MIN_DATE}) + CSV errors")
    print("=" * 70)

    master_password = input("🔐 Мастер-пароль: ").strip()
    if not SecureNeuralChannel.init(master_password):
        print("❌ Неверный пароль")
        return

    print("⏳ Проверка ИИ...")
    if SecureNeuralChannel.query('{"status":"ok"}', "Тест", use_cache=False):
        print("✅ ИИ работает")

    print("\n📊 Загрузка реальных пар из базы (только с августа 2022)...")
    all_pairs = load_fight_pairs()

    unique_pairs = []
    seen = set()
    for pair in all_pairs:
        key = f"{pair.get('fighter_a')}_{pair.get('fighter_b')}_{pair.get('date')}"
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)

    if len(unique_pairs) > EXCLUDE_COUNT:
        unique_pairs = unique_pairs[EXCLUDE_COUNT:]

    history = load_test_history()
    tested_keys = set(history.get("tested_fights", []))
    skip_existing = not args.no_skip

    if skip_existing:
        new_pairs = [p for p in unique_pairs if f"{p.get('fighter_a')}_{p.get('fighter_b')}_{p.get('date')}" not in tested_keys]
        tested_pairs = [p for p in unique_pairs if f"{p.get('fighter_a')}_{p.get('fighter_b')}_{p.get('date')}" in tested_keys]

        if len(new_pairs) < TOTAL_PAIRS:
            needed = TOTAL_PAIRS - len(new_pairs)
            additional = random.sample(tested_pairs, min(needed, len(tested_pairs)))
            test_pairs = new_pairs + additional
            print(f"ℹ️ Новых пар: {len(new_pairs)}, дополнено протестированными: {len(additional)}")
        else:
            test_pairs = random.sample(new_pairs, TOTAL_PAIRS)
    else:
        test_pairs = random.sample(unique_pairs, min(TOTAL_PAIRS, len(unique_pairs)))

    print(f"📋 Выбрано {len(test_pairs)} пар для теста.")

    current_keys = [f"{p.get('fighter_a')}_{p.get('fighter_b')}_{p.get('date')}" for p in test_pairs]
    history["tested_fights"] = list(set(history.get("tested_fights", []) + current_keys))
    history["last_run"] = datetime.now().isoformat()
    save_test_history(history)

    engine = MMAEngine()
    print("\n📊 СТАРТ С ТЕКУЩИМИ ВЕСАМИ (накопление знаний)...")
    initial_accuracy = engine.best_accuracy
    print(f"✅ Начальная точность (текущие веса): {initial_accuracy*100:.1f}%")

    initial_weights_snapshot = {
        "weights": list(engine.model.weights),
        "accuracy": engine.best_accuracy
    }

    print("🔄 Перекалибровка нормализатора...")
    engine.recalibrate_scaler()
    print("=" * 70)

    correct_predictions = 0
    total_predictions = 0
    failed_predictions = 0
    report_lines = []
    start_time = time.time()
    interrupted = False
    last_completed_idx = 0

    # ================================================================
    # СОЗДАЁМ CSV-ФАЙЛ ДЛЯ ОШИБОК (заголовки)
    # ================================================================
    csv_headers = [
        "fighter_a", "fighter_b", "date", "winner", "prediction", "prob", "correct",
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
    # Перезаписываем файл при каждом запуске
    with open(ERRORS_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
    print(f"📁 Создан CSV-файл для ошибок: {ERRORS_CSV_FILE}")

    # ================================================================
    # ОСНОВНОЙ ЦИКЛ
    # ================================================================
    try:
        for idx, pair in enumerate(test_pairs, 1):
            fighter_a = pair.get("fighter_a", "")
            fighter_b = pair.get("fighter_b", "")
            fight_date = pair.get("date", "")
            winner = pair.get("winner", "")
            fighter_dob_a = pair.get("stats_a", {}).get("dob") if pair.get("stats_a") else None
            fighter_dob_b = pair.get("stats_b", {}).get("dob") if pair.get("stats_b") else None

            print(f"\n[{idx}/{len(test_pairs)}] 🔍 {fighter_a} vs {fighter_b} ({fight_date})")

            try:
                fa_stats = get_fighter_data(
                    fighter_name=fighter_a,
                    fight_date=fight_date,
                    opponent_name=fighter_b,
                    opponent_record=pair.get("stats_a", {}).get("record") if pair.get("stats_a") else None,
                    fight_context="regular",
                    fighter_dob=fighter_dob_a
                )

                fb_stats = get_fighter_data(
                    fighter_name=fighter_b,
                    fight_date=fight_date,
                    opponent_name=fighter_a,
                    opponent_record=pair.get("stats_b", {}).get("record") if pair.get("stats_b") else None,
                    fight_context="regular",
                    fighter_dob=fighter_dob_b
                )

                fd = FightData(
                    a=fa_stats, b=fb_stats,
                    date=datetime.strptime(fight_date, "%Y-%m-%d"),
                    wc="Auto", rounds=3, location="UFC",
                    odds_a=1.85, matchup_odds={"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85}
                )
                prediction = engine.predict(fd)

                # Извлечение признаков и вероятности
                odds_b = fd.matchup_odds.get("odds_b", 1.85) if fd.matchup_odds else 1.85
                features, feature_names = engine.model._extract_features(
                    fa_stats, fb_stats, fd.odds_a, odds_b
                )
                prob = engine.model.predict_proba(features)
                print(f"   📊 Вероятность победы {fighter_a}: {prob:.3f}")

                contributions = [(feature_names[i], engine.model.weights[i] * features[i]) for i in range(len(features))]
                contributions.sort(key=lambda x: abs(x[1]), reverse=True)
                top3 = contributions[:3]
                print("   📊 Топ-3 признака (вклад в прогноз):")
                for name, val in top3:
                    print(f"      {name}: {val:+.4f}")

                result = Result(winner=winner, rnd=3, method=FinishType.DECISION_UNANIMOUS, verification=VerificationStatus.VERIFIED_DUAL)
                engine.train_on_new_fight(fd, result, fighter_a, fighter_b)

                is_correct = (prediction.winner == winner)

                # ============================================================
                # ЕСЛИ ОШИБКА – ЗАПИСЫВАЕМ В CSV ВСЕ 46 ПРИЗНАКОВ
                # ============================================================
                if not is_correct:
                    a_features = features[:17]
                    b_features = features[17:34]
                    interactions = features[34:38]
                    extra = features[38:46]

                    row = [
                        fighter_a, fighter_b, fight_date, winner, prediction.winner,
                        round(prob, 6), is_correct,
                        *a_features, *b_features, *interactions, *extra
                    ]
                    with open(ERRORS_CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(row)

                if is_correct:
                    correct_predictions += 1
                    print(f"   ✅ Верно: {prediction.winner} ({prediction.prob*100:.0f}%)")
                else:
                    print(f"   ❌ Неверно: прогноз {prediction.winner}, факт {winner}")

                total_predictions += 1
                report_lines.append({
                    "fighter_a": fighter_a,
                    "fighter_b": fighter_b,
                    "date": fight_date,
                    "prediction": prediction.winner,
                    "confidence": prediction.prob,
                    "fact": winner,
                    "correct": is_correct,
                    "features": features,
                    "feature_names": feature_names
                })
                last_completed_idx = idx

            except KeyboardInterrupt:
                print(f"\n⚠️ Тест прерван на бое [{idx}]")
                interrupted = True
                break
            except Exception as e:
                print(f"   ⚠️ Ошибка: {e}")
                failed_predictions += 1
                continue

    except KeyboardInterrupt:
        print("\n⚠️ Тест прерван пользователем")
        interrupted = True

    # ================================================================
    # ЗАВЕРШЕНИЕ (без изменений)
    # ================================================================
    finally:
        print("\n" + "=" * 70)
        print("🔄 ПРИНУДИТЕЛЬНАЯ ОБРАБОТКА БУФЕРА ОБУЧЕНИЯ...")
        print("=" * 70)

        try:
            flush_result = engine.flush_buffer()
            if flush_result.get("status") == "trained":
                print(f"✅ {flush_result.get('status_text')}")
                print(f"   📊 {flush_result.get('accuracy_str')}")
            elif flush_result.get("status") == "empty":
                print("ℹ️ Буфер пуст — обработка не требуется")
            else:
                print(f"⚠️ Статус: {flush_result}")
        except Exception as e:
            print(f"❌ Ошибка flush_buffer: {e}")

        end_time = time.time()
        duration = end_time - start_time
        final_accuracy = engine.best_accuracy

        final_weights_snapshot = {
            "weights": list(engine.model.weights),
            "accuracy": engine.best_accuracy
        }

        try:
            snapshot_file = f"dataset/weights_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            snapshot_data = {
                "timestamp": datetime.now().isoformat(),
                "initial": initial_weights_snapshot,
                "final": final_weights_snapshot,
                "delta": {
                    "accuracy_change": (final_accuracy - initial_accuracy) * 100,
                    "weights_changed": sum(1 for a, b in zip(initial_weights_snapshot["weights"], final_weights_snapshot["weights"]) if abs(a - b) > 0.001)
                }
            }
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
            print(f"\n📄 Снапшот весов сохранён: {snapshot_file}")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения снапшота: {e}")

        print("\n" + "=" * 70)
        print("📊 ДЕЛЬТА ВЕСОВ (начало → конец теста)")
        print("=" * 70)
        feature_names_delta = [
            "recent_wins_diff", "fin_rate_diff", "sub_rate_diff", "td_def_diff", "grap_def_diff",
            "age_diff", "exp_diff", "activity_diff", "rust_diff", "log_odds_ratio",
            "wp_diff", "stress_diff", "motivation_diff", "biorythm_diff", "camp_diff",
            "mystic_diff", "fin_x_td", "sub_x_grap", "rust_x_exp", "stress_x_camp",
            "mystic_v2_diff"
        ]
        for i, (name, w_start, w_end) in enumerate(zip(feature_names_delta, initial_weights_snapshot["weights"], final_weights_snapshot["weights"])):
            delta = w_end - w_start
            if abs(delta) > 0.001:
                print(f"   {name:<20} {w_start:>7.4f} → {w_end:>7.4f}  (Δ {delta:>+.4f})")
        print("=" * 70)

        print("\n" + "=" * 70)
        if interrupted:
            print(f"⚠️ ТЕСТ ПРЕРВАН НА БОЕ [{last_completed_idx + 1}/{len(test_pairs)}]")
        else:
            print("📊 КРАТКАЯ СВОДКА")
        print("=" * 70)
        print(f"⏱️  Длительность: {duration:.1f} сек ({duration/60:.1f} мин)")
        print(f"📊 Всего пар: {len(test_pairs)}")
        print(f"✅ Верных: {correct_predictions}")
        print(f"❌ Неверных: {total_predictions - correct_predictions}")
        print(f"⚠️ Сбоев: {failed_predictions}")

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

        try:
            report_file = f"dataset/direct_test_report_100_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("📊 DIRECT TEST 100 v5.6.1 ОТЧЁТ\n")
                f.write("=" * 70 + "\n\n")
                f.write(f"🕐 Время теста: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"🎲 Seed: {args.seed}\n")
                f.write(f"⏱️  Длительность: {duration:.1f} сек ({duration/60:.1f} мин)\n")
                f.write(f"📋 Пропуск уже тестированных: {'Да' if skip_existing else 'Нет'}\n")
                if interrupted:
                    f.write(f"⚠️ ТЕСТ ПРЕРВАН на бое {last_completed_idx + 1}\n")
                f.write("\n")
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
                f.write(f"Сбоев обработки:    {failed_predictions}\n")
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
        except Exception as e:
            print(f"❌ Ошибка сохранения отчёта: {e}")

        print(f"📋 История тестов сохранена в: {HISTORY_FILE}")
        print(f"📊 Всего протестировано боёв: {len(history['tested_fights'])}")
        print(f"📁 Файл с ошибками (46 признаков) сохранён: {ERRORS_CSV_FILE}")


if __name__ == "__main__":
    main()