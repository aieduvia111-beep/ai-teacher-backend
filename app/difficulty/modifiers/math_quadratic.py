# -*- coding: utf-8 -*-
"""Adapter dla rownan kwadratowych - opakowuje ISTNIEJACY, juz dzis
dzialajacy i przetestowany kod w app/math_verify.py
(classify_quadratic_difficulty / validate_quadratic_difficulty).

ZERO zmian w math_verify.py. Tam, gdzie to mozliwe, ZERO wlasnej logiki
klasyfikacji trudnosci - to jest CELOWO cienki adapter (proof of concept
z audytu, Czesc 12: "Nie usuwaj go. Potraktuj go jako domain-specific
modifier/adapter. Nie kopiuj jego logiki do kolejnych tematow").

ETAP 5, Czesc 3: `evaluate()` przyjmuje teraz opcjonalny `level`. BEZ
`level` (albo gdy przesuniecie dla danego poziomu wychodzi 0) zachowanie
jest DOKLADNIE identyczne jak przed Etapem 5 - wprost wywoluje
validate_quadratic_difficulty. Z `level` INNYM niz baseline
(QUADRATIC_BASELINE_LEVEL w calibration.py) okno akceptowalnych tierow
jest przesuniete wzgledem poziomu ucznia (patrz
calibration.level_adjusted_tier_shift) - detekcja tieru
(classify_quadratic_difficulty) zostaje NIETKNIETA, przesuwa sie TYLKO
to, ktory tier liczy sie jako "pasujacy" do zadanej trudnosci."""
from typing import List, Optional

from . import DomainModifier
from ...math_verify import classify_quadratic_difficulty, validate_quadratic_difficulty
from ...level_config import QUADRATIC_DIFFICULTY_TIERS
from ..calibration import level_adjusted_tier_shift

_TIER_ORDER = list(QUADRATIC_DIFFICULTY_TIERS.keys())  # ["1-2","3-4","5-6","7-8","9-10"]

# Bazowe (poziom-agnostyczne) indeksy tierow dla kazdego slowa trudnosci -
# logiczny odpowiednik math_verify._QUADRATIC_ACCEPTABLE_TIERS (prywatna
# stala, NIE importowana stamtad) wyrazony jako indeksy w _TIER_ORDER,
# potrzebny do przesuwania okna wzgledem poziomu. Te same slowa/warianty
# co w math_verify.py.
_BASE_TIER_INDICES = {
    "easy": {0, 1}, "latwy": {0, 1}, "łatwy": {0, 1}, "latwa": {0, 1}, "łatwa": {0, 1},
    "medium": {2}, "sredni": {2}, "średni": {2}, "srednia": {2}, "średnia": {2},
    "hard": {3, 4}, "trudny": {3, 4}, "trudna": {3, 4},
}


def _level_adjusted_acceptable_tiers(difficulty_word: str, level: str):
    """Zbior akceptowalnych stringow tieru (np. {'5-6'}) dla danego slowa
    trudnosci, przesuniety wzgledem `level`. None jesli slowo trudnosci
    nierozpoznane."""
    base = _BASE_TIER_INDICES.get((difficulty_word or "").strip().lower())
    if base is None:
        return None
    shift = level_adjusted_tier_shift(level)
    n = len(_TIER_ORDER)
    shifted = {max(0, min(n - 1, i + shift)) for i in base}
    return {_TIER_ORDER[i] for i in shifted}


class QuadraticEquationModifier(DomainModifier):
    name = "math_quadratic"

    def applies(self, question_text: str, option_texts: Optional[List[str]] = None) -> bool:
        return classify_quadratic_difficulty(question_text, option_texts=option_texts) is not None

    def evaluate(self, question_text: str, option_texts: Optional[List[str]],
                 requested_difficulty_word: Optional[str], level: Optional[str] = None) -> Optional[dict]:
        if not requested_difficulty_word:
            return None

        if not level or level_adjusted_tier_shift(level) == 0:
            # ETAP 5: bez poziomu (albo poziom rownowazny baseline'owi,
            # np. sam liceum_2) - DOKLADNIE dzisiejsza sciezka, zero
            # zmiany zachowania.
            return validate_quadratic_difficulty(
                question_text, requested_difficulty_word, option_texts=option_texts
            )

        detected_tier = classify_quadratic_difficulty(question_text, option_texts=option_texts)
        if detected_tier is None:
            return {"status": "not_quadratic"}
        acceptable = _level_adjusted_acceptable_tiers(requested_difficulty_word, level)
        if not acceptable:
            return {"status": "not_quadratic"}
        requested_label = "/".join(sorted(acceptable))
        if detected_tier in acceptable:
            return {"status": "ok", "detected_tier": detected_tier, "requested_tier": requested_label}
        if _TIER_ORDER.index(detected_tier) < _TIER_ORDER.index(min(acceptable, key=_TIER_ORDER.index)):
            reason = (
                f"za latwe jak na poziom {level} - brak parametru/zlozonego warunku "
                f"(wykryto {detected_tier}, oczekiwano {requested_label})"
            )
        else:
            reason = (
                f"za trudne jak na poziom {level} - zbyt zlozona analiza jak na ta trudnosc "
                f"(wykryto {detected_tier}, oczekiwano {requested_label})"
            )
        return {"status": "fail", "reason": reason, "detected_tier": detected_tier, "requested_tier": requested_label}
