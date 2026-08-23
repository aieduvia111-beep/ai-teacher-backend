# -*- coding: utf-8 -*-
"""DifficultyAnalyzer - glowny wejsciowy punkt Universal Difficulty Engine
(Etap 1). Orkiestruje: uniwersalna ekstrakcja cech -> uniwersalny scoring
-> (jesli pasuje) autorytatywny domain modifier -> kalibracja wzgledem
poziomu.

CELOWO NIEPODLACZONY do prawdziwego pipeline'u Quiz/Sprawdzian - patrz
test_difficulty_engine.py dla testow w izolacji. Podlaczenie do
openai_exam.py/exam_pdf_generator.py to kolejny, OSOBNY etap, po
zaakceptowaniu wynikow tego."""
from typing import List, Optional

from .calibration import calibrate
from .features import extract_features
from .scoring import DifficultyBreakdown, DifficultyConfidence, DifficultyScore, compute_score
from .modifiers import DEFAULT_MODIFIERS


class DifficultyAnalyzer:
    def __init__(self, modifiers=None):
        self.modifiers = modifiers if modifiers is not None else DEFAULT_MODIFIERS

    def analyze(
        self,
        question_text: str,
        option_texts: Optional[List[str]] = None,
        explanation_text: Optional[str] = None,
        requested_difficulty_word: Optional[str] = None,
        level: Optional[str] = None,
    ) -> DifficultyScore:
        breakdown, has_formulas = extract_features(question_text, option_texts, explanation_text)
        universal_score = compute_score(breakdown)

        domain_name = None
        domain_verdict = None
        domain_detail = None
        matched_modifier = None
        for modifier in self.modifiers:
            try:
                if modifier.applies(question_text, option_texts):
                    matched_modifier = modifier
                    break
            except Exception:
                # Modifier nie powinien nigdy wywalic calej analizy -
                # traktujemy to jak "nie pasuje", zostaje uniwersalny wynik.
                continue

        if matched_modifier is not None:
            domain_name = matched_modifier.name
            try:
                result = matched_modifier.evaluate(question_text, option_texts, requested_difficulty_word, level=level)
            except Exception as e:
                result = None
                domain_detail = {"error": str(e)}
            if result is not None:
                domain_verdict = result.get("status")
                domain_detail = result

        confidence = _compute_confidence(breakdown, has_formulas, matched_modifier is not None, bool(explanation_text))
        level_label = calibrate(universal_score, level)

        return DifficultyScore(
            score=universal_score,
            level=level_label,
            breakdown=breakdown,
            confidence=confidence,
            domain=domain_name,
            domain_verdict=domain_verdict,
            domain_detail=domain_detail,
            raw_features={
                "has_formulas": has_formulas,
                "contributions": _contributions_as_plain_dict(breakdown),
            },
        )


def _contributions_as_plain_dict(breakdown: DifficultyBreakdown) -> dict:
    from .scoring import feature_contributions
    return {
        name: {"normalized": round(norm, 3), "weight": weight, "contribution": round(contrib, 2)}
        for name, (norm, weight, contrib) in feature_contributions(breakdown).items()
    }


def _compute_confidence(breakdown: DifficultyBreakdown, has_formulas: bool,
                         domain_applied: bool, has_explanation: bool) -> DifficultyConfidence:
    if domain_applied:
        return DifficultyConfidence(1.0, "domain modifier zastosowany - wynik autorytatywny, nie uniwersalny heurystyczny")
    if not has_formulas and breakdown.methods == 0:
        return DifficultyConfidence(0.2, "brak rozpoznanych wzorow/metod - prawdopodobnie zadanie spoza domen matematycznych obslugiwanych dzis przez ten silnik")
    base = 0.6
    reason = "cechy uniwersalne (regex/heurystyki), brak specjalistycznego adaptera dla tej domeny"
    if has_explanation:
        base += 0.2
        reason += " - steps liczone z faktycznego wyjasnienia"
    else:
        reason += " - steps przyblizone z liczby wzorow w tresci (brak wyjasnienia)"
    return DifficultyConfidence(round(min(base, 0.9), 2), reason)
