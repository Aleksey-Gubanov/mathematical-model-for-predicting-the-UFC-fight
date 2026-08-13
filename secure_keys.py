#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SECURE KEYS | Зашифрованное хранилище API-ключей
================================================================
- Шифрование AES через мастер-пароль
- Отдельно от SecureNeuralChannel (чтобы не ломать архитектуру)
================================================================
"""
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

KEYS_FILE = "secure_keys.enc"
SALT = b"mma_predictor_2026_salt"

class SecureKeys:
    _fernet = None

    @classmethod
    def init(cls, master_password: str) -> bool:
        """Инициализация хранилища по мастер-паролю"""
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=SALT,
                iterations=100000
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            cls._fernet = Fernet(key)
            return True
        except Exception as e:
            print(f"❌ Ошибка инициализации SecureKeys: {e}")
            return False

    @classmethod
    def get(cls, key_name: str) -> str:
        """Получить ключ по имени"""
        if not cls._fernet:
            raise RuntimeError("SecureKeys не инициализирован!")

        if not os.path.exists(KEYS_FILE):
            return ""

        try:
            with open(KEYS_FILE, "rb") as f:
                encrypted_data = f.read()
            decrypted = cls._fernet.decrypt(encrypted_data)
            keys = json.loads(decrypted.decode())
            return keys.get(key_name, "")
        except:
            return ""

    @classmethod
    def save(cls, key_name: str, value: str) -> bool:
        """Сохранить ключ"""
        if not cls._fernet:
            raise RuntimeError("SecureKeys не инициализирован!")

        # Загружаем существующие ключи
        keys = {}
        if os.path.exists(KEYS_FILE):
            try:
                with open(KEYS_FILE, "rb") as f:
                    decrypted = cls._fernet.decrypt(f.read())
                keys = json.loads(decrypted.decode())
            except:
                keys = {}

        # Добавляем новый ключ
        keys[key_name] = value

        # Шифруем и сохраняем
        encrypted = cls._fernet.encrypt(json.dumps(keys).encode())
        with open(KEYS_FILE, "wb") as f:
            f.write(encrypted)

        return True