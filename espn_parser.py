#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESPN PARSER v1.0 | ЕДИНЫЙ ИСТОЧНИК ДЛЯ ПРОГНОЗА И БЭКТЕСТА
================================================================
Заменяет:
- sports_parser.py (для режима ПРОГНОЗ)
- ufc_parser.py (для режима 2b БЭКТЕСТ)
================================================================
"""
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


class ESPNParser:
    def __init__(self):
        self.cache = {}  # Кэш по датам

    def get_fights_by_date(self, target_date_str: str) -> List[Dict]:
        """
        Получает все бои на указанную дату из ESPN API.
        Работает и для будущих (ПРОГНОЗ), и для прошедших (БЭКТЕСТ) боёв.

        Args:
            target_date_str: Дата в формате "ДД.ММ.ГГГГ"

        Returns:
            List[Dict]: Список боёв с полной информацией
        """
        try:
            target_date = datetime.strptime(target_date_str, "%d.%m.%Y")
        except ValueError:
            print(f"   ❌ Неверный формат даты: {target_date_str}")
            return []

        # Проверяем кэш
        cache_key = target_date_str
        if cache_key in self.cache:
            print(f"   💾 Из кэша ESPN: {len(self.cache[cache_key])} боёв")
            return self.cache[cache_key]

        # Запрашиваем окно дат ±1 день (из-за часовых поясов)
        dates_to_query = []
        for delta in [-1, 0, 1]:
            query_date = target_date + timedelta(days=delta)
            dates_to_query.append(query_date.strftime("%Y%m%d"))

        all_fights = []

        for date_str in dates_to_query:
            url = f"{ESPN_BASE_URL}?dates={date_str}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                events = data.get('events', [])

                for event in events:
                    event_name = event.get('name', 'UFC Event')
                    event_date_str = event.get('date', '')

                    try:
                        event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                        # Конвертируем в локальное время и сравниваем только дату
                        event_date_local = event_date.astimezone(tz=None)
                        if event_date_local.date() != target_date.date():
                            continue
                    except Exception:
                        continue

                    competitions = event.get('competitions', [])

                    for comp in competitions:
                        competitors = comp.get('competitors', [])
                        if len(competitors) < 2:
                            continue

                        # Извлекаем данные бойцов
                        f1_data = competitors[0]
                        f2_data = competitors[1]

                        f1_name = f1_data.get('athlete', {}).get('fullName', 'Unknown')
                        f2_name = f2_data.get('athlete', {}).get('fullName', 'Unknown')

                        # Статус боя
                        status = comp.get('status', {})
                        status_type = status.get('type', {}).get('name', 'STATUS_SCHEDULED')
                        is_completed = status.get('type', {}).get('state', '') == 'post'

                        # Количество раундов
                        regulation = comp.get('format', {}).get('regulation', {})
                        rounds = regulation.get('periods', 3)

                        # Main event
                        is_main_event = comp.get('featured', False)

                        # Весовая категория
                        weight_class = comp.get('type', {}).get('abbreviation', '')

                        # Для прошедших боёв извлекаем результат
                        winner = None
                        method = 'TBD'
                        fact_round = rounds

                        if is_completed and status_type == 'STATUS_FINAL':
                            # Находим победителя
                            for comp_data in competitors:
                                if comp_data.get('winner'):
                                    winner = comp_data.get('athlete', {}).get('fullName')
                                    break

                            # Извлекаем метод из details
                            details = comp.get('details', [])
                            for detail in details:
                                detail_text = detail.get('type', {}).get('text', '')
                                if 'Submission' in detail_text:
                                    method = 'SUB'
                                    break
                                elif 'Kotko' in detail_text or 'KO' in detail_text:
                                    method = 'KO'
                                    break
                                elif 'Decision' in detail_text:
                                    # Проверяем UD или SD по linescores
                                    linescores = []
                                    for comp_data in competitors:
                                        ls = comp_data.get('linescores', [])
                                        if ls:
                                            linescores.append(ls)

                                    if len(linescores) == 2:
                                        # Проверяем, все ли судьи согласны
                                        scores_f1 = []
                                        scores_f2 = []
                                        for round_score in linescores[0]:
                                            if 'linescores' in round_score:
                                                for judge_score in round_score['linescores']:
                                                    scores_f1.append(judge_score.get('displayValue', ''))
                                        for round_score in linescores[1]:
                                            if 'linescores' in round_score:
                                                for judge_score in round_score['linescores']:
                                                    scores_f2.append(judge_score.get('displayValue', ''))

                                        # Если все три судьи дали одинаковый счёт - UD
                                        if len(scores_f1) == 3 and len(scores_f2) == 3:
                                            if scores_f1[0] == scores_f1[1] == scores_f1[2]:
                                                method = 'UD'
                                            else:
                                                method = 'SD'
                                        else:
                                            method = 'UD'
                                    else:
                                        method = 'UD'
                                    break

                            # Раунд, в котором закончился бой
                            fact_round = status.get('period', rounds)

                        fight_dict = {
                            'date': target_date,
                            'event_name': event_name,
                            'fighter1': f1_name,
                            'fighter2': f2_name,
                            'fighter_a': f1_name,   # ✅ для режима 2b
                            'fighter_b': f2_name,   # ✅ для режима 2b
                            'rounds': rounds,
                            'round': fact_round,    # ✅ реальный раунд для 2b
                            'fact_round': fact_round,
                            'is_main_event': is_main_event,
                            'winner': winner,
                            'method': method,
                        }

                        all_fights.append(fight_dict)

            except Exception as e:
                print(f"   ⚠️ Ошибка запроса ESPN для {date_str}: {e}")
                continue

        # Сохраняем в кэш
        self.cache[cache_key] = all_fights
        print(f"   ✅ ESPN API: найдено {len(all_fights)} боёв на {target_date_str}")

        return all_fights


# Тестовый запуск
if __name__ == "__main__":
    parser = ESPNParser()

    print("="*70)
    print("🧪 ТЕСТ ESPN PARSER")
    print("="*70)

    # Тест будущего события
    future_date = "29.08.2026"
    print(f"\n📅 Будущее событие: {future_date}")
    fights = parser.get_fights_by_date(future_date)
    for f in fights[:3]:
        print(f"   {f['fighter1']} vs {f['fighter2']} | Раундов: {f['rounds']} | ME: {f['is_main_event']}")

    # Тест прошедшего события
    past_date = "07.06.2026"
    print(f"\n📅 Прошедшее событие: {past_date}")
    fights = parser.get_fights_by_date(past_date)
    for f in fights[:3]:
        print(f"   {f['fighter1']} vs {f['fighter2']} | Победитель: {f['winner']} | Метод: {f['method']}")

    print("\n" + "="*70)
    print("✅ ESPN PARSER готов к использованию!")
    print("="*70)