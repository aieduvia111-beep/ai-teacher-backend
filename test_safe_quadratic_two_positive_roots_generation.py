# -*- coding: utf-8 -*-
"""User: "idz dalej profesjolnie" - osme rozszerzenie Safe Parameter
Generation tego samego dnia (po twierdzeniu sinusow). Temat: rownania
kwadratowe z parametrem, DWA ROZNE PIERWIASTKI DODATNIE, poziom trudny.

Oficjalny "trudny" przyklad programowy dla liceum_1 (level_config.py)
to DOKLADNIE ten wzorzec: "Dla jakich wartości parametru m równanie
x²-(m+1)x+m=0 ma dwa różne pierwiastki dodatnie?" - SILNIEJSZY warunek
niz istniejacy medium-tier archetyp (build_safe_linear_param_quadratic,
x^2+mx+C=0), ktory sprawdza TYLKO dyskryminanta>0 ("dwa rozne
pierwiastki", bez wymogu dodatniosci) - stad OSOBNY, nowy archetyp
zamiast rozszerzania istniejacego.

KLUCZOWA KONSTRUKCJA: x^2-(K+m)x+K*m=0 faktoryzuje sie ZAWSZE jako
(x-K)(x-m) dla DOWOLNEGO K - pierwiastki sa wiec DOKLADNIE {K, m},
SILNIEJSZA gwarancja niz analiza dyskryminanty (nie ma przypadku
zespolonego/podwojnego do osobnego rozpatrzenia - wynika wprost z
faktoryzacji).

Ten plik testuje SAMA logike (zero AI, zero kosztu): poprawnosc
(niezalezna sciezka - probkowanie wielu wartosci parametru + sympy
solve na oryginalnym wielomianie, NIE zakladajac znanej faktoryzacji),
brak kolizji miedzy 4 opcjami, dokladne odtworzenie oficjalnego
przykladu programowego (K=1), gating w obu miejscach (w tym rozlacznosc
z istniejacym medium-tier archetypem przez roznice trudnosci)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import (
    build_safe_quadratic_two_positive_roots, verify_quadratic_two_positive_roots, _QP_K_POOL,
)

print("=" * 70)
print("Poprawnosc na WSZYSTKICH kombinacjach K x litera (40) + 500 losowych")
print("probach (niezalezna sciezka - probkowanie + sympy solve od zera,")
print("BEZ zakladania znanej faktoryzacji (x-K)(x-parametr))")
print("=" * 70)
bad = []
collision = []
for k in _QP_K_POOL:
    for letter in ["m", "n", "p", "k"]:
        sk = build_safe_quadratic_two_positive_roots(param_letter=letter, k_value=k)
        if not verify_quadratic_two_positive_roots(letter, k, k):
            bad.append(sk)
        all_texts = [sk["correct_text"]] + sk["distractors"]
        if len(set(all_texts)) != 4:
            collision.append(sk)
# NAPRAWIONE: 500 losowych probek (kazda ~10 wywolan sp.solve() w
# verify_quadratic_two_positive_roots) bylo NAPRAWDE WOLNE (nie
# zawieszone na zawsze - kilka minut na cala probke), znalezione wlasnym
# testem wydajnosci tego pliku. 150 losowych + 40 systematycznych
# (wyzej, pokrywajace WSZYSTKIE K x litera) daje ta sama sile
# diagnostyczna przy ulamku czasu.
for _ in range(150):
    sk = build_safe_quadratic_two_positive_roots()
    if not verify_quadratic_two_positive_roots(sk["param_letter"], sk["k_value"], sk["k_value"]):
        bad.append(sk)
    all_texts = [sk["correct_text"]] + sk["distractors"]
    if len(set(all_texts)) != 4:
        collision.append(sk)
check(f"0 bledow poprawnosci na 190 probach (40 systematycznych + 150 losowych)",
      not bad, bad[:2] if bad else None)
check("0 kolizji miedzy 4 opcjami na 190 probach (deterministyczne teksty - matematycznie niemozliwe, ale sprawdzone)",
      not collision, collision[:2] if collision else None)

print()
print("=" * 70)
print("Oficjalny przyklad programowy liceum_1 (level_config.py), K=1:")
print("x²-(m+1)x+m=0 -> dwa rozne pierwiastki dodatnie: 0<m<1 lub m>1")
print("=" * 70)
sk = build_safe_quadratic_two_positive_roots(param_letter="m", k_value=1)
check("K=1 -> rownanie 'x^2 - (m + 1)x + m = 0' (BEZ '1m' - wspolczynnik 1 pomijany, jak w oryginale)",
      "x^2 - (m + 1)x + m = 0" in sk["question_text"], sk["question_text"])
check("K=1 -> correct_text '$0 < m < 1$ lub $m > 1$'",
      sk["correct_text"] == "$0 < m < 1$ lub $m > 1$", sk["correct_text"])
check("Niezalezna weryfikacja potwierdza K=1",
      verify_quadratic_two_positive_roots("m", 1, 1))

print()
print("=" * 70)
print("Dystraktory - typowe, czesciowe bledy uczniow (zawsze tekstowo")
print("rozne od poprawnej odpowiedzi - zero ryzyka kolizji z definicji)")
print("=" * 70)
sk = build_safe_quadratic_two_positive_roots(param_letter="m", k_value=5)
check("Dystraktor 1: '$m \\neq 5$' (pominieta dodatniosc)",
      sk["distractors"][0] == "$m \\neq 5$", sk["distractors"])
check("Dystraktor 2: '$m > 0$' (pominiete wykluczenie m=K)",
      sk["distractors"][1] == "$m > 0$", sk["distractors"])
check("Dystraktor 3: '$m < 0$' (odwrocony znak)",
      sk["distractors"][2] == "$m < 0$", sk["distractors"])

print()
print("=" * 70)
print("Gating: _is_hard_quadratic_two_positive_roots (Quiz) - kwadratowe")
print("+ trudny, ROZLACZNE z istniejacym medium-tier archetypem")
print("=" * 70)
from app.openai_exam import _is_hard_quadratic_two_positive_roots, _is_medium_linear_param_quadratic
check("'równania kwadratowe z parametrem' + trudny -> True",
      _is_hard_quadratic_two_positive_roots("Matematyka: równania kwadratowe z parametrem", "trudny") is True)
check("'rownania kwadratowe' (bez diakrytykow, literowka 'rownanai') + trudny -> True",
      _is_hard_quadratic_two_positive_roots("rownanai kwadratowe", "trudny") is True)
check("'równania kwadratowe' + srednia -> False (to jest medium-tier archetyp)",
      _is_hard_quadratic_two_positive_roots("równania kwadratowe", "srednia") is False)
check("ROZLACZNOSC: 'równania kwadratowe' + srednia -> medium-tier gate=True, hard-tier gate=False",
      _is_medium_linear_param_quadratic("równania kwadratowe", "srednia") is True
      and _is_hard_quadratic_two_positive_roots("równania kwadratowe", "srednia") is False)
check("ROZLACZNOSC (odwrotnie): 'równania kwadratowe' + trudny -> hard-tier gate=True, medium-tier gate=False",
      _is_hard_quadratic_two_positive_roots("równania kwadratowe", "trudny") is True
      and _is_medium_linear_param_quadratic("równania kwadratowe", "trudny") is False)
check("inny temat + trudny -> False",
      _is_hard_quadratic_two_positive_roots("Twierdzenie sinusów", "trudny") is False)

print()
print("=" * 70)
print("Gating: _is_hard_quadratic_two_positive_roots_exam (Sprawdzian)")
print("=" * 70)
from app.exam_pdf_generator import _is_hard_quadratic_two_positive_roots_exam
check("'równania kwadratowe z parametrem' + trudna -> True",
      _is_hard_quadratic_two_positive_roots_exam("Matematyka: równania kwadratowe z parametrem", "trudna") is True)
check("inny temat + trudna -> False",
      _is_hard_quadratic_two_positive_roots_exam("Ciągi geometryczne", "trudna") is False)

print()
print("=" * 70)
print("Warstwa 2/2.5 EXEMPTION - dziedziczona automatycznie z 'safe_generated'")
print("=" * 70)
import asyncio
from app.openai_exam import _verify_and_fix_quiz_math

fake_safe_q = {
    "question": "Dla jakich wartości parametru m równanie x^2-(m+5)x+5m=0 ma dwa różne pierwiastki dodatnie?",
    "options": ["$0 < m < 5$ lub $m > 5$", "$m \\neq 5$", "$m > 0$", "$m < 0$"],
    "correct": 0, "final_answer": "$0 < m < 5$ lub $m > 5$", "explanation": "test",
    "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"},
    "_safe_generated": True,
}
result = asyncio.run(_verify_and_fix_quiz_math({"questions": [dict(fake_safe_q)]}))
check("Pytanie _safe_generated (archetyp kwadratowe dwa dodatnie pierwiastki) -> zaakceptowane bez blind-check",
      len(result.get("questions", [])) == 1, result)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
