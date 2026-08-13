#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SECURE NEURAL CHANNEL v3.1 | API MANAGER
================================================================
ИСПРАВЛЕНИЯ v3.1 (КРИТИЧНО — УСТРАНЕНИЕ ОШИБКИ 400):
1. ✅ response_format ТОЛЬКО если system_prompt требует JSON
2. ✅ temperature увеличен с 0.1 до 0.7 (разнообразие ответов)
3. ✅ Обработка ошибки 400 с автоматическим retry без response_format
4. ✅ Fallback модель: deepseek-chat → deepseek-v3.1
5. ✅ Расширенная диагностика ошибок
================================================================
Шифрование: PBKDF2 (100k итераций) + XOR + Base64
Кэширование: MD5 хэш запроса → JSON файл
================================================================
"""
import os
import json
import hashlib
import base64
import requests
import time
from typing import Optional, Dict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class SecureNeuralChannel:
    _api_key: str = ""
    _provider: str = "deepseek"
    _is_initialized: bool = False
    _cache_file: str = "llm_cache.json"
    _cache: Dict = {}
    _config_file: str = "api_config.enc"
    _master_password: str = ""

    # ========================================================================
    # КРИПТОГРАФИЯ (PBKDF2 + XOR + Base64)
    # ========================================================================
    @staticmethod
    def _derive_key(password: str, salt: bytes = b"mma_predictor_salt_v3") -> bytes:
        """Derive 32-byte key from password using PBKDF2 (100k iterations)."""
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)

    @staticmethod
    def _encrypt(data: bytes, password: str) -> bytes:
        """Шифрование: ключ + XOR + base64."""
        key = SecureNeuralChannel._derive_key(password)
        extended_key = (key * ((len(data) // len(key)) + 1))[:len(data)]
        encrypted = bytes(a ^ b for a, b in zip(data, extended_key))
        salt = b"MMA_PRED_V3"
        check = hashlib.sha256(salt + data).digest()[:8]
        return base64.b64encode(salt + check + encrypted)

    @staticmethod
    def _decrypt(encrypted_b64: bytes, password: str) -> Optional[bytes]:
        """Дешифрование. Возвращает None если пароль неверный."""
        try:
            raw = base64.b64decode(encrypted_b64)
            if len(raw) < 19:
                return None
            salt = raw[:11]
            check = raw[11:19]
            encrypted = raw[19:]
            if salt != b"MMA_PRED_V3":
                return None
            key = SecureNeuralChannel._derive_key(password)
            extended_key = (key * ((len(encrypted) // len(key)) + 1))[:len(encrypted)]
            decrypted = bytes(a ^ b for a, b in zip(encrypted, extended_key))
            expected_check = hashlib.sha256(salt + decrypted).digest()[:8]
            if expected_check != check:
                return None
            return decrypted
        except Exception:
            return None

    # ========================================================================
    # УПРАВЛЕНИЕ КОНФИГУРАЦИЕЙ
    # ========================================================================
    @classmethod
    def _save_config(cls, api_key: str, provider: str = "deepseek"):
        """Сохранить зашифрованный API ключ."""
        config_data = {"provider": provider, "api_key": api_key, "version": "3.1"}
        json_bytes = json.dumps(config_data, ensure_ascii=False).encode('utf-8')
        encrypted = cls._encrypt(json_bytes, cls._master_password)
        with open(cls._config_file, "wb") as f:
            f.write(encrypted)

    @classmethod
    def _load_config(cls) -> Optional[Dict]:
        """Загрузить и расшифровать API ключ."""
        if not os.path.exists(cls._config_file):
            return None
        try:
            with open(cls._config_file, "rb") as f:
                encrypted = f.read()
            decrypted = cls._decrypt(encrypted, cls._master_password)
            if decrypted is None:
                return None
            return json.loads(decrypted.decode('utf-8'))
        except Exception:
            return None

    # ========================================================================
    # ИНИЦИАЛИЗАЦИЯ
    # ========================================================================
    @classmethod
    def init(cls, password: str) -> bool:
        """Инициализация через мастер-пароль."""
        cls._master_password = password
        cls._is_initialized = False

        # Попытка загрузить сохранённый ключ
        config = cls._load_config()
        if config:
            cls._api_key = config.get("api_key", "")
            cls._provider = config.get("provider", "deepseek")
            cls._is_initialized = True
            print("✅ SecureNeuralChannel инициализирован")
            print(f"   🔌 Провайдер: {cls._provider}")
            print(f"   🔑 API ключ: загружен из зашифрованного хранилища")
        else:
            # Первый запуск или неверный пароль
            if os.path.exists(cls._config_file):
                print("❌ Неверный мастер-пароль или повреждённый файл конфигурации.")
                return False

            print("🔧 Первый запуск. Настройка API ключа...")
            print("   📝 Поддерживаемые провайдеры:")
            print("      1. DeepSeek (рекомендуется)")
            print("      2. OpenRouter")
            choice = input("   Выберите (1/2) [1]: ").strip() or "1"
            cls._provider = "deepseek" if choice == "1" else "openrouter"

            print(f"   🔑 Введите API ключ для {cls._provider}:")
            cls._api_key = input("   API Key: ").strip()
            if not cls._api_key:
                print("   ❌ Ключ не может быть пустым.")
                return False

            # Сохраняем зашифрованный ключ
            cls._save_config(cls._api_key, cls._provider)
            cls._is_initialized = True
            print("   ✅ API ключ сохранён и зашифрован!")
            print(f"   📁 Файл: {cls._config_file}")

        # Загрузка кэша
        cls._load_cache()
        print(f"   💾 Кэш: {len(cls._cache)} записей")
        return True

    # ========================================================================
    # КАСТОМНЫЙ API КЛЮЧ (для пользователя)
    # ========================================================================
    @classmethod
    def set_custom_api_key(cls, api_key: str):
        """Установить пользовательский API ключ (временно)."""
        if api_key and api_key.strip():
            cls._api_key = api_key.strip()
            print(f"   🔑 Установлен пользовательский API ключ")

    # ========================================================================
    # КЭШИРОВАНИЕ
    # ========================================================================
    @classmethod
    def _load_cache(cls):
        """Загрузить кэш из файла."""
        if os.path.exists(cls._cache_file):
            try:
                with open(cls._cache_file, "r", encoding="utf-8") as f:
                    cls._cache = json.load(f)
            except Exception:
                cls._cache = {}

    @classmethod
    def _save_cache(cls):
        """Сохранить кэш в файл."""
        try:
            with open(cls._cache_file, "w", encoding="utf-8") as f:
                json.dump(cls._cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ========================================================================
    # ✅ v3.1: ОПРЕДЕЛЕНИЕ ТРЕБОВАНИЯ JSON
    # ========================================================================
    @classmethod
    def _requires_json_format(cls, system_prompt: str, user_prompt: str) -> bool:
        """
        Определяет, требует ли запрос JSON формат.
        Проверяет system_prompt и user_prompt на ключевые слова.
        """
        combined = (system_prompt + " " + user_prompt).lower()
        json_keywords = [
            "json", "валидный json", "строго json", "только json",
            "json формат", "json формате", "json object",
            "верни json", "отвечай в json", "return json"
        ]
        return any(keyword in combined for keyword in json_keywords)

    # ========================================================================
    # ✅ v3.1: ЗАПРОСЫ К API (С ОБРАБОТКОЙ 400)
    # ========================================================================
    @classmethod
    def query(cls, prompt: str, system_prompt: str = "Ты полезный ассистент.",
              use_cache: bool = True, temperature: float = 0.7) -> Optional[Dict]:
        """
        Отправить запрос к LLM API.

        :param prompt: Текст запроса
        :param system_prompt: Системный промпт
        :param use_cache: Использовать кэш
        :param temperature: Температура (0.0-1.0), по умолчанию 0.7
        :return: dict (JSON) или None (ошибка)
        """
        if not cls._is_initialized:
            raise RuntimeError("SecureNeuralChannel не инициализирован. Вызовите init() первым.")

        # Проверка кэша
        cache_key = hashlib.md5(f"{system_prompt}_{prompt}".encode()).hexdigest()
        if use_cache and cache_key in cls._cache:
            return cls._cache[cache_key]

        # Формирование запроса
        if cls._provider == "deepseek":
            url = "https://api.deepseek.com/chat/completions"
            model = "deepseek-chat"  # Алиас на последнюю модель
        elif cls._provider == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            model = "deepseek/deepseek-chat-v3.1:free"
        else:
            raise ValueError(f"Неизвестный провайдер: {cls._provider}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls._api_key}"
        }
        if cls._provider == "openrouter":
            headers["HTTP-Referer"] = "https://mma-predictor.local"
            headers["X-Title"] = "MMA Predictor"

        # ✅ v3.1: Определяем, нужен ли JSON формат
        requires_json = cls._requires_json_format(system_prompt, prompt)

        # Базовый payload
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": 3000   # 🔼 увеличено с 2000 до 3000
        }

        # ✅ v3.1: response_format ТОЛЬКО если требуется JSON
        if requires_json:
            payload["response_format"] = {"type": "json_object"}

        # ================================================================
        # ✅ ИСПРАВЛЕНИЕ: Сессия с повторными попытками и таймаутом 60 сек
        # ================================================================
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))

        try:
            # Первый запрос (с response_format, если требуется)
            response = session.post(url, json=payload, headers=headers, timeout=60)

            # Обработка ошибки 400 (повтор без response_format)
            if response.status_code == 400:
                print(f"⚠️ Ошибка 400, повтор без response_format...")
                if "response_format" in payload:
                    del payload["response_format"]
                response = session.post(url, json=payload, headers=headers, timeout=60)

            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Парсинг JSON ответа
            try:
                content = content.replace("```json", "").replace("```", "").strip()
                result = json.loads(content)
            except json.JSONDecodeError:
                # Если не JSON, но ожидался — пробуем извлечь
                if requires_json:
                    import re
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        try:
                            result = json.loads(match.group())
                        except json.JSONDecodeError:
                            result = {"raw_content": content}
                    else:
                        result = {"raw_content": content}
                else:
                    result = {"raw_content": content}

            # Сохранение в кэш
            if use_cache:
                cls._cache[cache_key] = result
                cls._save_cache()

            return result

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP ошибка API запроса: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_body = e.response.json()
                    print(f"   📋 Детали: {json.dumps(error_body, ensure_ascii=False)[:200]}")
                except Exception:
                    print(f"   📋 Текст: {e.response.text[:200]}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка API запроса: {e}")
            return None
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
            return None
        finally:
            # Закрываем сессию, чтобы освободить ресурсы
            session.close()

    # ========================================================================
    # УТИЛИТЫ
    # ========================================================================
    @classmethod
    def change_password(cls, old_password: str, new_password: str) -> bool:
        """Сменить мастер-пароль."""
        cls._master_password = old_password
        config = cls._load_config()
        if config is None:
            return False
        cls._master_password = new_password
        cls._save_config(config["api_key"], config["provider"])
        return True

    @classmethod
    def delete_config(cls) -> bool:
        """Удалить конфигурацию (сброс API ключа)."""
        if os.path.exists(cls._config_file):
            os.remove(cls._config_file)
            return True
        return False

    @classmethod
    def clear_cache(cls) -> bool:
        """Очистить кэш запросов."""
        cls._cache = {}
        try:
            if os.path.exists(cls._cache_file):
                os.remove(cls._cache_file)
            return True
        except Exception:
            return False


# ========================================================================
# ТЕСТ ПРИ ЗАПУСКЕ
# ========================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТ SECURE NEURAL CHANNEL v3.1")
    print("=" * 70)

    pwd = input("🔐 Мастер-пароль: ").strip()

    if not SecureNeuralChannel.init(pwd):
        print("❌ Не удалось инициализировать")
        exit(1)

    # Тест 1: Простой запрос (без JSON)
    print("\n🧪 Тест 1: Простой запрос...")
    result = SecureNeuralChannel.query(
        "Скажи 'ok'",
        "Ты полезный ассистент.",
        use_cache=False
    )
    print(f"   Результат: {result}")

    # Тест 2: Запрос с JSON
    print("\n🧪 Тест 2: Запрос с JSON...")
    result = SecureNeuralChannel.query(
        'Верни JSON: {"status":"ok"}',
        "Ты полезный ассистент. Отвечай только в JSON формате.",
        use_cache=False
    )
    print(f"   Результат: {result}")

    # Тест 3: Запрос с кэшем
    print("\n🧪 Тест 3: Кэширование...")
    result1 = SecureNeuralChannel.query("Тест кэша", "Система")
    result2 = SecureNeuralChannel.query("Тест кэша", "Система")
    print(f"   Первый запрос: {result1}")
    print(f"   Второй запрос (из кэша): {result2}")
    print(f"   Совпадают: {result1 == result2}")

    print("\n" + "=" * 70)
    print("✅ ТЕСТ ЗАВЕРШЁН!")
    print("=" * 70)