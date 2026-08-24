# -*- coding: utf-8 -*-
"""Adaptery dla funkcji liniowej i funkcji kwadratowej JAKO FUNKCJI (nie
rownania - patrz math_quadratic.py dla tamtej strony) - opakowuja
ISTNIEJACY kod w app/math_verify.py, dokladnie ten sam wzorzec co
math_sequences.py/math_trigonometry.py, na bazie wspolnego
LevelAwareTierModifier (patrz modifiers/__init__.py).

DWA modifiery w jednym pliku (nie jeden), bo to dwa NIEZALEZNE
klasyfikatory (classify_linear_function_difficulty /
classify_quadratic_function_difficulty) - dziela ten sam plik i baseline
(oba wprowadzone w liceum_1/technikum_1, patrz SUBJECT_SCOPE), ale kazdy
ma wlasna applies()/evaluate() (jeden modifier nie zgaduje za drugi).

ZERO zmian w math_verify.py."""
from . import LevelAwareTierModifier
from ...math_verify import (
    classify_linear_function_difficulty, validate_linear_function_difficulty,
    classify_quadratic_function_difficulty, validate_quadratic_function_difficulty,
)
from ...level_config import LINEAR_FUNCTION_DIFFICULTY_TIERS, QUADRATIC_FUNCTION_DIFFICULTY_TIERS
from ..calibration import (
    LINEAR_FUNCTION_BASELINE_LEVEL, LINEAR_FUNCTION_MAX_SHIFT,
    QUADRATIC_FUNCTION_BASELINE_LEVEL, QUADRATIC_FUNCTION_MAX_SHIFT,
)


class LinearFunctionModifier(LevelAwareTierModifier):
    name = "math_linear_function"
    _classify_fn = staticmethod(classify_linear_function_difficulty)
    _validate_fn = staticmethod(validate_linear_function_difficulty)
    _tier_order = list(LINEAR_FUNCTION_DIFFICULTY_TIERS.keys())  # ["1", "2-3", "4-5"]
    _baseline_level = LINEAR_FUNCTION_BASELINE_LEVEL
    _max_shift = LINEAR_FUNCTION_MAX_SHIFT
    _abstain_status = "not_linear_function"


class QuadraticFunctionModifier(LevelAwareTierModifier):
    name = "math_quadratic_function"
    _classify_fn = staticmethod(classify_quadratic_function_difficulty)
    _validate_fn = staticmethod(validate_quadratic_function_difficulty)
    _tier_order = list(QUADRATIC_FUNCTION_DIFFICULTY_TIERS.keys())  # ["1", "2-3", "4-5"]
    _baseline_level = QUADRATIC_FUNCTION_BASELINE_LEVEL
    _max_shift = QUADRATIC_FUNCTION_MAX_SHIFT
    _abstain_status = "not_quadratic_function"
