# -*- coding: utf-8 -*-
"""Universal Diversity Engine - Krok 3: potwierdza WPIECIE (nie tylko
czysta logike z Kroku 2) do _verify_and_fix_quiz_math/
_verify_and_fill_quiz_math - syntetyczne pytania z reczne wpisanymi
diversity_tag (zero AI), sprawdza ze pytania o tym samym schemacie
faktycznie zostaja odrzucone przez PRAWDZIWA funkcje produkcyjna, i ze
brak/uszkodzony tag NIE blokuje (bezpieczny abstain, wazne dla
wstecznej kompatybilnosci z pytaniami bez tego pola - np. sciezka z
obrazka, ktora nie ma tej instrukcji w prompcie)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import asyncio
from app.openai_exam import _verify_and_fix_quiz_math, _verify_and_fill_quiz_math

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


def _q(n, tag=None):
    return {
        "question": f"Testowe pytanie {n}?",
        "options": ["a", "b", "c", "d"],
        "correct": 0,
        "final_answer": "a",
        "diversity_tag": tag,
    }


SAME_TAG = {"skill": "wzor na delte", "concept": "parametr jako wyraz wolny",
            "task_type": "wyznacz parametr", "reasoning": "oblicz delte, rozwiaz nierownosc"}
DIFFERENT_TAG = {"skill": "twierdzenie sinusow", "concept": "trojkat dowolny",
                  "task_type": "oblicz bok trojkata", "reasoning": "zastosuj wzor, podstaw dane"}

print("=" * 70)
print("1. _verify_and_fix_quiz_math - odrzuca schemat-duplikat w partii")
print("=" * 70)

quiz = {"title": "Test", "questions": [
    _q(1, SAME_TAG), _q(2, SAME_TAG), _q(3, SAME_TAG), _q(4, DIFFERENT_TAG),
]}
seen = []
result = _verify_and_fix_quiz_math(quiz, seen_diversity_tags=seen)
kept_count = len(result["questions"])
check("z 4 pytan (3x ten sam schemat + 1 rozny) -> zostaja 2 (1 pierwszy z grupy + 1 rozny)",
      kept_count == 2, result["questions"])

print()
print("=" * 70)
print("2. Brak/None diversity_tag -> NIE blokuje (bezpieczny abstain)")
print("=" * 70)

quiz2 = {"title": "Test", "questions": [_q(1, None), _q(2, None), _q(3, None)]}
seen2 = []
result2 = _verify_and_fix_quiz_math(quiz2, seen_diversity_tags=seen2)
check("3 pytania BEZ diversity_tag -> wszystkie 3 zaakceptowane (nie da sie ocenic)",
      len(result2["questions"]) == 3, result2["questions"])

print()
print("=" * 70)
print("3. seen_diversity_tags=None (domyslne) -> zero zmiany zachowania")
print("=" * 70)

quiz3 = {"title": "Test", "questions": [_q(1, SAME_TAG), _q(2, SAME_TAG), _q(3, SAME_TAG)]}
result3 = _verify_and_fix_quiz_math(quiz3)  # brak seen_diversity_tags w ogole
check("bez podania seen_diversity_tags -> mechanizm WYLACZONY, wszystkie 3 przechodza",
      len(result3["questions"]) == 3, result3["questions"])

print()
print("=" * 70)
print("4. _verify_and_fill_quiz_math end-to-end (mock regenerate) - N==N mimo odrzucen schematu")
print("=" * 70)


async def run_fill_test():
    counter = {"n": 0}

    async def mock_regenerate(n):
        # Kazde wywolanie zwraca NOWY tekst Z GENUINE UNIKALNYM tagiem
        # (licznik wpisany w "concept") - symuluje AI, ktore faktycznie
        # roznicuje schematy miedzy rundami dogenerowania. Nieskonczona
        # pula unikalnych tagow (w przeciwienstwie do pierwszych dwoch
        # wersji tego mocka, ktore mialy skonczona/zerowa pule unikalnych
        # tagow, wiec nigdy nie mogly osiagnac N==N - to byl blad w
        # KONSTRUKCJI TESTU, nie w produkcyjnej logice, ktora poprawnie
        # odrzucala kazdy powtarzajacy sie tag zgodnie z projektem).
        # UWAGA: diversity_tag_tokens usuwa CYFRY (patrz math_verify.py
        # _DIVERSITY_NON_WORD_RE) - unikalnosc trzeba kodowac SLOWAMI,
        # nie liczbami, inaczej "koncept 1"/"koncept 2" normalizuja sie
        # do TYCH SAMYCH tokenow (pierwsza wersja tego mocka mialaby
        # ten sam blad).
        unique_words = ["alfa", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]
        out = []
        for _ in range(n):
            counter["n"] += 1
            word = unique_words[(counter["n"] - 1) % len(unique_words)]
            tag = {"skill": f"umiejetnosc {word}", "concept": f"koncept {word}",
                   "task_type": f"typ {word}", "reasoning": f"rozumowanie {word}"}
            out.append(_q(2000 + counter["n"], tag))
        return {"questions": out}

    quiz_data = {"questions": [_q(1, SAME_TAG), _q(2, SAME_TAG), _q(3, SAME_TAG), _q(4, DIFFERENT_TAG)]}
    return await _verify_and_fill_quiz_math(quiz_data, 4, mock_regenerate)


result4 = asyncio.run(run_fill_test())
final_count = len(result4.get("questions", []))
check(f"N==N: zamowiono 4, mimo odrzucen schematu system dogenerowal do {final_count}",
      final_count == 4, result4.get("_shortfall_warning"))

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
