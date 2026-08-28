# -*- coding: utf-8 -*-
"""User pobral wygenerowany PDF Sprawdzianu (Ciagi, klasa 3 liceum,
trudny) i zapytal o ocene jakosci ("oceń poziom trudny... jest git?").
Recznie zweryfikowano wszystkie 14 zadan - 3 z 6 zadan zamknietych (Czesc
A) mialy ZEPSUTY klucz odpowiedzi:

- Zadanie 1: a_n=3n+m, "ma pierwszy wyraz rowny 7" - obliczenia
  poprawnie daja m=4 (opcja b w PDF), ale klucz oznaczyl [A] (m=10).
- Zadanie 2: b_n=k^n, "suma pierwszych trzech wyrazow rowna 13" -
  MATEMATYCZNIE NIEROZWIAZYWALNE wsrod podanych opcji (k+k^2+k^3=13 nie
  ma calkowitego rozwiazania - dla k=2 wychodzi 14, nie 13). Wlasne
  wyjasnienie AI to przyznaje ("co jest bledne"), a mimo to oznacza k=2
  jako poprawne.
- Zadanie 3: c_n=pn+5, "roznica miedzy drugim a pierwszym wyrazem wynosi
  3" - obliczenia poprawnie daja p=3 (opcja a w PDF), ale klucz
  oznaczyl [C] (p=2).

Diagnoza (kod/logi, real-test verify_and_fix_math_question na
DOKLADNYM tekscie z PDF): wszystkie 3 zwracaly "unverifiable" - ten
KSZTALT pytania (wzor ciagu WPROST jako funkcja n z jednym nieznanym
parametrem, np. "a_n=3n+m", NIE konkretne wyrazy jak "a_1=5") nie byl
w ogole rozpoznawany przez analyze_sequence_question (ktora wymaga
KONKRETNYCH liczb, nie formuly). Skutek: ZERO niezaleznej weryfikacji
Warstwy 2 dla calej tej kategorii pytan - jesli pole "final_answer" od
AI bylo niezgodne z jego WLASNYM wyjasnieniem (dokladnie ten sam blad
klasy co wczesniej dzis naprawiony "Zatem k=4, co daje k=2"), nic tego
nie lapalo.

Naprawiono: nowy weryfikator verify_sequence_formula_parameter,
obslugujacy 3 typy warunkow (wszystkie 3 potwierdzone realnymi
przypadkami z tego PDF): (a) konkretny wyraz rowny wartosci, (b)
roznica miedzy dwoma konkretnymi wyrazami, (c) suma pierwszych N
wyrazow rowna wartosci. Podlaczony do glownego dispatchera
verify_and_fix_math_question (Quiz + Sprawdzian - wspolny kod).

Wszystkie testy sa JEDNOSTKOWE (zero AI), na DOKLADNYCH tekstach
odczytanych z realnego PDF."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import verify_and_fix_math_question

print("=" * 70)
print("Real Zadanie 1 (PDF): a_n=3n+m, 'ma pierwszy wyraz rowny 7' - "
      "klucz PDF mial zla litere ([A]=m=10 zamiast [B]=m=4)")
print("=" * 70)
q1 = "Dla jakich wartości parametru m ciąg arytmetyczny a_n = 3n + m ma pierwszy wyraz równy 7?"
opts1 = ["a) m = 10", "b) m = 4", "c) m = 7", "d) m = 3"]
r1 = verify_and_fix_math_question(q1, opts1)
check("m=4 (index 1, opcja b) poprawnie wykryte - PRZED naprawa: unverifiable",
      r1["status"] == "match_index" and r1["true_index"] == 1, r1)

print()
print("=" * 70)
print("Real Zadanie 2 (PDF): b_n=k^n, 'suma pierwszych trzech wyrazow "
      "rowna 13' - MATEMATYCZNIE NIEROZWIAZYWALNE wsrod opcji "
      "(wlasne wyjasnienie AI to przyznaje, a mimo to k=2 oznaczone "
      "jako poprawne)")
print("=" * 70)
q2 = "Dla jakich wartości parametru k, suma pierwszych trzech wyrazów ciągu geometrycznego b_n = k^n jest równa 13?"
opts2 = ["a) k = 0", "b) k = 2", "c) k = 1", "d) k = 3"]
r2 = verify_and_fix_math_question(q2, opts2)
check("zadne z k=0,1,2,3 nie spelnia rownania - poprawnie ODRZUCONE (no_option_matches), NIE potwierdzone k=2",
      r2["status"] == "no_option_matches", r2)

print()
print("=" * 70)
print("Real Zadanie 3 (PDF): c_n=pn+5, 'roznica miedzy drugim a "
      "pierwszym wyrazem wynosi 3' - klucz PDF mial zla litere "
      "([C]=p=2 zamiast [A]=p=3)")
print("=" * 70)
q3 = "Dla jakich wartości parametru p, różnica między drugim a pierwszym wyrazem ciągu arytmetycznego c_n = pn + 5 wynosi 3?"
opts3 = ["a) p = 3", "b) p = 0", "c) p = 2", "d) p = 1"]
r3 = verify_and_fix_math_question(q3, opts3)
check("p=3 (index 0, opcja a) poprawnie wykryte - PRZED naprawa: unverifiable",
      r3["status"] == "match_index" and r3["true_index"] == 0, r3)

print()
print("=" * 70)
print("Real Zadanie 4 (PDF): e_n=b*n^2, 'sume pierwszych dwoch wyrazow "
      "rowna 10' - klucz PDF byl JUZ poprawny (b=2, opcja d) - "
      "potwierdzenie, nie regresja")
print("=" * 70)
q4 = "Dla jakich wartości parametru b, ciąg e_n = b*n^2 ma sumę pierwszych dwóch wyrazów równą 10?"
opts4 = ["a) b = 3", "b) b = 4", "c) b = 1", "d) b = 2"]
r4 = verify_and_fix_math_question(q4, opts4)
check("b=2 (index 3, opcja d) potwierdzone - bylo juz poprawne w PDF",
      r4["status"] == "match_index" and r4["true_index"] == 3, r4)

print()
print("=" * 70)
print("Regresja: Zadania 5, 6 (INNY ksztalt - a1=m/r=3 dane wprost, "
      "nie formula 'letter_n=...') nie sa dotkniete nowym weryfikatorem")
print("=" * 70)
q5 = "Dla jakich wartości parametru m ciąg arytmetyczny o pierwszym wyrazie a1 = m i różnicy r = 3 ma trzeci wyraz równy 10?"
r5 = verify_and_fix_math_question(q5, ["a) m = 7", "b) m = 2", "c) m = 4", "d) m = 1"])
check("Regresja: Zadanie 5 (inny ksztalt) niezmieniona odpowiedz (unverifiable jak wczesniej - bylo juz poprawne przez Warstwe 1)",
      r5["status"] == "unverifiable", r5)

print()
print("=" * 70)
print("Regresja: pelny zestaw wczesniejszych naprawionych dzisiaj "
      "wzorcow ciagow nadal dziala")
print("=" * 70)
r_geom_power = verify_and_fix_math_question(
    "Dla jakich wartości parametru k ciąg geometryczny $b_n = k^n$ ma iloraz równy 4?",
    ["2", "4", "8", "16"]
)
check("Regresja: verify_geometric_power_form_ratio (b_n=k^n + iloraz) nadal dziala",
      r_geom_power["status"] == "match_index" and r_geom_power["true_index"] == 1, r_geom_power)

r_d_notation = verify_and_fix_math_question(
    "Dany jest ciąg arytmetyczny, w którym pierwszy wyraz wynosi $a_1 = 5$, a różnica $d = 3$. Oblicz dziesiąty wyraz tego ciągu.",
    ["$a_{10} = 32$", "$a_{10} = 35$", "$a_{10} = 38$", "$a_{10} = 41$"]
)
check("Regresja: notacja 'd' dla roznicy (naprawiona wczesniej dzis) nadal dziala",
      r_d_notation["status"] == "match_index" and r_d_notation["true_index"] == 0, r_d_notation)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
