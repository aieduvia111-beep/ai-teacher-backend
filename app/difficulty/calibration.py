# -*- coding: utf-8 -*-
"""Mapowanie score (0-100) -> easy/medium/hard, wzgledem poziomu
edukacyjnego (Czesc 11 audytu: HARD nie oznacza tego samego dla 7 klasy
i 4 LO).

ETAP 1: LEVEL_THRESHOLDS jest CELOWO puste - nie zgadujemy progow per
poziom bez danych (audyt, Czesc 11: "Nie hardcode'uj tych progow bez
analizy"). Kalibracja per-poziom to Etap 3, po zebraniu realnych score'ow
z produkcji. Na razie kazdy poziom dostaje ten sam DEFAULT_THRESHOLDS -
funkcjonalnie identyczne globalnym progom uzywanym dzis w
math_verify._QUADRATIC_ACCEPTABLE_TIERS (choc na innej skali)."""

DEFAULT_THRESHOLDS = {
    "easy": (0, 35),
    "medium": (35, 65),
    "hard": (65, 101),  # 101, nie 100, zeby score=100 tez trafil w "hard"
}

# Wypelniane w Etapie 3 kalibracji - np. LEVEL_THRESHOLDS["liceum_2"] = {...}
LEVEL_THRESHOLDS: dict = {}


def calibrate(score: int, level: str = None) -> str:
    """score: 0-100. level: klucz z level_config (np. "liceum_2") albo
    None - jesli brak kalibracji dla danego poziomu, uzywa DEFAULT_THRESHOLDS."""
    thresholds = LEVEL_THRESHOLDS.get(level, DEFAULT_THRESHOLDS)
    for name, (lo, hi) in thresholds.items():
        if lo <= score < hi:
            return name
    return "hard"
