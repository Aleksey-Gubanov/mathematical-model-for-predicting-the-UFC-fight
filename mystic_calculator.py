#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MYSTIC CALCULATOR v1.0 | Программный расчёт мистического фактора
================================================================
ДЕТЕРМИНИРОВАННЫЙ расчёт mystic_factor БЕЗ YandexGPT.
Основан на 4 подфакторах:
1. Число судьбы (нумерология даты рождения)
2. Число дня боя (нумерология даты боя)
3. Совместимость чисел (таблица 9×9)
4. Фаза луны (математическая формула, точность ±1 день)

ФОРМУЛА:
mystic = destiny*0.25 + day*0.25 + compatibility*0.25 + moon*0.25

Диапазон: 0.0 (неблагоприятно) — 1.0 (максимально благоприятно)
================================================================
"""
from datetime import datetime
from typing import Dict, Optional


# ============================================================================
# ТАБЛИЦА СОВМЕСТИМОСТИ ЧИСЕЛ (9×9)
# ============================================================================
# Индексы: 1-9 (нумерологические числа)
# Значения: 0.0-1.0 (степень совместимости)
#
# Характеристика чисел:
# 1 = Лидер, воин         2 = Дипломат, партнёр
# 3 = Творец, артист      4 = Строитель, стабильность
# 5 = Путешественник      6 = Опекун, семья
# 7 = Мистик, аналитик    8 = Босс, власть
# 9 = Мудрец, философ
# ============================================================================
COMPATIBILITY_MATRIX = {
    #       1     2     3     4     5     6     7     8     9
    1: [0.50, 0.70, 0.80, 0.60, 0.90, 0.70, 0.80, 0.70, 0.60],  # Лидер
    2: [0.70, 0.60, 0.75, 0.80, 0.65, 0.90, 0.70, 0.65, 0.75],  # Дипломат
    3: [0.80, 0.75, 0.70, 0.55, 0.85, 0.80, 0.75, 0.60, 0.90],  # Творец
    4: [0.60, 0.80, 0.55, 0.75, 0.50, 0.85, 0.60, 0.90, 0.65],  # Строитель
    5: [0.90, 0.65, 0.85, 0.50, 0.70, 0.60, 0.80, 0.65, 0.75],  # Путешеств.
    6: [0.70, 0.90, 0.80, 0.85, 0.60, 0.75, 0.70, 0.80, 0.85],  # Опекун
    7: [0.80, 0.70, 0.75, 0.60, 0.80, 0.70, 0.95, 0.65, 0.90],  # Мистик
    8: [0.70, 0.65, 0.60, 0.90, 0.65, 0.80, 0.65, 0.85, 0.70],  # Босс
    9: [0.60, 0.75, 0.90, 0.65, 0.75, 0.85, 0.90, 0.70, 0.80],  # Мудрец
}


# ============================================================================
# ФУНКЦИЯ 1: РЕДУКЦИЯ ЧИСЛА ДО 1-9 (нумерология)
# ============================================================================
def reduce_to_digit(n: int) -> int:
    """
    Редукция числа до одной цифры (1-9) по правилам нумерологии.

    Примеры:
        28 → 2+8=10 → 1+0=1
        45 → 4+5=9
        19920512 → 1+9+9+2+0+5+1+2=29 → 2+9=11 → 1+1=2
    """
    if n <= 0:
        return 1
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n if n > 0 else 1


# ============================================================================
# ФУНКЦИЯ 2: ЧИСЛО СУДЬБЫ (из даты рождения)
# ============================================================================
def calculate_destiny_number(fighter_dob: str) -> Optional[int]:
    """
    Рассчитывает число судьбы бойца по дате рождения.

    :param fighter_dob: Дата рождения в формате "YYYY-MM-DD" или "DD.MM.YYYY"
    :return: Число 1-9 или None если дата невалидна
    """
    if not fighter_dob:
        return None
    try:
        digits = [int(d) for d in fighter_dob if d.isdigit()]
        if len(digits) < 8:
            return None
        return reduce_to_digit(sum(digits))
    except Exception:
        return None


# ============================================================================
# ФУНКЦИЯ 3: ЧИСЛО ДНЯ БОЯ
# ============================================================================
def calculate_day_number(fight_date: str) -> Optional[int]:
    """
    Рассчитывает число дня боя.

    :param fight_date: Дата боя в формате "YYYY-MM-DD" или "DD.MM.YYYY"
    :return: Число 1-9 или None если дата невалидна
    """
    if not fight_date:
        return None
    try:
        digits = [int(d) for d in fight_date if d.isdigit()]
        if len(digits) < 8:
            return None
        return reduce_to_digit(sum(digits))
    except Exception:
        return None


# ============================================================================
# ФУНКЦИЯ 4: СОВМЕСТИМОСТЬ ЧИСЕЛ
# ============================================================================
def calculate_compatibility(destiny_number: int, day_number: int) -> float:
    """
    Рассчитывает совместимость числа судьбы и числа дня.

    :param destiny_number: Число судьбы бойца (1-9)
    :param day_number: Число дня боя (1-9)
    :return: Значение 0.0-1.0
    """
    if not (1 <= destiny_number <= 9) or not (1 <= day_number <= 9):
        return 0.5  # Дефолт при невалидных данных
    return COMPATIBILITY_MATRIX[destiny_number][day_number - 1]


# ============================================================================
# ФУНКЦИЯ 5: ФАЗА ЛУНЫ (математическая формула)
# ============================================================================
def calculate_moon_phase_value(fight_date: str) -> float:
    """
    Рассчитывает влияние фазы луны на бойца в день боя.

    Использует синодический месяц (29.53 дня) и известное новолуние 06.01.2000.
    Точность: ±1 день (достаточно для мистического фактора).

    Фазы луны и их значения:
    - Новолуние (0°)     → 0.3 (слабость, начало цикла)
    - Первая четверть    → 0.5 (рост)
    - Полнолуние (180°)  → 0.9 (пик силы)
    - Последняя четверть → 0.6 (спад)

    :param fight_date: Дата боя в формате "YYYY-MM-DD" или "DD.MM.YYYY"
    :return: Значение 0.0-1.0
    """
    if not fight_date:
        return 0.5

    try:
        # Парсим дату
        if '-' in fight_date:
            dt = datetime.strptime(fight_date, "%Y-%m-%d")
        elif '.' in fight_date:
            dt = datetime.strptime(fight_date, "%d.%m.%Y")
        else:
            return 0.5

        # Известное новолуние: 6 января 2000, 18:14 UTC
        known_new_moon = datetime(2000, 1, 6, 18, 14)
        synodic_month = 29.530588853  # Синодический месяц в днях

        # Разница в днях
        days_diff = (dt - known_new_moon).total_seconds() / 86400.0

        # Фаза в цикле (0-1)
        phase = (days_diff % synodic_month) / synodic_month

        # Конвертируем в значение 0.0-1.0
        if phase < 0.125:
            # Новолуние → растущий серп
            value = 0.3 + (phase / 0.125) * 0.2
        elif phase < 0.25:
            # Растущий серп → первая четверть
            value = 0.5 + ((phase - 0.125) / 0.125) * 0.2
        elif phase < 0.375:
            # Первая четверть → растущая луна
            value = 0.7 + ((phase - 0.25) / 0.125) * 0.2
        elif phase < 0.5:
            # Растущая луна → полнолуние
            value = 0.9 - ((phase - 0.375) / 0.125) * 0.1
        elif phase < 0.625:
            # Полнолуние → убывающая луна
            value = 0.8 - ((phase - 0.5) / 0.125) * 0.2
        elif phase < 0.75:
            # Убывающая луна → последняя четверть
            value = 0.6 - ((phase - 0.625) / 0.125) * 0.1
        elif phase < 0.875:
            # Последняя четверть → убывающий серп
            value = 0.5 - ((phase - 0.75) / 0.125) * 0.1
        else:
            # Убывающий серп → новолуние
            value = 0.4 - ((phase - 0.875) / 0.125) * 0.1

        return round(max(0.3, min(0.9, value)), 2)

    except Exception as e:
        print(f"⚠️ Ошибка расчёта фазы луны: {e}")
        return 0.5


# ============================================================================
# ФУНКЦИЯ 6: ОПРЕДЕЛЕНИЕ НАЗВАНИЯ ФАЗЫ ЛУНЫ (для диагностики)
# ============================================================================
def get_moon_phase_name(fight_date: str) -> str:
    """Возвращает название фазы луны для диагностики."""
    if not fight_date:
        return "Неизвестно"

    try:
        if '-' in fight_date:
            dt = datetime.strptime(fight_date, "%Y-%m-%d")
        elif '.' in fight_date:
            dt = datetime.strptime(fight_date, "%d.%m.%Y")
        else:
            return "Неизвестно"

        known_new_moon = datetime(2000, 1, 6, 18, 14)
        synodic_month = 29.530588853
        days_diff = (dt - known_new_moon).total_seconds() / 86400.0
        phase = (days_diff % synodic_month) / synodic_month

        if phase < 0.0625 or phase >= 0.9375:
            return "🌑 Новолуние"
        elif phase < 0.1875:
            return "🌒 Растущий серп"
        elif phase < 0.3125:
            return "🌓 Первая четверть"
        elif phase < 0.4375:
            return "🌔 Растущая луна"
        elif phase < 0.5625:
            return "🌕 Полнолуние"
        elif phase < 0.6875:
            return "🌖 Убывающая луна"
        elif phase < 0.8125:
            return "🌗 Последняя четверть"
        else:
            return "🌘 Убывающий серп"
    except Exception:
        return "Неизвестно"


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ: РАСЧЁТ MYSTIC FACTOR
# ============================================================================
def calculate_mystic_factor(fighter_dob: str, fight_date: str) -> Dict:
    """
    Рассчитывает мистический фактор бойца на дату боя.

    ФОРМУЛА:
    mystic = destiny*0.25 + day*0.25 + compatibility*0.25 + moon*0.25

    :param fighter_dob: Дата рождения бойца ("YYYY-MM-DD" или "DD.MM.YYYY")
    :param fight_date: Дата боя ("YYYY-MM-DD" или "DD.MM.YYYY")
    :return: dict с компонентами и итоговым значением
    """
    # 1. Число судьбы
    destiny_number = calculate_destiny_number(fighter_dob)
    if destiny_number is None:
        destiny_value = 0.5
        destiny_number = 5  # Нейтральное число
    else:
        # Сила числа судьбы (нумерологическая интерпретация)
        destiny_strength = {
            1: 0.80,  # Лидер — высокая сила
            2: 0.50,  # Дипломат — средняя
            3: 0.70,  # Творец — выше среднего
            4: 0.60,  # Строитель — средняя
            5: 0.90,  # Путешественник — очень высокая
            6: 0.60,  # Опекун — средняя
            7: 0.75,  # Мистик — высокая
            8: 0.70,  # Босс — высокая
            9: 0.85   # Мудрец — очень высокая
        }
        destiny_value = destiny_strength.get(destiny_number, 0.5)

    # 2. Число дня боя
    day_number = calculate_day_number(fight_date)
    if day_number is None:
        day_value = 0.5
        day_number = 5
    else:
        day_strength = {
            1: 0.70, 2: 0.50, 3: 0.80, 4: 0.60, 5: 0.85,
            6: 0.70, 7: 0.75, 8: 0.65, 9: 0.90
        }
        day_value = day_strength.get(day_number, 0.5)

    # 3. Совместимость чисел
    compatibility_value = calculate_compatibility(destiny_number, day_number)

    # 4. Фаза луны
    moon_value = calculate_moon_phase_value(fight_date)
    moon_phase_name = get_moon_phase_name(fight_date)

    # ИТОГОВАЯ ФОРМУЛА
    mystic_factor = (
            destiny_value * 0.25 +
            day_value * 0.25 +
            compatibility_value * 0.25 +
            moon_value * 0.25
    )

    return {
        "mystic_factor": round(mystic_factor, 2),
        "components": {
            "destiny_number": destiny_number,
            "destiny_value": round(destiny_value, 2),
            "day_number": day_number,
            "day_value": round(day_value, 2),
            "compatibility": round(compatibility_value, 2),
            "moon_phase": round(moon_value, 2),
            "moon_phase_name": moon_phase_name
        }
    }


# ============================================================================
# ТЕСТ ПРИ ЗАПУСКЕ
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТ MYSTIC CALCULATOR v1.0")
    print("=" * 70)

    # Тест 1: Магомед Анкалаев (12.05.1992) vs Джонни Уокер (18.04.1992)
    # Бой: 13.01.2024

    print("\n🧪 Тест 1: Магомед Анкалаев")
    print("   Дата рождения: 12.05.1992")
    print("   Дата боя: 13.01.2024")
    result_a = calculate_mystic_factor("1992-05-12", "2024-01-13")
    print(f"   Результат: {result_a}")

    print("\n🧪 Тест 2: Джонни Уокер")
    print("   Дата рождения: 18.04.1992")
    print("   Дата боя: 13.01.2024")
    result_b = calculate_mystic_factor("1992-04-18", "2024-01-13")
    print(f"   Результат: {result_b}")

    # Сравнение
    print("\n📊 СРАВНЕНИЕ:")
    print(f"   Анкалаев mystic: {result_a['mystic_factor']}")
    print(f"   Уокер mystic:    {result_b['mystic_factor']}")
    diff = result_a['mystic_factor'] - result_b['mystic_factor']
    print(f"   Разница: {diff:+.2f}")

    # Тест 3: Детерминированность
    print("\n🧪 Тест 3: Детерминированность (повторный расчёт)")
    result_a2 = calculate_mystic_factor("1992-05-12", "2024-01-13")
    print(f"   Первый расчёт:  {result_a['mystic_factor']}")
    print(f"   Второй расчёт:  {result_a2['mystic_factor']}")
    print(f"   Совпадают: {result_a['mystic_factor'] == result_a2['mystic_factor']} ✅")

    # Тест 4: Разные даты → разные значения
    print("\n🧪 Тест 4: Разные даты боя (Анкалаев)")
    for date in ["2024-01-13", "2024-06-22", "2024-12-31"]:
        result = calculate_mystic_factor("1992-05-12", date)
        phase = result['components']['moon_phase_name']
        print(f"   {date}: mystic={result['mystic_factor']}, "
              f"moon={result['components']['moon_phase']}, фаза={phase}")

    # Тест 5: Без даты рождения
    print("\n🧪 Тест 5: Без даты рождения (fallback)")
    result = calculate_mystic_factor(None, "2024-01-13")
    print(f"   Результат: {result}")

    # Тест 6: Проверка всех 9 чисел судьбы
    print("\n🧪 Тест 6: Все 9 чисел судьбы (дата боя: 2024-01-13)")
    for i in range(1, 10):
        # Генерируем дату рождения, дающую нужное число
        # Для простоты: используем прямое значение
        result = calculate_mystic_factor(f"2000-01-0{i}", "2024-01-13")
        print(f"   Число {i}: mystic={result['mystic_factor']}")

    print("\n" + "=" * 70)
    print("✅ ТЕСТ ЗАВЕРШЁН!")
    print("=" * 70)