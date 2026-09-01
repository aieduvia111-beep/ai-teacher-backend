# -*- coding: utf-8 -*-
"""REALNY test (koszt API) - user poprosil o potwierdzenie ze naprawa
z 01.09.2026 (get_quadratic_difficulty_anchor teraz uwzglednia level)
faktycznie dziala: DOKLADNIE scenariusz, ktory w telemetrii mial 0/20
zaakceptowanych (id=46: podstawowka_7, "Rownania kwadratowe", medium).

Male N (5), zeby test byl tani - to sprawdzenie CZY DZIALA, nie pelny
sprawdzian produkcyjny."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.openai_exam import generate_quiz_from_topic
from app.exam_pdf_generator import ExamGenerator
from app.config import settings

TEMAT = "Równania kwadratowe"
KLASA_QUIZ = "podstawowka_7"
KLASA_EXAM = "podstawowka"
N = 5


async def run_quiz():
    print("=" * 70)
    print(f"QUIZ: temat='{TEMAT}', poziom='{KLASA_QUIZ}', trudnosc='medium', n={N}")
    print("(dokladnie ten scenariusz co wczesniej mial 0/20 w telemetrii)")
    print("=" * 70)
    t0 = time.time()
    result = await generate_quiz_from_topic(
        topic=TEMAT, subject="matematyka", level=KLASA_QUIZ,
        num_questions=N, difficulty="medium",
    )
    elapsed = time.time() - t0
    print(f"\nCzas generowania: {elapsed:.1f}s")
    print(f"success: {result.get('success')}")
    if not result.get("success"):
        print(f"BLAD: {result.get('error')}")
        return False
    questions = result.get("quiz", {}).get("questions", [])
    print(f"Otrzymano pytan: {len(questions)}/{N}")
    for i, q in enumerate(questions, 1):
        print(f"\n--- Pytanie {i} ---")
        print(f"  Tresc: {q.get('question')}")
        print(f"  Opcje: {q.get('options')}")
        print(f"  Poprawna: {q.get('correct')}")
    return len(questions) == N


def run_exam():
    print("\n" + "=" * 70)
    print(f"SPRAWDZIAN: temat='{TEMAT}', poziom='{KLASA_EXAM}', trudnosc='srednia', n={N}")
    print("=" * 70)
    api_key = getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "openai_api_key", None)
    gen = ExamGenerator(api_key)
    t0 = time.time()
    data = gen._get_exam_data(TEMAT, KLASA_EXAM, "srednia", N)
    elapsed = time.time() - t0
    print(f"\nCzas generowania: {elapsed:.1f}s")
    sekcje = data.get("sekcje", [])
    zamkniete = [s for s in sekcje if s.get("typ") == "zamkniete"]
    otwarte = [s for s in sekcje if s.get("typ") == "otwarte"]
    pytania_zamkniete = zamkniete[0].get("pytania", []) if zamkniete else []
    pytania_otwarte = otwarte[0].get("pytania", []) if otwarte else []
    total = len(pytania_zamkniete) + len(pytania_otwarte)
    print(f"Zadania zamkniete: {len(pytania_zamkniete)}, otwarte: {len(pytania_otwarte)}, razem: {total}/{N}")
    print(f"_shortfall_warning: {data.get('_shortfall_warning')}")
    for i, p in enumerate(pytania_zamkniete, 1):
        print(f"\n--- Zadanie zamkniete {i} ---")
        print(f"  Tresc: {p.get('tresc')}")
        print(f"  Opcje: {p.get('opcje')}")
        print(f"  Odpowiedz: {p.get('odpowiedz')}")
    for i, p in enumerate(pytania_otwarte, 1):
        print(f"\n--- Zadanie otwarte {i} ---")
        print(f"  Tresc: {p.get('tresc')}")
        print(f"  Odpowiedz: {p.get('odpowiedz')}")
    return total == N


async def main():
    quiz_ok = await run_quiz()
    exam_ok = run_exam()
    print("\n" + "=" * 70)
    print(f"WYNIK: quiz {'OK' if quiz_ok else 'NIEPELNY'}, exam {'OK' if exam_ok else 'NIEPELNY'}")


if __name__ == "__main__":
    asyncio.run(main())
