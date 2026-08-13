#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БЫСТРЫЙ ТЕСТ: enrich_fighter_via_deepseek
Проверяет новый метод в deep_ai_analyst.py
"""
import sys
import json
sys.path.append(".")

from secure_neural_channel import SecureNeuralChannel
from deep_ai_analyst import DeepAIAnalyst

print("=" * 70)
print("🧪 ТЕСТ enrich_fighter_via_deepseek")
print("=" * 70)

# 1. Инициализация
password = input("🔐 Мастер-пароль: ").strip()
if not SecureNeuralChannel.init(password):
    print("❌ Неверный пароль")
    sys.exit(1)

print("✅ SecureNeuralChannel инициализирован")

# 2. Тестовые бойцы
test_cases = [
    {
        "fighter_name": "Jon Jones",
        "fight_date": "2023-03-04",
        "opponent_name": "Ciryl Gane",
        "opponent_record": "11-1",
        "fight_context": "title",
        "recent_form": ["W", "W", "W", "W", "L"]
    },
    {
        "fighter_name": "Islam Makhachev",
        "fight_date": "2023-10-21",
        "opponent_name": "Alexander Volkanovski",
        "opponent_record": "26-2",
        "fight_context": "title",
        "recent_form": ["W", "W", "W", "W", "W"]
    }
]

results = []

for i, tc in enumerate(test_cases, 1):
    print(f"\n{'=' * 70}")
    print(f"🥊 ТЕСТ {i}: {tc['fighter_name']} vs {tc['opponent_name']}")
    print(f"{'=' * 70}")

    try:
        result = DeepAIAnalyst.enrich_fighter(
            fighter_name=tc["fighter_name"],
            fight_date=tc["fight_date"],
            opponent_name=tc["opponent_name"],
            opponent_record=tc["opponent_record"],
            fight_context=tc["fight_context"],
            recent_form=tc["recent_form"]
        )

        if result:
            results.append(result)
            print(f"✅ УСПЕХ! Получено {len(result)} полей")
            print(f"\n КЛЮЧЕВЫЕ ПОЛЯ:")
            print(f"   • camp_name:      {result.get('camp_name', 'N/A')}")
            print(f"   • stress_factor:  {result.get('stress_factor', 'N/A')}")
            print(f"   • motivation:     {result.get('motivation_index', 'N/A')}")
            print(f"   • biorythm:       {result.get('biorythm_score', 'N/A')}")
            print(f"   • camp_quality:   {result.get('camp_quality', 'N/A')}")
            print(f"   • mystic_v2:      {result.get('mystic_v2', 'N/A')}")
            print(f"   • reach_cm:       {result.get('reach_cm', 'N/A')}")
            print(f"   • height_cm:      {result.get('height_cm', 'N/A')}")
        else:
            print(f"❌ ПУСТОЙ ОТВЕТ")

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

# 3. Сравнение результатов (проверка на шаблонность)
if len(results) >= 2:
    print(f"\n{'=' * 70}")
    print("📊 СРАВНЕНИЕ ЗНАЧЕНИЙ (проверка на шаблонность)")
    print(f"{'=' * 70}")

    fields_to_check = ["stress_factor", "motivation_index", "biorythm_score",
                       "camp_quality", "mystic_v2", "camp_name"]

    for field in fields_to_check:
        values = [r.get(field) for r in results]
        unique_values = set(str(v) for v in values)

        if len(unique_values) == 1:
            print(f"️  {field}: ОДИНАКОВОЕ ({values[0]}) — ШАБЛОН!")
        else:
            print(f"✅ {field}: РАЗНЫЕ ({values})")

# 4. Итог
print(f"\n{'=' * 70}")
print(" ИТОГ")
print(f"{'=' * 70}")
print(f"✅ Протестировано: {len(results)} из {len(test_cases)}")
if len(results) == len(test_cases):
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
else:
    print(f"⚠️  Пройдено {len(results)} из {len(test_cases)}")

print("=" * 70)