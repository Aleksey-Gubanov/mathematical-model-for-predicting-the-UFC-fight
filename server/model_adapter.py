#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERVER MODEL ADAPTER | Запуск mma_predictor_bridge.py через subprocess
================================================================
Веб общается ТОЛЬКО с файлом управления mma_predictor_bridge.py
ВСЕ вызовы защищены от зависания (stdin=DEVNULL) и ошибок кодировки.
================================================================
"""
import subprocess
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any

# Путь к mma_predictor_bridge.py
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE_PATH = os.path.join(ROOT_DIR, "mma_predictor_bridge.py")

# Флаг для Windows: предотвращает создание лишнего окна консоли и зависание
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

def _run_bridge(args: list) -> Dict[str, Any]:
    """Универсальная функция запуска bridge с максимальной защитой."""
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        result = subprocess.run(
            [sys.executable, BRIDGE_PATH] + args,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ROOT_DIR,
            env=env,
            encoding='utf-8',
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )

        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)

        if result.returncode != 0:
            return {"success": False, "error": f"Ошибка (код {result.returncode}): {result.stderr[:300]}"}

        output = result.stdout.strip()
        json_start = output.find('{')
        json_end = output.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return {"success": False, "error": f"Не удалось получить JSON. Вывод: {output[:300]}"}

        data = json.loads(output[json_start:json_end])

        if "error" in data:
            return {"success": False, "error": data["error"]}

        return {"success": True, "data": data}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Таймаут выполнения (300 сек)"}
    except Exception as e:
        return {"success": False, "error": f"Ошибка: {str(e)}"}


def get_real_prediction(fighter_a: str, fighter_b: str, date_str: str) -> Dict[str, Any]:
    """Режим 1: Прогноз"""
    date_ddmmyyyy = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    print(f"🔍 Запуск bridge: {fighter_a} vs {fighter_b} на {date_ddmmyyyy}")

    res = _run_bridge(['--predict', fighter_a, fighter_b, date_ddmmyyyy])
    if not res["success"]:
        return res

    d = res["data"]
    return {
        "success": True,
        "prediction": {
            "winner": d.get("winner", ""),
            "probability_percent": round(d.get("probability", 0) * 100, 2),
            "method": d.get("method", "Решение"),
            "round": d.get("round", 3),
            "confidence_interval": f"{round(d.get('ci_lo', 0)*100, 1)}% - {round(d.get('ci_hi', 0)*100, 1)}%"
        },
        "odds_a": d.get("odds_a", 1.85),
        "odds_b": d.get("odds_b", 1.85),
        "bookmaker": d.get("bookmaker", "Нет данных"),
        "ai_winner": d.get("ai_winner", ""),
        "ai_confidence": d.get("ai_confidence", 0),
        "ai_reason": d.get("ai_reason", ""),
        "verdict": d.get("verdict", ""),
        "verdict_reason": d.get("verdict_reason", ""),
        "stats_a": d.get("stats_a", ""),
        "stats_b": d.get("stats_b", ""),
        "fighters_data": {
            "fighter_a": fighter_a,
            "fighter_b": fighter_b
        }
    }


def run_training_2a_stream(period: str, year: str):
    """Запускает обучение 2a и возвращает генератор SSE."""
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        process = subprocess.Popen(
            [sys.executable, BRIDGE_PATH, '--train2a', period, year],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=ROOT_DIR,
            env=env,
            encoding='utf-8',
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )

        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "stage":
                    # ✅ Исправлено: формируем словарь отдельно, чтобы избежать SyntaxError
                    current = data.get("current", 0)
                    total = data.get("total", 0)
                    title = f"Обработка боя {current}/{total}"
                    payload = {"type": "stage", "title": title, "lines": ["⏳ Анализ..."]}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                elif "status" in data:
                    payload = {"type": "final_result", "data": data}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            except json.JSONDecodeError:
                # Не JSON строка (например, лог) - пропускаем
                continue
            except Exception as e:
                print(f"⚠️ Ошибка обработки строки: {e}")
                continue

        process.wait()

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


def run_training_2b(date_str: str, fight_indices: list) -> Dict[str, Any]:
    """Режим 2b: Бэктест по дате"""
    print(f"🔍 Запуск обучения 2b: дата {date_str}, бои {fight_indices}")

    res = _run_bridge(['--train2b', date_str, json.dumps(fight_indices)])
    if not res["success"]:
        return res

    d = res["data"]
    print(f"✅ Обучение 2b завершено: {d.get('message', '')}")

    return {
        "success": True,
        "message": d.get("message", ""),
        "date": d.get("date", ""),
        "total_fights": d.get("total_fights", 0),
        "correct": d.get("correct", 0),
        "incorrect": d.get("incorrect", 0),
        "accuracy": d.get("accuracy", 0.0),
        "details": d.get("details", [])   # ← ДОБАВЛЕНО: передача деталей по каждому бою
    }