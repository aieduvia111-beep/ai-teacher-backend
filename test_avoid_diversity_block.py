# -*- coding: utf-8 -*-
"""User (real-test Sprawdzianu z trygonometrii, 29.08.2026): "Udalo sie
wygenerowac i zweryfikowac 8 z 13 zamowionych zadan - przekroczono limit
czasu (60s)". Logi pokazaly PRAWDZIWA przyczyne (rejection_reasons):
duplicate=7 + diversity_too_similar=4 = 11/16 odrzucen (69%) - NIE blad
LaTeX (tylko 1/16). AI w kolko trafialo w te same "oczywiste" schematy
trygonometryczne w KAZDEJ rundzie dogenerowania, bo kazda runda pytala
AI OD ZERA, bez zadnej wiedzy o tym, co juz zostalo zaakceptowane (i
odrzucone jako zbyt podobne) we wczesniejszych rundach.

User: "zbadaj głebiej, żeby to działało na wszystkie tematy, zrób prosto
i profesjonalnie" - naprawiono OGOLNIE (nie tylko dla trygonometrii):
format_avoid_diversity_block (math_verify.py) zamienia liste JUZ
zaakceptowanych diversity_tag (ktore AI i tak juz generuje dla KAZDEGO
tematu, patrz Diversity Engine) na blok tekstu wstrzykiwany w prompt
KOLEJNEJ rundy dogenerowania - dziala identycznie w Quizie i Sprawdzianie,
dla dowolnego tematu, bo diversity_tag jest uniwersalny.

Ten plik testuje SAM czysty budowniczy bloku (zero AI, zero kosztu)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import format_avoid_diversity_block

print("=" * 70)
print("Pusta/brakujaca lista -> pusty string (bez zmiany zachowania promptu)")
print("=" * 70)
check("Pusta lista -> ''", format_avoid_diversity_block([]) == "")
check("None -> ''", format_avoid_diversity_block(None) == "")

print()
print("=" * 70)
print("Real przypadek (schematy z real-testu Trygonometrii)")
print("=" * 70)
tags = [
    {"skill": "zakres wartości funkcji trygonometrycznej", "concept": "wartości funkcji tangens",
     "task_type": "wyznacz przedział dla parametru", "reasoning": "analizuj zakres funkcji tangens"},
    {"skill": "przeksztalcenie rownania trygonometrycznego", "concept": "sinus i cosinus",
     "task_type": "rozwiaz rownanie trygonometryczne", "reasoning": "zamiana sin^2 na 1-cos^2"},
]
block = format_avoid_diversity_block(tags)
check("Blok zawiera pierwszy schemat (skill/concept/task_type)",
      "zakres wartości funkcji trygonometrycznej" in block and "wartości funkcji tangens" in block and "wyznacz przedział dla parametru" in block, block)
check("Blok zawiera drugi schemat",
      "przeksztalcenie rownania trygonometrycznego" in block and "rozwiaz rownanie trygonometryczne" in block, block)
check("Blok NIE zawiera pole 'reasoning' (celowo pominiete - zbyt szczegolowe/dlugie dla samego 'unikaj')",
      "analizuj zakres funkcji tangens" not in block, block)
check("Blok ma jawna instrukcje NIE POWTARZAJ",
      "NIE" in block.upper() and ("POWTARZAJ" in block.upper() or "POWTORZ" in block.upper()), block)

print()
print("=" * 70)
print("Odpornosc na zle dane (nie crashuje, pomija bezuzyteczne wpisy)")
print("=" * 70)
messy = [
    {"skill": "x", "concept": "y", "task_type": "z"},
    "nie-dict-string",
    123,
    None,
    {},  # dict bez zadnego z 3 pol
    {"reasoning": "tylko reasoning, brak skill/concept/task_type"},
]
block2 = format_avoid_diversity_block(messy)
check("Nie rzuca wyjatku na mieszanych/zlych danych", True)
check("Poprawny wpis nadal trafia do bloku", "x / y / z" in block2, block2)

print()
print("=" * 70)
print("Wiele schematow -> wiele oddzielnych linii (czytelne dla AI)")
print("=" * 70)
many = [{"skill": f"skill{i}", "concept": f"concept{i}", "task_type": f"type{i}"} for i in range(5)]
block3 = format_avoid_diversity_block(many)
lines_with_dash = [l for l in block3.split("\n") if l.strip().startswith("-")]
check("5 schematow -> 5 linii zaczynajacych sie od '-'", len(lines_with_dash) == 5, block3)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
