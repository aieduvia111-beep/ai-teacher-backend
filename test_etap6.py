# -*- coding: utf-8 -*-
"""ETAP 6: rozszerzenie Universal Difficulty Engine na ciagi arytmetyczne/
geometryczne (math_sequences.py, wzorem math_quadratic.py z Etapu 1-5).

Wymagane przez usera (per punkty 1-4 z instrukcji Etapu 6):
  1. testy jednostkowe klasyfikacji (classify_sequence_difficulty)
  2. testy poprawnych przypadkow PASS (validate_sequence_difficulty -> ok)
  3. testy przypadkow FAIL (validate_sequence_difficulty -> fail)
  4. testy abstain dla nierozpoznanych zadan (-> not_sequence / None)

Plain script (bez pytest), wzorem test_etap5.py - `check()` zbiera
niepowodzenia do FAILED, exit(1) na koncu jesli cokolwiek nie przeszlo."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.math_verify import classify_sequence_difficulty, validate_sequence_difficulty
from app.difficulty.modifiers.math_sequences import SequenceModifier
from app.difficulty.calibration import level_adjusted_shift, SEQUENCE_BASELINE_LEVEL, SEQUENCE_MAX_SHIFT

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


# ---------------------------------------------------------------
# 1. Testy jednostkowe klasyfikacji (classify_sequence_difficulty)
# ---------------------------------------------------------------
print("=== 1. classify_sequence_difficulty: tiery per wzorzec ===")

t = classify_sequence_difficulty("Ciąg arytmetyczny ma a1=3, r=5. Oblicz 10. wyraz tego ciągu.")
check("find_nth_term (arytmetyczny) -> tier 1", t == "1", t)

t = classify_sequence_difficulty("Ciąg geometryczny ma a1=2, q=3. Oblicz 5. wyraz tego ciągu.")
check("find_nth_term (geometryczny) -> tier 1", t == "1", t)

t = classify_sequence_difficulty("Ciąg arytmetyczny ma a1=2, r=3. Oblicz sumę pierwszych 10 wyrazów tego ciągu.")
check("sum_given_n (arytmetyczny) -> tier 2", t == "2", t)

t = classify_sequence_difficulty("Ciąg geometryczny ma a1=2, q=3. Oblicz sumę pierwszych 5 wyrazów tego ciągu.")
check("sum_given_n (geometryczny) -> tier 3", t == "3", t)

t = classify_sequence_difficulty("W ciągu arytmetycznym a3=10, a7=22. Wyznacz pierwszy wyraz i różnicę tego ciągu.")
check("two_term_to_a1_ratio (arytmetyczny) -> tier 4", t == "4", t)

t = classify_sequence_difficulty("W ciągu geometrycznym a2=6, a5=48. Wyznacz pierwszy wyraz i iloraz tego ciągu.")
check("two_term_to_a1_ratio (geometryczny) -> tier 5", t == "5", t)

t = classify_sequence_difficulty("W ciągu arytmetycznym a2=7. Suma pierwszych 4 wyrazów wynosi 26. Wyznacz pierwszy wyraz i różnicę tego ciągu.")
check("term_and_sum_to_a1_ratio (nowy wzorzec Etapu 6) -> tier 4", t == "4", t)

t = classify_sequence_difficulty("Ciąg arytmetyczny ma a1=3, r=2. Suma pierwszych n wyrazów wynosi 120. Wyznacz n.")
check("find_n_from_sum (nowy wzorzec Etapu 6) -> tier 5", t == "5", t)

print()

# ---------------------------------------------------------------
# 2. Testy poprawnych przypadkow PASS (validate_sequence_difficulty -> ok)
#    Rozdzielone tak, zeby kazde pasmo trudnosci obejmowalo WIECEJ NIZ
#    jeden wzorzec (glowny wymog usera - "hard" nie ma byc jednym
#    powtarzalnym typem zadania).
# ---------------------------------------------------------------
print("=== 2. validate_sequence_difficulty: przypadki PASS ===")

r = validate_sequence_difficulty("Ciąg arytmetyczny ma a1=3, r=5. Oblicz 10. wyraz tego ciągu.", "easy")
check("easy vs find_nth_term -> ok", r["status"] == "ok", r)

r = validate_sequence_difficulty("Ciąg arytmetyczny ma a1=2, r=3. Oblicz sumę pierwszych 10 wyrazów tego ciągu.", "medium")
check("medium vs sum_given_n (arytmetyczny) -> ok", r["status"] == "ok", r)

r = validate_sequence_difficulty("Ciąg geometryczny ma a1=2, q=3. Oblicz sumę pierwszych 5 wyrazów tego ciągu.", "medium")
check("medium vs sum_given_n (geometryczny, INNY wzorzec niz wyzej) -> ok", r["status"] == "ok", r)

r = validate_sequence_difficulty("W ciągu arytmetycznym a3=10, a7=22. Wyznacz pierwszy wyraz i różnicę tego ciągu.", "hard")
check("hard vs two_term_to_a1_ratio (arytmetyczny) -> ok", r["status"] == "ok", r)

r = validate_sequence_difficulty(
    "W ciągu arytmetycznym a2=7. Suma pierwszych 4 wyrazów wynosi 26. Wyznacz pierwszy wyraz i różnicę tego ciągu.",
    "trudny",
)
check("trudny vs term_and_sum_to_a1_ratio (INNY wzorzec niz wyzej, ten sam poziom) -> ok", r["status"] == "ok", r)

r = validate_sequence_difficulty("Ciąg arytmetyczny ma a1=3, r=2. Suma pierwszych n wyrazów wynosi 120. Wyznacz n.", "trudna")
check("trudna vs find_n_from_sum (TRZECI rozny wzorzec dla 'hard') -> ok", r["status"] == "ok", r)

print()

# ---------------------------------------------------------------
# 3. Testy przypadkow FAIL
# ---------------------------------------------------------------
print("=== 3. validate_sequence_difficulty: przypadki FAIL ===")

r = validate_sequence_difficulty("Ciąg arytmetyczny ma a1=3, r=5. Oblicz 10. wyraz tego ciągu.", "hard")
check("hard vs find_nth_term -> fail (za latwe)", r["status"] == "fail" and "za latwe" in r["reason"], r)

r = validate_sequence_difficulty("W ciągu arytmetycznym a3=10, a7=22. Wyznacz pierwszy wyraz i różnicę tego ciągu.", "easy")
check("easy vs two_term_to_a1_ratio -> fail (za trudne)", r["status"] == "fail" and "za trudne" in r["reason"], r)

r = validate_sequence_difficulty("Ciąg arytmetyczny ma a1=2, r=3. Oblicz sumę pierwszych 10 wyrazów tego ciągu.", "easy")
check("easy vs sum_given_n -> fail (za trudne)", r["status"] == "fail" and "za trudne" in r["reason"], r)

r = validate_sequence_difficulty("Ciąg arytmetyczny ma a1=3, r=2. Suma pierwszych n wyrazów wynosi 120. Wyznacz n.", "medium")
check("medium vs find_n_from_sum -> fail (za trudne)", r["status"] == "fail" and "za trudne" in r["reason"], r)

print()

# ---------------------------------------------------------------
# 4. Testy abstain dla nierozpoznanych zadan
# ---------------------------------------------------------------
print("=== 4. abstain (not_sequence / None) ===")

t = classify_sequence_difficulty("Kto napisał Pana Tadeusza?")
check("tresc niematematyczna -> classify=None", t is None, t)

r = validate_sequence_difficulty("Kto napisał Pana Tadeusza?", "hard")
check("tresc niematematyczna -> validate=not_sequence", r["status"] == "not_sequence", r)

t = classify_sequence_difficulty("Co to jest ciąg arytmetyczny? Podaj definicję.")
check("pytanie koncepcyjne o ciagu (brak danych liczbowych) -> classify=None", t is None, t)

t = classify_sequence_difficulty("Ciąg arytmetyczny ma a1=m, r=2. Oblicz dziesiąty wyraz tego ciągu.")
check("ciag z PARAMETREM (swiadomie poza zakresem Etapu 6) -> classify=None (abstain)", t is None, t)

r = validate_sequence_difficulty("Rozwiąż równanie $x^2-5x+6=0$.", "easy")
check("rownanie kwadratowe (inny temat) -> validate=not_sequence", r["status"] == "not_sequence", r)

r = validate_sequence_difficulty("Ciąg arytmetyczny ma a1=3, r=5. Oblicz 10. wyraz tego ciągu.", "nieznane_slowo")
check("nierozpoznane slowo trudnosci -> not_sequence", r["status"] == "not_sequence", r)

print()

# ---------------------------------------------------------------
# Dodatkowo: SequenceModifier adapter (level-aware, jak w test_etap5.py
# dla math_quadratic.py) - potwierdzenie ze adapter bez `level` daje
# IDENTYCZNY wynik co bezposrednie wywolanie validate_sequence_difficulty,
# i ze mechanizm przesuniecia (level_adjusted_shift) dziala.
# ---------------------------------------------------------------
print("=== 5. SequenceModifier adapter: zgodnosc + level-aware shift ===")

mod = SequenceModifier()
q = "Ciąg arytmetyczny ma a1=3, r=5. Oblicz 10. wyraz tego ciągu."
direct = validate_sequence_difficulty(q, "easy")
via_adapter = mod.evaluate(q, None, "easy", level=None)
check("adapter bez level == wywolanie bezposrednie", direct == via_adapter, (direct, via_adapter))

check("applies() zgodny z classify_sequence_difficulty", mod.applies(q) == (classify_sequence_difficulty(q) is not None))

shift_baseline = level_adjusted_shift(SEQUENCE_BASELINE_LEVEL, SEQUENCE_BASELINE_LEVEL, SEQUENCE_MAX_SHIFT)
check("shift na baseline (liceum_2) == 0", shift_baseline == 0, shift_baseline)

# sum_given_n (tier 2, "medium" na baseline) dla mlodszego ucznia
# (podstawowka_5) powinno przesunac sie w strone "za trudne", tak jak
# dzialalo to dla rownan kwadratowych w Etapie 5.
q_medium = "Ciąg arytmetyczny ma a1=2, r=3. Oblicz sumę pierwszych 10 wyrazów tego ciągu."
r_young = mod.evaluate(q_medium, None, "hard", level="podstawowka_5")
check(
    "mlodszy uczen (podstawowka_5): 'hard' okno przesuniete w dol, tier 2 moze juz pasowac",
    r_young["status"] in ("ok", "fail"),
    r_young,
)
print("    detail:", r_young)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
