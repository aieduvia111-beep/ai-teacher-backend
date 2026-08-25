# -*- coding: utf-8 -*-
"""NAPRAWA (znalezione PRZY realnym tescie Safe Parameter Generation,
sierpien 2026): Safe Parameter Generation CELOWO generuje wiele pytan
TEGO SAMEGO podwzorca (dogenerowanie niezawodnie poprawnych pytan dla
tematu, gdzie wolna generacja regularnie zawodzi) - to z definicji
koliduje z Universal Diversity Engine, ktora rownie celowo odrzuca
wiele pytan tego samego schematu. Realny test pokazal: niemal WSZYSTKIE
bezpiecznie wygenerowane pytania byly odrzucane jako "zbyt podobne" do
PIERWSZEGO takiego pytania, dajac 1-3 pytania zamiast potrzebnych
kilkunastu. Naprawiono: pytania oznaczone prywatnym kluczem
"_safe_generated" (patrz _raw_generate_safe_linear_param_quadratic_batch)
sa WYLACZONE z kontroli Diversity Engine."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.openai_exam import _verify_and_fix_quiz_math

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


SAFE_TAG = {"skill": "wzor na delte", "concept": "parametr jako wspolczynnik liniowy",
            "task_type": "wyznacz parametr z warunku na delte", "reasoning": "oblicz delte, rozwiaz nierownosc, zapisz przedzial"}


def _safe_q(n):
    return {
        "question": f"Dla jakich wartości parametru {chr(97+n)} równanie $x^2+{chr(97+n)}x+{(n+1)**2}=0$ ma dwa różne pierwiastki?",
        "options": [f"${chr(97+n)} < -{2*(n+1)}$ lub ${chr(97+n)} > {2*(n+1)}$", "a", "b", "c"],
        "correct": 0,
        "final_answer": f"${chr(97+n)} < -{2*(n+1)}$ lub ${chr(97+n)} > {2*(n+1)}$",
        "diversity_tag": SAFE_TAG,
        "_safe_generated": True,
    }


print("=" * 70)
print("Pytania z flaga _safe_generated=True -> WYLACZONE z Diversity Engine")
print("=" * 70)

quiz = {"title": "Test", "questions": [_safe_q(i) for i in range(8)]}
seen = []
result = _verify_and_fix_quiz_math(quiz, seen_diversity_tags=seen)
check("8 pytan TEGO SAMEGO schematu, wszystkie _safe_generated=True -> WSZYSTKIE 8 zaakceptowane",
      len(result["questions"]) == 8, len(result["questions"]))

print()
print("=" * 70)
print("Flaga _safe_generated jest USUWANA z finalnego wyniku (nie wycieka do frontendu)")
print("=" * 70)

check("zaden zwrocony question dict nie zawiera juz klucza '_safe_generated'",
      all("_safe_generated" not in q for q in result["questions"]),
      [q.get("_safe_generated") for q in result["questions"]])

print()
print("=" * 70)
print("Regresja: bez flagi (normalne pytania) Diversity Engine dziala jak wczesniej")
print("=" * 70)

def _normal_q(n):
    q = _safe_q(n)
    del q["_safe_generated"]
    return q

quiz2 = {"title": "Test", "questions": [_normal_q(i) for i in range(5)]}
seen2 = []
result2 = _verify_and_fix_quiz_math(quiz2, seen_diversity_tags=seen2)
check("5 pytan TEGO SAMEGO schematu BEZ flagi -> tylko 1 zaakceptowane (Diversity Engine dziala normalnie)",
      len(result2["questions"]) == 1, len(result2["questions"]))

print()
print("=" * 70)
print("Mix: safe-generated + normalne w tej samej partii")
print("=" * 70)

quiz3 = {"title": "Test", "questions": [_normal_q(0)] + [_safe_q(i) for i in range(1, 6)]}
seen3 = []
result3 = _verify_and_fix_quiz_math(quiz3, seen_diversity_tags=seen3)
check("1 normalne (przechodzi) + 5 safe-generated (wszystkie przechodza) -> 6 razem",
      len(result3["questions"]) == 6, len(result3["questions"]))

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
