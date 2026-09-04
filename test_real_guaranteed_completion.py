# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: "ma byc 20 na 20, 15 na 15
i tak dalej") - weryfikuje wzmocniony mechanizm ratunkowy (do 3 prob z
relax_difficulty=True) na DOKLADNIE tych scenariuszach, ktore wczesniej
(z JEDNA proba ratunkowa) nadal zawodzily."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from app.openai_exam import generate_quiz_from_topic
from app.exam_pdf_generator import ExamGenerator
from app.config import settings


async def test_quiz():
    print("=== QUIZ ===")
    for topic, level, n in [("Funkcje trygonometryczne", "liceum_2", 5)]:
        t0 = time.time()
        r = await generate_quiz_from_topic(topic=topic, subject="matematyka", level=level, num_questions=n, difficulty="medium")
        ok = r.get("success") and len(r.get("quiz", {}).get("questions", [])) == n
        print(f"{topic}: {'OK ' + str(n) + '/' + str(n) if ok else 'FAIL: ' + str(r.get('error'))} w {time.time()-t0:.1f}s")


def test_exam():
    print("\n=== SPRAWDZIAN ===")
    gen = ExamGenerator(settings.OPENAI_API_KEY)
    for temat, klasa, n in [("Rownania kwadratowe", "podstawowka_7", 8)]:
        t0 = time.time()
        data = gen._get_exam_data(temat, klasa, "srednia", n)
        total = sum(len(s.get("pytania", [])) for s in data.get("sekcje", []))
        ok = total == n
        print(f"{temat}: {'OK ' + str(total) + '/' + str(n) if ok else 'FAIL: ' + str(total) + '/' + str(n)} w {time.time()-t0:.1f}s" + (f" shortfall={data.get('_shortfall_warning')}" if data.get('_shortfall_warning') else ""))


async def main():
    await test_quiz()
    test_exam()


if __name__ == "__main__":
    asyncio.run(main())
