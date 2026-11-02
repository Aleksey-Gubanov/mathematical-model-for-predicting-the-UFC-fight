import json
import os
from math_engine import MMAEngine

def load_weights(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('weights', []), data.get('feature_names', [])

engine = MMAEngine()
current_weights = engine.model.weights
feature_names = engine.model.feature_names

print("=" * 70)
print("📊 АНАЛИЗ ИЗМЕНЕНИЯ ВЕСОВ ПОСЛЕ ОБУЧЕНИЯ НА 150 БОЯХ")
print("=" * 70)

old_weights = None
try:
    with open('weights_best.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    old_weights = data.get('weights', [])
    print("✅ Старые веса загружены из weights_best.json")
except Exception as e:
    print(f"❌ Не удалось загрузить weights_best.json: {e}")
    old_weights = current_weights

if old_weights and len(old_weights) == len(current_weights):
    changes = []
    for i, (old, new) in enumerate(zip(old_weights, current_weights)):
        diff = new - old
        # ✅ ПОНИЖЕННЫЙ ПОРОГ: 0.000001 вместо 0.0001
        if abs(diff) > 0.000001:
            name = feature_names[i] if i < len(feature_names) else f"feature_{i}"
            changes.append((name, old, new, diff, abs(diff)))

    changes.sort(key=lambda x: x[4], reverse=True)

    print(f"\n📈 Топ-20 изменений весов:")
    print("-" * 70)
    print(f"{'Признак':<30} {'Старый':>10} {'Новый':>10} {'Изменение':>12}")
    print("-" * 70)
    for name, old, new, diff, _ in changes[:20]:
        print(f"{name:<30} {old:>10.6f} {new:>10.6f} {diff:>+12.6f}")

    print(f"\n📊 Статистика изменений:")
    print(f"   Всего признаков: {len(current_weights)}")
    print(f"   Изменено: {len(changes)}")
    if changes:  # ✅ ИСПРАВЛЕНИЕ: проверка на пустой список
        print(f"   Среднее изменение: {sum(c[4] for c in changes) / len(changes):.6f}")
        print(f"   Максимальное изменение: {changes[0][4]:.6f} ({changes[0][0]})")
    else:
        print("   Среднее изменение: 0 (весовые изменения не обнаружены)")
        print("   Максимальное изменение: 0")
else:
    print("❌ Не удалось сравнить веса (разная длина или отсутствуют старые)")

print("=" * 70)