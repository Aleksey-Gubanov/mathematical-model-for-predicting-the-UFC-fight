# 🥊 MATH ENGINE v55.7 — MMA Fight Prediction System

Система прогнозирования результатов боёв MMA на основе математической модели с инкрементальным обучением и серверным SaaS-интерфейсом.

---

## 🎯 Цель проекта

Превратить локальную модель в коммерческий SaaS-сервис:
- **Цена:** 1500₽ / год
- **Триал:** 20 бесплатных прогнозов при регистрации
- **Каналы:** веб-интерфейс, Telegram-бот, desktop-клиент (в разработке)
- **Архитектура:** все вычисления на сервере, тонкие клиенты через API

---

## 🎯 Основные возможности

### Модель
- Прогнозирование победителя с вероятностью 0–100%
- **46 признаков** (статистика, физика, психология, стиль, лагерь, биоритмы, мистика)
- Инкрементальное обучение на батчах по **150 боёв**
- Z-score нормализация признаков
- Ограничения весов для предотвращения переобучения
- Тройной арбитраж: **Математика + ИИ-Аналитик + Букмекер**
- Слепой ИИ (обезличенные профили X/Y) для веса образцов
- Авто-возврат к лучшим весам при деградации > 4%

### Сервер (FastAPI)
- REST API для тонких клиентов
- SSE-стриминг этапов расчёта в реальном времени
- PostgreSQL для пользователей, лицензий, платежей, истории прогнозов
- HMAC-подписанные лицензионные ключи (привязка к устройству)
- Rate-limit и тарифные планы (free / pro)
- Bridge-архитектура: subprocess-изоляция ядра от серверного процесса

### Клиенты
- **Веб-интерфейс** (`server/mobile_client.html`) — 3 рабочих режима: прогноз, обучение 2a, бэктест 2b
- **Telegram-бот** — в разработке (aiogram 3.x)
- **Desktop / Mobile** — в планах

---

## 📊 Архитектура модели

### Признаки (46):

**Боец A (17):**
recent_wins, fin_rate, sub_rate, td_def, grap_def, age, exp, fights_12m,
months_off, wins, losses, stress_factor, motivation_index, biorythm_score,
camp_quality, mystic_factor, mystic_v2

**Боец B (17):** аналогично A.

**Взаимодействия (4):**
fin_x_td_A, sub_x_grap_A, rust_x_exp_A, stress_x_camp_A

**Дополнительные (8):**
a_reach, a_height, b_reach, b_height,
a_camp_encoded, b_camp_encoded,
a_children_factor, b_children_factor

### Параметры обучения (v55.7):

| Параметр | Значение |
|----------|----------|
| LEARNING_RATE | 0.005 |
| EPOCHS | 100 |
| L1_RATIO | 0.01 |
| ALPHA (L2) | 0.1 |
| DROPOUT_RATE | 0.2 (enriched: 0.05) |
| BATCH_TRAIN_SIZE | **150** |
| MIN_TRAIN_SIZE (flush) | 150 |
| TRAIN_SEED | 42 |
| WP_DAMPENING | 0.75 |
| ADAPTIVE_C | 0.5 |

### Ограничения весов:

- POSITIVE_ONLY_INDICES: [3, 4, 15, 20, 21]
- B_RECENT_WINS_MAX_ABS: 0.040
- A_LOSSES_MAX_ABS: 0.060
- B_MYSTIC_FACTOR_MAX_ABS: 0.030
- B_MONTHS_OFF_MAX_ABS: 0.060
- B_LOSSES_MAX_ABS: 0.100
- AGE_DIFF_MAX: 0.10
- BIAS_MAX_ABS: 0.05

---

## 📁 Структура проекта
mma_predictor/
├── math_engine.py # Математическое ядро модели (81,4 KB)
├── mma_predictor.py # CLI-интерфейс владельца (99,5 KB)
├── mma_predictor_bridge.py # Subprocess-мост для сервера (13,3 KB)
├── config.py # Централизованный конфиг (5,1 KB)
├── .env # Секреты и параметры окружения (вне git!)
│
├── deep_ai_analyst.py # Обогащение через DeepSeek API
├── secure_neural_channel.py # Безопасное подключение к LLM
├── secure_keys.py # Шифрование API-ключей
├── espn_parser.py # Парсинг кардов и результатов ESPN
├── odds_api_client.py # Коэффициенты The Odds API
├── fighters_ids_manager.py # База ID бойцов
├── mystic_calculator.py # Мистические факторы (дата рождения × дата боя)
├── dataset_audit.py # Аудит датасета
├── requirements.txt # Зависимости Python
├── pyproject.toml # Метаданные проекта
│
├── server/ # FastAPI сервер (SaaS-ядро)
│ ├── main.py # Эндпоинты + SSE-стриминг
│ ├── model_adapter.py # Обёртка над bridge
│ ├── engine_pool.py # Singleton-пул движков
│ ├── database.py # SQLAlchemy: users, licenses, predictions, payments
│ ├── license_manager.py # HMAC-ключи, балансы, триал
│ └── mobile_client.html # Веб-интерфейс (3 режима)
│
├── clients/ # Тонкие клиенты (задел)
├── dataset/ # Датасет боёв (публичный)
│ ├── real_dataset_part1..6.json
│ ├── fighters_ids.json # 605 KB: база ID бойцов
│ ├── pending_buffer.json # Буфер инкрементального обучения
│ ├── odds_cache.json # Кэш коэффициентов
│ ├── recent_features.json # Последние признаки для нормализатора
│ └── holdout_registry.json # Реестр holdout-боёв
│
├── data/ # Бэкапы БД (вне git!)
├── logs/ # Логи сервера (вне git!)
└── plans/ # Планирование и документация

