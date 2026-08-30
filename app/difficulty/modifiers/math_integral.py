# -*- coding: utf-8 -*-
"""Adapter dla calek nieoznaczonych - opakowuje ISTNIEJACY kod w
app/math_verify.py, na bazie wspolnego LevelAwareTierModifier (patrz
modifiers/__init__.py).

MAX_SHIFT=0 (patrz calibration.py) bo calki sa tematem WYLACZNIE
studiow (SUBJECT_SCOPE w level_config.py) - nie ma innego poziomu, do
ktorego przesuwac okno akceptowalnych tierow, w odroznieniu od
pozostalych domen rozlozonych na kilka lat liceum.

ZERO zmian w math_verify.py."""
from . import LevelAwareTierModifier
from ...math_verify import classify_integral_difficulty, validate_integral_difficulty
from ..calibration import INTEGRAL_BASELINE_LEVEL, INTEGRAL_MAX_SHIFT


class IntegralModifier(LevelAwareTierModifier):
    name = "math_integral"
    _classify_fn = staticmethod(classify_integral_difficulty)
    _validate_fn = staticmethod(validate_integral_difficulty)
    _tier_order = ["1", "3"]
    _baseline_level = INTEGRAL_BASELINE_LEVEL
    _max_shift = INTEGRAL_MAX_SHIFT
    _abstain_status = "not_integral"
