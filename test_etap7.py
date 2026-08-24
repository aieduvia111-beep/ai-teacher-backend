# -*- coding: utf-8 -*-
"""ETAP 7: rozszerzenie Universal Difficulty Engine na trygonometrie
(math_trigonometry.py, wzorem math_quadratic.py/math_sequences.py).

Wymagane (ten sam wzorzec co test_etap6.py):
  1. testy jednostkowe klasyfikacji (classify_trig_difficulty)
  2. testy poprawnych przypadkow PASS (validate_trig_difficulty -> ok)
  3. testy przypadkow FAIL (validate_trig_difficulty -> fail)
  4. testy abstain dla nierozpoznanych zadan (-> not_trig / None)
  5. testy Warstwy 2 (weryfikacja sympy katow specjalnych) - PASS/FAIL/abstain
  6. adapter (TrigonometryModifier) - zgodnosc + level-aware shift

Plain script (bez pytest), wzorem test_etap5.py/test_etap6.py."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.math_verify import (
    classify_trig_difficulty, validate_trig_difficulty,
    analyze_trig_special_angle_question, verify_trig_special_angle_question,
    verify_and_fix_math_question,
)
from app.difficulty.modifiers.math_trigonometry import TrigonometryModifier
from app.difficulty.calibration import level_adjusted_shift, TRIG_BASELINE_LEVEL, TRIG_MAX_SHIFT

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


# ---------------------------------------------------------------
# 1. Testy jednostkowe klasyfikacji (classify_trig_difficulty)
# ---------------------------------------------------------------
print("=== 1. classify_trig_difficulty: tiery per wzorzec ===")

t = classify_trig_difficulty("Ile wynosi sin(30°)?")
check("wartosc kata specjalnego (sin) -> tier 1", t == "1", t)

t = classify_trig_difficulty("Oblicz cos(45°).")
check("wartosc kata specjalnego (cos) -> tier 1", t == "1", t)

t = classify_trig_difficulty(
    "W trójkącie prostokątnym przeciwprostokątna ma długość 10, a jeden z kątów ostrych 35°. "
    "Oblicz długości przyprostokątnych."
)
check("trojkat prostokatny (SOH-CAH-TOA) -> tier 2", t == "2", t)

t = classify_trig_difficulty("Zamień 45° na radiany.")
check("zamiana stopnie<->radiany -> tier 2", t == "2", t)

t = classify_trig_difficulty(
    "W trójkącie kąt α=60°, boki przy tym kącie mają długość 5 i 8. "
    "Oblicz pole trójkąta, stosując twierdzenie cosinusów."
)
check("twierdzenie cosinusow -> tier 3", t == "3", t)

t = classify_trig_difficulty("Rozwiąż równanie 2sin²(x)-3cos(x)=0 dla x∈[0,2π).")
check("rownanie trygonometryczne bez parametru -> tier 4", t == "4", t)

t = classify_trig_difficulty("Dla jakich wartości parametru a równanie sin(x)=a ma rozwiązanie w [0,2π)?")
check("rownanie trygonometryczne Z parametrem -> tier 5", t == "5", t)

t = classify_trig_difficulty("Udowodnij tożsamość (1-cos(2x))/sin(2x) = tan(x).")
check("dowod tozsamosci -> tier 5 (INNY wzorzec niz rownanie z parametrem)", t == "5", t)

print()

# ---------------------------------------------------------------
# 2. Testy poprawnych przypadkow PASS - rozdzielone tak, zeby "hard"
#    obejmowalo WIECEJ NIZ JEDEN wzorzec (glowny wymog z Etapu 6,
#    zastosowany konsekwentnie tu tez).
# ---------------------------------------------------------------
print("=== 2. validate_trig_difficulty: przypadki PASS ===")

r = validate_trig_difficulty("Ile wynosi sin(30°)?", "easy")
check("easy vs kat specjalny -> ok", r["status"] == "ok", r)

r = validate_trig_difficulty(
    "W trójkącie prostokątnym przeciwprostokątna ma długość 10, a jeden z kątów ostrych 35°. "
    "Oblicz długości przyprostokątnych.", "medium",
)
check("medium vs trojkat prostokatny -> ok", r["status"] == "ok", r)

r = validate_trig_difficulty(
    "W trójkącie kąt α=60°, boki przy tym kącie mają długość 5 i 8. "
    "Oblicz pole trójkąta, stosując twierdzenie cosinusów.", "sredni",
)
check("sredni vs twierdzenie cosinusow (INNY wzorzec niz wyzej) -> ok", r["status"] == "ok", r)

r = validate_trig_difficulty("Rozwiąż równanie 2sin²(x)-3cos(x)=0 dla x∈[0,2π).", "hard")
check("hard vs rownanie bez parametru -> ok", r["status"] == "ok", r)

r = validate_trig_difficulty(
    "Dla jakich wartości parametru a równanie sin(x)=a ma rozwiązanie w [0,2π)?", "trudny",
)
check("trudny vs rownanie Z parametrem (INNY wzorzec) -> ok", r["status"] == "ok", r)

r = validate_trig_difficulty("Udowodnij tożsamość (1-cos(2x))/sin(2x) = tan(x).", "trudna")
check("trudna vs dowod tozsamosci (TRZECI rozny wzorzec dla 'hard') -> ok", r["status"] == "ok", r)

print()

# ---------------------------------------------------------------
# 3. Testy przypadkow FAIL
# ---------------------------------------------------------------
print("=== 3. validate_trig_difficulty: przypadki FAIL ===")

r = validate_trig_difficulty("Ile wynosi sin(30°)?", "hard")
check("hard vs kat specjalny -> fail (za latwe)", r["status"] == "fail" and "za latwe" in r["reason"], r)

r = validate_trig_difficulty("Rozwiąż równanie 2sin²(x)-3cos(x)=0 dla x∈[0,2π).", "easy")
check("easy vs rownanie -> fail (za trudne)", r["status"] == "fail" and "za trudne" in r["reason"], r)

r = validate_trig_difficulty(
    "W trójkącie prostokątnym przeciwprostokątna ma długość 10, a jeden z kątów ostrych 35°. "
    "Oblicz długości przyprostokątnych.", "easy",
)
check("easy vs trojkat prostokatny -> fail (za trudne)", r["status"] == "fail" and "za trudne" in r["reason"], r)

r = validate_trig_difficulty("Udowodnij tożsamość (1-cos(2x))/sin(2x) = tan(x).", "medium")
check("medium vs dowod tozsamosci -> fail (za trudne)", r["status"] == "fail" and "za trudne" in r["reason"], r)

print()

# ---------------------------------------------------------------
# 4. Testy abstain dla nierozpoznanych zadan
# ---------------------------------------------------------------
print("=== 4. abstain (not_trig / None) ===")

t = classify_trig_difficulty("Kto napisał Pana Tadeusza?")
check("tresc niematematyczna -> classify=None", t is None, t)

r = validate_trig_difficulty("Kto napisał Pana Tadeusza?", "hard")
check("tresc niematematyczna -> validate=not_trig", r["status"] == "not_trig", r)

t = classify_trig_difficulty("Rozwiąż równanie $x^2-5x+6=0$.")
check("rownanie kwadratowe (inny temat) -> classify=None", t is None, t)

r = validate_trig_difficulty("Rozwiąż równanie $x^2-5x+6=0$.", "easy")
check("rownanie kwadratowe (inny temat) -> validate=not_trig", r["status"] == "not_trig", r)

t = classify_trig_difficulty("Ile wynosi tg(90°)?")
check("tg(90°) niezdefiniowane -> classify=None (abstain, nie zgadujemy)", t is None, t)

r = validate_trig_difficulty("Ile wynosi sin(30°)?", "nieznane_slowo")
check("nierozpoznane slowo trudnosci -> not_trig", r["status"] == "not_trig", r)

print()

# ---------------------------------------------------------------
# 5. Warstwa 2: weryfikacja sympy katow specjalnych
# ---------------------------------------------------------------
print("=== 5. verify_trig_special_angle_question (Warstwa 2) ===")

parsed = analyze_trig_special_angle_question("Ile wynosi sin(30°)?")
check("analyze: sin(30°) -> value=1/2", parsed is not None and str(parsed["value"]) == "1/2", parsed)

r = verify_trig_special_angle_question("Ile wynosi sin(30°)?", ["1/2", "sqrt(2)/2", "sqrt(3)/2", "1"])
check("sin(30°): poprawna opcja wsrod podanych -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_trig_special_angle_question("Ile wynosi cos(60°)?", ["1/2", "sqrt(2)/2", "sqrt(3)/2", "1"])
check("cos(60°)=1/2: poprawna opcja -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_trig_special_angle_question("Ile wynosi sin(90°)?", ["0", "1/2", "sqrt(2)/2", "sqrt(3)/2"])
check("sin(90°)=1: ZADNA opcja nie pasuje -> no_option_matches", r["status"] == "no_option_matches", r)

r = verify_trig_special_angle_question("Ile wynosi tg(90°)?", ["0", "1", "niezdefiniowane", "-1"])
check("tg(90°) niezdefiniowane -> unverifiable (abstain)", r["status"] == "unverifiable", r)

r = verify_trig_special_angle_question("Kto napisał Pana Tadeusza?", ["a", "b", "c", "d"])
check("tresc niematematyczna -> unverifiable", r["status"] == "unverifiable", r)

r = verify_and_fix_math_question("Ile wynosi sin(30°)?", ["1/2", "sqrt(2)/2", "sqrt(3)/2", "1"])
check("verify_and_fix_math_question dispatchuje do trig -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

print()

# ---------------------------------------------------------------
# 6. TrigonometryModifier adapter: zgodnosc + level-aware shift
# ---------------------------------------------------------------
print("=== 6. TrigonometryModifier adapter: zgodnosc + level-aware shift ===")

mod = TrigonometryModifier()
q = "Ile wynosi sin(30°)?"
direct = validate_trig_difficulty(q, "easy")
via_adapter = mod.evaluate(q, None, "easy", level=None)
check("adapter bez level == wywolanie bezposrednie", direct == via_adapter, (direct, via_adapter))

check("applies() zgodny z classify_trig_difficulty", mod.applies(q) == (classify_trig_difficulty(q) is not None))

shift_baseline = level_adjusted_shift(TRIG_BASELINE_LEVEL, TRIG_BASELINE_LEVEL, TRIG_MAX_SHIFT)
check("shift na baseline (liceum_2) == 0", shift_baseline == 0, shift_baseline)

q_medium = (
    "W trójkącie prostokątnym przeciwprostokątna ma długość 10, a jeden z kątów ostrych 35°. "
    "Oblicz długości przyprostokątnych."
)
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
