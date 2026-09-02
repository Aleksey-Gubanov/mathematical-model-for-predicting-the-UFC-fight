#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MATH ENGINE v55.7 | 46 ПРИЗНАКОВ + АДАПТИВНЫЙ CLIPPING + УПРОЩЁННАЯ ЛОГИКА
================================================================
ИЗМЕНЕНИЯ v55.7:
1. ✅ Адаптивный clipping весов на основе feature_stds (raw std до z-score)
2. ✅ Упрощена логика обновления весов (единый step_ratio = 0.5)
3. ✅ Добавлен вызов recalibrate_scaler() после пакетного обучения
4. ✅ Сброс _recalibrated_this_cycle в начале process_batch()
5. ✅ Добавлен специфический лимит для b_losses (индекс 27) = 0.100
6. ✅ Порядок операций: обновление весов → адаптивный clipping → лимиты
7. ✅ Сохранены все специфические лимиты как дополнительная защита
8. ✅ Глобальная константа ADAPTIVE_C = 0.5
================================================================
"""
import math
import os
import json
import re
import random
import glob
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, fields
from enum import Enum

DATASET_DIR = "dataset"
MAX_DATASET_SIZE_BYTES = 10 * 1024 * 1024
VALID_ROUNDS = [3, 5]
TARGET_FEATURES = 46

# ============================================================================
# ✅ v55.7: ГЛОБАЛЬНАЯ КОНСТАНТА ДЛЯ АДАПТИВНОГО CLIPPING
# ============================================================================
ADAPTIVE_C = 0.5  # подбирается эмпирически, обеспечивает баланс

# ============================================================================
# ✅ v55.3-v55.7: ГЛОБАЛЬНЫЕ ОГРАНИЧЕНИЯ ДЛЯ СТАБИЛИЗАЦИИ ВЕСОВ
# ============================================================================
B_RECENT_WINS_INDEX = 17
B_RECENT_WINS_MAX_ABS = 0.040
B_RECENT_WINS_STEP_RATIO = 0.25   # оставлено для совместимости

B_MYSTIC_FACTOR_INDEX = 32
B_MYSTIC_FACTOR_MAX_ABS = 0.030
B_MYSTIC_FACTOR_STEP_RATIO = 0.20

A_LOSSES_INDEX = 10
A_LOSSES_MAX_ABS = 0.060
A_LOSSES_STEP_RATIO = 0.30

B_MONTHS_OFF_INDEX = 25
B_MONTHS_OFF_MAX_ABS = 0.060 # было 0,040
B_MONTHS_OFF_STEP_RATIO = 0.30

# ✅ v55.7: НОВОЕ — специфический лимит для b_losses (индекс 27)
B_LOSSES_INDEX = 27
B_LOSSES_MAX_ABS = 0.100

POSITIVE_ONLY_INDICES = [3, 4, 15, 20, 21]
POSITIVE_MIN_WEIGHT = 0.001

PROTECTED_USEFUL_INDICES = [3, 4, 7, 20, 21]
PROTECTED_STEP_RATIO = 0.30   # оставлено для совместимости

USEFUL_MIN_WEIGHTS = {
    3: 0.002,   # a_td_def
    4: 0.002,   # a_grap_def
    7: 0.004,   # a_fights_12m
    20: 0.002,  # b_td_def
    21: 0.002,  # b_grap_def
}

# ✅ v55.6: Индексы wins/losses для коррекции масштаба при загрузке
WINS_LOSSES_INDICES = [9, 10, 26, 27]


class ModelConstants:
    LEARNING_RATE = 0.005
    EPOCHS = 100
    L1_RATIO = 0.01
    ALPHA = 0.1
    ROLLBACK_THRESHOLD_BEST = 0.05
    ROLLBACK_THRESHOLD_BASELINE = 0.07
    DAMPENING_FACTOR = 0.85
    MYSTIC_WEIGHT = 0.05
    BATCH_SIZE = 50
    DROPOUT_RATE = 0.2
    STEP_RATIO = 0.70      # оставлено для совместимости
    TEMPORAL_WEIGHT_NEW = 1.2
    TEMPORAL_WEIGHT_OLD = 1.0
    WP_DAMPENING = 0.60
    BATCH_TRAIN_SIZE = 200


class Mode(Enum):
    PROGNOZ = "ПРОГНОЗ"
    OBUCHENIE = "ОБУЧЕНИЕ"


class FinishType(Enum):
    DECISION_UNANIMOUS = "Решение (единогласное)"
    DECISION_SPLIT = "Решение (раздельное)"
    DRAW = "Ничья"
    TKO = "ТКО (удары)"
    KO = "КО (удары)"
    SUBMISSION = "Сабмишен"


class VerificationStatus(Enum):
    VERIFIED_DUAL = "verified_dual"


@dataclass
class Fighter:
    name: str
    dob: str = None
    flag: str = "🏳️"
    wins: int = 0
    losses: int = 0
    recent_wins: int = 0
    form: List[str] = field(default_factory=list)
    fin_rate: float = 0.5
    sub_rate: float = 0.0
    td_def: float = 0.5
    grap_def: float = 0.5
    age: int = 30
    exp: int = 0
    months_off: int = 0
    fights_12m: int = 0
    reach_cm: int = 180
    height_cm: int = 175
    stress_factor: float = 0.5
    motivation_index: float = 0.5
    biorythm_score: float = 0.5
    camp_quality: float = 0.5
    camp_name: str = "Independent"
    mystic_factor: float = 0.5
    mystic_v2: float = 0.5
    verif: VerificationStatus = VerificationStatus.VERIFIED_DUAL


@dataclass
class FightData:
    a: Fighter
    b: Fighter
    date: datetime
    wc: str
    rounds: int
    location: str = "Не указано"
    odds_a: float = 1.85
    matchup_odds: dict = None

    def __post_init__(self):
        if self.rounds not in VALID_ROUNDS:
            self.rounds = 3


@dataclass
class Prediction:
    winner: str
    prob: float
    ci_lo: float
    ci_hi: float
    rnd: int
    method: FinishType
    odds: float


@dataclass
class Result:
    winner: str
    rnd: int
    method: FinishType
    verification: VerificationStatus = VerificationStatus.VERIFIED_DUAL


def normalize_name(name: str) -> str:
    return re.sub(r'[^a-zа-я0-9]', '', str(name).lower().replace('ё', 'е').replace('й', 'и'))


def names_match(name1: str, name2: str) -> bool:
    n1, n2 = normalize_name(name1), normalize_name(name2)
    return n1 == n2 or n1 in n2 or n2 in n1


def _names_match_by_id(name1: str, name2: str) -> bool:
    try:
        from fighters_ids_manager import names_match_by_id
        return names_match_by_id(name1, name2)
    except ImportError:
        return names_match(name1, name2)


def make_fighter_from_dict(data: dict, name: str) -> Fighter:
    allowed_keys = {f.name for f in fields(Fighter)}
    filtered = {k: v for k, v in data.items() if k in allowed_keys}

    if "verif" not in filtered:
        filtered["verif"] = VerificationStatus.VERIFIED_DUAL

    percent_fields = ["fin_rate", "sub_rate", "td_def", "grap_def"]
    for field_name in percent_fields:
        if field_name in filtered and filtered[field_name] is not None:
            try:
                val = float(filtered[field_name])
                if val > 1.0:
                    filtered[field_name] = val / 100.0
            except (ValueError, TypeError):
                filtered[field_name] = 0.5

    for new_field in [
        "stress_factor",
        "motivation_index",
        "biorythm_score",
        "camp_quality",
        "mystic_factor",
        "mystic_v2",
        "camp_name"
    ]:
        if new_field not in filtered or filtered[new_field] is None:
            if new_field == "camp_name":
                filtered[new_field] = "Independent"
            else:
                filtered[new_field] = 0.5

    numeric_fields = ["wins", "losses", "recent_wins", "age", "exp", "months_off", "fights_12m"]
    for field_name in numeric_fields:
        if field_name in filtered and filtered[field_name] is not None:
            try:
                filtered[field_name] = int(filtered[field_name])
            except (ValueError, TypeError):
                filtered[field_name] = 0

    filtered["name"] = name
    return Fighter(**filtered)


def safe_val(val, default=0.0):
    if val is None or val != val or val == float('inf') or val == float('-inf'):
        return default
    return float(val)


class FeaturePairConstraints:
    PAIR_BOUNDS: Dict[Tuple[int, int], Tuple[float, float]] = {
        (0, 7): (-0.50, 0.50),
        (1, 2): (-0.50, 0.50),
        (3, 4): (-0.40, 0.40),
        (5, 6): (-0.30, 0.30),
        (11, 12): (-0.35, 0.35),
        (13, 14): (-0.25, 0.25),
        (15, 16): (-0.20, 0.20),
        (17, 24): (-0.50, 0.50),
        (18, 19): (-0.50, 0.50),
        (20, 21): (-0.40, 0.40),
        (22, 23): (-0.30, 0.30),
        (28, 29): (-0.35, 0.35),
        (30, 31): (-0.25, 0.25),
        (32, 33): (-0.20, 0.20),
        (34, 35): (-0.30, 0.30),
        (36, 37): (-0.30, 0.30),
        (38, 39): (-0.20, 0.20),
        (40, 41): (-0.20, 0.20),
        (42, 43): (-0.15, 0.15),
        (44, 45): (-0.10, 0.10),
    }

    PAIR_NAMES = {
        (0, 7): "a_recent_wins+activity",
        (1, 2): "a_fin_rate+sub_rate",
        (3, 4): "a_td_def+grap_def",
        (5, 6): "a_age+exp",
        (11, 12): "a_stress+motivation",
        (13, 14): "a_biorythm+camp",
        (15, 16): "a_mystic+mystic_v2",
        (17, 24): "b_recent_wins+activity",
        (18, 19): "b_fin_rate+sub_rate",
        (20, 21): "b_td_def+grap_def",
        (22, 23): "b_age+exp",
        (28, 29): "b_stress+motivation",
        (30, 31): "b_biorythm+camp",
        (32, 33): "b_mystic+mystic_v2",
        (34, 35): "fin_x_td_A+sub_x_grap_A",
        (36, 37): "rust_x_exp_A+stress_x_camp_A",
        (38, 39): "a_reach+height",
        (40, 41): "b_reach+height",
        (42, 43): "camp_enc_A+B",
        (44, 45): "children_A+B",
    }

    @classmethod
    def apply_constraints(cls, weights: List[float]) -> Tuple[List[float], int]:
        corrections = 0

        for (idx1, idx2), (min_val, max_val) in cls.PAIR_BOUNDS.items():
            if idx1 >= len(weights) or idx2 >= len(weights):
                continue

            w1, w2 = weights[idx1], weights[idx2]
            w1_in_bounds = min_val <= w1 <= max_val
            w2_in_bounds = min_val <= w2 <= max_val

            if w1_in_bounds and w2_in_bounds:
                continue

            if w1_in_bounds and not w2_in_bounds:
                w2_new = max(min_val, min(max_val, w2))
                weights[idx2] = w2_new
                corrections += 1
                continue

            if w2_in_bounds and not w1_in_bounds:
                w1_new = max(min_val, min(max_val, w1))
                weights[idx1] = w1_new
                corrections += 1
                continue

            max_abs = max(abs(w1), abs(w2))
            if max_abs > abs(max_val) and max_abs > 0.001:
                scale = abs(max_val) / max_abs
                w1_scaled = w1 * scale
                w2_scaled = w2 * scale

                w1_clipped = max(min_val, min(max_val, w1_scaled))
                w2_clipped = max(min_val, min(max_val, w2_scaled))

                if abs(weights[idx1] - w1_clipped) > 0.0001:
                    weights[idx1] = w1_clipped
                    corrections += 1

                if abs(weights[idx2] - w2_clipped) > 0.0001:
                    weights[idx2] = w2_clipped
                    corrections += 1

        return weights, corrections

    @classmethod
    def validate_pair_balance(cls, weights: List[float]) -> Dict[str, Dict]:
        violations = {}

        for (idx1, idx2), (min_val, max_val) in cls.PAIR_BOUNDS.items():
            if idx1 >= len(weights) or idx2 >= len(weights):
                continue

            w1, w2 = weights[idx1], weights[idx2]

            if not (min_val <= w1 <= max_val and min_val <= w2 <= max_val):
                pair_key = cls.PAIR_NAMES.get((idx1, idx2), f"pair_{idx1}_{idx2}")
                violations[pair_key] = {
                    'weights': (w1, w2),
                    'bounds': (min_val, max_val)
                }

        return violations

    @classmethod
    def get_pair_stats(cls, weights: List[float]) -> Dict[str, Dict]:
        stats = {}

        for (idx1, idx2), (min_val, max_val) in cls.PAIR_BOUNDS.items():
            if idx1 >= len(weights) or idx2 >= len(weights):
                continue

            w1, w2 = weights[idx1], weights[idx2]
            pair_key = cls.PAIR_NAMES.get((idx1, idx2), f"pair_{idx1}_{idx2}")

            stats[pair_key] = {
                'w1': round(w1, 4),
                'w2': round(w2, 4),
                'sum': round(w1 + w2, 4),
                'diff': round(abs(w1 - w2), 4),
                'in_bounds': (min_val <= w1 <= max_val and min_val <= w2 <= max_val),
                'bounds': (min_val, max_val)
            }

        return stats


class AdvancedMathEngine:
    def __init__(self, lr=0.01, epochs=100, l1_ratio=0.01, alpha=0.1):
        self.lr = lr
        self.epochs = epochs
        self.l1_ratio = l1_ratio
        self.alpha = alpha
        self.weights = []
        self.bias = 0.0
        self.feature_means = []
        self.feature_stds = []
        self.feature_names = []

    def _sigmoid(self, z):
        z = max(-500, min(500, z))
        return 1.0 / (1.0 + math.exp(-z))

    def _extract_features(self, a: Fighter, b: Fighter, odds_a: float = 1.85, odds_b: float = 1.85):
        def safe_val(val, default=0.0):
            if val is None or val != val or val == float('inf') or val == float('-inf'):
                return default
            return float(val)

        a_features = [
            ("a_recent_wins", safe_val(a.recent_wins)),
            ("a_fin_rate", safe_val(a.fin_rate)),
            ("a_sub_rate", safe_val(a.sub_rate)),
            ("a_td_def", safe_val(a.td_def)),
            ("a_grap_def", safe_val(a.grap_def)),
            ("a_age", safe_val(a.age) / 50.0),
            ("a_exp", safe_val(a.exp)),
            ("a_fights_12m", safe_val(a.fights_12m)),
            ("a_months_off", safe_val(a.months_off)),
            ("a_wins", safe_val(a.wins) / 100.0),
            ("a_losses", safe_val(a.losses) / 100.0),
            ("a_stress_factor", safe_val(a.stress_factor)),
            ("a_motivation_index", safe_val(a.motivation_index)),
            ("a_biorythm_score", safe_val(a.biorythm_score)),
            ("a_camp_quality", safe_val(a.camp_quality)),
            ("a_mystic_factor", safe_val(a.mystic_factor)),
            ("a_mystic_v2", safe_val(a.mystic_v2)),
        ]

        b_features = [
            ("b_recent_wins", safe_val(b.recent_wins)),
            ("b_fin_rate", safe_val(b.fin_rate)),
            ("b_sub_rate", safe_val(b.sub_rate)),
            ("b_td_def", safe_val(b.td_def)),
            ("b_grap_def", safe_val(b.grap_def)),
            ("b_age", safe_val(b.age) / 50.0),
            ("b_exp", safe_val(b.exp)),
            ("b_fights_12m", safe_val(b.fights_12m)),
            ("b_months_off", safe_val(b.months_off)),
            ("b_wins", safe_val(b.wins) / 100.0),
            ("b_losses", safe_val(b.losses) / 100.0),
            ("b_stress_factor", safe_val(b.stress_factor)),
            ("b_motivation_index", safe_val(b.motivation_index)),
            ("b_biorythm_score", safe_val(b.biorythm_score)),
            ("b_camp_quality", safe_val(b.camp_quality)),
            ("b_mystic_factor", safe_val(b.mystic_factor)),
            ("b_mystic_v2", safe_val(b.mystic_v2)),
        ]

        fin_x_td_a = safe_val(a.fin_rate) * safe_val(a.td_def)
        sub_x_grap_a = safe_val(a.sub_rate) * safe_val(a.grap_def)
        rust_x_exp_a = (safe_val(a.months_off) / 12.0) * safe_val(a.exp)
        stress_x_camp_a = safe_val(a.stress_factor) * safe_val(a.camp_quality)

        interactions = [
            ("fin_x_td_A", fin_x_td_a),
            ("sub_x_grap_A", sub_x_grap_a),
            ("rust_x_exp_A", rust_x_exp_a),
            ("stress_x_camp_A", stress_x_camp_a),
        ]

        a_reach = safe_val(a.reach_cm) / 200.0
        a_height = safe_val(a.height_cm) / 200.0
        b_reach = safe_val(b.reach_cm) / 200.0
        b_height = safe_val(b.height_cm) / 200.0

        camp_encoding = {
            "Independent": 0.3,
            "Jackson Wink MMA": 0.8,
            "American Top Team": 0.85,
            "Team Alpha Male": 0.75,
            "Xtreme Couture": 0.7,
            "Elevation Fight Team": 0.7,
            "MMA Lab": 0.65,
            "Fortis MMA": 0.7,
            "Kill Cliff FC": 0.65,
            "SBG Ireland": 0.6,
            "Tiger Muay Thai": 0.6,
            "Nova União": 0.55,
            "American Kickboxing Academy": 0.8,
            "Serra-Longo Fight Team": 0.6,
            "Tristar Gym": 0.55,
            "MMA Factory": 0.5,
        }

        a_camp_enc = camp_encoding.get(a.camp_name, 0.4)
        b_camp_enc = camp_encoding.get(b.camp_name, 0.4)

        a_children = 0.3
        b_children = 0.3

        extra_features = [
            ("a_reach_cm", a_reach),
            ("a_height_cm", a_height),
            ("b_reach_cm", b_reach),
            ("b_height_cm", b_height),
            ("a_camp_name_encoded", a_camp_enc),
            ("b_camp_name_encoded", b_camp_enc),
            ("a_children_factor", a_children),
            ("b_children_factor", b_children),
        ]

        all_features = a_features + b_features + interactions + extra_features
        return [f[1] for f in all_features], [f[0] for f in all_features]

    def _normalize(self, X: List[List[float]], fit: bool = False, skip_indices: List[int] = None) -> List[List[float]]:
        if skip_indices is None:
            skip_indices = [5, 22]

        if not X:
            return X

        n_features = len(X[0])

        if fit:
            self.feature_means = [0.0] * n_features
            self.feature_stds = [1.0] * n_features

            for i in range(n_features):
                if i in skip_indices:
                    continue

                self.feature_means[i] = sum(row[i] for row in X) / len(X)
                variance = sum((row[i] - self.feature_means[i]) ** 2 for row in X) / len(X)
                std = math.sqrt(variance) if variance > 1e-8 else 1.0
                self.feature_stds[i] = std

        if not self.feature_means or not self.feature_stds:
            return X

        n_model = len(self.feature_means)
        n_data = len(X[0]) if X else 0

        if n_model != n_data:
            if n_model < n_data:
                for i in range(n_model, n_data):
                    self.feature_means.append(0.0)
                    self.feature_stds.append(1.0)
            else:
                self.feature_means = self.feature_means[:n_data]
                self.feature_stds = self.feature_stds[:n_data]

        result = []

        for row in X:
            new_row = []

            for i, x in enumerate(row):
                if i in skip_indices:
                    new_row.append(x)
                else:
                    mean = self.feature_means[i] if i < len(self.feature_means) else 0.0
                    std = self.feature_stds[i] if i < len(self.feature_stds) else 1.0

                    if std <= 1e-12:
                        std = 1.0

                    new_row.append((x - mean) / std)

            result.append(new_row)

        return result

    def fit(self, X, y, names=None, warm_start=False, sample_weights=None):
        if not X:
            return

        n_samples = len(X)
        n_features = len(X[0]) if X else 0

        if n_samples == 0 or n_features == 0:
            return

        if not warm_start:
            self.weights = [0.0] * n_features
            self.bias = 0.0

        if len(self.weights) != n_features:
            self.weights = [0.001] * n_features
            self.bias = 0.0

        if sample_weights is None:
            sample_weights = [1.0] * n_samples

        if len(sample_weights) != n_samples:
            sample_weights = [1.0] * n_samples

        if n_features == TARGET_FEATURES:
            means = getattr(self, "feature_means", [])
            stds = getattr(self, "feature_stds", [])

            has_stats = (
                    len(means) == TARGET_FEATURES
                    and len(stds) == TARGET_FEATURES
                    and all(s > 1e-12 for s in stds)
            )

            normalized = self._normalize(X, fit=not has_stats, skip_indices=[5, 22])
            if normalized and len(normalized) == n_samples:
                X = normalized

        dropout_rate = ModelConstants.DROPOUT_RATE
        MYSTIC_INDICES = [15, 32]
        ENRICHED_INDICES = [11, 12, 13, 14, 15, 28, 29, 30, 31, 32]
        ENRICHED_DROPOUT_RATE = 0.05

        for epoch in range(self.epochs):
            predictions = []

            for row in X:
                z = sum(w * x for w, x in zip(self.weights, row)) + self.bias
                prob = self._sigmoid(z)
                predictions.append(prob)

            gradients = [0.0] * n_features

            for i, row in enumerate(X):
                err = predictions[i] - y[i]
                w = sample_weights[i]

                for j in range(n_features):
                    gradients[j] += err * row[j] * w

            for j in range(n_features):
                gradients[j] /= n_samples

            dropout_mask = [1.0 if random.random() > dropout_rate else 0.0 for _ in range(n_features)]

            for j in ENRICHED_INDICES:
                if j < n_features:
                    if random.random() > ENRICHED_DROPOUT_RATE:
                        dropout_mask[j] = 1.0
                    else:
                        dropout_mask[j] = 0.0

            for j in range(n_features):
                if dropout_mask[j] == 0.0:
                    continue

                if j in MYSTIC_INDICES:
                    self.weights[j] -= self.lr * gradients[j]
                else:
                    l2_penalty = self.alpha * (1 - self.l1_ratio) * self.weights[j]
                    self.weights[j] -= self.lr * (gradients[j] + l2_penalty)

                    if abs(self.weights[j]) < 0.001:
                        self.weights[j] = 0.001 if self.weights[j] >= 0 else -0.001

            weighted_error = sum((predictions[i] - y[i]) * sample_weights[i] for i in range(n_samples))
            self.bias -= self.lr * weighted_error / n_samples

            for idx in POSITIVE_ONLY_INDICES:
                if idx < len(self.weights) and self.weights[idx] < POSITIVE_MIN_WEIGHT:
                    self.weights[idx] = POSITIVE_MIN_WEIGHT

            if A_LOSSES_INDEX < len(self.weights):
                if self.weights[A_LOSSES_INDEX] < -A_LOSSES_MAX_ABS:
                    self.weights[A_LOSSES_INDEX] = -A_LOSSES_MAX_ABS

            if B_MYSTIC_FACTOR_INDEX < len(self.weights):
                if abs(self.weights[B_MYSTIC_FACTOR_INDEX]) > B_MYSTIC_FACTOR_MAX_ABS:
                    self.weights[B_MYSTIC_FACTOR_INDEX] = max(
                        -B_MYSTIC_FACTOR_MAX_ABS,
                        min(B_MYSTIC_FACTOR_MAX_ABS, self.weights[B_MYSTIC_FACTOR_INDEX])
                    )

            if (epoch + 1) % 50 == 0:
                correct = sum(1 for i in range(n_samples) if (predictions[i] > 0.5) == (y[i] == 1))
                train_acc = correct / n_samples if n_samples > 0 else 0.0
                print(f" 📊 Эпоха {epoch + 1}/{self.epochs}: train_acc={train_acc * 100:.1f}%, "
                      f"dropout(base)={dropout_rate * 100:.0f}%, "
                      f"dropout(enriched)={ENRICHED_DROPOUT_RATE * 100:.0f}%")

    def predict_proba(self, features: List[float]) -> float:
        if features is None:
            return 0.5

        clean_features = []

        for f in features:
            if f is None:
                clean_features.append(0.0)
            elif f != f or f == float('inf') or f == float('-inf'):
                clean_features.append(0.0)
            else:
                clean_features.append(f)

        normalized = self._normalize([clean_features], fit=False, skip_indices=[5, 22])
        features = normalized[0] if normalized else clean_features

        z = sum(w * x for w, x in zip(self.weights, features)) + self.bias
        return self._sigmoid(z)


class MMAEngine:
    def __init__(self, weights_file: str = "mma_weights_v21.json"):
        self.weights_file = weights_file
        self.model = AdvancedMathEngine()
        self.best_accuracy = 0.0
        self.BATCH_TRAIN_SIZE = ModelConstants.BATCH_TRAIN_SIZE
        self.previous_run_accuracy = None
        self.fight_buffer = []
        self.pending_fights = []
        self.is_training_mode = True
        self.training_history = []
        self.recent_features = []
        self.stability_score = 0.0
        self.baseline_accuracy = 0.0
        self._recalibrated_this_cycle = False
        self.trained_on_fights = 0

        self._load_weights()
        self.load_baseline_weights()
        self.load_best_weights()
        self.load_recent_features()

    def _load_weights(self):
        TARGET_FEATURES = 46

        if os.path.exists(self.weights_file):
            try:
                with open(self.weights_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                data = {k.strip(): v for k, v in data.items()}

                loaded_weights = data.get("weights", [])
                loaded_means = data.get("feature_means", [])
                loaded_stds = data.get("feature_stds", [])
                loaded_names = data.get("feature_names", [])

                if len(loaded_weights) < TARGET_FEATURES:
                    needed = TARGET_FEATURES - len(loaded_weights)
                    for _ in range(needed):
                        loaded_weights.append(0.001)
                    print(f"✅ Добавлено {needed} новых весов (всего {len(loaded_weights)})")

                if len(loaded_means) < TARGET_FEATURES:
                    needed = TARGET_FEATURES - len(loaded_means)
                    for _ in range(needed):
                        loaded_means.append(0.0)

                if len(loaded_stds) < TARGET_FEATURES:
                    needed = TARGET_FEATURES - len(loaded_stds)
                    for _ in range(needed):
                        loaded_stds.append(1.0)

                if len(loaded_names) < TARGET_FEATURES:
                    new_names = [
                        "a_recent_wins", "a_fin_rate", "a_sub_rate", "a_td_def", "a_grap_def",
                        "a_age", "a_exp", "a_fights_12m", "a_months_off", "a_wins", "a_losses",
                        "a_stress_factor", "a_motivation_index", "a_biorythm_score", "a_camp_quality",
                        "a_mystic_factor", "a_mystic_v2",
                        "b_recent_wins", "b_fin_rate", "b_sub_rate", "b_td_def", "b_grap_def",
                        "b_age", "b_exp", "b_fights_12m", "b_months_off", "b_wins", "b_losses",
                        "b_stress_factor", "b_motivation_index", "b_biorythm_score", "b_camp_quality",
                        "b_mystic_factor", "b_mystic_v2",
                        "fin_x_td_A", "sub_x_grap_A", "rust_x_exp_A", "stress_x_camp_A",
                        "a_reach_cm", "a_height_cm", "b_reach_cm", "b_height_cm",
                        "a_camp_name_encoded", "b_camp_name_encoded",
                        "a_children_factor", "b_children_factor"
                    ]

                    for name in new_names:
                        if len(loaded_names) < TARGET_FEATURES:
                            loaded_names.append(name)

                if len(loaded_weights) > TARGET_FEATURES:
                    loaded_weights = loaded_weights[:TARGET_FEATURES]

                if len(loaded_means) > TARGET_FEATURES:
                    loaded_means = loaded_means[:TARGET_FEATURES]

                if len(loaded_stds) > TARGET_FEATURES:
                    loaded_stds = loaded_stds[:TARGET_FEATURES]

                if len(loaded_names) > TARGET_FEATURES:
                    loaded_names = loaded_names[:TARGET_FEATURES]

                # ✅ v55.3: Санация весов при загрузке
                if len(loaded_weights) > B_RECENT_WINS_INDEX:
                    loaded_weights[B_RECENT_WINS_INDEX] = max(
                        -B_RECENT_WINS_MAX_ABS,
                        min(B_RECENT_WINS_MAX_ABS, loaded_weights[B_RECENT_WINS_INDEX])
                    )

                # ✅ v55.4: a_losses ограничен ±0.060
                if len(loaded_weights) > A_LOSSES_INDEX:
                    loaded_weights[A_LOSSES_INDEX] = max(
                        -A_LOSSES_MAX_ABS,
                        min(A_LOSSES_MAX_ABS, loaded_weights[A_LOSSES_INDEX])
                    )

                # ✅ v55.4: b_mystic_factor ограничен ±0.030
                if len(loaded_weights) > B_MYSTIC_FACTOR_INDEX:
                    loaded_weights[B_MYSTIC_FACTOR_INDEX] = max(
                        -B_MYSTIC_FACTOR_MAX_ABS,
                        min(B_MYSTIC_FACTOR_MAX_ABS, loaded_weights[B_MYSTIC_FACTOR_INDEX])
                    )

                # ✅ v55.5: b_months_off ограничен ±0.040
                if len(loaded_weights) > B_MONTHS_OFF_INDEX:
                    loaded_weights[B_MONTHS_OFF_INDEX] = max(
                        -B_MONTHS_OFF_MAX_ABS,
                        min(B_MONTHS_OFF_MAX_ABS, loaded_weights[B_MONTHS_OFF_INDEX])
                    )

                # ✅ v55.7: b_losses ограничен ±0.100
                if len(loaded_weights) > B_LOSSES_INDEX:
                    loaded_weights[B_LOSSES_INDEX] = max(
                        -B_LOSSES_MAX_ABS,
                        min(B_LOSSES_MAX_ABS, loaded_weights[B_LOSSES_INDEX])
                    )

                # ✅ v55.6: Автоматическая коррекция масштаба wins/losses
                for idx in WINS_LOSSES_INDICES:
                    if idx < len(loaded_means) and loaded_means[idx] > 1.0:
                        loaded_means[idx] /= 100.0
                        loaded_stds[idx] /= 100.0

                for idx in POSITIVE_ONLY_INDICES:
                    if idx < len(loaded_weights) and loaded_weights[idx] < POSITIVE_MIN_WEIGHT:
                        loaded_weights[idx] = POSITIVE_MIN_WEIGHT

                for idx, min_weight in USEFUL_MIN_WEIGHTS.items():
                    if idx < len(loaded_weights) and loaded_weights[idx] < min_weight:
                        loaded_weights[idx] = min_weight

                self.model.weights = loaded_weights
                self.model.bias = data.get("bias", 0.0)
                self.model.feature_means = loaded_means
                self.model.feature_stds = loaded_stds
                self.model.feature_names = loaded_names
                self.stability_score = data.get('stability_score', 0.0)
                self.trained_on_fights = data.get('trained_on_fights', 0)

                n_weights = len(self.model.weights)

                if len(self.model.feature_means) < n_weights:
                    for i in range(len(self.model.feature_means), n_weights):
                        self.model.feature_means.append(0.0)
                        self.model.feature_stds.append(1.0)
                        self.model.feature_names.append(f"feature_{i}")

                if abs(self.model.bias) > 0.3:
                    self.model.bias = 0.0

                acc = data.get('loocv_accuracy', 0.0)

                if acc > 0.001:
                    print(f"✅ Веса загружены (боёв: {data.get('trained_on_fights', '?')}, "
                          f"точность: {acc * 100:.1f}%, стабильность: {self.stability_score})")
                    self.best_accuracy = acc

                self.previous_run_accuracy = data.get('previous_run_accuracy', None)

            except Exception as e:
                print(f"⚠️ Ошибка загрузки весов: {e}")
                print("🔧 Инициализация весов с нуля...")

                self.model.weights = [0.001] * TARGET_FEATURES
                self.model.bias = 0.0
                self.model.feature_means = [0.0] * TARGET_FEATURES
                self.model.feature_stds = [1.0] * TARGET_FEATURES
                self.model.feature_names = [
                    "a_recent_wins", "a_fin_rate", "a_sub_rate", "a_td_def", "a_grap_def",
                    "a_age", "a_exp", "a_fights_12m", "a_months_off", "a_wins", "a_losses",
                    "a_stress_factor", "a_motivation_index", "a_biorythm_score", "a_camp_quality",
                    "a_mystic_factor", "a_mystic_v2",
                    "b_recent_wins", "b_fin_rate", "b_sub_rate", "b_td_def", "b_grap_def",
                    "b_age", "b_exp", "b_fights_12m", "b_months_off", "b_wins", "b_losses",
                    "b_stress_factor", "b_motivation_index", "b_biorythm_score", "b_camp_quality",
                    "b_mystic_factor", "b_mystic_v2",
                    "fin_x_td_A", "sub_x_grap_A", "rust_x_exp_A", "stress_x_camp_A",
                    "a_reach_cm", "a_height_cm", "b_reach_cm", "b_height_cm",
                    "a_camp_name_encoded", "b_camp_name_encoded",
                    "a_children_factor", "b_children_factor"
                ]

                self.best_accuracy = 0.0
                self.previous_run_accuracy = None

                try:
                    with open(self.weights_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "version": "v55.7-46_FEATURES",
                            "weights": self.model.weights,
                            "bias": self.model.bias,
                            "feature_means": self.model.feature_means,
                            "feature_stds": self.model.feature_stds,
                            "feature_names": self.model.feature_names,
                            "trained_on_fights": 0,
                            "loocv_accuracy": 0.0,
                            "previous_run_accuracy": 0.0,
                            "stability_score": 0.0
                        }, f, indent=2)
                    print(f"✅ Создан новый файл весов: {self.weights_file}")
                except Exception as e2:
                    print(f"⚠️ Ошибка создания файла весов: {e2}")
        else:
            print("🔧 Файл весов не найден — инициализация с нуля...")

            self.model.weights = [0.001] * TARGET_FEATURES
            self.model.bias = 0.0
            self.model.feature_means = [0.0] * TARGET_FEATURES
            self.model.feature_stds = [1.0] * TARGET_FEATURES
            self.model.feature_names = [
                "a_recent_wins", "a_fin_rate", "a_sub_rate", "a_td_def", "a_grap_def",
                "a_age", "a_exp", "a_fights_12m", "a_months_off", "a_wins", "a_losses",
                "a_stress_factor", "a_motivation_index", "a_biorythm_score", "a_camp_quality",
                "a_mystic_factor", "a_mystic_v2",
                "b_recent_wins", "b_fin_rate", "b_sub_rate", "b_td_def", "b_grap_def",
                "b_age", "b_exp", "b_fights_12m", "b_months_off", "b_wins", "b_losses",
                "b_stress_factor", "b_motivation_index", "b_biorythm_score", "b_camp_quality",
                "b_mystic_factor", "b_mystic_v2",
                "fin_x_td_A", "sub_x_grap_A", "rust_x_exp_A", "stress_x_camp_A",
                "a_reach_cm", "a_height_cm", "b_reach_cm", "b_height_cm",
                "a_camp_name_encoded", "b_camp_name_encoded",
                "a_children_factor", "b_children_factor"
            ]

            self.best_accuracy = 0.0
            self.previous_run_accuracy = None

            try:
                with open(self.weights_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "version": "v55.7-46_FEATURES",
                        "weights": self.model.weights,
                        "bias": self.model.bias,
                        "feature_means": self.model.feature_means,
                        "feature_stds": self.model.feature_stds,
                        "feature_names": self.model.feature_names,
                        "trained_on_fights": 0,
                        "loocv_accuracy": 0.0,
                        "previous_run_accuracy": 0.0,
                        "stability_score": 0.0
                    }, f, indent=2)
                print(f"✅ Создан новый файл весов: {self.weights_file}")
            except Exception as e2:
                print(f"⚠️ Ошибка создания файла весов: {e2}")

    def load_baseline_weights(self):
        if os.path.exists("weights_baseline.json"):
            try:
                with open("weights_baseline.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.baseline_accuracy = data.get('loocv_accuracy', 0.0)
                print(f"✅ Эталон загружен: {self.baseline_accuracy * 100:.1f}%")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки эталона: {e}")
        else:
            print("⚠️ Эталон не найден.")

    def load_best_weights(self):
        """
        ✅ v55.8: best = глобальный максимум.
        1. Всегда читает best_accuracy из weights_best.json.
        2. Если best выше рабочей точности — АВТО-ВОЗВРАТ best-весов в модель.
        """
        if os.path.exists("weights_best.json"):
            try:
                with open("weights_best.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                data = {k.strip(): v for k, v in data.items()}
                best_acc = data.get('loocv_accuracy', 0.0)
                self.best_accuracy = max(self.best_accuracy, best_acc)
                working_acc = self.previous_run_accuracy if self.previous_run_accuracy is not None else 0.0
                if best_acc > working_acc and best_acc > 0.001:
                    self.model.weights = data.get("weights", self.model.weights)
                    self.model.bias = data.get("bias", self.model.bias)
                    self.model.feature_means = data.get("feature_means", self.model.feature_means)
                    self.model.feature_stds = data.get("feature_stds", self.model.feature_stds)
                    raw_names = data.get("feature_names", []) or []
                    if raw_names:
                        self.model.feature_names = [n.strip() if isinstance(n, str) else n for n in raw_names]
                    if abs(self.model.bias) > 0.3:
                        self.model.bias = 0.0
                    print(f"✅ АВТО-ВОЗВРАТ: best {best_acc * 100:.1f}% > рабочие {working_acc * 100:.1f}%")
                else:
                    print(f"✅ Лучшие веса: {self.best_accuracy * 100:.1f}% "
                          f"(рабочие: {working_acc * 100:.1f}%)")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки лучших весов: {e}")
        else:
            print("⚠️ Лучшие веса не найдены.")

    def load_recent_features(self):
        recent_file = os.path.join(DATASET_DIR, "recent_features.json")

        if os.path.exists(recent_file):
            try:
                with open(recent_file, "r", encoding="utf-8") as f:
                    self.recent_features = json.load(f)
                print(f"✅ Загружено {len(self.recent_features)} последних боёв для нормализатора")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки recent_features: {e}")

    def update_recent_features(self, features: List[float]):
        self.recent_features.append(features)

        if len(self.recent_features) > 500:
            self.recent_features = self.recent_features[-500:]

        recent_file = os.path.join(DATASET_DIR, "recent_features.json")

        try:
            with open(recent_file, "w", encoding="utf-8") as f:
                json.dump(self.recent_features, f)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения recent_features: {e}")

    def recalibrate_scaler(self):
        if self._recalibrated_this_cycle:
            return

        if not self.recent_features:
            return

        print("Плавная адаптация (alpha=0.005)...")
        alpha = 0.005

        valid_features = [row for row in self.recent_features if len(row) > 0]

        if not valid_features:
            print("⚠️ Нет валидных записей для нормализации")
            return

        n_features = len(valid_features[0])

        valid_features = [row for row in valid_features if len(row) == n_features]

        if not valid_features:
            print("⚠️ Нет записей с корректной размерностью")
            return

        try:
            new_means = [sum(row[i] for row in valid_features) / len(valid_features) for i in range(n_features)]
            new_stds = []

            for i in range(n_features):
                variance = sum((row[i] - new_means[i]) ** 2 for row in valid_features) / len(valid_features)
                std = math.sqrt(variance) if variance > 1e-8 else 1.0
                new_stds.append(std)

            if not self.model.feature_means:
                self.model.feature_means = new_means
                self.model.feature_stds = new_stds
            else:
                for i in range(min(len(self.model.feature_means), n_features)):
                    self.model.feature_means[i] = (1 - alpha) * self.model.feature_means[i] + alpha * new_means[i]
                    self.model.feature_stds[i] = (1 - alpha) * self.model.feature_stds[i] + alpha * new_stds[i]

        except Exception as e:
            print(f"⚠️ Ошибка при расчёте нормализации: {e}")
            return

        self._recalibrated_this_cycle = True

    def rollback_to_baseline(self):
        if not os.path.exists("weights_baseline.json"):
            print("❌ Эталон не найден!")
            return False

        try:
            with open("weights_baseline.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            self.model.weights = data["weights"]
            self.model.bias = data["bias"]
            self.model.feature_means = data.get("feature_means", [])
            self.model.feature_stds = data.get("feature_stds", [])

            raw_names = data.get("feature_names", []) or []
            self.model.feature_names = [n.strip() if isinstance(n, str) else n for n in raw_names]

            if abs(self.model.bias) > 0.3:
                self.model.bias = 0.0

            with open("mma_weights_v21.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print(f"✅ Откат к эталону! Точность: {self.baseline_accuracy * 100:.1f}%")
            return True

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def rollback_to_best(self):
        if not os.path.exists("weights_best.json"):
            print("❌ Лучшие веса не найдены!")
            return False

        try:
            with open("weights_best.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            self.model.weights = data["weights"]
            self.model.bias = data["bias"]
            self.model.feature_means = data.get("feature_means", [])
            self.model.feature_stds = data.get("feature_stds", [])
            self.model.feature_names = data.get("feature_names", [])

            if abs(self.model.bias) > 0.3:
                self.model.bias = 0.0

            with open("mma_weights_v21.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print(f"✅ Откат к лучшим весам! Точность: {self.best_accuracy * 100:.1f}%")
            return True

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def retrain_from_dataset(self):
        print("❌ Полное переобучение запрещено! (занимает 30+ часов)")
        print(" Используйте инкрементальное обучение (команда 2).")

    def get_recent_accuracies(self, dataset: list) -> Tuple[float, float, float]:
        if len(dataset) < 5:
            return 0.0, 0.0, 0.0

        eval_start = max(0, len(dataset) - 500)
        eval_end = max(0, len(dataset) - 400)
        eval_fights = dataset[eval_start:eval_end]

        if len(eval_fights) < 10:
            print("⚠️ get_recent_accuracies: недостаточно боёв вне обучающего окна, используется последние 100 (возможно пересечение)")
            eval_fights = dataset[-100:]

        correct_win = 0
        total = 0

        for fight in eval_fights:
            try:
                a = make_fighter_from_dict(fight.get("stats_a", {}), fight.get("fighter_a", "Unknown"))
                b = make_fighter_from_dict(fight.get("stats_b", {}), fight.get("fighter_b", "Unknown"))

                try:
                    odds_a = float(fight.get("odds_a", 1.85))
                except (ValueError, TypeError):
                    odds_a = 1.85

                try:
                    odds_b = float(fight.get("odds_b", 1.85))
                except (ValueError, TypeError):
                    odds_b = 1.85

                features, _ = self.model._extract_features(a, b, odds_a, odds_b)
                prob_a = self.model.predict_proba(features)
                predicted_winner = fight.get("fighter_a") if prob_a > 0.5 else fight.get("fighter_b")

                if _names_match_by_id(predicted_winner, fight.get("winner", "")):
                    correct_win += 1

                total += 1
            except Exception as e:
                print(f" ⚠️ Ошибка при оценке боя: {e}")
                continue

        win_acc = (correct_win / total * 100) if total else 0.0
        return win_acc, 0.0, 0.0

    def _incremental_fit(self, new_fight_data: dict, all_dataset: list) -> Tuple[int, int]:
        batch_size = 200

        recent_fights = all_dataset[-300:] if len(all_dataset) >= 300 else all_dataset
        historical_fights = all_dataset[:-300] if len(all_dataset) > 300 else []

        sampled_fresh = random.sample(recent_fights, min(139, len(recent_fights)))
        sampled_hist = random.sample(historical_fights, min(60, len(historical_fights))) if historical_fights else []

        micro_batch = sampled_fresh + sampled_hist

        weights_batch = [ModelConstants.TEMPORAL_WEIGHT_NEW] * len(sampled_fresh)
        weights_batch.extend([0.7] * len(sampled_hist))

        X, y, names, sample_weights = [], [], [], []

        for d, w in zip(micro_batch, weights_batch):
            try:
                a = make_fighter_from_dict(d.get("stats_a", {}), d.get("fighter_a", "Unknown"))
                b = make_fighter_from_dict(d.get("stats_b", {}), d.get("fighter_b", "Unknown"))

                odds_a = float(d.get("odds_a", 1.85))
                odds_b = float(d.get("odds_b", 1.85))

                features, names = self.model._extract_features(a, b, odds_a, odds_b)

                X.append(features)
                y.append(1 if _names_match_by_id(d.get("winner", ""), d.get("fighter_a", "")) else 0)
                sample_weights.append(w)
            except:
                continue

        if not X or len(X[0]) == 0:
            return 0, len(self.model.weights)

        temp_model = AdvancedMathEngine(
            lr=ModelConstants.LEARNING_RATE,
            epochs=ModelConstants.EPOCHS,
            l1_ratio=ModelConstants.L1_RATIO,
            alpha=ModelConstants.ALPHA
        )

        temp_model.weights = self.model.weights.copy() if self.model.weights else [0.0] * len(X[0])
        temp_model.bias = self.model.bias
        temp_model.feature_means = self.model.feature_means.copy() if self.model.feature_means else []
        temp_model.feature_stds = self.model.feature_stds.copy() if self.model.feature_stds else []
        temp_model.feature_names = self.model.feature_names.copy() if self.model.feature_names else []

        old_dropout = ModelConstants.DROPOUT_RATE
        ModelConstants.DROPOUT_RATE = 0.05

        try:
            temp_model.fit(X, y, names, warm_start=True, sample_weights=sample_weights)
        finally:
            ModelConstants.DROPOUT_RATE = old_dropout

        # ✅ v55.2: копируем bias из temp_model в self.model
        if temp_model.bias == temp_model.bias and temp_model.bias != float('inf') and temp_model.bias != float('-inf'):
            self.model.bias = temp_model.bias
        else:
            self.model.bias = 0.0
            print(" ⚠️ Bias temp_model был NaN/Inf — сброшен к 0.0")

        if abs(self.model.bias) > 0.3:
            print(f" ⚠️ Bias ограничен: {self.model.bias:.4f} → 0.0")
            self.model.bias = 0.0

        # ✅ v55.6: дополнительное ограничение bias ±0.003 (для стабильности)
        BIAS_MAX_ABS = 0.003
        if abs(self.model.bias) > BIAS_MAX_ABS:
            old_bias = self.model.bias
            self.model.bias = max(-BIAS_MAX_ABS, min(BIAS_MAX_ABS, self.model.bias))
            print(f" ⚠️ Bias ограничен (v55.6): {old_bias:.4f} → {self.model.bias:.4f}")

        # ========= ИЗМЕНЕНИЯ v55.7 =========
        # 1. Упрощённая логика обновления весов (единый step_ratio)
        corrections_made = 0

        for i in range(len(self.model.weights)):
            if i < len(temp_model.weights):
                diff = abs(temp_model.weights[i] - self.model.weights[i])
                threshold = 0.00001
                step_ratio = 0.5   # единый коэффициент
                if diff > threshold:
                    step = diff * step_ratio
                    if temp_model.weights[i] > self.model.weights[i]:
                        self.model.weights[i] += step
                    else:
                        self.model.weights[i] -= step
                    corrections_made += 1

        # 2. Адаптивный clipping на основе feature_stds (ПОСЛЕ обновления весов)
        for i in range(len(self.model.weights)):
            if i < len(self.model.feature_stds):
                raw_std = self.model.feature_stds[i]
                if raw_std < 1e-8:
                    raw_std = 1.0
                max_w = ADAPTIVE_C / (raw_std + 1e-8)
                if abs(self.model.weights[i]) > max_w:
                    self.model.weights[i] = max_w if self.model.weights[i] > 0 else -max_w
                    corrections_made += 1
        # ========= КОНЕЦ ИЗМЕНЕНИЙ v55.7 =========

        # ✅ Специфические лимиты (СОХРАНЕНЫ как дополнительная защита):
        if B_RECENT_WINS_INDEX < len(self.model.weights):
            w = self.model.weights[B_RECENT_WINS_INDEX]
            if abs(w) > B_RECENT_WINS_MAX_ABS:
                self.model.weights[B_RECENT_WINS_INDEX] = max(
                    -B_RECENT_WINS_MAX_ABS,
                    min(B_RECENT_WINS_MAX_ABS, w)
                )
                corrections_made += 1

        if A_LOSSES_INDEX < len(self.model.weights):
            w = self.model.weights[A_LOSSES_INDEX]
            if abs(w) > A_LOSSES_MAX_ABS:
                self.model.weights[A_LOSSES_INDEX] = max(
                    -A_LOSSES_MAX_ABS,
                    min(A_LOSSES_MAX_ABS, w)
                )
                corrections_made += 1

        if B_MYSTIC_FACTOR_INDEX < len(self.model.weights):
            w = self.model.weights[B_MYSTIC_FACTOR_INDEX]
            if abs(w) > B_MYSTIC_FACTOR_MAX_ABS:
                self.model.weights[B_MYSTIC_FACTOR_INDEX] = max(
                    -B_MYSTIC_FACTOR_MAX_ABS,
                    min(B_MYSTIC_FACTOR_MAX_ABS, w)
                )
                corrections_made += 1

        if B_MONTHS_OFF_INDEX < len(self.model.weights):
            w = self.model.weights[B_MONTHS_OFF_INDEX]
            if abs(w) > B_MONTHS_OFF_MAX_ABS:
                self.model.weights[B_MONTHS_OFF_INDEX] = max(
                    -B_MONTHS_OFF_MAX_ABS,
                    min(B_MONTHS_OFF_MAX_ABS, w)
                )
                corrections_made += 1

        # ✅ v55.7: b_losses ограничен ±0.100
        if B_LOSSES_INDEX < len(self.model.weights):
            w = self.model.weights[B_LOSSES_INDEX]
            if abs(w) > B_LOSSES_MAX_ABS:
                self.model.weights[B_LOSSES_INDEX] = max(
                    -B_LOSSES_MAX_ABS,
                    min(B_LOSSES_MAX_ABS, w)
                )
                corrections_made += 1

        # ✅ Защита положительных весов
        for idx in POSITIVE_ONLY_INDICES:
            if idx < len(self.model.weights) and self.model.weights[idx] < POSITIVE_MIN_WEIGHT:
                self.model.weights[idx] = POSITIVE_MIN_WEIGHT
                corrections_made += 1

        for idx, min_weight in USEFUL_MIN_WEIGHTS.items():
            if idx < len(self.model.weights) and self.model.weights[idx] < min_weight:
                self.model.weights[idx] = min_weight
                corrections_made += 1

        # ✅ Ограничение для возраста
        AGE_DIFF_INDEX_A = 5
        AGE_DIFF_INDEX_B = 22
        AGE_DIFF_MAX = 0.10

        for idx in [AGE_DIFF_INDEX_A, AGE_DIFF_INDEX_B]:
            if idx < len(self.model.weights):
                current_age = self.model.weights[idx]
                if abs(current_age) > AGE_DIFF_MAX:
                    target_age = AGE_DIFF_MAX if current_age > 0 else -AGE_DIFF_MAX
                    self.model.weights[idx] = target_age
                    print(f" 📊 age_diff демпфирован: {current_age:.4f} → {target_age:.4f}")
                    corrections_made += 1

        # ✅ Защита от NaN/Inf
        zero_count = 0
        total_weight = sum(abs(w) for w in self.model.weights)
        n_weights = len(self.model.weights)

        if n_weights > 0 and total_weight > 0:
            avg_weight = total_weight / n_weights
            adaptive_threshold = max(avg_weight * 0.01, 0.00001)

            for i in range(len(self.model.weights)):
                if abs(self.model.weights[i]) < adaptive_threshold:
                    sign = 1 if self.model.weights[i] >= 0 else -1
                    self.model.weights[i] = sign * adaptive_threshold
                    zero_count += 1

            if zero_count > 0:
                print(f" 🔄 Инициализировано {zero_count} весов → ±{adaptive_threshold:.6f} "
                      f"(1% от среднего {avg_weight:.6f})")
        else:
            for i in range(len(self.model.weights)):
                if abs(self.model.weights[i]) < 0.0001:
                    sign = 1 if self.model.weights[i] >= 0 else -1
                    self.model.weights[i] = sign * 0.0001
                    zero_count += 1

            if zero_count > 0:
                print(f" 🔄 Инициализировано {zero_count} весов → ±0.0001 (фолбэк)")

        nan_count = 0
        for i in range(len(self.model.weights)):
            w = self.model.weights[i]
            if w != w or w == float('inf') or w == float('-inf'):
                nan_count += 1
                if i < len(temp_model.weights) and temp_model.weights[i] == temp_model.weights[i]:
                    self.model.weights[i] = temp_model.weights[i]
                else:
                    self.model.weights[i] = 0.001

        if nan_count > 0:
            print(f" ⚠️ Восстановлено {nan_count} весов с NaN/Inf!")

        if self.model.bias != self.model.bias or self.model.bias == float('inf') or self.model.bias == float('-inf'):
            self.model.bias = 0.0
            print(f" ⚠️ Bias восстановлен к 0.0!")

        # ✅ Применение парных ограничений
        print(f" 🔒 Применение ограничений для пар признаков...")
        self.model.weights, pair_corrections = FeaturePairConstraints.apply_constraints(self.model.weights)

        if pair_corrections > 0:
            print(f" ✅ Скорректировано {pair_corrections} весов пар признаков")
            corrections_made += pair_corrections

        violations = FeaturePairConstraints.validate_pair_balance(self.model.weights)
        if violations:
            for pair_key, info in violations.items():
                w1, w2 = info['weights']
                min_b, max_b = info['bounds']
                print(f" ⚠️ {pair_key}: [{w1:.4f}, {w2:.4f}] "
                      f"границы [{min_b:.2f}, {max_b:.2f}]")
        else:
            print(f" ✅ Все пары в границах")

        print(f" 🔄 Обучение: {corrections_made} весов, батч={len(micro_batch)} "
              f"(свежие={len(sampled_fresh)}, исторические={len(sampled_hist)})")

        return corrections_made, len(self.model.weights)

    def _fight_to_dict(self, fd: FightData, res: Result, orig_a: str, orig_b: str) -> dict:
        odds_b_value = fd.matchup_odds.get("odds_b", 1.85) if fd.matchup_odds else 1.85

        return {
            "event": fd.location.split('(')[0].strip() if '(' in fd.location else fd.location,
            "date": fd.date.strftime("%Y-%m-%d"),
            "fighter_a": orig_a,
            "fighter_b": orig_b,
            "winner": res.winner,
            "round": res.rnd,
            "method": res.method.name,
            "odds_a": fd.odds_a,
            "odds_b": odds_b_value,
            "stats_a": {
                k: getattr(fd.a, k) for k in
                ["age", "wins", "losses", "fin_rate", "sub_rate", "td_def", "grap_def",
                 "recent_wins", "months_off", "fights_12m", "stress_factor",
                 "motivation_index", "biorythm_score", "camp_quality", "camp_name",
                 "mystic_factor", "mystic_v2", "reach_cm", "height_cm"]
            },
            "stats_b": {
                k: getattr(fd.b, k) for k in
                ["age", "wins", "losses", "fin_rate", "sub_rate", "td_def", "grap_def",
                 "recent_wins", "months_off", "fights_12m", "stress_factor",
                 "motivation_index", "biorythm_score", "camp_quality", "camp_name",
                 "mystic_factor", "mystic_v2", "reach_cm", "height_cm"]
            }
        }

    def add_fight_to_buffer(self, fd: FightData, res: Result, orig_a: str, orig_b: str) -> dict:
        fight_dict = self._fight_to_dict(fd, res, orig_a, orig_b)
        self.pending_fights.append(fight_dict)

        buffer_status = f"{len(self.pending_fights)}/{self.BATCH_TRAIN_SIZE}"
        print(f" 📦 Буфер: {buffer_status} боёв")

        if len(self.pending_fights) >= self.BATCH_TRAIN_SIZE:
            return self.process_batch()

        return {
            "status": "buffered",
            "status_text": f"📦 Бой добавлен в буфер ({buffer_status})",
            "buffer_size": len(self.pending_fights),
            "batch_size": self.BATCH_TRAIN_SIZE
        }

    def _get_active_part_file(self) -> str:
        os.makedirs(DATASET_DIR, exist_ok=True)
        part_files = sorted(glob.glob(os.path.join(DATASET_DIR, "real_dataset_part*.json")))

        if not part_files:
            new_file = os.path.join(DATASET_DIR, "real_dataset_part1.json")

            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

            print(f" 📄 Создан новый файл: {new_file}")
            return new_file

        last_file = part_files[-1]

        try:
            file_size = os.path.getsize(last_file)
        except Exception:
            file_size = 0

        if file_size >= MAX_DATASET_SIZE_BYTES:
            import re

            match = re.search(r'part(\d+)\.json$', last_file)

            if match:
                next_num = int(match.group(1)) + 1
            else:
                next_num = len(part_files) + 1

            new_file = os.path.join(DATASET_DIR, f"real_dataset_part{next_num}.json")

            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

            print(f" 📄 Файл {os.path.basename(last_file)} достиг {file_size / (1024 * 1024):.2f} МБ")
            print(f" 📄 Создан новый файл: {os.path.basename(new_file)}")
            return new_file

        return last_file

    def process_batch(self) -> dict:
        if len(self.pending_fights) == 0:
            return {"status": "empty", "status_text": "⚠️ Буфер пуст"}

        # ✅ v55.7: сброс флага для обновления статистик при каждом батче
        self._recalibrated_this_cycle = False

        current_timestamp = datetime.now()
        batch_size = len(self.pending_fights)

        print(f"📦 ПАКЕТНОЕ ОБУЧЕНИЕ на {batch_size} боях...")
        print("=" * 50)

        full_dataset = []
        part_files = sorted(glob.glob(os.path.join(DATASET_DIR, "real_dataset_part*.json")))

        for part_file in part_files:
            try:
                with open(part_file, "r", encoding="utf-8") as f:
                    full_dataset.extend(json.load(f))
            except Exception as e:
                print(f"⚠️ Ошибка чтения {os.path.basename(part_file)}: {e}")

        dataset = full_dataset
        new_fights_to_save = []

        for fight in self.pending_fights:
            key = f"{fight['fighter_a']}_{fight['fighter_b']}_{fight['date']}"
            seen = {f"{d['fighter_a']}_{d['fighter_b']}_{d['date']}": d for d in dataset}

            if key not in seen:
                dataset.append(fight)
                new_fights_to_save.append(fight)

        old_acc = 0.0

        if os.path.exists("mma_weights_v21.json"):
            try:
                old_acc = json.load(open("mma_weights_v21.json", "r", encoding="utf-8")).get('loocv_accuracy', 0.0)
            except:
                pass

        last_fight = self.pending_fights[-1]
        corrections, total_weights = self._incremental_fit(last_fight, dataset)

        # ✅ v55.7: обновление статистик нормализации после обучения
        self.recalibrate_scaler()

        acc_win, acc_rnd, acc_mth = self.get_recent_accuracies(dataset)
        acc_win_ratio = acc_win / 100.0

        print(f" 💾 Сохранение текущих весов...")

        # ✅ v55.8: цель — глобальный максимум (best), а не прошлый прогон:
        # деградация не lowers планку, «отскок» не уничтожает best
        target_accuracy = self.best_accuracy

        with open("mma_weights_v21.json", "w", encoding="utf-8") as f:
            json.dump({
                "version": "v55.7-46_FEATURES",
                "weights": self.model.weights,
                "bias": self.model.bias,
                "feature_means": self.model.feature_means,
                "feature_stds": self.model.feature_stds,
                "feature_names": self.model.feature_names,
                "trained_on_fights": len(dataset),
                "loocv_accuracy": acc_win_ratio,
                "previous_run_accuracy": acc_win_ratio,
                "stability_score": self.stability_score
            }, f, indent=2)

        if acc_win_ratio > target_accuracy:
            self.best_accuracy = acc_win_ratio
            self.previous_run_accuracy = acc_win_ratio

            print(f" ✅ ТОЧНОСТЬ УЛУЧШИЛАСЬ! {acc_win:.1f}% > {target_accuracy * 100:.1f}%")

            with open("weights_best.json", "w", encoding="utf-8") as f:
                json.dump({
                    "version": "v55.7-46_FEATURES",
                    "weights": self.model.weights,
                    "bias": self.model.bias,
                    "feature_means": self.model.feature_means,
                    "feature_stds": self.model.feature_stds,
                    "feature_names": self.model.feature_names,
                    "trained_on_fights": len(dataset),
                    "loocv_accuracy": acc_win_ratio,
                    "previous_run_accuracy": acc_win_ratio,
                    "stability_score": self.stability_score
                }, f, indent=2)
        else:
            delta = (acc_win_ratio - target_accuracy) * 100
            print(f" ⚠️ Точность НЕ улучшилась: {acc_win:.1f}% vs {target_accuracy * 100:.1f}% ({delta:+.1f}%)")
            print(f" 📌 Веса сохранены для накопления знаний (инкрементальное обучение)")

        if new_fights_to_save:
            print(f" Сохранение {len(new_fights_to_save)} новых боев в part-файлы...")
            active_part = self._get_active_part_file()

            try:
                with open(active_part, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                existing_data.extend(new_fights_to_save)

                with open(active_part, "w", encoding="utf-8") as f:
                    json.dump(existing_data, f, indent=2, ensure_ascii=False)

                print(f" ✅ Сохранено в {os.path.basename(active_part)} (всего {len(existing_data)} боев)")
            except Exception as e:
                print(f" ❌ Ошибка сохранения в part-файл: {e}")

        self.pending_fights = []

        pair_stats = FeaturePairConstraints.get_pair_stats(self.model.weights)
        return {
            "status": "trained",
            "status_text": f"✅ Обучено на {batch_size} боях",
            "accuracy_str": f"Точность: {acc_win:.1f}% (порог: {target_accuracy * 100:.1f}%)",
            "accuracy": acc_win,
            "saved": True,
            "is_best": acc_win_ratio > target_accuracy,
            "acc_win": acc_win,
            "acc_rnd": acc_rnd,
            "acc_mth": acc_mth,
            "pair_stats": pair_stats
        }

    def set_training_mode(self, enabled: bool):
        self.is_training_mode = enabled
        status = "включён" if enabled else "отключён"
        print(f"📌 Режим обучения {status}")

        if not enabled and len(self.pending_fights) > 0:
            print(f"⚠️ В буфере {len(self.pending_fights)} боёв. Обучение перед отключением...")
            return self.process_batch()

        return {"status": "mode_changed", "training_mode": enabled}

    def flush_buffer(self) -> dict:
        if len(self.pending_fights) == 0:
            return {"status": "empty", "status_text": "⚠️ Буфер пуст"}

        print(f"🔄 Принудительное обучение на {len(self.pending_fights)} боях...")
        return self.process_batch()

    def get_buffer_status(self) -> dict:
        return {
            "buffer_size": len(self.pending_fights),
            "batch_size": self.BATCH_TRAIN_SIZE,
            "is_training": self.is_training_mode,
            "fights_remaining": self.BATCH_TRAIN_SIZE - len(self.pending_fights)
        }

    def train_on_new_fight(self, fd: FightData, res: Result, orig_a: str, orig_b: str) -> dict:
        if not self.is_training_mode:
            print(" ⏸️ Режим только прогноз — обучение отключено")
            return {"status": "predict_only"}

        return self.add_fight_to_buffer(fd, res, orig_a, orig_b)

    def predict(self, fd: FightData) -> Prediction:
        odds_b = fd.matchup_odds.get("odds_b", 1.85) if fd.matchup_odds else 1.85

        safe_a = fd.a
        safe_b = fd.b

        features, _ = self.model._extract_features(safe_a, safe_b, fd.odds_a, odds_b)
        self.update_recent_features(features)

        pure_prob_a = self.model.predict_proba(features)
        dampened_prob = 0.50 + (pure_prob_a - 0.50) * ModelConstants.WP_DAMPENING

        is_stub_odds = (abs(fd.odds_a - 1.85) < 0.01 and abs(odds_b - 1.85) < 0.01)

        if is_stub_odds:
            final_prob_a = dampened_prob
        else:
            implied_prob_a = 1.0 / max(fd.odds_a, 1.01)
            delta = dampened_prob - implied_prob_a
            final_prob_a = dampened_prob - (delta * 0.25)
            final_prob_a = max(0.30, min(0.90, final_prob_a))

        if final_prob_a > 0.50:
            winner, prob, wf, lf = fd.a.name, final_prob_a, safe_a, safe_b
        else:
            winner, prob, wf, lf = fd.b.name, 1.0 - final_prob_a, safe_b, safe_a

        if wf.sub_rate > 0.35 and lf.td_def < 0.65:
            meth = FinishType.SUBMISSION
        elif wf.fin_rate > 0.75 and prob > 0.65:
            meth = FinishType.KO
        elif wf.fin_rate > 0.60 and prob > 0.55:
            meth = FinishType.TKO
        elif prob <= 0.58:
            meth = FinishType.DECISION_SPLIT
        else:
            meth = FinishType.DECISION_UNANIMOUS

        rnd = fd.rounds if meth in (FinishType.DECISION_UNANIMOUS, FinishType.DECISION_SPLIT, FinishType.DRAW) else min(
            3 if prob > 0.65 else (1 if prob > 0.75 else 2), fd.rounds)

        return Prediction(
            winner=winner,
            prob=prob,
            ci_lo=max(0.0, prob - 0.15),
            ci_hi=min(1.0, prob + 0.15),
            rnd=rnd,
            method=meth,
            odds=fd.odds_a if winner == fd.a.name else odds_b
        )