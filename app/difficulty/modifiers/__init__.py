# -*- coding: utf-8 -*-
"""Interfejs domain modifierow (Czesc 13 audytu) - uniwersalny scoring nie
wystarcza wszedzie, wiec konkretne domeny moga dostarczyc dokladniejsza,
AUTORYTATYWNA analize, ktora nadpisuje uniwersalny wynik.

Kazdy modifier implementuje dwie metody:
  applies(question_text, option_texts) -> bool
      Czy ten modifier rozpoznaje ten typ zadania (np. rownanie kwadratowe
      w tresci LUB w opcjach).
  evaluate(question_text, option_texts, requested_difficulty_word, level=None) -> dict | None
      Zwraca dict {"status": "ok"/"fail"/..., ...} - identyczny ksztalt do
      tego, co juz zwraca np. validate_quadratic_difficulty w
      math_verify.py. None jesli nie da sie ocenic (np. brak
      requested_difficulty_word). `level` (ETAP 5, opcjonalny) - klucz
      poziomu edukacyjnego (np. "liceum_2") - modifier MOZE (nie musi)
      go uwzglednic przy ocenie; brak `level` = dotychczasowe,
      poziom-agnostyczne zachowanie.

WAZNE: modifiery NIE implementuja wlasnej logiki walidacji od zera -
opakowuja/wywoluja ISTNIEJACY, juz sprawdzony kod (patrz math_quadratic.py
wywolujacy math_verify.validate_quadratic_difficulty bez zadnych zmian w
nim). To jest sedno Etapu 1: jeden wspolny silnik + adaptery, nie
przepisywanie dzialajacej logiki."""
from abc import ABC, abstractmethod
from typing import List, Optional


class DomainModifier(ABC):
    name: str = "base"

    @abstractmethod
    def applies(self, question_text: str, option_texts: Optional[List[str]] = None) -> bool:
        ...

    @abstractmethod
    def evaluate(self, question_text: str, option_texts: Optional[List[str]],
                 requested_difficulty_word: Optional[str], level: Optional[str] = None) -> Optional[dict]:
        ...


class LevelAwareTierModifier(DomainModifier):
    """ETAP 8 (audyt architektury): wspolny szkielet level-aware
    evaluate() dla modifierow o skali pasm (np. '1'/'2-3'/'4-5') -
    wyodrebniony PO tym, jak SequenceModifier/TrigonometryModifier/
    LinearFunctionModifier/QuadraticFunctionModifier okazaly sie
    niemal identycznymi kopiami tej samej logiki przesuniecia
    poziomu (ten sam wzorzec co _generic_validate_difficulty w
    math_verify.py, ale na warstwie modifiera). Podklasa deklaruje
    TYLKO: name, _classify_fn, _validate_fn, _tier_order,
    _baseline_level, _max_shift, _abstain_status - zero wlasnej logiki
    przesuniecia.

    Bez `level` (albo gdy przesuniecie wychodzi 0) zachowanie jest
    DOKLADNIE identyczne jak wprost wywolanie _validate_fn."""
    _classify_fn = None
    _validate_fn = None
    _tier_order: List[str] = []
    _baseline_level: str = ""
    _max_shift: int = 0
    _abstain_status: str = "not_applicable"

    _BASE_TIER_INDICES = {
        "easy": {0}, "latwy": {0}, "łatwy": {0}, "latwa": {0}, "łatwa": {0},
        "medium": {1}, "sredni": {1}, "średni": {1}, "srednia": {1}, "średnia": {1},
        "hard": {2}, "trudny": {2}, "trudna": {2},
    }

    def applies(self, question_text: str, option_texts: Optional[List[str]] = None) -> bool:
        return self._classify_fn(question_text) is not None

    def _level_shift(self, level: Optional[str]) -> int:
        from ..calibration import level_adjusted_shift
        return level_adjusted_shift(level, self._baseline_level, self._max_shift) if level else 0

    def _band_for_tier(self, detected_tier: str):
        return next((b for b in self._tier_order if detected_tier in b.split("-")), None)

    def _level_adjusted_acceptable_tiers(self, difficulty_word: str, level: str):
        base = self._BASE_TIER_INDICES.get((difficulty_word or "").strip().lower())
        if base is None:
            return None
        shift = self._level_shift(level)
        n = len(self._tier_order)
        shifted = {max(0, min(n - 1, i + shift)) for i in base}
        return {self._tier_order[i] for i in shifted}

    def evaluate(self, question_text: str, option_texts: Optional[List[str]],
                 requested_difficulty_word: Optional[str], level: Optional[str] = None) -> Optional[dict]:
        if not requested_difficulty_word:
            return None
        if not level or self._level_shift(level) == 0:
            return self._validate_fn(question_text, requested_difficulty_word)

        detected_tier = self._classify_fn(question_text)
        if detected_tier is None:
            return {"status": self._abstain_status}
        detected_band = self._band_for_tier(detected_tier)
        if detected_band is None:
            return {"status": self._abstain_status}
        acceptable = self._level_adjusted_acceptable_tiers(requested_difficulty_word, level)
        if not acceptable:
            return {"status": self._abstain_status}
        requested_label = "/".join(sorted(acceptable))
        if detected_band in acceptable:
            return {"status": "ok", "detected_tier": detected_tier, "requested_tier": requested_label}
        if self._tier_order.index(detected_band) < self._tier_order.index(min(acceptable, key=self._tier_order.index)):
            reason = (
                f"za latwe jak na poziom {level} - brak zlozonego warunku "
                f"(wykryto {detected_tier}, oczekiwano {requested_label})"
            )
        else:
            reason = (
                f"za trudne jak na poziom {level} - zbyt zlozony warunek "
                f"(wykryto {detected_tier}, oczekiwano {requested_label})"
            )
        return {"status": "fail", "reason": reason, "detected_tier": detected_tier, "requested_tier": requested_label}


from .math_quadratic import QuadraticEquationModifier
from .math_sequences import SequenceModifier
from .math_trigonometry import TrigonometryModifier
from .math_functions_poly import LinearFunctionModifier, QuadraticFunctionModifier
from .math_functions_exponential import ExponentialFunctionModifier

DEFAULT_MODIFIERS = [
    QuadraticEquationModifier(), SequenceModifier(), TrigonometryModifier(),
    LinearFunctionModifier(), QuadraticFunctionModifier(), ExponentialFunctionModifier(),
]
