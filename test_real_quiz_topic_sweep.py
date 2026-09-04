# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: "a inne tematy to jak") -
oszczedny przeglad kilku popularnych tematow (n=3 kazdy, zeby bylo tanio)
zeby sprawdzic czy problem kalibracji trudnosci (znaleziony dla
"Funkcje trygonometryczne") jest izolowany, czy wystepuje szerzej."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from app.openai_exam import generate_quiz_from_topic

CASES = [
    ("Procenty i proporcje", "podstawowka_7"),
    ("Ciagi arytmetyczne i geometryczne", "liceum_2"),
    ("Statystyka - srednia mediana dominanta", "liceum_1"),
    ("Potegi i pierwiastki", "podstawowka_8"),
]


async def run(topic, level):
    print(f"\n{'='*70}\n'{topic}' ({level}, medium, n=3)\n{'='*70}")
    t0 = time.time()
    result = await generate_quiz_from_topic(
        topic=topic, subject="matematyka", level=level,
        num_questions=3, difficulty="medium",
    )
    elapsed = time.time() - t0
    ok = result.get("success") and len(result.get("quiz", {}).get("questions", [])) == 3
    print(f"Czas: {elapsed:.1f}s -> {'OK 3/3' if ok else 'PROBLEM: ' + str(result.get('error') or len(result.get('quiz',{}).get('questions',[])))}")
    return ok


async def main():
    results = {}
    for topic, level in CASES:
        results[topic] = await run(topic, level)
    print(f"\n{'='*70}\nPODSUMOWANIE:")
    for topic, ok in results.items():
        print(f"  {'OK ' if ok else 'FAIL'} - {topic}")


if __name__ == "__main__":
    asyncio.run(main())
