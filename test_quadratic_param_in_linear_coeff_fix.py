# -*- coding: utf-8 -*-
"""NAPRAWA (audyt realnej generacji V1, sierpien 2026): realny test
(generowanie n=10/n=20, "Rownania kwadratowe", medium) pokazal 14-21 z
26 pytan odrzuconych - WSZYSTKIE tego samego podwzorca: parametr
WEWNATRZ WYRAZENIA jako wspolczynnik przy x (np. "x^2+(m-4)x+2=0",
"x^2+(2m-1)x+2=0"), NIE goly parametr ("x^2+mx+3=0"). Diagnostyka
(nowy log_no_option_matches_diagnostic / log_final_answer_mismatch_
diagnostic) potwierdzila: to byly REALNE bledy matematyczne AI (prawdziwy
warunek na delte wymaga rozwiniecia kwadratu dwumianu (wyrazenie)^2-4C,
AI systematycznie zgadywalo "ladny" symetryczny przedzial zamiast tego).

classify_quadratic_difficulty klasyfikowal ten podwzorzec identycznie
jak goly parametr (oba "5-6"/medium) - IRONICZNIE, byl to nawet oficjalny
"przyklad" dla tier 5-6 w level_config.py. Naprawiono: parametr
WEWNATRZ wyrazenia (nie sam siebie) w B -> tier 7-8, tak samo jak juz
istniejacy check dla parametru w A (wspolczynnik wiodacy)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.math_verify import classify_quadratic_difficulty, validate_quadratic_difficulty

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("Parametr WEWNATRZ wyrazenia jako wspolczynnik przy x -> tier 7-8")
print("=" * 70)

CASES_EMBEDDED = [
    "Dla jakich wartości parametru m równanie $x^2+(m-4)x+2=0$ ma dwa różne pierwiastki?",
    "Dla jakich wartości parametru m równanie $x^2+(2m-1)x+2=0$ ma dwa różne pierwiastki?",
    "Dla jakich wartości parametru m równanie $x^2-(m+2)x+5=0$ ma dwa różne pierwiastki?",
    "Dla jakich wartości parametru m równanie $x^2+(4-m)x+m+1=0$ ma dwa różne pierwiastki?",
]
for q in CASES_EMBEDDED:
    tier = classify_quadratic_difficulty(q)
    check(f"'{q[:55]}...' -> tier 7-8 (nie 5-6)", tier == "7-8", tier)

print()
print("=" * 70)
print("Goly parametr (bez wyrazenia) w B -> nadal tier 5-6 (BRAK REGRESJI)")
print("=" * 70)

CASES_BARE = [
    "Dla jakich wartości parametru m równanie $x^2+mx+3=0$ ma dwa różne pierwiastki?",
    "Dla jakich wartości parametru k równanie $x^2-6x+k=0$ ma dwa różne pierwiastki?",
    "Dla jakich wartości parametru m równanie $x^2+5x+m=0$ ma dwa różne pierwiastki?",
]
for q in CASES_BARE:
    tier = classify_quadratic_difficulty(q)
    check(f"'{q[:55]}...' -> tier 5-6 (bez regresji)", tier == "5-6", tier)

print()
print("=" * 70)
print("validate_quadratic_difficulty: 'medium' odrzuca embedded, akceptuje bare")
print("=" * 70)

r = validate_quadratic_difficulty(CASES_EMBEDDED[0], "medium")
check("embedded '(m-4)x' + medium -> fail (za trudne)", r["status"] == "fail", r)

r = validate_quadratic_difficulty(CASES_BARE[0], "medium")
check("bare 'mx' + medium -> ok", r["status"] == "ok", r)

r = validate_quadratic_difficulty(CASES_EMBEDDED[0], "hard")
check("embedded '(m-4)x' + hard -> ok (teraz poprawnie zaklasyfikowane jako trudne)", r["status"] == "ok", r)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
