# -*- coding: utf-8 -*-
"""Смоук-тесты: слои защиты дат и путь коэффициентов. Запуск: python tests_smoke.py"""
import json
import os
import subprocess
import sys

import requests

API = "http://201.51.30.5"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), "|", name, ("| " + str(detail) if detail else ""))


# --- T1: клиент (исходник) ---
src = open("clients/desktop_app.py", encoding="utf-8").read()
check("T1.1 клиент: календарь прогноза не раньше сегодня", "setMinimumDate(QDate.currentDate())" in src)
check("T1.2 клиент: календарь 2b не позже сегодня", "setMaximumDate(QDate.currentDate())" in src)
check("T1.3 клиент: кард шлёт mode=predict", "mode=predict" in src)
check("T1.4 клиент: кард шлёт mode=train", "mode=train" in src)

# --- T2: исходники сервера и консоли (локальные копии) ---
src_main = open("server/main.py", encoding="utf-8").read()
check("T2.1 сервер: /api/card принимает mode", "mode: str" in src_main)
check("T2.2 сервер: /api/predict блокирует прошлое", "недопустима дата старше сегодня" in src_main)
src_bridge = open("mma_predictor_bridge.py", encoding="utf-8").read()
check("T2.3 bridge: перехват stdout в stderr", "redirect_stdout_to_stderr" in src_bridge)
src_console = open("mma_predictor.py", encoding="utf-8").read()
check("T2.4 консоль: прогноз блокирует прошлое", "недопустима дата старше сегодня" in src_console)
check("T2.5 консоль: 2b блокирует будущее", "недопустима дата младше сегодня" in src_console)

# --- T3: живой сервер ---
r = requests.get(f"{API}/api/card", params={"date": "2026-10-17", "device_id": "test", "mode": "predict"}, timeout=20)
d = r.json()
check("T3.1 сервер живой: кард прошлое+predict отклонён", d.get("status") == "error", d.get("message", "")[:60])

r = requests.get(f"{API}/api/card", params={"date": "2026-12-01", "device_id": "test", "mode": "train"}, timeout=20)
d = r.json()
check("T3.2 сервер живой: кард будущее+train отклонён", d.get("status") == "error", d.get("message", "")[:60])

r = requests.post(f"{API}/api/predict",
                  json={"device_id": "test", "fighter_a": "A", "fighter_b": "B",
                        "date": "2026-10-17", "lang": "ru"}, timeout=20)
check("T3.3 сервер живой: /api/predict прошлое отклоняет (400)", r.status_code == 400, f"code={r.status_code}")

# --- T4: bridge локально: JSON в stdout, логи Odds в stderr ---
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
p = subprocess.run(
    [sys.executable, "mma_predictor_bridge.py", "--predict",
     "Merab Dvalishvili", "Petr Yan", "25.10.2026"],
    capture_output=True, text=True, timeout=300,
    encoding="utf-8", errors="replace", env=env
)
out, err = p.stdout, p.stderr
print("----- STDERR BRIDGE (хвост) -----")
print(err[-3000:])
print("---------------------------------")
data = {}
ok_json = False
try:
    data = json.loads(out[out.find("{"): out.rfind("}") + 1])
    ok_json = True
except Exception:
    pass
check("T4.1 bridge: stdout содержит валидный JSON", ok_json)
check("T4.2 bridge: логи Odds API ушли в stderr", ("Поиск боя" in err) or ("Бой найден" in err))
if ok_json:
    check("T4.3 bridge: коэффициенты реальные (не 1.85)",
          data.get("odds_a", 1.85) != 1.85,
          f"odds_a={data.get('odds_a')} odds_b={data.get('odds_b')} bookmaker={data.get('bookmaker')}")

print()
fails = [x for x in RESULTS if not x[1]]
print(f"ВСЕГО: {len(RESULTS)}  FAIL: {len(fails)}")
for name, ok, detail in fails:
    print("  FAIL:", name, detail)