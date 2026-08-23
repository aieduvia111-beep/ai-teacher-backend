# -*- coding: utf-8 -*-
"""Struktury danych i algorytm scoringu Universal Difficulty Engine.

ETAP 1 (patrz rozmowa z userem) - TYLKO infrastruktura + adapter dla
rownan kwadratowych. Ten modul jest CELOWO niepodlaczony do prawdziwego
pipeline'u Quiz/Sprawdzian - testowany w izolacji, zanim cokolwiek zostanie
podlaczone (openai_exam.py, exam_pdf_generator.py NIE sa dzis dotykane).

Algorytm scoringu jest ADDYTYWNY: kazda cecha ma wlasna funkcje normalizujaca
(0.0-1.0) i wlasna wage - suma wag = 100, wiec finalny score jest z definicji
w zakresie 0-100. Wagi ponizej to PUNKT STARTOWY do kalibracji na realnych
danych (patrz audyt "Czesc 8" w rozmowie z userem) - NIE ostateczne wartosci.
Kazda cecha jest osobno testowalna (patrz test_difficulty_engine.py)."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DifficultyBreakdown:
    """Uniwersalne cechy wygenerowanego zadania, wspolne dla wszystkich
    tematow (patrz Czesc 7 audytu). Domain modifiery (np. math_quadratic)
    moga dostarczyc dokladniejsza analize dla SWOJEJ domeny - to pole
    zostaje jednak zawsze wypelnione heurystyka uniwersalna, tak zeby
    kazde zadanie (nawet spoza obslugiwanych domen) mialo jakis breakdown."""
    steps: int = 0
    operations: int = 0
    conditions: int = 0
    methods: int = 0
    cases: int = 0
    has_parameter: bool = False
    abstraction_level: int = 0  # 0=liczbowe, 1=parametr, 2=dowod/uogolnienie
    cross_topic: bool = False


@dataclass
class DifficultyConfidence:
    """Jak bardzo silnik ufa wlasnemu wynikowi. NISKA pewnosc NIE oznacza
    automatycznego odrzucenia zadania (patrz Czesc 10 audytu) - to
    informacja dla wywolujacego kodu, nie werdykt."""
    value: float  # 0.0-1.0
    reason: str


@dataclass
class DifficultyScore:
    """Finalny wynik analizy jednego zadania."""
    score: int  # 0-100, z uniwersalnego scoringu (patrz compute_score)
    level: str  # "easy"/"medium"/"hard" po kalibracji wzgledem poziomu
    breakdown: DifficultyBreakdown
    confidence: DifficultyConfidence
    # Wypelnione TYLKO gdy zadanie pasuje do jakiegos domain modifiera
    # (patrz modifiers/) I podano requested_difficulty_word - domain_verdict
    # to WYNIK AUTORYTATYWNY z istniejacej, sprawdzonej walidacji domenowej
    # (np. validate_quadratic_difficulty), NIE z uniwersalnego scoringu.
    # Przyszla integracja z pipeline'em (Etap 2+) ma respektowac
    # domain_verdict, jesli jest ustawiony, zamiast samego `level`.
    domain: Optional[str] = None
    domain_verdict: Optional[str] = None  # "ok" / "fail" / None
    domain_detail: Optional[dict] = None
    raw_features: dict = field(default_factory=dict)


# ---------------------------------------------------------------
# Algorytm scoringu - kazda cecha: (normalizacja 0-1, waga). Suma wag = 100.
# ---------------------------------------------------------------
def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# (nazwa, waga, funkcja normalizujaca breakdown->0..1, uzasadnienie)
_FEATURE_SPECS = (
    ("steps", 20, lambda b: _clamp01(b.steps / 6),
     "powyzej 6 krokow zadanie jest subiektywnie trudne niezaleznie od reszty"),
    ("operations", 10, lambda b: _clamp01(b.operations / 10),
     "liczba operacji koreluje z czasem rozwiazania, ale slabiej niz kroki"),
    ("conditions", 20, lambda b: _clamp01(b.conditions / 3),
     "powyzej 3 warunkow to zlozona analiza logiczna"),
    ("methods", 20, lambda b: _clamp01((b.methods - 1) / 2) if b.methods > 0 else 0.0,
     "1 metoda = baseline, kazda dodatkowa metoda to realny skok trudnosci"),
    ("cases", 15, lambda b: _clamp01(b.cases / 2),
     "rozbicie na przypadki to potwierdzony wyznacznik trudnosci (patrz QUADRATIC_DIFFICULTY_TIERS 9-10)"),
    ("has_parameter", 10, lambda b: 1.0 if b.has_parameter else 0.0,
     "najsilniejszy pojedynczy sygnal - potwierdzone przez caly istniejacy system rownan kwadratowych"),
    ("abstraction_level", 5, lambda b: _clamp01(b.abstraction_level / 2),
     "dowody/uogolnienia sa jakosciowo innym poziomem"),
)

assert sum(w for _, w, _, _ in _FEATURE_SPECS) == 100


def feature_contributions(breakdown: DifficultyBreakdown) -> dict:
    """Zwraca wklad KAZDEJ cechy do finalnego score (do debugowania/testow) -
    {nazwa: (normalized_0_1, waga, wklad_punktowy)}."""
    out = {}
    for name, weight, norm_fn, _reason in _FEATURE_SPECS:
        normalized = norm_fn(breakdown)
        out[name] = (normalized, weight, normalized * weight)
    return out


def compute_score(breakdown: DifficultyBreakdown) -> int:
    """Sumuje wklady wszystkich cech -> int 0-100."""
    total = sum(contrib for _, _, contrib in feature_contributions(breakdown).values())
    return round(_clamp01(total / 100) * 100)
