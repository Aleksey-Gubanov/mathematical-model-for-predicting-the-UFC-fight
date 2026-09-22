Цитата из вашего сообщения:

> **«изучай! дай новый!»**

Изучил. Вот **новый `README.md`** — под текущее состояние модели.

---

```markdown
# 🥊 MATH ENGINE v55.7 — MMA Fight Prediction System

Система прогнозирования результатов боёв MMA на основе математической модели с инкрементальным обучением.

---

## 🎯 Основные возможности

- Прогнозирование победителя с вероятностью от 0 до 100%
- **46 признаков** для анализа бойцов (статистика, физика, психология)
- Инкрементальное обучение на батчах по **150 боёв**
- Z-score нормализация признаков
- Ограничения весов для предотвращения переобучения
- Тройной арбитраж: **Математика + ИИ-Аналитик + Букмекер**
- Слепой ИИ (обезличенные профили X/Y) для веса образцов
- Бэктест по дате (режим 2b)
- Калибровка и чекпоинты (best / baseline)
- Авто-возврат к лучшим весам при деградации > 4%

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

## 🚀 Быстрый старт

### Установка зависимостей:

```bash
pip install -r requirements.txt
```

### Запуск основного интерфейса:

```bash
python mma_predictor.py
```

### Структура проекта:

```
├── math_engine.py              # Математическое ядро модели
├── mma_predictor.py            # Главный интерфейс (прогноз, обучение, калибровка)
├── deep_ai_analyst.py          # Обогащение данных через DeepSeek API
├── secure_neural_channel.py    # Безопасное подключение к API
├── secure_keys.py              # Шифрование ключей
├── espn_parser.py              # Парсинг кардов и результатов ESPN
├── odds_api_client.py          # Коэффициенты букмекеров
├── fighters_ids_manager.py     # База ID бойцов
├── mystic_calculator.py        # Мистические факторы
├── dashboard_api.py            # API для дашборда
├── dataset_audit.py            # Аудит датасета
├── requirements.txt            # Зависимости
├── mma_weights_v21.json        # Текущие веса модели
├── weights_best.json           # Лучшие веса (чекпоинт)
├── known_fighters_cache.json   # Кэш имён бойцов
└── dataset/                    # Датасет боёв
    ├── real_dataset_part*.json
    ├── fighters_ids.json
    ├── pending_buffer.json
    ├── recent_features.json
    └── holdout_registry.json
```

---

## 📈 Режимы работы

### 1 — ПРОГНОЗ
- Ввод даты (ДД.ММ.ГГГГ) или команды `1`
- Загрузка карда из ESPN
- Прогноз по каждому бою
- Тройной арбитраж (Математика + ИИ + БК)

### 2 — ОБУЧЕНИЕ
- **2a** — обучение на свежих боях из ESPN (по месяцу или диапазону)
- **2b** — бэктест по дате

### 3 — КАЛИБРОВКА
- **3a** — быстрая проверка точности
- **3d** — статус весов и файлов

### 0 — ВЫХОД
- Сохраняет `pending_buffer.json`

---

## 📊 Результаты

| Период | Модель | Слепой ИИ | Best |
|--------|--------|-----------|------|
| 08–11.2025 | 56.2% | 60.4% | 70.0% |
| 07.2026 | 60.5% | 57.9% | 70.0% |
| 04–06.2022 | 61.2% | 71.6% | 70.0% |
| 02–04.2022 | 68.1% | 73.9% | 70.0% |
| Все бои (3a) | **71.0%** | — | **70.0%** |

**Точность — живая.**  
Колеблется по периодам.  
Best = 70.0%.  
Средняя по периодам ≈ 64%.

---

## 🔧 Основные компоненты

### `math_engine.py`
- `AdvancedMathEngine` — ядро (логистическая регрессия)
- `MMAEngine` — главный движок с обучением
- `FeaturePairConstraints` — парные ограничения весов

### `mma_predictor.py`
- `run_month_training` — режим 2a
- `run_backtest_session` — режим 2b
- `handle_calibration_command` — режим 3
- `get_ai_arbitrator_prediction` — ИИ-арбитр
- `get_blind_ai_verdict` — слепой ИИ
- `apply_blind_tilt` — тилт прогноза

### `direct_test_101.py`
- Тестовый скрипт на 100 парах
- Не участвует в основном пайплайне

---

## 🧪 Тесты

```
test_blind_tilt.py
test_dataset_audit.py
test_deepseek.py
test_espn_athlete_fields.py
test_normalization_diagnostic.py
```

Запуск:
```bash
python test_blind_tilt.py
```

---

## 📝 Лицензия

MIT License

## 👥 Автор

Разработано для прогнозирования боёв UFC/MMA
```

---

## Что изменилось по сравнению со старым

| Пункт | Старый | Новый |
|-------|--------|-------|
| Версия | v55.0 | **v55.7** |
| BATCH_TRAIN_SIZE | 200 | **150** |
| EPOCHS | 200 | **100** |
| LEARNING_RATE | 0.015 | **0.005** |
| Запуск | `direct_test_101.py_й` | **`mma_predictor.py`** |
| Режимы | не описаны | **описаны** |
| Тройной арбитраж | не описан | **описан** |
| Слепой ИИ | не описан | **описан** |
| Результаты | 58.0% | **обновлены** |
| Структура | неполная | **полная** |
| Тесты | не указаны | **указаны** |

