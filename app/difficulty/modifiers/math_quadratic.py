# -*- coding: utf-8 -*-
"""Adapter dla rownan kwadratowych - opakowuje ISTNIEJACY, juz dzis
dzialajacy i przetestowany kod w app/math_verify.py
(classify_quadratic_difficulty / validate_quadratic_difficulty).

ZERO zmian w math_verify.py. ZERO wlasnej logiki klasyfikacji trudnosci -
to jest CELOWO cienki adapter (proof of concept z audytu, Czesc 12: "Nie
usuwaj go. Potraktuj go jako domain-specific modifier/adapter. Nie kopiuj
jego logiki do kolejnych tematow")."""
from typing import List, Optional

from . import DomainModifier
from ...math_verify import classify_quadratic_difficulty, validate_quadratic_difficulty


class QuadraticEquationModifier(DomainModifier):
    name = "math_quadratic"

    def applies(self, question_text: str, option_texts: Optional[List[str]] = None) -> bool:
        return classify_quadratic_difficulty(question_text, option_texts=option_texts) is not None

    def evaluate(self, question_text: str, option_texts: Optional[List[str]],
                 requested_difficulty_word: Optional[str]) -> Optional[dict]:
        if not requested_difficulty_word:
            return None
        return validate_quadratic_difficulty(
            question_text, requested_difficulty_word, option_texts=option_texts
        )
