# -*- coding: utf-8 -*-
"""NAPRAWA (audyt realnej generacji V1, sierpien 2026): Warstwa 2 dla
katow specjalnych trygonometrii (analyze_trig_special_angle_question /
verify_trig_special_angle_question) rozpoznawala WYLACZNIE zapis w
STOPNIACH. Realny test na prawdziwej generacji (n=20, "Trygonometria",
medium) pokazal 0/26 rozpoznanych - AI pisze niemal zawsze w radianach
(pi/6, pi/3, 3pi/2...). Naprawiono: analyze_trig_special_angle_question
teraz rozpoznaje TAKZE argument w radianach jako wielokrotnosc pi.

Dodatkowo: prompt "medium" (2-3) dla trygonometrii dostal jawny zakaz
generowania rownania DO ROZWIAZANIA (poziom 4-5) - w tym samym realnym
tescie AI generowalo rownania-do-rozwiazania w 14/26 przypadkow mimo
zadanego "medium", co Warstwa 3 poprawnie odrzucala, ale powodowalo
masowy shortfall (12/20 po 65s)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.math_verify import (
    analyze_trig_special_angle_question, verify_trig_special_angle_question,
)

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("Rozpoznawanie katow specjalnych w RADIANACH (realne przyklady)")
print("=" * 70)

CASES = [
    ("Oblicz wartość $\\sin(\\frac{\\pi}{6})$.", "sin", 30, "1/2"),
    ("Oblicz wartość $\\cos(\\pi)$.", "cos", 180, "-1"),
    ("Oblicz wartość $\\sin(\\frac{3\\pi}{2})$.", "sin", 270, "-1"),
    ("Znajdź wartość $\\tan(\\frac{\\pi}{4})$.", "tan", 45, "1"),
    ("Oblicz wartość $\\cot(\\pi/4)$.", "cot", 45, "1"),
    ("Oblicz wartość $\\cos(\\frac{\\pi}{3})$.", "cos", 60, "1/2"),
    ("Znajdź wartość $\\cos(\\frac{\\pi}{2})$.", "cos", 90, "0"),
    ("Oblicz wartość $\\sin(\\pi)$.", "sin", 180, "0"),
]
for text, func, deg, val_str in CASES:
    r = analyze_trig_special_angle_question(text)
    check(f"'{text}' -> deg={deg}", r is not None and r["deg"] == deg and r["func"] == func, r)

# Niezdefiniowane (tan(pi/2)) - musi ZOSTAC None (abstain), nie zgadywac
r = analyze_trig_special_angle_question("Oblicz wartość $\\tan(\\frac{\\pi}{2})$.")
check("tan(pi/2) niezdefiniowany -> None (abstain, nie zgadujemy)", r is None, r)

# Rownanie do rozwiazania (NIE lookup katow specjalnych) - musi zostac None
r = analyze_trig_special_angle_question("Rozwiąż równanie $\\sin(x) = \\cos(x)$ w przedziale $[0, 2\\pi)$.")
check("rownanie sin(x)=cos(x) do rozwiazania -> None (to NIE lookup kata specjalnego)", r is None, r)

# Stopnie nadal dzialaja (regresja wzgledem oryginalnej funkcji)
r = analyze_trig_special_angle_question("Ile wynosi sin(30°)?")
check("stopnie nadal dzialaja: sin(30°) -> deg=30", r is not None and r["deg"] == 30, r)

print()
print("=" * 70)
print("verify_trig_special_angle_question - koniec do konca (radiany)")
print("=" * 70)

q = "Oblicz wartość $\\sin(\\frac{\\pi}{6})$."
opts_present = ["$\\frac{1}{2}$", "$\\frac{\\sqrt{3}}{2}$", "$1$", "$0$"]
opts_absent = ["$\\frac{\\sqrt{3}}{2}$", "$1$", "$0$", "$\\frac{\\sqrt{2}}{2}$"]

r = verify_trig_special_angle_question(q, opts_present)
check("sin(pi/6): poprawna 1/2 obecna -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_trig_special_angle_question(q, opts_absent)
check("sin(pi/6): BRAK poprawnej 1/2 -> no_option_matches (NIE unverifiable)", r["status"] == "no_option_matches", r)

print()
print("=" * 70)
print("Bonus: \\sqrt{} nigdzie w module nie bylo normalizowane (znaleziony")
print("przy okazji tego samego audytu - psulo KAZDA opcje z pierwiastkiem)")
print("=" * 70)

from app.math_verify import _parse_expr

r = _parse_expr(r"\frac{\sqrt{2}}{2}")
check(r"\frac{\sqrt{2}}{2} parsuje sie na sqrt(2)/2", str(r) == "sqrt(2)/2", r)

q45 = "Oblicz wartość $\\cos(45°)$."
opts_sqrt = ["$\\frac{\\sqrt{2}}{2}$", "$1$", "$\\frac{1}{2}$", "$\\frac{\\sqrt{3}}{2}$"]
r = verify_trig_special_angle_question(q45, opts_sqrt)
check("cos(45°): poprawna sqrt(2)/2 obecna wsrod opcji z pierwiastkiem -> match_index=0",
      r["status"] == "match_index" and r["true_index"] == 0, r)

q30 = "Oblicz wartość $\\tan(30°)$."
opts_sqrt2 = ["$\\frac{1}{\\sqrt{3}}$", "$\\sqrt{3}$", "$\\frac{1}{2}$", "$1$"]
r = verify_trig_special_angle_question(q30, opts_sqrt2)
check("tan(30°): poprawna 1/sqrt(3) obecna (rowna sqrt(3)/3) -> match_index=0",
      r["status"] == "match_index" and r["true_index"] == 0, r)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
