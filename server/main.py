#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERVER MAIN | FastAPI с SSE для стриминга
================================================================
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

# ============================================================================
# ИМПОРТЫ И ИНИЦИАЛИЗАЦИЯ ЯДРА
# ============================================================================
import math_engine
from deep_ai_analyst import DeepAIAnalyst
from mystic_calculator import calculate_mystic_factor
from secure_neural_channel import SecureNeuralChannel
from secure_keys import SecureKeys
from odds_api_client import OddsAPIClient

MASTER_PWD = "5Tgfder%$"

# 1. Инициализация защищенного канала для ИИ
if not SecureNeuralChannel.init(MASTER_PWD):
    raise RuntimeError("❌ SecureNeuralChannel не инициализирован.")
print("✅ SecureNeuralChannel инициализирован.")

# 2. Инициализация хранилища API-ключей (для букмекеров)
if SecureKeys.init(MASTER_PWD):
    print("✅ SecureKeys инициализирован.")
else:
    print("❌ Ошибка инициализации SecureKeys.")

# 3. Инициализация математического ядра
print("⚙️ Инициализация математического ядра MMAEngine...")
core_engine = math_engine.MMAEngine()
core_engine.recalibrate_scaler()
print("✅ Математическое ядро готово к работе.")

# 4. Инициализация клиента букмекеров
odds_client = OddsAPIClient()
print("✅ OddsAPIClient инициализирован.")
# ============================================================================
# ИМПОРТЫ ВНУТРЕННИХ МОДУЛЕЙ СЕРВЕРА
from .database import get_db, init_db
from .license_manager import (
    register_user, activate_license,
    check_and_decrement_balance, get_user_status
)
from .engine_pool import EnginePool

