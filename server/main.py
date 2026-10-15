#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERVER MAIN | FastAPI с SSE для стриминга
================================================================
Прогноз считается ТОЛЬКО эталонным конвейером mma_predictor_bridge.py
через server/model_adapter.py. Математика, ИИ-арбитр и букмекеры независимы.
================================================================
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Корень проекта в пути поиска корневых модулей
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ============================================================================
# ИМПОРТЫ И ИНИЦИАЛИЗАЦИЯ ЯДРА (прогрев при старте)
# ============================================================================
import math_engine
from deep_ai_analyst import DeepAIAnalyst
from mystic_calculator import calculate_mystic_factor
from secure_neural_channel import SecureNeuralChannel
from secure_keys import SecureKeys
from odds_api_client import OddsAPIClient

MASTER_PWD = "5Tgfder%$"

if not SecureNeuralChannel.init(MASTER_PWD):
    raise RuntimeError("❌ SecureNeuralChannel не инициализирован.")
print("✅ SecureNeuralChannel инициализирован.")

if SecureKeys.init(MASTER_PWD):
    print("✅ SecureKeys инициализирован.")
else:
    print("❌ Ошибка инициализации SecureKeys.")

print("️ Инициализация математического ядра MMAEngine...")
core_engine = math_engine.MMAEngine()
core_engine.recalibrate_scaler()
print("✅ Математическое ядро готово к работе.")

odds_client = OddsAPIClient()
print("✅ OddsAPIClient инициализирован.")

