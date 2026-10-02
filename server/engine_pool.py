#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERVER ENGINE POOL | Пул движков с блокировками
================================================================
Управляет общим экземпляром MMAEngine для всех пользователей.
Прогнозы - параллельно, обучение - последовательно.
================================================================
"""
import asyncio
import importlib.util
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


# Динамический импорт mma_predictor
spec = importlib.util.spec_from_file_location("mma_predictor", "mma_predictor.py")
mma_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mma_module)

MMAEngine = mma_module.MMAEngine
ESPNParser = mma_module.ESPNParser
DeepAIAnalyst = mma_module.DeepAIAnalyst


class EnginePool:
    """Singleton-пул движков с блокировками."""

    _instance: Optional[MMAEngine] = None
    _espn: Optional[ESPNParser] = None
    _analyst: Optional[DeepAIAnalyst] = None

    _lock = asyncio.Lock()  # Для инициализации
    _train_lock = asyncio.Lock()  # Только для обучения

    # Трекинг обучения для free-пользователей
    _training_log: Dict[str, datetime] = {}  # device_id -> last_training_time

    @classmethod
    async def get_engine(cls) -> MMAEngine:
        """Получить или создать движок (ленивая инициализация)."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    print("⚙️ Инициализация MMAEngine...")
                    cls._instance = MMAEngine()
                    cls._instance.recalibrate_scaler()
                    cls._espn = ESPNParser()
                    cls._analyst = DeepAIAnalyst()
                    print("✅ MMAEngine готов")
        return cls._instance

    @classmethod
    async def get_espn(cls) -> ESPNParser:
        await cls.get_engine()  # Убедиться, что инициализировано
        return cls._espn

    @classmethod
    async def get_analyst(cls) -> DeepAIAnalyst:
        await cls.get_engine()
        return cls._analyst

    @classmethod
    async def predict(cls, fight_data) -> Any:
        """Прогноз - параллельно (без блокировки)."""
        engine = await cls.get_engine()
        return engine.predict(fight_data)

    @classmethod
    async def train(cls, fight_data, result, f1: str, f2: str,
                    ai_factor: float = 1.0, blind_conf: Optional[float] = None) -> Dict[str, Any]:
        """Обучение - последовательно (с блокировкой)."""
        async with cls._train_lock:
            engine = await cls.get_engine()
            return engine.train_on_new_fight(fight_data, result, f1, f2, ai_factor, blind_conf)

    @classmethod
    def check_training_limit(cls, device_id: str, plan: str) -> Dict[str, Any]:
        """
        Проверить лимит обучения.
        Free: 1 раз в день
        Pro: без ограничений
        """
        if plan == "pro":
            return {"allowed": True, "reason": "Pro-подписка"}

        # Free-пользователь
        last_training = cls._training_log.get(device_id)
        if last_training and (datetime.now() - last_training) < timedelta(days=1):
            hours_left = 24 - (datetime.now() - last_training).total_seconds() / 3600
            return {
                "allowed": False,
                "reason": f"Free-лимит: 1 обучение в день. Следующее через {hours_left:.1f} ч"
            }

        return {"allowed": True, "reason": "Free-лимит доступен"}

    @classmethod
    def log_training(cls, device_id: str):
        """Записать факт обучения."""
        cls._training_log[device_id] = datetime.now()

    @classmethod
    async def flush_buffer(cls) -> Dict[str, Any]:
        """Принудительное обучение на буфере."""
        async with cls._train_lock:
            engine = await cls.get_engine()
            return engine.flush_buffer()