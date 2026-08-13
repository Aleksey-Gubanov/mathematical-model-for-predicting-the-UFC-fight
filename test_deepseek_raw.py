#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ТЕСТ DEEPSEEK RAW | НОВЫЙ ПРОМПТ С ДИАПАЗОНОМ 0.0-1.0
"""
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from secure_neural_channel import SecureNeuralChannel

def main():
    print("=" * 70)
    print("🧪 ТЕСТ DEEPSEEK RAW | НОВЫЙ ПРОМПТ С ДИАПАЗОНОМ 0.0-1.0")
    print("=" * 70)

    # 1. Инициализация
    master_password = input("🔐 Мастер-пароль: ").strip()
    if not SecureNeuralChannel.init(master_password):
        print("❌ Неверный пароль")
        return

    # 2. Тестовый боец
    fighter_name = "Конор Макгрегор"
    target_date = "2023-08-01"

    print(f"\n🥊 Боец: {fighter_name}")
    print(f"📅 Дата: {target_date}")
    print("\n" + "=" * 70)

    # 3. НОВЫЙ ПРОМПТ С ЯВНЫМ УКАЗАНИЕМ ДИАПАЗОНА 0.0-1.0
    prompt = f"""Ты элитный аналитик ММА. Дай статистику бойца {fighter_name} на дату {target_date}.

Верни СТРОГО JSON с полями:
- "age": число (возраст в годах)
- "dob": строка "YYYY-MM-DD" (дата рождения)
- "record_wins": число (победы)
- "record_losses": число (поражения)
- "recent_wins": число (победы в последних 5 боях)
- "fin_rate": число от 0.0 до 1.0 (процент финишей, например 0.75 = 75%)
- "sub_rate": число от 0.0 до 1.0 (процент сабмишенов, например 0.30 = 30%)
- "td_def": число от 0.0 до 1.0 (защита от тейкдаунов, например 0.65 = 65%)
- "grap_def": число от 0.0 до 1.0 (защита в грэпплинге, например 0.70 = 70%)
- "months_off": число (месяцев без боёв)
- "fights_12m": число (боёв за последние 12 месяцев)
- "last_5_fights": массив из 5 строк "W"/"L"/"D" (последние 5 боёв)
- "stress_factor": число от 0.0 до 1.0 (психологическое давление)
- "motivation_index": число от 0.0 до 1.0 (мотивация)
- "biorythm_score": число от 0.0 до 1.0 (физическая форма)
- "camp_quality": число от 0.0 до 1.0 (качество лагеря)

