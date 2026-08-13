#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEEP AI ANALYST v5.7 | ДОБАВЛЕНА ПЕРЕДАЧА FORM
================================================================
ИЗМЕНЕНИЯ v5.7:
1. ✅ Добавлено поле "form" в required_keys
2. ✅ Добавлена структура "form" в JSON
3. ✅ DeepSeek теперь возвращает форму бойца (последние 5 боёв)
4. ✅ Все улучшения v5.6 сохранены
================================================================
"""
import sys
import os
import re
import json
import time
import random
from datetime import datetime
from typing import Dict, List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from secure_neural_channel import SecureNeuralChannel
except ImportError:
    print("❌ secure_neural_channel.py не найден!")
    sys.exit(1)


def safe_int(val, default=3):
    try:
        return int(float(str(val).strip()))
    except:
        return default


def safe_float(val, default=1.85):
    try:
        return float(str(val).strip())
    except:
        return default


class DeepAIAnalyst:
    @staticmethod
    def enrich_fighter(fighter_name: str, fight_date: str,
                       opponent_name: str = None,
                       opponent_record: str = None,
                       fight_context: str = "regular",
                       recent_form: List[str] = None,
                       weight_class: str = None,
                       fighter_stats: Dict = None) -> Dict:
        """
        ✅ v5.7: Жёсткий промпт + проверка шаблонов + возврат form
        """
        context_parts = []
        if opponent_name:
            context_parts.append(f"Соперник: {opponent_name} (рекорд: {opponent_record or 'неизвестен'})")
        if fight_context and fight_context != "regular":
            context_parts.append(f"Контекст: {fight_context.upper()}")
        if recent_form:
            context_parts.append(f"Форма (последние 5): {', '.join(recent_form)}")
        if weight_class:
            context_parts.append(f"Весовая категория: {weight_class}")
        context_str = " | ".join(context_parts) if context_parts else "Стандартный бой"

        prompt = f"""Ты элитный аналитик ММА с доступом к базе данных бойцов.

ЗАДАНИЕ: Дай РЕАЛЬНЫЕ статистические данные о бойце {fighter_name} на дату {fight_date}.

КОНТЕКСТ: {context_str}

⚠️ КРИТИЧЕСКИ ВАЖНО:
1. НЕ ИСПОЛЬЗУЙ ШАБЛОНЫ! Каждый боец уникален.
2. Рекорд (wins/losses) должен быть РЕАЛЬНЫМ на указанную дату.
3. Не используй "22-5" для всех — это нереально.
4. reach_cm — РЕАЛЬНЫЙ размах рук (зависит от весовой категории).
5. stress_factor — ИНДИВИДУАЛЕН (зависит от опыта, веса, статуса боя).

📊 ТРЕБОВАНИЯ К ДАННЫМ:

1. РЕКОРД (wins, losses):
   - Используй известные рекорды из памяти.
   - Примеры: Jon Jones (27-1), Khabib (29-0), Conor (22-6)
   - НЕ используй 22-5 для всех!

2. ФИЗИЧЕСКИЕ ДАННЫЕ (reach_cm, height_cm):
   - Зависят от весовой категории:
     * Легчайший вес (135): reach 165-175
     * Полусредний вес (170): reach 175-190
     * Средний вес (185): reach 180-195
     * Полутяжёлый вес (205): reach 185-200
     * Тяжёлый вес (265): reach 190-210
   - НЕ используй 185 для всех!

3. ПСИХОЛОГИЧЕСКИЕ ФАКТОРЫ:
   - stress_factor: 0.20-0.85 (зависит от давления, опыта)
   - motivation_index: 0.30-0.95 (зависит от статуса боя)
   - camp_quality: 0.30-0.95 (зависит от лагеря)

4. ЛАГЕРЬ (camp_name):
   - Используй РЕАЛЬНЫЕ залы: "American Top Team", "Jackson Wink MMA",
     "Team Alpha Male", "SBG Ireland", "AKA", "Kill Cliff FC"
   - НЕ используй "профессиональный клуб" или "неизвестно"

5. ✅ v5.7: ФОРМА (form):
   - Верни массив из 5 результатов последних боёв.
   - Формат: ["W", "W", "L", "W", "W"] где W = победа, L = поражение.
   - Если боец недавно дебютировал, верни ["W", "W", "W", "W", "W"].
   - Это КРИТИЧЕСКИ ВАЖНО для анализа формы!

Верни ТОЛЬКО валидный JSON (без markdown-обёрток) со следующей структурой.
ВСЕ поля обязательны:

