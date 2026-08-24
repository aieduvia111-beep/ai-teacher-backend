# -*- coding: utf-8 -*-
"""Adapter dla funkcji wykladniczej podstawowej - opakowuje ISTNIEJACY
kod w app/math_verify.py, na bazie wspolnego LevelAwareTierModifier
(patrz modifiers/__init__.py). Osobny plik/baseline od
math_functions_poly.py, bo funkcja wykladnicza jest wprowadzona w
liceum_3/technikum_4 (2 lata programu pozniej niz liniowa/kwadratowa-
jako-funkcja, patrz SUBJECT_SCOPE w level_config.py).

ZERO zmian w math_verify.py."""
from . import LevelAwareTierModifier
from ...math_verify import classify_exponential_function_difficulty, validate_exponential_function_difficulty
from ...level_config import EXPONENTIAL_FUNCTION_DIFFICULTY_TIERS
from ..calibration import EXPONENTIAL_FUNCTION_BASELINE_LEVEL, EXPONENTIAL_FUNCTION_MAX_SHIFT


class ExponentialFunctionModifier(LevelAwareTierModifier):
    name = "math_exponential_function"
    _classify_fn = staticmethod(classify_exponential_function_difficulty)
    _validate_fn = staticmethod(validate_exponential_function_difficulty)
    _tier_order = list(EXPONENTIAL_FUNCTION_DIFFICULTY_TIERS.keys())  # ["1", "2-3", "4-5"]
    _baseline_level = EXPONENTIAL_FUNCTION_BASELINE_LEVEL
    _max_shift = EXPONENTIAL_FUNCTION_MAX_SHIFT
    _abstain_status = "not_exponential_function"
