#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PARSER WORKER v1.5 | ДОБАВЛЕНА ПОДДЕРЖКА DeepSeek
================================================================
ИЗМЕНЕНИЯ v1.5:
1. ✅ Добавлен новый тип запроса "enrich_deepseek"
2. ✅ Добавлен метод _handle_enrich_deepseek() для прямого вызова DeepSeek
3. ✅ Обновлена маршрутизация в process_one()
4. ✅ Сохранена обратная совместимость с "enrich" (YandexGPT)
================================================================
"""
import os
import time
import json
import glob
import traceback
import random
from typing import Dict, Optional, List
from exchange_protocol import ExchangeProtocol
from yandex_enricher import YandexEnricher


class ParserWorker:
    """Воркер для обработки запросов от мозга"""

    def __init__(self, master_password: str):
        self.protocol = ExchangeProtocol()
        self.enricher = YandexEnricher(master_password=master_password)
        self.running = False
        print("✅ ParserWorker инициализирован")
        print(f"   📁 Requests:  {self.protocol.REQUESTS_DIR}")
        print(f"   📁 Responses: {self.protocol.RESPONSES_DIR}")
        print(f"   🤖 YandexGPT: {'✅ готов' if self.enricher.client.api_key else '❌ не настроен'}")

    def process_one(self) -> bool:
        """Обрабатывает ОДИН запрос (возвращает True если обработал)"""
        # Получаем все ожидающие запросы
        pending = self.protocol.get_pending_requests()

        # ДИАГНОСТИКА
        print(f"   🔍 Найдено запросов в очереди: {len(pending)}")
        if pending:
            for p in pending:
                print(f"      • {p['id']} | {p['type']}")

        if not pending:
            return False

        # Берём первый запрос с наивысшим приоритетом
        request = pending[0]
        request_id = request["id"]
        request_type = request["type"]
        data = request.get("data", {})

        print(f"\n🔄 Обработка запроса: {request_id} ({request_type})")

        try:
            # ✅ v1.5: МАРШРУТИЗАЦИЯ С ПОДДЕРЖКОЙ DeepSeek
            if request_type == "enrich":
                result = self._handle_enrich(data)
            elif request_type == "enrich_deepseek":  # ✅ НОВЫЙ ТИП
                result = self._handle_enrich_deepseek(data)
            elif request_type == "fighter_stats":
                result = self._handle_fighter_stats(data)
            elif request_type == "fight_result":
                result = self._handle_fight_result(data)
            elif request_type == "schedule":
                result = self._handle_schedule(data)
            else:
                result = {
                    "status": "error",
                    "error": f"Неизвестный тип запроса: {request_type}",
                    "data": {}
                }

            # Записываем ответ
            self.protocol.write_response(
                request_id=request_id,
                status=result.get("status", "error"),
                data=result.get("data", {}),
                error=result.get("error"),
                validation=result.get("validation", {"complete": False})
            )

            # ✅ Удаляем ТОЛЬКО файл запроса, ответ оставляем для мозга!
            self.protocol.cleanup_request_only(request_id)

            print(f"   ✅ Запрос обработан: {result.get('status')}")
            return True

        except Exception as e:
            print(f"   ❌ Ошибка обработки: {e}")
            traceback.print_exc()

            self.protocol.write_response(
                request_id=request_id,
                status="error",
                error=str(e),
                data={}
            )

            # ✅ Удаляем файл запроса даже при ошибке
            self.protocol.cleanup_request_only(request_id)
            return False

    def _handle_enrich(self, data: Dict) -> Dict:
        """
        ✅ v1.4: Обогащение данных через YandexGPT (БЕЗ ДУБЛИРОВАНИЯ!)
        """
        fighter_name = data.get("fighter_name")
        fight_date = data.get("fight_date")
        fighter_stats = data.get("fighter_stats", {})

        if not fighter_name or not fight_date:
            return {
                "status": "error",
                "error": "Отсутствуют fighter_name или fight_date",
                "data": {}
            }

        print(f"      🤖 Вызов enrich_fighter (YandexGPT) для: {fighter_name} (дата: {fight_date})")
        if fighter_stats:
            print(f"      📊 Переданная статистика: {fighter_stats}")

        # ✅ v3.0: Извлекаем параметры из fighter_stats
        opponent_name = fighter_stats.get("opponent_name")
        opponent_record = fighter_stats.get("opponent_record")
        fight_context = fighter_stats.get("fight_context", "regular")
        recent_form = fighter_stats.get("recent_form")

        # ✅ v1.4: ОДИН вызов с правильными параметрами (БЕЗ дублирования!)
        enrichment = self.enricher.enrich_fighter(
            fighter_name,
            fight_date,
            fighter_stats=fighter_stats,
            opponent_name=opponent_name,
            opponent_record=opponent_record,
            fight_context=fight_context,
            recent_form=recent_form
        )

        print(f"      📥 Результат enrich_fighter (YandexGPT):")
        if enrichment:
            for key, value in enrichment.items():
                print(f"         • {key}: {value}")
        else:
            print(f"         ❌ ПУСТО!")

        return {
            "status": "success" if enrichment else "error",
            "data": enrichment or {},
            "validation": {
                "complete": True,
                "missing_fields": [],
                "confidence": 0.85
            }
        }

    # ================================================================
    # ✅ v1.5: НОВЫЙ МЕТОД ДЛЯ DeepSeek
    # ================================================================
    def _handle_enrich_deepseek(self, data: Dict) -> Dict:
        """
        ✅ v1.5: Обогащение данных через DeepSeek (прямой вызов)
        """
        fighter_name = data.get("fighter_name")
        fight_date = data.get("fight_date")
        fighter_stats = data.get("fighter_stats", {})

        if not fighter_name or not fight_date:
            return {
                "status": "error",
                "error": "Отсутствуют fighter_name или fight_date",
                "data": {}
            }

        print(f"      🤖 DeepSeek enrich для: {fighter_name} (дата: {fight_date})")

        # ✅ ПРЯМОЙ ВЫЗОВ DeepAIAnalyst.enrich_fighter
        try:
            from deep_ai_analyst import DeepAIAnalyst
            enrichment = DeepAIAnalyst.enrich_fighter(
                fighter_name=fighter_name,
                fight_date=fight_date,
                opponent_name=fighter_stats.get("opponent_name"),
                opponent_record=fighter_stats.get("opponent_record"),
                fight_context=fighter_stats.get("fight_context", "regular"),
                recent_form=fighter_stats.get("recent_form", []),
                weight_class=fighter_stats.get("weight_class"),
                fighter_stats=fighter_stats
            )
        except ImportError:
            print(f"      ❌ Не удалось импортировать DeepAIAnalyst!")
            return {
                "status": "error",
                "error": "DeepAIAnalyst не найден",
                "data": {}
            }
        except Exception as e:
            print(f"      ❌ Ошибка DeepSeek enrich: {e}")
            return {
                "status": "error",
                "error": str(e),
                "data": {}
            }

        print(f"      📥 Результат DeepSeek enrich:")
        if enrichment:
            for key, value in enrichment.items():
                if key in ["camp_name", "name"]:
                    print(f"         • {key}: {value}")
                else:
                    print(f"         • {key}: {value}")
        else:
            print(f"         ❌ ПУСТО!")

        return {
            "status": "success" if enrichment else "error",
            "data": enrichment or {},
            "validation": {
                "complete": True,
                "missing_fields": [],
                "confidence": 0.90
            }
        }

    def _handle_fighter_stats(self, data: Dict) -> Dict:
        """Парсинг статистики бойца (заглушка)"""
        fighter_name = data.get("fighter_name")
        return {
            "status": "partial",
            "data": {"fighter_name": fighter_name, "note": "Реальный парсинг ещё не реализован"},
            "validation": {"complete": False, "missing_fields": ["wins", "losses", "age"]}
        }

    def _handle_fight_result(self, data: Dict) -> Dict:
        """Парсинг результата боя (заглушка)"""
        return {
            "status": "partial",
            "data": {"note": "Реальный парсинг ещё не реализован"},
            "validation": {"complete": False, "missing_fields": ["winner", "method", "round"]}
        }

    def _handle_schedule(self, data: Dict) -> Dict:
        """Парсинг расписания (заглушка)"""
        return {
            "status": "partial",
            "data": {"note": "Реальный парсинг ещё не реализован"},
            "validation": {"complete": False, "missing_fields": ["fights"]}
        }

    def cleanup_after_read(self, request_id: str):
        """
        Мозг вызывает после чтения ответа для очистки файлов
        :param request_id: ID запроса
        """
        self.protocol.cleanup_request(request_id)
        print(f"🧹 Очищены файлы для запроса: {request_id}")

    def run_once(self):
        """Обрабатывает ВСЕ ожидающие запросы (один проход)"""
        print("\n" + "="*70)
        print("🔄 Запуск обработки запросов...")
        print("="*70)

        processed = 0
        while self.process_one():
            processed += 1

        if processed == 0:
            print("\n📭 Нет ожидающих запросов")
        else:
            print(f"\n✅ Обработано запросов: {processed}")

    def run_daemon(self, interval: int = 2):
        """Запускает воркер как демон"""
        self.running = True
        print("\n" + "="*70)
        print("🚀 ParserWorker запущен в режиме демона")
        print(f"   Интервал проверки: {interval} сек")
        print("   Нажмите Ctrl+C для остановки")
        print("="*70)

        try:
            while self.running:
                self.process_one()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n🛑 ParserWorker остановлен")
            self.running = False


# =============================================================================
# ТЕСТ ПРИ ЗАПУСКЕ
# =============================================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        # РЕЖИМ ДЕМОНА
        print("="*70)
        print("🚀 PARSER WORKER v1.5 | РЕЖИМ ДЕМОНА")
        print("="*70)

        pwd = input("🔐 Мастер-пароль: ").strip()
        worker = ParserWorker(master_password=pwd)
        worker.run_daemon(interval=2)
    else:
        # РЕЖИМ ТЕСТА
        print("="*70)
        print("🧪 ТЕСТ PARSER WORKER v1.5")
        print("="*70)

        pwd = input("🔐 Мастер-пароль: ").strip()
        worker = ParserWorker(master_password=pwd)

        # Тест 1: Проверка очереди
        print("\n🧪 Тест 1: Проверка очереди запросов...")
        pending = worker.protocol.get_pending_requests()
        print(f"   📭 Ожидающих запросов: {len(pending)}")

        # Тест 2: Создание тестового запроса на обогащение (YandexGPT)
        print("\n🧪 Тест 2: Создание тестового запроса на обогащение (enrich)...")
        req_id = worker.protocol.create_request(
            request_type="enrich",
            data={
                "fighter_name": "Jon Jones",
                "fight_date": "2023-03-04"
            },
            priority=3
        )
        print(f"   ✅ Создан запрос: {req_id}")

        # Тест 3: Обработка запроса
        print("\n🧪 Тест 3: Обработка запроса...")
        processed = worker.process_one()
        print(f"   Результат process_one(): {processed}")

        # Тест 4: Чтение ответа
        print("\n🧪 Тест 4: Чтение ответа...")
        response = worker.protocol.get_response(req_id, timeout=5)
        if response:
            print(f"   ✅ Ответ получен:")
            print(f"      Статус: {response['status']}")
            print(f"      Данные: {json.dumps(response['data'], indent=6, ensure_ascii=False)}")
        else:
            print("   ❌ Ответ не получен")

        # Тест 5: Очистка
        print("\n🧪 Тест 5: Очистка...")
        worker.cleanup_after_read(req_id)
        print("   ✅ Файлы удалены")

        # ✅ v1.5: ТЕСТ НОВОГО ТИПА ЗАПРОСА
        print("\n🧪 Тест 6: Создание запроса enrich_deepseek...")
        req_id2 = worker.protocol.create_request(
            request_type="enrich_deepseek",
            data={
                "fighter_name": "Jon Jones",
                "fight_date": "2023-03-04",
                "fighter_stats": {
                    "opponent_name": "Stipe Miocic",
                    "opponent_record": "20-4",
                    "fight_context": "title",
                    "recent_form": ["W", "W", "W", "W", "W"]
                }
            },
            priority=5
        )
        print(f"   ✅ Создан запрос: {req_id2}")

        print("\n🧪 Тест 7: Обработка запроса enrich_deepseek...")
        processed2 = worker.process_one()
        print(f"   Результат process_one(): {processed2}")

        print("\n🧪 Тест 8: Чтение ответа enrich_deepseek...")
        response2 = worker.protocol.get_response(req_id2, timeout=10)
        if response2:
            print(f"   ✅ Ответ получен:")
            print(f"      Статус: {response2['status']}")
            data_preview = response2.get('data', {})
            if data_preview:
                print(f"      wins: {data_preview.get('wins')}, losses: {data_preview.get('losses')}")
                print(f"      reach: {data_preview.get('reach_cm')}, stress: {data_preview.get('stress_factor')}")
            else:
                print("      ❌ Данные пусты")
        else:
            print("   ❌ Ответ не получен")

        # Очистка второго запроса
        print("\n🧪 Тест 9: Очистка второго запроса...")
        worker.cleanup_after_read(req_id2)
        print("   ✅ Файлы удалены")

        print("\n" + "="*70)
        print("✅ ТЕСТ ЗАВЕРШЁН!")
        print("="*70)