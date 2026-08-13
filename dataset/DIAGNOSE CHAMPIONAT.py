#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSE CHAMPIONAT | ДИАГНОСТИКА СТРУКТУРЫ САЙТА
================================================================
Показывает что РЕАЛЬНО есть на странице championat.com
НЕ ищет бои — просто показывает структуру данных
================================================================
"""
import requests
from bs4 import BeautifulSoup
import re

URL = "https://www.championat.com/boxing/_ufc/tournament/822/calendar/"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("=" * 70)
print("🔍 ДИАГНОСТИКА САЙТА CHAMPIONAT.COM")
print("=" * 70)
print(f"🌐 URL: {URL}")
print("=" * 70)

# Получаем HTML
resp = requests.get(URL, headers=HEADERS, timeout=15)
print(f"\n✅ Статус: {resp.status_code}")
print(f"📦 Размер HTML: {len(resp.text)} байт")

soup = BeautifulSoup(resp.text, 'lxml')

# Ищем таблицы
tables = soup.find_all('table')
print(f"\n📊 Найдено таблиц: {len(tables)}")

if not tables:
    print("❌ Таблицы не найдены!")
    exit()

# Анализируем первую таблицу
table = tables[0]
rows = table.find_all('tr')
print(f"📝 Строк в первой таблице: {len(rows)}")

print("\n" + "=" * 70)
print("📋 ПЕРВЫЕ 10 СТРОК ТАБЛИЦЫ (СЫРЫЕ ДАННЫЕ)")
print("=" * 70)

for i, row in enumerate(rows[:10]):
    cells = row.find_all('td')
    print(f"\n🔹 Строка {i+1}: {len(cells)} ячеек")

    for j, cell in enumerate(cells):
        text = cell.get_text(strip=True)
        # Показываем первые 100 символов
        if len(text) > 100:
            text = text[:100] + "..."
        print(f"   [{j}] {text}")

print("\n" + "=" * 70)
print("🥊 ПРИМЕРЫ БОЁВ (ПЕРВЫЕ 5)")
print("=" * 70)

fight_count = 0
for row in rows:
    cells = row.find_all('td')
    if len(cells) < 3:
        continue

    # Ищем ячейку с боем
    fight_text = None
    date_text = None

    for cell in cells:
        text = cell.get_text(strip=True)

        # Ищем дату
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
        if date_match:
            date_text = date_match.group(1)

        # Ищем бой (содержит дефис или vs)
        if re.search(r'[-–—]|vs\.|\(W\)|\(L\)', text, re.IGNORECASE):
            fight_text = text

    if fight_text and date_text:
        fight_count += 1
        print(f"\n🥊 Бой #{fight_count}:")
        print(f"   📅 Дата: {date_text}")
        print(f"   👥 Бой: {fight_text[:150]}")

        if fight_count >= 5:
            break

print("\n" + "=" * 70)
print("📊 ИТОГО")
print("=" * 70)
print(f"✅ Найдено боёв на странице: {fight_count}")
print("=" * 70)