{{
  "age": число (реальный возраст),
  "wins": число (реальный рекорд побед),
  "losses": число (реальный рекорд поражений),
  "recent_wins": число (побед в последних 5 боях),
  "fin_rate": число (0.0-1.0, процент финишей),
  "sub_rate": число (0.0-1.0, процент сабмишенов),
  "td_def": число (0.0-1.0, защита от тейкдаунов),
  "grap_def": число (0.0-1.0, защита в партере),
  "months_off": число (месяцев без боёв),
  "fights_12m": число (боёв за последние 12 месяцев),
  "reach_cm": число (реальный размах рук в см),
  "height_cm": число (реальный рост в см),
  "camp_name": "реальное название лагеря",
  "stress_factor": число (0.20-0.85),
  "motivation_index": число (0.30-0.95),
  "biorythm_score": число (0.35-0.95),
  "camp_quality": число (0.30-0.95),
  "mystic_v2": число (0.30-0.90),
  "form": ["W", "W", "L", "W", "W"]
}}"""

        required_keys = [
            "age", "wins", "losses", "recent_wins", "fin_rate", "sub_rate",
            "td_def", "grap_def", "months_off", "fights_12m", "reach_cm",
            "height_cm", "camp_name", "stress_factor", "motivation_index",
            "biorythm_score", "camp_quality", "mystic_v2",
            "form"  # ✅ v5.7: ДОБАВЛЕН
        ]

        try:
            res = DeepAIAnalyst._robust_query(
                prompt,
                "Верни СТРОГО JSON без markdown-обёрток. Используй РЕАЛЬНЫЕ данные!",
                required_keys,
                max_retries=3,
                use_cache=True
            )

            wins = safe_int(res.get('wins'), 0)
            losses = safe_int(res.get('losses'), 0)
            reach = safe_int(res.get('reach_cm'), 0)
            stress = safe_float(res.get('stress_factor'), 0.0)

            is_template = (wins == 22 and losses == 5 and reach == 185 and abs(stress - 0.45) < 0.01)

            if is_template:
                print(f"      ⚠️ ОБНАРУЖЕН ШАБЛОН для {fighter_name}! Повторный запрос без кэша...")
                res = DeepAIAnalyst._robust_query(
                    prompt + "\n\n⚠️ ПРЕДЫДУЩИЙ ОТВЕТ БЫЛ ШАБЛОНОМ (22-5). ВЕРНИ РЕАЛЬНЫЕ ДАННЫЕ!",
                    "КРИТИЧЕСКИ ВАЖНО: Верни РЕАЛЬНЫЕ данные, а не шаблон 22-5!",
                    required_keys,
                    max_retries=3,
                    use_cache=False
                )

                wins2 = safe_int(res.get('wins'), 0)
                losses2 = safe_int(res.get('losses'), 0)

                if wins2 == 22 and losses2 == 5:
                    print(f"      ⚠️ Второй запрос снова вернул шаблон! Используем фолбэк с вариацией.")
                    return DeepAIAnalyst._generate_fallback(fighter_name)

            result = {}

            result['age'] = safe_int(res.get('age'), 30)
            result['wins'] = safe_int(res.get('wins'), 0)
            result['losses'] = safe_int(res.get('losses'), 0)
            result['recent_wins'] = safe_int(res.get('recent_wins'), 0)
            result['months_off'] = safe_int(res.get('months_off'), 0)
            result['fights_12m'] = safe_int(res.get('fights_12m'), 0)

            result['fin_rate'] = max(0.0, min(1.0, safe_float(res.get('fin_rate'), 0.5)))
            result['sub_rate'] = max(0.0, min(1.0, safe_float(res.get('sub_rate'), 0.0)))
            result['td_def'] = max(0.0, min(1.0, safe_float(res.get('td_def'), 0.5)))
            result['grap_def'] = max(0.0, min(1.0, safe_float(res.get('grap_def'), 0.5)))

            reach_val = safe_int(res.get('reach_cm'), 180)
            result['reach_cm'] = max(150, min(225, reach_val))
            height_val = safe_int(res.get('height_cm'), 175)
            result['height_cm'] = max(150, min(210, height_val))

            result['stress_factor'] = max(0.20, min(0.85, safe_float(res.get('stress_factor'), 0.45)))
            result['motivation_index'] = max(0.30, min(0.95, safe_float(res.get('motivation_index'), 0.65)))
            result['biorythm_score'] = max(0.35, min(0.95, safe_float(res.get('biorythm_score'), 0.65)))
            result['camp_quality'] = max(0.30, min(0.95, safe_float(res.get('camp_quality'), 0.70)))
            result['mystic_v2'] = max(0.30, min(0.90, safe_float(res.get('mystic_v2'), 0.62)))

            # ✅ v5.7: ОБРАБОТКА FORM
            form_data = res.get('form', [])
            if isinstance(form_data, list) and len(form_data) > 0:
                # Проверяем, что все элементы - валидные W/L
                valid_form = []
                for f in form_data[:5]:
                    if str(f).upper() in ['W', 'L']:
                        valid_form.append(str(f).upper())
                    else:
                        # Если пришло что-то другое, конвертируем
                        valid_form.append('W' if safe_int(f, 0) > 0 else 'L')
                result['form'] = valid_form if valid_form else ['W', 'W', 'W', 'W', 'W']
            else:
                # Если form не пришёл, используем переданный recent_form или генерируем
                if recent_form:
                    result['form'] = recent_form[:5]
                else:
                    # Генерируем на основе recent_wins
                    rw = result.get('recent_wins', 3)
                    result['form'] = ['W'] * min(rw, 5) + ['L'] * max(0, 5 - min(rw, 5))

            banned_camps = [
                'профессиональный клуб', 'неизвестно', 'не указано', 'unknown',
                'none', 'null', '', 'неизвестен', 'профессиональный', 'клуб',
                'неизвестна', 'неизвестный', 'no data', 'n/a', 'na'
            ]
            camp_name = str(res.get('camp_name', '')).strip()
            if camp_name.lower() in banned_camps or len(camp_name) < 3:
                result['camp_name'] = 'Independent'
            else:
                result['camp_name'] = camp_name

            age_val = result['age']
            if age_val >= 38:
                result['motivation_index'] = min(result['motivation_index'], 0.75)
                result['biorythm_score'] = min(result['biorythm_score'], 0.70)
            elif age_val >= 35:
                result['motivation_index'] = min(result['motivation_index'], 0.85)
                result['biorythm_score'] = min(result['biorythm_score'], 0.80)
            elif age_val <= 25:
                result['biorythm_score'] = max(result['biorythm_score'], 0.70)

            if fight_context and fight_context.lower() in ['title', 'чемпионский', 'титульный']:
                result['motivation_index'] = max(result['motivation_index'], 0.80)

            print(f"      ✅ {fighter_name}: {result['wins']}-{result['losses']}, "
                  f"reach={result['reach_cm']}, stress={result['stress_factor']:.2f}, "
                  f"mystic_v2={result['mystic_v2']:.2f}, camp={result['camp_name']}, "
                  f"form={result['form']}")

            return result

        except Exception as e:
            print(f"❌ Ошибка enrich_fighter для {fighter_name}: {e}")
            return DeepAIAnalyst._generate_fallback(fighter_name)

    @staticmethod
    def _generate_fallback(fighter_name: str) -> Dict:
        name_hash = sum(ord(c) for c in fighter_name) % 10
        wins_base = 12 + (name_hash % 10)
        losses_base = 3 + (name_hash % 5)
        rw = 2 + (name_hash % 3)

        return {
            'age': 28 + (name_hash % 8),
            'wins': wins_base,
            'losses': losses_base,
            'recent_wins': rw,
            'fin_rate': round(0.30 + (name_hash % 5) * 0.08, 2),
            'sub_rate': round(0.00 + (name_hash % 3) * 0.08, 2),
            'td_def': round(0.40 + (name_hash % 5) * 0.06, 2),
            'grap_def': round(0.40 + (name_hash % 5) * 0.06, 2),
            'months_off': name_hash % 5,
            'fights_12m': 1 + (name_hash % 3),
            'reach_cm': 170 + (name_hash % 20),
            'height_cm': 170 + (name_hash % 15),
            'camp_name': random.choice([
                "American Top Team", "Jackson Wink MMA", "Team Alpha Male",
                "SBG Ireland", "AKA", "Kill Cliff FC", "Fortis MMA",
                "Elevation Fight Team", "MMA Lab", "Xtreme Couture"
            ]),
            'stress_factor': round(0.30 + (name_hash % 4) * 0.07, 2),
            'motivation_index': round(0.50 + (name_hash % 4) * 0.08, 2),
            'biorythm_score': round(0.50 + (name_hash % 4) * 0.07, 2),
            'camp_quality': round(0.50 + (name_hash % 4) * 0.08, 2),
            'mystic_v2': round(0.50 + (name_hash % 4) * 0.07, 2),
            'form': ['W'] * min(rw, 5) + ['L'] * max(0, 5 - min(rw, 5))
        }

    @staticmethod
    def _robust_query(prompt: str, system_prompt: str, required_keys: List[str],
                      max_retries: int = 5, use_cache: bool = True) -> Dict:
        current_prompt = prompt
        wait_time = 3

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"      ⏳ Повторная попытка {attempt}/{max_retries} через {wait_time} сек...")
                    time.sleep(wait_time)
                    wait_time *= 2

                response = SecureNeuralChannel.query(
                    current_prompt,
                    system_prompt,
                    use_cache=use_cache
                )

            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "Service Unavailable" in error_msg:
                    print(f"      ⚠️ Сервис временно недоступен (503), попытка {attempt}/{max_retries}")
                    continue
                else:
                    print(f"      ❌ Ошибка запроса: {e}")
                    continue

            if isinstance(response, dict) and all(k in response for k in required_keys):
                return response

            if isinstance(response, str):
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group())
                        if all(k in parsed for k in required_keys):
                            return parsed
                    except:
                        pass

            missing = [k for k in required_keys if k not in (response or {})]
            current_prompt += f"\n\n⚠️ ОШИБКА ПОПЫТКИ {attempt}: Не хватает ключей: {missing}."

        print(f"⚠️ Не удалось получить JSON после {max_retries} попыток. Возвращаю дефолты.")
        return {k: None for k in required_keys}


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТ DeepAIAnalyst v5.7")
    print("=" * 70)

    try:
        snc = SecureNeuralChannel()
        print("✅ SecureNeuralChannel инициализирован")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

    print("\n✅ DeepAIAnalyst v5.7 готов к работе!")
    print("=" * 70)