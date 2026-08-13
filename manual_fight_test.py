#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MANUAL FIGHT TEST | Ручной тест пайплайна MMA Predictor
================================================================
Использование:
1. Запуск: python manual_fight_test.py
2. Ввод мастер-пароля
3. Ввод пар бойцов в формате: "Имя1 - Имя2"
4. Для выхода: "exit" или "quit"
================================================================
"""
import sys
import os
from datetime import datetime, timedelta

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from secure_neural_channel import SecureNeuralChannel
    from math_engine import Fighter, FightData, Prediction, Result, FinishType, MMAEngine, names_match
    from ufc_parser import UFCParser
    from deep_ai_analyst import DeepAIAnalyst
    from fighters_ids_manager import (
        ensure_both_fighters_exist,
        add_ids_to_fight_in_memory,
        load_fighters_ids,
        get_canonical_name,
        names_match_by_id
    )
    # Импортируем функции из mma_predictor
    from mma_predictor import (
        clean_user_input,
        canonicalize_names_with_db,
        normalize_winner_name,
        enrich_fighters_via_yandex,
        load_known_fighters_cache,
        save_known_fighters_cache,
        strict_out
    )
    HAS_ALL_IMPORTS = True
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    import traceback
    traceback.print_exc()
    HAS_ALL_IMPORTS = False
    sys.exit(1)


def main():
    if not HAS_ALL_IMPORTS:
        print(" Не удалось импортировать необходимые модули. Выход.")
        return

    print("=" * 70)
    print("🧪 MANUAL FIGHT TEST | Ручной тест пайплайна")
    print("=" * 70)

    # 1. Инициализация SecureNeuralChannel
    pwd = ""
    try:
        pwd = input("🔐 Мастер-пароль: ").strip()
        if not SecureNeuralChannel.init(pwd):
            print("❌ Ошибка инициализации SecureNeuralChannel")
            return
        print("✅ SecureNeuralChannel инициализирован")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return

    # 2. Инициализация компонентов
    print("\n⚙️ Инициализация компонентов...")
    try:
        engine = MMAEngine()
        parser = UFCParser()
        analyst = DeepAIAnalyst()
        print("✅ Компоненты инициализированы")
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return

    # 3. Загрузка базы имён
    print("\n📥 Загрузка базы имён...")
    known_fighters = load_known_fighters_cache()
    if not known_fighters:
        print("⚠️ Кэш пуст, загрузка из парсера...")
        try:
            known_fighters = parser.get_all_known_fighters()
            save_known_fighters_cache(known_fighters)
            print(f"✅ Загружено {len(known_fighters)} имён из парсера")
        except Exception as e:
            print(f"❌ Не удалось загрузить: {e}")
            known_fighters = []
    else:
        print(f"✅ Загружено {len(known_fighters)} имён из кэша")

    # 4. Главный цикл
    print("\n" + "=" * 70)
    print("📋 ИНСТРУКЦИЯ:")
    print("   Формат ввода: Имя1 - Имя2")
    print("   Пример: Jon Jones - Stipe Miocic")
    print("   Для выхода: exit или quit")
    print("=" * 70)

    fight_count = 0
    correct_predictions = 0

    while True:
        try:
            print(f"\n{'=' * 70}")
            print(f" Бой #{fight_count + 1}")
            print(f"{'=' * 70}")

            raw_input = input("\n📥 Введите бойцов (Имя1 - Имя2): ").strip()

            if not raw_input:
                continue

            if raw_input.lower() in ["exit", "quit", "выход"]:
                print("\n👋 Завершение работы...")
                break

            # Очистка ввода
            user_in = clean_user_input(raw_input)
            if not user_in:
                print("❌ Пустой ввод")
                continue

            # Нормализация имён
            print(f"\n🔍 Нормализация имён...")
            names = canonicalize_names_with_db(user_in, known_fighters)
            if not names:
                print("❌ Не удалось сопоставить имена с базой")
                continue

            f1_clean = names["f1"]
            f2_clean = names["f2"]
            print(f"✅ Имена нормализованы: '{f1_clean}' vs '{f2_clean}'")

            # Поиск факта боя
            print(f"\n Шаг 1: Поиск факта боя...")
            fact = parser.get_fight_result(f1_clean, f2_clean)
            if not fact or 'winner' not in fact:
                print("❌ Бой не найден в архиве парсера")
                print("💡 Проверьте правильность написания имён")
                continue

            print(f"✅ ФАКТ найден: {fact['date'].strftime('%d.%m.%Y')} | {fact['winner']} ({fact['method']}, R{fact['round']})")

            # Целевая дата (за день до боя)
            target_date = (fact['date'] - timedelta(days=1)).strftime("%Y-%m-%d")
            fact_winner_normalized = normalize_winner_name(fact['winner'], f1_clean, f2_clean, parser)

            # Получение статистики от DeepSeek
            print(f"\n🧠 Шаг 2: Получение статистики на {target_date}...")
            fa = analyst.get_fighter_deep_stats(f1_clean, target_date)
            fb = analyst.get_fighter_deep_stats(f2_clean, target_date)

            if not fa or not fb:
                print("❌ Не удалось получить статистику от ИИ")
                continue

            print(f"✅ Статистика получена:")
            print(f"   {f1_clean}: {fa.wins}-{fa.losses}, возраст={fa.age}")
            print(f"   {f2_clean}: {fb.wins}-{fb.losses}, возраст={fb.age}")

            # Обогащение через YandexGPT
            print(f"\n🔮 Шаг 3: Обогащение через YandexGPT...")
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

            print(f"✅ Обогащение получено:")
            if enrichment_a:
                print(f"   {f1_clean}: stress={enrichment_a.get('stress_factor', 0.5):.2f}, "
                      f"motivation={enrichment_a.get('motivation_index', 0.5):.2f}, "
                      f"mystic_v2={enrichment_a.get('mystic_v2', 0.5):.2f}")
                fa.stress_factor = enrichment_a.get('stress_factor', fa.stress_factor)
                fa.motivation_index = enrichment_a.get('motivation_index', fa.motivation_index)
                fa.biorythm_score = enrichment_a.get('biorythm_score', fa.biorythm_score)
                fa.camp_quality = enrichment_a.get('camp_quality', fa.camp_quality)
                fa.mystic_factor = enrichment_a.get('mystic_factor', fa.mystic_factor)
                fa.mystic_v2 = enrichment_a.get('mystic_v2', getattr(fa, 'mystic_v2', 0.5))
            else:
                print(f"   {f1_clean}: ❌ Данные не получены")

            if enrichment_b:
                print(f"   {f2_clean}: stress={enrichment_b.get('stress_factor', 0.5):.2f}, "
                      f"motivation={enrichment_b.get('motivation_index', 0.5):.2f}, "
                      f"mystic_v2={enrichment_b.get('mystic_v2', 0.5):.2f}")
                fb.stress_factor = enrichment_b.get('stress_factor', fb.stress_factor)
                fb.motivation_index = enrichment_b.get('motivation_index', fb.motivation_index)
                fb.biorythm_score = enrichment_b.get('biorythm_score', fb.biorythm_score)
                fb.camp_quality = enrichment_b.get('camp_quality', fb.camp_quality)
                fb.mystic_factor = enrichment_b.get('mystic_factor', fb.mystic_factor)
                fb.mystic_v2 = enrichment_b.get('mystic_v2', getattr(fb, 'mystic_v2', 0.5))
            else:
                print(f"   {f2_clean}: ❌ Данные не получены")

            # Создание объектов для модели
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

            fd = FightData(
                a=fa,
                b=fb,
                date=fact['date'],
                wc="Auto",
                rounds=int(fact.get('round', 3)),
                location=fact.get('tournament', 'UFC')
            )

            # Прогноз
            print(f"\n⚙️ Шаг 4: Расчёт прогноза...")
            pred = engine.predict(fd)

            # Вывод результата
            matchup = {"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85}
            real_win = 100.0 if names_match_by_id(pred.winner, res.winner) else 0.0
            real_rnd = 100.0 if pred.rnd == res.rnd else 0.0
            real_mth = 100.0 if pred.method == res.method else 0.0

            print("\n" + strict_out(pred, res, fd, "ТЕСТ", matchup, f1_clean, f2_clean, real_win, real_rnd, real_mth))

            # Обучение (опционально)
            learn = input("\n📚 Добавить бой в обучение? (y/n): ").strip().lower()
            if learn == 'y':
                print("\n🔄 Обучение модели...")
                train_result = engine.train_on_new_fight(fd, res, f1_clean, f2_clean)
                if train_result and train_result.get("status") in ["updated", "trained"]:
                    print(f"✅ {train_result.get('status_text', 'Обучение завершено')}")
                    print(f"   {train_result.get('corrections', '0')}")
                    print(f"   📊 {train_result.get('accuracy_str', 'Точность обновлена')}")

                    # Обновление ID и кэша
                    fight_date_str = fd.date.strftime("%Y-%m-%d")
                    id_a, id_b = ensure_both_fighters_exist(f1_clean, f2_clean, fight_date_str)
                    if id_a and id_b:
                        print(f"   🔗 ID добавлены в базу")
                        id_result = add_ids_to_fight_in_memory(f1_clean, f2_clean)
                        if id_result.get("updated_files"):
                            print(f"   ✅ ID добавлены в: {', '.join(id_result['updated_files'])}")

                    if f1_clean not in known_fighters:
                        known_fighters.append(f1_clean)
                    if f2_clean not in known_fighters:
                        known_fighters.append(f2_clean)
                    save_known_fighters_cache(known_fighters)
                    print(f"    Кэш обновлён ({len(known_fighters)} имён)")
                else:
                    print("⚠️ Обучение не выполнено")

            fight_count += 1
            if real_win > 0:
                correct_predictions += 1

            print(f"\n📊 Статистика: {correct_predictions}/{fight_count} верных ({correct_predictions/max(fight_count,1)*100:.1f}%)")

        except KeyboardInterrupt:
            print("\n\n👋 Прервано пользователем")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            print("⚠️ Возврат к вводу...")
            continue

    print("\n" + "=" * 70)
    print(f"✅ Тест завершён. Обработано боёв: {fight_count}")
    print(f"🎯 Точность: {correct_predictions}/{fight_count} ({correct_predictions/max(fight_count,1)*100:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)