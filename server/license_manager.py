#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERVER LICENSE MANAGER | Управление лицензиями и балансом
================================================================
Реализует бизнес-логику доступа к SaaS-сервису:
1. Регистрация пользователя с 20 триальными прогнозами
2. Генерация и валидация HMAC-подписанных ключей активации
3. Проверка и списание баланса прогнозов
================================================================
"""
import hashlib
import hmac
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

# ✅ ОТНОСИТЕЛЬНЫЙ импорт для файлов внутри папки server
from .database import (
    SessionLocal, User, License, Prediction, Payment,
    create_trial_license
)
from sqlalchemy.orm import Session


import config
import json


# ============================================================================
# 1. ГЕНЕРАЦИЯ И ПРОВЕРКА HMAC-КЛЮЧЕЙ
# ============================================================================

def generate_license_key(device_id: str, days: int = config.LICENSE_DURATION_DAYS) -> str:
    """Генерирует лицензионный ключ формата: MMA-<device_id>-<YYYYMMDD>-<HMAC_16>"""
    expiry_date = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y%m%d")
    payload = f"{device_id}:{expiry_date}"

    signature = hmac.new(
        config.HMAC_SECRET.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:16]

    return f"MMA-{device_id}-{expiry_date}-{signature}"


def verify_license_key(key: str, device_id: str) -> Dict[str, Any]:
    """Проверяет валидность ключа (формат, подпись, срок действия)."""
    parts = key.split("-")
    if len(parts) != 4 or parts[0] != "MMA":
        return {"valid": False, "error": "Неверный формат ключа"}

    key_device_id, expiry_date_str, signature = parts[1], parts[2], parts[3]

    if key_device_id != device_id:
        return {"valid": False, "error": "Ключ привязан к другому устройству"}

    payload = f"{device_id}:{expiry_date_str}"
    expected_signature = hmac.new(
        config.HMAC_SECRET.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:16]

    if not hmac.compare_digest(signature, expected_signature):
        return {"valid": False, "error": "Недействительная подпись ключа"}

    try:
        expiry_date = datetime.strptime(expiry_date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry_date:
            return {"valid": False, "error": "Срок действия ключа истёк"}
    except ValueError:
        return {"valid": False, "error": "Неверная дата в ключе"}

    return {"valid": True, "error": "", "expiry_date": expiry_date_str}


# ============================================================================
# 2. УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ И БАЛАНСОМ
# ============================================================================

def register_user(db: Session, device_id: str, email: Optional[str] = None) -> Dict[str, Any]:
    """Регистрирует нового пользователя или возвращает данные существующего."""
    user = db.query(User).filter(User.device_id == device_id).first()

    if user:
        license_obj = db.query(License).filter(License.user_id == user.id).first()
        return {
            "status": "existing",
            "user_id": user.id,
            "balance": license_obj.balance if license_obj else 0,
            "plan": license_obj.plan if license_obj else "free",
            "message": "С возвращением!"
        }

    new_user = User(device_id=device_id, email=email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    create_trial_license(db, new_user.id)

    return {
        "status": "created",
        "user_id": new_user.id,
        "balance": config.TRIAL_PREDICTIONS,
        "plan": "free",
        "message": f"Добро пожаловать! Вам начислено {config.TRIAL_PREDICTIONS} бесплатных прогнозов."
    }


def activate_license(db: Session, device_id: str, key: str) -> Dict[str, Any]:
    """Активирует годовую лицензию по ключу."""
    validation = verify_license_key(key, device_id)
    if not validation["valid"]:
        return {"success": False, "error": validation["error"]}

    user = db.query(User).filter(User.device_id == device_id).first()
    if not user:
        return {"success": False, "error": "Пользователь не найден. Сначала зарегистрируйтесь."}

    license_obj = db.query(License).filter(License.user_id == user.id).first()
    if not license_obj:
        license_obj = License(user_id=user.id)
        db.add(license_obj)

    license_obj.plan = "pro"
    license_obj.balance = config.LICENSE_PREDICTIONS_LIMIT
    # Сохраняем с часовым поясом
    license_obj.expires_at = datetime.strptime(validation["expiry_date"], "%Y%m%d").replace(tzinfo=timezone.utc)
    license_obj.is_active = True

    db.commit()
    db.refresh(license_obj)

    return {
        "success": True,
        "message": "Лицензия успешно активирована!",
        "balance": license_obj.balance,
        "expires_at": license_obj.expires_at.strftime("%Y-%m-%d")
    }


def check_and_decrement_balance(db: Session, device_id: str) -> Dict[str, Any]:
    """Проверяет наличие прогнозов и списывает 1 при успехе."""
    user = db.query(User).filter(User.device_id == device_id).first()
    if not user:
        return {"allowed": False, "balance": 0, "error": "Пользователь не найден"}

    license_obj = db.query(License).filter(License.user_id == user.id).first()
    if not license_obj or not license_obj.is_active:
        return {"allowed": False, "balance": 0, "error": "Лицензия неактивна"}

    # ✅ ИСПРАВЛЕНИЕ: Безопасное сравнение времени (учитывает naive/aware)
    if license_obj.expires_at:
        expires_at = license_obj.expires_at
        # Если БД вернула время без часового пояса, добавляем UTC
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at:
            license_obj.is_active = False
            db.commit()
            return {"allowed": False, "balance": 0, "error": "Срок действия лицензии истёк"}

    # Проверка баланса (-1 означает безлимит)
    if license_obj.balance > 0 or license_obj.balance == -1:
        if license_obj.balance != -1:
            license_obj.balance -= 1
            db.commit()

        return {"allowed": True, "balance": license_obj.balance, "error": ""}

    return {
        "allowed": False,
        "balance": 0,
        "error": f"Лимит прогнозов исчерпан. Приобретите лицензию за {config.LICENSE_PRICE_RUB}₽"
    }


def get_user_status(db: Session, device_id: str) -> Dict[str, Any]:
    """Возвращает текущий статус пользователя для отображения в UI."""
    user = db.query(User).filter(User.device_id == device_id).first()
    if not user:
        return {"exists": False}

    license_obj = db.query(License).filter(License.user_id == user.id).first()

    return {
        "exists": True,
        "device_id": user.device_id,
        "email": user.email,
        "balance": license_obj.balance if license_obj else 0,
        "plan": license_obj.plan if license_obj else "free",
        "expires_at": license_obj.expires_at.strftime("%Y-%m-%d") if license_obj and license_obj.expires_at else "Бессрочно",
        "is_active": license_obj.is_active if license_obj else False
    }
def refund_balance(db: Session, device_id: str) -> Dict[str, Any]:
    """Возвращает 1 прогноз, если эталонный расчёт не состоялся."""
    user = db.query(User).filter(User.device_id == device_id).first()
    if not user:
        return {"success": False, "balance": 0}

    license_obj = db.query(License).filter(License.user_id == user.id).first()
    if not license_obj:
        return {"success": False, "balance": 0}

    # -1 = безлимит, возвращать нечего
    if license_obj.balance == -1:
        return {"success": True, "balance": -1}

    license_obj.balance += 1
    db.commit()
    return {"success": True, "balance": license_obj.balance}


# ============================================================================
# 3. SMS-ОПЛАТА ЧЕРЕЗ СБП (резервирование и применение платежей)
# ============================================================================

def _load_tariffs() -> dict:
    """Читает tariffs.json из корня проекта. Позволяет менять тарифы без перезапуска сервера."""
    tariffs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tariffs.json")
    try:
        with open(tariffs_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка чтения tariffs.json: {e}")
        return {"tariffs": {}, "sbp_phone": ""}


def create_payment_reservation(db: Session, device_id: str, tariff_price: int) -> Dict[str, Any]:
    """
    Создаёт резервирование платежа: уникальная сумма с копейками + запись в Payment.
    Возвращает amount, transaction_id, expires_at, sbp_phone.
    """

    import random
    from datetime import timedelta

    tariffs_data = _load_tariffs()
    tariff_key = str(tariff_price)
    tariff = tariffs_data.get("tariffs", {}).get(tariff_key)
    if not tariff:
        return {"success": False, "error": "Неизвестный тариф"}

    user = db.query(User).filter(User.device_id == device_id).first()
    if not user:
        return {"success": False, "error": "Пользователь не найден"}

    # Генерируем уникальную сумму: базовая цена + случайные копейки 1-99
    for _ in range(50):
        cents = random.randint(1, 99)
        amount = float(tariff_price) + cents / 100.0
        # Проверяем, что такая сумма не зарезервирована в последние 15 минут
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        existing = (db.query(Payment)
                    .filter(Payment.amount == amount,
                            Payment.status == "pending",
                            Payment.created_at >= cutoff)
                    .first())
        if not existing:
            break
    else:
        return {"success": False, "error": "Не удалось сгенерировать уникальную сумму"}

    transaction_id = f"sbp_{device_id}_{int(datetime.now(timezone.utc).timestamp())}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    payment = Payment(
        user_id=user.id,
        amount=amount,
        currency="RUB",
        status="pending",
        provider="sbp_sms",
        transaction_id=transaction_id,
    )
    payment.created_at = datetime.now(timezone.utc)
    db.add(payment)
    db.commit()

    return {
        "success": True,
        "amount": amount,
        "transaction_id": transaction_id,
        "expires_at": expires_at.isoformat(),
        "sbp_phone": tariffs_data.get("sbp_phone", ""),
        "predictions": tariff.get("predictions", 0),
        "days": tariff.get("days", 0),
    }


def finalize_payment(db: Session, transaction_id: str) -> Dict[str, Any]:
    """
    Применяет оплаченный платёж: начисляет прогнозы и продлевает срок.
    Вызывается из webhook-а после совпадения суммы SMS с pending-платежом.
    """

    payment = db.query(Payment).filter(
        Payment.transaction_id == transaction_id,
        Payment.status == "pending"
    ).first()
    if not payment:
        return {"success": False, "error": "Платёж не найден или уже обработан"}

    # Определяем тариф по целой части суммы
    tariffs_data = _load_tariffs()
    tariff_key = str(int(payment.amount))
    tariff = tariffs_data.get("tariffs", {}).get(tariff_key)
    if not tariff:
        payment.status = "failed"
        db.commit()
        return {"success": False, "error": "Неизвестный тариф для суммы"}

    license_obj = db.query(License).filter(License.user_id == payment.user_id).first()
    if not license_obj:
        license_obj = License(user_id=payment.user_id, balance=0, plan="free", is_active=True)
        db.add(license_obj)

    # Суммируем прогнозы
    license_obj.balance = (license_obj.balance or 0) + tariff.get("predictions", 0)

    # Срок = максимум из текущего и (сейчас + дни тарифа)
    days = tariff.get("days", 0)
    if days > 0:
        new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
        if license_obj.expires_at:
            current_expiry = license_obj.expires_at
            if current_expiry.tzinfo is None:
                current_expiry = current_expiry.replace(tzinfo=timezone.utc)
            license_obj.expires_at = max(current_expiry, new_expiry)
        else:
            license_obj.expires_at = new_expiry
        license_obj.is_active = True

    payment.status = "success"
    db.commit()

    return {
        "success": True,
        "new_balance": license_obj.balance,
        "added_predictions": tariff.get("predictions", 0),
        "expires_at": license_obj.expires_at.isoformat() if license_obj.expires_at else None,
    }