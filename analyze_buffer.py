"""
Анализ точности MMAEngine + калибровка уверенности
"""
import json
from datetime import datetime
from math_engine import MMAEngine, Fighter, FightData


def norm(obj):
    if isinstance(obj, dict):
        return {k.strip(): norm(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [norm(x) for x in obj]
    if isinstance(obj, str):
        return obj.strip()
    return obj


engine = MMAEngine()
print("✅ Модель загружена")

with open("dataset/pending_buffer.json", "r", encoding="utf-8") as f:
    buffer = norm(json.load(f))

print(f"📊 Боёв в буфере: {len(buffer)}\n")

FIGHTER_FIELDS = ["age", "wins", "losses", "fin_rate", "sub_rate", "td_def",
                  "grap_def", "recent_wins", "months_off", "fights_12m",
                  "stress_factor", "motivation_index", "biorythm_score",
                  "camp_quality", "mystic_factor", "mystic_v2",
                  "reach_cm", "height_cm", "exp"]


def make_fighter(name, stats):
    kwargs = {k: stats[k] for k in FIGHTER_FIELDS if k in stats}
    kwargs["name"] = name
    kwargs["camp_name"] = stats.get("camp_name", "Independent")
    kwargs["dob"] = stats.get("dob")
    kwargs["dob_quality"] = stats.get("dob_quality", 1)
    return Fighter(**kwargs)


stats_all = [0, 0]
stats_conf = [0, 0]
stats_low = [0, 0]

for i, fight in enumerate(buffer, 1):
    try:
        fa = make_fighter(fight["fighter_a"], fight["stats_a"])
        fb = make_fighter(fight["fighter_b"], fight["stats_b"])
        fd = FightData(a=fa, b=fb,
                       date=datetime.strptime(fight["date"], "%Y-%m-%d"),
                       wc="Open", rounds=fight.get("round", 3),
                       odds_a=fight.get("odds_a", 1.85))
        pred = engine.predict(fd)
        real = fight["winner"]
        ok = pred.winner == real

        features, _ = engine.model._extract_features(fa, fb, 1.85, 1.85)
        pure_a = engine.model.predict_proba(features)
        pure_conf = max(pure_a, 1.0 - pure_a)

        stats_all[1] += 1
        stats_all[0] += ok
        if pure_conf >= 0.60:
            stats_conf[1] += 1
            stats_conf[0] += ok
            tag = "УВЕР"
        else:
            stats_low[1] += 1
            stats_low[0] += ok
            tag = "слаб"
        mark = "✅" if ok else "❌"
        print(f"{i:2d}. {mark} [{tag} {pure_conf:.0%}] {fight['fighter_a']} vs {fight['fighter_b']} -> {pred.winner} | факт {real}")
    except Exception as e:
        print(f"{i:2d}. ⚠️ Ошибка: {type(e).__name__}: {e}")

print("=" * 70)
def pct(s): return f"{s[0]}/{s[1]} = {s[0]/s[1]:.1%}" if s[1] else "нет данных"
print(f"📊 ВСЕ прогнозы:       {pct(stats_all)}")
print(f"🎯 Уверенные (>=60%):  {pct(stats_conf)}")
print(f"😐 Неуверенные (<60%): {pct(stats_low)}")
print("=" * 70)
