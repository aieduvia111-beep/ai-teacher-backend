# -*- coding: utf-8 -*-
"""REALNY test (koszt API) - weryfikuje naprawe z 04.09.2026 (level=
przekazywany do get_sequence_difficulty_anchor/get_trig_difficulty_anchor
+ wzmocniony tekst tieru "2-3" dla ciagow). 3 powtorzenia kazdego tematu
(n=3, liceum_2, medium) - zeby odroznic realna poprawe od losowego
trafienia (te tematy maja z natury zmienny wskaznik odrzucen)."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from app.openai_exam import generate_quiz_from_topic


async def run(topic, level, i):
    t0 = time.time()
    result = await generate_quiz_from_topic(
        topic=topic, subject="matematyka", level=level,
        num_questions=3, difficulty="medium",
    )
    elapsed = time.time() - t0
    n = len(result.get("quiz", {}).get("questions", [])) if result.get("success") else 0
    print(f"  proba {i}: {n}/3 w {elapsed:.1f}s" + ("" if result.get("success") else f" (BLAD: {result.get('error')})"))
    return n == 3


async def main():
    for topic in ["Ciagi arytmetyczne i geometryczne", "Funkcje trygonometryczne"]:
        print(f"\n{'='*70}\n{topic} (liceum_2, medium, n=3) x3\n{'='*70}")
        oks = []
        for i in range(1, 4):
            oks.append(await run(topic, "liceum_2", i))
        print(f"WYNIK: {sum(oks)}/3 probek udanych")


if __name__ == "__main__":
    asyncio.run(main())
