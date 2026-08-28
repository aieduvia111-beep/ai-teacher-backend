# -*- coding: utf-8 -*-
"""User zglosil Sprawdzian z ciagow z 3 powaznymi bledami naraz:
1. Pytanie 1 - tresc URWANA w polowie zdania (podejrzenie: max_tokens).
2. Pytanie 2 - literalny znak "$" w tekscie ("n$").
3. Pytanie 7 - BLEDNA matematyka: bn=k^n, poprawny k=4, system oznaczyl
   k=2, z NIELOGICZNYM wyjasnieniem "Zatem k=4, co daje k=2".

Diagnoza (patrz odpowiedzi ponizej + kod):

ZADANIE 1 (dlaczego Warstwa 1 nie zlapala sprzecznosci wyjasnienie/
odpowiedz): match_final_answer_index() porownuje WYLACZNIE final_answer
z opcjami - NIE MA dostepu do tresci "wyjasnienie" i nigdy nie mial -
to poza jej zakresem z definicji, nie regresja. Realnym brakiem bylo
ZERO pokrycia Warstwy 2 (sympy) dla tego podwzorca - naprawione w
ZADANIU 2 ponizej.

ZADANIE 2: dodano verify_geometric_power_form_ratio (math_verify.py) -
minimalny, bezpieczny weryfikator dla b_n=k^n + "iloraz rowny X" -> k=X.

ZADANIE 3: max_tokens dla Sprawdzianu podniesiony z 600/pytanie do
750/pytanie (sufit z 10000 do 12000) - defensywny margines bezpieczenstwa
(OpenAI liczy oplate za FAKTYCZNIE zuzyte tokeny, nie za sufit). Dodano
tez diagnostyke finish_reason='length', zeby przyszle ewentualne uciecia
byly natychmiast widoczne w logu, nie wymagaly zgadywania.

ZADANIE 4: _strip_mistaken_dollar_pairs (exam_pdf_generator.py +
openai_exam.py) blednie usuwala poprawna pare "$n$" (pojedyncza litera
zmiennej, bez cyfry/operatora) jako "pomylkowy dolar", co kaskadowo
niszczylo KOLEJNA, oddzielna pare "$n$" dalej w tekscie - naprawione
przez rozpoznawanie pojedynczej litery jako poprawnej matematyki.

Wszystkie testy ponizej sa JEDNOSTKOWE (zero wywolan AI) - zgodnie z
prosba usera o oszczedzanie kosztow. Real-test (JEDEN, na koniec calej
naprawy) potwierdza wszystkie 3 razem w realnej generacji."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("ZADANIE 1 (diagnostyka, brak kodu do naprawy): Warstwa 1 nie ma")
print("dostepu do 'wyjasnienie' - to poza jej zakresem z definicji")
print("=" * 70)
from app.math_verify import match_final_answer_index
import inspect
src = inspect.getsource(match_final_answer_index)
check("match_final_answer_index NIE odwoluje sie do 'wyjasnienie' (poza zakresem z definicji)",
      "wyjasnienie" not in src, None)

print()
print("=" * 70)
print("ZADANIE 2: verify_geometric_power_form_ratio (b_n=k^n, iloraz)")
print("=" * 70)
from app.math_verify import verify_and_fix_math_question, verify_geometric_power_form_ratio

# DOKLADNY zgloszony przypadek (Pytanie 7)
q7 = "Dla jakich wartości parametru k ciąg geometryczny $b_n = k^n$ ma iloraz równy 4?"
opts7 = ["2", "4", "8", "16"]
r7 = verify_and_fix_math_question(q7, opts7)
check("Pytanie 7 (dokladny zgloszony przypadek): true_index=1 (k=4), NIE k=2",
      r7["status"] == "match_index" and r7["true_index"] == 1, r7)

# Wariant z inna litera bazowa i innym parametrem
q7b = "Ciąg geometryczny $a_n = q^n$ ma iloraz wynosi 3. Ile wynosi q?"
r7b = verify_and_fix_math_question(q7b, ["1", "2", "3", "9"])
check("Wariant (a_n=q^n, 'iloraz wynosi 3') -> true_index=2 (q=3)",
      r7b["status"] == "match_index" and r7b["true_index"] == 2, r7b)

# Regresja: NIE powinien lapac arytmetycznych/innych ksztaltow
q_arith = "Dla jakich wartości parametru k ciąg arytmetyczny a_n = k^n jest rosnący?"
r_arith = verify_geometric_power_form_ratio(q_arith, ["k>0", "k<0", "k=0", "k=1"])
check("Regresja: ciag ARYTMETYCZNY (nie geometryczny) w tej samej formie -> abstain",
      r_arith["status"] == "unverifiable", r_arith)

q_terms = "Ciąg geometryczny (b_n), gdzie b1 = 3 i b2 = 3k, jest malejący."
r_terms = verify_geometric_power_form_ratio(q_terms, ["k>1", "k<1", "k=1", "k<=0"])
check("Regresja: ciag geometryczny z KONKRETNYMI wyrazami (nie formula k^n) -> abstain (obsluguje to inna galaz)",
      r_terms["status"] == "unverifiable", r_terms)

r_unrelated = verify_and_fix_math_question(
    "Ciąg arytmetyczny ma a3=11 i a7=27. Znajdź pierwszy wyraz.",
    ["a1=3, r=4", "a1=5, r=3", "a1=7, r=2", "a1=9, r=1"]
)
check("Regresja: zupelnie inny (juz istniejacy) podwzorzec ciagow nadal dziala",
      r_unrelated["status"] == "match_index" and r_unrelated["true_index"] == 0, r_unrelated)

print()
print("=" * 70)
print("ZADANIE 3: max_tokens Sprawdzianu podniesiony (defensywny margines)")
print("=" * 70)
import re as re_mod
with open(r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend\app\exam_pdf_generator.py", encoding="utf-8") as f:
    src_exam = f.read()
check("max_tokens formula podniesiona z 600/pytanie do 750/pytanie",
      "750 * liczba_pytan" in src_exam, None)
check("sufit podniesiony z 10000 do 12000",
      "min(12000, max(5500, 750 * liczba_pytan))" in src_exam, None)
check("dodana diagnostyka finish_reason='length' (widocznosc na przyszlosc)",
      'finish_reason == "length"' in src_exam, None)

print()
print("=" * 70)
print("ZADANIE 4: literalny '$' (np. 'n$') - _strip_mistaken_dollar_pairs")
print("=" * 70)
from app.exam_pdf_generator import _strip_mistaken_dollar_pairs as _strip_exam, _fix_latex
from app.openai_exam import _strip_mistaken_dollar_pairs as _strip_quiz

# DOKLADNY zgloszony przypadek (Pytanie 1 i 2 z jednego tekstu, 2x "$n$")
t_real = ("Oblicz sumę pierwszych $n$ wyrazów ciągu arytmetycznego, którego pierwszy "
          "wyraz wynosi 2, a różnica wynosi 3. Dla jakiego $n$ suma wynosi 50?")
out_exam = _strip_exam(t_real)
check("Sprawdzian: oba '$n$' przetrwaly NIENARUSZONE (0 literalnych 'n$' bez pary)",
      out_exam.count("$n$") == 2 and "n$" not in out_exam.replace("$n$", ""), out_exam)

out_quiz = _strip_quiz(t_real)
check("Quiz: identyczna naprawa (port) - oba '$n$' nienaruszone",
      out_quiz.count("$n$") == 2, out_quiz)

# Drugi realny przyklad z tego samego sprawdzianu (opcje odpowiedzi)
t_opts = "a) Tak, dla każdego $n$"
check("Opcja z pojedynczym '$n$' na koncu stringu nadal poprawna",
      _strip_exam(t_opts) == t_opts, _strip_exam(t_opts))

# Regresja: oryginalny przypadek, dla ktorego funkcja zostala napisana -
# PRAWDZIWIE osierocony dolar nadal poprawnie usuwany
t_orphan = "Liczymy deltę:$ $\\Delta=5$"
out_orphan = _fix_latex(t_orphan)
check("Regresja: prawdziwy osierocony dolar nadal poprawnie usuwany (nie zepsute przez fix)",
      out_orphan == "Liczymy deltę: $\\Delta=5$", out_orphan)

# Regresja: wieloznakowe "nie-matematyczne" pary nadal usuwane (bare slowo, nie litera)
t_word = "To jest $bardzo trudne$ pytanie, wiec licz $\\frac{1}{2}$ uwaznie"
out_word = _strip_exam(t_word)
check("Regresja: wieloznakowa 'pomylkowa' para (slowo, nie pojedyncza litera) nadal usuwana",
      "$bardzo trudne$" not in out_word and "$\\frac{1}{2}$" in out_word, out_word)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
