#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""БЭКАП ПРОЕКТА ПЕРЕД ОЧИСТКОЙ"""
import shutil
import os
from datetime import datetime

backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
backup_dir = os.path.join("C:\\Users\\Aleksey\\Backups\\MMA", backup_name)
os.makedirs(backup_dir, exist_ok=True)

# Копируем ВЕСЬ проект
src = "C:\\Users\\Aleksey\\IdeaProjects\\untitled"
for item in os.listdir(src):
    s = os.path.join(src, item)
    d = os.path.join(backup_dir, item)
    if item in ['.venv', '__pycache__', '.idea', '.gigaide']:
        continue
    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copy2(s, d)

print(f"✅ Бэкап создан: {backup_dir}")