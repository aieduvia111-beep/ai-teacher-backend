# -*- coding: utf-8 -*-
"""User uruchomil real Quiz (ciagi, liceum_3, trudny) i wkleil wyniki -
co najmniej 3 pytania mialy odpowiedz oznaczona "poprawna", ktora byla
SPRZECZNA z wlasnym wyjasnieniem (Pytanie 7: wyjasnienie liczy S10=150,
ale system oznaczyl S10=135 jako poprawna).

Diagnoza (real logi z serwera, temat='ciagi'/liceum_3/trudny):

BLAD 1 (NAJWIEKSZY, dotyka WIEKSZOSCI pytan arytmetycznych w tej
partii): _SEQ_R_RE lapal WYLACZNIE litere "r" dla roznicy ciagu
arytmetycznego - ta generacja KONSEKWENTNIE uzywala "d" ("$d = 3$",
"$d = 4$"). Skutek: `ratio` bylo ZAWSZE None dla kazdego pytania o
ciag arytmetyczny, niezaleznie od intencji - Warstwa 2 byla calkowicie
slepa. Naprawiono: _SEQ_R_RE akceptuje teraz "r" LUB "d".

BLAD 2 (Pytanie 7 - "Oblicz sume dziesieciu pierwszych wyrazow..."):
2 niezalezne luki w _SEQ_SUM_N_RE/_SEQ_SUM_VALUE_RE - (a) tylko cyfra
(\\d+), nie slowna forma liczebnika ("dziesieciu"); (b) sztywna
kolejnosc "pierwszych <N>", podczas gdy naturalny polski "<N>
pierwszych" (liczebnik przed "pierwszych") wcale nie pasowal.
Naprawiono: nowy _SEQ_CARDINAL_WORDS + elastyczna kolejnosc.

BLAD 3 (odkryty PRZY OKAZJI naprawy Bledu 2 - Pytanie 7 nadal dawalo
"no_option_matches" mimo poprawnie policzonego true_value=150): 3
galezie dispatch (sum_given_n, find_n_from_last_term, find_n_from_sum)
parsowaly CALY tekst opcji ("S_{10} = 150") jako JEDNO wyrazenie sympy
zamiast wyciagac wartosc PO znaku "=" - identyczny, juz wczesniej
naprawiony w find_a1_given_sum blad (patrz _option_value_after_equals),
nigdy nie przeniesiony do tych 3 innych galezi. Naprawiono: wszystkie
3 uzywaja teraz _option_value_after_equals.

BLAD 4 (Pytania 3, 4 - "c1=4,c3=16, oblicz iloraz" / "d1=7,d5=19,
oblicz roznice"): gdy a1 jest JUZ PODANE wprost, zaden istniejacy
intent nie pasowal do pytania o SAM r/q (bez pytania tez o a1) -
dodano nowy intent "two_term_to_ratio_only" (ten sam uklad rownan co
two_term_to_a1_ratio, ale interesuje nas DRUGA niewiadoma).

Wszystkie testy ponizej sa JEDNOSTKOWE (zero AI), na DOKLADNYCH
tekstach pytan z realnego logu serwera tej generacji."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import verify_and_fix_math_question, detect_sequence_intent, analyze_sequence_question

print("=" * 70)
print("BLAD 1: _SEQ_R_RE rozpoznaje 'd' (nie tylko 'r')")
print("=" * 70)
a1 = analyze_sequence_question("Ciąg arytmetyczny ma pierwszy wyraz $a_1 = 5$ i różnicę $d = 3$.")
check("'d = 3' rozpoznane jako ratio=3 (nie None)", a1["ratio"] == 3, a1)

print()
print("=" * 70)
print("Real przypadek 1 (dokladny tekst z logu): a1=5,d=3, 'dziesiaty wyraz' -> 32")
print("=" * 70)
q1 = "Dany jest ciąg arytmetyczny, w którym pierwszy wyraz wynosi $a_1 = 5$, a różnica $d = 3$. Oblicz dziesiąty wyraz tego ciągu."
opts1 = ["$a_{10} = 32$", "$a_{10} = 35$", "$a_{10} = 38$", "$a_{10} = 41$"]
r1 = verify_and_fix_math_question(q1, opts1)
check("a10=32 poprawnie zweryfikowane (byloby 'unverifiable' PRZED naprawa)",
      r1["status"] == "match_index" and r1["true_index"] == 0, r1)

print()
print("=" * 70)
print("BLAD 2+3, Real przypadek (Pytanie 7 z realnego logu): S10, "
      "'sume dziesieciu pierwszych wyrazow' - wyjasnienie liczylo 150, "
      "system oznaczyl 135 jako poprawne")
print("=" * 70)
q7 = "Dany jest ciąg arytmetyczny, w którym pierwszy wyraz wynosi $h_1 = -3$, a różnica $d = 4$. Oblicz sumę dziesięciu pierwszych wyrazów tego ciągu."
opts7 = ["$S_{10} = 150$", "$S_{10} = 145$", "$S_{10} = 140$", "$S_{10} = 135$"]
r7 = verify_and_fix_math_question(q7, opts7)
check("S10: PRAWDZIWA odpowiedz 150 (index 0) wykryta, NIE bledna 135 (index 3)",
      r7["status"] == "match_index" and r7["true_index"] == 0, r7)

print()
print("=" * 70)
print("Regresja: slowna forma liczebnika z INNYM slowem (pieciu) + "
      "INNA kolejnosc (pierwszych <N>) nadal dziala")
print("=" * 70)
q_5w = "Ciąg arytmetyczny ma pierwszy wyraz $a_1 = 2$ i różnicę $d = 4$. Oblicz sumę pierwszych pięciu wyrazów tego ciągu."
opts_5w = ["$S_5 = 50$", "$S_5 = 30$", "$S_5 = 40$", "$S_5 = 60$"]
r_5w = verify_and_fix_math_question(q_5w, opts_5w)
# S5 = 5*(2*2+4*4)/2 = 5*(4+16)/2 = 5*20/2 = 50
check("'pierwszych pieciu' (kolejnosc odwrotna niz Pytanie 7) -> S5=50 wykryte",
      r_5w["status"] == "match_index" and r_5w["true_index"] == 0, r_5w)

print()
print("=" * 70)
print("Regresja: cyfra (nie slowo) nadal dziala (istniejacy przypadek)")
print("=" * 70)
q_digit = "Ciąg arytmetyczny ma pierwszy wyraz $a_1 = 1$ i różnicę $d = 1$. Oblicz sumę pierwszych 3 wyrazów tego ciągu."
opts_digit = ["$S_3 = 6$", "$S_3 = 5$", "$S_3 = 7$", "$S_3 = 8$"]
r_digit = verify_and_fix_math_question(q_digit, opts_digit)
check("cyfra '3' (nie slowna forma) nadal dziala jak wczesniej", r_digit["status"] == "match_index" and r_digit["true_index"] == 0, r_digit)

print()
print("=" * 70)
print("BLAD 4: nowy intent two_term_to_ratio_only (Pytania 3, 4 z logu)")
print("=" * 70)
q4 = "Ciąg arytmetyczny ma pierwszy wyraz $d_1 = 7$ i piąty wyraz $d_5 = 19$. Oblicz różnicę tego ciągu."
opts4 = ["$d = 2$", "$d = 3$", "$d = 4$", "$d = 5$"]
r4 = verify_and_fix_math_question(q4, opts4)
check("Pytanie 4 (d1=7,d5=19,oblicz roznice): d=3 poprawnie wykryte (byloby 'unverifiable' PRZED naprawa)",
      r4["status"] == "match_index" and r4["true_index"] == 1, r4)

# ZMIENIONE (kolejna naprawa tego samego dnia - _disambiguate_multi_solution):
# q^2=4 MA dwa matematycznie poprawne rozwiazania (+-2), ale TYLKO q=2
# wystepuje wsrod podanych opcji (q=-2 nigdy nie jest wypisane) - zamiast
# zawsze abstainowac, weryfikator teraz sprawdza to i bezpiecznie wybiera
# JEDYNE rozwiazanie faktycznie obecne wsrod opcji (nie zgadywanie -
# wyciaganie dodatkowej pewnosci z danych opcji). Patrz test_math_verify_
# ratio_disambiguation.py po test samej funkcji _disambiguate_multi_solution
# (w tym przypadek GDY oba rozwiazania sa wsrod opcji -> nadal abstain).
q3 = "Dany jest ciąg geometryczny, w którym pierwszy wyraz jest $c_1 = 4$, a trzeci wyraz $c_3 = 16$. Oblicz iloraz tego ciągu."
opts3 = ["$q = 2$", "$q = 3$", "$q = 4$", "$q = 5$"]
r3 = verify_and_fix_math_question(q3, opts3)
check("Pytanie 3 (c1=4,c3=16,oblicz iloraz - q^2=4 ma DWA rozwiazania +-2, ale TYLKO q=2 jest wsrod opcji): q=2 bezpiecznie wybrane",
      r3["status"] == "match_index" and r3["true_index"] == 0, r3)

print()
print("=" * 70)
print("Regresja: two_term_to_a1_ratio (a1 SZUKANE, nie podane) nadal dziala")
print("=" * 70)
q_a1 = "Ciąg arytmetyczny ma a3=11 i a7=27. Znajdź pierwszy wyraz."
opts_a1 = ["a1=3, r=4", "a1=5, r=3", "a1=7, r=2", "a1=9, r=1"]
r_a1 = verify_and_fix_math_question(q_a1, opts_a1)
check("Regresja: two_term_to_a1_ratio (juz istniejacy podwzorzec) nadal dziala",
      r_a1["status"] == "match_index" and r_a1["true_index"] == 0, r_a1)

print()
print("=" * 70)
print("Regresja: geometric_power_form_ratio (naprawiony wczesniej dzisiaj) nadal dziala")
print("=" * 70)
q_pf = "Dla jakich wartości parametru k ciąg geometryczny $b_n = k^n$ ma iloraz równy 4?"
opts_pf = ["2", "4", "8", "16"]
r_pf = verify_and_fix_math_question(q_pf, opts_pf)
check("Regresja: verify_geometric_power_form_ratio nadal dziala (k=4, index 1)",
      r_pf["status"] == "match_index" and r_pf["true_index"] == 1, r_pf)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
