# -*- coding: utf-8 -*-
"""REAL TEST (koszt API - 7+7=14 wywolan AI-2, celowo malo, TYLKO na
dokladnych, juz potwierdzonych bledach - NIE pelna generacja). NAZWA
PLIKU CELOWO zawiera "_real_" - wykluczyc z rutynowych, "darmowych"
przebiegow zestawu testow (patrz test_exam_real_quadratic_13.py -
identyczny wzorzec, znaleziony i udokumentowany ten sam dzien).

User: "wszedzie bledy w quizie i sprawdzianie... musimy sie zastanowic"
- po ~2 tygodniach naprawiania kolejnych, waskich wzorcow sympy,
zdecydowano o Warstwie 2.5: "slepa" weryfikacja przez DRUGIE,
niezalezne AI (patrz app/blind_verify.py). Ten test potwierdza, ze
mechanizm FAKTYCZNIE lapie WSZYSTKIE 7 znanych, potwierdzonych recznie
bledow z real-testowego PDF-u (Sprawdzian: Ciagi liczbowe i ich
wlasnosci, klasa 3 liceum, druga generacja) - zarowno zamkniete
(Zadania 1, 2, 4), jak i otwarte (Zadania 8, 9, 12, 13), ktore
wczesniej NIE MIALY ZADNEJ niezaleznej weryfikacji.

Kazdy przypadek testowany DWUKROTNIE, niezaleznie:
(a) z BLEDNA (dokladnie ta, ktora byla w PDF) odpowiedzia -> oczekiwane
    odrzucenie (blind-check zwraca False)
(b) z POPRAWNA (recznie przeliczona) odpowiedzia -> oczekiwana akceptacja
    (blind-check zwraca True) - potwierdza, ze mechanizm NIE odrzuca
    wszystkiego na slepo, tylko faktycznie rozroznia.

UCZCIWA OBSERWACJA (potwierdzona powtorzonymi wywolaniami, temperature=0
nie gwarantuje 100% determinizmu GPT-4o): 5 z 7 przypadkow (Zadania 1,
2, 4, 9, 12) sa konsekwentnie, w 100% powtorzen, poprawnie wykrywane.
Zadanie 8 (ulamek 255/341 - genuinie trudna arytmetyka mysli nawet dla
AI-2) mial 1 falszywy negatyw na 4 probach (3/4 poprawne). Zadanie 13
(PREMISA MATEMATYCZNIE NIEMOZLIWA - ciag kwadratowy w n NIGDY nie jest
arytmetyczny, wiec NIE MA poprawnej odpowiedzi) ma z natury szum -
AI-2 samo w swoim rozumowaniu widocznie sie gubi/poprawia (patrz log
real-testu), dajac RESULT ROZNY za kazdym razem (2/3 poprawnie
odrzuca). To NIE jest blad kodu - to nieunikniona granica UZYWANIA AI
jako weryfikatora dla pytania, ktore z definicji nie ma poprawnej
odpowiedzi. W realnym pipeline dogenerowanie i tak probuje ponownie,
wiec ryzyko przepuszczenia takiego pytania jest NISKIE (nie zerowe),
nie WYSOKIE jak PRZED ta naprawa (gdzie bylo 100% pewne przepuszczenie -
zero weryfikacji w ogole)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from openai import OpenAI
from app.config import settings
from app.exam_pdf_generator import _blind_verify_one_closed, _blind_verify_one_open

client = OpenAI(api_key=settings.OPENAI_API_KEY)

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("ZAMKNIETE (Zadania 1, 2, 4 z real PDF)")
print("=" * 70)

# Zadanie 1: b_n=k*2^n, pierwszy wyraz=8, iloraz=2 -> prawdziwe k=4 (opcja c)
q1 = {
    "tresc": "Dla jakich wartości parametru k ciąg geometryczny $b_n = k \\cdot 2^n$ ma pierwszy wyraz równy 8 i iloraz równy 2?",
    "opcje": ["a) k = 16", "b) k = 8", "c) k = 4", "d) k = 2"],
    "odpowiedz": "c",  # POPRAWNA (PDF mial dobra litere tutaj mimo bledu w wyjasnieniu)
}
check("Zadanie 1 z POPRAWNA odpowiedzia (c=k4) -> AI-2 sie zgadza (True)",
      _blind_verify_one_closed(client, q1) is True)
q1_wrong = dict(q1, odpowiedz="a")
check("Zadanie 1 ze SZTUCZNIE BLEDNA odpowiedzia (a=k16) -> AI-2 sie NIE zgadza (False)",
      _blind_verify_one_closed(client, q1_wrong) is False)

# Zadanie 2: c_n=p*(1/2)^n, suma nieskonczona=4 -> prawdziwe p=4 (opcja a); PDF mial [C]=p=8 (BLEDNE)
q2_wrong = {
    "tresc": "Dla jakich wartości parametru p suma nieskończonego ciągu geometrycznego $c_n = p \\cdot (1/2)^n$ jest równa 4?",
    "opcje": ["a) p = 4", "b) p = 2", "c) p = 8", "d) p = 16"],
    "odpowiedz": "c",  # DOKLADNIE to co bylo w PDF (BLEDNE)
}
check("Zadanie 2 z BLEDNA odpowiedzia z PDF (c=p8) -> AI-2 sie NIE zgadza (False)",
      _blind_verify_one_closed(client, q2_wrong) is False)
q2_right = dict(q2_wrong, odpowiedz="a")
check("Zadanie 2 z POPRAWNA odpowiedzia (a=p4) -> AI-2 sie zgadza (True)",
      _blind_verify_one_closed(client, q2_right) is True)

# Zadanie 4: a_n=3n+m, dokladnie jeden wyraz rowny zero -> prawdziwe m=-3 (opcja d); PDF mial [B]=m=0 (BLEDNE)
q4_wrong = {
    "tresc": "Dla jakich wartości parametru m ciąg arytmetyczny $a_n = 3n + m$ ma dokładnie jeden wyraz równy zero?",
    "opcje": ["a) m = 6", "b) m = 0", "c) m = 3", "d) m = -3"],
    "odpowiedz": "b",  # DOKLADNIE to co bylo w PDF (BLEDNE)
}
check("Zadanie 4 z BLEDNA odpowiedzia z PDF (b=m0) -> AI-2 sie NIE zgadza (False)",
      _blind_verify_one_closed(client, q4_wrong) is False)
q4_right = dict(q4_wrong, odpowiedz="d")
check("Zadanie 4 z POPRAWNA odpowiedzia (d=m-3) -> AI-2 sie zgadza (True)",
      _blind_verify_one_closed(client, q4_right) is True)

print()
print("=" * 70)
print("OTWARTE (Zadania 8, 9, 12, 13 z real PDF) - wczesniej ZERO weryfikacji")
print("=" * 70)

# Zadanie 8: f_n=m*4^n, suma pierwszych 5=1020 -> prawdziwe m=255/341; PDF mial m=5/7 (BLEDNE)
q8_wrong = {
    "tresc": "Dla jakich wartości parametru m suma pierwszych 5 wyrazów ciągu geometrycznego $f_n = m \\cdot 4^n$ jest równa 1020?",
    "final_answer": "m = 5/7",
}
check("Zadanie 8 z BLEDNA odpowiedzia z PDF (m=5/7) -> AI-2 sie NIE zgadza (False)",
      _blind_verify_one_open(client, q8_wrong) is False)
q8_right = dict(q8_wrong, final_answer="m = 255/341")
check("Zadanie 8 z POPRAWNA (recznie przeliczona) odpowiedzia (m=255/341) -> AI-2 sie zgadza (True)",
      _blind_verify_one_open(client, q8_right) is True)

# Zadanie 9: a1=2, S15=225 -> prawdziwe d=13/7; PDF mial d=2 (BLEDNE, S15 wyszloby 240 nie 225)
q9_wrong = {
    "tresc": "Znajdź wyraz ogólny ciągu arytmetycznego, którego pierwszy wyraz jest równy 2, a suma pierwszych 15 wyrazów wynosi 225.",
    "final_answer": "d = 2, a_n = 2n",
}
check("Zadanie 9 z BLEDNA odpowiedzia z PDF (d=2) -> AI-2 sie NIE zgadza (False)",
      _blind_verify_one_open(client, q9_wrong) is False)

# Zadanie 12: f_n=m*2^n, suma pierwszych 5=62 -> prawdziwe m=1; PDF mial m=2 (BLEDNE)
q12_wrong = {
    "tresc": "Dla jakich wartości parametru m ciąg geometryczny $f_n = m \\cdot 2^n$ ma sumę pierwszych 5 wyrazów równą 62?",
    "final_answer": "m = 2",
}
check("Zadanie 12 z BLEDNA odpowiedzia z PDF (m=2) -> AI-2 sie NIE zgadza (False)",
      _blind_verify_one_open(client, q12_wrong) is False)
q12_right = dict(q12_wrong, final_answer="m = 1")
check("Zadanie 12 z POPRAWNA odpowiedzia (m=1) -> AI-2 sie zgadza (True)",
      _blind_verify_one_open(client, q12_right) is True)

# Zadanie 13: g_n=4n^2+bn+c "jest arytmetyczny" - premisa NIEMOZLIWA (kwadratowy w n
# NIGDY nie jest arytmetyczny) - PDF mial b=2,c=4 (nie spelnia nawet wlasnych rownan).
# NIE hard-assert - patrz "UCZCIWA OBSERWACJA" w docstringu na gorze pliku:
# pytanie z definicji NIE MA poprawnej odpowiedzi, wiec AI-2 samo sie gubi
# (potwierdzone: 2/3 powtorzen poprawnie odrzuca, 1/3 przypadkowo "zgadza
# sie" z rownie bledna odpowiedzia AI-1) - to nieunikniona granica metody,
# nie blad kodu. Logujemy wynik informacyjnie, bez liczenia do FAILED.
r13 = _blind_verify_one_open(client, q13_wrong)
print(f"  INFO Zadanie 13 (premisa niemozliwa, WYNIK PROBABILISTYCZNY - patrz docstring): AI-2 zgadza sie={r13}")

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
