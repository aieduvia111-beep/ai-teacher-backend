"""
Test regresyjny app/math_verify.py (weryfikacja sympy kluczy odpowiedzi
dla rownan kwadratowych i ciagow arytmetycznych/geometrycznych) +
mechanizmu final_answer.

Uruchom: python test_math_verify.py

Sprawdza:
1. Zgloszony crash "Can only compare inequalities with Expr" - opcja
   z PODWOJNA nierownoscia (np. "0 < m < 2") juz nie wywala wyjatku.
2. _parse_relational_list poprawnie rozbija podwojne nierownosci na
   przeciecie dwoch relacji (kilka wariantow operatorow).
3. Wszystkie przypadki znalezionych w tej sesji blednych kluczy
   odpowiedzi (rownania kwadratowe z parametrem, rownania liczbowe,
   ciagi arytmetyczne/geometryczne) - upewniamy sie ze fix nie
   wprowadzil regresji w tym, co juz dzialalo.
4. force_correct_from_final_answer / match_final_answer_index -
   dopasowanie, brak dopasowania, wieloznacznosc, brak final_answer.
"""
import sys
sys.path.insert(0, ".")

from app.math_verify import (
    verify_and_fix_math_question,
    _parse_relational_list,
    force_correct_from_final_answer,
    match_final_answer_index,
)

FAILED = []


def check(name, condition, detail=""):
    if condition:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


# ============================================================
# 1-2. Crash "Can only compare inequalities with Expr" - odtworzony
# realny przypadek z produkcji (patrz commit) + warianty operatorow.
# ============================================================
print("=== Podwojne nierownosci w opcjach (zgloszony crash) ===")

q_crash = (
    "Dla jakich wartości parametru $m$ równanie $x^2 - (m+1)x + m = 0$ "
    "ma dwa różne pierwiastki rzeczywiste, z których jeden jest mniejszy "
    "od 1, a drugi większy od 1?"
)
opts_crash = ["$m > 2$", "$m < 0$", "$m > 0$", "$0 < m < 2$"]
try:
    result = verify_and_fix_math_question(q_crash, opts_crash)
    check("realny przypadek z produkcji nie rzuca wyjatku", True)
    check("zwraca poprawny status (nie crash)", result["status"] in ("no_option_matches", "match_index", "unverifiable"), result)
except Exception as e:
    check("realny przypadek z produkcji nie rzuca wyjatku", False, repr(e))

import sympy as sp
m = sp.Symbol("m")

cases = [
    ("0 < m < 2", sp.Interval.open(0, 2)),
    ("-1 <= m <= 5", sp.Interval(-1, 5)),
    ("0 < m <= 4", sp.Interval.Lopen(0, 4)),
    ("-3 <= m < 0", sp.Interval.Ropen(-3, 0)),
]
for text, expected_interval in cases:
    rels = _parse_relational_list(text)
    ok = rels is not None and len(rels) == 2
    if ok:
        sets = [sp.solveset(rel, m, domain=sp.S.Reals) for rel in rels]
        combined = sets[0].intersect(sets[1])
        ok = combined == expected_interval
    check(f"_parse_relational_list('{text}') rozbija na 2 relacje AND", ok, rels)

# Zwykle (pojedyncze) nierownosci nadal dzialaja jak wczesniej.
for text in ["m < 3", "m >= -2", "m != 5", "m = 4"]:
    rels = _parse_relational_list(text)
    check(f"_parse_relational_list('{text}') zwraca 1 relacje", rels is not None and len(rels) == 1, rels)


# ============================================================
# 3. Regresja - przypadki znalezione w tej sesji (rownania kwadratowe
# z parametrem, rownania liczbowe, ciagi).
# ============================================================
print()
print("=== Regresja: rownania kwadratowe z parametrem ===")

r = verify_and_fix_math_question(
    'Dla jakich wartości parametru $m$ równanie $x^2 + (m-3)x + m = 0$ ma dwa różne pierwiastki rzeczywiste?',
    ['$m > 3$', '$m < 3$', '$m \\neq 3$', '$m = 3$'],
)
check("param quiz Q1: prawdziwa odpowiedz NIE jest wsrod opcji -> no_option_matches", r["status"] == "no_option_matches", r)

r = verify_and_fix_math_question(
    'Dla jakich wartości parametru $m$ równanie $x^2 - 4x + m = 0$ ma dwa różne pierwiastki rzeczywiste?',
    ['a) $m > 4$', 'b) $m < 4$', 'c) $m = 4$', 'd) $m \\leq 4$'],
)
check("param exam Q1: AI mial racje -> match_index=1", r["status"] == "match_index" and r["true_index"] == 1, r)

print()
print("=== Regresja: rownania liczbowe (bez parametru) ===")

