#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UFC PARSER v48.2 | УМНЫЙ ПОИСК + ДИНАМИЧЕСКАЯ ЗАЩИТА ОТ ПРОГНОЗОВ
================================================================
ИСПРАВЛЕНИЯ v48.2 (КРИТИЧНО — ГЛОБАЛЬНАЯ ОШИБКА ДАТЫ):
- ✅ УДАЛЕНА жёсткая MODEL_CREATION_DATE = 01.03.2026
- ✅ ДОБАВЛЕНА динамическая граница: datetime.now() - 3 дня
- ✅ FACT_BUFFER_DAYS = 3 (буфер на обновление сайта)
- ✅ Бои до (сегодня - 3 дня) = ФАКТЫ (сохраняются)
- ✅ Бои после (сегодня - 3 дня) = ПРОГНОЗЫ (отклоняются)
- ✅ Все пути ТОЛЬКО в папке dataset/
================================================================
"""
import re
import os
import json
import glob
import requests
import difflib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

# Попытка импортировать библиотеку транслитерации
try:
    from transliterate import translit
    HAS_TRANSLIT = True
except ImportError:
    HAS_TRANSLIT = False
    TRANS_TABLE = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    def _simple_translit(text: str) -> str:
        """Простая транслитерация кириллицы в латиницу."""
        result = []
        for ch in text.lower():
            if ch in TRANS_TABLE:
                result.append(TRANS_TABLE[ch])
            else:
                result.append(ch)
        return ''.join(result)


class UFCParser:
    SOURCES = {
        2022: ["https://www.championat.com/boxing/_ufc/tournament/677/calendar/"],
        2023: ["https://www.championat.com/boxing/_ufc/tournament/735/calendar/"],
        2024: ["https://www.championat.com/boxing/_ufc/tournament/822/calendar/"],
        2025: ["https://www.championat.com/boxing/_ufc/tournament/896/calendar/"],
        2026: ["https://www.championat.com/boxing/_ufc/tournament/1038/calendar/"]
    }

    # ✅ v48.2: КРИТИЧНО — ВСЕ ФАЙЛЫ ТОЛЬКО В dataset/
    DATASET_DIR = "dataset"
    CACHE_FILE = os.path.join(DATASET_DIR, "ufc_history_cache.json")
    FIGHTERS_IDS_FILE = os.path.join(DATASET_DIR, "fighters_ids.json")
    REAL_DATASET_FILE = os.path.join(DATASET_DIR, "real_dataset.json")

    # ✅ v48.2: КРИТИЧНО — ДИНАМИЧЕСКАЯ ГРАНИЦА!
    # Бои до (сегодня - FACT_BUFFER_DAYS) = ФАКТЫ
    # Бои после (сегодня - FACT_BUFFER_DAYS) = ПРОГНОЗЫ
    FACT_BUFFER_DAYS = 3

    def __init__(self, similarity_threshold: float = 0.85):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        self.threshold = similarity_threshold
        self.history: List[Dict] = []
        self._load_and_clean_cache()
        self._fallback_cache: Dict[Tuple[str, str], Dict] = {}
        self._fighters_ids_cache: Optional[Dict] = None

    # =========================================================================
    # ✅ v48.2: ДИНАМИЧЕСКАЯ ГРАНИЦА ФАКТОВ
    # =========================================================================
    def _get_fact_threshold(self) -> datetime:
        """
        ✅ v48.2: Возвращает динамическую границу между фактами и прогнозами.
        Формула: datetime.now() - FACT_BUFFER_DAYS

        Сегодня: 03.07.2026
        FACT_BUFFER_DAYS = 3
        Граница: 30.06.2026

        Бои до 30.06.2026 → ФАКТЫ ✅
        Бои после 30.06.2026 → ПРОГНОЗЫ ❌
        """
        return datetime.now() - timedelta(days=self.FACT_BUFFER_DAYS)

    # ---------- ТРАНСЛИТЕРАЦИЯ ----------
    def _transliterate(self, text: str) -> str:
        """Приводит имя к единому алфавиту (латиница) для сравнения."""
        if not text:
            return ""
        if re.search(r'[а-яё]', text, re.IGNORECASE):
            if HAS_TRANSLIT:
                return translit(text, 'ru', reversed=True).lower()
            else:
                return _simple_translit(text)
        else:
            return text.lower()

    def _normalize(self, name: str) -> str:
        """Полная нормализация: транслитерация + удаление всего, кроме букв и цифр."""
        if not name:
            return ""
        latin = self._transliterate(name)
        normalized = re.sub(r'[^a-z0-9]', '', latin)
        return normalized

    # ---------- СРАВНЕНИЕ ИМЁН ----------

    def _names_match(self, name1: str, name2: str) -> bool:
        """Сравнивает два имени с учётом транслитерации и порога."""
        n1 = self._normalize(name1)
        n2 = self._normalize(name2)
        if not n1 or not n2:
            return False
        if n1 == n2:
            return True
        # ✅ ИСПРАВЛЕНО: Убран оператор in (давал ложные срабатывания)
        ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
        return ratio >= self.threshold

    # ---------- ОЧИСТКА ИМЁН ОТ МУСОРА ----------
    def _clean_fighter_name(self, raw_name: str) -> str:
        """Очищает имя от прилипших методов боя и скобок."""
        if not raw_name:
            return ""
        name = str(raw_name)
        name = re.sub(r'\(.*?\)', '', name)
        name = re.sub(r'\([^)]*$', '', name)
        methods = ['TKO', 'KO', 'SUB', 'UD', 'SD', 'MD', 'NC', 'DSQ', 'DRAW', 'DEC', 'TSD', 'TSUB', 'UTD']
        for method in methods:
            name = re.sub(r'\s+' + method + r'\s*$', '', name, flags=re.IGNORECASE)
            name = re.sub(method + r'\s*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'[^\w\sа-яёА-ЯЁa-zA-Z\-]+$', '', name).strip()
        return name

    # ---------- ЗАГРУЗКА / СОХРАНЕНИЕ КЭША ----------
    def _load_and_clean_cache(self) -> None:
        """Загружает кэш, очищает имена и обновляет self.history."""
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    raw_history = json.load(f)
                for fight in raw_history:
                    fight['fighter_a'] = self._clean_fighter_name(fight.get('fighter_a', ''))
                    fight['fighter_b'] = self._clean_fighter_name(fight.get('fighter_b', ''))
                    fight['winner'] = self._clean_fighter_name(fight.get('winner', ''))
                self.history = raw_history
                print(f"   ✅ История загружена и очищена ({len(self.history)} боев).")
                return
            except Exception as e:
                print(f"   ⚠️ Ошибка чтения кэша: {e}")
        self.history = self._build_cache()
        self._save_cache()

    def _save_cache(self) -> None:
        """Сохраняет текущую историю в файл."""
        try:
            os.makedirs(self.DATASET_DIR, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            print(f"   ✅ Кэш сохранён ({len(self.history)} боев).")
        except Exception as e:
            print(f"   ⚠️ Не удалось сохранить кэш: {e}")

    # ---------- v48.2: ОЧИСТКА КЭША ОТ ПРОГНОЗОВ (ДИНАМИЧЕСКАЯ) ----------
    def clean_cache_from_predictions(self) -> int:
        """
        ✅ v48.2: Удаляет все бои с датой > (сегодня - FACT_BUFFER_DAYS) из кэша.
        Возвращает количество удалённых боёв.
        """
        threshold = self._get_fact_threshold()
        print(f"   🧹 Очистка кэша от прогнозов (дата > {threshold.strftime('%d.%m.%Y')})...")

        original_count = len(self.history)
        cleaned_history = []

        for fight in self.history:
            date_str = fight.get("date", "")
            try:
                if "-" in str(date_str) and len(str(date_str)) == 10:
                    fight_date = datetime.strptime(str(date_str), "%Y-%m-%d")
                else:
                    fight_date = datetime.strptime(str(date_str), "%d.%m.%Y")

                # ✅ v48.2: Оставляем только бои до динамической границы
                if fight_date <= threshold:
                    cleaned_history.append(fight)
            except Exception:
                continue

        removed_count = original_count - len(cleaned_history)
        self.history = cleaned_history
        self._save_cache()

        print(f"   ✅ Удалено прогнозов: {removed_count}")
        print(f"   ✅ Осталось реальных фактов: {len(self.history)}")

        return removed_count

    # ---------- ПАРСИНГ САЙТА (построение кэша) ----------
    def _build_cache(self) -> List[Dict]:
        """Первичный парсинг всех источников для создания кэша."""
        print("   ⏳ Первый запуск: парсинг истории боев с championat.com...")
        all_fights = []
        for year, urls in self.SOURCES.items():
            for url in urls:
                try:
                    resp = requests.get(url, headers=self.headers, timeout=15)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, 'lxml')
                    tables = soup.find_all('table', class_=re.compile(r'calendar|schedule|b-table', re.I))
                    if not tables:
                        tables = soup.find_all('table')
                    for table in tables:
                        for row in table.find_all('tr'):
                            cells = row.find_all('td')
                            if len(cells) < 3:
                                continue
                            date_str = ""
                            for cell in cells:
                                m = re.search(r'(\d{2}\.\d{2}\.\d{4})', cell.get_text())
                                if m:
                                    date_str = m.group(1)
                                    break
                            if not date_str:
                                continue
                            try:
                                fight_date = datetime.strptime(date_str, "%d.%m.%Y")
                            except ValueError:
                                continue
                            if fight_date > datetime.now():
                                continue

                            tournament = self._extract_tournament(soup, cells, url)
                            fight_info = self._extract_fight_cell(row)
                            if not fight_info:
                                continue
                            parsed = self._parse_fight_universal(fight_info)
                            if not parsed:
                                continue

                            all_fights.append({
                                'date': date_str,
                                'event': tournament,
                                'fighter_a': self._clean_fighter_name(parsed['fighter_a']),
                                'fighter_b': self._clean_fighter_name(parsed['fighter_b']),
                                'winner': self._clean_fighter_name(parsed['winner']),
                                'method': parsed['method'],
                                'round': parsed['round']
                            })
                except Exception as e:
                    print(f"   ⚠️ Ошибка при парсинге {url}: {e}")
                    continue
        return all_fights

    # ---------- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ ПАРСИНГА ----------
    def _extract_tournament(self, soup: BeautifulSoup, cells: List, url: str) -> str:
        if len(cells) > 1:
            cell1_text = cells[1].get_text(strip=True)
            if cell1_text and len(cell1_text) > 3:
                return cell1_text
        h1 = soup.find('h1')
        if h1:
            h1_text = h1.get_text(strip=True)
            if h1_text and len(h1_text) > 3:
                return h1_text
        url_match = re.search(r'/tournament/(\d+)/', url)
        if url_match:
            return f"UFC Tournament {url_match.group(1)}"
        return "UFC"

    def _extract_fight_cell(self, row) -> Optional[str]:
        for cell in row.find_all('td'):
            text = cell.get_text(strip=True)
            if re.search(r'[-–—]|vs\.|\s+\w+\s+\w+\s+\(W\)|\(L\)', text, re.IGNORECASE):
                return text
        cells = row.find_all('td')
        if len(cells) >= 6:
            return cells[5].get_text(strip=True)
        return None

    def _parse_fight_universal(self, fight_info: str) -> Optional[Dict]:
        if not fight_info:
            return None
        sep = None
        for s in [' - ', ' — ', ' vs ', ' VS ']:
            if s in fight_info:
                sep = s
                break
        if not sep:
            return None

        parts = fight_info.split(sep)
        if len(parts) != 2:
            return None

        raw_f1, raw_f2 = parts[0].strip(), parts[1].strip()
        combined_text = (raw_f1 + " " + raw_f2).upper()

        def clean_part(raw: str):
            is_winner = '(W)' in raw.upper()
            is_loser = '(L)' in raw.upper()
            clean = re.sub(r'\s*\([WL]\)\s*', ' ', raw, flags=re.IGNORECASE)
            return clean.strip(), is_winner, is_loser

        f1, w1, l1 = clean_part(raw_f1)
        f2, w2, l2 = clean_part(raw_f2)
        if not f1 or not f2:
            return None

        if w1:
            winner = f1
        elif w2:
            winner = f2
        elif l1:
            winner = f2
        elif l2:
            winner = f1
        else:
            winner = f2

        method = "DEC"
        round_num = 3
        round_match = re.search(r'(?:R|РАУНД\s*|раунд\s*)(\d)', combined_text)
        if round_match:
            round_num = int(round_match.group(1))

        for m in ['TKO', 'KO', 'SUB', 'UD', 'SD', 'MD', 'DRAW', 'NC']:
            if m in combined_text:
                method = m

                break

        return {'fighter_a': f1, 'fighter_b': f2, 'winner': winner, 'method': method, 'round': round_num}

    # ---------- FALLBACK НА САЙТ ----------
    def _parse_from_website(self, fighter_a: str, fighter_b: str) -> Optional[Dict]:
        """FALLBACK: прямой парсинг championat.com."""
        print("   🌐 Fallback: парсинг сайта championat.com...")
        key = (self._normalize(fighter_a), self._normalize(fighter_b))
        if key in self._fallback_cache:
            print("   💾 Результат взят из fallback-кэша.")
            return self._fallback_cache[key]

        fighters_db = self._load_fighters_ids_db()
        id_a = self._find_fighter_id(fighter_a, fighters_db)
        id_b = self._find_fighter_id(fighter_b, fighters_db)

        # ✅ v48.2: Динамическая граница
        fact_threshold = self._get_fact_threshold()

        for year in [2026, 2025, 2024, 2023, 2022]:
            for url in self.SOURCES.get(year, []):
                try:
                    resp = requests.get(url, headers=self.headers, timeout=10)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, 'lxml')
                    tables = soup.find_all('table', class_=re.compile(r'calendar|schedule|b-table', re.I))
                    if not tables:
                        tables = soup.find_all('table')
                    for table in tables:
                        for row in table.find_all('tr'):
                            cells = row.find_all('td')
                            if len(cells) < 3:
                                continue
                            date_str = ""
                            for cell in cells:
                                m = re.search(r'(\d{2}\.\d{2}\.\d{4})', cell.get_text())
                                if m:
                                    date_str = m.group(1)
                                    break
                            if not date_str:
                                continue

                            fight_info = self._extract_fight_cell(row)
                            if not fight_info:
                                continue
                            parsed = self._parse_fight_universal(fight_info)
                            if not parsed:
                                continue

                            if (self._names_match(fighter_a, parsed['fighter_a']) and
                                self._names_match(fighter_b, parsed['fighter_b'])) or \
                                    (self._names_match(fighter_a, parsed['fighter_b']) and
                                     self._names_match(fighter_b, parsed['fighter_a'])):
                                try:
                                    fight_date = datetime.strptime(date_str, "%d.%m.%Y")
                                except:
                                    continue
                                if fight_date > datetime.now():
                                    continue

                                # ✅ v48.2: КРИТИЧНО — проверка динамической границы!
                                if fight_date > fact_threshold:
                                    print(f"   ⚠️ Бой после динамической границы ({fact_threshold.strftime('%d.%m.%Y')}) — пропущен (прогноз)")
                                    continue

                                result = {
                                    'date': fight_date,
                                    'winner': self._clean_fighter_name(parsed['winner']),
                                    'method': parsed['method'],
                                    'round': parsed['round'],
                                    'tournament': f"UFC {year}"
                                }

                                if id_a:
                                    result['fighter_a_id'] = id_a
                                if id_b:
                                    result['fighter_b_id'] = id_b

                                self._fallback_cache[key] = result
                                self._add_to_cache(fighter_a, fighter_b, result, date_str, parsed)
                                return result
                except Exception as e:
                    print(f"   ⚠️ Ошибка при парсинге {url}: {e}")
                    continue
        return None

    def _add_to_cache(self, fighter_a: str, fighter_b: str, result: Dict, date_str: str, parsed: Dict) -> None:
        """Добавляет найденный через fallback бой в основной кэш."""
        # ✅ v48.2: КРИТИЧНО — проверка даты перед добавлением!
        try:
            if "-" in str(date_str) and len(str(date_str)) == 10:
                fight_date = datetime.strptime(str(date_str), "%Y-%m-%d")
            else:
                fight_date = datetime.strptime(str(date_str), "%d.%m.%Y")

            fact_threshold = self._get_fact_threshold()
            if fight_date > fact_threshold:
                print(f"   ⚠️ Отказ от сохранения: бой после {fact_threshold.strftime('%d.%m.%Y')} (прогноз)")
                return
        except Exception:
            pass

        for fight in self.history:
            if (self._names_match(fighter_a, fight['fighter_a']) and
                self._names_match(fighter_b, fight['fighter_b'])) or \
                    (self._names_match(fighter_a, fight['fighter_b']) and
                     self._names_match(fighter_b, fight['fighter_a'])):
                return
        new_entry = {
            'date': date_str,
            'event': result.get('tournament', 'UFC'),
            'fighter_a': self._clean_fighter_name(parsed['fighter_a']),
            'fighter_b': self._clean_fighter_name(parsed['fighter_b']),
            'winner': self._clean_fighter_name(result['winner']),
            'method': result['method'],
            'round': result['round']
        }

        if 'fighter_a_id' in result:
            new_entry['fighter_a_id'] = result['fighter_a_id']
        if 'fighter_b_id' in result:
            new_entry['fighter_b_id'] = result['fighter_b_id']

        self.history.append(new_entry)
        self._save_cache()
        print(f"   ➕ Бой добавлен в кэш.")

    # ---------- v48.2: НОВЫЕ МЕТОДЫ ДЛЯ СИСТЕМЫ ID (ПУТИ В dataset/) ----------
    def _load_fighters_ids_db(self) -> dict:
        """✅ v48.2: Загружает базу fighters_ids.json ИЗ ПАПКИ dataset/."""
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
        """Находит fighter_id по имени через нормализацию."""
        if not fighter_name or not fighters_db:
            return None

        norm_name = self._normalize(fighter_name)
        if not norm_name:
            return None

        for fid, data in fighters_db.items():
            if data.get("normalized") == norm_name:
                return fid

        for fid, data in fighters_db.items():
            for alias in data.get("aliases", []):
                if self._normalize(alias) == norm_name:
                    return fid

        return None

    def _search_by_fighter_ids(self, fighter_a: str, fighter_b: str) -> Optional[Dict]:
        """
        ✅ v48.2: Поиск боя по fighter_id — ТОЛЬКО В ПАПКЕ dataset/!
        ✅ v48.2: Динамическая проверка даты — не возвращать прогнозы!
        """
        fighters_db = self._load_fighters_ids_db()
        if not fighters_db:
            return None

        id_a = self._find_fighter_id(fighter_a, fighters_db)
        id_b = self._find_fighter_id(fighter_b, fighters_db)

        if not id_a or not id_b:
            return None

        print(f"   🆔 Поиск по ID: {fighter_a}={id_a}, {fighter_b}={id_b}")

        # ✅ v48.2: Ищем ТОЛЬКО в папке dataset/
        files_to_check = []
        files_to_check.extend(sorted(glob.glob(os.path.join(self.DATASET_DIR, "real_dataset_part*.json"))))
        if os.path.exists(self.REAL_DATASET_FILE):
            files_to_check.append(self.REAL_DATASET_FILE)
        if os.path.exists(self.CACHE_FILE):
            files_to_check.append(self.CACHE_FILE)

        for filepath in files_to_check:
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    dataset = json.load(f)
                for fight in dataset:
                    fa_id = fight.get("fighter_a_id")
                    fb_id = fight.get("fighter_b_id")

                    if fa_id == id_a and fb_id == id_b:
                        result = self._format_fight_result(fight)
                        if result is None:
                            continue  # ✅ v48.2: Пропускаем прогнозы
                        print(f"   ✅ Найдено по ID (прямое) в {filepath}")
                        return result

                    if fa_id == id_b and fb_id == id_a:
                        result = self._format_fight_result(fight)
                        if result is None:
                            continue  # ✅ v48.2: Пропускаем прогнозы
                        print(f"   ✅ Найдено по ID (обратное) в {filepath}")
                        return result
            except Exception as e:
                print(f"   ⚠️ Ошибка чтения {filepath}: {e}")
                continue

        return None

    # ---------- v48.2: УМНЫЙ ПОИСК (ПУТИ В dataset/) ----------
    def _load_all_fights(self) -> List[Dict]:
        """✅ v48.2: Загружает ВСЕ бои ТОЛЬКО из папки dataset/."""
        all_fights = []
        all_fights.extend(self.history)

        for filename in sorted(glob.glob(os.path.join(self.DATASET_DIR, "real_dataset_part*.json"))):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    dataset = json.load(f)
                all_fights.extend(dataset)
            except Exception as e:
                print(f"   ⚠️ Ошибка чтения {filename}: {e}")

        if os.path.exists(self.REAL_DATASET_FILE):
            try:
                with open(self.REAL_DATASET_FILE, 'r', encoding='utf-8') as f:
                    dataset = json.load(f)
                all_fights.extend(dataset)
            except Exception as e:
                print(f"   ⚠️ Ошибка чтения {self.REAL_DATASET_FILE}: {e}")

        return all_fights

    def _search_with_smart_logic(self, all_fights: List[Dict], fighter_a: str, fighter_b: str) -> Optional[Dict]:
        """
        Умная логика поиска:
        - Если fighter_a найден с 100% совпадением → ищем fighter_b среди его соперников (мягко)
        - Если fighter_b найден с 100% совпадением → ищем fighter_a среди его соперников (мягко)
        ✅ v48.2: Динамическая проверка даты — не возвращать прогнозы!
        """
        THRESHOLD_100 = 0.95
        THRESHOLD_SOFT = 0.70

        print(f"   🧠 Умный поиск: {fighter_a} vs {fighter_b}")

        norm_a_input = self._normalize(fighter_a)
        norm_b_input = self._normalize(fighter_b)

        for fight in all_fights:
            fa = fight.get("fighter_a", "")
            fb = fight.get("fighter_b", "")

            norm_fa = self._normalize(fa)
            norm_fb = self._normalize(fb)

            score_a_fa = difflib.SequenceMatcher(None, norm_a_input, norm_fa).ratio()
            score_a_fb = difflib.SequenceMatcher(None, norm_a_input, norm_fb).ratio()
            score_b_fa = difflib.SequenceMatcher(None, norm_b_input, norm_fa).ratio()
            score_b_fb = difflib.SequenceMatcher(None, norm_b_input, norm_fb).ratio()

            if score_a_fa >= THRESHOLD_100 and score_b_fb >= THRESHOLD_SOFT:
                result = self._format_fight_result(fight)
                if result is None:
                    continue
                print(f"   ✅ Найдено (A=100%, B=мягко): {fa} vs {fb}")
                return result

            if score_a_fb >= THRESHOLD_100 and score_b_fa >= THRESHOLD_SOFT:
                result = self._format_fight_result(fight)
                if result is None:
                    continue
                print(f"   ✅ Найдено (A=100%, B=мягко, обратный): {fb} vs {fa}")
                return result

            if score_b_fb >= THRESHOLD_100 and score_a_fa >= THRESHOLD_SOFT:
                result = self._format_fight_result(fight)
                if result is None:
                    continue
                print(f"   ✅ Найдено (B=100%, A=мягко): {fa} vs {fb}")
                return result

            if score_b_fa >= THRESHOLD_100 and score_a_fb >= THRESHOLD_SOFT:
                result = self._format_fight_result(fight)
                if result is None:
                    continue
                print(f"   ✅ Найдено (B=100%, A=мягко, обратный): {fb} vs {fa}")
                return result

        return None

    def _search_with_old_logic(self, all_fights: List[Dict], fighter_a: str, fighter_b: str) -> Optional[Dict]:
        """Старая логика поиска (fallback).
        ✅ v48.2: Динамическая проверка даты — не возвращать прогнозы!
        """
        for fight in all_fights:
            fa = fight.get("fighter_a", "")
            fb = fight.get("fighter_b", "")

            if (self._names_match(fighter_a, fa) and self._names_match(fighter_b, fb)) or \
                    (self._names_match(fighter_a, fb) and self._names_match(fighter_b, fa)):
                result = self._format_fight_result(fight)
                if result is None:
                    continue
                print(f"   ✅ Найдено (старая логика): {fa} vs {fb}")
                return result

        return None

    def _format_fight_result(self, fight: Dict) -> Optional[Dict]:
        """
        Форматирует результат боя в единый формат.
        ✅ v48.2: Возвращает None, если дата > (сегодня - FACT_BUFFER_DAYS) — защита от прогнозов!
        """
        date_str = fight.get("date", "")
        try:
            if "-" in str(date_str) and len(str(date_str)) == 10:
                fight_date = datetime.strptime(str(date_str), "%Y-%m-%d")
            else:
                fight_date = datetime.strptime(str(date_str), "%d.%m.%Y")
        except ValueError:
            return None

        # ✅ v48.2: КРИТИЧНО — динамическая защита от прогнозов!
        fact_threshold = self._get_fact_threshold()
        if fight_date > fact_threshold:
            return None  # Это прогноз, не использовать для обучения!

        result = {
            "date": fight_date,
            "event": fight.get("event", "UFC"),
            "fighter_a": fight.get("fighter_a", "Unknown"),
            "fighter_b": fight.get("fighter_b", "Unknown"),
            "winner": fight.get("winner", "Unknown"),
            "method": fight.get("method", "DEC"),
            "round": int(fight.get("round", 3))
        }

        if "fighter_a_id" in fight:
            result["fighter_a_id"] = fight["fighter_a_id"]
        if "fighter_b_id" in fight:
            result["fighter_b_id"] = fight["fighter_b_id"]

        return result

    # ---------- ПУБЛИЧНЫЕ МЕТОДЫ ----------
    def get_all_known_fighters(self) -> List[str]:
        """Возвращает список всех уникальных очищенных имён."""
        fighters = set()
        for fight in self.history:
            fa = fight.get('fighter_a', '')
            fb = fight.get('fighter_b', '')
            if fa and len(fa) > 2:
                fighters.add(fa)
            if fb and len(fb) > 2:
                fighters.add(fb)
        return list(fighters)

    def _query_ai_fallback(self, fighter_a: str, fighter_b: str, known_date: str) -> Optional[Dict]:
        """
        ✅ v48.3: Последовательный запрос к ИИ: DeepSeek → YandexGPT.
        ЖЕСТКИЙ ЗАПРЕТ НА ГАЛЛЮЦИНАЦИИ: если ИИ не знает точного результата, он обязан вернуть null.
        """
        prompt = f"""Ты эксперт по ММА. Дай ТОЧНЫЙ исторический результат боя:
