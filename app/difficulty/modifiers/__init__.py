# -*- coding: utf-8 -*-
"""Interfejs domain modifierow (Czesc 13 audytu) - uniwersalny scoring nie
wystarcza wszedzie, wiec konkretne domeny moga dostarczyc dokladniejsza,
AUTORYTATYWNA analize, ktora nadpisuje uniwersalny wynik.

Kazdy modifier implementuje dwie metody:
  applies(question_text, option_texts) -> bool
      Czy ten modifier rozpoznaje ten typ zadania (np. rownanie kwadratowe
      w tresci LUB w opcjach).
  evaluate(question_text, option_texts, requested_difficulty_word) -> dict | None
      Zwraca dict {"status": "ok"/"fail"/..., ...} - identyczny ksztalt do
      tego, co juz zwraca np. validate_quadratic_difficulty w
      math_verify.py. None jesli nie da sie ocenic (np. brak
      requested_difficulty_word).

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
                 requested_difficulty_word: Optional[str]) -> Optional[dict]:
        ...


from .math_quadratic import QuadraticEquationModifier

DEFAULT_MODIFIERS = [QuadraticEquationModifier()]
