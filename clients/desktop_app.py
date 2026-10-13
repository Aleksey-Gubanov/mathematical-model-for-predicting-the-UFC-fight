# -*- coding: utf-8 -*-
"""
MMA Predictor AI - Desktop Client (Windows)
PyQt6 UI по HTML-макету. SSE-стриминг анализа боёв.
БЕЗОПАСНАЯ АРХИТЕКТУРА: результат диалога читается синхронно после exec().
"""
import sys
import json
import uuid
import socket
import hashlib
from pathlib import Path
import requests


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QTextEdit, QDateEdit,
    QSpinBox, QListWidget, QListWidgetItem, QMessageBox, QFrame,
    QDialog, QGroupBox, QCheckBox, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QColor

# === КОНСТАНТЫ ===
API_URL = "http://201.51.30.5"
HWID_CACHE = Path(__file__).parent.parent / ".hwid_cache"
DISCLAIMER_FILE = Path(__file__).parent.parent / ".disclaimer_accepted"
LANGUAGE_FILE = Path(__file__).parent.parent / ".language"

# === СТИЛИ ===
STYLESHEET = """
QMainWindow, QDialog {
    background: #0a0e27;
    color: #e0e0e0;
}
QLabel {
    color: #e0e0e0;
}
QLineEdit, QDateEdit, QSpinBox {
    background: #0a0e27;
    border: 1px solid #2a2f4a;
    border-radius: 6px;
    padding: 6px;
    color: #ffffff;
    font-size: 13px;
}
QLineEdit:focus, QDateEdit:focus, QSpinBox:focus {
    border: 1px solid #667eea;
}
QPushButton {
    background: #2a2f4a;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover { background: #3a3f5a; }
QPushButton:disabled {
    background: #1a1f3a;
    color: #555566;
}
QPushButton.primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #667eea, stop:1 #764ba2);
}
QPushButton.primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #7690ee, stop:1 #8a5db6);
}
QPushButton.primary:disabled {
    background: #1a1f3a;
    color: #555566;
}
QPushButton.secondary { background: #2a2f4a; }
QCheckBox {
    color: #e0e0e0;
    font-size: 13px;
    spacing: 8px;
    padding: 6px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #667eea;
    border-radius: 4px;
    background: #0a0e27;
}
QCheckBox::indicator:checked {
    background: #667eea;
}
QScrollArea {
    border: none;
    background: #0a0e27;
}
QScrollArea > QWidget > QWidget {
    background: #0a0e27;
}
QTabWidget::pane {
    border: 1px solid #2a2f4a;
    border-radius: 8px;
    background: #1a1f3a;
}
QTabBar::tab {
    background: #1a1f3a;
    color: #a0a0a0;
    padding: 10px 14px;
    border-radius: 6px;
    margin-right: 4px;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #667eea, stop:1 #764ba2);
    color: white;
}
QListWidget {
    background: #0a0e27;
    border: 1px solid #2a2f4a;
    border-radius: 6px;
    color: #e0e0e0;
    padding: 4px;
}
QListWidget::item {
    background: #0a0e27;
    border-left: 3px solid #2a2f4a;
    padding: 10px;
    margin: 3px 0;
    border-radius: 4px;
}
QListWidget::item:hover {
    border-left: 3px solid #667eea;
    background: #1a1f3a;
}
QListWidget::item:selected {
    background: #2a2f4a;
    border-left: 3px solid #667eea;
}
QTextEdit {
    background: #0a0e27;
    border: 1px solid #2a2f4a;
    border-radius: 6px;
    color: #e0e0e0;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QMessageBox {
    background: #1a1f3a;
    color: #e0e0e0;
}
QGroupBox {
    border: 1px solid #2a2f4a;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px;
    background: #1a1f3a;
}
"""

