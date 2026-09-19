# -*- coding: utf-8 -*-
"""Offline (zero AI): karty pojec w notatkach - potegi/indeksy zapisywane
jako Unicode (x^2 -> x²), a nie wycinane ("x2"). Regresja z 19.09.2026."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.notes_pdf_generator import _plain_math_text as f

CASES = [
    ("f(x) = ax^2 + bx + c", "f(x) = ax² + bx + c"),
    ("x^{2} - 5x + 6", "x² - 5x + 6"),
    ("b^2 - 4ac", "b² - 4ac"),
    ("a(x-p)^2 + q", "a(x-p)² + q"),
    ("x_1, x_2", "x₁, x₂"),
    ("a^{n+1}", "aⁿ⁺¹"),
    (r"\frac{-b}{2a}", "(-b)/(2a)"),
]
bad = 0
for src, exp in CASES:
    got = f(src)
    ok = got == exp
    bad += (not ok)
    print(f"{'OK  ' if ok else 'FAIL'} {src!r} -> {got!r} (oczekiwano {exp!r})")
print("bledy:", bad)
sys.exit(1 if bad else 0)
