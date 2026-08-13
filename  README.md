# 📄 README.md

```markdown
# 🥊 MATH ENGINE v55.0 - MMA Fight Prediction System

Система прогнозирования результатов боёв MMA на основе математической модели с инкрементальным обучением.

## 🎯 Основные возможности

- **Прогнозирование победителя** с вероятностью от 0 до 100%
- **46 признаков** для анализа бойцов (статистика, физические параметры, психологические факторы)
- **Инкрементальное обучение** на батчах по 200 боёв
- **Z-score нормализация** признаков
- **Ограничения весов** для предотвращения переобучения

## 📊 Архитектура модели

### Признаки (46):
- **Боец A/B** (17+17): recent_wins, fin_rate, sub_rate, td_def, grap_def, age, exp, fights_12m, months_off, wins, losses, stress, motivation, biorythm, camp_quality, mystic_factor, mystic_v2
- **Взаимодействия** (4): fin_x_td, sub_x_grap, rust_x_exp, stress_x_camp
- **Дополнительные** (8): reach, height, camp_encoded, children_factor

### Параметры обучения:
- Learning Rate: 0.015
- Epochs: 200
- Dropout: 5% (enriched features)
- MAX_ABS_WEIGHT: 0.1

## 🚀 Быстрый старт

### Установка зависимостей:
```bash
pip install -r requirements.txt
```

### Запуск теста:
```bash
python direct_test_101.py
```

### Структура проекта:
```
├── math_engine.py              # Математическое ядро модели
├── direct_test_101.py          # Тестовый скрипт на 200 боях
├── deep_ai_analyst.py          # Обогащение данных через DeepSeek API
├── secure_neural_channel.py    # Безопасное подключение к API
├── mma_weights_v21.json        # Обученные веса модели
└── dataset/                    # Датасет боёв
    ├── real_dataset_part*.json
    └── training_history.json
```

## 📈 Результаты

- **Точность на обучении**: 72.9%
- **Точность на тесте**: 58.0%
- **Обучено на**: 13,640 боях

## 🔧 Основные компоненты

### math_engine.py
- `AdvancedMathEngine` - ядро модели (логистическая регрессия)
- `MMAEngine` - главный движок с системой обучения
- `FeaturePairConstraints` - ограничения пар признаков

### direct_test_101.py
- Загрузка 200 боёв из датасета
- Прогнозирование и сравнение с фактом
- Инкрементальное обучение после теста

## 📝 Лицензия

MIT License

## 👥 Автор

Разработано для прогнозирования боёв UFC/MMA
```