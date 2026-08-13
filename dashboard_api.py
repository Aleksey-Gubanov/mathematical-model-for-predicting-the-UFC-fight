#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DASHBOARD API v3.1 | Пошаговое отображение процесса
================================================================
Добавлено: массив steps в ответе API для визуализации прогресса
================================================================
"""
import sys
import os
import re
import json
import uuid
import platform
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from secure_neural_channel import SecureNeuralChannel
    from math_engine import Fighter, FightData, Prediction, Result, FinishType, MMAEngine, names_match
    from ufc_parser import UFCParser
    from deep_ai_analyst import DeepAIAnalyst
    from sports_parser import SportsUFCScheduler
    from cryptography.fernet import Fernet
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    sys.exit(1)

app = FastAPI(title="MMA PREDICTOR DASHBOARD", version="3.1")

class InitRequest(BaseModel):
    password: str

class AnalyzeRequest(BaseModel):
    fighter1: str
    fighter2: str
    mode: str

class AgreementRequest(BaseModel):
    agreed: bool

class ApiKeyRequest(BaseModel):
    api_key: str

# ==============================================================================
# БЕЗОПАСНОСТЬ
# ==============================================================================
CONFIG_FILE = "mma_secure_config.enc"
DEV_API_KEY = "sk-your-dev-key-here"
MAX_DEV_PREDICTIONS = 100

def get_hwid() -> str:
    return hashlib.sha256(f"{uuid.getnode()}_{platform.platform()}".encode()).hexdigest()

def get_cipher(hwid: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(hwid.encode()).digest()))

def load_config(hwid: str) -> dict:
    default = {"hwid": hwid, "api_key": "", "predictions_used": 0, "is_agreed": False}
    if not os.path.exists(CONFIG_FILE): return default
    try:
        config = json.loads(get_cipher(hwid).decrypt(open(CONFIG_FILE, "rb").read()).decode('utf-8'))
        return config if config.get("hwid") == hwid else default
    except: return default

def save_config(config: dict, hwid: str):
    with open(CONFIG_FILE, "wb") as f:
        f.write(get_cipher(hwid).encrypt(json.dumps(config).encode('utf-8')))

def check_api_access(config: dict) -> Tuple[str, str]:
    if not config.get("is_agreed"): return "", "agreement_required"
    user_key = config.get("api_key", "").strip()
    if user_key and user_key != DEV_API_KEY: return user_key, "ok"
    if config.get("predictions_used", 0) >= MAX_DEV_PREDICTIONS: return "", "limit_reached"
    return DEV_API_KEY, "ok"

def increment_prediction_count(config: dict, hwid: str):
    if config.get("api_key", "").strip() in ["", DEV_API_KEY]:
        config["predictions_used"] = config.get("predictions_used", 0) + 1
        save_config(config, hwid)

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def sanitize_fighter_name(raw_name: str) -> str:
    if not raw_name: return ""
    cleaned = re.sub(r'\s*\([^)]*\)', '', raw_name)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def clean_user_input(raw_input: str) -> str:
    if not raw_input: return ""
    cleaned = raw_input.replace('—', '-').replace('–', '-').replace('−', '-')
    cleaned = cleaned.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').replace('\xa0', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def canonicalize_names_with_db(raw_input: str, known_fighters: List[str]) -> Optional[Dict[str, str]]:
    unique_fighters = list(set(known_fighters))[:500]
    fighters_list_str = ", ".join(unique_fighters)

    prompt = f"""Ты эксперт по ММА. Пользователь ввел строку: "{raw_input}".
