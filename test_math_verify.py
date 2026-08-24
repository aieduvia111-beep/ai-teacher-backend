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
    validate_quadratic_difficulty,
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


# ============================================================
# 5. validate_quadratic_difficulty - rownanie w OPCJACH, nie w tresci
# pytania ("Ktore z ponizszych rownan..." - residualny gap z Iteracji 2,
# naprawiony rozszerzeniem analyzera o przeszukiwanie option_texts).
# ============================================================
print()
print("=== Regresja: validate_quadratic_difficulty - rownanie w opcjach ===")

stem_options_only = "Które z poniższych równań ma dwa różne pierwiastki rzeczywiste?"
opts_equations_easy = ["$x^2-5x+6=0$", "$x^2+4=0$", "$x^2-2x+5=0$", "$x^2+9=0$"]

r = validate_quadratic_difficulty(stem_options_only, "easy")
check("rownanie TYLKO w opcjach, bez option_texts -> nadal not_quadratic (brak regresji)", r["status"] == "not_quadratic", r)

r = validate_quadratic_difficulty(stem_options_only, "easy", option_texts=opts_equations_easy)
check("rownanie TYLKO w opcjach, z option_texts -> juz NIE not_quadratic, faktycznie waliduje", r["status"] in ("ok", "fail"), r)
check("rownanie TYLKO w opcjach: wykryty pierwszy parsowalny wzorzec -> tier 1-2 (ladny rozklad)", r.get("detected_tier") == "1-2", r)
check("rownanie TYLKO w opcjach, 'easy' vs tier 1-2 -> ok", r["status"] == "ok", r)

r = validate_quadratic_difficulty(stem_options_only, "hard", option_texts=opts_equations_easy)
check("rownanie TYLKO w opcjach, 'hard' vs tier 1-2 -> fail (za latwe)", r["status"] == "fail" and r["detected_tier"] == "1-2", r)

# Rownanie w TRESCI pytania (dotychczasowy przypadek) dziala tak samo
# jak przed zmiana, niezaleznie od tego, czy przekazano option_texts.
# NAPRAWIONE (audyt realnej generacji V1, sierpien 2026): oryginalny
# fixture "x^2+(m-3)x+m=0" mial parametr WEWNATRZ WYRAZENIA jako
# wspolczynnik przy x ("(m-3)x") - realny test generacji pokazal, ze to
# podpasmo jest SYSTEMATYCZNIE zbyt trudne dla AI na poziomie "medium"
# (patrz nowy check w classify_quadratic_difficulty), wiec teraz slusznie
# klasyfikuje sie jako 7-8, nie 5-6 - zmieniono na fixture z GOLYM
# parametrem (bez zmiany celu tego testu: spojnosc tresc vs opcje).
stem_in_question = "Dla jakich wartości parametru $m$ równanie $x^2+mx+3=0$ ma dwa różne pierwiastki?"
r_no_opts = validate_quadratic_difficulty(stem_in_question, "medium")
r_with_opts = validate_quadratic_difficulty(stem_in_question, "medium", option_texts=["$m > 1$", "$m < 1$ lub $m > 9$", "tak", "nie"])
check("rownanie w tresci pytania: bez option_texts -> ok, tier 5-6 (brak regresji)", r_no_opts["status"] == "ok" and r_no_opts["detected_tier"] == "5-6", r_no_opts)
check("rownanie w tresci pytania: z option_texts -> ten sam wynik (tresc ma pierwszenstwo)", r_with_opts == r_no_opts, (r_no_opts, r_with_opts))

# Zwykle pytania z tekstowymi opcjami (bez rownan wcale, nawet gdy
# przekazano option_texts) nie generuja falszywych blokad.
r = validate_quadratic_difficulty("Kto napisał Pana Tadeusza?", "hard", option_texts=["Mickiewicz", "Słowacki", "Kochanowski", "Sienkiewicz"])
check("pytanie i opcje bez rownan -> not_quadratic, bez falszywej blokady", r["status"] == "not_quadratic", r)


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
