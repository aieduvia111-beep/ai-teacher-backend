# -*- coding: utf-8 -*-
"""NAPRAWA KRYTYCZNEGO BLEDU (zgloszony realny test): weryfikacja rownan
kwadratowych z parametrem (parse_option_as_param_set / verify_param_
quadratic_question) nie rozpoznawala unicode "≠" (U+2260, tylko ASCII
"!=") ani unicode superscript "²"/"³" (np. "e²>1") - gdy WSZYSTKIE 4
opcje AI zawieraly ktorys z tych znakow, ZADNA sie nie parsowala,
`any_option_parsed=False`, weryfikator zwracal "unverifiable" i pytanie
przechodzilo BEZ WETA, nawet jesli AI podalo matematycznie bledna
odpowiedz (potwierdzony przypadek: AI "c≠0 i c<1" zamiast poprawnego
"c<0 lub c>1"; "e≠0 i e>1" zamiast "e²>1"; "f≠0" zamiast "f²>24").

NAPRAWA: _clean_latex (jedyny wspolny punkt normalizacji przed
parse_expr w calej sciezce rownan kwadratowych) teraz zamienia "≠"->"!="
i unicode superscript->"^N" (uzywajac juz istniejacego _SUPERSCRIPT_RE/
_SUPERSCRIPT_MAP z Etapu 8). ZERO zmian w logice rozwiazywania rownan,
difficulty tiers, promptach, limitach API/retry/N=N.

Plain script (bez pytest), wzorem test_probability_fix.py. ZERO
wywolan AI - wszystko lokalne."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import sympy as sp

from app.math_verify import parse_option_as_param_set, verify_param_quadratic_question

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


# =================================================================
# 1. parse_option_as_param_set: pojedyncze teksty opcji (jak w zgloszeniu)
# =================================================================
print("=" * 70)
print("1. parse_option_as_param_set: unicode ≠/² teraz parsuja sie poprawnie")
print("=" * 70)

c, e, f = sp.symbols('c e f')

r = parse_option_as_param_set("c\u22600", c)
check("'c≠0' parsuje sie (nie None)", r is not None, r)
check("'c≠0' == R\\{0}", r == (sp.S.Reals - sp.FiniteSet(0)) if r is not None else False, r)

r = parse_option_as_param_set("e\u00b2>1", e)
check("'e²>1' parsuje sie (nie None)", r is not None, r)
check("'e²>1' == (-oo,-1)∪(1,oo)", r == sp.Union(sp.Interval.open(-sp.oo, -1), sp.Interval.open(1, sp.oo)) if r is not None else False, r)

r = parse_option_as_param_set("f\u00b2>24", f)
check("'f²>24' parsuje sie (nie None)", r is not None, r)
expected_f = sp.Union(sp.Interval.open(-sp.oo, -2 * sp.sqrt(6)), sp.Interval.open(2 * sp.sqrt(6), sp.oo))
check("'f²>24' == (-oo,-2√6)∪(2√6,oo)", r == expected_f if r is not None else False, r)

r = parse_option_as_param_set("c<0 lub c>1", c)
check("'c<0 lub c>1' nadal parsuje sie poprawnie (bez regresji)",
      r == sp.Union(sp.Interval.open(-sp.oo, 0), sp.Interval.open(1, sp.oo)), r)

r = parse_option_as_param_set("c<4", c)
check("'c<4' nadal parsuje sie poprawnie (bez regresji)", r == sp.Interval.open(-sp.oo, 4), r)

r = parse_option_as_param_set("c>-4", c)
check("'c>-4' nadal parsuje sie poprawnie (bez regresji)", r == sp.Interval.open(-4, sp.oo), r)

# "c≠0 i c<1" (zlozony warunek AND z Polskim 'i') - CELOWO POZA ZAKRESEM
# tej naprawy (parsowanie AND-compound to logika, nie normalizacja
# unicode) - ale NIE MA to juz znaczenia dla calosciowego wyniku pytania,
# bo INNE opcje juz sie parsuja (patrz sekcja 3).
r = parse_option_as_param_set("c\u22600 i c<1", c)
check("'c≠0 i c<1' (AND-compound) nadal None - swiadomie poza zakresem tej naprawy", r is None, r)

print()

# =================================================================
# 2. Dokladne zgloszone przypadki testowe (z instrukcji)
# =================================================================
print("=" * 70)
print("2. Dokladne zgloszone przypadki")
print("=" * 70)

for text, param, name in [
    ("c\u22600", c, "c≠0"),
    ("e\u00b2>1", e, "e²>1"),
    ("f\u00b2>24", f, "f²>24"),
    ("c<0 lub c>1", c, "c<0 lub c>1"),
    ("c<4", c, "c<4"),
    ("c>-4", c, "c>-4"),
]:
    r = parse_option_as_param_set(text, param)
    check(f"'{name}' parsuje sie (poza swiadomie wykluczonym AND-compound)", r is not None, r)

print()

# =================================================================
# 3. Pelny przeplyw verify_param_quadratic_question - dokladnie
#    zgloszony scenariusz: poprawna odpowiedz NIE jest wsrod 4 opcji
#    (tylko bledne warianty AI) - PRZED naprawa: unverifiable (bez weta).
#    PO naprawie: no_option_matches (odrzucenie, jak powinno byc).
# =================================================================
print("=" * 70)
print("3. Pelny przeplyw: verify_param_quadratic_question")
print("=" * 70)

# 4x^2+4cx+c=0 -> delta=16(c^2-c)>0 -> c<0 lub c>1
Q_C = "Dla jakich wartości parametru c równanie $4x^2 + 4cx + c = 0$ ma dwa różne pierwiastki?"

r = verify_param_quadratic_question(Q_C, ["c<0 lub c>1", "c\u22600 i c<1", "c>1", "c<0"])
check("poprawna opcja 'c<0 lub c>1' WSROD 4 -> match_index (rozpoznana)",
      r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_param_quadratic_question(Q_C, ["c\u22600 i c<1", "c>1", "c<0", "c=0"])
check("BRAK poprawnej opcji wsrod 4 (dokladnie zgloszony bug) -> no_option_matches (NIE unverifiable!)",
      r["status"] == "no_option_matches", r)

# x^2+2x+(2-e^2)=0 -> delta=4(e^2-1)>0 -> e^2>1 -> (-oo,-1)∪(1,oo)
Q_E = "Dla jakich wartości parametru e równanie $x^2 + 2x + (2 - e^2) = 0$ ma dwa różne pierwiastki?"

r = verify_param_quadratic_question(Q_E, ["e\u00b2>1", "e\u22600 i e>1", "e>1", "e<1"])
check("poprawna opcja 'e²>1' WSROD 4 -> match_index (rozpoznana)",
      r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_param_quadratic_question(Q_E, ["e\u22600 i e>1", "e>1", "e<1", "e=0"])
check("BRAK poprawnej opcji 'e²>1' wsrod 4 -> no_option_matches (NIE unverifiable!)",
      r["status"] == "no_option_matches", r)

# Bledna odpowiedz NIGDY nie zostaje uznana za poprawna, nawet gdy jest
# JEDYNA opcja ktora sie parsuje (bo inne tez zawieraja unicode ≠) -
# dopoki nie zgadza sie matematycznie z true_set.
r = verify_param_quadratic_question(Q_C, ["c\u22600 i c<1", "c<0 lub c>1", "c<0", "c>0"])
check("bledna 'c≠0 i c<1' (nieparsowalna) NIGDY nie jest false-positive matched",
      not (r["status"] == "match_index" and r.get("true_index") == 0), r)

print()

print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
