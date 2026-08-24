# -*- coding: utf-8 -*-
"""NAPRAWA: Etap 8 (funkcje - liniowa/kwadratowa-jako-funkcja/wykladnicza)
mial gotowa, przetestowana Warstwe 2, ale NIGDY nie byla podlaczona do
verify_and_fix_math_question - jedynego dispatchera, ktorego faktycznie
uzywa _verify_and_fix_quiz_math/_verify_and_fix_exam_math w produkcji
(openai_exam.py/exam_pdf_generator.py). W praktyce caly Warstwa-2 kod
funkcji byl martwy - dzialal tylko gdy wywolywany BEZPOSREDNIO (jak w
test_etap8.py), nigdy w prawdziwym potoku Quiz/Sprawdzian.

Ten plik dowodzi, ze KAZDY z 5 wariantow Warstwy 2 funkcji jest teraz
osiagalny PRZEZ verify_and_fix_math_question (nie tylko przez wlasna
funkcje verify_X bezposrednio) - dokladnie ta funkcja, ktora produkcja
faktycznie wywoluje. Zero kosztu API - czysto lokalne testy jednostkowe."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.math_verify import verify_and_fix_math_question

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("Etap 8 przez verify_and_fix_math_question (dispatch chain)")
print("=" * 70)

# 1. Liniowa: ewaluacja f(k)
r = verify_and_fix_math_question("Dla funkcji f(x)=2x+3, oblicz f(4).", ["11", "10", "9", "8"])
check("liniowa: f(4)=11 przez dispatch -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

# 2. Liniowa: rownanie prostej przez 2 punkty
q2p = "Wyznacz równanie prostej przechodzącej przez punkty (1,5) i (3,-1)."
r = verify_and_fix_math_question(q2p, ["y=-3x+8", "y=2x+3", "y=-2x+7", "y=3x-2"])
check("liniowa: prosta przez 2 punkty przez dispatch -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

# 3. Kwadratowa-jako-funkcja: wierzcholek z postaci ogolnej
q_vertex = "Funkcja f(x)=x²-4x+7. Wyznacz wierzchołek paraboli."
r = verify_and_fix_math_question(q_vertex, ["(2,3)", "(2,4)", "(4,7)", "(-2,3)"])
check("kwadratowa-funkcja: wierzcholek (2,3) przez dispatch -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

# 4. Wykladnicza: ewaluacja f(k)
q_exp_eval = "Funkcja f(x)=2^x. Oblicz f(3)."
r = verify_and_fix_math_question(q_exp_eval, ["8", "6", "9", "16"])
check("wykladnicza: f(3)=8 przez dispatch -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

# 5. Wykladnicza: rownanie przy tej samej podstawie
q_exp_eq = "Rozwiąż równanie 2^(x+1) = 8."
r = verify_and_fix_math_question(q_exp_eq, ["2", "3", "4", "1"])
check("wykladnicza: 2^(x+1)=8 -> x=2 przez dispatch -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

print()
print("--- kontrola: bledne odpowiedzi w opcjach musza byc ODRZUCONE (no_option_matches) ---")

r = verify_and_fix_math_question("Dla funkcji f(x)=2x+3, oblicz f(4).", ["10", "9", "8", "7"])
check("liniowa: f(4)=11 BRAK wsrod blednych opcji -> no_option_matches", r["status"] == "no_option_matches", r)

r = verify_and_fix_math_question(q_vertex, ["(1,1)", "(2,4)", "(4,7)", "(-2,3)"])
check("kwadratowa-funkcja: wierzcholek BRAK wsrod blednych opcji -> no_option_matches", r["status"] == "no_option_matches", r)

r = verify_and_fix_math_question(q_exp_eval, ["6", "9", "16", "32"])
check("wykladnicza: f(3)=8 BRAK wsrod blednych opcji -> no_option_matches", r["status"] == "no_option_matches", r)

print()
print("--- kontrola: pozostale (zero regresji, inne tematy wciaz dzialaja PRZEZ ten sam dispatcher) ---")

r = verify_and_fix_math_question(
    "Rozwiąż równanie kwadratowe $x^2 - 5x + 6 = 0$",
    ["$x = 2$ i $x = 3$", "$x = -2$ i $x = -3$", "$x = 1$ i $x = 6$", "$x = -1$ i $x = -6$"],
)
check("rownanie kwadratowe nadal dziala przez dispatch", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_and_fix_math_question(
    "W urnie znajduje się 5 kul białych i 3 czarne. Losujemy bez zwracania dwie kule. "
    "Oblicz prawdopodobieństwo, że obie są tego samego koloru.",
    ["10/28", "9/28", "1/2", "3/14"],
)
check("prawdopodobienstwo nadal dziala przez dispatch (odrzuca bledne opcje)", r["status"] == "no_option_matches", r)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