app = FastAPI(title="MMA Predictor AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ============================================================================
# 1. БЕЗОПАСНАЯ ИНИЦИАЛИЗАЦИЯ ЯДРА (ДО ИМПОРТА АДАПТЕРА)
# ============================================================================
# Добавляем корень проекта в путь, чтобы найти secure_neural_channel
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from secure_neural_channel import SecureNeuralChannel

# Инициализация без интерактивных запросов (использует существующий api_config.enc)
MASTER_PWD = "5Tgfder%$"
if not SecureNeuralChannel.init(MASTER_PWD):
    raise RuntimeError("❌ SecureNeuralChannel не инициализирован. Проверьте api_config.enc в корне проекта.")
print("✅ SecureNeuralChannel успешно инициализирован сервером.")
# ============================================================================

# 2. ИМПОРТЫ ВНУТРЕННИХ МОДУЛЕЙ СЕРВЕРА
from .database import get_db, init_db
from .license_manager import (
    register_user, activate_license,
    check_and_decrement_balance, get_user_status
)
from .engine_pool import EnginePool
from .model_adapter import get_real_prediction

app = FastAPI(title="MMA Predictor AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Модели ---
class RegisterRequest(BaseModel):
    device_id: str
    email: Optional[str] = None

class ActivateRequest(BaseModel):
    device_id: str
    key: str

class PredictRequest(BaseModel):
    device_id: str
    fighter_a: str
    fighter_b: str
    date: str
    lang: str = "ru"

class Train2aRequest(BaseModel):
    device_id: str
    period: str
    year: int
    lang: str = "ru"

class Train2bRequest(BaseModel):
    device_id: str
    date: str
    fight_indices: List[int]
    lang: str = "ru"

# --- События ---
@app.on_event("startup")
def startup():
    init_db()
    print("✅ База данных инициализирована.")

# --- Эндпоинты ---
@app.post("/api/register")
def api_register(req: RegisterRequest, db: Session = Depends(get_db)):
    return register_user(db, req.device_id, req.email)

@app.post("/api/activate")
def api_activate(req: ActivateRequest, db: Session = Depends(get_db)):
    result = activate_license(db, req.device_id, req.key)
    if not result["success"]:
        raise HTTPException(400, result["error"])
    return result

@app.get("/api/status")
def api_status(device_id: str, db: Session = Depends(get_db)):
    return get_user_status(db, device_id)

@app.get("/api/card")
async def get_card(date: str, device_id: str):
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        date_str_ddmmyyyy = date_obj.strftime("%d.%m.%Y")

        espn = await EnginePool.get_espn()
        card_fights = espn.get_fights_by_date(date_str_ddmmyyyy, verbose=False)

        if not card_fights:
            return {"status": "empty", "message": f"Нет боев на {date_str_ddmmyyyy}", "fights": []}

        fights = []
        for fight in card_fights:
            fights.append({
                "fighter_a": fight.get('fighter_a', 'Unknown'),
                "fighter_b": fight.get('fighter_b', 'Unknown'),
                "rounds": fight.get('rounds', 3),
                "is_main_event": fight.get('is_main_event', False)
            })
        return {"status": "ok", "fights": fights, "count": len(fights)}
    except Exception as e:
        return {"status": "error", "message": str(e), "fights": []}

import asyncio
import json

@app.post("/api/predict")
async def api_predict(req: PredictRequest, db: Session = Depends(get_db)):
    """Реальный прогноз с пошаговым SSE-стримингом."""

    async def generate_stream():
        # 1. Проверка баланса
        balance = check_and_decrement_balance(db, req.device_id)
        if not balance["allowed"]:
            yield f"data: {json.dumps({'type': 'error', 'message': balance['error']}, ensure_ascii=False)}\n\n"
            return

        fight_date = datetime.strptime(req.date, "%Y-%m-%d")
        enrich_date = (fight_date - timedelta(days=1)).strftime("%Y-%m-%d")

        # ШАГ 1: Сбор данных
        yield f"data: {json.dumps({'type': 'stage', 'title': ' ШАГ 1: СБОР ДАННЫХ БОЙЦОВ', 'lines': [f'⏳ Загрузка данных для {req.fighter_a}...', f'⏳ Загрузка данных для {req.fighter_b}...']}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.3)

        data_a = DeepAIAnalyst.enrich_fighter(req.fighter_a, enrich_date, req.fighter_b, "regular") or {}
        data_b = DeepAIAnalyst.enrich_fighter(req.fighter_b, enrich_date, req.fighter_a, "regular") or {}

        line1 = f"✅ {req.fighter_a}: {data_a.get('wins', 0)}-{data_a.get('losses', 0)}, {data_a.get('camp_name', 'Independent')}, reach {data_a.get('reach_cm', 180)}см"
        line2 = f"✅ {req.fighter_b}: {data_b.get('wins', 0)}-{data_b.get('losses', 0)}, {data_b.get('camp_name', 'Independent')}, reach {data_b.get('reach_cm', 180)}см"
        yield f"data: {json.dumps({'type': 'stage_complete', 'title': '🔍 ШАГ 1: СБОР ДАННЫХ БОЙЦОВ', 'lines': [line1, line2]}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)

        # ШАГ 2: Коэффициенты (РЕАЛЬНЫЙ ВЫЗОВ ODDS API)
        yield f"data: {json.dumps({'type': 'stage', 'title': '💰 ШАГ 2: КОЭФФИЦИЕНТЫ БУКМЕКЕРОВ', 'lines': ['⏳ Запрос к The Odds API...']}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.3)

        odds_result = odds_client.get_fight_odds(req.fighter_a, req.fighter_b)

        if odds_result and odds_result.get('bookmaker') != 'Нет данных':
            odds_a = odds_result.get('odds_a', 1.85)
            odds_b = odds_result.get('odds_b', 1.85)
            bookmaker = odds_result.get('bookmaker', 'Unknown')
            market_text = f"Конкурентный бой ({bookmaker})"
            odds_lines = [
                f"📈 {req.fighter_a}: {odds_a} ({bookmaker})",
                f"📈 {req.fighter_b}: {odds_b} ({bookmaker})",
                f"⚖️ Рынок: {market_text}"
            ]
        else:
            odds_a = 1.85
            odds_b = 1.85
            bookmaker = "Нет данных"
            market_text = "Конкурентный бой (дефолтные коэффициенты)"
            odds_lines = [
                f" {req.fighter_a}: {odds_a} (Средний)",
                f"📈 {req.fighter_b}: {odds_b} (Средний)",
                f"️ Рынок: {market_text}"
            ]

        yield f"data: {json.dumps({'type': 'stage_complete', 'title': '💰 ШАГ 2: КОЭФФИЦИЕНТЫ БУКМЕКЕРОВ', 'lines': odds_lines}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)

        # ШАГ 3: Математическая модель
        yield f"data: {json.dumps({'type': 'stage', 'title': '️ ШАГ 3: РАСЧЁТ ВЕРОЯТНОСТЕЙ (MATH ENGINE)', 'lines': ['⏳ Запуск математической модели...']}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)

        mystic_a = calculate_mystic_factor(data_a.get('dob', ''), enrich_date).get('mystic_factor', 0.5)
        mystic_b = calculate_mystic_factor(data_b.get('dob', ''), enrich_date).get('mystic_factor', 0.5)

        fa = math_engine.Fighter(name=req.fighter_a, dob=data_a.get('dob') or None, dob_quality=1 if data_a.get('dob') else 0, age=data_a.get('age', 30), wins=data_a.get('wins', 0), losses=data_a.get('losses', 0), recent_wins=data_a.get('recent_wins', 0), form=data_a.get('form', []), fin_rate=data_a.get('fin_rate', 0.5), sub_rate=data_a.get('sub_rate', 0.0), td_def=data_a.get('td_def', 0.5), grap_def=data_a.get('grap_def', 0.5), months_off=data_a.get('months_off', 0), fights_12m=data_a.get('fights_12m', 0), exp=data_a.get('exp', 0), reach_cm=data_a.get('reach_cm', 180), height_cm=data_a.get('height_cm', 175), stress_factor=data_a.get('stress_factor', 0.5), motivation_index=data_a.get('motivation_index', 0.5), biorythm_score=data_a.get('biorythm_score', 0.5), camp_quality=data_a.get('camp_quality', 0.5), camp_name=data_a.get('camp_name', 'Independent'), mystic_factor=mystic_a, mystic_v2=data_a.get('mystic_v2', 0.62))
        fb = math_engine.Fighter(name=req.fighter_b, dob=data_b.get('dob') or None, dob_quality=1 if data_b.get('dob') else 0, age=data_b.get('age', 30), wins=data_b.get('wins', 0), losses=data_b.get('losses', 0), recent_wins=data_b.get('recent_wins', 0), form=data_b.get('form', []), fin_rate=data_b.get('fin_rate', 0.5), sub_rate=data_b.get('sub_rate', 0.0), td_def=data_b.get('td_def', 0.5), grap_def=data_b.get('grap_def', 0.5), months_off=data_b.get('months_off', 0), fights_12m=data_b.get('fights_12m', 0), exp=data_b.get('exp', 0), reach_cm=data_b.get('reach_cm', 180), height_cm=data_b.get('height_cm', 175), stress_factor=data_b.get('stress_factor', 0.5), motivation_index=data_b.get('motivation_index', 0.5), biorythm_score=data_b.get('biorythm_score', 0.5), camp_quality=data_b.get('camp_quality', 0.5), camp_name=data_b.get('camp_name', 'Independent'), mystic_factor=mystic_b, mystic_v2=data_b.get('mystic_v2', 0.62))

        fd = math_engine.FightData(a=fa, b=fb, date=fight_date, wc="Auto", rounds=3, location="UFC", odds_a=odds_a, matchup_odds={"bookmaker": bookmaker, "odds_a": odds_a, "odds_b": odds_b})
        pred = core_engine.predict(fd)

        yield f"data: {json.dumps({'type': 'stage_complete', 'title': '⚙️ ШАГ 3: РАСЧЁТ ВЕРОЯТНОСТЕЙ (MATH ENGINE)', 'lines': [f'🎯 Сырая вероятность: {pred.prob*100:.1f}%', f'📈 Метод: {pred.method.value}', f'📊 Доверительный интервал: {pred.ci_lo*100:.1f}% - {pred.ci_hi*100:.1f}%']}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)

        # ШАГ 4: ИИ-арбитр
        yield f"data: {json.dumps({'type': 'stage', 'title': ' ШАГ 4: ИИ-АРБИТР (НЕЗАВИСИМЫЙ АНАЛИЗ)', 'lines': ['⏳ Финальная верификация прогноза...']}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)

        stats_a = f"{data_a.get('wins', 0)}-{data_a.get('losses', 0)}, reach={data_a.get('reach_cm', 180)}см, camp={data_a.get('camp_name', 'Independent')}"
        stats_b = f"{data_b.get('wins', 0)}-{data_b.get('losses', 0)}, reach={data_b.get('reach_cm', 180)}см, camp={data_b.get('camp_name', 'Independent')}"

        ai_prompt = f"""Проанализируй бой ММА между {req.fighter_a} и {req.fighter_b}.

Данные бойцов:
- {req.fighter_a}: {stats_a}
- {req.fighter_b}: {stats_b}

Математическая модель прогнозирует: {pred.winner} с вероятностью {pred.prob*100:.1f}%
Коэффициенты букмекеров: {req.fighter_a}={odds_a}, {req.fighter_b}={odds_b} ({bookmaker})

Кто победит и почему? Дай развёрнутый анализ на 2-3 предложения. Ответь СТРОГО в формате JSON:
{{"winner": "имя победителя", "confidence": 72, "reason": "причина победы"}}"""

        ai_response = SecureNeuralChannel.query(
            prompt=ai_prompt,
            system_prompt="Ты эксперт по ММА. Анализируй бои на основе статистики. Отвечай СТРОГО в JSON формате без markdown.",
            use_cache=True,
            temperature=0.7
        )

        ai_winner = req.fighter_a
        ai_confidence = 70
        ai_reason = "Анализ недоступен"

        if ai_response:
            if isinstance(ai_response, dict):
                ai_winner = ai_response.get('winner', req.fighter_a)
                ai_confidence = ai_response.get('confidence', 70)
                ai_reason = ai_response.get('reason', 'Анализ недоступен')
            elif isinstance(ai_response, str):
                try:
                    import re as re_module
                    match = re_module.search(r'\{.*\}', ai_response, re_module.DOTALL)
                    if match:
                        parsed = json.loads(match.group())
                        ai_winner = parsed.get('winner', req.fighter_a)
                        ai_confidence = parsed.get('confidence', 70)
                        ai_reason = parsed.get('reason', 'Анализ недоступен')
                except:
                    ai_reason = ai_response[:200]

        # === ВЕРДИКТ (ТРОЙНОЙ АРБИТРАЖ — как в консоли) ===
        model_prob = pred.prob
        model_winner = pred.winner

        # Определяем фаворита букмекера (меньший коэффициент = фаворит)
        if odds_a < odds_b:
            bookmaker_favorite = req.fighter_a
        elif odds_b < odds_a:
            bookmaker_favorite = req.fighter_b
        else:
            bookmaker_favorite = "Ничья"

        # Считаем совпадения
        agreements = 0
        if ai_winner == model_winner:
            agreements += 1
        if bookmaker_favorite == model_winner:
            agreements += 1

        # Формируем вердикт по правилу тройного арбитража (как в консоли)
        if agreements == 2:
            # Все три согласны (модель + ИИ + букмекер)
            verdict = "РЕКОМЕНДУЮ"
            verdict_reason = f"Полное совпадение: Математика, ИИ и БК единогласны за {model_winner} (3 из 3)"
        elif agreements == 1:
            if ai_winner == model_winner:
                # Модель и ИИ согласны, но букмекер против → ВАЛУЙ
                verdict = "ВАЛУЙ"
                verdict_reason = f"Математика и ИИ за {model_winner}, но БК за {bookmaker_favorite}. Рынок ошибается!"
            elif bookmaker_favorite == model_winner:
                # Модель и БК согласны, но ИИ против → СЛАБАЯ РЕКОМЕНДАЦИЯ
                verdict = "СЛАБАЯ РЕКОМЕНДАЦИЯ"
                verdict_reason = f"Математика и БК за {model_winner}, но ИИ предупреждает о рисках ({ai_winner})."
            else:
                verdict = "СПОРНЫЙ"
                verdict_reason = "Расхождение между всеми тремя источниками"
        else:
            # Только модель поддерживает своего бойца
            if model_prob > 0.60:
                verdict = "РЕКОМЕНДУЮ"
                verdict_reason = f"Высокая уверенность модели ({model_prob*100:.1f}%) за {model_winner}"
            elif model_prob > 0.50:
                verdict = "СЛАБАЯ РЕКОМЕНДАЦИЯ"
                verdict_reason = f"Небольшое преимущество модели ({model_prob*100:.1f}%) за {model_winner}"
            else:
                verdict = "ПРОПУСТИТЬ"
                verdict_reason = f"Низкая уверенность модели ({model_prob*100:.1f}%)"

        yield f"data: {json.dumps({'type': 'stage_complete', 'title': ' ШАГ 4: ИИ-АРБИТР (НЕЗАВИСИМЫЙ АНАЛИЗ)', 'lines': [f'🧠 ИИ выбирает: {ai_winner} ({ai_confidence}%)', f'💬 Причина: {ai_reason}']}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)

        # ФИНАЛЬНЫЙ РЕЗУЛЬТАТ
        final_data = {
            "type": "final_result",
            "winner": pred.winner,
            "probability": round(pred.prob * 100, 1),
            "method": pred.method.value,
            "round": pred.rnd,
            "confidence_interval": f"{round(pred.ci_lo * 100, 1)}% - {round(pred.ci_hi * 100, 1)}%",
            "fighters_data": {
                "fighter_a": req.fighter_a,
                "fighter_b": req.fighter_b,
                "stats_a": stats_a,
                "stats_b": stats_b,
                "wins_a": data_a.get('wins', 0),
                "losses_a": data_a.get('losses', 0),
                "camp_a": data_a.get('camp_name', 'Independent'),
                "wins_b": data_b.get('wins', 0),
                "losses_b": data_b.get('losses', 0),
                "camp_b": data_b.get('camp_name', 'Independent')
            },
            "odds_a": odds_a,
            "odds_b": odds_b,
            "bookmaker": bookmaker,
            "bookmaker_favorite": bookmaker_favorite,
            "market_assessment": market_text,
            "ai_winner": ai_winner,
            "ai_confidence": ai_confidence,
            "ai_reason": ai_reason,
            "agreements": agreements,
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "balance_remaining": balance.get("balance", 0)
        }
        yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@app.post("/api/train/2a")
async def api_train_2a(req: Train2aRequest, db: Session = Depends(get_db)):
    """Обучение 2a с SSE-стримингом этапов."""
    status = get_user_status(db, req.device_id)
    if not status.get("exists"):
        raise HTTPException(404, "Пользователь не найден")

    limit_check = EnginePool.check_training_limit(req.device_id, status.get("plan", "free"))
    if not limit_check["allowed"]:
        raise HTTPException(403, limit_check["reason"])

    # Генератор для потоковой передачи данных (SSE)
    async def generate_stream():
        from .model_adapter import run_training_2a_stream
        for chunk in run_training_2a_stream(req.period, str(req.year)):
            yield chunk

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@app.post("/api/train/2b")
async def api_train_2b(req: Train2bRequest, db: Session = Depends(get_db)):
    """Проверка модели (бэктест) с возвратом детального JSON."""
    status = get_user_status(db, req.device_id)
    if not status.get("exists"):
        raise HTTPException(404, "Пользователь не найден")

    limit_check = EnginePool.check_training_limit(req.device_id, status.get("plan", "free"))
    if not limit_check["allowed"]:
        raise HTTPException(403, limit_check["reason"])

    try:
        from .model_adapter import run_training_2b
        result = run_training_2b(req.date, req.fight_indices)

        if not result.get("success"):
            raise HTTPException(500, result.get("error", "Ошибка обучения"))

        return {
            "status": "ok",
            "message": result["message"],
            "date": result["date"],
            "total_fights": result["total_fights"],
            "correct": result["correct"],
            "incorrect": result["incorrect"],
            "accuracy": result["accuracy"],
            "details": result.get("details", [])  # ← Массив с деталями по каждому бою
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Ошибка обучения: {str(e)}")