r = verify_and_fix_math_question(
    'Rozwiąż równanie kwadratowe $x^2 - 5x + 6 = 0$',
    ['$x = 2$ i $x = 3$', '$x = -2$ i $x = -3$', '$x = 1$ i $x = 6$', '$x = -1$ i $x = -6$'],
)
check("numeric quiz: poprawna odpowiedz wsrod opcji -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_and_fix_math_question(
    'Rozwiąż równanie kwadratowe $2x^2 - 3x - 2 = 0$',
    ['$x = -1$ i $x = 3/2$', '$x = 1$ i $x = -2$', '$x = 1/2$ i $x = -2$', '$x = 2$ i $x = -3/2$'],
)
check("numeric quiz: zadna opcja nie pasuje -> no_option_matches", r["status"] == "no_option_matches", r)

print()
print("=== Regresja: ciagi arytmetyczne/geometryczne ===")

r = verify_and_fix_math_question(
    'Dany jest ciąg arytmetyczny, w którym pierwszy wyraz wynosi $a_1 = 5$, a różnica wynosi $r = 3$. Oblicz sumę pierwszych 10 wyrazów tego ciągu.',
    ['$245$', '$185$', '$155$', '$205$'],
)
check("sequence sum_given_n: AI mial zle -> match_index=1 (poprawka)", r["status"] == "match_index" and r["true_index"] == 1, r)

r = verify_and_fix_math_question(
    'Dla ciągu arytmetycznego (a_n) dane są: $a_3 = 10$ i $a_7 = 22$. Znajdź pierwszy wyraz $a_1$ oraz różnicę $r$ tego ciągu.',
    ['$a_1 = 4$, $r = 2$', '$a_1 = 6$, $r = 4$', '$a_1 = 2$, $r = 3$', '$a_1 = 8$, $r = 3$'],
)
check("sequence two_term_to_a1_ratio: zadna opcja nie pasuje -> no_option_matches", r["status"] == "no_option_matches", r)

r = verify_and_fix_math_question(
    'Oblicz liczbę wyrazów ciągu arytmetycznego, w którym pierwszy wyraz wynosi $a_1 = 7$, różnica $r = 3$, a ostatni wyraz $a_n = 55$.',
    ['$17$', '$16$', '$15$', '$18$'],
)
check("sequence find_n_from_last_term: AI mial racje -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_and_fix_math_question(
    'Dany jest ciąg arytmetyczny o pierwszym wyrazie $a_1 = 3$ i różnicy $r = 5$. Oblicz 10-ty wyraz tego ciągu.',
    ['$a_{10} = 48$', '$a_{10} = 50$', '$a_{10} = 53$', '$a_{10} = 55$'],
)
check("sequence find_nth_term: AI mial zle -> match_index=0 (poprawka)", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_and_fix_math_question(
    'Dany jest ciąg geometryczny, w którym $a_1 = 2$, a iloraz wynosi $q = 3$. Oblicz sumę pierwszych 4 wyrazów tego ciągu.',
    ['$80$', '$54$', '$60$', '$70$'],
)
check("sequence geometric sum: AI mial racje -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

# Bezpieczenstwo - tresc niematematyczna nie crashuje i zwraca unverifiable.
r = verify_and_fix_math_question("Kto napisał Pana Tadeusza?", ["Mickiewicz", "Słowacki", "Kochanowski", "Sienkiewicz"])
check("tresc niematematyczna -> unverifiable, bez crasha", r["status"] == "unverifiable", r)


# ============================================================
# 4. final_answer -> correct (Warstwa 1)
# ============================================================
print()
print("=== Regresja: final_answer -> correct (Warstwa 1) ===")

q = {"options": ["$x = 2$", "$x = -2$", "$x = \\pm 2$", "$x = 4$"], "correct": 0, "final_answer": "$x = \\pm 2$"}
status = force_correct_from_final_answer(q)
check("final_answer dopasowany -> forced + correct nadpisany", status == "forced" and q["correct"] == 2, (status, q["correct"]))

status, idx = match_final_answer_index("zzz", ["a", "b", "c", "d"])
check("final_answer bez dopasowania -> no_match", status == "no_match" and idx is None, (status, idx))

status, idx = match_final_answer_index("5", ["5", "5", "6"])
check("final_answer pasuje do 2 opcji -> ambiguous", status == "ambiguous" and idx is None, (status, idx))

status, idx = match_final_answer_index(None, ["a", "b"])
check("brak final_answer -> no_final_answer", status == "no_final_answer" and idx is None, (status, idx))

status, idx = match_final_answer_index("b) $m < 4$", ["a) $m > 4$", "b) $m < 4$", "c) $m = 4$", "d) $m <= 4$"])
check("final_answer z prefiksem litery (Sprawdzian) dopasowany", status == "forced" and idx == 1, (status, idx))


print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
    sys.exit(0)
