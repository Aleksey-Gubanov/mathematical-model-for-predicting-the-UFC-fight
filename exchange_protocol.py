#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXCHANGE PROTOCOL v1.2 | Протокол обмена файлами между мозгом и воркером
================================================================
ИСПРАВЛЕНИЯ v1.2:
- Безопасная сортировка запросов (приведение типов)
- Добавлен метод cleanup_request_only() — удаляет только запрос и статус
- Метод cleanup_request() — удаляет ВСЁ (запрос + ответ + статус)
================================================================
"""
import os
import json
import time
import uuid
import glob
from typing import Dict, Optional, List


class ExchangeProtocol:
    """Протокол обмена файлами между мозгом и воркером"""

    def __init__(self, base_dir: str = "mma_exchange"):
        self.base_dir = base_dir
        self.REQUESTS_DIR = os.path.join(base_dir, "requests")
        self.RESPONSES_DIR = os.path.join(base_dir, "responses")
        self.STATUS_DIR = os.path.join(base_dir, "status")

        # Создаём папки если их нет
        for directory in [self.REQUESTS_DIR, self.RESPONSES_DIR, self.STATUS_DIR]:
            os.makedirs(directory, exist_ok=True)

    def create_request(self, request_type: str, data: Dict, priority: int = 1) -> str:
        """
        Создаёт новый запрос

        :param request_type: тип запроса (enrich, fighter_stats, fight_result, schedule)
        :param data: данные запроса
        :param priority: приоритет (1-5, где 5 — наивысший)
        :return: ID запроса
        """
        request_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"

        request = {
            "id": request_id,
            "type": request_type,
            "data": data,
            "priority": priority,
            "created_at": time.time(),  # ✅ ВСЕГДА float
            "status": "pending"
        }

        filename = os.path.join(self.REQUESTS_DIR, f"req_{request_id}_{request_type}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(request, f, indent=2, ensure_ascii=False)

        # Записываем статус
        self._write_status(request_id, "pending")

        return request_id

    def get_pending_requests(self) -> List[Dict]:
        """
        Возвращает список ожидающих запросов, отсортированных по приоритету

        :return: список запросов
        """
        requests = []
        pattern = os.path.join(self.REQUESTS_DIR, "req_*.json")

        for filepath in glob.glob(pattern):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    request = json.load(f)
                requests.append(request)
            except Exception as e:
                print(f"⚠️ Ошибка чтения {filepath}: {e}")

        # ✅ ИСПРАВЛЕНИЕ: Безопасная сортировка с приведением типов
        def safe_sort_key(r):
            try:
                priority = float(r.get('priority', 1))
            except (ValueError, TypeError):
                priority = 1.0
            try:
                created_at = float(r.get('created_at', 0))
            except (ValueError, TypeError):
                created_at = 0.0
            return (-priority, created_at)

        requests.sort(key=safe_sort_key)

        return requests

    def write_response(self, request_id: str, status: str, data: Dict,
                       error: str = None, validation: Dict = None):
        """
        Записывает ответ на запрос

        :param request_id: ID запроса
        :param status: статус (success, error, partial)
        :param data: данные ответа
        :param error: сообщение об ошибке (если есть)
        :param validation: информация о валидации
        """
        response = {
            "id": request_id,
            "status": status,
            "data": data,
            "error": error,
            "validation": validation or {"complete": False},
            "created_at": time.time()
        }

        filename = os.path.join(self.RESPONSES_DIR, f"res_{request_id}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2, ensure_ascii=False)

        # Обновляем статус
        self._write_status(request_id, status)

    def get_response(self, request_id: str, timeout: int = 30) -> Optional[Dict]:
        """
        Ожидает и читает ответ на запрос

        :param request_id: ID запроса
        :param timeout: таймаут в секундах
        :return: ответ или None при таймауте
        """
        filename = os.path.join(self.RESPONSES_DIR, f"res_{request_id}.json")

        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"⚠️ Ошибка чтения ответа: {e}")
                    return None
            time.sleep(0.5)

        print(f"⚠️ Таймаут ожидания ответа для {request_id}")
        return None

    def cleanup_request(self, request_id: str):
        """
        Удаляет ВСЕ файлы, связанные с запросом (запрос + ответ + статус)
        Используется мозгом ПОСЛЕ чтения ответа

        :param request_id: ID запроса
        """
        patterns = [
            os.path.join(self.REQUESTS_DIR, f"req_{request_id}_*.json"),
            os.path.join(self.RESPONSES_DIR, f"res_{request_id}.json"),
            os.path.join(self.STATUS_DIR, f"status_{request_id}.json")
        ]

        for pattern in patterns:
            for filepath in glob.glob(pattern):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"⚠️ Не удалось удалить {filepath}: {e}")

    def cleanup_request_only(self, request_id: str):
        """
        Удаляет ТОЛЬКО файл запроса (req_*.json) и статус
        НЕ трогает файл ответа (res_*.json) — его удалит мозг после чтения

        :param request_id: ID запроса
        """
        # Удаляем только файл запроса
        pattern = os.path.join(self.REQUESTS_DIR, f"req_{request_id}_*.json")
        for filepath in glob.glob(pattern):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"⚠️ Не удалось удалить {filepath}: {e}")

        # Удаляем файл статуса
        status_file = os.path.join(self.STATUS_DIR, f"status_{request_id}.json")
        if os.path.exists(status_file):
            try:
                os.remove(status_file)
            except Exception as e:
                print(f"⚠️ Не удалось удалить {status_file}: {e}")

        # ❌ НЕ удаляем файл ответа! Его удалит мозг после чтения!

    def _write_status(self, request_id: str, status: str):
        """Записывает статус запроса"""
        status_data = {
            "id": request_id,
            "status": status,
            "updated_at": time.time()
        }

        filename = os.path.join(self.STATUS_DIR, f"status_{request_id}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2)

    def get_status(self, request_id: str) -> Optional[str]:
        """Получает статус запроса"""
        filename = os.path.join(self.STATUS_DIR, f"status_{request_id}.json")
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('status')
            except:
                pass
        return None

    def list_all_pending(self) -> List[str]:
        """Возвращает список ID всех ожидающих запросов"""
        return [r['id'] for r in self.get_pending_requests()]


if __name__ == "__main__":
    print("="*70)
    print("🧪 ТЕСТ EXCHANGE PROTOCOL v1.2")
    print("="*70)

    protocol = ExchangeProtocol()

    # Тест 1: Создание запроса
    print("\n🧪 Тест 1: Создание запроса...")
    req_id = protocol.create_request(
        request_type="enrich",
        data={"fighter_name": "Jon Jones", "fight_date": "2023-03-04"},
        priority=3
    )
    print(f"   ✅ Создан запрос: {req_id}")

    # Тест 2: Проверка очереди
    print("\n🧪 Тест 2: Проверка очереди...")
    pending = protocol.get_pending_requests()
    print(f"   📭 Ожидающих запросов: {len(pending)}")

    # Тест 3: Запись ответа
    print("\n🧪 Тест 3: Запись ответа...")
    protocol.write_response(
        request_id=req_id,
        status="success",
        data={"stress_factor": 0.3, "motivation_index": 0.9},
        validation={"complete": True}
    )
    print("   ✅ Ответ записан")

    # Тест 4: Чтение ответа
    print("\n🧪 Тест 4: Чтение ответа...")
    response = protocol.get_response(req_id, timeout=5)
    if response:
        print(f"   ✅ Ответ получен: {response['status']}")
    else:
        print("   ❌ Ответ не получен")

    # Тест 5: cleanup_request_only (удаляет только запрос)
    print("\n🧪 Тест 5: cleanup_request_only...")
    protocol.cleanup_request_only(req_id)
    pending_after = protocol.get_pending_requests()
    print(f"   📭 Запросов после cleanup_request_only: {len(pending_after)}")

    # Проверяем, что ответ ещё есть
    response_after = protocol.get_response(req_id, timeout=1)
    if response_after:
        print("   ✅ Ответ ещё существует (не удалён)")
    else:
        print("   ❌ Ответ удалён (ошибка!)")

    # Тест 6: cleanup_request (удаляет ВСЁ)
    print("\n🧪 Тест 6: cleanup_request...")
    protocol.cleanup_request(req_id)
    response_final = protocol.get_response(req_id, timeout=1)
    if not response_final:
        print("   ✅ Все файлы удалены")
    else:
        print("   ❌ Файлы остались (ошибка!)")

    print("\n" + "="*70)
    print("✅ ТЕСТ ЗАВЕРШЁН!")
    print("="*70)