Вот официальный список имен бойцов из базы: [{fighters_list_str}].
Твоя задача: найти в этом списке РОВНО ДВА имени, которые соответствуют вводу пользователя.
Верни СТРОГО валидный JSON без markdown:
{{"f1": "Точное имя из списка", "f2": "Точное имя из списка"}}
Если не можешь найти два имени, верни: {{"f1": null, "f2": null}}"""

    try:
        response = SecureNeuralChannel.query(prompt, "CanonicalizeNamesWithDB")
        if isinstance(response, dict):
            data = response
        else:
            clean_response = str(response).replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', clean_response, re.DOTALL)
            data = json.loads(match.group()) if match else {}

        f1 = data.get("f1")
        f2 = data.get("f2")

        if f1 and f2 and str(f1).lower() != "null" and str(f2).lower() != "null":
            return {"f1": str(f1).strip(), "f2": str(f2).strip()}
        return None
    except Exception as e:
        print(f"⚠️ Ошибка ИИ при коррекции имен: {e}")
        return None

# ==============================================================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# ==============================================================================
engine: Optional[MMAEngine] = None
parser: Optional[UFCParser] = None
analyst: Optional[DeepAIAnalyst] = None
scheduler: Optional[SportsUFCScheduler] = None
known_fighters_forecast: List[str] = []
known_fighters_training: List[str] = []
is_initialized: bool = False
current_hwid: str = ""
config: dict = {}

# ==============================================================================
# ЭНДПОИНТЫ
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(html_path):
        return HTMLResponse("<h1>Ошибка: templates/index.html не найден</h1>", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/agreement")
async def accept_agreement(request: AgreementRequest):
    global config, current_hwid
    if not current_hwid: current_hwid = get_hwid()
    config = load_config(current_hwid)
    if request.agreed:
        config["is_agreed"] = True
        save_config(config, current_hwid)
        return {"status": "success"}
    return {"status": "error"}

@app.post("/api/set_api_key")
async def set_api_key(request: ApiKeyRequest):
    global config, current_hwid
    if not current_hwid: current_hwid = get_hwid()
    config = load_config(current_hwid)
    config["api_key"] = request.api_key.strip()
    save_config(config, current_hwid)
    SecureNeuralChannel.set_custom_api_key(config["api_key"])
    return {"status": "success"}

@app.post("/api/init")
async def init_system(request: InitRequest):
    global engine, parser, analyst, scheduler
    global known_fighters_forecast, known_fighters_training, is_initialized, current_hwid, config

    if is_initialized:
        return {"status": "already_initialized"}

    current_hwid = get_hwid()
    config = load_config(current_hwid)

    if not config.get("is_agreed"):
        return {"status": "agreement_required"}

    api_key, status = check_api_access(config)
    if status == "limit_reached":
        return {"status": "limit_reached"}

    if config.get("api_key") and config["api_key"] != DEV_API_KEY:
        SecureNeuralChannel.set_custom_api_key(config["api_key"])

    if not SecureNeuralChannel.init(request.password):
        raise HTTPException(status_code=401, detail="Неверный мастер-пароль")

    engine = MMAEngine()
    parser = UFCParser()
    analyst = DeepAIAnalyst()
    scheduler = SportsUFCScheduler()

    try:
        all_fights = scheduler.parse_schedule()
        known_fighters_forecast = []
        for f in all_fights:
            if f.get('fighter1'): known_fighters_forecast.append(f['fighter1'])
            if f.get('fighter2'): known_fighters_forecast.append(f['fighter2'])
    except Exception as e:
        print(f"⚠️ Не удалось загрузить расписание: {e}")

    try:
        known_fighters_training = parser.get_all_known_fighters()
    except Exception as e:
        print(f"⚠️ Не удалось загрузить историю: {e}")

    is_initialized = True
    return {"status": "success"}

@app.get("/api/status")
async def get_status():
    if not is_initialized or not engine:
        return {"accuracy": 0.0, "stability": 0.0, "total_fights": 0, "initialized": False}

    try:
        if os.path.exists("mma_weights_v21.json"):
            with open("mma_weights_v21.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "accuracy": data.get('loocv_accuracy', 0.0) * 100,
                "stability": data.get('stability_score', 0.0),
                "total_fights": data.get('trained_on_fights', 0),
                "initialized": True,
                "predictions_used": config.get("predictions_used", 0),
                "predictions_limit": MAX_DEV_PREDICTIONS
            }
    except:
        pass

    return {"accuracy": 0.0, "stability": 0.0, "total_fights": 0, "initialized": True}

@app.post("/api/analyze")
async def analyze_fight(request: AnalyzeRequest):
    """Основная логика с пошаговым отображением"""
    if not is_initialized:
        raise HTTPException(status_code=400, detail="Система не инициализирована")

    api_key, status = check_api_access(config)
    if status == "limit_reached" and request.mode == "forecast":
        raise HTTPException(status_code=403, detail="Лимит исчерпан")

    f1_raw = request.fighter1.strip()
    f2_raw = request.fighter2.strip()
    mode = request.mode

    if not f1_raw or not f2_raw:
        raise HTTPException(status_code=400, detail="Введите имена обоих бойцов")

    # Массив шагов для визуализации
    steps = []

    user_in = clean_user_input(f"{f1_raw} - {f2_raw}")

    # Шаг 1: ИИ-коррекция
    steps.append({"icon": "🔍", "text": "ИИ анализирует ввод и сопоставляет с базой...", "status": "running"})
    current_db = known_fighters_training if mode == "training" else known_fighters_forecast
    names = canonicalize_names_with_db(user_in, current_db)

    if not names:
        steps[-1]["status"] = "error"
        steps[-1]["text"] = "❌ Не удалось распознать имена бойцов"
        raise HTTPException(status_code=400, detail="Не удалось распознать имена")

    f1_clean = names["f1"]
    f2_clean = names["f2"]
    steps[-1]["status"] = "success"
    steps[-1]["text"] = f"✅ Имена распознаны: {f1_clean} vs {f2_clean}"

    try:
        # ======================================================================
        # РЕЖИМ ОБУЧЕНИЕ
        # ======================================================================
        if mode == "training":
            # Шаг 2: Поиск факта
            steps.append({"icon": "📄", "text": "Поиск исторического факта в архиве...", "status": "running"})
            fact = parser.get_fight_result(f1_clean, f2_clean)

            if not fact or 'winner' not in fact:
                steps[-1]["status"] = "error"
                steps[-1]["text"] = "❌ Бой не найден в архиве"
                raise HTTPException(status_code=404, detail="Бой не найден в архиве")

            steps[-1]["status"] = "success"
            steps[-1]["text"] = f"✅ Факт найден: {fact['date'].strftime('%d.%m.%Y')} | {fact['winner']} ({fact['method']}, R{fact['round']})"

            # Шаг 3: Сбор статистики
            target_date = (fact['date'] - timedelta(days=1)).strftime("%Y-%m-%d")
            steps.append({"icon": "🧠", "text": f"ИИ собирает предматчевую статистику на {target_date}...", "status": "running"})
            fa = analyst.get_fighter_deep_stats(f1_clean, target_date)
            fb = analyst.get_fighter_deep_stats(f2_clean, target_date)

            if not fa or not fb:
                steps[-1]["status"] = "error"
                steps[-1]["text"] = "❌ Не удалось получить статистику"
                raise HTTPException(status_code=500, detail="Ошибка сбора статистики")

            steps[-1]["status"] = "success"
            steps[-1]["text"] = "✅ Статистика собрана"

            fd = FightData(
                a=fa, b=fb, date=fact['date'], wc="Auto",
                rounds=int(fact.get('round', 3)),
                location=fact.get('tournament', 'UFC'),
                odds_a=1.85,
                matchup_odds={"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85}
            )

            meth_map = {
                'UD': FinishType.DECISION_UNANIMOUS, 'SD': FinishType.DECISION_SPLIT,
                'MD': FinishType.DECISION_SPLIT, 'DEC': FinishType.DECISION_UNANIMOUS,
                'TKO': FinishType.TKO, 'KO': FinishType.KO, 'SUB': FinishType.SUBMISSION
            }
            res = Result(
                winner=fact['winner'], rnd=int(fact['round']),
                method=meth_map.get(str(fact['method']).upper(), FinishType.DECISION_UNANIMOUS)
            )

            # Шаг 4: Расчет прогноза
            steps.append({"icon": "⚙️", "text": "Расчет прогноза моделью...", "status": "running"})
            pred = engine.predict(fd)
            steps[-1]["status"] = "success"
            steps[-1]["text"] = f"✅ Прогноз: {pred.winner} ({pred.method.value}, R{pred.rnd})"

            # Шаг 5: Обучение
            steps.append({"icon": "🔄", "text": "Инкрементальное обучение...", "status": "running"})
            train_result = engine.train_on_new_fight(fd, res, f1_clean, f2_clean)

            acc_win, acc_rnd, acc_mth = 0.0, 0.0, 0.0
            training_log = ""

            if train_result and train_result.get("status") == "updated":
                acc_win, acc_rnd, acc_mth = train_result["acc_win"], train_result["acc_rnd"], train_result["acc_mth"]
                training_log = f"{train_result['corrections']}\n{train_result['accuracy_str']}\n💾 Веса сохранены"
                steps[-1]["status"] = "success"
                steps[-1]["text"] = "✅ Веса обновлены, датасет расширен"
            elif train_result and train_result.get("status") == "exists":
                steps[-1]["status"] = "warning"
                steps[-1]["text"] = "ℹ️ Бой уже есть в датасете"
                if os.path.exists("hlam proshloe/RRRreal_dataset.json"):
                    with open("hlam proshloe/RRRreal_dataset.json", "r", encoding="utf-8") as f:
                        acc_win, acc_rnd, acc_mth = engine.get_recent_accuracies(json.load(f))

            return {
                "mode": mode,
                "fighter1_clean": f1_clean,
                "fighter2_clean": f2_clean,
                "event_name": fact.get('tournament', 'UFC'),
                "event_date": fact['date'].strftime("%d.%m.%Y"),
                "rounds": fact.get('round', 3),
                "prediction": {
                    "winner": pred.winner if pred.method != FinishType.DRAW else "Ничья",
                    "prob": int(pred.prob * 100),
                    "margin": int((pred.ci_hi - pred.ci_lo) * 100),
                    "rnd": pred.rnd,
                    "method": pred.method.value
                },
                "fact": {"winner": res.winner, "rnd": res.rnd, "method": res.method.value},
                "accuracy": {"win": acc_win, "rnd": acc_rnd, "method": acc_mth},
                "odds": {
                    "model_f1": 1.0 / max(pred.prob, 0.01),
                    "model_f2": 1.0 / max(1 - pred.prob, 0.01),
                    "book_f1": "Уточняется", "book_f2": "Уточняется", "bookmaker": "—"
                },
                "training_log": training_log,
                "steps": steps
            }

        # ======================================================================
        # РЕЖИМ ПРОГНОЗ
        # ======================================================================
        else:
            target = datetime.now().strftime("%Y-%m-%d")
            f1_clean_for_ai = sanitize_fighter_name(f1_clean)
            f2_clean_for_ai = sanitize_fighter_name(f2_clean)

            # Шаг 2: Сбор статистики
            steps.append({"icon": "🧠", "text": "ИИ собирает текущую статистику бойцов...", "status": "running"})
            fa = analyst.get_fighter_deep_stats(f1_clean_for_ai, target)
            fb = analyst.get_fighter_deep_stats(f2_clean_for_ai, target)

            if not fa or not fb:
                steps[-1]["status"] = "error"
                steps[-1]["text"] = "❌ Не удалось получить статистику"
                raise HTTPException(status_code=500, detail="Ошибка сбора статистики")

            steps[-1]["status"] = "success"
            steps[-1]["text"] = "✅ Статистика собрана"

            # Шаг 3: Поиск боя
            steps.append({"icon": "📅", "text": "Поиск боя в расписании...", "status": "running"})
            fight_info = scheduler.find_fight(f1_clean_for_ai, f2_clean_for_ai)

            if not fight_info:
                fight_info = {
                    'event_name': 'UFC Fight Night',
                    'event_date': datetime.now().strftime("%d.%m.%Y"),
                    'rounds': 3, 'location': 'UFC',
                    'odds_a': 1.85, 'odds_b': 1.85, 'bookmaker': 'Нейтрально'
                }
                steps[-1]["status"] = "warning"
                steps[-1]["text"] = "⚠️ Бой не найден, используются данные по умолчанию"
            else:
                steps[-1]["status"] = "success"
                steps[-1]["text"] = f"✅ Бой найден: {fight_info['event_name']}"

            ev_date = datetime.strptime(fight_info['event_date'], "%d.%m.%Y")
            rounds = int(fight_info.get('rounds', 3))

            try:
                odds_a_num = float(fight_info.get('odds_a', 1.85))
            except:
                odds_a_num = 1.85
            try:
                odds_b_num = float(fight_info.get('odds_b', 1.85))
            except:
                odds_b_num = 1.85

            matchup = {
                "bookmaker": fight_info.get('bookmaker', 'Нейтрально'),
                "odds_a": odds_a_num, "odds_b": odds_b_num
            }

            fd = FightData(
                a=fa, b=fb, date=ev_date, wc="Auto", rounds=rounds,
                location=fight_info.get('location', 'UFC'),
                odds_a=odds_a_num, matchup_odds=matchup
            )

            # Шаг 4: Расчет прогноза
            steps.append({"icon": "⚙️", "text": "Расчет прогноза моделью...", "status": "running"})
            pred = engine.predict(fd)
            steps[-1]["status"] = "success"
            steps[-1]["text"] = f"✅ Прогноз готов: {pred.winner} ({int(pred.prob*100)}%)"

            acc_win, acc_rnd, acc_mth = 0.0, 0.0, 0.0
            if os.path.exists("hlam proshloe/RRRreal_dataset.json"):
                try:
                    with open("hlam proshloe/RRRreal_dataset.json", "r", encoding="utf-8") as f:
                        dataset = json.load(f)
                    acc_win, acc_rnd, acc_mth = engine.get_recent_accuracies(dataset)
                except:
                    pass

            increment_prediction_count(config, current_hwid)

            return {
                "mode": mode,
                "fighter1_clean": f1_clean,
                "fighter2_clean": f2_clean,
                "event_name": fight_info['event_name'],
                "event_date": fight_info['event_date'],
                "rounds": rounds,
                "prediction": {
                    "winner": pred.winner if pred.method != FinishType.DRAW else "Ничья",
                    "prob": int(pred.prob * 100),
                    "margin": int((pred.ci_hi - pred.ci_lo) * 100),
                    "rnd": pred.rnd,
                    "method": pred.method.value
                },
                "fact": {"winner": "Ожидание", "rnd": "Ожидание", "method": "Ожидание"},
                "accuracy": {"win": acc_win, "rnd": acc_rnd, "method": acc_mth},
                "odds": {
                    "model_f1": 1.0 / max(pred.prob, 0.01),
                    "model_f2": 1.0 / max(1 - pred.prob, 0.01),
                    "book_f1": fight_info.get('odds_a', 'Уточняется'),
                    "book_f2": fight_info.get('odds_b', 'Уточняется'),
                    "bookmaker": fight_info.get('bookmaker', '—')
                },
                "training_log": "",
                "steps": steps
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.post("/api/calibrate")
async def calibrate_model():
    if not is_initialized or not engine:
        raise HTTPException(status_code=400, detail="Система не инициализирована")

    try:
        engine.run_full_loocv_evaluation()
        if os.path.exists("mma_weights_v21.json"):
            with open("mma_weights_v21.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            accuracy = data.get('loocv_accuracy', 0.0) * 100
        else:
            accuracy = 0.0
        return {"status": "success", "accuracy": accuracy}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка калибровки: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("=" * 70)
    print("🚀 MMA PREDICTOR DASHBOARD API v3.1")
    print("=" * 70)
    print("📡 Сервер: http://127.0.0.1:8000")
    print("=" * 70)
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)