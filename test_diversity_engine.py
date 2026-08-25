# -*- coding: utf-8 -*-
"""Universal Diversity Engine - Krok 2: czysta, testowalna logika
porownania diversity_tag (Jaccard similarity), BEZ wywolan AI. Fixture
w tescie 2 to DOSLOWNIE realne tagi zebrane w Kroku 1 (real test, n=10,
"Rownania kwadratowe", medium) - 9/10 pytan mialo identyczny schemat
("parametr jako wyraz wolny"), 1 realnie inny ("parametr jako
wspolczynnik liniowy") - AI uczciwie to odzwierciedlilo w tagach."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.math_verify import (
    diversity_tag_tokens, jaccard_similarity, is_too_similar_diversity_tag,
    DIVERSITY_SIMILARITY_THRESHOLD,
)

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("1. diversity_tag_tokens - normalizacja i bezpieczny abstain")
print("=" * 70)

t1 = diversity_tag_tokens({
    "skill": "wzor na delte", "concept": "parametr jako wyraz wolny",
    "task_type": "wyznacz parametr z warunku na delte",
    "reasoning": "oblicz delte, rozwiaz nierownosc, zapisz przedzial",
})
check("zwraca niepusty frozenset dla poprawnego tagu", len(t1) > 0, t1)
check("'delte' jest w tokenach (rdzen slowa kluczowego)", "delte" in t1, t1)
check("stopword 'na' NIE jest w tokenach", "na" not in t1, t1)
check("stopword 'z' NIE jest w tokenach", "z" not in t1, t1)

check("None -> pusty frozenset (brak pola, nie crash)", diversity_tag_tokens(None) == frozenset(), diversity_tag_tokens(None))
check("string zamiast dict -> pusty frozenset (nie crash)", diversity_tag_tokens("cos") == frozenset(), diversity_tag_tokens("cos"))
check("pusty dict -> pusty frozenset", diversity_tag_tokens({}) == frozenset(), diversity_tag_tokens({}))
check("dict z brakujacymi polami -> nie crashuje", diversity_tag_tokens({"skill": "x"}) != None, diversity_tag_tokens({"skill": "x"}))

print()
print("=" * 70)
print("2. jaccard_similarity - matematyka + bezpieczny abstain")
print("=" * 70)

a = frozenset({"delta", "parametr", "wyraz", "wolny"})
b = frozenset({"delta", "parametr", "wyraz", "wolny"})
check("identyczne zbiory -> similarity 1.0", jaccard_similarity(a, b) == 1.0, jaccard_similarity(a, b))

c = frozenset({"trojkat", "sinus", "cosinus"})
check("zupelnie rozne zbiory -> similarity 0.0", jaccard_similarity(a, c) == 0.0, jaccard_similarity(a, c))

d = frozenset({"delta", "parametr", "inny", "temat"})
sim = jaccard_similarity(a, d)
check(f"czesciowe pokrycie -> similarity miedzy 0 i 1 (tu {sim:.2f})", 0.0 < sim < 1.0, sim)

check("pusty zbior vs cokolwiek -> 0.0 (nie 'identyczne')", jaccard_similarity(frozenset(), a) == 0.0, None)
check("oba puste -> 0.0", jaccard_similarity(frozenset(), frozenset()) == 0.0, None)

print()
print("=" * 70)
print("3. REALNE tagi z Kroku 1 (n=10, rownania kwadratowe, medium)")
print("=" * 70)

# Doslowne tagi zebrane real-testem (patrz docstring pliku)
REAL_TAGS = [
    {"skill": "wzor na delte", "concept": "parametr jako wspolczynnik liniowy",
     "task_type": "wyznacz parametr z warunku na delte",
     "reasoning": "oblicz delte, rozwiaz nierownosc, zapisz przedzial"},
] + [
    {"skill": "wzor na delte", "concept": "parametr jako wyraz wolny",
     "task_type": "wyznacz parametr z warunku na delte",
     "reasoning": "oblicz delte, rozwiaz nierownosc, zapisz przedzial"},
] * 9

seen = []
accepted, rejected = 0, 0
for i, tag in enumerate(REAL_TAGS):
    too_similar, tokens = is_too_similar_diversity_tag(tag, seen)
    if too_similar:
        rejected += 1
    else:
        accepted += 1
        seen.append(tokens)
    print(f"  pytanie {i+1}: {'ODRZUCONE (za podobne)' if too_similar else 'zaakceptowane'}")

check("z 10 realnych pytan (9 identycznych + 1 rozny) -> dokladnie 2 zaakceptowane (1 unikalny schemat + pierwszy z grupy 9)",
      accepted == 2, accepted)
check("8 z 9 identycznych zostaje odrzuconych jako 'za podobne'", rejected == 8, rejected)

print()
print("=" * 70)
print("4. Prog podobienstwa - kalibracja z Kroku 1")
print("=" * 70)

tag_a = REAL_TAGS[0]   # "parametr jako wspolczynnik liniowy"
tag_b = REAL_TAGS[1]   # "parametr jako wyraz wolny"
# NAPRAWIONE: pierwsza wersja tego testu ZAKLADALA (bez przeliczenia),
# ze rozne schematy beda mialy niskie Jaccard - realny pomiar pokazal
# 0.733 (pola skill/task_type/reasoning to CZESTO wspolny, generyczny
# szkielet proceduralny dla calej rodziny zadan o delcie - roznicuje
# je realnie tylko "concept"). Prog przekalibrowany na 0.85 (patrz
# komentarz w math_verify.py) - test teraz sprawdza PRZELICZONA,
# rzeczywista wartosc.
sim_ab = jaccard_similarity(diversity_tag_tokens(tag_a), diversity_tag_tokens(tag_b))
print(f"  Jaccard(rozny schemat A, rozny schemat B) = {sim_ab:.3f}")
check(f"zmierzone: rozne schematy maja similarity ~0.733 (potwierdzenie kalibracji progu 0.85)", abs(sim_ab - 0.733) < 0.01, sim_ab)
check(f"rozne schematy maja similarity < prog ({DIVERSITY_SIMILARITY_THRESHOLD}) - NIE zostana odrzucone", sim_ab < DIVERSITY_SIMILARITY_THRESHOLD, sim_ab)

sim_same = jaccard_similarity(diversity_tag_tokens(REAL_TAGS[1]), diversity_tag_tokens(REAL_TAGS[2]))
check("identyczne realne tagi maja similarity 1.0", sim_same == 1.0, sim_same)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
