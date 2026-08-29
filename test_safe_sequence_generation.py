# -*- coding: utf-8 -*-
"""User (29.08.2026, po dwoch udanych real-testach trygonometrii i
prosbie "rozszerz... aby caly system byl profesjonalny"): kontynuacja
Safe Parameter Generation na KOLEJNY temat - ciagi arytmetyczne, poziom
trudny. Archetyp wybrany na podstawie OFICJALNEGO, juz istniejacego w
tym systemie kryterium poziomu 4-5 dla ciagow (SEQUENCE_DIFFICULTY_TIERS
w level_config.py): "Uklad DWOCH warunkow jednoczesnie... dwa rozne
wyrazy ciagu" - przyklad tam wprost: "W ciagu arytmetycznym a3=10,
a7=22. Wyznacz pierwszy wyraz i roznice."

KOD wybiera a1 i r JAKO PIERWSZE, liczy PRAWDZIWE wartosci dwoch wyrazow
z tych parametrow, i DOPIERO wtedy formuluje pytanie w odwrotnej
kolejnosci - poprawnosc gwarantowana przez konstrukcje (identyczny
wzorzec co Warstwa dla rownan kwadratowych i trygonometrii).

Ten plik testuje SAMA logike (zero AI, zero kosztu)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import build_safe_sequence_two_terms, verify_sequence_two_terms

print("=" * 70)
print("Real przypadek (dokladnie oficjalny przyklad z level_config.py)")
print("=" * 70)
sk = build_safe_sequence_two_terms(a1=4, r=3, m=3, n=7)
check("a_3 = 10, a_7 = 22 (dokladnie jak oficjalny przyklad 'a3=10, a7=22')",
      sk["a_m_val"] == 10 and sk["a_n_val"] == 22, sk)
check("Tresc pytania pasuje do oficjalnego wzorca",
      "a_{3} = 10" in sk["question_text"] and "a_{7} = 22" in sk["question_text"], sk["question_text"])
check("Poprawna odpowiedz: a_1 = 4, r = 3",
      sk["correct_text"] == "a_1 = 4, r = 3", sk["correct_text"])

print()
print("=" * 70)
print("Poprawnosc na 200 losowych probach (niezalezna sciezka - sympy solve)")
print("=" * 70)
all_correct = True
first_fail = None
for _ in range(200):
    sk = build_safe_sequence_two_terms()
    ok = verify_sequence_two_terms(sk["a1"], sk["r"], sk["m"], sk["n"], sk["a_m_val"], sk["a_n_val"])
    if not ok:
        all_correct = False
        first_fail = sk
        break
check("200/200 poprawne wg niezaleznej weryfikacji (sympy solve ukladu rownan)",
      all_correct, first_fail)

print()
print("=" * 70)
print("Dystraktory - nigdy nie koliduja z poprawna odpowiedzia ani ze soba")
print("=" * 70)
collision = False
for _ in range(200):
    sk = build_safe_sequence_two_terms()
    all_texts = [sk["correct_text"]] + sk["distractors"]
    if sk["correct_text"] in sk["distractors"] or len(set(all_texts)) != 4:
        collision = True
        print(f"  KOLIZJA: {sk}")
check("200 losowych prob - zawsze 4 rozne teksty (1 poprawny + 3 dystraktory)",
      not collision)

print()
print("=" * 70)
print("Gating: _is_hard_arithmetic_sequence (Quiz) - TYLKO ciagi")
print("ARYTMETYCZNE (NIE geometryczne) + trudny")
print("=" * 70)
from app.openai_exam import _is_hard_arithmetic_sequence
check("ciagi arytmetyczne + trudny -> True",
      _is_hard_arithmetic_sequence("Matematyka: ciągi arytmetyczne", "trudny") is True)
check("ciagi arytmetyczne + hard -> True (angielski synonim)",
      _is_hard_arithmetic_sequence("ciągi arytmetyczne", "hard") is True)
check("ciagi arytmetyczne + srednia -> False (tylko trudny)",
      _is_hard_arithmetic_sequence("ciągi arytmetyczne", "srednia") is False)
check("ciagi GEOMETRYCZNE + trudny -> False (archetyp jest tylko dla arytmetycznych)",
      _is_hard_arithmetic_sequence("ciągi geometryczne", "trudny") is False)
check("temat wspominajacy OBA rodzaje ciagow -> False (niejednoznaczne, bezpieczny abstain)",
      _is_hard_arithmetic_sequence("ciągi arytmetyczne i geometryczne", "trudny") is False)
check("inny temat + trudny -> False",
      _is_hard_arithmetic_sequence("Rownania kwadratowe", "trudny") is False)

print()
print("=" * 70)
print("Gating: _is_hard_arithmetic_sequence_exam (Sprawdzian) - identyczna logika")
print("=" * 70)
from app.exam_pdf_generator import _is_hard_arithmetic_sequence_exam
check("ciagi arytmetyczne + trudna -> True",
      _is_hard_arithmetic_sequence_exam("Matematyka: ciągi arytmetyczne", "trudna") is True)
check("ciagi geometryczne + trudna -> False",
      _is_hard_arithmetic_sequence_exam("ciągi geometryczne", "trudna") is False)
check("ciagi arytmetyczne + srednia -> False",
      _is_hard_arithmetic_sequence_exam("ciągi arytmetyczne", "srednia") is False)

print()
print("=" * 70)
print("Warstwa 2/2.5 EXEMPTION - dziedziczona automatycznie z 'safe_generated'")
print("(mechanizm juz istnieje dla trygonometrii/rownan kwadratowych -")
print("ten test potwierdza ze dziala TEZ dla tego archetypu)")
print("=" * 70)
import asyncio
from app.openai_exam import _verify_and_fix_quiz_math

fake_safe_q = {
    "question": "W ciągu arytmetycznym a_5=X, a_9=Y. Wyznacz a1 i r.",
    "options": ["a_1 = 1, r = 1", "a_1 = 2, r = 2", "a_1 = 3, r = 3", "a_1 = 4, r = 4"],
    "correct": 0, "final_answer": "a_1 = 1, r = 1", "explanation": "test",
    "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"},
    "_safe_generated": True,
}
result = asyncio.run(_verify_and_fix_quiz_math({"questions": [dict(fake_safe_q)]}))
check("Pytanie _safe_generated (archetyp ciagow) -> zaakceptowane bez blind-check",
      len(result.get("questions", [])) == 1, result)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
