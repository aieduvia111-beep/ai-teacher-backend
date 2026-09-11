# -*- coding: utf-8 -*-
"""Safe Parameter Generation - odwrocenie kolejnosci dla NAJTRUDNIEJSZEGO
potwierdzonego podwzorca (rownanie x^2+mx+C=0, parametr jako goly
wspolczynnik liniowy, medium): KOD wybiera C (kwadrat idealny) i liczy
PRAWDZIWY warunek PRZED wywolaniem AI, zamiast prosic AI o policzenie
calej matematyki i sprawdzac dopiero po fakcie (co dawalo ~50%
odrzucen w realnych testach - patrz audyt V1). Ten test sprawdza SAMA
LOGIKE (zero AI) - poprawnosc matematyczna szkieletu."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import sympy as sp
from app.math_verify import (
    build_safe_linear_param_quadratic, verify_param_quadratic_question,
    _SAFE_PERFECT_SQUARES,
)

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("1. build_safe_linear_param_quadratic - poprawnosc matematyczna")
print("=" * 70)

for c in _SAFE_PERFECT_SQUARES:
    # NAPRAWIONE (wrzesien 2026, "kind" jako nowy parametr - patrz
    # sekcja 5 nizej): "kind" domyslnie jest LOSOWANY z ('pos','zero','neg'),
    # wiec ta sekcja PRZYPINA kind="pos" jawnie, zeby nadal testowac
    # KONKRETNIE historyczny format "dwa rozne pierwiastki" (bez tego
    # przypiecia test byłby niedeterministyczny/zalezny od losowania).
    sk = build_safe_linear_param_quadratic(param_letter="m", c_value=c, kind="pos")
    expected_bound = int(2 * sp.sqrt(c))
    check(f"C={c}: granica={sk['bound']} == 2*sqrt({c})={expected_bound} (calkowita)",
          sk["bound"] == expected_bound, sk)
    check(f"C={c}: correct_text ma poprawna forme '$m < -{expected_bound}$ lub $m > {expected_bound}$'",
          sk["correct_text"] == f"$m < -{expected_bound}$ lub $m > {expected_bound}$", sk["correct_text"])

print()
print("=" * 70)
print("2. Losowy dobor (bez podania param_letter/c_value) - deterministycznie poprawny")
print("=" * 70)

for _ in range(20):
    sk = build_safe_linear_param_quadratic()
    check(f"c_value={sk['c_value']} jest kwadratem idealnym", sk["c_value"] in _SAFE_PERFECT_SQUARES, sk)
    check(f"param_letter='{sk['param_letter']}' jest pojedyncza litera", len(sk["param_letter"]) == 1, sk)
    check(f"bound={sk['bound']} jest liczba calkowita > 0", isinstance(sk["bound"], int) and sk["bound"] > 0, sk)

print()
print("=" * 70)
print("3. KRYTYCZNE: wygenerowany szkielet PRZECHODZI przez ISTNIEJACY weryfikator Warstwy 2")
print("=" * 70)
print("   (to jest gwarancja z Kroku 4 planu - sympy nadal robi koncowa weryfikacje)")

for c in [1, 16, 49, 100]:
    sk = build_safe_linear_param_quadratic(param_letter="m", c_value=c, kind="pos")
    # Symulacja: opcja 0 = poprawna (nasz correct_text), 3 "bledne" dystraktory
    wrong1 = f"$m < -{sk['bound']-1}$ lub $m > {sk['bound']-1}$"
    wrong2 = f"$m < {sk['bound']}$ lub $m > {sk['bound']}$"
    wrong3 = f"$m = {sk['bound']}$"
    options = [sk["correct_text"], wrong1, wrong2, wrong3]
    result = verify_param_quadratic_question(sk["question"], options)
    check(f"C={c}: Warstwa 2 (verify_param_quadratic_question) potwierdza poprawna opcje na indeksie 0",
          result["status"] == "match_index" and result["true_index"] == 0, result)

print()
print("=" * 70)
print("4. Regresja: jesli ktos przez pomylke poda opcje BEZ prawdziwej odpowiedzi -> odrzucone")
print("=" * 70)

sk = build_safe_linear_param_quadratic(param_letter="m", c_value=16, kind="pos")
bad_options = ["$m < -4$ lub $m > 4$", "$m < -6$ lub $m > 6$", "$m < -10$ lub $m > 10$", "$m = 8$"]
result = verify_param_quadratic_question(sk["question"], bad_options)
check("brak prawdziwej odpowiedzi (8) wsrod opcji -> no_option_matches (bezpiecznik dziala)",
      result["status"] == "no_option_matches", result)

print()
print("=" * 70)
print("5. NOWE (wrzesien 2026): warianty 'zero'/'neg' - rozszerzenie z JEDNEGO")
print("   podwzorca ('pos' - dwa rozne pierwiastki) na TRZY, zeby batch nie byl")
print("   zawsze tym samym zadaniem (user zglosil 8/10 identycznych zadan)")
print("=" * 70)

for kind, tail in (("zero", "ma dokładnie jeden pierwiastek"), ("neg", "nie ma pierwiastków rzeczywistych")):
    sk = build_safe_linear_param_quadratic(param_letter="m", c_value=16, kind=kind)
    check(f"kind='{kind}': pytanie zawiera oczekiwana fraze ('{tail}')",
          tail in sk["question"], sk["question"])
    check(f"kind='{kind}': Warstwa 2 (verify_param_quadratic_question) potwierdza wlasna poprawna opcje",
          verify_param_quadratic_question(sk["question"], [sk["correct_text"], "$m = 999$", "$m < 0$", "$m > 0$"])["status"] == "match_index",
          sk)

check("kind domyslny (brak argumentu) losuje z {'pos','zero','neg'}, nigdy spoza tej puli",
      all(build_safe_linear_param_quadratic(param_letter="m", c_value=16)["kind"] in ("pos", "zero", "neg") for _ in range(30)))

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
