# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: niepewnosc czy Quiz z SAMEGO
tematu - bez zdjecia - tez dziala niezawodnie, po tym jak Quiz ze zdjecia
mial powazny blad). To jest sciezka produkcyjna (generate_quiz_from_topic,
aktualnie na gpt-4o-mini po dzisiejszym swapie) - n=5, jak w realnym
uzyciu, 2 rozne tematy zeby nie polegac na jednej probie."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from app.openai_exam import generate_quiz_from_topic


async def run(topic, level, difficulty="medium", n=5):
    print(f"\n{'='*70}\nQuiz z tematu: '{topic}' ({level}, {difficulty}, n={n})\n{'='*70}")
    t0 = time.time()
    result = await generate_quiz_from_topic(
        topic=topic, subject="matematyka", level=level,
        num_questions=n, difficulty=difficulty,
    )
    elapsed = time.time() - t0
    print(f"Czas: {elapsed:.1f}s, success: {result.get('success')}")
    if not result.get("success"):
        print(f"BLAD: {result.get('error')}")
        return False
    questions = result["quiz"].get("questions", [])
    print(f"Otrzymano: {len(questions)}/{n}")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q.get('question')}  [opcje: {q.get('options')}]  [final_answer: {q.get('final_answer')}]")
    return len(questions) == n


async def main():
    ok1 = await run("Pole i obwod figur plaskich", "podstawowka_6")
    ok2 = await run("Funkcje trygonometryczne", "liceum_2")
    print(f"\n{'='*70}\nWYNIK: test1={'OK 5/5' if ok1 else 'NIEPELNY'}, test2={'OK 5/5' if ok2 else 'NIEPELNY'}")


if __name__ == "__main__":
    asyncio.run(main())
