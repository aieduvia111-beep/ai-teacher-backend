# -*- coding: utf-8 -*-
"""KRYTYCZNY, POTWIERDZONY BLAD (zgloszony przez usera, sierpien 2026):
ciag arytmetyczny a3=11, a7=27 - system oznaczyl a1=5 jako "poprawna",
mimo ze PRAWDZIWE a1=3 (r=4, sprawdzone: a3=3+2*4=11, a7=3+6*4=27;
a1=5 daje sprzecznosc: gdyby a1=5 to z a3=11 wynika r=3, ale wtedy
a7=5+6*3=23 != 27).

Bezposrednie sledztwo (patrz tez skryptowe wywolanie
verify_sequence_question w rozmowie) potwierdzilo: SAMA funkcja
liczaca (an_expr, wzor a_n=a1+(n-1)*r) jest matematycznie poprawna -
liczy a1=3 poprawnie i odrzuca a1=5 poprawnie, GDY zostanie wywolana.
Prawdziwy bug byl w detect_sequence_intent: galaz two_term_to_a1_ratio
wymagala DOSLOWNEGO slowa "roznice"/"iloraz" w tresci pytania - dla
najbardziej naturalnego wariantu ("Wyznacz pierwszy wyraz tego ciagu."
bez wzmianki o "roznicy") intent=None -> verify_sequence_question
zwracalo "unverifiable" -> ZERO ochrony Warstwy 2 -> AI (Warstwa 1)
moglo podac dowolnie bledne a1 bez sprzeciwu."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.math_verify import verify_sequence_question, detect_sequence_intent

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("Dokladny zgloszony przypadek: a3=11, a7=27 (prawdziwe a1=3, NIE 5)")
print("=" * 70)

# Warianty realistycznego frazowania - w tym te BEZ slowa "roznica"/
# "iloraz", ktore przed naprawa dawaly intent=None.
VARIANTS = [
    "Ciąg arytmetyczny ma a3=11 i a7=27. Wyznacz pierwszy wyraz tego ciągu.",
    "Dany jest ciąg arytmetyczny, w którym a3=11 oraz a7=27. Oblicz a1.",
    "W ciągu arytmetycznym a3=11, a7=27. Znajdź pierwszy wyraz ciągu.",
    "Ciąg arytmetyczny ma a3=11 i a7=27. Wyznacz pierwszy wyraz i różnicę tego ciągu.",
]
OPTIONS_ONLY_WRONG = ["a1=5, r=3", "a1=6, r=4", "a1=2, r=5", "a1=1, r=2"]
OPTIONS_WITH_CORRECT = ["a1=5, r=3", "a1=3, r=4", "a1=11, r=4", "a1=3, r=3"]

for q in VARIANTS:
    intent = detect_sequence_intent(q)
    check(f"intencja rozpoznana dla: '{q[:55]}...'", intent == {"intent": "two_term_to_a1_ratio"}, intent)

    r_wrong_only = verify_sequence_question(q, OPTIONS_ONLY_WRONG)
    check(f"BEZ poprawnej a1=3 w opcjach -> no_option_matches (NIE ciche zaakceptowanie a1=5): '{q[:40]}...'",
          r_wrong_only["status"] == "no_option_matches", r_wrong_only)

    r_with_correct = verify_sequence_question(q, OPTIONS_WITH_CORRECT)
    check(f"z poprawna a1=3 w opcjach -> match_index wskazuje a1=3 (indeks 1), NIE a1=5: '{q[:40]}...'",
          r_with_correct["status"] == "match_index" and r_with_correct["true_index"] == 1, r_with_correct)

print()
print("=" * 70)
print("Regresja: przypadki, ktore JUZ wczesniej dzialaly, nadal dzialaja")
print("=" * 70)

# a1 juz PODANE wprost - two_term_to_a1_ratio NIE powinno sie aktywowac
# (to inny, juz istniejacy przypadek - "latwe" pytanie z podanym a1).
q_a1_given = "Ciąg arytmetyczny ma pierwszy wyraz a1=3 i różnicę r=5. Oblicz piąty wyraz."
intent_given = detect_sequence_intent(q_a1_given)
check("a1 JUZ PODANE wprost -> NIE two_term_to_a1_ratio (inny przypadek, bez regresji)",
      intent_given != {"intent": "two_term_to_a1_ratio"}, intent_given)

# Pytanie o sume, nie o a1 z dwoch wyrazow - nie powinno kolidowac.
q_sum = "Ciąg arytmetyczny ma a1=2, r=3. Oblicz sumę pierwszych 10 wyrazów tego ciągu."
intent_sum = detect_sequence_intent(q_sum)
check("pytanie o sume (nie o a1 z dwoch wyrazow) -> NIE two_term_to_a1_ratio",
      intent_sum != {"intent": "two_term_to_a1_ratio"}, intent_sum)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
