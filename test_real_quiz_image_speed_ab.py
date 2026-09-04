# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: quiz z tematem+zdjeciem, n=5,
"czas minal", 2-3/5 zamiast 5/5) - sprawdza czy gpt-4o-mini dla Quizu ze
zdjecia jest ROWNIE dokladny i (kluczowe dla problemu timeoutu) SZYBSZY/
potrzebuje mniej rund dogenerowania niz gpt-4o. n=5, jeden real przebieg
na kazdy model (bez zbednego powtarzania - user czeka)."""
import asyncio
import base64
import io
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from PIL import Image, ImageDraw
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


def make_test_image() -> str:
    img = Image.new("RGB", (900, 560), "white")
    d = ImageDraw.Draw(img)
    lines = [
        "Notatki: Geometria plaska",
        "- Pole prostokata: P = a * b, Obwod: Obw = 2(a+b)",
        "- Pole trojkata: P = (a * h) / 2",
        "- Pole kola: P = pi * r^2, Obwod: Obw = 2 * pi * r",
        "- Twierdzenie Pitagorasa: a^2 + b^2 = c^2",
        "Przyklad: prostokat a=6cm, b=9cm",
        "Przyklad: kolo r=4cm",
    ]
    y = 25
    for line in lines:
        d.text((30, y), line, fill="black")
        y += 60
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


async def run(model_name, forced):
    print(f"\n{'='*70}\nQuiz ze zdjecia n=5 - model: {model_name}\n{'='*70}")
    img_b64 = make_test_image()
    original_client = oai.client
    if forced:
        oai.client = _ForcedModelClientWrapper(REAL_CLIENT, model_name)
    t0 = time.time()
    try:
        result = await oai.generate_quiz_from_image(
            img_b64, num_questions=5, difficulty="medium",
            level="liceum_2", subject="matematyka", topic="Pole i obwod figur",
        )
    finally:
        oai.client = original_client
    elapsed = time.time() - t0
    print(f"Czas CALKOWITY: {elapsed:.1f}s, success: {result.get('success')}")
    if not result.get("success"):
        print(f"BLAD: {result.get('error')}")
        return
    questions = result["quiz"].get("questions", [])
    print(f"Otrzymano: {len(questions)}/5")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q.get('question')}")


async def main():
    await run("gpt-4o", forced=False)
    await run("gpt-4o-mini", forced=True)


if __name__ == "__main__":
    asyncio.run(main())
