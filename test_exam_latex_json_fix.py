# -*- coding: utf-8 -*-
"""Sprawdzian - port naprawy z Quizu: ExamGenerator._fix_json mial
WLASNA, zduplikowana kopie dokladnie tego samego algorytmu co
sanitize_latex_json_backslashes (openai_exam.py), ale z KROTSZA, nieaktualna
lista chronionych komend LaTeX - brakowalo m.in. "textbackslash" (dokladnie
ta sama luka, ktora zostala znaleziona i naprawiona w Quizie tego samego
dnia). Teraz _fix_json woła wspoldzielona funkcje.

WAZNE: Sprawdzian NIE uzywa response_format=json_object (w przeciwienstwie
do Quizu), wiec zachowano oryginalna ochrone: surowe znaki nowej linii/
tabulacji wewnatrz wartosci stringow sa escapowane PRZED wywolaniem
wspoldzielonego sanitizera."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import json
from app.exam_pdf_generator import ExamGenerator

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


gen = ExamGenerator("fake-key-never-called-in-this-test")

print("=" * 70)
print("1. Markdown fences nadal usuwane")
print("=" * 70)
raw = "```json\n{\"a\": 1}\n```"
check("fences usuniete", gen._fix_json(raw) == '{"a": 1}', gen._fix_json(raw))

print()
print("=" * 70)
print("2. Surowy znak nowej linii wewnatrz stringa -> escapowany (ZACHOWANE)")
print("=" * 70)
raw = '{"tresc": "linia1\nlinia2"}'
fixed = gen._fix_json(raw)
parsed = json.loads(fixed)
check("json.loads sie udaje (surowa nowa linia poprawnie escapowana)",
      parsed == {"tresc": "linia1\nlinia2"}, parsed)

print()
print("=" * 70)
print("3. Port fixu z Quizu: \\textbackslash i podobne komendy chronione")
print("=" * 70)
CASES = [
    (r'{"x": "$a < -2\textbackslash sqrt5$"}', "textbackslash"),
    (r'{"x": "\mathbb{R}"}', "mathbb"),
    (r'{"x": "\underbrace{x}"}', "underbrace"),
]
for raw, expect_word in CASES:
    fixed = gen._fix_json(raw)
    parsed = json.loads(fixed)
    value = parsed["x"]
    check(f"'{raw[:40]}...' parsuje sie, zawiera '{expect_word}' nienaruszone, brak znaku tabulacji",
          expect_word in value and "\t" not in value, value)

print()
print("=" * 70)
print("4. Regresja: juz chronione komendy (frac/sqrt) nadal dzialaja")
print("=" * 70)
raw = r'{"x": "$\frac{1}{2}$ i $\sqrt{2}$"}'
fixed = gen._fix_json(raw)
parsed = json.loads(fixed)
check("frac/sqrt nadal poprawnie chronione", "frac" in parsed["x"] and "sqrt" in parsed["x"], parsed["x"])

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