ВАЖНО: Все проценты (fin_rate, sub_rate, td_def, grap_def) должны быть в диапазоне 0.0-1.0, НЕ 0-100!
Пример: если процент финишей 75%, верни 0.75, НЕ 75!"""

    print("\n📤 НОВЫЙ ПРОМПТ:")
    print("-" * 70)
    print(prompt)
    print("-" * 70)

    # 4. Запрос к DeepSeek
    print("\n⏳ Отправка запроса к DeepSeek...")

    try:
        response = SecureNeuralChannel.query(
            prompt,
            "Верни СТРОГО JSON.",
            use_cache=False
        )
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return

    # 5. СЫРОЙ ответ
    print("\n" + "=" * 70)
    print("📥 СЫРОЙ ОТВЕТ ОТ DEEPSEEK:")
    print("=" * 70)
    print(f"\nТип: {type(response).__name__}")
    print(f"\nСодержимое:\n{response}")

    # 6. Если это строка — пробуем распарсить
    if isinstance(response, str):
        print("\n" + "=" * 70)
        print("🔍 ПОПЫТКА РАСПАРСИТЬ JSON:")
        print("=" * 70)
        try:
            # Ищем JSON в строке
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                print("\n✅ УСПЕШНО! Распарсенный JSON:")
                print(json.dumps(parsed, indent=2, ensure_ascii=False))

                print("\n" + "=" * 70)
                print("📊 АНАЛИЗ ПОЛЕЙ:")
                print("=" * 70)

                required = [
                    "age", "dob", "record_wins", "record_losses",
                    "recent_wins", "fin_rate", "sub_rate", "td_def",
                    "grap_def", "months_off", "fights_12m",
                    "last_5_fights", "stress_factor", "motivation_index",
                    "biorythm_score", "camp_quality"
                ]

                for field in required:
                    value = parsed.get(field, "❌ ОТСУТСТВУЕТ")
                    status = "✅" if field in parsed else "❌"
                    print(f"  {status} {field}: {value}")

                # 7. ПРОВЕРКА ДИАПАЗОНА 0.0-1.0
                print("\n" + "=" * 70)
                print("🔍 ПРОВЕРКА ДИАПАЗОНА 0.0-1.0:")
                print("=" * 70)

                percentage_fields = ["fin_rate", "sub_rate", "td_def", "grap_def"]
                all_ok = True

                for field in percentage_fields:
                    value = parsed.get(field)
                    if value is not None:
                        try:
                            val_float = float(value)
                            if 0.0 <= val_float <= 1.0:
                                print(f"  ✅ {field}: {val_float} (в диапазоне 0.0-1.0)")
                            elif 1.0 < val_float <= 100.0:
                                print(f"  ❌ {field}: {val_float} (ПРОЦЕНТЫ 0-100, НУЖНО 0.0-1.0!)")
                                all_ok = False
                            else:
                                print(f"  ❌ {field}: {val_float} (ВНЕ ДИАПАЗОНА!)")
                                all_ok = False
                        except:
                            print(f"  ❌ {field}: не число")
                            all_ok = False
                    else:
                        print(f"  ❌ {field}: отсутствует")
                        all_ok = False

                if all_ok:
                    print("\n✅ ВСЕ ПОЛЯ В ДИАПАЗОНЕ 0.0-1.0! ПРОМПТ РАБОТАЕТ!")
                else:
                    print("\n❌ НЕКОТОРЫЕ ПОЛЯ ВНЕ ДИАПАЗОНА! НУЖЕН ДРУГОЙ ПРОМПТ!")
            else:
                print("❌ JSON не найден в ответе")
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")

    elif isinstance(response, dict):
        print("\n" + "=" * 70)
        print("📊 АНАЛИЗ ПОЛЕЙ (уже dict):")
        print("=" * 70)

        required = [
            "age", "dob", "record_wins", "record_losses",
            "recent_wins", "fin_rate", "sub_rate", "td_def",
            "grap_def", "months_off", "fights_12m",
            "last_5_fights", "stress_factor", "motivation_index",
            "biorythm_score", "camp_quality"
        ]

        for field in required:
            value = response.get(field, "❌ ОТСУТСТВУЕТ")
            status = "✅" if field in response else "❌"
            print(f"  {status} {field}: {value}")

        # 7. ПРОВЕРКА ДИАПАЗОНА 0.0-1.0
        print("\n" + "=" * 70)
        print("🔍 ПРОВЕРКА ДИАПАЗОНА 0.0-1.0:")
        print("=" * 70)

        percentage_fields = ["fin_rate", "sub_rate", "td_def", "grap_def"]
        all_ok = True

        for field in percentage_fields:
            value = response.get(field)
            if value is not None:
                try:
                    val_float = float(value)
                    if 0.0 <= val_float <= 1.0:
                        print(f"  ✅ {field}: {val_float} (в диапазоне 0.0-1.0)")
                    elif 1.0 < val_float <= 100.0:
                        print(f"  ❌ {field}: {val_float} (ПРОЦЕНТЫ 0-100, НУЖНО 0.0-1.0!)")
                        all_ok = False
                    else:
                        print(f"  ❌ {field}: {val_float} (ВНЕ ДИАПАЗОНА!)")
                        all_ok = False
                except:
                    print(f"  ❌ {field}: не число")
                    all_ok = False
            else:
                print(f"  ❌ {field}: отсутствует")
                all_ok = False

        if all_ok:
            print("\n✅ ВСЕ ПОЛЯ В ДИАПАЗОНЕ 0.0-1.0! ПРОМПТ РАБОТАЕТ!")
        else:
            print("\n❌ НЕКОТОРЫЕ ПОЛЯ ВНЕ ДИАПАЗОНА! НУЖЕН ДРУГОЙ ПРОМПТ!")

    print("\n" + "=" * 70)
    print("✅ ТЕСТ ЗАВЕРШЁН")
    print("=" * 70)

if __name__ == "__main__":
    main()