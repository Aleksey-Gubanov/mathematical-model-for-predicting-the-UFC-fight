#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPORTS PARSER v49.0 | ПАРСЕР РАСПИСАНИЯ БУДУЩИХ БОЁВ (РЕЖИМ ПРОГНОЗ)
================================================================
ИСПРАВЛЕНИЯ v49.0:
1. ✅ Поиск боя через fighter_id (как в ufc_parser.py)
2. ✅ Получение canonical_name (кириллица) из fighters_ids.json
3. ✅ Сравнение canonical_name с именами на сайте (кириллица vs кириллица)
4. ✅ Все пути ТОЛЬКО в папке dataset/
================================================================
"""
import requests
from bs4 import BeautifulSoup
import re
import difflib
import os
import json
from typing import Optional, List, Dict

class SportsUFCScheduler:
    def __init__(self):
        self.base_url = "https://www.sports.ru/ufc/schedule/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        self._cache = None
        self._fighters_ids_cache = None

        # ✅ v49.0: Пути в папке dataset/
        self.DATASET_DIR = "dataset"
        self.FIGHTERS_IDS_FILE = os.path.join(self.DATASET_DIR, "fighters_ids.json")

    def _clean_name_for_match(self, name: str) -> str:
        """Очищает имя от рейтингов, мусора и приводит к нижнему регистру для сравнения"""
        if not name:
            return ""
        # Удаляем всё в скобках: (#1), (C), (W), (IC) и т.д.
        cleaned = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
        # Удаляем лишние пробелы и спецсимволы, приводим к нижнему регистру
        cleaned = re.sub(r'[^\w\sа-яёa-z]', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip().lower()

    # =========================================================================
    # ✅ v49.0: НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С fighter_id (как в ufc_parser.py)
    # =========================================================================

    def _load_fighters_ids_db(self) -> dict:
        """✅ v49.0: Загружает базу fighters_ids.json ИЗ ПАПКИ dataset/."""
        if self._fighters_ids_cache is not None:
            return self._fighters_ids_cache

        if not os.path.exists(self.FIGHTERS_IDS_FILE):
            self._fighters_ids_cache = {}
            return {}

        try:
            with open(self.FIGHTERS_IDS_FILE, 'r', encoding='utf-8') as f:
                self._fighters_ids_cache = json.load(f)
            return self._fighters_ids_cache
        except Exception as e:
            print(f"   ⚠️ Ошибка чтения {self.FIGHTERS_IDS_FILE}: {e}")
            self._fighters_ids_cache = {}
            return {}

    def _find_fighter_id(self, fighter_name: str, fighters_db: dict) -> Optional[str]:
        """✅ v49.0: Находит fighter_id по имени через нормализацию."""
        if not fighter_name or not fighters_db:
            return None

        norm_name = self._normalize_for_id(fighter_name)
        if not norm_name:
            return None

        # Сначала ищем по normalized
        for fid, data in fighters_db.items():
            if data.get("normalized") == norm_name:
                return fid

        # Потом ищем по aliases
        for fid, data in fighters_db.items():
            for alias in data.get("aliases", []):
                if self._normalize_for_id(alias) == norm_name:
                    return fid

        return None

    def _normalize_for_id(self, name: str) -> str:
        """✅ v49.0: Нормализация для fighter_id (кириллица + латиница → единый формат)."""
        if not name:
            return ""
        # Транслитерация кириллицы в латиницу
        TRANS_TABLE = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }

        result = []
        for ch in name.lower():
            if ch in TRANS_TABLE:
                result.append(TRANS_TABLE[ch])
            else:
                result.append(ch)
        latin = ''.join(result)

        # Удаляем всё, кроме букв и цифр
        return re.sub(r'[^a-z0-9]', '', latin)

    def _get_canonical_name(self, fighter_id: str, fighters_db: dict) -> Optional[str]:
        """✅ v49.0: Получает canonical_name (кириллическое имя) по fighter_id."""
        if not fighter_id or not fighters_db:
            return None

        data = fighters_db.get(fighter_id)
        if not data:
            return None

        # Возвращаем canonical_name (кириллица)
        canonical = data.get("canonical_name")
        if canonical:
            return canonical

        # Если canonical_name нет — возвращаем первый alias на кириллице
        for alias in data.get("aliases", []):
            if re.search(r'[а-яё]', alias, re.IGNORECASE):
                return alias

        # Если ничего не нашли — возвращаем normalized
        return data.get("normalized", "")

    def parse_schedule(self) -> List[Dict]:
        """Парсит расписание будущих боев. Использует кэш для экономии запросов."""
        if self._cache is not None:
            return self._cache

        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Ошибка сети при парсинге sports.ru: {e}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        fights = []

        months = {
            'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
            'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
            'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
        }

        # Ищем все заголовки турниров (h2)
        for h2 in soup.find_all('h2'):
            h2_text = h2.get_text(strip=True)

            # Проверяем, что это заголовок турнира UFC
            if "UFC" not in h2_text.upper():
                continue

            # Извлекаем название турнира и дату из заголовка
            current_event = h2_text.split(',')[0].strip()
            date_match = re.search(r'(\d{1,2}\s+[а-яё]+\s+\d{4}|\d{2}\.\d{2}\.\d{4})', h2_text, re.I)

            if date_match:
                date_str = date_match.group(1)
                if '.' in date_str:
                    current_date = date_str
                else:
                    parts = date_str.split()
                    if len(parts) == 3:
                        day = parts[0].zfill(2)
                        month = months.get(parts[1].lower(), '01')
                        year = parts[2]
                        current_date = f"{day}.{month}.{year}"
                    else:
                        current_date = "Неизвестная дата"
            else:
                current_date = "Неизвестная дата"

            # Находим таблицу, следующую сразу за этим h2
            table = h2.find_next_sibling('table')
            if not table:
                continue

            tbody = table.find('tbody')
            if not tbody:
                continue

            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 3:
                    f1_raw = tds[1].get_text(strip=True)
                    f2_raw = tds[2].get_text(strip=True)

                    if not f1_raw or not f2_raw:
                        continue

                    # Определяем количество раундов: ME (Main Event) = 5 раундов, остальные = 3
                    status = tds[0].get_text(strip=True)
                    rounds = 5 if status.upper() == 'ME' else 3

                    fights.append({
                        "event_name": current_event,
                        "event_date": current_date,
                        "fighter1": f1_raw,
                        "fighter2": f2_raw,
                        "rounds": rounds,
                        "is_main_event": (status.upper() == 'ME'),
                        "location": "UFC"
                    })

        # Удаляем дубликаты
        unique_fights = []
        seen = set()
        for f in fights:
            key = (self._clean_name_for_match(f['fighter1']), self._clean_name_for_match(f['fighter2']))
            if key not in seen:
                seen.add(key)
                unique_fights.append(f)

        self._cache = unique_fights
        return unique_fights

    def find_fight(self, fighter1: str, fighter2: str) -> Optional[Dict]:
        """
        ✅ v49.0: Ищет бой через fighter_id (как в ufc_parser.py).

        Логика:
        1. Получаем fighter_id для обоих бойцов
        2. Получаем canonical_name (кириллицу) для обоих бойцов
        3. Сравниваем canonical_name с именами на сайте (кириллица vs кириллица)
        4. Если нашли — возвращаем данные боя
        """
        schedule = self.parse_schedule()
        if not schedule:
            return None

        # ✅ v49.0: Загружаем fighters_ids.json
        fighters_db = self._load_fighters_ids_db()

        # ✅ v49.0: Получаем fighter_id для обоих бойцов
        id1 = self._find_fighter_id(fighter1, fighters_db)
        id2 = self._find_fighter_id(fighter2, fighters_db)

        # ✅ v49.0: Получаем canonical_name (кириллицу)
        canonical1 = self._get_canonical_name(id1, fighters_db) if id1 else fighter1
        canonical2 = self._get_canonical_name(id2, fighters_db) if id2 else fighter2

        print(f"   🆔 fighter_id: {fighter1}={id1}, {fighter2}={id2}")
        print(f"   📝 canonical_name: '{canonical1}' vs '{canonical2}'")

        # ✅ v49.0: Очищаем canonical_name для сравнения
        clean_canonical1 = self._clean_name_for_match(canonical1)
        clean_canonical2 = self._clean_name_for_match(canonical2)

        for fight in schedule:
            db_f1 = self._clean_name_for_match(fight['fighter1'])
            db_f2 = self._clean_name_for_match(fight['fighter2'])

            # ✅ v49.0: Сравниваем canonical_name (кириллица vs кириллица)
            # Прямое совпадение
            match_1 = difflib.SequenceMatcher(None, clean_canonical1, db_f1).ratio() >= 0.80
            match_2 = difflib.SequenceMatcher(None, clean_canonical2, db_f2).ratio() >= 0.80

            # Обратное совпадение
            match_reverse_1 = difflib.SequenceMatcher(None, clean_canonical1, db_f2).ratio() >= 0.80
            match_reverse_2 = difflib.SequenceMatcher(None, clean_canonical2, db_f1).ratio() >= 0.80

            if (match_1 and match_2) or (match_reverse_1 and match_reverse_2):
                return fight

        return None