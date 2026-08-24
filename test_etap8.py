# -*- coding: utf-8 -*-
"""ETAP 8: rozszerzenie Universal Difficulty Engine na funkcje (liniowa,
kwadratowa JAKO FUNKCJA, wykladnicza podstawowa) - wzorem test_etap7.py.

Wymagane (ten sam wzorzec co Etap 6/7), TRZY RAZY (raz per podtemat):
  1. testy jednostkowe klasyfikacji
  2. testy poprawnych przypadkow PASS
  3. testy przypadkow FAIL
  4. testy abstain dla nierozpoznanych zadan
  5. testy Warstwy 2 (weryfikacja sympy closed-form) - PASS/FAIL/abstain
  6. adapter (LinearFunctionModifier/QuadraticFunctionModifier/
     ExponentialFunctionModifier) - zgodnosc + level-aware shift

Plain script (bez pytest), wzorem test_etap6.py/test_etap7.py. ZERO
wywolan AI - wszystko testowalne lokalnie (zgodnie z wymogiem
oszczednosci kosztow API)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.math_verify import (
    analyze_linear_function_question, verify_linear_function_evaluate,
    analyze_linear_two_points_question, verify_linear_two_points_question,
    classify_linear_function_difficulty, validate_linear_function_difficulty,
    analyze_quadratic_function_question, verify_quadratic_function_vertex,
    classify_quadratic_function_difficulty, validate_quadratic_function_difficulty,
    analyze_exponential_function_question, verify_exponential_function_evaluate,
    verify_exponential_same_base_equation,
    classify_exponential_function_difficulty, validate_exponential_function_difficulty,
)
from app.difficulty.modifiers.math_functions_poly import LinearFunctionModifier, QuadraticFunctionModifier
from app.difficulty.modifiers.math_functions_exponential import ExponentialFunctionModifier
from app.difficulty.calibration import (
    level_adjusted_shift,
    LINEAR_FUNCTION_BASELINE_LEVEL, LINEAR_FUNCTION_MAX_SHIFT,
    QUADRATIC_FUNCTION_BASELINE_LEVEL, QUADRATIC_FUNCTION_MAX_SHIFT,
    EXPONENTIAL_FUNCTION_BASELINE_LEVEL, EXPONENTIAL_FUNCTION_MAX_SHIFT,
)

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


# =================================================================
# 8a. FUNKCJA LINIOWA
# =================================================================
print("=" * 70)
print("8a. FUNKCJA LINIOWA")
print("=" * 70)

print("--- klasyfikacja ---")
t = classify_linear_function_difficulty("Dla funkcji f(x)=2x+3, oblicz f(4).")
check("ewaluacja f(k) -> tier 1", t == "1", t)

t = classify_linear_function_difficulty("Wyznacz równanie prostej przechodzącej przez punkty (1,5) i (3,-1).")
check("rownanie przez 2 punkty -> tier 3", t == "3", t)

t = classify_linear_function_difficulty(
    "Wyznacz równanie prostej prostopadłej do prostej y=2x-3, przechodzącej przez punkt (4,1)."
)
check("prostopadla (INNY wzorzec) -> tier 3", t == "3", t)

t = classify_linear_function_difficulty("Dla jakich x funkcja f(x)=3x-6 jest rosnąca? Podaj miejsce zerowe.")
check("monotonicznosc -> tier 2", t == "2", t)

t = classify_linear_function_difficulty("Dla jakich wartości m funkcja f(x)=(m-2)x+3 jest malejąca?")
check("parametr -> tier 5", t == "5", t)

t = classify_linear_function_difficulty("Rozwiąż układ dwóch prostych: y=2x+1 oraz y=-x+4.")
check("uklad prostych (INNY wzorzec dla hard) -> tier 4", t == "4", t)

print("--- PASS/FAIL ---")
r = validate_linear_function_difficulty("Dla funkcji f(x)=2x+3, oblicz f(4).", "easy")
check("easy vs ewaluacja -> ok", r["status"] == "ok", r)

r = validate_linear_function_difficulty("Dla jakich wartości m funkcja f(x)=(m-2)x+3 jest malejąca?", "hard")
check("hard vs parametr -> ok", r["status"] == "ok", r)

r = validate_linear_function_difficulty("Rozwiąż układ dwóch prostych: y=2x+1 oraz y=-x+4.", "trudny")
check("trudny vs uklad (INNY wzorzec 'hard') -> ok", r["status"] == "ok", r)

r = validate_linear_function_difficulty("Dla funkcji f(x)=2x+3, oblicz f(4).", "hard")
check("hard vs ewaluacja -> fail (za latwe)", r["status"] == "fail" and "za latwe" in r["reason"], r)

r = validate_linear_function_difficulty("Dla jakich wartości m funkcja f(x)=(m-2)x+3 jest malejąca?", "easy")
check("easy vs parametr -> fail (za trudne)", r["status"] == "fail" and "za trudne" in r["reason"], r)

print("--- abstain ---")
t = classify_linear_function_difficulty("Kto napisał Pana Tadeusza?")
check("tresc niematematyczna -> classify=None", t is None, t)
r = validate_linear_function_difficulty("Kto napisał Pana Tadeusza?", "easy")
check("tresc niematematyczna -> validate=not_linear_function", r["status"] == "not_linear_function", r)
r = validate_linear_function_difficulty("Rozwiąż równanie x²-5x+6=0.", "easy")
check("rownanie kwadratowe (inny temat) -> not_linear_function", r["status"] == "not_linear_function", r)

print("--- Warstwa 2 ---")
r = verify_linear_function_evaluate("Dla funkcji f(x)=2x+3, oblicz f(4).", ["11", "10", "9", "8"])
check("f(4)=11: poprawna opcja -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_linear_function_evaluate("Dla funkcji f(x)=2x+3, oblicz f(4).", ["10", "9", "8", "7"])
check("f(4)=11: brak poprawnej opcji -> no_option_matches", r["status"] == "no_option_matches", r)

q2p = "Wyznacz równanie prostej przechodzącej przez punkty (1,5) i (3,-1)."
r = verify_linear_two_points_question(q2p, ["y=-3x+8", "y=2x+3", "y=-2x+7", "y=3x-2"])
check("prosta przez 2 punkty: poprawna opcja -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_linear_function_evaluate("Dla jakich wartości m funkcja f(x)=(m-2)x+3 jest malejąca?", ["1", "2", "3"])
check("parametr w f(x) -> unverifiable (abstain, nie zgadujemy)", r["status"] == "unverifiable", r)

print("--- adapter ---")
mod = LinearFunctionModifier()
q = "Dla funkcji f(x)=2x+3, oblicz f(4)."
check("adapter bez level == wywolanie bezposrednie",
      mod.evaluate(q, None, "easy", level=None) == validate_linear_function_difficulty(q, "easy"))
check("applies() zgodny z classify", mod.applies(q) == (classify_linear_function_difficulty(q) is not None))
check("shift na baseline (liceum_1) == 0",
      level_adjusted_shift(LINEAR_FUNCTION_BASELINE_LEVEL, LINEAR_FUNCTION_BASELINE_LEVEL, LINEAR_FUNCTION_MAX_SHIFT) == 0)


# =================================================================
# 8b. FUNKCJA KWADRATOWA JAKO FUNKCJA
# =================================================================
print()
print("=" * 70)
print("8b. FUNKCJA KWADRATOWA JAKO FUNKCJA")
print("=" * 70)

print("--- klasyfikacja ---")
t = classify_quadratic_function_difficulty("Funkcja f(x)=2(x-3)²+5. Podaj współrzędne wierzchołka paraboli.")
check("wierzcholek z postaci kanonicznej -> tier 1", t == "1", t)

t = classify_quadratic_function_difficulty("Funkcja f(x)=x²-4x+7. Wyznacz wierzchołek paraboli.")
check("wierzcholek z postaci ogolnej -> tier 2", t == "2", t)

t = classify_quadratic_function_difficulty(
    "Funkcja f(x)=x²-4x+7. Wyznacz wierzchołek paraboli i zbiór wartości funkcji."
)
check("wierzcholek+zbior wartosci (2 markery) -> tier 3", t == "3", t)

t = classify_quadratic_function_difficulty("Dla jakich m wierzchołek paraboli f(x)=x²-2mx+1 leży powyżej osi OX?")
check("parametr wplywajacy na wierzcholek -> tier 5", t == "5", t)

t = classify_quadratic_function_difficulty("Znajdź maksymalną wartość funkcji f(x)=-x²+4x+1.")
check("optymalizacja (INNY wzorzec dla hard) -> tier 5", t == "5", t)

t = classify_quadratic_function_difficulty("Rozwiąż równanie x²-5x+6=0.")
check("rownanie BEZ markera wlasciwosci -> None (abstain, inny modifier)", t is None, t)

print("--- PASS/FAIL ---")
r = validate_quadratic_function_difficulty("Funkcja f(x)=2(x-3)²+5. Podaj współrzędne wierzchołka paraboli.", "easy")
check("easy vs kanoniczna -> ok", r["status"] == "ok", r)

r = validate_quadratic_function_difficulty("Znajdź maksymalną wartość funkcji f(x)=-x²+4x+1.", "hard")
check("hard vs optymalizacja -> ok", r["status"] == "ok", r)

r = validate_quadratic_function_difficulty("Dla jakich m wierzchołek paraboli f(x)=x²-2mx+1 leży powyżej osi OX?", "trudna")
check("trudna vs parametr (INNY wzorzec 'hard') -> ok", r["status"] == "ok", r)

r = validate_quadratic_function_difficulty("Funkcja f(x)=2(x-3)²+5. Podaj współrzędne wierzchołka paraboli.", "hard")
check("hard vs kanoniczna -> fail (za latwe)", r["status"] == "fail" and "za latwe" in r["reason"], r)

print("--- abstain ---")
r = validate_quadratic_function_difficulty("Kto napisał Pana Tadeusza?", "easy")
check("tresc niematematyczna -> not_quadratic_function", r["status"] == "not_quadratic_function", r)
r = validate_quadratic_function_difficulty("Rozwiąż równanie x²-5x+6=0.", "easy")
check("rownanie kwadratowe (bez markera) -> not_quadratic_function", r["status"] == "not_quadratic_function", r)

print("--- Warstwa 2 ---")
q_vertex = "Funkcja f(x)=x²-4x+7. Wyznacz wierzchołek paraboli."
r = verify_quadratic_function_vertex(q_vertex, ["(2,3)", "(2,4)", "(4,7)", "(-2,3)"])
check("wierzcholek (2,3): poprawna opcja -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_quadratic_function_vertex(q_vertex, ["(1,1)", "(2,4)", "(4,7)", "(-2,3)"])
check("wierzcholek (2,3): brak poprawnej opcji -> no_option_matches", r["status"] == "no_option_matches", r)

r = verify_quadratic_function_vertex(
    "Dla jakich m wierzchołek paraboli f(x)=x²-2mx+1 leży powyżej osi OX?", ["(1,1)", "(2,4)"]
)
check("parametr w f(x) -> unverifiable (abstain)", r["status"] == "unverifiable", r)

print("--- adapter ---")
mod2 = QuadraticFunctionModifier()
q2 = "Funkcja f(x)=2(x-3)²+5. Podaj współrzędne wierzchołka paraboli."
check("adapter bez level == wywolanie bezposrednie",
      mod2.evaluate(q2, None, "easy", level=None) == validate_quadratic_function_difficulty(q2, "easy"))
check("applies() zgodny z classify", mod2.applies(q2) == (classify_quadratic_function_difficulty(q2) is not None))


# =================================================================
# 8c. FUNKCJA WYKLADNICZA PODSTAWOWA
# =================================================================
print()
print("=" * 70)
print("8c. FUNKCJA WYKLADNICZA PODSTAWOWA")
print("=" * 70)

print("--- klasyfikacja ---")
t = classify_exponential_function_difficulty("Funkcja f(x)=2^x. Oblicz f(3).")
check("ewaluacja f(k) -> tier 1", t == "1", t)

t = classify_exponential_function_difficulty("Rozwiąż równanie 2^(x+1) = 8.")
check("rownanie przy tej samej podstawie -> tier 3", t == "3", t)

t = classify_exponential_function_difficulty("Naszkicuj przesunięcie wykresu funkcji f(x)=2^x o 3 w górę.")
check("przesuniecie wykresu (INNY wzorzec medium) -> tier 2", t == "2", t)

t = classify_exponential_function_difficulty("Rozwiąż nierówność 4^x-3*2^x-4 ≤ 0, podstawiając t=2^x.")
check("podstawienie/nierownosc -> tier 5", t == "5", t)

t = classify_exponential_function_difficulty("Dla jakich wartości parametru a równanie a^x = 8 ma rozwiązanie?")
check("parametryzowana podstawa (INNY wzorzec hard) -> tier 5", t == "5", t)

print("--- PASS/FAIL ---")
r = validate_exponential_function_difficulty("Funkcja f(x)=2^x. Oblicz f(3).", "easy")
check("easy vs ewaluacja -> ok", r["status"] == "ok", r)

r = validate_exponential_function_difficulty("Rozwiąż nierówność 4^x-3*2^x-4 ≤ 0, podstawiając t=2^x.", "hard")
check("hard vs podstawienie -> ok", r["status"] == "ok", r)

r = validate_exponential_function_difficulty("Dla jakich wartości parametru a równanie a^x = 8 ma rozwiązanie?", "trudny")
check("trudny vs parametr (INNY wzorzec 'hard') -> ok", r["status"] == "ok", r)

r = validate_exponential_function_difficulty("Funkcja f(x)=2^x. Oblicz f(3).", "hard")
check("hard vs ewaluacja -> fail (za latwe)", r["status"] == "fail" and "za latwe" in r["reason"], r)

print("--- abstain ---")
r = validate_exponential_function_difficulty("Kto napisał Pana Tadeusza?", "easy")
check("tresc niematematyczna -> not_exponential_function", r["status"] == "not_exponential_function", r)
r = validate_exponential_function_difficulty("Rozwiąż równanie x²-5x+6=0.", "easy")
check("rownanie kwadratowe (inny temat) -> not_exponential_function", r["status"] == "not_exponential_function", r)

print("--- Warstwa 2 ---")
r = verify_exponential_function_evaluate("Funkcja f(x)=2^x. Oblicz f(3).", ["8", "6", "9", "16"])
check("f(3)=8: poprawna opcja -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_exponential_same_base_equation("Rozwiąż równanie 2^(x+1) = 8.", ["2", "3", "4", "1"])
check("2^(x+1)=8 -> x=2, poprawna opcja -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_exponential_same_base_equation("Rozwiąż nierówność 4^x-3*2^x-4 ≤ 0.", ["0", "1", "2"])
check("nierownosc -> unverifiable (abstain, poza zakresem Warstwy 2)", r["status"] == "unverifiable", r)

print("--- adapter ---")
mod3 = ExponentialFunctionModifier()
q3 = "Funkcja f(x)=2^x. Oblicz f(3)."
check("adapter bez level == wywolanie bezposrednie",
      mod3.evaluate(q3, None, "easy", level=None) == validate_exponential_function_difficulty(q3, "easy"))
check("applies() zgodny z classify", mod3.applies(q3) == (classify_exponential_function_difficulty(q3) is not None))
check("baseline liceum_3 != baseline liceum_1 (osobne kalibracje)",
      EXPONENTIAL_FUNCTION_BASELINE_LEVEL != LINEAR_FUNCTION_BASELINE_LEVEL)


print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
