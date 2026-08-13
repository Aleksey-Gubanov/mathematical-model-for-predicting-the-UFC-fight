#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STRICT API PIPELINE v3.0 | СТРОГОЕ СОБЛЮДЕНИЕ АРХИТЕКТУРЫ
================================================================
ПРАВИЛА:
1. НЕ читает dataset/*.json напрямую.
2. ФАКТ боя получает ТОЛЬКО через parser.get_fight_result() (который сам управляет кэшем/сайтом).
3. СТАТИСТИКА только от DeepAIAnalyst.
4. ОБОГАЩЕНИЕ только от YandexEnricher.
5. Имена только очищаются и передаются парсеру, который сам делает fuzzy-matching.
================================================================
"""
import sys
import os
from datetime import datetime, timedelta
import re

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from secure_neural_channel import SecureNeuralChannel
    from math_engine import Fighter, FightData, Result, FinishType, MMAEngine
    from ufc_parser import UFCParser
    from deep_ai_analyst import DeepAIAnalyst
    from yandex_enricher import YandexEnricher
    HAS_ALL_IMPORTS = True
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    import traceback
    traceback.print_exc()
    HAS_ALL_IMPORTS = False
    sys.exit(1)


def clean_name_for_parser(raw_name: str) -> str:
    """Минимальная очистка имени перед передачей в парсер."""
    if not raw_name:
        return ""
    # Убираем лишние пробелы и нормализуем тире
    name = re.sub(r'\s+', ' ', raw_name.strip())
    name = name.replace('—', '-').replace('–', '-').replace('−', '-')
    return name


def validate_fighter_stats(fighter: Fighter, name: str) -> bool:
    """Отлавливает мусор от DeepSeek."""
    if not fighter:
        print(f"   🔴 [{name}] Объект Fighter пуст!")
        return False
    if fighter.wins == 0 and fighter.losses == 0:
        print(f"   🔴 [{name}] DeepSeek вернул нулевой рекорд (0-0). Мусор!")
        return False
    if fighter.age < 16 or fighter.age > 60:
        print(f"   🔴 [{name}] Некорректный возраст: {fighter.age}")
        return False
    return True


def validate_enrichment(enrichment: dict, name: str) -> bool:
    """Отлавливает мусор от YandexGPT."""
    if not enrichment:
        print(f"   🔴 [{name}] YandexGPT вернул пустой словарь!")
        return False
    required_keys = ['stress_factor', 'motivation_index', 'biorythm_score', 'camp_quality', 'mystic_v2']
    for key in required_keys:
        if key not in enrichment:
            print(f"   🔴 [{name}] Отсутствует ключ {key} в обогащении!")
            return False
    return True


def run_pipeline():
    if not HAS_ALL_IMPORTS:
        return

    print("=" * 70)
    print("🚀 STRICT API PIPELINE v3.0 | Архитектурно чистый тест")
    print("=" * 70)

    pwd = input("🔐 Мастер-пароль: ").strip()
    try:
        if not SecureNeuralChannel.init(pwd):
            print("❌ Ошибка инициализации SecureNeuralChannel!")
            return
        print("✅ SecureNeuralChannel инициализирован")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return

    print("\n⚙️ Инициализация компонентов...")
    try:
        engine = MMAEngine()
        # ✅ Парсер сам загрузит свой кэш и будет управлять им
        parser = UFCParser(similarity_threshold=0.75)
        analyst = DeepAIAnalyst()
        enricher = YandexEnricher(master_password=pwd)
        print("✅ Компоненты инициализированы")
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return

    print("\n" + "=" * 70)
    print(" ИНСТРУКЦИЯ:")
    print("   Формат ввода: Имя1 - Имя2")
    print("   Для выхода: exit или quit")
    print("=" * 70)

    fight_count = 0
    correct_predictions = 0
    MAX_FIGHTS = 100

    while fight_count < MAX_FIGHTS:
        try:
            print(f"\n{'=' * 70}")
            print(f"🥊 Бой #{fight_count + 1}")
            print(f"{'=' * 70}")

            raw_input = input("\n📥 Введите бойцов (Имя1 - Имя2): ").strip()

            if not raw_input:
                continue

            if raw_input.lower() in ["exit", "quit", "выход"]:
                print("\n👋 Завершение работы...")
                break

            # Шаг 1: Разделение и минимальная очистка имен
            parts = None
            for sep in [" - ", " — ", " vs ", " VS ", " против ", "-"]:
                if sep in raw_input:
                    parts = raw_input.split(sep, 1)
                    break

            if not parts or len(parts) != 2:
                print("❌ Не удалось разделить имена. Используйте формат 'Имя1 - Имя2'")
                continue

            f1_clean = clean_name_for_parser(parts[0])
            f2_clean = clean_name_for_parser(parts[1])

            if not f1_clean or not f2_clean:
                print("❌ Пустое имя после очистки")
                continue

            print(f"✅ Имена для поиска: '{f1_clean}' vs '{f2_clean}'")

            # Шаг 2: ПОЛУЧЕНИЕ ФАКТА ТОЛЬКО ЧЕРЕЗ ПАРСЕР
            # Парсер сам решит: взять из кэша, спросить ИИ или спарсить сайт.
            # Он сам применит _search_with_smart_logic и динамическую защиту от прогнозов.
            print(f"\n📄 Шаг 1: Поиск факта боя (через UFCParser)...")
            fact = parser.get_fight_result(f1_clean, f2_clean)

            if not fact or 'winner' not in fact:
                print("❌ Бой не найден (парсер не нашел факт в кэше или на сайте).")
                continue

            print(f"✅ ФАКТ: {fact['date'].strftime('%d.%m.%Y')} | Победитель: {fact['winner']}")

            # Целевая дата для ИИ (за день до боя)
            target_date = (fact['date'] - timedelta(days=1)).strftime("%Y-%m-%d")

            # Шаг 3: ПОЛУЧЕНИЕ СТАТИСТИКИ ТОЛЬКО ОТ DEEPSEEK
            print(f"\n🧠 Шаг 2: Запрос статистики у DeepSeek на {target_date}...")
            fa = analyst.get_fighter_deep_stats(f1_clean, target_date)
            fb = analyst.get_fighter_deep_stats(f2_clean, target_date)

            if not validate_fighter_stats(fa, f1_clean) or not validate_fighter_stats(fb, f2_clean):
                print("❌ Данные от DeepSeek не прошли валидацию. Пропуск.")
                continue

            print(f"✅ Статистика: {f1_clean} ({fa.wins}-{fa.losses}), {f2_clean} ({fb.wins}-{fb.losses})")

            # Шаг 4: ОБОГАЩЕНИЕ ТОЛЬКО ОТ YANDEXGPT
            print(f"\n🔮 Шаг 3: Обогащение через YandexGPT...")
            enrich_a = enricher.enrich_fighter(
                fighter_name=f1_clean,
                fight_date=target_date,
                fighter_stats={"age": fa.age, "wins": fa.wins, "losses": fa.losses, "dob": fa.dob},
                opponent_name=f2_clean,
                opponent_record=f"{fb.wins}-{fb.losses}",
                fight_context="regular",
                recent_form=fa.form
            )
            enrich_b = enricher.enrich_fighter(
                fighter_name=f2_clean,
                fight_date=target_date,
                fighter_stats={"age": fb.age, "wins": fb.wins, "losses": fb.losses, "dob": fb.dob},
                opponent_name=f1_clean,
                opponent_record=f"{fa.wins}-{fa.losses}",
                fight_context="regular",
                recent_form=fb.form
            )

            if not validate_enrichment(enrich_a, f1_clean) or not validate_enrichment(enrich_b, f2_clean):
                print("❌ Данные от YandexGPT не прошли валидацию. Пропуск.")
                continue

            # Применяем обогащение
            fa.stress_factor = enrich_a.get('stress_factor', fa.stress_factor)
            fa.motivation_index = enrich_a.get('motivation_index', fa.motivation_index)
            fa.biorythm_score = enrich_a.get('biorythm_score', fa.biorythm_score)
            fa.camp_quality = enrich_a.get('camp_quality', fa.camp_quality)
            fa.mystic_factor = enrich_a.get('mystic_factor', fa.mystic_factor)
            fa.mystic_v2 = enrich_a.get('mystic_v2', getattr(fa, 'mystic_v2', 0.5))

            fb.stress_factor = enrich_b.get('stress_factor', fb.stress_factor)
            fb.motivation_index = enrich_b.get('motivation_index', fb.motivation_index)
            fb.biorythm_score = enrich_b.get('biorythm_score', fb.biorythm_score)
            fb.camp_quality = enrich_b.get('camp_quality', fb.camp_quality)
            fb.mystic_factor = enrich_b.get('mystic_factor', fb.mystic_factor)
            fb.mystic_v2 = enrich_b.get('mystic_v2', getattr(fb, 'mystic_v2', 0.5))

            print(f"✅ Обогащение: {f1_clean} mystic_v2={fa.mystic_v2:.2f}, {f2_clean} mystic_v2={fb.mystic_v2:.2f}")

            # Шаг 5: РАСЧЕТ ПРОГНОЗА
            print(f"\n⚙️ Шаг 4: Расчёт прогноза...")
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
                winner=fact['winner'],
                rnd=int(fact.get('round', 3)),
                method=meth_map.get(str(fact.get('method', 'UD')).upper(), FinishType.DECISION_UNANIMOUS)
            )

            fd = FightData(
                a=fa,
                b=fb,
                date=fact['date'],
                wc="Auto",
                rounds=int(fact.get('round', 3)),
                location=fact.get('tournament', 'UFC')
            )

            pred = engine.predict(fd)

            print(f"\n🔮 ПРОГНОЗ: {pred.winner} ({pred.prob*100:.1f}%)")
            print(f"✅ ФАКТ: {res.winner}")

            if pred.winner == res.winner:
                print("✅ ПРОГНОЗ ВЕРНЫЙ!")
                correct_predictions += 1
            else:
                print("❌ ПРОГНОЗ НЕВЕРНЫЙ")

            fight_count += 1
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
        run_pipeline()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)