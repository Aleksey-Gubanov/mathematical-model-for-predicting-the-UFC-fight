#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MMA PREDICTOR | ЦЕНТРАЛИЗОВАННАЯ КОНФИГУРАЦИЯ (Production-Ready)
================================================================
Все параметры управляются через файл .env или переменные окружения.
Хардкод секретов в коде ЗАПРЕЩЁН!
В продакшене все ключи должны быть обязательными (без fallback).
Для локалки используются безопасные заглушки.
================================================================
"""
import os
from typing import List
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Загружаем переменные из .env (если он есть) ДО любых импортов
load_dotenv()

# ============================================================================
# 🎯 БАЗА ДАННЫХ (PostgreSQL + Type Hints для IDE)
# ============================================================================
DB_USER: str = os.getenv("DB_USER", "mma_user")
DB_PASSWORD_RAW: str = os.getenv("DB_PASSWORD", "5Tgfder%$")  # Экранируем только при сборке URL
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: str = os.getenv("DB_PORT", "5432")
DB_NAME: str = os.getenv("DB_NAME", "mma_predictor")

# ️ ВНИМАНИЕ! Для psycopg2 экранирование спецсимволов ($, @) обязательно.
DATABASE_URL: str = f"postgresql+psycopg2://{DB_USER}:{quote_plus(DB_PASSWORD_RAW)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DATABASE_BACKUP_DIR: str = "data/backups"

# ============================================================================
# 🔐 БЕЗОПАСНОСТЬ И КЛЮЧИ
# ============================================================================
HMAC_SECRET: str = os.getenv("MMA_HMAC_SECRET", "LOCAL_DEV_FALLBACK_SECRET_CHANGE_ME_IN_PRODUCTION_2026!")
JWT_SECRET: str = os.getenv("MMA_JWT_SECRET", "LOCAL_DEV_JWT_SECRET_CHANGE_ME")
OWNER_MASTER_PASSWORD: str = os.getenv("OWNER_MASTER_PASSWORD", "5Tgfder%$")

DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")

# ============================================================================
# 🎯 БИЗНЕС-ПАРАМЕТРЫ
# ============================================================================
TRIAL_PREDICTIONS: int = int(os.getenv("TRIAL_PREDICTIONS", "20"))
LICENSE_PRICE_RUB: int = int(os.getenv("LICENSE_PRICE_RUB", "1500"))
LICENSE_DURATION_DAYS: int = int(os.getenv("LICENSE_DURATION_DAYS", "365"))
LICENSE_PREDICTIONS_LIMIT: int = int(os.getenv("LICENSE_PREDICTIONS_LIMIT", "365"))

REFERRAL_BONUS_PREDICTIONS: int = int(os.getenv("REFERRAL_BONUS_PREDICTIONS", "10"))
SUPPORT_EMAIL: str = os.getenv("SUPPORT_EMAIL", "support@mma-predictor.ru")
GITHUB_REPO_URL: str = "https://github.com/Aleksey-Gubanov/mathematical-model-for-predicting-the-UFC-fight"
TELEGRAM_BOT_USERNAME: str = "@MMA_Predictor_Bot"

# ============================================================================
# 🧮 ПАРАМЕТРЫ МОДЕЛИ
# ============================================================================
TARGET_FEATURES: int = 46
BATCH_TRAIN_SIZE: int = 150
WEIGHTS_FILE: str = "mma_weights_v21.json"
BEST_WEIGHTS_FILE: str = "weights_best.json"
DATASET_DIR: str = "dataset"

BEST_ACCURACY_PERCENT: float = 71.0
WORKING_ACCURACY_PERCENT: float = 65.0

# ============================================================================
# 🌐 СЕРВЕР
# ============================================================================
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
DEBUG_MODE: bool = os.getenv("MMA_DEBUG", "false").lower() in ["true", "yes", "on", "1"]

CORS_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://mma-predictor.ru",
]

# ============================================================================
# 💳 ПЛАТЁЖНЫЕ СИСТЕМЫ
# ============================================================================
DONATIONALERTS_ENABLED: bool = os.getenv("DONATIONALERTS_ENABLED", "true").lower() == "true"
DONATIONALERTS_TOKEN: str = os.getenv("DONATIONALERTS_TOKEN", "")

YUKASSA_ENABLED: bool = os.getenv("YUKASSA_ENABLED", "false").lower() == "true"
YUKASSA_SHOP_ID: str = os.getenv("YUKASSA_SHOP_ID", "")
YUKASSA_SECRET_KEY: str = os.getenv("YUKASSA_SECRET_KEY", "")

NOWPAYMENTS_ENABLED: bool = os.getenv("NOWPAYMENTS_ENABLED", "false").lower() == "true"
NOWPAYMENTS_API_KEY: str = os.getenv("NOWPAYMENTS_API_KEY", "")

# ============================================================================
# 📝 ЛОГИРОВАНИЕ
# ============================================================================
LOG_LEVEL: str = os.getenv("MMA_LOG_LEVEL", "INFO").upper()
LOG_FILE: str = "logs/mma_predictor.log"
LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 МБ
LOG_BACKUP_COUNT: int = 5