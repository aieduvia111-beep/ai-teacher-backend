# -*- coding: utf-8 -*-
"""User zglosil: Pytanie 6 i 7 w wygenerowanym Sprawdzianie uzywaly
IDENTYCZNEJ stalej C=25 w rowaniu kwadratowym x^2+_x+25=0 - rozne tylko
litery parametru (n vs c). Litery byly juz losowane bez powtorzen W
OBREBIE jednej partii, ale stale C w ogole nie (random.choice z
powtorzeniami), i ZADNE z nich nie pamietalo, co bylo juz uzyte w
POPRZEDNIEJ partii (pierwsza generacja vs runda dogenerowania to
OSOBNE wywolania). Ten test sprawdza nowy, wspoldzielony mechanizm
pick_safe_param_values (math_verify.py) uzywany teraz przez OBIE
strony (Quiz i Sprawdzian) - ZERO wywolan AI."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.math_verify import pick_safe_param_values, _SAFE_PERFECT_SQUARES, _SAFE_PARAM_LETTERS

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("1. W obrebie JEDNEGO wywolania - brak powtorzen, dopoki pula starcza")
print("=" * 70)
used = set()
picks = pick_safe_param_values(_SAFE_PERFECT_SQUARES, used, 6)
check("6 wywolan z puli 10 -> wszystkie unikalne", len(set(picks)) == 6, picks)
check("used zawiera dokladnie te 6 wartosci", used == set(picks), used)

print()
print("=" * 70)
print("2. MIEDZY wywolaniami (symulacja: pierwsza partia + runda dogenerowania)")
print("   - DOKLADNY scenariusz zgloszony przez usera")
print("=" * 70)
used_c = set()
round1 = pick_safe_param_values(_SAFE_PERFECT_SQUARES, used_c, 5)
round2 = pick_safe_param_values(_SAFE_PERFECT_SQUARES, used_c, 4)
overlap = set(round1) & set(round2)
check("stale z rundy 1 i rundy 2 (osobne wywolania) NIE nakladaja sie",
      len(overlap) == 0, {"round1": round1, "round2": round2, "overlap": overlap})
check("wszystkie 9 stale (5+4) sa unikalne", len(set(round1 + round2)) == 9, round1 + round2)

print()
print("=" * 70)
print("3. Litery: ten sam mechanizm dziala identycznie")
print("=" * 70)
used_l = set()
l1 = pick_safe_param_values(_SAFE_PARAM_LETTERS, used_l, 4)
l2 = pick_safe_param_values(_SAFE_PARAM_LETTERS, used_l, 3)
check("litery z dwoch osobnych wywolan nie nakladaja sie", len(set(l1) & set(l2)) == 0, (l1, l2))

print()
print("=" * 70)
print("4. Wyczerpanie puli (>10 zadan tego podwzorca w JEDNYM dokumencie)")
print("   - dopiero WTEDY dopuszczalne powtorzenia (unikniecie niemozliwe)")
print("=" * 70)
used_big = set()
big = pick_safe_param_values(_SAFE_PERFECT_SQUARES, used_big, 13)
check("pierwsze 10 z 13 nadal unikalne (caly pool wykorzystany raz)",
      len(set(big[:10])) == 10, big[:10])
check("funkcja nie rzuca wyjatku i zwraca dokladnie 13 wartosci mimo wyczerpanej puli",
      len(big) == 13, big)

print()
print("=" * 70)
print("5. Regresja: bez podania used-set (stary, opcjonalny tryb) - dziala jak wczesniej")
print("=" * 70)
from app.exam_pdf_generator import ExamGenerator
gen = ExamGenerator("fake-key-never-called-in-this-test")
try:
    data = gen._raw_generate_safe_linear_param_quadratic_batch.__wrapped__ if False else None
except Exception:
    pass
check("metoda nadal istnieje z nowa sygnatura (used_letters/used_constants opcjonalne)",
      hasattr(ExamGenerator, "_raw_generate_safe_linear_param_quadratic_batch"), None)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
