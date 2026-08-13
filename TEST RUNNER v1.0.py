#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST RUNNER v3.3 | С ВВОДОМ ПАРОЛЯ И ПОЛНЫМ ЛОГИРОВАНИЕМ
================================================================
ИСПРАВЛЕНИЯ v3.3:
1. ✅ ЗАПРОС ПАРОЛЯ при запуске (как в test_deepseek_raw.py)
2. ✅ ИНИЦИАЛИЗАЦИЯ SecureNeuralChannel через пароль
3. ✅ ПЕРЕДАЧА пароля в ParserWorker
4. ✅ ПОЛНОЕ ЛОГИРОВАНИЕ каждого боя
5. ✅ ВСЕ 20 ТЕСТОВ
================================================================
"""
import os
import sys
import json
import time
import shutil
import random
import importlib.util
from datetime import datetime
from typing import List, Tuple, Dict, Optional

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================
TEST_SIZE = 50
ORIGINAL_FILE = "math_engine.py"
TEST_FILE = "math_engine_test.py"
BACKUP_FILE = f"{ORIGINAL_FILE}.backup"
LOG_FILE = f"test_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

# Глобальная переменная для пароля (заполняется при запуске)
MASTER_PASSWORD = None

TEST_PAIRS = [
    ("recent_wins_diff", "activity_diff"),
    ("fin_rate_diff", "sub_rate_diff"),
    ("td_def_diff", "grap_def_diff"),
    ("age_diff", "exp_diff"),
    ("rust_diff", "activity_diff"),
    ("wp_diff", "recent_wins_diff"),
    ("stress_diff", "motivation_diff"),
    ("biorythm_diff", "camp_diff"),
    ("mystic_diff", "mystic_v2_diff"),
    ("fin_x_td", "sub_x_grap"),
    ("rust_x_exp", "stress_x_camp"),
    ("wp_diff", "age_diff"),
    ("recent_wins_diff", "stress_diff"),
    ("motivation_diff", "camp_diff"),
    ("log_odds_ratio", "wp_diff"),
]

SINGLE_TESTS = [
    ("wp_diff",),
    ("recent_wins_diff",),
    ("age_diff",),
    ("mystic_diff",),
    ("mystic_v2_diff",),
]

# ============================================================================
# ЛОГГЕР
# ============================================================================
class TestLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.buffer = []
        self._init_log()

    def _init_log(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(f"{'='*80}\n")
            f.write(f"🧪 TEST RUNNER v3.3 | ЛОГ ТЕСТИРОВАНИЯ\n")
            f.write(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n\n")

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"
        self.buffer.append(log_line)
        print(log_line)
        if len(self.buffer) >= 10:
            self.flush()

    def log_battle(self, idx: int, fighter_a: str, fighter_b: str,
                   winner: str, prediction: str, correct: bool):
        status = "✅" if correct else "❌"
        self.log(f"  Бой {idx:2d}: {fighter_a[:25]} vs {fighter_b[:25]} | Реально: {winner} | Прогноз: {prediction} {status}")

    def log_test_result(self, test_name: str, accuracy: float, correct: int, total: int, failed: int):
        self.log(f"\n{'─'*60}")
        self.log(f"📊 ТЕСТ: {test_name}")
        self.log(f"   ✅ Верных: {correct}/{total} ({accuracy:.1f}%)")
        self.log(f"   ❌ Ошибок: {failed}")
        self.log(f"{'─'*60}\n")

    def flush(self):
        if self.buffer:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write("\n".join(self.buffer) + "\n")
            self.buffer = []

    def finalize(self):
        self.flush()
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n")


# ============================================================================
# ФУНКЦИИ ПРОВЕРКИ ИИ
# ============================================================================
def check_secure_neural_channel(logger: TestLogger) -> bool:
    """Проверяет и инициализирует SecureNeuralChannel"""
    global MASTER_PASSWORD

    try:
        from secure_neural_channel import SecureNeuralChannel

        # Проверяем, инициализирован ли уже
        if hasattr(SecureNeuralChannel, '_initialized') and SecureNeuralChannel._initialized:
            logger.log("✅ SecureNeuralChannel уже инициализирован")
            return True

        # Инициализируем с паролем
        logger.log("🔐 Инициализация SecureNeuralChannel с паролем...")
        if SecureNeuralChannel.init(MASTER_PASSWORD):
            logger.log("✅ SecureNeuralChannel инициализирован успешно")
            return True
        else:
            logger.log("❌ Ошибка инициализации SecureNeuralChannel", "ERROR")
            return False

    except Exception as e:
        logger.log(f"❌ Ошибка проверки SecureNeuralChannel: {e}", "ERROR")
        return False


def check_yandex_gpt(logger: TestLogger) -> bool:
    """Проверяет и инициализирует YandexGPT"""
    global MASTER_PASSWORD

    try:
        from parser_worker import ParserWorker

        logger.log("🤖 Инициализация YandexGPT с паролем...")
        worker = ParserWorker(master_password=MASTER_PASSWORD)

        if worker:
            logger.log("✅ YandexGPT готов к работе")
            return True
        else:
            logger.log("❌ Ошибка создания ParserWorker", "ERROR")
            return False

    except Exception as e:
        logger.log(f"❌ Ошибка проверки YandexGPT: {e}", "ERROR")
        return False


def check_all_ai(logger: TestLogger) -> bool:
    """Проверяет все ИИ перед запуском теста"""
    logger.log("\n" + "="*60)
    logger.log("🔍 ПРОВЕРКА ИНИЦИАЛИЗАЦИИ ИИ")
    logger.log("="*60)

    deepseek_ok = check_secure_neural_channel(logger)
    yandex_ok = check_yandex_gpt(logger)

    logger.log("="*60)
    if deepseek_ok and yandex_ok:
        logger.log("✅ ВСЕ ИИ ГОТОВЫ К РАБОТЕ")
    else:
        logger.log("❌ ЕСТЬ ПРОБЛЕМЫ С ИИ", "ERROR")
    logger.log("="*60 + "\n")

    return deepseek_ok and yandex_ok


# ============================================================================
# ФУНКЦИЯ СОЗДАНИЯ ТЕСТОВОГО ФАЙЛА
# ============================================================================
def create_test_math_engine(active_features: List[str], logger: TestLogger) -> bool:
    logger.log(f"📝 Создание math_engine_test.py с признаками: {', '.join(active_features)}")

    try:
        with open(ORIGINAL_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.log(f"❌ Ошибка чтения {ORIGINAL_FILE}: {e}", "ERROR")
        return False

    def process_block(block_start_marker: str, block_end_marker: str, active_features: List[str]) -> Tuple[str, bool]:
        start_pos = content.find(block_start_marker)
        if start_pos == -1:
            return "", False
        end_pos = content.find(block_end_marker, start_pos)
        if end_pos == -1:
            return "", False

        block = content[start_pos:end_pos + 1]
        lines = block.split("\n")
        new_lines = []

        for line in lines:
            if not line.strip() or "[" in line or "]" in line:
                new_lines.append(line)
                continue

            is_active = any(f in line for f in active_features)

            if is_active:
                cleaned = line
                if "#" in line:
                    cleaned = line.split("#", 1)[0].rstrip()
                    if cleaned.strip():
                        indent = " " * (len(line) - len(line.lstrip()))
                        new_lines.append(f"{indent}{cleaned.strip()}")
                    else:
                        continue
                else:
                    new_lines.append(line)
            else:
                if "#" in line:
                    new_lines.append(line)
                else:
                    indent = " " * (len(line) - len(line.lstrip()))
                    new_lines.append(f"{indent}# {line.strip()}")

        return "\n".join(new_lines), True

    new_base, ok_base = process_block("base = [", "]", active_features)
    if not ok_base:
        logger.log("❌ Ошибка обработки блока base", "ERROR")
        return False

    new_interactions, ok_interactions = process_block("interactions = [", "]", active_features)
    if not ok_interactions:
        logger.log("❌ Ошибка обработки блока interactions", "ERROR")
        return False

    base_start = content.find("base = [")
    base_end = content.find("]", base_start) + 1
    interactions_start = content.find("interactions = [")
    interactions_end = content.find("]", interactions_start) + 1

    new_content = content[:base_start] + new_base + content[base_end:interactions_start] + new_interactions + content[interactions_end:]
    new_content = new_content.replace("MATH ENGINE v51.0-MYSTIC_TEST", f"MATH ENGINE v51.0-TEST_{'_'.join(active_features)}")

    label = f"\n# 🧪 АКТИВНЫЕ ПРИЗНАКИ: {', '.join(active_features)}\n"
    new_content = new_content.replace("# -*- coding: utf-8 -*-", "# -*- coding: utf-8 -*-\n" + label)

    try:
        with open(TEST_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        logger.log("✅ Тестовый файл создан")
        return True
    except Exception as e:
        logger.log(f"❌ Ошибка сохранения {TEST_FILE}: {e}", "ERROR")
        return False


# ============================================================================
# ФУНКЦИЯ ЗАПУСКА ТЕСТА
# ============================================================================
def run_test_with_logging(test_name: str, active_features: List[str], logger: TestLogger) -> Dict:
    global MASTER_PASSWORD

    logger.log(f"\n{'█'*60}")
    logger.log(f"🧪 ЗАПУСК ТЕСТА: {test_name}")
    logger.log(f"📋 Активные признаки: {', '.join(active_features)}")
    logger.log(f"{'█'*60}")

    results = {
        "test_name": test_name,
        "features": active_features,
        "accuracy": 0.0,
        "correct": 0,
        "total": 0,
        "failed": 0,
        "battles": []
    }

    if not check_all_ai(logger):
        logger.log("❌ Пропуск теста из-за проблем с ИИ", "ERROR")
        return results

    if not create_test_math_engine(active_features, logger):
        return results

    try:
        spec = importlib.util.spec_from_file_location("math_engine_test", TEST_FILE)
        test_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(test_module)

        MMAEngine = test_module.MMAEngine
        FightData = test_module.FightData
        Result = test_module.Result
        FinishType = test_module.FinishType
        VerificationStatus = test_module.VerificationStatus
    except Exception as e:
        logger.log(f"❌ Ошибка импорта: {e}", "ERROR")
        return results

    try:
        from direct_test_101 import load_fight_pairs, enrich_fighters_via_yandex
        from deep_ai_analyst import DeepAIAnalyst

        engine = MMAEngine()
        logger.log(f"📊 Начальная точность: {engine.best_accuracy:.1f}%")

        all_pairs = load_fight_pairs()
        if len(all_pairs) < TEST_SIZE:
            logger.log(f"⚠️ Недостаточно пар ({len(all_pairs)} < {TEST_SIZE})", "WARNING")
            return results

        test_pairs = random.sample(all_pairs, TEST_SIZE)
        logger.log(f"📊 Загружено {len(test_pairs)} случайных боев")

        correct = 0
        total = 0
        failed = 0
        battle_log = []

        for idx, pair in enumerate(test_pairs, 1):
            fighter_a = pair.get("fighter_a", "")
            fighter_b = pair.get("fighter_b", "")
            fight_date = pair.get("date", "")
            winner = pair.get("winner", "")

            try:
                logger.log(f"  Бой {idx:2d}/{TEST_SIZE}: {fighter_a} vs {fighter_b} ({fight_date})", "DEBUG")

                # 🔥 ПОЛУЧАЕМ СВЕЖИЕ ДАННЫЕ ОТ DEEPSEEK
                fa_stats = DeepAIAnalyst.get_fighter_deep_stats(fighter_a, fight_date)
                fb_stats = DeepAIAnalyst.get_fighter_deep_stats(fighter_b, fight_date)

                # 🔥 ОБОГАЩЕНИЕ ЧЕРЕЗ YANDEXGPT (передаём пароль)
                enrichment_a, enrichment_b = enrich_fighters_via_yandex(
                    fighter_a, fighter_b, fight_date, MASTER_PASSWORD,
                    fighter_a_stats={}, fighter_b_stats={}
                )

                # Применяем обогащение
                if enrichment_a:
                    fa_stats.stress_factor = enrichment_a.get('stress_factor', fa_stats.stress_factor)
                    fa_stats.motivation_index = enrichment_a.get('motivation_index', fa_stats.motivation_index)
                    fa_stats.biorythm_score = enrichment_a.get('biorythm_score', fa_stats.biorythm_score)
                    fa_stats.camp_quality = enrichment_a.get('camp_quality', fa_stats.camp_quality)
                    fa_stats.mystic_factor = enrichment_a.get('mystic_factor', fa_stats.mystic_factor)
                    fa_stats.mystic_v2 = enrichment_a.get('mystic_v2', getattr(fa_stats, 'mystic_v2', 0.5))

                if enrichment_b:
                    fb_stats.stress_factor = enrichment_b.get('stress_factor', fb_stats.stress_factor)
                    fb_stats.motivation_index = enrichment_b.get('motivation_index', fb_stats.motivation_index)
                    fb_stats.biorythm_score = enrichment_b.get('biorythm_score', fb_stats.biorythm_score)
                    fb_stats.camp_quality = enrichment_b.get('camp_quality', fb_stats.camp_quality)
                    fb_stats.mystic_factor = enrichment_b.get('mystic_factor', fb_stats.mystic_factor)
                    fb_stats.mystic_v2 = enrichment_b.get('mystic_v2', getattr(fb_stats, 'mystic_v2', 0.5))

                fd = FightData(
                    a=fa_stats, b=fb_stats,
                    date=datetime.strptime(fight_date, "%Y-%m-%d"),
                    wc="Auto", rounds=3, location="UFC",
                    odds_a=1.85, matchup_odds={"bookmaker": "Нейтрально", "odds_a": 1.85, "odds_b": 1.85}
                )

                prediction = engine.predict(fd)
                result = Result(winner=winner, rnd=3, method=FinishType.DECISION_UNANIMOUS, verification=VerificationStatus.VERIFIED_DUAL)
                engine.train_on_new_fight(fd, result, fighter_a, fighter_b)

                is_correct = prediction.winner == winner
                if is_correct:
                    correct += 1
                total += 1

                logger.log_battle(idx, fighter_a, fighter_b, winner, prediction.winner, is_correct)
                battle_log.append({
                    "fighter_a": fighter_a,
                    "fighter_b": fighter_b,
                    "winner": winner,
                    "predicted": prediction.winner,
                    "correct": is_correct
                })

            except Exception as e:
                failed += 1
                logger.log(f"  ❌ Ошибка в бое {idx}: {str(e)[:80]}", "ERROR")
                continue

        final_accuracy = engine.best_accuracy if engine.best_accuracy > 0 else (correct / total if total > 0 else 0)

        results["accuracy"] = final_accuracy * 100
        results["correct"] = correct
        results["total"] = total
        results["failed"] = failed
        results["battles"] = battle_log

        logger.log_test_result(test_name, results["accuracy"], correct, total, failed)

    except Exception as e:
        logger.log(f"❌ Критическая ошибка: {e}", "ERROR")
        import traceback
        logger.log(traceback.format_exc(), "ERROR")

    return results


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================
def main():
    global MASTER_PASSWORD

    logger = TestLogger(LOG_FILE)
    logger.log("=" * 70)
    logger.log("🧪 TEST RUNNER v3.3 | С ВВОДОМ ПАРОЛЯ")
    logger.log("=" * 70)

    # 🔥 ЗАПРОС ПАРОЛЯ (как в test_deepseek_raw.py)
    print("🔐 Мастер-пароль: ", end="", flush=True)
    MASTER_PASSWORD = input().strip()

    if not MASTER_PASSWORD:
        logger.log("❌ Пароль не введён", "ERROR")
        return

    # 🔥 ИНИЦИАЛИЗАЦИЯ SECURENEURALCHANNEL
    try:
        from secure_neural_channel import SecureNeuralChannel
        if not SecureNeuralChannel.init(MASTER_PASSWORD):
            logger.log("❌ Неверный пароль", "ERROR")
            return
        logger.log("✅ SecureNeuralChannel инициализирован")
    except Exception as e:
        logger.log(f"❌ Ошибка инициализации: {e}", "ERROR")
        return

    # 🔥 ПРОВЕРЯЕМ ВСЕ ИИ
    if not check_all_ai(logger):
        logger.log("❌ НЕВОЗМОЖНО ПРОДОЛЖИТЬ: проблемы с ИИ", "ERROR")
        return

    # Собираем тесты
    all_tests = []
    for pair in TEST_PAIRS:
        all_tests.append({
            "name": f"{pair[0]}_{pair[1]}",
            "features": list(pair)
        })
    for single in SINGLE_TESTS:
        all_tests.append({
            "name": single[0],
            "features": list(single)
        })

    logger.log(f"📋 Всего тестов: {len(all_tests)}")
    logger.log(f"📊 Боев на тест: {TEST_SIZE}")
    logger.log("=" * 70)

    if not os.path.exists(ORIGINAL_FILE):
        logger.log(f"❌ Файл {ORIGINAL_FILE} не найден!", "ERROR")
        return

    try:
        shutil.copy2(ORIGINAL_FILE, BACKUP_FILE)
        logger.log(f"✅ Бэкап создан: {BACKUP_FILE}")
    except Exception as e:
        logger.log(f"⚠️ Ошибка создания бэкапа: {e}")

    results = []
    total_tests = len(all_tests)

    for idx, test in enumerate(all_tests, 1):
        test_name = test["name"]
        features = test["features"]

        logger.log(f"\n{'='*70}")
        logger.log(f"[{idx}/{total_tests}] 🧪 Тест: {test_name}")
        logger.log(f"{'='*70}")

        result = run_test_with_logging(test_name, features, logger)
        results.append(result)

        time.sleep(2)

    if os.path.exists(TEST_FILE):
        try:
            os.remove(TEST_FILE)
        except:
            pass

    logger.log("\n" + "=" * 70)
    logger.log("📊 ИТОГОВАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
    logger.log("=" * 70)
    logger.log(f"{'Тест':<35} {'Точность':>15} {'Верных':>10} {'Всего':>8}")
    logger.log("-" * 70)

    sorted_results = sorted(results, key=lambda x: x["accuracy"], reverse=True)

    for r in sorted_results:
        if r["accuracy"] > 0:
            logger.log(f"{r['test_name']:<35} {r['accuracy']:>14.1f}% {r['correct']:>10} {r['total']:>8}")
        else:
            logger.log(f"{r['test_name']:<35} {'N/A':>15} {r['correct']:>10} {r['total']:>8}")

    logger.log("=" * 70)

    top5 = sorted_results[:5]
    logger.log("\n🏆 ТОП-5 ЛУЧШИХ ТЕСТОВ:")
    for i, r in enumerate(top5, 1):
        if r["accuracy"] > 0:
            logger.log(f"   {i}. {r['test_name']} → {r['accuracy']:.1f}% (признаки: {', '.join(r['features'])}")

    logger.log("=" * 70)

    mystic_tests = [r for r in results if "mystic" in r["test_name"].lower()]
    if mystic_tests:
        logger.log("\n🔮 МИСТИКА В ТЕСТАХ:")
        for r in mystic_tests:
            if r["accuracy"] > 0:
                logger.log(f"   {r['test_name']}: {r['accuracy']:.1f}%")

    logger.log("=" * 70)

    report_file = f"dataset/pair_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        os.makedirs("dataset", exist_ok=True)
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "test_size": TEST_SIZE,
                "total_tests": len(results),
                "results": sorted_results
            }, f, indent=2, ensure_ascii=False)
        logger.log(f"\n📄 Результаты сохранены: {report_file}")
    except Exception as e:
        logger.log(f"⚠️ Ошибка сохранения результатов: {e}")

    logger.finalize()
    logger.log(f"\n✅ ПОЛНЫЙ ЛОГ СОХРАНЕН: {LOG_FILE}")

if __name__ == "__main__":
    main()