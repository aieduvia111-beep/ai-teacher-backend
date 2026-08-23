# -*- coding: utf-8 -*-
"""Universal Difficulty Engine (Etap 1: silnik + adapter dla rownan
kwadratowych, NIEPODLACZONY do prawdziwego pipeline'u Quiz/Sprawdzian).

Publiczne API:
    from app.difficulty import DifficultyAnalyzer, DifficultyScore

    analyzer = DifficultyAnalyzer()
    result = analyzer.analyze(question_text, option_texts=[...],
                               requested_difficulty_word="medium",
                               level="liceum_2")
    result.score        # 0-100
    result.level         # "easy"/"medium"/"hard"
    result.breakdown     # DifficultyBreakdown
    result.confidence    # DifficultyConfidence
    result.domain_verdict  # "ok"/"fail"/None - autorytatywny werdykt
                            # domain modifiera (np. rownania kwadratowe),
                            # gdy dostepny, ma pierwszenstwo nad `level`.
"""
from .analyzer import DifficultyAnalyzer
from .scoring import DifficultyBreakdown, DifficultyConfidence, DifficultyScore

__all__ = [
    "DifficultyAnalyzer",
    "DifficultyScore",
    "DifficultyBreakdown",
    "DifficultyConfidence",
]
