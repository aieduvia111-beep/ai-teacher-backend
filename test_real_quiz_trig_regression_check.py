# -*- coding: utf-8 -*-
"""REALNY test (koszt API) - 'Funkcje trygonometryczne' liceum_2 n=5
przed chwila NIE POWIODL SIE (2/5, ZABLOKOWANY) na gpt-4o-mini (dzisiejszy
swap _raw_generate_quiz_topic_once). Sprawdza, czy TEN SAM temat/poziom/n
dziala na gpt-4o (baseline sprzed swapu) - zeby ustalic, czy to REGRESJA
od dzisiejszej zmiany modelu, czy problem istniejacy wczesniej."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from openai import AsyncOpenAI
from app.config import settings
import app.openai_exam as oai

REAL_CLIENT = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class _ForcedModelChat:
    def __init__(self, real_completions, forced_model):
        self._real = real_completions
        self._forced_model = forced_model

    async def create(self, *a, **kw):
        kw["model"] = self._forced_model
        return await self._real.create(*a, **kw)


class _ForcedModelClientWrapper:
    def __init__(self, real_client, forced_model):
        self.chat = type("C", (), {"completions": _ForcedModelChat(real_client.chat.completions, forced_model)})()


async def run(model_name, forced):
    print(f"\n{'='*70}\nFunkcje trygonometryczne / liceum_2 / n=5 - model: {model_name}\n{'='*70}")
    original_client = oai.client
    if forced:
        oai.client = _ForcedModelClientWrapper(REAL_CLIENT, model_name)
    t0 = time.time()
    try:
        result = await oai.generate_quiz_from_topic(
            topic="Funkcje trygonometryczne", subject="matematyka", level="liceum_2",
            num_questions=5, difficulty="medium",
        )
    finally:
        oai.client = original_client
    elapsed = time.time() - t0
    print(f"Czas: {elapsed:.1f}s, success: {result.get('success')}")
    if not result.get("success"):
        print(f"BLAD: {result.get('error')}")
        return False
    questions = result["quiz"].get("questions", [])
    print(f"Otrzymano: {len(questions)}/5")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q.get('question')}")
    return len(questions) == 5


async def main():
    ok = await run("gpt-4o", forced=True)
    print(f"\nWYNIK gpt-4o (baseline sprzed swapu): {'5/5 OK' if ok else 'RÓWNIEŻ NIEPEŁNY'}")


if __name__ == "__main__":
    asyncio.run(main())