# === ЛОКАЛИЗАЦИЯ ===
LOCALES = {
    "ru": {
        "title": "MMA Predictor AI",
        "device_id": "Device ID:",
        "balance": "Баланс:",
        "predict": "Прогноз",
        "train2a": "Обучение 2а",
        "train2b": "Обучение 2b",
        "status": "Статус",
        "load_card": "Загрузить кард",
        "tournament_date": "Дата турнира",
        "period": "Период (ММ или ММ-ММ):",
        "year": "Год:",
        "start_training": "Запустить обучение",
        "start_check": "Запустить проверку выбранных",
        "check_status": "Проверить статус",
        "loading_card": "⏳ Загрузка карда...",
        "no_fights": "Бои не найдены",
        "loaded_fights": "Загружено боёв:",
        "fill_period": "Заполните период",
        "select_fight": "Выберите хотя бы один бой",
        "network_error": "Ошибка сети",
        "error": "Ошибка",
        "training_started": "▶ Запуск обучения",
        "training_done": "✅ ОБУЧЕНИЕ ЗАВЕРШЕНО",
        "period_label": "Период:",
        "total_fights": "Всего боёв:",
        "processed": "Обработано:",
        "test_accuracy": "Точность на тесте:",
        "best_accuracy": "Лучшая точность:",
        "checking_model": "▶ Проверка модели...",
        "total_checked": "✅ Всего проверено:",
        "correct": "✅ Верных:",
        "incorrect": "❌ Неверных:",
        "accuracy": "🎯 Точность:",
        "correct_mark": "✅ ВЕРНО",
        "incorrect_mark": "❌ НЕВЕРНО",
        "prediction": "Прогноз:",
        "fact": "Факт:",
        "requesting": "⏳ Запрос...",
        "balance_label": "прогнозов",
        "tariff": "Тариф:",
        "expires": "Действует до:",
        "active": "Активен:",
        "yes": "Да",
        "no": "Нет",
        "close": "Закрыть",
        "about": "О программе",
        "agree": "Согласен",
        "disclaimer": "Я понимаю, что модель даёт только рекомендации, а не гарантии результата",
        "final": "🎯 ИТОГОВЫЙ ПРОГНОЗ",
        "model_result": "🤖 РЕЗУЛЬТАТ МОДЕЛИ",
        "ai_analysis": "🧠 АНАЛИЗ ИИ-АРБИТРА",
        "odds": "💰 КОЭФФИЦИЕНТЫ",
        "method": "Метод:",
        "round": "Раунд:",
        "ci": "Доверительный интервал:",
        "ai_selects": "🤖 ИИ выбирает:",
        "reason": "💬 Причина:",
        "main_event": "МЕ",
        "rounds_short": "р.",
    },
    "en": {
        "title": "MMA Predictor AI",
        "device_id": "Device ID:",
        "balance": "Balance:",
        "predict": "Predict",
        "train2a": "Train 2a",
        "train2b": "Train 2b",
        "status": "Status",
        "load_card": "Load card",
        "tournament_date": "Tournament date",
        "period": "Period (MM or MM-MM):",
        "year": "Year:",
        "start_training": "Start training",
        "start_check": "Start check selected",
        "check_status": "Check status",
        "loading_card": "⏳ Loading card...",
        "no_fights": "No fights found",
        "loaded_fights": "Fights loaded:",
        "fill_period": "Fill the period",
        "select_fight": "Select at least one fight",
        "network_error": "Network error",
        "error": "Error",
        "training_started": "▶ Starting training",
        "training_done": "✅ TRAINING COMPLETED",
        "period_label": "Period:",
        "total_fights": "Total fights:",
        "processed": "Processed:",
        "test_accuracy": "Test accuracy:",
        "best_accuracy": "Best accuracy:",
        "checking_model": "▶ Checking model...",
        "total_checked": "✅ Total checked:",
        "correct": "✅ Correct:",
        "incorrect": "❌ Incorrect:",
        "accuracy": "🎯 Accuracy:",
        "correct_mark": "✅ CORRECT",
        "incorrect_mark": "❌ INCORRECT",
        "prediction": "Prediction:",
        "fact": "Fact:",
        "requesting": "⏳ Requesting...",
        "balance_label": "predictions",
        "tariff": "Plan:",
        "expires": "Valid until:",
        "active": "Active:",
        "yes": "Yes",
        "no": "No",
        "close": "Close",
        "about": "About",
        "agree": "Agree",
        "disclaimer": "I understand that the model provides only recommendations, not guarantees of results",
        "final": "🎯 FINAL PREDICTION",
        "model_result": "🤖 MODEL RESULT",
        "ai_analysis": "🧠 AI ARBITER ANALYSIS",
        "odds": "💰 ODDS",
        "method": "Method:",
        "round": "Round:",
        "ci": "Confidence interval:",
        "ai_selects": "🤖 AI selects:",
        "reason": "💬 Reason:",
        "main_event": "ME",
        "rounds_short": "r.",
    }
}

# === ОПИСАНИЕ ПРИНЦИПА РАБОТЫ ===
ABOUT_TEXT = {
    "ru": """
<h2>🥊 MMA Predictor AI — Принцип работы</h2>
<h3>🎯 Назначение</h3>
<p>Инструмент анализа боёв ММА на основе трёх независимых источников:</p>
<ol>
<li><b>Математическая модель</b> — статистика 14 000+ боёв, точность ~62%</li>
<li><b>ИИ-арбитр (DeepSeek)</b> — независимый анализ физиологии, формы, лагерей</li>
<li><b>Коэффициенты букмекеров</b> — рыночная оценка через The Odds API</li>
</ol>
<h3>🧮 Математическая природа ядра</h3>
<p><b style="color:#667eea;">Модель строго математическая</b> — всё решается цифрами. Вероятностная основа:</p>
<ul>
<li><b>Вероятностное пространство:</b> боец = многомерный вектор признаков</li>
<li><b>Нелинейная агрегация:</b> логистические преобразования, взвешенные метрики</li>
<li><b>Байесовский вывод:</b> апостериорное распределение через обновление весов</li>
<li><b>Доверительные интервалы:</b> диапазон вероятностей, а не одно число</li>
<li><b>Автокалибровка:</b> регуляризация на выборке 14 000+ боёв</li>
</ul>
<h3>🔄 Непрерывное обучение</h3>
<p><b style="color:#4caf50;">Модель обучается постоянно, в реальном времени:</b></p>
<ul>
<li>Обновление весов признаков (α=0.005) на каждом завершённом бое</li>
<li>Корректировка нормализатора на 415 последних боях</li>
<li>Буфер ожидания пополняется новыми боями</li>
<li>Авто-возврат к эталону при деградации точности &gt;4%</li>
</ul>
<h3>💡 Тройной арбитраж</h3>
<ul>
<li>Все три источника согласны → <b style="color:#4caf50;">РЕКОМЕНДУЮ</b></li>
<li>Модель + ИИ против букмекера → <b style="color:#ff9800;">ВАЛУЙ</b></li>
<li>Расхождение → <b style="color:#a0a0a0;">СЛАБАЯ РЕКОМЕНДАЦИЯ</b> / <b style="color:#f44336;">ПРОПУСТИТЬ</b></li>
</ul>
<h3>💰 Оплата</h3>
<p>20 бесплатных прогнозов при регистрации. Пополнение через DonationAlerts.</p>
<h3>⚠️ Важное предупреждение</h3>
<p><b style="color:#f44336;">Модель даёт только рекомендации, а не гарантии результата.</b></p>
""",
    "en": """
<h2> MMA Predictor AI — How it works</h2>
<h3>🎯 Purpose</h3>
<p>MMA fight analysis tool based on three independent sources:</p>
<ol>
<li><b>Mathematical model</b> — statistics of 14,000+ fights, accuracy ~62%</li>
<li><b>AI arbiter (DeepSeek)</b> — independent analysis of physiology, form, camps</li>
<li><b>Bookmaker odds</b> — market assessment via The Odds API</li>
</ol>
<h3>🧮 Mathematical nature of the core</h3>
<p><b style="color:#667eea;">The model is strictly mathematical</b> — everything is solved by numbers:</p>
<ul>
<li><b>Probabilistic space:</b> fighter = multi-dimensional feature vector</li>
<li><b>Non-linear aggregation:</b> logistic transformations, weighted metrics</li>
<li><b>Bayesian inference:</b> posterior distribution via weight updates</li>
<li><b>Confidence intervals:</b> probability range, not a single number</li>
<li><b>Auto-calibration:</b> regularization on 14,000+ fight sample</li>
</ul>
<h3>🔄 Continuous learning</h3>
<p><b style="color:#4caf50;">The model learns constantly, in real time:</b></p>
<ul>
<li>Feature weight updates (α=0.005) on every completed fight</li>
<li>Normalizer recalibration on last 415 fights</li>
<li>Pending buffer populated with new fights</li>
<li>Auto-rollback to baseline if accuracy degrades &gt;4%</li>
</ul>
<h3>💡 Triple arbitration</h3>
<ul>
<li>All three sources agree → <b style="color:#4caf50;">RECOMMEND</b></li>
<li>Model + AI vs bookmaker → <b style="color:#ff9800;">VALUE</b></li>
<li>Disagreement → <b style="color:#a0a0a0;">WEAK RECOMMENDATION</b> / <b style="color:#f44336;">SKIP</b></li>
</ul>
<h3>💰 Payment</h3>
<p>20 free predictions on registration. Top-up via DonationAlerts.</p>
<h3>⚠️ Important disclaimer</h3>
<p><b style="color:#f44336;">The model provides only recommendations, not guarantees.</b></p>
"""
}


