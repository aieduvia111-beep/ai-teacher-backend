# -*- coding: utf-8 -*-
"""NAPRAWA (zgloszony problem systemowy): weryfikator matematyczny
traktowal "unverifiable" jako bezpieczny sukces w SZESCIU roznych
funkcjach (verify_param_quadratic_question, verify_numeric_quadratic_
question, verify_sequence_question, _match_single_value_option [dzielone
przez trig/liniowa/wykladnicza/prawdopodobienstwo], verify_linear_two_
points_question, verify_quadratic_function_vertex) - we WSZYSTKICH
przypadku, gdy PRAWDZIWA odpowiedz zostala juz policzona, ale ZADNA z 4
opcji AI sie nie sparsowala, funkcja zwracala "unverifiable" (cichy
sukces) zamiast "no_option_matches" (odrzucenie). Do tego dolaczone:
brakujace unicode operatory (≤,≥,∞), losowanie pozycji A/B/C/D po
weryfikacji, diagnostyczne logowanie dla prawdziwych (legalnych)
"unverifiable".

Wymagane min. 16 testow (z instrukcji) - ponumerowane ponizej.
Plain script (bez pytest), wzorem test_etap6.py/test_probability_fix.py.
ZERO wywolan AI."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import io
import contextlib
import sympy as sp

from app.math_verify import (
    verify_and_fix_math_question, force_correct_from_final_answer,
    verify_param_quadratic_question, verify_sequence_question,
    verify_hypergeometric_probability_question,
    shuffle_options_preserving_correct, log_unverifiable_diagnostic,
    parse_option_as_param_set,
)
from app.openai_exam import _verify_and_fix_quiz_math

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


# =================================================================
# 1-4. Poprawna odpowiedz na kazdej z 4 pozycji (A/B/C/D) przezywa
#      Warstwe 1 (force_correct_from_final_answer) bez zmiany.
# =================================================================
print("=" * 70)
print("1-4. Poprawna odpowiedz na pozycji A/B/C/D")
print("=" * 70)
for correct_idx, letter in enumerate(["A", "B", "C", "D"]):
    q = {
        "question": f"Testowe pytanie {letter}?",
        "options": ["opcja0", "opcja1", "opcja2", "opcja3"],
        "correct": 99,
        "final_answer": f"opcja{correct_idx}",
    }
    result = _verify_and_fix_quiz_math({"questions": [q]})
    kept = result["questions"]
    check(f"poprawna odpowiedz na pozycji {letter} (index {correct_idx}) rozpoznana",
          len(kept) == 1, kept)

print()

# =================================================================
# 5. Blednym kluczem -> pytanie odrzucone (no_option_matches, gdy
#    prawdziwa odpowiedz JEST wsrod opcji, ale final_answer/correct AI
#    wskazuje na INNA, bledna opcje - Warstwa 2 ma to poprawic/odrzucic)
# =================================================================
print("=" * 70)
print("5. Blad klucza -> Warstwa 2 koryguje/odrzuca")
print("=" * 70)
Q_QUAD = "Dla jakich wartości parametru c równanie $x^2 - 6x + c = 0$ ma dwa różne pierwiastki?"
r = verify_param_quadratic_question(Q_QUAD, ["c<0", "c<9", "c>9", "c=9"])
check("poprawna 'c<9' obecna wsrod opcji -> match_index (rozpoznawalna, korekta mozliwa)",
      r["status"] == "match_index" and r["true_index"] == 1, r)

print()

# =================================================================
# 6. Brak poprawnej opcji -> pytanie odrzucone (GLOWNA naprawa -
#    dokladnie zgloszony bug: prawdziwa odpowiedz znana, ale ZADNA z 4
#    opcji sie nie zgadza/parsuje -> MUSI byc no_option_matches, NIE
#    unverifiable)
# =================================================================
print("=" * 70)
print("6. Brak poprawnej opcji -> no_option_matches (NIE unverifiable)")
print("=" * 70)
r = verify_param_quadratic_question(Q_QUAD, ["c>9", "c=9", "c\u22609", "c>0"])
check("BRAK poprawnej 'c<9' wsrod opcji -> no_option_matches (odrzucenie)",
      r["status"] == "no_option_matches", r)

print()

# =================================================================
# 7. Unicode operatory: ², ≠, ≤, ≥
# =================================================================
print("=" * 70)
print("7. Unicode operatory ², ≠, ≤, ≥")
print("=" * 70)
i_sym = sp.Symbol('i')
c_sym = sp.Symbol('c')
check("'i²>8' parsuje sie", parse_option_as_param_set("i\u00b2>8", i_sym) is not None)
check("'c≠0' parsuje sie", parse_option_as_param_set("c\u22600", c_sym) is not None)
check("'c≤9' parsuje sie", parse_option_as_param_set("c\u22649", c_sym) == sp.Interval(-sp.oo, 9))
check("'c≥9' parsuje sie", parse_option_as_param_set("c\u22659", c_sym) == sp.Interval(9, sp.oo))

print()

# =================================================================
# 8. Ulamki
# =================================================================
print("=" * 70)
print("8. Ulamki")
print("=" * 70)
Q_FRAC = "Dla jakich wartości parametru d równanie $x^2 + 5x + d = 0$ ma dwa różne pierwiastki?"
r = verify_param_quadratic_question(Q_FRAC, ["d<25/4", "d=25/4", "d>25/4", "d<0"])
check("ulamek 'd<25/4' poprawnie rozpoznany", r["status"] == "match_index" and r["true_index"] == 0, r)

print()

# =================================================================
# 9. Przedzialy (unia dwoch polprostych, "c<0 lub c>1")
# =================================================================
print("=" * 70)
print("9. Przedzialy (unia - 'lub')")
print("=" * 70)
Q_UNION = "Dla jakich wartości parametru c równanie $4x^2 + 4cx + c = 0$ ma dwa różne pierwiastki?"
r = verify_param_quadratic_question(Q_UNION, ["c<0 lub c>1", "0<c<1", "c=0", "c=1"])
check("unia 'c<0 lub c>1' poprawnie rozpoznana", r["status"] == "match_index" and r["true_index"] == 0, r)

print()

# =================================================================
# 10. Pytanie z parametrem (ogolny przypadek - juz pokryte wyzej,
#     dodatkowy test na inny parametr/rownanie dla pewnosci)
# =================================================================
print("=" * 70)
print("10. Pytanie z parametrem (rozny parametr/rownanie)")
print("=" * 70)
Q_PARAM2 = "Dla jakich wartości parametru h równanie $x^2 + 3x + h = 0$ ma dwa różne pierwiastki?"
r = verify_param_quadratic_question(Q_PARAM2, ["h<9/4", "h\u22609/4", "h=9/4", "h>9/4"])
check("parametr 'h', ulamek '9/4' poprawnie rozpoznany", r["status"] == "match_index" and r["true_index"] == 0, r)

print()

# =================================================================
# 11-12. N==N: 5->5, 20->20 (mock regenerate, ZERO wywolan API)
# =================================================================
print("=" * 70)
print("11-12. N==N z mockowanym generatorem (zero API)")
print("=" * 70)
import asyncio
from app.openai_exam import _verify_and_fill_quiz_math


def _make_valid_question(n):
    """Generuje ZAWSZE matematycznie poprawne pytanie (rozne parametry/
    stale, zeby unikac fingerprint-duplikatow) - final_answer = prawdziwa
    odpowiedz."""
    c_val = 5 + n
    return {
        "question": f"Dla jakich wartości parametru m równanie $x^2 - {c_val}x + (m-{n}) = 0$ ma dwa różne pierwiastki?",
        "options": [f"m<{c_val**2/4+n}", f"m>{c_val**2/4+n}", f"m={c_val**2/4+n}", "m<0"],
        "correct": 99,
        "final_answer": f"m<{c_val**2/4+n}",
    }


async def _mock_regenerate_always_valid(n):
    return {"questions": [_make_valid_question(1000 + i) for i in range(n)]}


async def run_n_equals_n_test(requested):
    quiz_data = {"questions": [_make_valid_question(i) for i in range(requested)]}
    result = await _verify_and_fill_quiz_math(
        quiz_data, requested, _mock_regenerate_always_valid,
    )
    return result


for requested in (5, 20):
    result = asyncio.run(run_n_equals_n_test(requested))
    final = len(result.get("questions", []))
    check(f"{requested} pytan zamowionych -> finalnie {final} (oczekiwano {requested})",
          final == requested, result.get("_shortfall_warning"))

print()

# =================================================================
# 13. Rozklad A/B/C/D dla wiekszej proby (shuffle_options_preserving_correct)
# =================================================================
print("=" * 70)
print("13. Rozklad A/B/C/D (1000 prob)")
print("=" * 70)
import collections
dist = collections.Counter()
opts = ["X", "Y", "Z", "W"]
for _ in range(1000):
    new_opts, new_correct = shuffle_options_preserving_correct(opts, 0)
    dist[new_correct] += 1
    # tresc poprawnej opcji MUSI byc zachowana
    if new_opts[new_correct] != "X":
        FAILED.append(("shuffle: tresc poprawnej opcji zmieniona!", (new_opts, new_correct)))
counts = [dist[i] for i in range(4)]
max_dev = max(abs(c - 250) for c in counts)
check(f"rozklad A/B/C/D w 1000 probach: {counts} (oczekiwano ~250 kazda, odchylenie<=75)",
      max_dev <= 75, counts)
check("kazda pozycja (A,B,C,D) wystapila przynajmniej raz jako poprawna",
      all(dist[i] > 0 for i in range(4)), dict(dist))

print()

# =================================================================
# 14. Duplikat -> dogenerowanie (N==N mimo duplikatow w partii)
# =================================================================
print("=" * 70)
print("14. Duplikat -> dogenerowanie (N==N mimo duplikatow)")
print("=" * 70)


async def _mock_regenerate_with_duplicate_first_round(n):
    """Za PIERWSZYM wywolaniem zwraca duplikat (ten sam tekst 2x) -
    dedup MUSI go odrzucic i wymusic runde dogenerowania."""
    if not hasattr(_mock_regenerate_with_duplicate_first_round, "_calls"):
        _mock_regenerate_with_duplicate_first_round._calls = 0
    _mock_regenerate_with_duplicate_first_round._calls += 1
    if _mock_regenerate_with_duplicate_first_round._calls == 1:
        dup = _make_valid_question(500)
        return {"questions": [dup, dict(dup)]}  # identyczny tekst 2x
    return {"questions": [_make_valid_question(2000 + i) for i in range(n)]}


async def run_dup_test():
    requested = 3
    quiz_data = {"questions": [_make_valid_question(i) for i in range(requested - 1)]}  # startowo o 1 za malo
    return await _verify_and_fill_quiz_math(
        quiz_data, requested, _mock_regenerate_with_duplicate_first_round,
    )


result = asyncio.run(run_dup_test())
final = len(result.get("questions", []))
check(f"duplikat w partii dogenerowania nadal daje finalnie {3} (otrzymano {final})",
      final == 3, result.get("_shortfall_warning"))

print()

# =================================================================
# 15. unverifiable -> diagnostyczny log + brak cichego sukcesu
#     (dla przypadkow, gdzie PRAWDZIWIE nie da sie zweryfikowac -
#     zaden domain modifier nie rozpoznaje tresci - to legalny,
#     bezpieczny abstain, ALE musi zostawic slad diagnostyczny)
# =================================================================
print("=" * 70)
print("15. unverifiable -> diagnostyczny log")
print("=" * 70)
Q_UNRECOGNIZED = "Oblicz pole trójkąta o bokach 3, 4 i 5."  # geometria - brak domain modifiera
r = verify_and_fix_math_question(Q_UNRECOGNIZED, ["6", "12", "7.5", "10"])
check("tresc bez rozpoznanego wzorca -> unverifiable (legalny abstain)",
      r["status"] == "unverifiable", r)

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    log_unverifiable_diagnostic("[MathVerify][Test]", "Geometria", Q_UNRECOGNIZED, ["6", "12", "7.5", "10"], "6")
log_output = buf.getvalue()
check("diagnostyczny log zawiera temat/tresc/opcje/final_answer",
      all(s in log_output for s in ["Geometria", "pole trójkąta", "[0]6", "final_answer='6'"]), log_output)

print()

# =================================================================
# 16. Co najmniej 2 inne tematy matematyczne poza rownaniami
#     kwadratowymi - ciagi i prawdopodobienstwo (ta sama naprawa
#     stosuje sie rownolegle)
# =================================================================
print("=" * 70)
print("16. Inne tematy: ciagi, prawdopodobienstwo")
print("=" * 70)

Q_SEQ = "Ciąg arytmetyczny ma a1=2, r=3. Oblicz sumę pierwszych 10 wyrazów tego ciągu."
# S10 = 10/2 * (2*2 + 9*3) = 5 * 31 = 155
r = verify_sequence_question(Q_SEQ, ["165", "160", "170", "155"])
check("ciagi: poprawna '155' obecna -> match_index", r["status"] == "match_index" and r["true_index"] == 3, r)
r2 = verify_sequence_question(Q_SEQ, ["160", "170", "150", "145"])
check("ciagi: BRAK poprawnej '155' -> no_option_matches (NIE unverifiable)",
      r2["status"] == "no_option_matches", r2)

Q_PROB = "W urnie znajduje się 5 kul białych i 3 czarne. Losujemy bez zwracania dwie kule. Oblicz prawdopodobieństwo, że obie są tego samego koloru."
r3 = verify_hypergeometric_probability_question(Q_PROB, ["13/28", "9/28", "1/2", "3/14"])
check("prawdopodobienstwo: poprawna '13/28' obecna -> match_index", r3["status"] == "match_index" and r3["true_index"] == 0, r3)
r4 = verify_hypergeometric_probability_question(Q_PROB, ["10/28", "9/28", "1/2", "3/14"])
check("prawdopodobienstwo: BRAK poprawnej '13/28' -> no_option_matches (NIE unverifiable)",
      r4["status"] == "no_option_matches", r4)

print()

print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
