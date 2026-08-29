# -*- coding: utf-8 -*-
"""User (29.08.2026, "rozpiszmy to porzadnie, krok po kroku" - trzecie
rozszerzenie Safe Parameter Generation tego samego dnia, po trygonometrii
i ciagach arytmetycznych). Archetyp z OFICJALNEGO przykladu w
level_config.py (technikum_3/liceum_3, "PRZYKLADY TRUDNYCH ZADAN"):
"W trojkacie boki maja dlugosc a=7, b=9, kat miedzy nimi gamma=50°.
Oblicz dlugosc trzeciego boku oraz pole trojkata."

Decyzje architektoniczne ustalone z userem PRZED kodowaniem:
(a) Wariant A - DWA OSOBNE mini-archetypy (bok c ALBO pole P), nie
    jedno pytanie z para wartosci.
(b) Zaokraglanie do 2 miejsc po przecinku, tolerancja +-0.01.
(c) a,b w [4,15], katy CELOWO "nieladne" (bez 30/45/60/90/120/135/150).

Real bug znaleziony i naprawiony PODCZAS budowy (przed napisaniem tego
pliku testowego) - dwa z szesciu dystraktorow (area_cos_confuse,
area_rad_confuse) moga wyjsc UJEMNE dla katow rozwartych (cos/sin
katow-jako-radianow moze byc ujemny) - pole nie moze wygladac na
ujemne w opcji odpowiedzi (oczywisty falszywy trop, oslabia
dystraktor) - naprawiono przez abs(). Ten plik testuje TO WPROST (duza
proba, szukajac ujemnych opcji), nie tylko ze test kiedys przechodzil."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import build_safe_law_of_cosines_triangle, verify_law_of_cosines_triangle

print("=" * 70)
print("Real przypadek (dokladnie oficjalny przyklad z level_config.py)")
print("=" * 70)
sk_c = build_safe_law_of_cosines_triangle(a=7, b=9, gamma_deg=50, ask="c")
check("a=7, b=9, gamma=50 -> c ≈ 7.00 (oficjalny przyklad)",
      sk_c["correct_text"] == "7.00", sk_c)
sk_p = build_safe_law_of_cosines_triangle(a=7, b=9, gamma_deg=50, ask="P")
check("a=7, b=9, gamma=50 -> P ≈ 24.13",
      sk_p["correct_text"] == "24.13", sk_p)

print()
print("=" * 70)
print("Poprawnosc na 1000 losowych probach (niezalezna sciezka obliczeniowa)")
print("=" * 70)
bad = []
for _ in range(1000):
    sk = build_safe_law_of_cosines_triangle()
    ok = verify_law_of_cosines_triangle(sk["a"], sk["b"], sk["gamma_deg"], sk["ask"], sk["correct_text"])
    if not ok:
        bad.append(sk)
check(f"1000/1000 poprawne (tolerancja +-0.01)", not bad, bad[:3] if bad else None)

print()
print("=" * 70)
print("Dystraktory - nigdy nie koliduja, NIGDY nie sa ujemne (real bug naprawiony)")
print("=" * 70)
collision = []
negative = []
for _ in range(1000):
    sk = build_safe_law_of_cosines_triangle()
    all_texts = [sk["correct_text"]] + sk["distractors"]
    if sk["correct_text"] in sk["distractors"] or len(set(all_texts)) != 4:
        collision.append(sk)
    for t in all_texts:
        if t.startswith("-"):
            negative.append((sk, t))
check("1000 prob - zero kolizji miedzy 4 opcjami", not collision, collision[:3] if collision else None)
check("1000 prob - ZERO ujemnych opcji (real bug: area_cos_confuse/area_rad_confuse dla katow rozwartych)",
      not negative, negative[:3] if negative else None)

print()
print("=" * 70)
print("Parametry zgodne z ustalonymi decyzjami (a,b w [4,15], katy 'nieladne')")
print("=" * 70)
range_ok = True
angle_ok = True
_SPECIAL = {30, 45, 60, 90, 120, 135, 150}
for _ in range(300):
    sk = build_safe_law_of_cosines_triangle()
    if not (4 <= sk["a"] <= 15 and 4 <= sk["b"] <= 15):
        range_ok = False
    if sk["gamma_deg"] in _SPECIAL:
        angle_ok = False
check("a,b zawsze w [4,15]", range_ok)
check("gamma NIGDY nie jest katem specjalnym (30/45/60/90/120/135/150)", angle_ok)

print()
print("=" * 70)
print("Gating: _is_hard_law_of_cosines (Quiz) - WASKO, samo 'cosinus'/'kosinus' + trudny")
print("=" * 70)
from app.openai_exam import _is_hard_law_of_cosines
check("'twierdzenie cosinusow' + trudny -> True",
      _is_hard_law_of_cosines("Matematyka: twierdzenie cosinusów", "trudny") is True)
check("'kosinusow' (alt. pisownia) + trudny -> True",
      _is_hard_law_of_cosines("prawo kosinusów", "trudny") is True)
check("'twierdzenie cosinusow' + srednia -> False (tylko trudny)",
      _is_hard_law_of_cosines("twierdzenie cosinusów", "srednia") is False)
check("'trojkat' bez 'cosinus' -> False (bezpieczny abstain, np. twierdzenie sinusow ma INNY wzor)",
      _is_hard_law_of_cosines("Geometria trojkata", "trudny") is False)
check("trygonometria (bez 'cosinus' w temacie) -> False (juz zajete przez inny archetyp)",
      _is_hard_law_of_cosines("Trygonometria", "trudny") is False)

print()
print("=" * 70)
print("Gating: _is_hard_law_of_cosines_exam (Sprawdzian) - identyczna logika")
print("=" * 70)
from app.exam_pdf_generator import _is_hard_law_of_cosines_exam
check("'twierdzenie cosinusow' + trudna -> True",
      _is_hard_law_of_cosines_exam("Matematyka: twierdzenie cosinusów", "trudna") is True)
check("'trojkat' bez 'cosinus' -> False",
      _is_hard_law_of_cosines_exam("Geometria trojkata", "trudna") is False)

print()
print("=" * 70)
print("Warstwa 2/2.5 EXEMPTION - dziedziczona automatycznie z 'safe_generated'")
print("=" * 70)
import asyncio
from app.openai_exam import _verify_and_fix_quiz_math

fake_safe_q = {
    "question": "W trójkącie a=7, b=9, gamma=50°. Oblicz c.",
    "options": ["7.00", "11.40", "14.53", "2.90"],
    "correct": 0, "final_answer": "7.00", "explanation": "test",
    "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"},
    "_safe_generated": True,
}
result = asyncio.run(_verify_and_fix_quiz_math({"questions": [dict(fake_safe_q)]}))
check("Pytanie _safe_generated (archetyp trojkata) -> zaakceptowane bez blind-check",
      len(result.get("questions", [])) == 1, result)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
