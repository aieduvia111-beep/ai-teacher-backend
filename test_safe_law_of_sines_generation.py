# -*- coding: utf-8 -*-
"""User: "idziemy dalej rob to dobrze prosze" - szoste rozszerzenie
Safe Parameter Generation tego samego dnia (po wartosci bezwzglednej).
Temat: twierdzenie sinusow, poziom trudny. "twierdzenie sinus" jest
JAWNIE wymienione jako dozwolony temat liceum_2/technikum_3 w
GENERIC_TOPIC_KEYWORDS (level_config.py) - grounded, nie wymyslony.

SWIADOMA REDUKCJA ZAKRESU (ujawniona userowi w kodzie i tutaj):
przypadek SSA (dwa boki + kat NIE miedzy nimi) jest w ogolnosci
NIEJEDNOZNACZNY ("przypadek dwuznaczny" - 0/1/2 rozwiazania). Zbudowano
zamiast tego dwa katy + bok naprzeciw jednego z nich (ASA/AAS) - trzeci
kat wyznaczony jednoznacznie (180-A-B), wiec caly trojkat (i szukany
bok) jest ZAWSZE jednoznaczny - zero ryzyka dwuznacznosci.

Ten plik testuje SAMA logike (zero AI, zero kosztu): poprawnosc
(niezalezna sciezka weryfikacji), brak kolizji miedzy 4 opcjami, gating
w obu miejscach, wyjatek dla twierdzenia cosinusow (rozlaczne archetypy)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import build_safe_law_of_sines_triangle, verify_law_of_sines_triangle

print("=" * 70)
print("Poprawnosc + brak kolizji na 2000 losowych probach (niezalezna")
print("sciezka - liczy b od zera z surowych parametrow)")
print("=" * 70)
none_count = 0
bad = []
collision = []
for _ in range(2000):
    sk = build_safe_law_of_sines_triangle()
    if sk is None:
        none_count += 1
        continue
    if not verify_law_of_sines_triangle(sk["a"], sk["angle_a_deg"], sk["angle_b_deg"], sk["correct_text"]):
        bad.append(sk)
    all_texts = [sk["correct_text"]] + sk["distractors"]
    if len(set(all_texts)) != 4:
        collision.append(sk)
check("build_safe_law_of_sines_triangle nigdy nie zwraca None (max_tries=100 wystarcza)",
      none_count == 0, none_count)
check(f"{2000 - len(bad)}/2000 poprawne (b zgadza sie z niezalezna weryfikacja +-0.01)",
      not bad, bad[:2] if bad else None)
check("2000 prob - zero kolizji miedzy 4 opcjami (w tym degeneraty A=B/sin(A)=sin(B))",
      not collision, collision[:2] if collision else None)

print()
print("=" * 70)
print("Przyklad recznie zweryfikowany: A=50°, B=75°, a=7 -> b=a*sin(B)/sin(A)")
print("=" * 70)
sk = build_safe_law_of_sines_triangle(a=7, angle_a_deg=50, angle_b_deg=75)
check("A=50°, B=75°, a=7 -> b=8.83 (7*sin(75°)/sin(50°) ≈ 7*0.9659/0.7660 ≈ 8.827)",
      sk is not None and sk["correct_text"] == "8.83", sk)
check("Weryfikacja niezalezna potwierdza ten sam wynik",
      sk is not None and verify_law_of_sines_triangle(7, 50, 75, "8.83"))

print()
print("=" * 70)
print("Zdegenerowany trojkat (A+B>=175°) jest ODRZUCANY (retry na inne")
print("losowe katy), nie generuje bezsensownego, prawie-plaskiego trojkata")
print("=" * 70)
sk_degenerate_forced = build_safe_law_of_sines_triangle(a=7, angle_a_deg=155, angle_b_deg=100, max_tries=1)
check("A=155°,B=100° (suma 255°>=175°) z max_tries=1 -> None (odrzucone, brak retry do sukcesu)",
      sk_degenerate_forced is None, sk_degenerate_forced)

print()
print("=" * 70)
print("Gating: _is_hard_law_of_sines (Quiz) - samo 'sinus', ROZLACZNE z")
print("twierdzeniem cosinusow (juz ma WLASNY archetyp)")
print("=" * 70)
from app.openai_exam import _is_hard_law_of_sines
check("'twierdzenie sinusów' + trudny -> True",
      _is_hard_law_of_sines("Matematyka: twierdzenie sinusów", "trudny") is True)
check("'twierdzenie sinusow' (bez diakrytykow) + trudny -> True",
      _is_hard_law_of_sines("twierdzenie sinusow", "trudny") is True)
check("'twierdzenie sinusów' + srednia -> False (zla trudnosc)",
      _is_hard_law_of_sines("twierdzenie sinusów", "srednia") is False)
check("'twierdzenie cosinusów' + trudny -> False (ROZLACZNE - to inny, juz istniejacy archetyp)",
      _is_hard_law_of_sines("twierdzenie cosinusów", "trudny") is False)
check("'twierdzenie kosinusów' (polska pisownia) + trudny -> False (ta sama wylaczenie)",
      _is_hard_law_of_sines("twierdzenie kosinusów", "trudny") is False)
check("inny temat + trudny -> False",
      _is_hard_law_of_sines("Ciągi arytmetyczne", "trudny") is False)

print()
print("=" * 70)
print("Gating: _is_hard_law_of_sines_exam (Sprawdzian) - identyczna logika")
print("=" * 70)
from app.exam_pdf_generator import _is_hard_law_of_sines_exam
check("'twierdzenie sinusów' + trudna -> True",
      _is_hard_law_of_sines_exam("Matematyka: twierdzenie sinusów", "trudna") is True)
check("'twierdzenie cosinusów' + trudna -> False (ROZLACZNE)",
      _is_hard_law_of_sines_exam("twierdzenie cosinusów", "trudna") is False)
check("inny temat + trudna -> False",
      _is_hard_law_of_sines_exam("Prawdopodobieństwo", "trudna") is False)

print()
print("=" * 70)
print("Warstwa 2/2.5 EXEMPTION - dziedziczona automatycznie z 'safe_generated'")
print("=" * 70)
import asyncio
from app.openai_exam import _verify_and_fix_quiz_math

fake_safe_q = {
    "question": "W trójkącie kąt A=50°, kąt B=75°, bok a=7. Oblicz długość boku b.",
    "options": ["8.83", "5.55", "7.49", "2.82"],
    "correct": 0, "final_answer": "8.83", "explanation": "test",
    "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"},
    "_safe_generated": True,
}
result = asyncio.run(_verify_and_fix_quiz_math({"questions": [dict(fake_safe_q)]}))
check("Pytanie _safe_generated (archetyp tw. sinusow) -> zaakceptowane bez blind-check",
      len(result.get("questions", [])) == 1, result)

print()
print("=" * 70)
print("Regresja _fix_latex (Sprawdzian): AI czasem uzywa '\\( \\)'/'\\[ \\]'")
print("zamiast '$...$' - _render_math_png rozpoznaje TYLKO '$' jako")
print("granice matematyki, wiec bez konwersji cala zawartosc renderowala")
print("sie jako DOSLOWNY tekst (real PNG z tego archetypu to pokazal,")
print("bez zadnego wyjatku/bledu w logach - czysto kosmetyczny blad)")
print("=" * 70)
from app.exam_pdf_generator import _fix_latex

check("'\\( \\frac{a}{b} \\)' -> '$ \\frac{a}{b} $' (konwersja na granice '$')",
      _fix_latex(r"\( \frac{a}{b} \)") == r"$ \frac{a}{b} $", _fix_latex(r"\( \frac{a}{b} \)"))
check("'\\[ x=1 \\]' -> '$ x=1 $'",
      _fix_latex(r"\[ x=1 \]") == r"$ x=1 $", _fix_latex(r"\[ x=1 \]"))
check("Juz-poprawne '$...$' NIE jest dotykane (regresja)",
      _fix_latex("$x=1$") == "$x=1$", _fix_latex("$x=1$"))

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
