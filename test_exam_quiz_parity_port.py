# -*- coding: utf-8 -*-
"""Port wszystkich mechanizmow z Quizu do Sprawdzianu (audyt Sprawdzian
V1, sierpien 2026 - user zglosil 13 zamowionych, 8 dostarczonych).
Sprawdza (ZERO wywolan AI) ze wpiecie do produkcyjnych funkcji dziala
identycznie jak w Quizie: Diversity Engine + wyjatek dla _safe_generated,
buffer +50%, timeout 45s - wszystko gated TYLKO dla rownan kwadratowych +
medium, bez zmiany zachowania dla innych tematow/trudnosci."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.exam_pdf_generator import (
    _verify_and_fix_exam_math, _buffered_question_count,
    _max_generation_seconds_exam, _is_medium_linear_param_quadratic_exam,
)

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


def _pyt(n, tag=None, safe=False):
    d = {
        "tresc": f"Testowe zadanie {n}?",
        "opcje": ["a) x", "b) y", "c) z", "d) w"],
        "odpowiedz": "a",
        "final_answer": "x",
        "diversity_tag": tag,
    }
    if safe:
        d["_safe_generated"] = True
    return d


def _data(pytania):
    return {"sekcje": [{"nazwa": "Czesc A", "typ": "zamkniete", "pytania": pytania}]}


SAME_TAG = {"skill": "wzor na delte", "concept": "parametr jako wyraz wolny",
            "task_type": "wyznacz parametr", "reasoning": "oblicz delte, rozwiaz nierownosc"}
DIFFERENT_TAG = {"skill": "twierdzenie sinusow", "concept": "trojkat dowolny",
                  "task_type": "oblicz bok trojkata", "reasoning": "zastosuj wzor, podstaw dane"}

print("=" * 70)
print("1. Diversity Engine w Sprawdzianie - odrzuca schemat-duplikat")
print("=" * 70)

data = _data([_pyt(1, SAME_TAG), _pyt(2, SAME_TAG), _pyt(3, SAME_TAG), _pyt(4, DIFFERENT_TAG)])
seen = []
result = _verify_and_fix_exam_math(data, seen_diversity_tags=seen)
kept = result["sekcje"][0]["pytania"]
check("z 4 zadan (3x ten sam schemat + 1 rozny) -> zostaja 2", len(kept) == 2, kept)

print()
print("=" * 70)
print("2. Brak diversity_tag -> nie blokuje (bezpieczny abstain)")
print("=" * 70)

data2 = _data([_pyt(1, None), _pyt(2, None), _pyt(3, None)])
result2 = _verify_and_fix_exam_math(data2, seen_diversity_tags=[])
check("3 zadania BEZ tagu -> wszystkie 3 zaakceptowane", len(result2["sekcje"][0]["pytania"]) == 3, None)

print()
print("=" * 70)
print("3. _safe_generated -> WYLACZONE z Diversity Engine, flaga usunieta z wyniku")
print("=" * 70)

data3 = _data([_pyt(i, SAME_TAG, safe=True) for i in range(6)])
result3 = _verify_and_fix_exam_math(data3, seen_diversity_tags=[])
kept3 = result3["sekcje"][0]["pytania"]
check("6 zadan tego samego schematu, wszystkie _safe_generated -> wszystkie 6 zaakceptowane",
      len(kept3) == 6, len(kept3))
check("flaga _safe_generated usunieta z wyniku (nie wycieka)",
      all("_safe_generated" not in p for p in kept3), None)

print()
print("=" * 70)
print("4. Bufor +50% dla medium quadratic (port z Quizu)")
print("=" * 70)

check("n=13, rownania kwadratowe, srednia -> bufor 20 (13+7, +50%)",
      _buffered_question_count(13, temat="Rownania kwadratowe", trudnosc="srednia") == 20,
      _buffered_question_count(13, temat="Rownania kwadratowe", trudnosc="srednia"))
check("n=13, inny temat, srednia -> bufor bez zmian (+30%)",
      _buffered_question_count(13, temat="Trygonometria", trudnosc="srednia") == 17,
      _buffered_question_count(13, temat="Trygonometria", trudnosc="srednia"))
check("n=13, rownania kwadratowe, trudna -> bufor +60% bez zmian",
      _buffered_question_count(13, temat="Rownania kwadratowe", trudnosc="trudna") == 21,
      _buffered_question_count(13, temat="Rownania kwadratowe", trudnosc="trudna"))

print()
print("=" * 70)
print("5. Limit czasowy: 60s dla latwy/sredni (jawna decyzja usera - Sprawdzian")
print("   dodatkowo buduje PDF, wiec potrzebuje wiecej marginesu niz Quiz),")
print("   120s dla trudny/trudna (ZWIEKSZONE 29.08.2026 po naprawie buga z")
print("   pominieta Warstwa 2.5 w rundach dogenerowania - patrz komentarz nad")
print("   _HARD_TIMEOUT_SECONDS_EXAM w exam_pdf_generator.py)")
print("=" * 70)

check("rownania kwadratowe + srednia -> 60s", _max_generation_seconds_exam("Rownania kwadratowe", "srednia") == 60.0, None)
check("rownania kwadratowe + trudna -> 120s (podwyzszone dla trudnych)", _max_generation_seconds_exam("Rownania kwadratowe", "trudna") == 120.0, None)
check("inny temat + srednia -> 60s (jednolicie)", _max_generation_seconds_exam("Trygonometria", "srednia") == 60.0, None)
check("brak tematu -> 60s (jednolicie)", _max_generation_seconds_exam(None, "srednia") == 60.0, None)

print()
print("=" * 70)
print("6. Gating Safe Parameter Generation - TYLKO medium quadratic")
print("=" * 70)

check("rownania kwadratowe + srednia -> True", _is_medium_linear_param_quadratic_exam("Rownania kwadratowe", "srednia") is True, None)
check("rownania kwadratowe + trudna -> False", _is_medium_linear_param_quadratic_exam("Rownania kwadratowe", "trudna") is False, None)
check("inny temat + srednia -> False", _is_medium_linear_param_quadratic_exam("Trygonometria", "srednia") is False, None)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
