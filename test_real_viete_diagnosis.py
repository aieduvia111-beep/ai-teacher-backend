# -*- coding: utf-8 -*-
"""REALNY test (koszt API) - diagnoza zgloszonego wczesniej total-failure
dla tematu "Wzory Viete" w Quizie. Hipoteza (potwierdzona statycznie w
kodzie): is_quadratic_equation_topic("Wzory Viete") zwraca False (wymaga
"rownan"+"kwadratow" w temacie), wiec AI NIE dostaje zadnej kalibracji
trudnosci (get_quadratic_difficulty_anchor nigdy wywolane) - ale
walidator (Warstwa 3, classify_quadratic_difficulty) i tak KLASYFIKUJE
kazde pytanie o wzorach Viete'a jako tier 7-8 (patrz math_verify.py:394),
NIEZALEZNIE od tematu - bo dziala na TRESCI pytania, nie na temacie.
Efekt: AI strzela na slepo, walidator oczekuje 7-8, dokladnie ten sam
mechanizm co oryginalny blog rownan kwadratowych sprzed tego sesji."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from app.openai_exam import generate_quiz_from_topic
from app.level_config import is_quadratic_equation_topic


async def main():
    topic_a = "Wzory Viete'a"
    topic_b = "Wzory Viete"
    print(f"is_quadratic_equation_topic({topic_a!r}): {is_quadratic_equation_topic(topic_a)}")
    print(f"is_quadratic_equation_topic({topic_b!r}): {is_quadratic_equation_topic(topic_b)}")
    t0 = time.time()
    r = await generate_quiz_from_topic(
        topic="Wzory Viete'a", subject="matematyka", level="liceum_2",
        num_questions=3, difficulty="medium",
    )
    elapsed = time.time() - t0
    n = len(r.get("quiz", {}).get("questions", [])) if r.get("success") else 0
    print(f"\nWYNIK: {n}/3 w {elapsed:.1f}s" + ("" if r.get('success') else f" BLAD: {r.get('error')}"))


if __name__ == "__main__":
    asyncio.run(main())