# ============================================================================
# ИМПОРТЫ ВНУТРЕННИХ МОДУЛЕЙ СЕРВЕРА
# ============================================================================
from .database import get_db, init_db
from .license_manager import (
    register_user, activate_license,
    check_and_decrement_balance, get_user_status, refund_balance
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


class SmsWebhookRequest(BaseModel):
    text: str
    sender: str = ""


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

@app.post("/api/predict")
async def api_predict(req: PredictRequest, db: Session = Depends(get_db)):
    """Эталонный прогноз: ВСЕ расчёты выполняет mma_predictor_bridge.py."""

    async def generate_stream():
        # 1. Проверка и списание баланса
        balance = check_and_decrement_balance(db, req.device_id)
        if not balance["allowed"]:
            yield f"data: {json.dumps({'type': 'error', 'message': balance['error']}, ensure_ascii=False)}\n\n"
            return

        yield f"data: {json.dumps({'type': 'stage', 'title': '🚀 ЭТАЛОННЫЙ КОНВЕЙЕР (bridge)', 'lines': [f'⏳ {req.fighter_a} vs {req.fighter_b} на {req.date}', '⏳ Математика → ИИ-арбитр → Букмекеры: независимые источники']}, ensure_ascii=False)}\n\n"

        # 2. ЕДИНСТВЕННЫЙ источник расчёта — эталонный bridge
        result = await asyncio.to_thread(get_real_prediction, req.fighter_a, req.fighter_b, req.date)

        if not result.get("success"):
            refund_balance(db, req.device_id)
            yield f"data: {json.dumps({'type': 'error', 'message': result.get('error', 'Эталонный расчёт не выполнен')}, ensure_ascii=False)}\n\n"
            return

        pred = result.get("prediction", {})
        stats_a = result.get("stats_a", "")
        stats_b = result.get("stats_b", "")
        odds_a = result.get("odds_a", 1.85)
        odds_b = result.get("odds_b", 1.85)
        bookmaker = result.get("bookmaker", "Нет данных")
        ai_winner = result.get("ai_winner", "")
        ai_confidence = result.get("ai_confidence", 0)
        ai_reason = result.get("ai_reason", "")
        verdict = result.get("verdict", "")
        verdict_reason = result.get("verdict_reason", "")
        model_winner = pred.get("winner", "")
        probability = pred.get("probability_percent", 0.0)
        method = pred.get("method", "")
        rnd = pred.get("round", 3)
        ci = pred.get("confidence_interval", "")

        # ШАГ 1: данные бойцов (из эталона)
        yield f"data: {json.dumps({'type': 'stage_complete', 'title': '🔍 ШАГ 1: СБОР ДАННЫХ БОЙЦОВ', 'lines': [f'✅ {req.fighter_a}: {stats_a}', f'✅ {req.fighter_b}: {stats_b}']}, ensure_ascii=False)}\n\n"

        # ШАГ 2: букмекеры (из эталона)
        if odds_a < odds_b:
            bookmaker_favorite = req.fighter_a
        elif odds_b < odds_a:
            bookmaker_favorite = req.fighter_b
        else:
            bookmaker_favorite = "Ничья"

        if bookmaker != "Нет данных":
            market_text = f"Конкурентный бой ({bookmaker})"
            odds_lines = [
                f"📈 {req.fighter_a}: {odds_a} ({bookmaker})",
                f"📈 {req.fighter_b}: {odds_b} ({bookmaker})",
                f"⚖️ Рынок: {market_text}"
            ]
        else:
            market_text = "Конкурентный бой (дефолтные коэффициенты)"
            odds_lines = [
                f"📈 {req.fighter_a}: {odds_a} (Средний)",
                f"📈 {req.fighter_b}: {odds_b} (Средний)",
                f"⚖️ Рынок: {market_text}"
            ]
        yield f"data: {json.dumps({'type': 'stage_complete', 'title': '💰 ШАГ 2: КОЭФФИЦИЕНТЫ БУКМЕКЕРОВ', 'lines': odds_lines}, ensure_ascii=False)}\n\n"

        # ШАГ 3: математика (из эталона)
        yield f"data: {json.dumps({'type': 'stage_complete', 'title': '⚙️ ШАГ 3: РАСЧЁТ ВЕРОЯТНОСТЕЙ (MATH ENGINE)', 'lines': [f'🎯 Сырая вероятность: {probability:.1f}%', f'📈 Метод: {method}', f'📊 Доверительный интервал: {ci}']}, ensure_ascii=False)}\n\n"

        # ШАГ 4: ИИ-арбитр (из эталона, НЕЗАВИСИМЫЙ)
        yield f"data: {json.dumps({'type': 'stage_complete', 'title': '🧠 ШАГ 4: ИИ-АРБИТР (НЕЗАВИСИМЫЙ АНАЛИЗ)', 'lines': [f'🧠 ИИ выбирает: {ai_winner} ({ai_confidence}%)', f'💬 Причина: {ai_reason}']}, ensure_ascii=False)}\n\n"

        # Совпадения для отображения (не влияют на вердикт: вердикт пришёл из эталона)
        agreements = (1 if ai_winner == model_winner else 0) + (1 if bookmaker_favorite == model_winner else 0)

        final_data = {
            "type": "final_result",
            "winner": model_winner,
            "probability": probability,
            "method": method,
            "round": rnd,
            "confidence_interval": ci,
            "fighters_data": {
                "fighter_a": req.fighter_a,
                "fighter_b": req.fighter_b,
                "stats_a": stats_a,
                "stats_b": stats_b,
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

    async def generate_stream():
        from .model_adapter import run_training_2a_stream
        for chunk in run_training_2a_stream(req.period, str(req.year)):
            yield chunk

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@app.post("/api/train/2b")
async def api_train_2b(req: Train2bRequest, db: Session = Depends(get_db)):
    """Проверка модели (бэктест) с SSE-стримингом."""
    status = get_user_status(db, req.device_id)
    if not status.get("exists"):
        raise HTTPException(404, "Пользователь не найден")

    limit_check = EnginePool.check_training_limit(req.device_id, status.get("plan", "free"))
    if not limit_check["allowed"]:
        raise HTTPException(403, limit_check["reason"])

    async def generate_stream():
        from .model_adapter import run_training_2b_stream
        for chunk in run_training_2b_stream(req.date, req.fight_indices):
            yield chunk

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


# === ВЕБХУК SMS-ОПЛАТ (MacroDroid → сервер) ===
WEBHOOK_SECRET = "mma_sms_webhook_2026_secret"

@app.post("/webhook/sms-payment")
async def sms_webhook(req: SmsWebhookRequest, request: Request):
    """Принимает текст SMS от MacroDroid. Пока только логирует."""
    secret = request.headers.get("X-Webhook-Secret", "")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(403, "Неверный секрет вебхука")
    line = f"{datetime.now().isoformat()} | sender={req.sender} | {req.text}"
    with open("/app/sms_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"📩 SMS-вебхук: {line}")
    return {"status": "logged"}
