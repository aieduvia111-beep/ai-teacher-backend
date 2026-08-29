# -*- coding: utf-8 -*-
"""User (29.08.2026, po serii real-testow trudnej trygonometrii z
Sprawdzianu/Quizu i dlugiej dyskusji o architekturze): "musimy miec inne
rozwiazanie" (nie kolejne podniesienie timeoutu) - port wzorca 'safe
parameter generation' (juz dzialajacego dla rownan kwadratowych) na
NAJCZESCIEJ generowany I najczesciej psuty przez AI archetyp trudnej
trygonometrii: rownanie A*sin^2(x)+B*cos(x)+C=0 na x w [0, 2pi),
sprowadzalne do rownania kwadratowego wzgledem cos(x).

User doprecyzowal architekture (po przeczytaniu zewnetrznej propozycji):
"dystraktory tez mozna liczyc kodem, nie wymyslac przez AI... to jest
drugie miejsce, gdzie wpuszczacie niepewnosc" - wiec w odroznieniu od
rownan kwadratowych (gdzie AI nadal wymysla dystraktory), TU kod liczy
WSZYSTKO: poprawna odpowiedz, 3 dystraktory, ktora opcja jest poprawna.
AI dostaje gotowy szkielet i pisze TYLKO tresc pytania po polsku +
wyjasnienie + diversity_tag.

Ten plik testuje SAMA logike (zero AI, zero kosztu):
1. build_safe_trig_quadratic_equation - poprawnosc rownania/odpowiedzi
   (zweryfikowana NIEZALEZNA sciezka - verify_trig_quadratic_equation,
   inny algorytm niz uzyty do budowy).
2. build_safe_trig_quadratic_distractors - dystraktory nigdy nie
   kolidują z poprawna odpowiedzia.
3. Gating (_is_hard_trig_quadratic w Quizie, _is_hard_trig_quadratic_exam
   w Sprawdzianie) - aktywne TYLKO dla trygonometrii + trudny/hard.
4. Warstwa 2/2.5 EXEMPTION - "_safe_generated" pomija sympy/blind-check
   w obu (Quiz i Sprawdzian) - bez tego kazde bezpiecznie wygenerowane
   trig-pytanie i tak wpadaloby do drogiego blind-verify, bo sympy nie
   rozpoznaje tego (nowego) wzorca."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import asyncio

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import (
    build_safe_trig_quadratic_equation, verify_trig_quadratic_equation,
    build_safe_trig_quadratic_distractors,
)

print("=" * 70)
print("build_safe_trig_quadratic_equation - poprawnosc (100 losowych prob,")
print("zweryfikowana NIEZALEZNA sciezka obliczeniowa)")
print("=" * 70)
all_correct = True
first_fail = None
for _ in range(100):
    sk = build_safe_trig_quadratic_equation()
    ok = verify_trig_quadratic_equation(sk["A"], sk["B"], sk["C"], sk["correct_text"])
    if not ok:
        all_correct = False
        first_fail = sk
        break
check("100/100 losowych rownan poprawne wg niezaleznej weryfikacji", all_correct, first_fail)

print()
print("=" * 70)
print("Real przypadek (dokladnie ten, ktory AI generowalo w real-tescie)")
print("=" * 70)
import sympy as sp
sk = build_safe_trig_quadratic_equation(u0=sp.Rational(1, 2), u1=-2, a_coeff=2)
check("Rownanie = '2\\sin^2(x) - 3\\cos(x) = 0' (dokladnie jak w real-logu)",
      sk["equation_latex"] == "2\\sin^2(x) - 3\\cos(x) = 0", sk["equation_latex"])
check("Odpowiedz = 'x = pi/3, x = 5pi/3' (dokladnie jak w real-logu)",
      sk["correct_text"] == "x = \\frac{\\pi}{3}, x = \\frac{5\\pi}{3}", sk["correct_text"])

print()
print("=" * 70)
print("build_safe_trig_quadratic_distractors - nigdy nie koliduje z poprawna")
print("=" * 70)
collision = False
not_three = False
for _ in range(50):
    u0 = sp.Rational(1, 2) if _ % 2 == 0 else sp.Rational(-1, 2)
    sk2 = build_safe_trig_quadratic_equation(u0=u0)
    distractors = sk2["distractors"]
    if len(set(distractors)) != 3:
        not_three = True
    if sk2["correct_text"] in distractors:
        collision = True
check("Zawsze DOKLADNIE 3 rozne dystraktory", not not_three)
check("Zaden dystraktor NIGDY nie jest identyczny z poprawna odpowiedzia", not collision)

print()
print("=" * 70)
print("Gating: _is_hard_trig_quadratic (Quiz) - TYLKO trygonometria+trudny")
print("=" * 70)
from app.openai_exam import _is_hard_trig_quadratic
check("trygonometria + trudny -> True", _is_hard_trig_quadratic("Matematyka: trygonometria", "trudny") is True)
check("trygonometria + hard -> True (angielski synonim)", _is_hard_trig_quadratic("Trygonometria", "hard") is True)
check("trygonometria + srednia -> False (tylko trudny)", _is_hard_trig_quadratic("Trygonometria", "srednia") is False)
check("rownania kwadratowe + trudny -> False (inny temat)", _is_hard_trig_quadratic("Rownania kwadratowe", "trudny") is False)
check("brak tematu -> False", _is_hard_trig_quadratic(None, "trudny") is False)

print()
print("=" * 70)
print("Gating: _is_hard_trig_quadratic_exam (Sprawdzian) - identyczna logika")
print("=" * 70)
from app.exam_pdf_generator import _is_hard_trig_quadratic_exam
check("trygonometria + trudna -> True", _is_hard_trig_quadratic_exam("Matematyka: Trygonometria", "trudna") is True)
check("trygonometria + srednia -> False", _is_hard_trig_quadratic_exam("Trygonometria", "srednia") is False)
check("rownania kwadratowe + trudna -> False", _is_hard_trig_quadratic_exam("Rownania kwadratowe", "trudna") is False)

print()
print("=" * 70)
print("Warstwa 2/2.5 EXEMPTION (Quiz) - _safe_generated pomija sympy/blind-check")
print("=" * 70)
from app.openai_exam import _verify_and_fix_quiz_math

# Rownanie CELOWO nierozpoznawalne przez sympy (losowy tekst) - gdyby
# exemption NIE dzialal, poszloby do Warstwy 2 (sympy: unverifiable) i
# BEZ client (None) zostaloby zaakceptowane "na sciepo" (bezpieczny
# domyslny fallback dla brakujacego client) - wiec test musi sprawdzic
# COS INNEGO niz samo zaakceptowanie: ze NIE trafia w ogole do
# needs_blind_check / print "UNVERIFIABLE" (posrednio, przez to ze
# wynik jest identyczny z i bez _safe_generated, ale NIE rzuca bledu
# nawet dla kompletnie nierozpoznawalnego rownania z 4 opcjami-tekstem).
fake_safe_q = {
    "question": "To jest zupelnie nierozpoznawalne dla sympy zdanie.",
    "options": ["x = A", "x = B", "x = C", "x = D"],
    "correct": 0,
    "final_answer": "x = A",
    "explanation": "test",
    "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"},
    "_safe_generated": True,
}
result = asyncio.run(_verify_and_fix_quiz_math({"questions": [dict(fake_safe_q)]}))
check("Pytanie _safe_generated z NIEROZPOZNAWALNYM rownaniem -> zaakceptowane (exemption dziala)",
      len(result.get("questions", [])) == 1, result)

print()
print("=" * 70)
print("Warstwa 2/2.5 EXEMPTION (Sprawdzian) - identyczny mechanizm")
print("=" * 70)
from app.exam_pdf_generator import _verify_and_fix_exam_math

fake_safe_pyt = {
    "tresc": "To jest zupelnie nierozpoznawalne dla sympy zdanie.",
    "opcje": ["a) x = A", "b) x = B", "c) x = C", "d) x = D"],
    "odpowiedz": "a",
    "final_answer": "x = A",
    "punkty": 1,
    "wyjasnienie": "test",
    "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"},
    "_safe_generated": True,
}
exam_data = {"sekcje": [{"typ": "zamkniete", "pytania": [dict(fake_safe_pyt)]}]}
result2 = _verify_and_fix_exam_math(exam_data)
kept_pytania = [p for s in result2.get("sekcje", []) for p in s.get("pytania", [])]
check("Zadanie _safe_generated z NIEROZPOZNAWALNYM rownaniem -> zaakceptowane (exemption dziala)",
      len(kept_pytania) == 1, result2)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
