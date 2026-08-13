#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ODDS API CLIENT v2.0 | С ТРАНСЛИТЕРАЦИЕЙ + fighters_ids.json
================================================================
ИСПРАВЛЕНИЯ v2.0:
1. ✅ ТРАНСЛИТЕРАЦИЯ кириллицы → латиница перед сравнением
2. ✅ Поиск в fighters_ids.json (canonical_name + aliases)
3. ✅ Сравнение по фамилии с транслитерацией
4. ✅ Отладочный вывод для диагностики
================================================================
"""
import os
import re
import json
import time
import difflib
import requests
from typing import Optional, Dict, List

# ============================================================================
# КОНСТАНТЫ
# ============================================================================
API_BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "mma_mixed_martial_arts"
CACHE_FILE = os.path.join("dataset", "odds_cache.json")
FIGHTERS_IDS_FILE = os.path.join("dataset", "fighters_ids.json")
CACHE_TTL = 3600  # 1 час

# ============================================================================
# ✅ v2.0: ТАБЛИЦА ТРАНСЛИТЕРАЦИИ
# ============================================================================
TRANS_TABLE = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    ' ': '', '-': '', '.': '', ',': ''
}

# ============================================================================
# ИМПОРТ ЗАЩИЩЁННОГО ХРАНИЛИЩА
# ============================================================================
try:
    from secure_keys import SecureKeys
    HAS_SECURE_KEYS = True
except ImportError:
    HAS_SECURE_KEYS = False
    print("⚠️ SecureKeys не найден!")


class OddsAPIClient:
    """Клиент для работы с The Odds API."""

    def __init__(self):
        self.api_key = self._load_api_key()
        self._cache = self._load_cache()
        self._fighters_db = None  # Ленивая загрузка fighters_ids.json

    # =========================================================================
    # 🔐 БЕЗОПАСНАЯ ЗАГРУЗКА API КЛЮЧА
    # =========================================================================
    def _load_api_key(self) -> str:
        """Загружает API ключ из защищённого хранилища."""
        if not HAS_SECURE_KEYS:
            print("❌ SecureKeys не инициализирован!")
            return ""

        if not SecureKeys._fernet:
            print("❌ SecureKeys не инициализирован (нет мастер-пароля)!")
            return ""

        api_key = SecureKeys.get("the_odds_api_key")
        if api_key:
            print("🔑 API ключ загружен из защищённого хранилища")
            return api_key

        print("⚠️ API ключ 'the_odds_api_key' не найден в SecureKeys")
        return ""

    # =========================================================================
    # ✅ v2.0: ЗАГРУЗКА fighters_ids.json (ленивая)
    # =========================================================================
    def _load_fighters_db(self) -> Dict:
        """Загружает fighters_ids.json для поиска aliases."""
        if self._fighters_db is not None:
            return self._fighters_db

        if not os.path.exists(FIGHTERS_IDS_FILE):
            self._fighters_db = {}
            return {}

        try:
            with open(FIGHTERS_IDS_FILE, 'r', encoding='utf-8') as f:
                self._fighters_db = json.load(f)
            print(f"   📚 fighters_ids.json загружен: {len(self._fighters_db)} бойцов")
            return self._fighters_db
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки fighters_ids.json: {e}")
            self._fighters_db = {}
            return {}

    # =========================================================================
    # ✅ v2.0: ТРАНСЛИТЕРАЦИЯ
    # =========================================================================
    def _transliterate(self, text: str) -> str:
        """Переводит кириллицу в латиницу."""
        if not text:
            return ""
        result = []
        for char in text.lower():
            if char in TRANS_TABLE:
                result.append(TRANS_TABLE[char])
            else:
                result.append(char)
        return ''.join(result)

    def _normalize_name(self, name: str) -> str:
        """
        ✅ v2.0: Нормализует имя с ТРАНСЛИТЕРАЦИЕЙ.
        'Макс Холлоуэй' → 'makskholouey'
        'Max Holloway' → 'maxholloway'
        """
        if not name:
            return ""
        # Шаг 1: Транслитерация (кириллица → латиница)
        latin = self._transliterate(name)
        # Шаг 2: Убираем всё, кроме букв и цифр
        normalized = re.sub(r'[^a-z0-9]', '', latin)
        return normalized

    def _get_surname(self, name: str) -> str:
        """
        ✅ v2.0: Извлекает фамилию с ТРАНСЛИТЕРАЦИЕЙ.
        'Макс Холлоуэй' → 'kholouey'
        'Max Holloway' → 'holloway'
        """
        if not name:
            return ""

        # Разбиваем на слова
        parts = name.strip().split()
        if not parts:
            return ""

        # Берём последнее слово (фамилию)
        surname = parts[-1]

        # Убираем суффиксы (Jr., Sr., III, etc.)
        suffixes = ['jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv', 'v']
        if surname.lower() in suffixes and len(parts) > 1:
            surname = parts[-2]

        # Транслитерируем
        return self._transliterate(surname)

    def _get_all_name_variants(self, name: str) -> List[str]:
        """
        ✅ v2.0: Получает ВСЕ варианты имени:
        1. Полное имя (нормализованное)
        2. Фамилия
        3. Aliases из fighters_ids.json
        """
        variants = set()

        # 1. Полное имя (нормализованное)
        full_norm = self._normalize_name(name)
        if full_norm:
            variants.add(full_norm)

        # 2. Фамилия
        surname = self._get_surname(name)
        if surname:
            variants.add(surname)

        # 3. Поиск в fighters_ids.json
        fighters_db = self._load_fighters_db()
        if fighters_db:
            # Ищем бойца по нормализованному имени
            for fid, data in fighters_db.items():
                canonical = data.get("canonical_name", "")
                aliases = data.get("aliases", [])
                all_names = [canonical] + aliases

                # Проверяем, совпадает ли имя с одним из aliases
                for alias in all_names:
                    if not alias:
                        continue
                    alias_norm = self._normalize_name(alias)
                    # Если совпадает полное имя или фамилия
                    if alias_norm == full_norm or self._get_surname(alias) == surname:
                        # Добавляем все aliases этого бойца
                        for a in all_names:
                            if a:
                                variants.add(self._normalize_name(a))
                                variants.add(self._get_surname(a))
                        break

        return list(variants)

    # =========================================================================
    # 💾 КЭШИРОВАНИЕ
    # =========================================================================
    def _load_cache(self) -> Dict:
        """Загружает кэш из файла."""
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            now = time.time()
            valid_cache = {
                k: v for k, v in cache.items()
                if now - v.get("timestamp", 0) < CACHE_TTL
            }
            if len(valid_cache) < len(cache):
                print(f"   🗑️ Кэш очищен от устаревших записей: {len(cache) - len(valid_cache)}")
            return valid_cache
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки кэша: {e}")
            return {}

    def _save_cache(self):
        """Сохраняет кэш в файл."""
        try:
            os.makedirs("dataset", exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"   ⚠️ Ошибка сохранения кэша: {e}")

    # =========================================================================
    # 📡 ПОЛУЧЕНИЕ СОБЫТИЙ
    # =========================================================================
    def get_upcoming_events(self) -> List[Dict]:
        """Получает список предстоящих событий MMA."""
        if not self.api_key:
            print("   ❌ API ключ не установлен!")
            return []

        cache_key = "upcoming_events"
        if cache_key in self._cache:
            cache_age = time.time() - self._cache[cache_key]["timestamp"]
            print(f"   💾 События из кэша (возраст: {cache_age:.0f} сек)")
            return self._cache[cache_key]["data"]

        try:
            url = f"{API_BASE_URL}/sports/{SPORT_KEY}/odds/"
            params = {
                "apiKey": self.api_key,
                "regions": "us,uk,eu",
                "markets": "h2h",
                "oddsFormat": "decimal"
            }

            print("   🌐 Запрос событий из API...")
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()

            events = response.json()
            print(f"   ✅ Получено событий: {len(events)}")

            self._cache[cache_key] = {
                "timestamp": time.time(),
                "data": events
            }
            self._save_cache()

            return events

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Ошибка запроса: {e}")
            return []

    # =========================================================================
    # 🔍 ПОИСК БОЯ ПО ИМЕНАМ
    # =========================================================================
    def get_fight_odds(self, fighter1: str, fighter2: str) -> Optional[Dict]:
        """
        ✅ v2.0: Ищет коэффициенты с учётом транслитерации.
        """
        if not self.api_key:
            return None

        events = self.get_upcoming_events()
        if not events:
            return None

        print(f"\n🔍 Поиск боя: {fighter1} vs {fighter2}")

        # ✅ v2.0: Получаем ВСЕ варианты имён
        f1_variants = self._get_all_name_variants(fighter1)
        f2_variants = self._get_all_name_variants(fighter2)

        print(f"   🔤 Варианты F1 ({fighter1}): {f1_variants[:5]}")
        print(f"   🔤 Варианты F2 ({fighter2}): {f2_variants[:5]}")

        for event in events:
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")

            # ✅ v2.0: Проверяем ВСЕ варианты имён
            if self._match_any(f1_variants, home_team) and self._match_any(f2_variants, away_team):
                print(f"   ✅ Бой найден (прямой): {home_team} vs {away_team}")
                return self._extract_odds(event, fighter1, fighter2, reverse=False)

            if self._match_any(f1_variants, away_team) and self._match_any(f2_variants, home_team):
                print(f"   ✅ Бой найден (обратный): {home_team} vs {away_team}")
                return self._extract_odds(event, fighter1, fighter2, reverse=True)

        # ✅ v2.0: Если не нашли — показываем ближайшие совпадения для отладки
        print(f"   ❌ Бой не найден. Ближайшие совпадения:")
        self._show_closest_matches(events, f1_variants, f2_variants)

        return None

    def _match_any(self, variants: List[str], api_name: str) -> bool:
        """Проверяет, совпадает ли хотя бы один вариант с именем из API."""
        if not api_name:
            return False

        api_norm = self._normalize_name(api_name)
        api_surname = self._get_surname(api_name)

        for variant in variants:
            if not variant:
                continue

            # Прямое совпадение
            if variant == api_norm:
                return True

            # Совпадение по фамилии
            if len(variant) >= 4 and len(api_surname) >= 4:
                if variant == api_surname:
                    return True

            # Вхождение подстроки
            if len(variant) >= 5 and len(api_norm) >= 5:
                if variant in api_norm or api_norm in variant:
                    return True

            # Fuzzy matching
            ratio = difflib.SequenceMatcher(None, variant, api_norm).ratio()
            if ratio >= 0.70:
                return True

            # Fuzzy matching по фамилии
            ratio_surname = difflib.SequenceMatcher(None, variant, api_surname).ratio()
            if ratio_surname >= 0.70:
                return True

        return False

    def _show_closest_matches(self, events: List[Dict], f1_variants: List[str], f2_variants: List[str]):
        """Показывает ближайшие совпадения для отладки."""
        matches = []

        for event in events:
            home = event.get("home_team", "")
            away = event.get("away_team", "")

            home_norm = self._normalize_name(home)
            away_norm = self._normalize_name(away)

            # Ищем максимальное сходство для F1
            best_f1_score = 0
            best_f1_match = ""
            for v in f1_variants:
                score = max(
                    difflib.SequenceMatcher(None, v, home_norm).ratio(),
                    difflib.SequenceMatcher(None, v, away_norm).ratio()
                )
                if score > best_f1_score:
                    best_f1_score = score
                    best_f1_match = home if difflib.SequenceMatcher(None, v, home_norm).ratio() > \
                                            difflib.SequenceMatcher(None, v, away_norm).ratio() else away

            # Ищем максимальное сходство для F2
            best_f2_score = 0
            best_f2_match = ""
            for v in f2_variants:
                score = max(
                    difflib.SequenceMatcher(None, v, home_norm).ratio(),
                    difflib.SequenceMatcher(None, v, away_norm).ratio()
                )
                if score > best_f2_score:
                    best_f2_score = score
                    best_f2_match = home if difflib.SequenceMatcher(None, v, home_norm).ratio() > \
                                            difflib.SequenceMatcher(None, v, away_norm).ratio() else away

            matches.append({
                "event": f"{home} vs {away}",
                "f1_score": best_f1_score,
                "f1_match": best_f1_match,
                "f2_score": best_f2_score,
                "f2_match": best_f2_match
            })

        # Сортируем по сумме сходства
        matches.sort(key=lambda x: x["f1_score"] + x["f2_score"], reverse=True)

        for m in matches[:5]:
            print(f"      • {m['event']} (F1: {m['f1_score']:.2f} → '{m['f1_match']}', F2: {m['f2_score']:.2f} → '{m['f2_match']}')")

    # =========================================================================
    # 📊 ИЗВЛЕЧЕНИЕ КОЭФФИЦИЕНТОВ
    # =========================================================================
    def _extract_odds(self, event: Dict, fighter1: str, fighter2: str, reverse: bool) -> Dict:
        """Извлекает коэффициенты из события."""
        bookmakers = event.get("bookmakers", [])

        if not bookmakers:
            return {
                "odds_a": 1.85,
                "odds_b": 1.85,
                "bookmaker": "Нет данных",
                "event": event.get("description", "UFC"),
                "date": event.get("commence_time", "")
            }

        bm = bookmakers[0]
        markets = bm.get("markets", [])

        if not markets:
            return {
                "odds_a": 1.85,
                "odds_b": 1.85,
                "bookmaker": bm.get("title", "Неизвестно"),
                "event": event.get("description", "UFC"),
                "date": event.get("commence_time", "")
            }

        outcomes = markets[0].get("outcomes", [])
        odds_map = {o.get("name", ""): o.get("price", 1.85) for o in outcomes}

        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")

        if reverse:
            odds_a = odds_map.get(away_team, 1.85)
            odds_b = odds_map.get(home_team, 1.85)
        else:
            odds_a = odds_map.get(home_team, 1.85)
            odds_b = odds_map.get(away_team, 1.85)

        return {
            "odds_a": float(odds_a),
            "odds_b": float(odds_b),
            "bookmaker": bm.get("title", "Неизвестно"),
            "event": event.get("description", "UFC"),
            "date": event.get("commence_time", "")
        }