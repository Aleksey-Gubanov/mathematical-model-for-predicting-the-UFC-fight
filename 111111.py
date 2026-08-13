#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIGA ANALYSIS v1.1 | Глубокий математический анализ весов модели
================================================================
ЦЕЛИ:
1. Проверить гипотезу инверсии знаков (stress_diff, motivation_diff)
2. Измерить влияние каждого веса на точность
3. Предложить оптимизированный набор весов
"""
import json
import math
import os
import sys
from typing import List, Dict, Tuple

# Путь к весам
WEIGHTS_FILE = "mma_weights_v21.json"
BASELINE_FILE = "weights_baseline.json"
BEST_FILE = "weights_best.json"
DATASET_DIR = "dataset"

# Признаки (по порядку в файле весов)
FEATURE_NAMES = [
    "recent_wins_diff",       # 0
    "fin_rate_diff",          # 1
    "sub_rate_diff",          # 2
    "td_def_diff",            # 3
    "grap_def_diff",          # 4
    "age_diff",               # 5
    "exp_diff",               # 6
    "activity_diff",          # 7
    "rust_diff",              # 8
    "log_odds_ratio",         # 9
    "wp_diff",                # 10
    "stress_diff",            # 11 ← ПРОВЕРИТЬ!
    "motivation_diff",        # 12
    "biorythm_diff",          # 13
    "camp_diff",              # 14
    "mystic_diff",            # 15
    "fin_x_td",               # 16
    "sub_x_grap",             # 17
    "rust_x_exp",             # 18
    "stress_x_camp",          # 19
    "mystic_v2_diff",         # 20
]

# Формулы признаков (из math_engine.py _extract_features)
FEATURE_FORMULAS = {
    "recent_wins_diff": "(a.recent_wins - b.recent_wins) / 5.0",
    "fin_rate_diff": "a.fin_rate - b.fin_rate",
    "sub_rate_diff": "a.sub_rate - b.sub_rate",
    "td_def_diff": "a.td_def - b.td_def",
    "grap_def_diff": "a.grap_def - b.grap_def",
    "age_diff": "(a.age - b.age) / 10.0",
    "exp_diff": "(a_exp_total - b_exp_total) / 20.0",
    "activity_diff": "(a.fights_12m - b.fights_12m) / 5.0",
    "rust_diff": "(a.months_off - b.months_off) / 12.0",
    "log_odds_ratio": "log(odds_b / odds_a)",
    "wp_diff": "a.win_percent - b.win_percent",
    "stress_diff": "b.stress - a.stress  ← ПРОБЛЕМА!",
    "motivation_diff": "a.motivation - b.motivation",
    "biorythm_diff": "a.biorythm - b.biorythm",
    "camp_diff": "a.camp_quality - b.camp_quality",
    "mystic_diff": "a.mystic - b.mystic",
    "fin_x_td": "fin_rate_diff * td_def_diff",
    "sub_x_grap": "sub_rate_diff * grap_def_diff",
    "rust_x_exp": "rust_diff * exp_diff",
    "stress_x_camp": "stress_diff * camp_diff",
    "mystic_v2_diff": "a.mystic_v2 - b.mystic_v2",
}

# Интерпретация: должно ли положительное значение признака быть преимуществом для бойца А
EXPECTED_SIGN = {
    "recent_wins_diff": "positive",      # Больше побед подряд = лучше
    "fin_rate_diff": "positive",         # Выше финиш rate = лучше
    "sub_rate_diff": "positive",         # Выше сабмишн rate = лучше
    "td_def_diff": "positive",           # Выше TD defend = лучше
    "grap_def_diff": "positive",         # Выше grappling = лучше
    "age_diff": "negative",              # Младше = лучше (разница a-b > 0 значит А старше)
    "exp_diff": "positive",              # Больше опыта = лучше
    "activity_diff": "positive",         # Активнее = лучше
    "rust_diff": "positive",             # Больше отдых = лучше (a больше отдых - это плюс)
    "log_odds_ratio": "positive",        # Больше odds_b/odds_a = А фаворит
    "wp_diff": "positive",               # Больше побед = лучше
    "stress_diff": "negative",           # МЕНЬШЕ стресса = лучше (A со стрессом хуже!)
    "motivation_diff": "positive",       # Мотивация А > Б = лучше для А
    "biorythm_diff": "positive",         # Лучший биоритм = лучше
    "camp_diff": "positive",             # Лучший лагерь = лучше
    "mystic_diff": "positive",           # Мистика = хорошо
    "fin_x_td": "positive",              # Комбо финиш+защита = хорошо
    "sub_x_grap": "positive",            # Комбо сабмишн+грапплинг = хорошо
    "rust_x_exp": "neutral",             # Зависит от опыта
    "stress_x_camp": "neutral",          # Зависит от лагеря
    "mystic_v2_diff": "positive",        # Мистика v2 = хорошо
}


def load_weights(filename: str) -> Dict:
    if not os.path.exists(filename):
        print(f"❌ Файл {filename} не найден!")
        return None
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_inversion(weights: Dict) -> List[Dict]:
    """
    Анализирует каждый вес на соответствие ожидаемому знаку.
    """
    issues = []
    w = weights["weights"]

    for i, name in enumerate(FEATURE_NAMES):
        if i >= len(w):
            continue

        weight_val = w[i]
        expected = EXPECTED_SIGN.get(name, "neutral")
        formula = FEATURE_FORMULAS.get(name, "unknown")

        # Проверяем логику
        is_correct = False
        issue_type = None

        if expected == "positive":
            # Положительная разница (A лучше) должна давать положительный вес
            is_correct = weight_val > 0
            if not is_correct:
                issue_type = "INVERTED"
        elif expected == "negative":
            # Для stress_diff формула: b.stress - a.stress
            # Если A имеет ВЫСОКИЙ стресс, то diff < 0.
            # Чтобы оштрафовать A (вклад < 0), вес должен быть ПОЛОЖИТЕЛЬНЫМ (положительный * отрицательный = отрицательный).
            # Если вес ОТРИЦАТЕЛЬНЫЙ, то (отрицательный * отрицательный) = положительный вклад.
            # Это означает, что модель ПООЩРЯЕТ высокий стресс, что является критической инверсией.
            is_correct = weight_val > 0
            if not is_correct:
                issue_type = "CRITICAL INVERSION"
        elif expected == "neutral":
            is_correct = True

        issues.append({
            "index": i,
            "name": name,
            "formula": formula,
            "expected_direction": expected,
            "weight": weight_val,
            "is_correct_sign": is_correct,
            "issue_type": issue_type,
            "interpretation": _interpret_weight(name, weight_val),
        })

    return issues


def _interpret_weight(name: str, weight: float) -> str:
    """Интерпретирует что означает вес для модели."""
    if abs(weight) < 0.05:
        return "ИГНОРИРУЕТСЯ (вес ≈ 0)"

    if name == "wp_diff":
        if weight > 0.5:
            return f"🔥 ДОМИНИРУЕТ (вес {weight:.3f}) - модель слепа к остальному"
        return f"⚠️ Сильное влияние (вес {weight:.3f})"

    if name == "stress_diff":
        if weight < 0:
            return f"❌ КРИТИЧНО: ПООЩРЯЕТ высокий стресс (инверсия!)"
        return f"✅ Корректно (вес {weight:.3f})"

    if name in ["motivation_diff", "biorythm_diff", "camp_diff", "mystic_diff", "mystic_v2_diff"]:
        if weight < 0:
            return f"❌ ОШИБКА: ШТРАФУЕТ за позитивный фактор!"
        return f"✅ Корректно (вес {weight:.3f})"

    if weight > 0:
        return f"✅ Положительное влияние (вес {weight:.3f})"
    else:
        return f"⚠️ Отрицательное влияние (вес {weight:.3f})"


def print_analysis_report(issues: List[Dict], weights: Dict):
    """Выводит красивый отчет с анализом."""
    print("=" * 110)
    print("🧮 МАТЕМАТИЧЕСКИЙ АНАЛИЗ ВЕСОВ МОДЕЛИ")
    print("=" * 110)

    print(f"\n📊 ИСТОЧНИК: {WEIGHTS_FILE}")
    print(f"📅 Точность модели: {weights.get('loocv_accuracy', 0) * 100:.1f}%")
    print(f"🎯 Обучено на боях: {weights.get('trained_on_fights', '?')}")
    print(f"⚖️ Bias: {weights.get('bias', 0):.4f}")

    # Подсчёт проблем
    critical_issues = [i for i in issues if i["issue_type"] == "CRITICAL INVERSION"]
    inverted_issues = [i for i in issues if i["issue_type"] == "INVERTED"]
    ignored_weights = [i for i in issues if i["weight"] == 0 or abs(i["weight"]) < 0.05]
    dominant_weights = [i for i in issues if i["weight"] > 0.5 or i["weight"] < -0.5]

    print(f"\n{'=' * 110}")
    print("📈 РЕЗЮМЕ ПРОБЛЕМ")
    print(f"{'=' * 110}")
    print(f"❌ Критические инверсии: {len(critical_issues)}")
    for issue in critical_issues:
        print(f"   • {issue['name']} (index {issue['index']}): вес={issue['weight']:.4f} → {issue['interpretation']}")

    print(f"\n⚠️ Неправильные знаки: {len(inverted_issues)}")
    for issue in inverted_issues:
        print(f"   • {issue['name']}: вес={issue['weight']:.4f} (ожидание: {issue['expected_direction']})")

    print(f"\n🔇 Игнорируемые веса (< 0.05): {len(ignored_weights)}")
    for issue in ignored_weights:
        print(f"   • {issue['name']}: вес={issue['weight']:.4f}")

    print(f"\n🔥 Доминирующие веса (> 0.5 или < -0.5): {len(dominant_weights)}")
    for issue in dominant_weights:
        print(f"   • {issue['name']}: вес={issue['weight']:.4f}")

    print(f"\n{'=' * 110}")
    print("📋 ПОДРОБНЫЙ АНАЛИЗ КАЖДОГО ВЕСА")
    print(f"{'=' * 110}")
    print(f"{'Index':<6} {'Name':<20} {'Weight':>10} {'Formula':<35} {'Status':<30}")
    print("-" * 110)

    for issue in issues:
        status = "✅ OK" if issue["is_correct_sign"] else f"❌ {issue['issue_type'] or 'WRONG'}"
        print(f"{issue['index']:<6} {issue['name']:<20} {issue['weight']:>10.4f} {issue['formula']:<35} {status:<30}")

    # Математический анализ stress_diff
    print(f"\n{'=' * 110}")
    print("🔍 ГЛУБОКИЙ АНАЛИЗ: stress_diff (инверсия)")
    print(f"{'=' * 110}")

    stress_index = 11
    if stress_index < len(weights["weights"]):
        stress_weight = weights["weights"][stress_index]
        print(f"\n📌 Формула в коде: stress_diff = b.stress_factor - a.stress_factor")
        print(f"📌 Вес для stress_diff: {stress_weight:.4f}")
        print(f"\n📐 Математическая проверка:")
        print(f"   Сценарий 1: stress_a=0.8, stress_b=0.2")
        print(f"   → diff = 0.2 - 0.8 = -0.6 (A имеет больший стресс)")
        print(f"   → вклад = weight * diff = {stress_weight:.4f} * (-0.6) = {stress_weight * (-0.6):.4f}")
        if stress_weight < 0:
            print(f"   ⚠️ РЕЗУЛЬТАТ: Положительный вклад ({stress_weight * (-0.6):.4f}) за ВЫСОКИЙ СТРЕСС!")
            print(f"   ⚠️ Модель ПООЩРЯЕТ бойца с большим стрессом — это КРИТИЧЕСКАЯ ОШИБКА!")
        else:
            print(f"   ✅ РЕЗУЛЬТАТ: Отрицательный вклад ({stress_weight * (-0.6):.4f}) за стресс — корректно")

        print(f"\n   Сценарий 2: stress_a=0.2, stress_b=0.8")
        print(f"   → diff = 0.8 - 0.2 = +0.6 (A имеет меньший стресс)")
        print(f"   → вклад = weight * diff = {stress_weight:.4f} * (+0.6) = {stress_weight * 0.6:.4f}")
        if stress_weight < 0:
            print(f"   ⚠️ РЕЗУЛЬТАТ: Отрицательный вклад ({stress_weight * 0.6:.4f}) за НИЗКИЙ стресс!")
            print(f"   ⚠️ Модель ШТРАФУЕТ бойца с низким стрессом — это КРИТИЧЕСКАЯ ОШИБКА!")
        else:
            print(f"   ✅ РЕЗУЛЬТАТ: Положительный вклад ({stress_weight * 0.6:.4f}) за низкий стресс — корректно")

    # Анализ мотивации
    print(f"\n{'=' * 110}")
    print("🔍 ГЛУБОКИЙ АНАЛИЗ: motivation_diff")
    print(f"{'=' * 110}")

    mot_index = 12
    if mot_index < len(weights["weights"]):
        mot_weight = weights["weights"][mot_index]
        print(f"\n📌 Формула в коде: motivation_diff = a.motivation - b.motivation")
        print(f"📌 Вес для motivation_diff: {mot_weight:.4f}")

        print(f"\n   Сценарий: motivation_a=0.9, motivation_b=0.3")
        print(f"   → diff = 0.9 - 0.3 = +0.6 (A более мотивирован)")
        print(f"   → вклад = weight * diff = {mot_weight:.4f} * (+0.6) = {mot_weight * 0.6:.4f}")
        if mot_weight < 0:
            print(f"   ❌ РЕЗУЛЬТАТ: ШТРАФ ({mot_weight * 0.6:.4f}) за ВЫСОКУЮ мотивацию!")
        else:
            print(f"   ✅ РЕЗУЛЬТАТ: БОНУС ({mot_weight * 0.6:.4f}) за ВЫСОКУЮ мотивацию — корректно")

    print(f"\n{'=' * 110}")
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print(f"{'=' * 110}")


def main():
    weights = load_weights(WEIGHTS_FILE)
    if not weights:
        print("Не удалось загрузить веса. Убедитесь, что файл существует.")
        sys.exit(1)

    issues = analyze_inversion(weights)
    print_analysis_report(issues, weights)


if __name__ == "__main__":
    main()