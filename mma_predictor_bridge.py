#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MMA PREDICTOR BRIDGE | Subprocess-интерфейс для веб (3 режима)
===============================================================
ВСЕ логи идут в sys.stderr. В sys.stdout попадает ТОЛЬКО чистый JSON.
Это гарантирует, что subprocess не зависнет и веб получит валидный JSON.
===============================================================
"""
import sys
import os
import json
import argparse
from datetime import datetime, timedelta

# Перенаправляем все обычные print в stderr, чтобы stdout остался чистым для JSON
def log(msg):
    print(msg, file=sys.stderr)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Импорты из основного файла и модулей
from mma_predictor import clean_name_for_api, get_fighter_data, get_ai_arbitrator_prediction, normalize_winner_name
from math_engine import MMAEngine, Fighter, FightData, Result, FinishType, names_match
from secure_neural_channel import SecureNeuralChannel
from secure_keys import SecureKeys
from espn_parser import ESPNParser
from odds_api_client import OddsAPIClient
from mystic_calculator import calculate_mystic_factor

MASTER_PASSWORD = "5Tgfder%$"

def init_engine():
    log("⚙️ Инициализация движка в bridge...")
    SecureNeuralChannel.init(MASTER_PASSWORD)
    SecureKeys.init(MASTER_PASSWORD)
    engine = MMAEngine()
    engine.recalibrate_scaler()
    espn = ESPNParser()
    return engine, espn

def run_predict(fighter_a: str, fighter_b: str, date_str: str) -> dict:
    log(f"🔍 Прогноз: {fighter_a} vs {fighter_b} на {date_str}")
    result = {"winner": "", "probability": 0.0, "method": "", "round": 0, "ci_lo": 0.0, "ci_hi": 0.0,
              "odds_a": 1.85, "odds_b": 1.85, "bookmaker": "Нет данных", "ai_winner": "", "ai_confidence": 0,
              "ai_reason": "", "verdict": "", "verdict_reason": "", "stats_a": "", "stats_b": ""}
    try:
        engine, espn = init_engine()
        f1_clean = clean_name_for_api(fighter_a)
        f2_clean = clean_name_for_api(fighter_b)

        fa = get_fighter_data(fighter_name=f1_clean, fight_date=date_str, opponent_name=f2_clean, fight_context="regular", fighter_dob=None)
        fb = get_fighter_data(fighter_name=f2_clean, fight_date=date_str, opponent_name=f1_clean, fight_context="regular", fighter_dob=None)
        if not fa or not fb:
            result["error"] = "Не удалось получить данные бойцов"
            return result

        result["stats_a"] = f"{fa.wins}-{fa.losses}, reach={fa.reach_cm}см, camp={fa.camp_name}"
        result["stats_b"] = f"{fb.wins}-{fb.losses}, reach={fb.reach_cm}см, camp={fb.camp_name}"

        odds_client = OddsAPIClient()
        odds_result = odds_client.get_fight_odds(f1_clean, f2_clean)
        if odds_result:
            result["odds_a"], result["odds_b"], result["bookmaker"] = odds_result['odds_a'], odds_result['odds_b'], odds_result['bookmaker']

        try: ev_date = datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError: ev_date = datetime.now()

        fd = FightData(a=fa, b=fb, date=ev_date, wc="Auto", rounds=3, location="UFC", odds_a=result["odds_a"],
                       matchup_odds={"bookmaker": result["bookmaker"], "odds_a": result["odds_a"], "odds_b": result["odds_b"]})
        pred = engine.predict(fd)

        result["winner"], result["probability"], result["method"], result["round"] = pred.winner, pred.prob, (pred.method.value if hasattr(pred.method, 'value') else str(pred.method)), pred.rnd
        result["ci_lo"], result["ci_hi"] = pred.ci_lo, pred.ci_hi

        ai_verdict = get_ai_arbitrator_prediction(fa, fb, "regular")
        result["ai_winner"], result["ai_confidence"], result["ai_reason"] = ai_verdict.get('winner', ''), ai_verdict.get('confidence', 0), ai_verdict.get('reason', '')

        # Тройной арбитраж
        model_winner, model_prob = pred.winner, pred.prob
        bookmaker_favorite = f1_clean if result["odds_a"] < result["odds_b"] else (f2_clean if result["odds_b"] < result["odds_a"] else "Ничья")
        agreements = (1 if result["ai_winner"] == model_winner else 0) + (1 if bookmaker_favorite == model_winner else 0)

        if agreements == 2:
            result["verdict"], result["verdict_reason"] = "РЕКОМЕНДУЮ", f"Полное совпадение: Математика, ИИ и БК единогласны за {model_winner} (3 из 3)"
        elif agreements == 1:
            if result["ai_winner"] == model_winner:
                result["verdict"], result["verdict_reason"] = "ВАЛУЙ", f"Математика и ИИ за {model_winner}, но БК за {bookmaker_favorite}. Рынок ошибается!"
            elif bookmaker_favorite == model_winner:
                result["verdict"], result["verdict_reason"] = "СЛАБАЯ РЕКОМЕНДАЦИЯ", f"Математика и БК за {model_winner}, но ИИ предупреждает о рисках ({result['ai_winner']})."
            else:
                result["verdict"], result["verdict_reason"] = "СПОРНЫЙ", "Расхождение между всеми тремя источниками"
        else:
            if model_prob > 0.60: result["verdict"], result["verdict_reason"] = "РЕКОМЕНДУЮ", f"Высокая уверенность модели ({model_prob*100:.1f}%) за {model_winner}"
            elif model_prob > 0.50: result["verdict"], result["verdict_reason"] = "СЛАБАЯ РЕКОМЕНДАЦИЯ", f"Небольшое преимущество модели ({model_prob*100:.1f}%) за {model_winner}"
            else: result["verdict"], result["verdict_reason"] = "ПРОПУСТИТЬ", f"Низкая уверенность модели ({model_prob*100:.1f}%)"

    except Exception as e:
        result["error"] = str(e)
    return result

def run_train_2a(period: str, year: str) -> dict:
    log(f"🚀 Обучение 2a: период {period}, год {year}")
    result = {"status": "error", "message": "", "period": period, "year": year, "total_fights": 0, "trained_fights": 0, "accuracy": 0.0, "new_best_accuracy": 0.0}
    try:
        engine, espn = init_engine()
        months = list(range(int(period.split('-')[0]), int(period.split('-')[1]) + 1)) if '-' in period else [int(period)]
        all_fights = []
        for m in months:
            all_fights.extend(espn.get_fights_by_month(int(year), m))

        if not all_fights:
            result["message"] = f"Боёв за период {period}.{year} не найдено"
            return result
        result["total_fights"] = len(all_fights)

        correct, incorrect = 0, 0
        meth_map = {'UD': FinishType.DECISION_UNANIMOUS, 'SD': FinishType.DECISION_SPLIT, 'MD': FinishType.DECISION_UNANIMOUS, 'DEC': FinishType.DECISION_UNANIMOUS, 'TKO': FinishType.TKO, 'KO': FinishType.KO, 'SUB': FinishType.SUBMISSION}

        for idx, fight in enumerate(all_fights, 1):
            # Выводим этап в stdout как JSON
            stage = {"type": "stage", "current": idx, "total": len(all_fights)}
            print(json.dumps(stage, ensure_ascii=False))

            f1, f2 = fight.get('fighter_a', 'Unknown'), fight.get('fighter_b', 'Unknown')
            try:
                target_date_str = (fight.get('date') - timedelta(days=1)).strftime("%Y-%m-%d")
                fa = get_fighter_data(fighter_name=f1, fight_date=target_date_str, opponent_name=f2, fighter_dob=fight.get('dob_a'))
                fb = get_fighter_data(fighter_name=f2, fight_date=target_date_str, opponent_name=f1, fighter_dob=fight.get('dob_b'))
                if not fa or not fb: continue

                fd = FightData(a=fa, b=fb, date=fight.get('date'), wc="Auto", rounds=fight.get('round', 3), location=fight.get('event_name', 'UFC'), odds_a=1.85, matchup_odds={"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85})
                pred = engine.predict(fd)

                fact_winner_norm = normalize_winner_name(fight.get('winner', 'Unknown'), f1, f2)
                if names_match(pred.winner, fact_winner_norm): correct += 1
                else: incorrect += 1

                res = Result(winner=fact_winner_norm, rnd=fight.get('round', 3), method=meth_map.get(fight.get('method', 'DEC'), FinishType.DECISION_UNANIMOUS))
                engine.train_on_new_fight(fd, res, f1, f2, ai_factor=1.0, blind_conf=None)
            except Exception:
                continue

        total = correct + incorrect
        eval_accuracy = (correct / total * 100) if total > 0 else 0.0

        result["status"] = "success"
        result["message"] = f"Обучение завершено. Точность на тесте: {eval_accuracy:.1f}%"
        result["trained_fights"] = total
        result["accuracy"] = eval_accuracy
        result["new_best_accuracy"] = engine.best_accuracy * 100

    except Exception as e:
        result["message"] = f"Ошибка: {str(e)}"
    return result

def run_train_2b(date_str: str, fight_indices: list) -> dict:
    log(f"🔍 Обучение 2b: дата {date_str}, бои {fight_indices}")
    result = {"status": "error", "message": "", "date": date_str, "total_fights": 0, "correct": 0, "incorrect": 0, "accuracy": 0.0, "details": []}
    try:
        engine, espn = init_engine()

        # Конвертируем дату из YYYY-MM-DD в ДД.ММ.ГГГГ
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            date_ddmmyyyy = date_obj.strftime("%d.%m.%Y")
        except ValueError:
            date_ddmmyyyy = date_str

        card_fights = espn.get_fights_by_date(date_ddmmyyyy)
        if not card_fights:
            result["message"] = f"Боёв на {date_ddmmyyyy} не найдено"
            return result

        selected = [card_fights[i] for i in fight_indices if 0 <= i < len(card_fights)]
        result["total_fights"] = len(selected)
        correct, incorrect = 0, 0

        for fight in selected:
            f1, f2 = fight.get('fighter_a', 'Unknown'), fight.get('fighter_b', 'Unknown')
            detail = {"f1": f1, "f2": f2, "fact": "Ошибка", "pred": "Ошибка", "is_correct": False}
            try:
                target_date_str = (fight.get('date') - timedelta(days=1)).strftime("%Y-%m-%d")
                fa = get_fighter_data(fighter_name=f1, fight_date=target_date_str, opponent_name=f2, fighter_dob=fight.get('dob_a'))
                fb = get_fighter_data(fighter_name=f2, fight_date=target_date_str, opponent_name=f1, fighter_dob=fight.get('dob_b'))

                if not fa or not fb:
                    detail["error"] = "Нет данных"
                    result["details"].append(detail)
                    continue

                fd = FightData(a=fa, b=fb, date=fight.get('date'), wc="Auto", rounds=fight.get('round', 3), location=fight.get('event', 'UFC'), odds_a=1.85, matchup_odds={"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85})
                pred = engine.predict(fd)

                fact_winner_norm = normalize_winner_name(fight.get('winner', 'Unknown'), f1, f2)
                is_correct = names_match(pred.winner, fact_winner_norm)

                detail["pred"] = pred.winner
                detail["pred_prob"] = round(pred.prob * 100, 1)
                detail["fact"] = fact_winner_norm
                detail["is_correct"] = is_correct

                if is_correct:
                    correct += 1
                else:
                    incorrect += 1

                result["details"].append(detail)
            except Exception as e:
                detail["error"] = str(e)
                result["details"].append(detail)
                continue

        total = correct + incorrect
        result["status"] = "success"
        result["message"] = f"Проверка завершена. Точность: {(correct/total*100) if total > 0 else 0:.1f}%"
        result["correct"], result["incorrect"] = correct, incorrect
        result["accuracy"] = (correct/total*100) if total > 0 else 0.0
    except Exception as e:
        result["message"] = f"Ошибка: {str(e)}"
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--predict', nargs=3, metavar=('FIGHTER_A', 'FIGHTER_B', 'DATE'))
    parser.add_argument('--train2a', nargs=2, metavar=('PERIOD', 'YEAR'))
    parser.add_argument('--train2b', nargs=2, metavar=('DATE', 'FIGHT_INDICES'))
    args = parser.parse_args()

    if args.predict:
        res = run_predict(args.predict[0], args.predict[1], args.predict[2])
    elif args.train2a:
        res = run_train_2a(args.train2a[0], args.train2a[1])
    elif args.train2b:
        res = run_train_2b(args.train2b[0], json.loads(args.train2b[1]))
    else:
        res = {"error": "Не указан режим. Используйте --predict, --train2a или --train2b"}

    # ВАЖНО: Только это попадает в stdout!
    print(json.dumps(res, ensure_ascii=False))

if __name__ == "__main__":
    main()