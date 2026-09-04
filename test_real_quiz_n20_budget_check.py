# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: "czy czas jest odpowiedni jak
ktos wybierze 20 pytan") - sprawdza jak dziala generowanie duzego quizu
(n=20, maksimum na suwaku w quiz_app.html) przy STALYM budzecie czasu
(_max_generation_seconds nie skaluje sie z num_questions - potwierdzone
w kodzie). Uzywa tematu ktory JUZ wiemy ze dziala dobrze (geometria),
zeby zmierzyc czysto wplyw duzego n, bez mieszania z problemem trudnosci
trygonometrii."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from app.openai_exam import generate_quiz_from_topic


async def main():
    print("Quiz z tematu: 'Pole i obwod figur plaskich' (podstawowka_6, medium, n=20)")
    t0 = time.time()
    result = await generate_quiz_from_topic(
        topic="Pole i obwod figur plaskich", subject="matematyka", level="podstawowka_6",
        num_questions=20, difficulty="medium",
    )
    elapsed = time.time() - t0
    print(f"Czas: {elapsed:.1f}s, success: {result.get('success')}")
    if not result.get("success"):
        print(f"BLAD: {result.get('error')}")
        return
    questions = result["quiz"].get("questions", [])
    print(f"Otrzymano: {len(questions)}/20")


if __name__ == "__main__":
    asyncio.run(main())
