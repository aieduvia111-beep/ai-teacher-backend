# -*- coding: utf-8 -*-
"""Adapter dla ciagow arytmetycznych/geometrycznych - opakowuje ISTNIEJACY
kod w app/math_verify.py (classify_sequence_difficulty /
validate_sequence_difficulty), dokladnie ten sam wzorzec co
math_quadratic.py (Czesc 12 audytu: "domain-specific modifier/adapter,
nie kopiuj jego logiki do kolejnych tematow").

ZERO zmian w math_verify.py. `evaluate()` przyjmuje opcjonalny `level` -
bez niego (albo gdy przesuniecie wychodzi 0) zachowanie jest DOKLADNIE
identyczne jak wprost wywolanie validate_sequence_difficulty."""
from typing import List, Optional

from . import DomainModifier
from ...math_verify import classify_sequence_difficulty, validate_sequence_difficulty
from ...level_config import SEQUENCE_DIFFICULTY_TIERS
from ..calibration import level_adjusted_shift, SEQUENCE_BASELINE_LEVEL, SEQUENCE_MAX_SHIFT

_TIER_ORDER = list(SEQUENCE_DIFFICULTY_TIERS.keys())  # ["1", "2-3", "4-5"]

_BASE_TIER_INDICES = {
    "easy": {0}, "latwy": {0}, "łatwy": {0}, "latwa": {0}, "łatwa": {0},
    "medium": {1}, "sredni": {1}, "średni": {1}, "srednia": {1}, "średnia": {1},
    "hard": {2}, "trudny": {2}, "trudna": {2},
}


def _sequence_level_shift(level: str) -> int:
    return level_adjusted_shift(level, SEQUENCE_BASELINE_LEVEL, SEQUENCE_MAX_SHIFT)


def _level_adjusted_acceptable_tiers(difficulty_word: str, level: str):
    """Zbior akceptowalnych stringow tieru (np. {'2-3'}) dla danego slowa
    trudnosci, przesuniety wzgledem `level`. None jesli slowo trudnosci
    nierozpoznane."""
    base = _BASE_TIER_INDICES.get((difficulty_word or "").strip().lower())
    if base is None:
        return None
    shift = _sequence_level_shift(level)
    n = len(_TIER_ORDER)
    shifted = {max(0, min(n - 1, i + shift)) for i in base}
    return {_TIER_ORDER[i] for i in shifted}


class SequenceModifier(DomainModifier):
    name = "math_sequences"

    def applies(self, question_text: str, option_texts: Optional[List[str]] = None) -> bool:
        return classify_sequence_difficulty(question_text) is not None

    def evaluate(self, question_text: str, option_texts: Optional[List[str]],
                 requested_difficulty_word: Optional[str], level: Optional[str] = None) -> Optional[dict]:
        if not requested_difficulty_word:
            return None

        if not level or _sequence_level_shift(level) == 0:
            return validate_sequence_difficulty(question_text, requested_difficulty_word)

        detected_tier = classify_sequence_difficulty(question_text)
        if detected_tier is None:
            return {"status": "not_sequence"}
        # detected_tier jest pojedyncza cyfra ("1".."5") - _TIER_ORDER uzywa
        # pasm ("1","2-3","4-5"), wiec trzeba znalezc pasmo zawierajace ten tier.
        detected_band = next((b for b in _TIER_ORDER if detected_tier in b.split("-")), None)
        if detected_band is None:
            return {"status": "not_sequence"}
        acceptable = _level_adjusted_acceptable_tiers(requested_difficulty_word, level)
        if not acceptable:
            return {"status": "not_sequence"}
        requested_label = "/".join(sorted(acceptable))
        if detected_band in acceptable:
            return {"status": "ok", "detected_tier": detected_tier, "requested_tier": requested_label}
        if _TIER_ORDER.index(detected_band) < _TIER_ORDER.index(min(acceptable, key=_TIER_ORDER.index)):
            reason = (
                f"za latwe jak na poziom {level} - brak zlozonego warunku "
                f"(wykryto {detected_tier}, oczekiwano {requested_label})"
            )
        else:
            reason = (
                f"za trudne jak na poziom {level} - zbyt zlozony uklad warunkow "
                f"(wykryto {detected_tier}, oczekiwano {requested_label})"
            )
        return {"status": "fail", "reason": reason, "detected_tier": detected_tier, "requested_tier": requested_label}
