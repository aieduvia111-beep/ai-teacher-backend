# -*- coding: utf-8 -*-
"""Mapowanie score (0-100) -> easy/medium/hard, wzgledem poziomu
edukacyjnego (Czesc 11 audytu: HARD nie oznacza tego samego dla 7 klasy
i 4 LO).

ETAP 5: LEVEL_THRESHOLDS wypelnione liniowa interpolacja miedzy
najlatwiejszym (podstawowka_1) a najtrudniejszym (studia_5) poziomem -
PUNKT STARTOWY do dalszej kalibracji na realnych danych, nie ostateczne
wartosci (zaakceptowane przez usera jako takie).

## Dlaczego "rok nauki", nie pozycja w liscie 24 poziomow

Naiwne ponumerowanie 24 poziomow w kolejnosci z level_config.py
(podstawowka_1..8, liceum_1..4, technikum_1..5, matura x2, studia_1..5)
bledne umiesciloby np. technikum_1 jako "trudniejszy" niz liceum_4 -
to sa ROWNOLEGLE sciezki w tym samym wieku (liceum 4 lata, technikum 5
lat), nie sekwencja. Zamiast tego uzywamy wspolnej osi "rok nauki"
(proxy na wiek/rozwoj poznawczy), z liceum i technikum na tych samych
latach - patrz LEVEL_YEAR."""

LEVEL_YEAR = {
    "podstawowka_1": 1, "podstawowka_2": 2, "podstawowka_3": 3, "podstawowka_4": 4,
    "podstawowka_5": 5, "podstawowka_6": 6, "podstawowka_7": 7, "podstawowka_8": 8,
    "liceum_1": 9, "liceum_2": 10, "liceum_3": 11, "liceum_4": 12,
    "technikum_1": 9, "technikum_2": 10, "technikum_3": 11, "technikum_4": 12, "technikum_5": 13,
    "matura_podstawowa": 12.5, "matura_rozszerzona": 13,
    "studia_1": 14, "studia_2": 15, "studia_3": 16, "studia_4": 17, "studia_5": 18,
}
_MIN_YEAR = min(LEVEL_YEAR.values())  # podstawowka_1 = 1
_MAX_YEAR = max(LEVEL_YEAR.values())  # studia_5 = 18


def level_index(level: str):
    """Znormalizowana pozycja poziomu na osi trudnosci: 0.0 (podstawowka_1,
    najlatwiejszy) do 1.0 (studia_5, najtrudniejszy). None dla
    nierozpoznanego poziomu (w tym koszyki ogolne bez numeru jak
    "liceum" - te celowo NIE sa w LEVEL_YEAR, bo nie wiadomo ktora
    klasa - wywolujacy dostaje bezpieczny fallback na DEFAULT_THRESHOLDS/
    shift=0, tak jak dzis bez podania poziomu)."""
    year = LEVEL_YEAR.get(level)
    if year is None:
        return None
    return (year - _MIN_YEAR) / (_MAX_YEAR - _MIN_YEAR)


DEFAULT_THRESHOLDS = {
    "easy": (0, 35),
    "medium": (35, 65),
    "hard": (65, 101),  # 101, nie 100, zeby score=100 tez trafil w "hard"
}

# Granice interpolowane liniowo miedzy skrajnosciami (Czesc 1-2, zaakceptowane
# jako punkt startowy do przyszlej kalibracji na realnych danych):
#   podstawowka_1 (index=0): easy/medium=15, medium/hard=35
#       (nawet niska zlozonosc juz liczy sie jako "trudne" dla 7-latka)
#   studia_5      (index=1): easy/medium=45, medium/hard=75
#       (potrzeba realnej zlozonosci, zeby cokolwiek bylo "trudne")
_BOUNDARY1_MIN, _BOUNDARY1_MAX = 15, 45  # easy/medium
_BOUNDARY2_MIN, _BOUNDARY2_MAX = 35, 75  # medium/hard


def _thresholds_for_index(idx: float) -> dict:
    b1 = _BOUNDARY1_MIN + idx * (_BOUNDARY1_MAX - _BOUNDARY1_MIN)
    b2 = _BOUNDARY2_MIN + idx * (_BOUNDARY2_MAX - _BOUNDARY2_MIN)
    return {"easy": (0, b1), "medium": (b1, b2), "hard": (b2, 101)}


# Wypelnione dla wszystkich 24 konkretnych klas (LEVEL_YEAR) - jeden wpis
# per poziom, wyliczony raz przy imporcie modulu.
LEVEL_THRESHOLDS: dict = {lvl: _thresholds_for_index(level_index(lvl)) for lvl in LEVEL_YEAR}


def calibrate(score: int, level: str = None) -> str:
    """score: 0-100. level: klucz z level_config (np. "liceum_2") albo
    None - jesli brak kalibracji dla danego poziomu (w tym koszyki
    ogolne bez numeru), uzywa DEFAULT_THRESHOLDS (dzisiejsze, globalne
    progi - zero zmiany zachowania bez podania poziomu)."""
    thresholds = LEVEL_THRESHOLDS.get(level, DEFAULT_THRESHOLDS)
    for name, (lo, hi) in thresholds.items():
        if lo <= score < hi:
            return name
    return "hard"


# ---------------------------------------------------------------
# ETAP 5, Czesc 3: przesuniecie okna akceptowalnych tierow rownan
# kwadratowych wzgledem poziomu - patrz uzycie w
# app/difficulty/modifiers/math_quadratic.py. Punkt odniesienia to
# liceum_2, bo na tym poziomie byla dzis kalibrowana i testowana skala
# 1-10 (QUADRATIC_DIFFICULTY_TIERS w level_config.py, wszystkie realne
# testy Etapu 2/3). validate_quadratic_difficulty w math_verify.py
# ZOSTAJE NIETKNIETY - to jest calkowicie OSOBNY mechanizm, uzywany
# TYLKO gdy adapter jawnie o niego poprosi (patrz level=None -> shift 0).
# ---------------------------------------------------------------
QUADRATIC_BASELINE_LEVEL = "liceum_2"
QUADRATIC_MAX_SHIFT = 2  # liczba pasm tieru na krancach skali (podstawowka_1..studia_5)


def level_adjusted_tier_shift(level: str) -> int:
    """Zwraca calkowita liczbe pasm (tierow), o jaka przesunac okno
    akceptowalnych tierow rownan kwadratowych, wzgledem QUADRATIC_BASELINE_LEVEL.

    Dodatnia wartosc = poziom TRUDNIEJSZY niz baseline -> okno przesuwa
    sie W GORE (to, co bylo tierem "hard", teraz moze liczyc sie jako
    "easy"/"medium" dla bardziej zaawansowanego ucznia).
    Ujemna wartosc = poziom LATWIEJSZY niz baseline -> okno przesuwa sie
    W DOL (to, co bylo tierem "medium", teraz moze liczyc sie jako
    "hard" dla mlodszego ucznia).

    None/nierozpoznany poziom -> shift 0 (bezpieczny fallback - dokladnie
    dzisiejsze, globalne zachowanie)."""
    idx = level_index(level)
    if idx is None:
        return 0
    baseline_idx = level_index(QUADRATIC_BASELINE_LEVEL)
    return round((idx - baseline_idx) * QUADRATIC_MAX_SHIFT)