Бойцы: {fighter_a} vs {fighter_b}
Дата боя: {known_date}

Верни СТРОГО JSON:
{{"winner": "Имя победителя (точно как в запросе)", "method": "KO/TKO/SUB/UD/SD/MD/DEC", "round": число}}

КРИТИЧЕСКИ ВАЖНО: 
1. Если этот бой еще не состоялся или дата позже твоей даты обучения — верни СТРОГО null.
2. Если ты не знаешь ТОЧНЫЙ результат этого конкретного боя — верни СТРОГО null.
3. НЕ ВЫДУМЫВАЙ результат. Любая галлюцинация недопустима."""

        # 1. Пробуем DeepSeek
        try:
            from secure_neural_channel import SecureNeuralChannel
            # Проверяем инициализацию более надежно
            if hasattr(SecureNeuralChannel, 'query'):
                response = SecureNeuralChannel.query(prompt, "Верни СТРОГО JSON или null.", use_cache=False)
                if isinstance(response, dict) and response.get("winner"):
                    print("   ✅ Результат получен от DeepSeek")
                    return response
        except Exception as e:
            pass # Тихо переходим к следующему этапу

        # 2. Пробуем YandexGPT (если клиент инициализирован глобально или передан)
        try:
            from yandex_gpt_client import YandexGPTClient
            # Пытаемся создать временный клиент (предполагая, что ключи в SecureKeys)
            # Если у вас есть глобальный экземпляр, используйте его вместо создания нового
            temp_client = YandexGPTClient(master_password="5Tgfder%$") # Замените на реальный способ получения пароля, если нужно
            if temp_client.api_key:
                response = temp_client.query(prompt, max_tokens=150, temperature=0.1, model="yandexgpt-5.1", expect_json=True)
                if isinstance(response, dict) and response.get("winner"):
                    print("   ✅ Результат получен от YandexGPT")
                    return response
        except Exception as e:
            pass # Тихо переходим к парсингу сайта

        return None

    def get_fight_result(self, fighter_a: str, fighter_b: str, known_date: str = None) -> Optional[Dict]:
        """
        ✅ v48.3: ПОСЛЕДОВАТЕЛЬНЫЙ ПОИСК (4 ЭТАПА)
        1. Свой локальный кэш (самый быстрый и 100% точный)
        2. Запрос к DeepSeek (с жестким запретом на галлюцинации)
        3. Запрос к YandexGPT (резервный ИИ)
        4. Парсинг сайта championat.com (крайняя мера, если ИИ вернул null)
        """
        # ЭТАП 1: Локальный кэш (ID, Умный поиск, Старая логика)
        result = self._search_by_fighter_ids(fighter_a, fighter_b)
        if result:
            return result

        all_fights = self._load_all_fights()

        result = self._search_with_smart_logic(all_fights, fighter_a, fighter_b)
        if result:
            return result

        result = self._search_with_old_logic(all_fights, fighter_a, fighter_b)
        if result:
            return result

        # ЭТАП 2 и 3: Запрос к ИИ (если известна дата боя)
        if known_date:
            ai_result = self._query_ai_fallback(fighter_a, fighter_b, known_date)
            if ai_result and ai_result.get("winner"):
                print(f"   💾 Сохраняем результат от ИИ в локальный кэш...")
                # Форматируем и сразу сохраняем в кэш, чтобы не спрашивать ИИ в следующий раз
                self._add_to_cache(fighter_a, fighter_b, {
                    'winner': ai_result.get("winner"),
                    'method': ai_result.get("method", "DEC"),
                    'round': int(ai_result.get("round", 3)),
                    'tournament': "UFC"
                }, known_date, {'fighter_a': fighter_a, 'fighter_b': fighter_b})

                return self._format_fight_result({
                    "date": known_date,
                    "fighter_a": fighter_a,
                    "fighter_b": fighter_b,
                    "winner": ai_result.get("winner"),
                    "method": ai_result.get("method", "DEC"),
                    "round": int(ai_result.get("round", 3))
                })

        # ЭТАП 4: Парсинг сайта (крайняя мера, только если кэш и ИИ вернули 0)
        print("   ⚠️ Кэш и ИИ не дали точного результата. Запускаем парсинг сайта...")
        return self._parse_from_website(fighter_a, fighter_b)

# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================
if __name__ == "__main__":
    parser = UFCParser(similarity_threshold=0.75)

    # ✅ v48.2: Показываем динамическую границу
    threshold = parser._get_fact_threshold()
    print(f"📅 Сегодня: {datetime.now().strftime('%d.%m.%Y')}")
    print(f"📅 Граница фактов: {threshold.strftime('%d.%m.%Y')} (сегодня - {parser.FACT_BUFFER_DAYS} дня)")

    # ✅ v48.2: Очистка кэша от прогнозов
    removed = parser.clean_cache_from_predictions()
    print(f"Удалено прогнозов: {removed}")

    result = parser.get_fight_result("Хабиб Нурмагомедов", "Джастин Гейджи")
    if result:
        print("\n✅ Бой найден:")
        print(f"   Дата: {result['date'].strftime('%d.%m.%Y')}")
        print(f"   Событие: {result['event']}")
        print(f"   Победитель: {result['winner']}")
        print(f"   Метод: {result['method']}, раунд: {result['round']}")
        if 'fighter_a_id' in result:
            print(f"   ID A: {result['fighter_a_id']}")
        if 'fighter_b_id' in result:
            print(f"   ID B: {result['fighter_b_id']}")
    else:
        print("\n❌ Бой не найден.")