# === HWID ===
def get_hwid() -> str:
    raw = f"{uuid.getnode()}-{socket.gethostname()}-{socket.getfqdn()}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"hwid_{digest}"


def load_or_create_hwid() -> str:
    if HWID_CACHE.exists():
        try:
            return HWID_CACHE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    hwid = get_hwid()
    try:
        HWID_CACHE.write_text(hwid, encoding="utf-8")
    except Exception as e:
        print(f"Не удалось сохранить кэш HWID: {e}")
    return hwid


# === АВТОРЕГИСТРАЦИЯ ===
def autoregister(device_id: str) -> dict:
    try:
        r = requests.post(
            f"{API_URL}/api/register",
            json={"device_id": device_id},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Register error: {e}")
    return None


# === ДИАЛОГ ВЫБОРА ЯЗЫКА ===
class LanguageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_lang = "ru"
        self.setWindowTitle("Select language / Выберите язык")
        self.resize(400, 200)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Select language / Выберите язык")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #667eea;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(20)

        btn_layout = QHBoxLayout()
        self.btn_ru = QPushButton("Русский")
        self.btn_ru.setProperty("class", "primary")
        self.btn_ru.clicked.connect(lambda: self._select_language("ru"))
        btn_layout.addWidget(self.btn_ru)

        self.btn_en = QPushButton("English")
        self.btn_en.setProperty("class", "primary")
        self.btn_en.clicked.connect(lambda: self._select_language("en"))
        btn_layout.addWidget(self.btn_en)
        layout.addLayout(btn_layout)

    def _select_language(self, lang: str):
        self.selected_lang = lang
        self.accept()


# === РАБОЧИЕ ПОТОКИ ===
class SSEWorker(QThread):
    stage_signal = pyqtSignal(dict)
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, endpoint: str, payload: dict, parent=None):
        super().__init__(parent)
        self.endpoint = endpoint
        self.payload = payload

    def run(self):
        try:
            r = requests.post(
                f"{API_URL}{self.endpoint}",
                json=self.payload,
                stream=True,
                timeout=120,
            )
            if r.status_code != 200:
                self.error_signal.emit(f"HTTP {r.status_code}: {r.text[:200]}")
                return
            for raw_line in r.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace")
                if not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                t = data.get("type")
                if t in ("stage", "stage_complete"):
                    self.stage_signal.emit(data)
                elif t == "final_result":
                    self.result_signal.emit(data)
                elif t == "error":
                    self.error_signal.emit(data.get("message", "Ошибка"))
        except Exception as e:
            self.error_signal.emit(f"Сетевая ошибка: {e}")
        finally:
            self.finished_signal.emit()


class JSONWorker(QThread):
    done_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, method: str, url: str, payload: dict = None, parent=None):
        super().__init__(parent)
        self.method = method
        self.url = url
        self.payload = payload

    def run(self):
        try:
            if self.method == "GET":
                r = requests.get(self.url, timeout=30)
            else:
                r = requests.post(self.url, json=self.payload, timeout=60)
            if r.status_code != 200:
                self.error_signal.emit(f"HTTP {r.status_code}: {r.text[:200]}")
                return
            self.done_signal.emit(r.json())
        except Exception as e:
            self.error_signal.emit(f"Сетевая ошибка: {e}")


# === ДИАЛОГ СОГЛАСИЯ ===
class DisclaimerDialog(QDialog):
    def __init__(self, lang: str, parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle("MMA Predictor AI")
        self.resize(620, 560)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        t = LOCALES[self.lang]

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content.setStyleSheet("background: #0a0e27;")
        content_layout = QVBoxLayout(content)

        text_label = QLabel(ABOUT_TEXT[self.lang])
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.TextFormat.RichText)
        text_label.setStyleSheet("color: #e0e0e0; background: #0a0e27; font-size: 13px;")
        content_layout.addWidget(text_label)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.checkbox = QCheckBox(t["disclaimer"])
        self.checkbox.toggled.connect(self._on_checkbox_toggled)
        layout.addWidget(self.checkbox)

        self.agree_btn = QPushButton(t["agree"])
        self.agree_btn.setProperty("class", "primary")
        self.agree_btn.setEnabled(False)
        self.agree_btn.clicked.connect(self.accept)
        layout.addWidget(self.agree_btn)

    def _on_checkbox_toggled(self, checked: bool):
        self.agree_btn.setEnabled(checked)