1234567891011121314
2. Локальный CLI (режим владельца)
   bash

1
Интерфейс: 1 — Прогноз | 2 — Обучение (2a/2b) | 3 — Калибровка (3a/3d) | 0 — Выход
3. SaaS-сервер
   bash

12
Открыть: http://localhost:8000 → server/mobile_client.html (или отдельным статик-сервером)
4. Веб-интерфейс (3 режима)
   Прогноз: загрузка карда по дате → выбор боя → 4 этапа (данные, коэф., модель, ИИ-арбитр) → тройной арбитраж
   Обучение 2a: пакетное обучение на свежих боях ESPN (месяц/диапазон, год)
   Обучение 2b (бэктест): кард по дате → выбор боёв → проверка модели с деталями по каждому бою
   📈 Режимы работы
   CLI (mma_predictor.py)
   1 — ПРОГНОЗ: ввод даты (ДД.ММ.ГГГГ), загрузка карда ESPN, прогноз + арбитраж
   2 — ОБУЧЕНИЕ:
   2a — на свежих боях ESPN (месяц/диапазон)
   2b — бэктест по дате (проверка модели)
   3 — КАЛИБРОВКА:
   3a — быстрая проверка точности
   3d — статус весов и файлов
   0 — ВЫХОД: сохраняет pending_buffer.json
   Веб (server/mobile_client.html)
   Вкладки: Прогноз | Обучение 2a | Обучение 2b | Статус
   SSE-стриминг этапов в реальном времени
   Карточки боёв с деталями (прогноз %, факт, вердикт)
   📊 Результаты
   Период
   Модель
   Слепой ИИ
   Best
   08–11.2025
   56.2%
   60.4%
   70.0%
   07.2026
   60.5%
   57.9%
   70.0%
   04–06.2022
   61.2%
   71.6%
   70.0%
   02–04.2022
   68.1%
   73.9%
   70.0%
   Все бои (3a)
   71.0%
   —
   70.0%
   Точность — живая. Колеблется по периодам. Best = 70.0%. Средняя ≈ 64%.
   🔧 Основные компоненты
   math_engine.py (81,4 KB)
   AdvancedMathEngine — ядро (логистическая регрессия + ElasticNet)
   MMAEngine — главный движок с инкрементальным обучением
   FeaturePairConstraints — парные ограничения весов
   Авто-возврат к best-весам при деградации
   mma_predictor.py (99,5 KB)
   run_month_training — режим 2a (пакетное обучение)
   run_backtest_session — режим 2b (интерактивный бэктест)
   handle_calibration_command — режим 3 (3a/3d)
   get_ai_arbitrator_prediction — ИИ-арбитр (тройной арбитраж)
   get_blind_ai_verdict — слепой ИИ (обезличенные X/Y)
   apply_blind_tilt — тилт прогноза в зоне неопределённости
   server/ (SaaS-ядро)
   main.py — FastAPI эндпоинты + SSE-стриминг
   model_adapter.py — обёртка над subprocess-мостом
   engine_pool.py — Singleton-пул движков + free-лимит обучения
   database.py — SQLAlchemy модели (User, License, Prediction, Payment)
   license_manager.py — HMAC-ключи, регистрация, активация, списание
   mobile_client.html — веб-интерфейс (35,1 KB)
   mma_predictor_bridge.py (13,3 KB)
   Subprocess-интерфейс для веб-сервера
   Логи → stderr, JSON → stdout
   Изолирует ядро от серверного процесса
   config.py (5,1 KB)
   Централизованный конфиг: БД, безопасность, бизнес-параметры, модель, сервер, платёжки
   Все значения через os.getenv() с безопасными fallback
   🧪 Тесты

1234
Запуск: python test_dataset_audit.py
🔐 Безопасность
Мастер-пароль и ключи API шифруются через Fernet (HMAC-SHA256 + AES)
Лицензионные ключи: MMA-<device_id>-<YYYYMMDD>-<HMAC_16>
Timing-safe проверка подписи (hmac.compare_digest)
.env и *.enc вне git (.gitignore v2.1)
Веса модели вне git
📝 Лицензия
MIT License
👥 Автор
Разработано для прогнозирования боёв UFC/MMA.
Репозиторий: https://github.com/Aleksey-Gubanov/mathematical-model-for-predicting-the-UFC-fight