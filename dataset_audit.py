#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dataset_audit.py — диагностика реального содержимого dataset/
Запуск: python dataset_audit.py
"""
import os
import json
import glob
from collections import Counter

DATASET_DIR = "dataset"


def safe_get(d, key, default=None):
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def line(title=""):
    print("=" * 78)
    if title:
        print(title)
        print("=" * 78)


def section(title):
    print()
    print("-" * 78)
    print(title)
    print("-" * 78)


def main():
    line("🔬 DATASET AUDIT")
    print(f"Папка: {os.path.abspath(DATASET_DIR)}")
    print()

    # 1. Список файлов
    section("1. ФАЙЛЫ В dataset/")
    all_files = sorted(glob.glob(os.path.join(DATASET_DIR, "*")))
    if not all_files:
        print("❌ Папка пуста или не существует")
        return
    for f in all_files:
        size = os.path.getsize(f)
        print(f"  {os.path.basename(f):45} {size:>12} байт")

    # 2. Part-файлы
    part_files = sorted(glob.glob(os.path.join(DATASET_DIR, "real_dataset_part*.json")))
    section(f"2. PART-ФАЙЛЫ ({len(part_files)} шт.)")

    total_fights = 0
    per_file_info = []

    for pf in part_files:
        try:
            with open(pf, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  ❌ {os.path.basename(pf)}: ошибка чтения: {e}")
            continue

        n = len(data) if isinstance(data, list) else 0
        size = os.path.getsize(pf)
        total_fights += n
        per_file_info.append((pf, n, size))
        print(f"  {os.path.basename(pf):45} боёв: {n:>6}   {size:>12} байт")

    print(f"\n  ИТОГО боёв во всех part-файлах: {total_fights}")

    # 3. Структура первой, средней и последней записи
    section("3. СТРУКТУРА ЗАПИСЕЙ (первая / средняя / последняя)")

    for pf, n, _ in per_file_info:
        if n == 0:
            continue
        try:
            with open(pf, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        print(f"\n### {os.path.basename(pf)}")

        for label, idx in [("первая", 0), ("средняя", n // 2), ("последняя", n - 1)]:
            fight = data[idx]
            print(f"\n  [{label}] index={idx}")
            print(f"    верхний уровень: {sorted(fight.keys())}")

            sa = fight.get("stats_a", {})
            sb = fight.get("stats_b", {})

            print(f"    stats_a ключи:   {sorted(sa.keys()) if isinstance(sa, dict) else type(sa).__name__}")
            print(f"    stats_b ключи:   {sorted(sb.keys()) if isinstance(sb, dict) else type(sb).__name__}")

            print(f"    winner: {fight.get('winner')}")
            print(f"    date:   {fight.get('date')}")
            print(f"    fighter_a: {fight.get('fighter_a')}")
            print(f"    fighter_b: {fight.get('fighter_b')}")

            # ключевые поля
            print(f"    stats_a.exp        = {safe_get(sa, 'exp')}")
            print(f"    stats_a.fin_rate   = {safe_get(sa, 'fin_rate')}")
            print(f"    stats_a.wins       = {safe_get(sa, 'wins')}")
            print(f"    stats_a.losses     = {safe_get(sa, 'losses')}")
            print(f"    stats_a.dob        = {safe_get(sa, 'dob')}")
            print(f"    stats_a.dob_quality= {safe_get(sa, 'dob_quality')}")
            print(f"    stats_b.exp        = {safe_get(sb, 'exp')}")
            print(f"    stats_b.fin_rate   = {safe_get(sb, 'fin_rate')}")
            print(f"    stats_b.wins       = {safe_get(sb, 'wins')}")
            print(f"    stats_b.losses     = {safe_get(sb, 'losses')}")
            print(f"    stats_b.dob        = {safe_get(sb, 'dob')}")
            print(f"    stats_b.dob_quality= {safe_get(sb, 'dob_quality')}")

            print(f"    ai_factor   = {fight.get('ai_factor')}")
            print(f"    blind_conf  = {fight.get('blind_conf')}")

    # 4. Агрегированная статистика полей по всем файлам
    section("4. АГРЕГИРОВАННАЯ СТАТИСТИКА ПО ВСЕМ PART-ФАЙЛАМ")

    total = 0
    missing_fields_top = Counter()
    missing_fields_a = Counter()
    missing_fields_b = Counter()
    zero_exp = 0
    zero_fin = 0
    has_dob_a = 0
    has_dob_b = 0
    has_dob_quality_a = 0
    has_dob_quality_b = 0
    has_blind_conf = 0
    has_ai_factor = 0
    years = Counter()

    for pf, n, _ in per_file_info:
        try:
            with open(pf, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        for fight in data:
            total += 1

            # верхний уровень
            for k in ("fighter_a", "fighter_b", "winner", "date", "stats_a", "stats_b",
                      "ai_factor", "blind_conf", "round", "method", "odds_a", "odds_b"):
                if k not in fight:
                    missing_fields_top[k] += 1

            if "ai_factor" in fight:
                has_ai_factor += 1
            if "blind_conf" in fight:
                has_blind_conf += 1

            # date year
            d = fight.get("date")
            if isinstance(d, str) and len(d) >= 4:
                try:
                    years[d[:4]] += 1
                except Exception:
                    pass

            # stats_a
            sa = fight.get("stats_a", {})
            if isinstance(sa, dict):
                for k in ("age", "wins", "losses", "fin_rate", "sub_rate", "td_def", "grap_def",
                          "recent_wins", "months_off", "fights_12m", "stress_factor",
                          "motivation_index", "biorythm_score", "camp_quality", "camp_name",
                          "mystic_factor", "mystic_v2", "reach_cm", "height_cm", "exp",
                          "dob", "dob_quality"):
                    if k not in sa:
                        missing_fields_a[k] += 1
                if safe_get(sa, "exp") in (None, 0):
                    zero_exp += 1
                if safe_get(sa, "fin_rate") in (None, 0):
                    zero_fin += 1
                if safe_get(sa, "dob"):
                    has_dob_a += 1
                if safe_get(sa, "dob_quality") is not None:
                    has_dob_quality_a += 1

            # stats_b
            sb = fight.get("stats_b", {})
            if isinstance(sb, dict):
                for k in ("age", "wins", "losses", "fin_rate", "sub_rate", "td_def", "grap_def",
                          "recent_wins", "months_off", "fights_12m", "stress_factor",
                          "motivation_index", "biorythm_score", "camp_quality", "camp_name",
                          "mystic_factor", "mystic_v2", "reach_cm", "height_cm", "exp",
                          "dob", "dob_quality"):
                    if k not in sb:
                        missing_fields_b[k] += 1
                if safe_get(sb, "dob"):
                    has_dob_b += 1
                if safe_get(sb, "dob_quality") is not None:
                    has_dob_quality_b += 1

    print(f"  Всего боёв: {total}")
    print()

    print("  --- Пропущенные поля верхнего уровня ---")
    for k, v in missing_fields_top.most_common():
        print(f"    {k:20} отсутствует в {v:>6} боях ({v/total*100:.1f}%)")

    print()
    print("  --- Пропущенные поля в stats_a ---")
    for k, v in missing_fields_a.most_common():
        print(f"    {k:20} отсутствует в {v:>6} боях ({v/total*100:.1f}%)")

    print()
    print("  --- Пропущенные поля в stats_b ---")
    for k, v in missing_fields_b.most_common():
        print(f"    {k:20} отсутствует в {v:>6} боях ({v/total*100:.1f}%)")

    print()
    print(f"  --- Значения полей ---")
    print(f"    stats_a.exp == 0 или пусто:       {zero_exp:>6} ({zero_exp/total*100:.1f}%)")
    print(f"    stats_a.fin_rate == 0 или пусто:  {zero_fin:>6} ({zero_fin/total*100:.1f}%)")
    print(f"    stats_a.dob заполнен:             {has_dob_a:>6} ({has_dob_a/total*100:.1f}%)")
    print(f"    stats_b.dob заполнен:             {has_dob_b:>6} ({has_dob_b/total*100:.1f}%)")
    print(f"    stats_a.dob_quality заполнен:     {has_dob_quality_a:>6} ({has_dob_quality_a/total*100:.1f}%)")
    print(f"    stats_b.dob_quality заполнен:     {has_dob_quality_b:>6} ({has_dob_quality_b/total*100:.1f}%)")
    print(f"    ai_factor присутствует:           {has_ai_factor:>6} ({has_ai_factor/total*100:.1f}%)")
    print(f"    blind_conf присутствует:          {has_blind_conf:>6} ({has_blind_conf/total*100:.1f}%)")

    print()
    print("  --- Распределение боёв по годам ---")
    for y, c in sorted(years.items()):
        print(f"    {y}: {c:>6} ({c/total*100:.1f}%)")

    # 5. Проверка сходимости с ожиданиями модели
    section("5. ПРОВЕРКА СХОДИМОСТИ С make_fighter_from_dict")

    EXPECTED = {
        "name", "dob", "dob_quality", "flag", "wins", "losses", "recent_wins", "form",
        "fin_rate", "sub_rate", "td_def", "grap_def", "age", "exp", "months_off",
        "fights_12m", "reach_cm", "height_cm", "stress_factor", "motivation_index",
        "biorythm_score", "camp_quality", "camp_name", "mystic_factor", "mystic_v2",
        "verif"
    }

    print(f"  Ожидаемые поля Fighter: {len(EXPECTED)}")
    print()

    # какое из ожидаемых полей отсутствует в stats_a во всех файлах
    for f_name in sorted(EXPECTED):
        miss = missing_fields_a.get(f_name, 0)
        flag = "✅" if miss == 0 else ("⚠️" if miss < total * 0.1 else "❌")
        print(f"    {flag} {f_name:22} отсутствует: {miss:>6} ({miss/total*100:.1f}%)")

    print()
    print("  --- ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ В stats_a, которых НЕ ждёт Fighter ---")
    extra = set()
    for pf, n, _ in per_file_info:
        try:
            with open(pf, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for fight in data[:50]:
            sa = fight.get("stats_a", {})
            if isinstance(sa, dict):
                extra.update(sa.keys())
    for k in sorted(extra - EXPECTED):
        print(f"    + {k}")

    line("КОНЕЦ АУДИТА")


if __name__ == "__main__":
    main()