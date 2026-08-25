# -*- coding: utf-8 -*-
"""KRYTYCZNY, ZGLOSZONY realny bug: pytanie o trygonometrii mialo
uszkodzony tekst "±±+cos(2x)=2cos²(x)" - podejrzenie, ze to nowy
przypadek tej samej klasy bledu co \\textbackslash (LaTeX psuty przez
naiwne przetwarzanie tekstu).

Sledztwo (real-test generacji trygonometrii, sierpien 2026)
zreprodukowalo dokladnie ten objaw NA PIERWSZA PROBE. Prawdziwa
przyczyna: fix_latex_in_quiz mial STARY, historyczny patch
"t.replace('$1 ', '$\\pm$')" na przypadek, gdy AI (bardzo dawno)
pisalo literalne "$1" majac na mysli "±". Ten BEZWARUNKOWY string-
replace psul KAZDE rownanie zaczynajace sie od cyfry 1 - np. prawdziwa
tozsamosc trygonometryczna "$1 - 2\\sin^2(x) = \\cos(2x)$" (raw AI
output, potwierdzone realnym testem) stawala sie uszkodzonym
"$\\pm$- 2\\sin^2(x) = \\cos(2x)$", z dodatkowym rozjechaniem
parzystosci dolarow w reszcie tekstu - dokladnie zgloszony objaw.

Naprawiono: zawezono regex do przypadku, gdy "1" jest CALA zawartoscia
wyrazenia (np. "$1$", "$1 $") - NIE gdy jest czescia dluzszego,
prawdziwego wyrazenia liczbowego. Historyczny przypadek (samotne "1"
zamiast "±") nadal dziala."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.openai_exam import fix_latex_in_quiz

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


def _fix_one(text):
    return fix_latex_in_quiz({"questions": [{"question": text, "explanation": "", "options": []}]})["questions"][0]["question"]


print("=" * 70)
print("Dokladnie zreprodukowany realny przypadek (raw AI output)")
print("=" * 70)

raw = "Rozwiąż równanie $1 - 2\\sin^2(x) = \\cos(2x)$ w przedziale $[0, 2\\pi)$"
fixed = _fix_one(raw)
check("prawdziwa tozsamosc '1 - 2sin^2(x)=cos(2x)' NIE zostaje uszkodzona",
      fixed == raw, fixed)
check("BRAK podwojnego '±±' albo pojedynczego blednego '$\\pm$-' w wyniku",
      "±±" not in fixed and "\\pm$-" not in fixed, fixed)

print()
print("=" * 70)
print("Inne realne rownania zaczynajace sie od cyfry 1 - rowniez nietkniete")
print("=" * 70)

CASES_SHOULD_BE_UNCHANGED = [
    "$1 + \\cos(2x) = 2\\cos^2(x)$",
    "$1 - \\sin^2(x) = \\cos^2(x)$",
    "Oblicz $1 + 2 + 3$.",
    "$1 \\leq x \\leq 5$",
]
for raw in CASES_SHOULD_BE_UNCHANGED:
    fixed = _fix_one(raw)
    check(f"'{raw}' pozostaje nietkniete", fixed == raw, fixed)

print()
print("=" * 70)
print("Regresja: historyczny przypadek (samotne '$1$' zamiast '±') nadal dziala")
print("=" * 70)

raw_legacy = "x = $1$ 2"
fixed_legacy = _fix_one(raw_legacy)
check("'$1$' (samo, bez reszty wyrazenia) nadal zamienia sie na '$\\pm$'",
      "\\pm" in fixed_legacy, fixed_legacy)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