# === ДИАЛОГ АНАЛИЗА БОЯ (БЕЗ СИГНАЛОВ НАРУЖУ) ===
class FightAnalysisDialog(QDialog):
    """Результат сохраняется в self.result_data и читается после exec()."""

    def __init__(self, fight: dict, device_id: str, fight_date: str, lang: str, parent=None):
        super().__init__(parent)
        self.fight = fight
        self.device_id = device_id
        self.fight_date = fight_date
        self.lang = lang
        self.result_data = None  # ← сюда пишем результат
        self.setWindowTitle(f"{fight.get('fighter_a', '')} vs {fight.get('fighter_b', '')}")
        self.resize(700, 600)
        self.worker = None
        self._build_ui()
        self._start_analysis()

    def _build_ui(self):
        t = LOCALES[self.lang]
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.title_label = QLabel(
            f"🥊 {self.fight.get('fighter_a', '')} vs {self.fight.get('fighter_b', '')}"
        )
        self.title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #667eea; padding: 8px;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.stage_label = QLabel("⏳ ...")
        self.stage_label.setWordWrap(True)
        self.stage_label.setStyleSheet(
            "background: #1a1f3a; padding: 12px; border-radius: 8px; "
            "border-left: 3px solid #ffd700; font-size: 13px;"
        )
        layout.addWidget(self.stage_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(180)
        layout.addWidget(self.log)

        self.result_frame = QFrame()
        self.result_frame.setStyleSheet(
            "QFrame { background: #1a1f3a; border-radius: 8px; "
            "border: 2px solid #667eea; }"
        )
        self.result_layout = QVBoxLayout(self.result_frame)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("padding: 12px; font-size: 13px;")
        self.result_layout.addWidget(self.result_label)
        layout.addWidget(self.result_frame)

        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton(t["close"])
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _start_analysis(self):
        payload = {
            "device_id": self.device_id,
            "fighter_a": self.fight.get("fighter_a", ""),
            "fighter_b": self.fight.get("fighter_b", ""),
            "date": self.fight_date,
            "lang": self.lang,
        }
        self.worker = SSEWorker("/api/predict", payload, self)
        self.worker.stage_signal.connect(self._on_stage)
        self.worker.result_signal.connect(self._on_result)
        self.worker.error_signal.connect(self._on_error)
        self.close_btn.setEnabled(False)  # Блокируем закрытие до завершения анализа
        self.worker.start()

    def _on_stage(self, data: dict):
        try:
            title = data.get("title", "")
            lines = data.get("lines", [])
            self.stage_label.setText(f"🔍 {title}")
            self.log.append(f"▶ {title}")
            for line in lines:
                self.log.append(f"  {line}")
        except Exception:
            pass

    def _on_result(self, data: dict):
        try:
            t = LOCALES[self.lang]
            verdict = str(data.get("verdict", ""))
            winner = str(data.get("winner", ""))
            try:
                prob = float(data.get("probability", 0) or 0)
            except (TypeError, ValueError):
                prob = 0.0
            method = str(data.get("method", ""))
            rnd = str(data.get("round", ""))
            ci = str(data.get("confidence_interval", ""))
            ai_winner = str(data.get("ai_winner", ""))
            ai_conf = data.get("ai_confidence", 0)
            ai_reason = str(data.get("ai_reason", ""))
            fd = data.get("fighters_data", {}) or {}
            odds_a = data.get("odds_a", "")
            odds_b = data.get("odds_b", "")
            bk = str(data.get("bookmaker", ""))
            v_reason = str(data.get("verdict_reason", ""))
            agr = data.get("agreements", 0)

            # Сохраняем результат для главного окна
            self.result_data = {
                "fighter_a": str(self.fight.get("fighter_a", "")),
                "verdict": verdict,
                "probability": prob,
            }

            if "РЕКОМЕНДУЮ" in verdict or "RECOMMEND" in verdict:
                border = "#4caf50"
            elif "ВАЛУЙ" in verdict or "VALUE" in verdict:
                border = "#ff9800"
            else:
                border = "#f44336"
            self.result_frame.setStyleSheet(
                f"QFrame {{ background: #1a1f3a; border-radius: 8px; "
                f"border: 2px solid {border}; }}"
            )

            html = f"""
            <div style='font-size:16px; font-weight:bold; text-align:center;
                        color:#667eea; margin-bottom:10px;'>
                {t['final']}
            </div>
            <div style='background:#0a0e27; padding:10px; border-radius:6px;
                        margin-bottom:8px;'>
                <div style='font-weight:bold; color:#667eea; margin-bottom:6px;'>
                    {t['model_result']}
                </div>
                <div style='font-size:18px; font-weight:bold; color:#4caf50;'>
                    {winner} — {prob:.1f}%
                </div>
                <div style='margin-top:6px; font-size:12px;'>
                    {t['method']} {method} | {t['round']} {rnd}<br>
                    {t['ci']} {ci}
                </div>
            </div>
            <div style='background:#0a0e27; padding:10px; border-radius:6px;
                        margin-bottom:8px;'>
                <div style='font-weight:bold; color:#667eea; margin-bottom:6px;'>
                    {t['ai_analysis']}
                </div>
                <div style='font-size:12px;'>
                    📊 {fd.get('fighter_a','')}: {fd.get('stats_a','')}<br>
                    📊 {fd.get('fighter_b','')}: {fd.get('stats_b','')}<br>
                    {t['ai_selects']} {ai_winner} ({ai_conf}%)<br>
                    {t['reason']} {ai_reason}
                </div>
            </div>
            <div style='background:#0a0e27; padding:10px; border-radius:6px;
                        margin-bottom:8px;'>
                <div style='font-weight:bold; color:#667eea; margin-bottom:6px;'>
                    {t['odds']} ({bk})
                </div>
                <div style='font-size:12px;'>
                    {fd.get('fighter_a','')}: {odds_a}<br>
                    {fd.get('fighter_b','')}: {odds_b}
                </div>
            </div>
            <div style='background:rgba(102,126,234,0.2); padding:10px;
                        border-radius:6px; text-align:center; font-weight:bold;'>
                {verdict} {f"(3/3)" if agr == 2 else ""}<br>
                <small>{v_reason}</small>
            </div>
            """
            self.result_label.setText(html)
            self.result_label.setTextFormat(Qt.TextFormat.RichText)
            self.close_btn.setEnabled(True)  # Разрешаем закрытие после получения результата
        except Exception as e:
            self.result_label.setText(f"❌ Ошибка отображения: {e}")

    def _on_error(self, msg: str):
        try:
            self.stage_label.setText(f"❌ {msg}")
            self.stage_label.setStyleSheet(
                "background: rgba(244,67,54,0.2); border: 1px solid #f44336; "
                "padding: 12px; border-radius: 8px; color: #f44336;"
            )
            self.close_btn.setEnabled(True)  # Разрешаем закрытие при ошибке
        except Exception:
            pass


# === ГЛАВНОЕ ОКНО ===
class MainWindow(QMainWindow):
    def __init__(self, device_id: str, balance: int = 0, lang: str = "ru"):
        super().__init__()
        self.device_id = device_id
        self.balance = balance
        self.lang = lang
        self.current_card = []
        self.fight_date = ""
        self.train2b_card = []
        self.workers = []
        self.predictions = {}
        self._build_ui()
        self._refresh_status_silent()

    def _build_ui(self):
        t = LOCALES[self.lang]
        self.setWindowTitle(f"MMA Predictor AI — {self.device_id}")
        self.resize(720, 820)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #667eea, stop:1 #764ba2); border-radius: 12px; }"
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)

        title_row = QHBoxLayout()
        self.title_label = QLabel(f"🥊 {t['title']}")
        self.title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        title_row.addWidget(self.title_label)
        title_row.addStretch()

        self.lang_btn = QPushButton("RU/EN")
        self.lang_btn.clicked.connect(self._toggle_lang)
        title_row.addWidget(self.lang_btn)

        self.about_btn = QPushButton(t["about"])
        self.about_btn.clicked.connect(self._show_about)
        title_row.addWidget(self.about_btn)

        header_layout.addLayout(title_row)

        user_bar = QFrame()
        user_bar.setStyleSheet("QFrame { background: rgba(0,0,0,0.3); border-radius: 8px; }")
        ub_layout = QHBoxLayout(user_bar)
        ub_layout.setContentsMargins(10, 6, 10, 6)
        self.device_label = QLabel(t["device_id"])
        self.device_label.setStyleSheet("color: white;")
        ub_layout.addWidget(self.device_label)
        self.hwid_label = QLineEdit(self.device_id)
        self.hwid_label.setReadOnly(True)
        ub_layout.addWidget(self.hwid_label, 1)
        self.balance_label = QLabel(f"{t['balance']} {self.balance}")
        self.balance_label.setStyleSheet("color: white; font-weight: bold;")
        ub_layout.addWidget(self.balance_label)
        header_layout.addWidget(user_bar)
        main_layout.addWidget(header)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_predict_tab(), t["predict"])
        self.tabs.addTab(self._build_train2a_tab(), t["train2a"])
        self.tabs.addTab(self._build_train2b_tab(), t["train2b"])
        self.tabs.addTab(self._build_status_tab(), t["status"])

        exit_btn = QPushButton("Выход / Exit")
        exit_btn.setProperty("class", "primary")
        exit_btn.clicked.connect(self._exit_app)
        main_layout.addWidget(exit_btn)

    # ---------- Локализация ----------
    def _toggle_lang(self):
        self.lang = "en" if self.lang == "ru" else "ru"
        self._retranslate_ui()

    def _retranslate_ui(self):
        t = LOCALES[self.lang]
        self.title_label.setText(f"🥊 {t['title']}")
        self.device_label.setText(t["device_id"])
        self.balance_label.setText(f"{t['balance']} {self.balance}")
        self.about_btn.setText(t["about"])
        self.tabs.setTabText(0, t["predict"])
        self.tabs.setTabText(1, t["train2a"])
        self.tabs.setTabText(2, t["train2b"])
        self.tabs.setTabText(3, t["status"])
        self.predict_form_group.setTitle(t["tournament_date"])
        self.load_card_btn.setText(t["load_card"])
        self.train2a_form_group.setTitle("Параметры" if self.lang == "ru" else "Parameters")
        self.train2a_period_label.setText(t["period"])
        self.train2a_year_label.setText(t["year"])
        self.train2a_run_btn.setText(t["start_training"])
        self.train2b_form_group.setTitle(t["tournament_date"])
        self.train2b_load_btn.setText(t["load_card"])
        self.train2b_run_btn.setText(t["start_check"])
        self.status_btn.setText(t["check_status"])

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("MMA Predictor AI")
        dlg.resize(620, 560)
        layout = QVBoxLayout(dlg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content.setStyleSheet("background: #0a0e27;")
        content_layout = QVBoxLayout(content)

        text_label = QLabel(ABOUT_TEXT[self.lang])
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.TextFormat.RichText)
        text_label.setStyleSheet("color: #e0e0e0; background: #0a0e27; font-size: 13px;")
        content_layout.addWidget(text_label)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        close_btn = QPushButton(LOCALES[self.lang]["close"])
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec()

    # ---------- Вкладка "Прогноз" ----------
    def _build_predict_tab(self) -> QWidget:
        t = LOCALES[self.lang]
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.predict_form_group = QGroupBox(t["tournament_date"])
        f_layout = QHBoxLayout(self.predict_form_group)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        f_layout.addWidget(self.date_edit, 1)
        self.load_card_btn = QPushButton(t["load_card"])
        self.load_card_btn.setProperty("class", "primary")
        self.load_card_btn.clicked.connect(self._load_card)
        f_layout.addWidget(self.load_card_btn)
        layout.addWidget(self.predict_form_group)

        self.card_status = QLabel("")
        self.card_status.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(self.card_status)

        self.fights_list = QListWidget()
        self.fights_list.itemClicked.connect(self._on_fight_clicked)
        layout.addWidget(self.fights_list, 1)
        return tab

    def _load_card(self):
        t = LOCALES[self.lang]
        date = self.date_edit.date().toString("yyyy-MM-dd")
        self.fight_date = date
        self.fights_list.clear()
        self.predictions.clear()
        self.card_status.setText(t["loading_card"])
        url = f"{API_URL}/api/card?date={date}&device_id={self.device_id}"
        w = JSONWorker("GET", url)
        w.done_signal.connect(self._on_card_loaded)
        w.error_signal.connect(self._on_net_error)
        self.workers.append(w)
        w.finished.connect(lambda: self.workers.remove(w))
        w.start()

    def _on_card_loaded(self, data: dict):
        t = LOCALES[self.lang]
        if data.get("status") == "error" or not data.get("fights"):
            self.card_status.setText(f"❌ {data.get('message', t['no_fights'])}")
            return
        self.current_card = data["fights"]
        self.card_status.setText(f"✅ {t['loaded_fights']} {len(self.current_card)}")
        for i, f in enumerate(self.current_card, 1):
            main_tag = f" • {t['main_event']}" if f.get("is_main_event") else ""
            text = (
                f"#{i}  {f['fighter_a']} vs {f['fighter_b']}  "
                f"({f.get('rounds', 3)} {t['rounds_short']}.{main_tag})"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.fights_list.addItem(item)
        self._restore_marks()

    def _on_fight_clicked(self, item: QListWidgetItem):
        """БЕЗОПАСНО: результат читается ПОСЛЕ закрытия диалога, без сигналов."""
        fight = item.data(Qt.ItemDataRole.UserRole)
        if not fight:
            return
        dlg = FightAnalysisDialog(fight, self.device_id, self.fight_date, self.lang, self)
        dlg.exec()  # блокирует до закрытия диалога
        # Читаем результат синхронно — никаких lambda, никаких C++-объектов в колбэках
        if dlg.result_data:
            idx = self.fights_list.row(item)
            if idx >= 0:
                self.predictions[idx] = dlg.result_data
                self._mark_item(item, dlg.result_data)
        dlg.deleteLater()
        self._refresh_status_silent()

    def _mark_item(self, item: QListWidgetItem, data: dict):
        try:
            verdict = str(data.get("verdict", ""))
            prob = float(data.get("probability", 0) or 0)
            winner = str(data.get("fighter_a", ""))
            if "РЕКОМЕНДУЮ" in verdict or "RECOMMEND" in verdict:
                color = "#4caf50"
            elif "ВАЛУЙ" in verdict or "VALUE" in verdict:
                color = "#ff9800"
            else:
                color = "#f44336"
            base_text = str(item.text()).split("  ✅")[0].split("  ❌")[0]
            item.setText(f"{base_text}  ✅ {verdict} • {winner} ({prob:.1f}%)")
            item.setForeground(QColor(color))
        except Exception:
            pass

    def _restore_marks(self):
        for idx, data in self.predictions.items():
            if idx < self.fights_list.count():
                self._mark_item(self.fights_list.item(idx), data)

    # ---------- Вкладка "Обучение 2а" ----------
    def _build_train2a_tab(self) -> QWidget:
        t = LOCALES[self.lang]
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.train2a_form_group = QGroupBox("Параметры" if self.lang == "ru" else "Parameters")
        f_layout = QVBoxLayout(self.train2a_form_group)

        p_row = QHBoxLayout()
        self.train2a_period_label = QLabel(t["period"])
        p_row.addWidget(self.train2a_period_label)
        self.train2a_period = QLineEdit()
        self.train2a_period.setPlaceholderText("01-06")
        p_row.addWidget(self.train2a_period, 1)
        f_layout.addLayout(p_row)

        y_row = QHBoxLayout()
        self.train2a_year_label = QLabel(t["year"])
        y_row.addWidget(self.train2a_year_label)
        self.train2a_year = QSpinBox()
        self.train2a_year.setRange(2022, 2030)
        self.train2a_year.setValue(2025)
        y_row.addWidget(self.train2a_year, 1)
        f_layout.addLayout(y_row)

        self.train2a_run_btn = QPushButton(t["start_training"])
        self.train2a_run_btn.setProperty("class", "primary")
        self.train2a_run_btn.clicked.connect(self._start_train2a)
        f_layout.addWidget(self.train2a_run_btn)
        layout.addWidget(self.train2a_form_group)

        self.train2a_log = QTextEdit()
        self.train2a_log.setReadOnly(True)
        self.train2a_log.setMinimumHeight(280)
        layout.addWidget(self.train2a_log, 1)
        return tab

    def _start_train2a(self):
        t = LOCALES[self.lang]
        period = self.train2a_period.text().strip()
        year = self.train2a_year.value()
        if not period:
            QMessageBox.warning(self, t["error"], t["fill_period"])
            return
        self.train2a_log.clear()
        self.train2a_log.append(f"{t['training_started']} {period}.{year}...")
        payload = {
            "device_id": self.device_id,
            "period": period,
            "year": year,
            "lang": self.lang,
        }
        w = SSEWorker("/api/train/2a", payload, self)
        w.stage_signal.connect(self._on_train2a_stage)
        w.result_signal.connect(self._on_train2a_result)
        w.error_signal.connect(self._on_train2a_error)
        self.workers.append(w)
        w.finished.connect(lambda: self.workers.remove(w))
        w.start()

    def _on_train2a_stage(self, data: dict):
        title = data.get("title", "")
        lines = data.get("lines", [])
        self.train2a_log.append(f"\n🔍 {title}")
        for l in lines:
            self.train2a_log.append(f"  {l}")

    def _on_train2a_result(self, data: dict):
        t = LOCALES[self.lang]
        d = data.get("data", data)
        self.train2a_log.append(f"\n{t['training_done']}")
        self.train2a_log.append(f"  {t['period_label']} {d.get('period')}.{d.get('year')}")
        self.train2a_log.append(f"  {t['total_fights']} {d.get('total_fights')}")
        self.train2a_log.append(f"  {t['processed']} {d.get('trained_fights')}")
        self.train2a_log.append(f"  {t['test_accuracy']} {d.get('accuracy', 0):.1f}%")
        self.train2a_log.append(f"  {t['best_accuracy']} {d.get('new_best_accuracy', 0):.1f}%")
        self.train2a_log.append(f"  {d.get('message', '')}")

    def _on_train2a_error(self, msg: str):
        self.train2a_log.append(f"\n❌ {msg}")

    # ---------- Вкладка "Обучение 2b" ----------
    def _build_train2b_tab(self) -> QWidget:
        t = LOCALES[self.lang]
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.train2b_form_group = QGroupBox(t["tournament_date"])
        f_layout = QHBoxLayout(self.train2b_form_group)
        self.train2b_date = QDateEdit()
        self.train2b_date.setCalendarPopup(True)
        self.train2b_date.setDate(QDate.currentDate())
        self.train2b_date.setDisplayFormat("yyyy-MM-dd")
        f_layout.addWidget(self.train2b_date, 1)
        self.train2b_load_btn = QPushButton(t["load_card"])
        self.train2b_load_btn.setProperty("class", "primary")
        self.train2b_load_btn.clicked.connect(self._load_train2b_card)
        f_layout.addWidget(self.train2b_load_btn)
        layout.addWidget(self.train2b_form_group)

        self.train2b_list = QListWidget()
        self.train2b_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.train2b_list.itemClicked.connect(self._on_train2b_item_clicked)
        layout.addWidget(self.train2b_list, 1)

        btn_row = QHBoxLayout()
        self.train2b_run_btn = QPushButton(t["start_check"])
        self.train2b_run_btn.setProperty("class", "primary")
        self.train2b_run_btn.clicked.connect(self._start_train2b)
        btn_row.addWidget(self.train2b_run_btn)
        layout.addLayout(btn_row)

        self.train2b_result = QTextEdit()
        self.train2b_result.setReadOnly(True)
        self.train2b_result.setMinimumHeight(220)
        layout.addWidget(self.train2b_result)
        return tab

    def _load_train2b_card(self):
        date = self.train2b_date.date().toString("yyyy-MM-dd")
        self.train2b_list.clear()
        self.train2b_result.clear()
        url = f"{API_URL}/api/card?date={date}&device_id={self.device_id}"
        w = JSONWorker("GET", url)
        w.done_signal.connect(self._on_train2b_card_loaded)
        w.error_signal.connect(self._on_net_error)
        self.workers.append(w)
        w.finished.connect(lambda: self.workers.remove(w))
        w.start()

    def _on_train2b_card_loaded(self, data: dict):
        t = LOCALES[self.lang]
        if data.get("status") == "error" or not data.get("fights"):
            self.train2b_result.setText(f"❌ {data.get('message', t['no_fights'])}")
            return
        self.train2b_card = data["fights"]
        for i, f in enumerate(self.train2b_card, 1):
            text = f"#{i}  {f['fighter_a']} vs {f['fighter_b']}"
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, i - 1)
            self.train2b_list.addItem(item)

    def _on_train2b_item_clicked(self, item: QListWidgetItem):
        if item.checkState() == Qt.CheckState.Checked:
            item.setCheckState(Qt.CheckState.Unchecked)
        else:
            item.setCheckState(Qt.CheckState.Checked)

    def _start_train2b(self):
        t = LOCALES[self.lang]
        indices = []
        for i in range(self.train2b_list.count()):
            item = self.train2b_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                indices.append(item.data(Qt.ItemDataRole.UserRole))
        if not indices:
            QMessageBox.warning(self, t["error"], t["select_fight"])
            return
        self.train2b_result.clear()
        self.train2b_result.append(t["checking_model"])
        payload = {
            "device_id": self.device_id,
            "date": self.train2b_date.date().toString("yyyy-MM-dd"),
            "fight_indices": indices,
            "lang": self.lang,
        }
        w = SSEWorker("/api/train/2b", payload, self)
        w.stage_signal.connect(self._on_train2b_stage)
        w.result_signal.connect(self._on_train2b_result)
        w.error_signal.connect(self._on_train2b_error)
        self.workers.append(w)
        w.finished.connect(lambda: self.workers.remove(w))
        w.start()

    def _on_train2b_stage(self, data: dict):
        title = data.get("title", "")
        self.train2b_result.append(f"\n🔍 {title}")

    def _on_train2b_result(self, data: dict):
        t = LOCALES[self.lang]
        d = data.get("data", data)
        if d.get("status") != "success":
            self.train2b_result.append(f"\n❌ {d.get('message', 'Ошибка')}")
            return
        lines = []
        lines.append(f"{t['total_checked']} {d.get('total_fights')}")
        lines.append(f"{t['correct']} {d.get('correct')} | {t['incorrect']} {d.get('incorrect')}")
        lines.append(f"{t['accuracy']} {d.get('accuracy', 0):.1f}%")
        lines.append("")
        for detail in d.get("details", []):
            mark = t["correct_mark"] if detail.get("is_correct") else t["incorrect_mark"]
            lines.append(f"{detail.get('f1')} vs {detail.get('f2')}")
            lines.append(f"  {t['prediction']} {detail.get('pred')} ({detail.get('pred_prob')}%)")
            lines.append(f"  {t['fact']} {detail.get('fact')}   {mark}")
            if detail.get("error"):
                lines.append(f"  ⚠ {detail.get('error')}")
            lines.append("")
        self.train2b_result.append("\n".join(lines))

    def _on_train2b_error(self, msg: str):
        self.train2b_result.setText(f"❌ {msg}")

    # ---------- Вкладка "Статус" ----------
    def _build_status_tab(self) -> QWidget:
        t = LOCALES[self.lang]
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.status_btn = QPushButton(t["check_status"])
        self.status_btn.setProperty("class", "primary")
        self.status_btn.clicked.connect(self._refresh_status)
        layout.addWidget(self.status_btn)

        self.status_output = QTextEdit()
        self.status_output.setReadOnly(True)
        layout.addWidget(self.status_output, 1)
        return tab

    def _refresh_status(self):
        t = LOCALES[self.lang]
        self.status_output.setText(t["requesting"])
        self._do_status_request()

    def _refresh_status_silent(self):
        self._do_status_request(silent=True)

    def _do_status_request(self, silent: bool = False):
        url = f"{API_URL}/api/status?device_id={self.device_id}"
        w = JSONWorker("GET", url)
        if silent:
            w.done_signal.connect(self._on_status_silent)
        else:
            w.done_signal.connect(self._on_status_done)
        w.error_signal.connect(
            lambda m: None if silent else self.status_output.setText(f"❌ {m}")
        )
        self.workers.append(w)
        w.finished.connect(lambda: self.workers.remove(w))
        w.start()

    def _on_status_done(self, data: dict):
        t = LOCALES[self.lang]
        lines = [
            f"Device ID:   {data.get('device_id')}",
            f"{t['balance']}     {data.get('balance')} {t['balance_label']}",
            f"{t['tariff']}      {data.get('plan')}",
            f"{t['expires']} {data.get('expires_at')}",
            f"{t['active']}      {t['yes'] if data.get('is_active') else t['no']}",
        ]
        self.status_output.setText("\n".join(lines))
        self._update_balance_from(data)

    def _on_status_silent(self, data: dict):
        self._update_balance_from(data)

    def _update_balance_from(self, data: dict):
        t = LOCALES[self.lang]
        try:
            self.balance = int(data.get("balance", self.balance))
            self.balance_label.setText(f"{t['balance']} {self.balance}")
        except (TypeError, ValueError):
            pass

    def _on_net_error(self, msg: str):
        t = LOCALES[self.lang]
        self.card_status.setText(f"❌ {msg}")
        QMessageBox.critical(self, t["network_error"], msg)

    def _exit_app(self):
        reply = QMessageBox.question(
            self,
            "Выход / Exit",
            "Вы уверены, что хотите выйти? / Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QApplication.quit()


# === ТОЧКА ВХОДА ===
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    device_id = load_or_create_hwid()

    if not LANGUAGE_FILE.exists():
        lang_dlg = LanguageDialog()
        if not lang_dlg.exec():
            sys.exit(0)
        selected_lang = lang_dlg.selected_lang
        try:
            LANGUAGE_FILE.write_text(selected_lang, encoding="utf-8")
        except Exception as e:
            print(f"Не удалось сохранить язык: {e}")
    else:
        try:
            selected_lang = LANGUAGE_FILE.read_text(encoding="utf-8").strip()
            if selected_lang not in ("ru", "en"):
                selected_lang = "ru"
        except Exception:
            selected_lang = "ru"

    if not DISCLAIMER_FILE.exists():
        dlg = DisclaimerDialog(selected_lang)
        if not dlg.exec():
            sys.exit(0)
        try:
            DISCLAIMER_FILE.write_text("1", encoding="utf-8")
        except Exception as e:
            print(f"Не удалось сохранить флаг согласия: {e}")

    reg = autoregister(device_id)
    initial_balance = 0
    welcome = ""

    if reg and reg.get("status") == "created":
        initial_balance = reg.get("balance", 20)
        welcome = reg.get(
            "message",
            f"Добро пожаловать! Вам начислено {initial_balance} бесплатных прогнозов.",
        )
    elif reg and reg.get("status") == "existing":
        initial_balance = reg.get("balance", 0)
        msg = reg.get("message", "С возвращением!")
        welcome = f"{msg}\nБаланс: {initial_balance} прогнозов."
    elif reg:
        initial_balance = reg.get("balance", 0)
        welcome = (
            f"Сервер ответил неизвестным статусом: {reg.get('status')}\n"
            f"Баланс: {initial_balance} прогнозов."
        )
    else:
        welcome = (
            "Не удалось связаться с сервером.\n"
            f"Проверьте доступность {API_URL}\n"
            "Программа запущена в режиме просмотра."
        )

    win = MainWindow(device_id, initial_balance, selected_lang)
    win.show()
    if welcome:
        QMessageBox.information(win, "MMA Predictor AI", welcome)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()