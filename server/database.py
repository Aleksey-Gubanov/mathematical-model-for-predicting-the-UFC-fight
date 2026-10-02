#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERVER DATABASE | Модели и конфигурация SQLAlchemy
================================================================
Реализует структуру БД для SaaS-сервиса:
1. User: пользователи (привязка по device_id/email)
2. License: баланс прогнозов и статус подписки (20 триалов по умолчанию)
3. Prediction: история прогнозов для аналитики и дообучения модели
4. Payment: история транзакций
================================================================
"""
import os
import sys
from datetime import datetime, timezone
from typing import Optional, List


# Импортируем модуль целиком (так надежнее для статического анализа IDE)
import config

# Явная подсказка типов для IDE — устраняет Unresolved reference
DATABASE_URL: str = config.DATABASE_URL

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, JSON, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session


# ============================================================================
# 1. КОНФИГУРАЦИЯ ДВИЖКА (ENGINE) И СЕССИИ
# ============================================================================
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Предотвращает "Connection dropped" при долгих простоях
    echo=False,          # Установить True только для отладки SQL-запросов
    pool_size=10,        # Размер пула соединений
    max_overflow=20      # Максимальное количество дополнительных соединений
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для declarative моделей
Base = declarative_base()


# ============================================================================
# 2. МОДЕЛИ ДАННЫХ (ТАБЛИЦЫ)
# ============================================================================

class User(Base):
    """Пользователь системы. Идентифицируется по device_id (HWID) или email."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), unique=True, index=True, nullable=False,
                       comment="Хэш аппаратного ID или UUID")
    email = Column(String(128), unique=True, index=True, nullable=True,
                   comment="Email для восстановления/уведомлений")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Связи
    license = relationship("License", back_populates="user", uselist=False, cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_user_device_id', 'device_id'),
        Index('idx_user_email', 'email'),
    )


class License(Base):
    """Лицензия пользователя: баланс прогнозов и статус подписки."""
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Бизнес-логика: 20 бесплатных прогнозов при регистрации
    balance = Column(Integer, default=20, nullable=False,
                     comment="Остаток бесплатных прогнозов")
    plan = Column(String(32), default="free", nullable=False,
                  comment="Тип тарифа: free, pro, unlimited")

    expires_at = Column(DateTime, nullable=True,
                        comment="Дата окончания платной подписки (NULL для бесплатного плана)")
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="license")

    __table_args__ = (
        Index('idx_license_user_id', 'user_id'),
        Index('idx_license_plan', 'plan'),
    )


class Prediction(Base):
    """История прогнозов. Используется для аналитики и сбора данных для дообучения."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    fighter_a = Column(String(128), nullable=False)
    fighter_b = Column(String(128), nullable=False)

    # Результат прогноза модели (JSON: winner, prob, method, round)
    prediction_result = Column(JSON, nullable=False)

    # Фактический исход (заполняется постфактум для валидации точности)
    actual_result = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="predictions")

    __table_args__ = (
        Index('idx_prediction_user_id', 'user_id'),
        Index('idx_prediction_created_at', 'created_at'),
    )


class Payment(Base):
    """История платежей и активаций лицензий."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    amount = Column(Float, nullable=False, comment="Сумма платежа")
    currency = Column(String(3), default="RUB", nullable=False)

    status = Column(String(32), default="pending", nullable=False,
                    comment="Статус: pending, success, failed, refunded")
    provider = Column(String(64), nullable=False,
                      comment="Поставщик: donationalerts, yukassa, crypto")

    transaction_id = Column(String(128), unique=True, index=True, nullable=False,
                            comment="Внешний ID транзакции")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="payments")

    __table_args__ = (
        Index('idx_payment_user_id', 'user_id'),
        Index('idx_payment_status', 'status'),
        Index('idx_payment_transaction_id', 'transaction_id'),
    )


# ============================================================================
# 3. УТИЛИТЫ ДЛЯ РАБОТЫ С БД
# ============================================================================

def get_db():
    """
    Генератор сессии БД для использования в качестве зависимости FastAPI (Depends).
    Гарантирует закрытие сессии после запроса.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Создание всех таблиц в БД.
    ⚠️ Использовать ТОЛЬКО при первом запуске. В продакшене предпочтительны миграции Alembic.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ База данных инициализирована (таблицы созданы или уже существуют).")


def create_trial_license(db: Session, user_id: int) -> License:
    """
    Создаёт стартовую лицензию с 20 бесплатными прогнозами.
    """
    license = License(
        user_id=user_id,
        balance=20,
        plan="free",
        expires_at=None,
        is_active=True
    )
    db.add(license)
    db.commit()
    db.refresh(license)
    return license