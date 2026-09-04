# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: "czy wszystko dziala
perfekcyjnie, zrob testy") - szybki, tani smoke-test WSZYSTKICH funkcji
juz przelaczonych na gpt-4o-mini (Czat, Quiz z tematu, Quiz ze zdjecia),
zeby potwierdzic ze nic nie jest zepsute PO wszystkich dzisiejszych
zmianach (5 commitow: final_answer, level/topic, model swap, budzet
czasu, kalibracja ciagow/trygonometrii)."""
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
from app.api.chat import SYSTEM_PROMPT as CHAT_SYSTEM_PROMPT
from app.openai_exam import generate_quiz_from_topic, generate_quiz_from_image

REAL_CLIENT = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def check_chat():
    t0 = time.time()
    resp = await REAL_CLIENT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": "Rozwiaz: 3x - 7 = 11"},
        ],
        max_tokens=800, temperature=0.7,
        response_format={"type": "json_object"},
    )
    elapsed = time.time() - t0
    import json
    data = json.loads(resp.choices[0].message.content)
    ok = "x = 6" in data.get("text", "") or "x=6" in data.get("text", "")
    print(f"[CZAT] {elapsed:.1f}s -> {'OK (x=6 w odpowiedzi)' if ok else 'SPRAWDZ RECZNIE: ' + data.get('text','')[:200]}")


async def check_quiz_topic():
    t0 = time.time()
    r = await generate_quiz_from_topic(topic="Procenty", subject="matematyka", level="podstawowka_7", num_questions=3, difficulty="medium")
    elapsed = time.time() - t0
    n = len(r.get("quiz", {}).get("questions", [])) if r.get("success") else 0
    print(f"[QUIZ z tematu] {elapsed:.1f}s -> {n}/3" + ("" if r.get('success') else f" BLAD: {r.get('error')}"))


def _make_img():
    img = Image.new("RGB", (700, 300), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 30), "Notatki: Procenty", fill="black")
    d.text((30, 90), "- 10% z 200 = 20", fill="black")
    d.text((30, 150), "- 25% z 80 = 20", fill="black")
    buf = io.BytesIO(); img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


async def check_quiz_image():
    t0 = time.time()
    r = await generate_quiz_from_image(_make_img(), num_questions=3, difficulty="medium", level="podstawowka_7", subject="matematyka", topic="Procenty")
    elapsed = time.time() - t0
    n = len(r.get("quiz", {}).get("questions", [])) if r.get("success") else 0
    print(f"[QUIZ ze zdjecia] {elapsed:.1f}s -> {n}/3" + ("" if r.get('success') else f" BLAD: {r.get('error')}"))


async def main():
    print("SMOKE-TEST wszystkich funkcji na gpt-4o-mini po dzisiejszych zmianach\n" + "="*70)
    await check_chat()
    await check_quiz_topic()
    await check_quiz_image()


if __name__ == "__main__":
    asyncio.run(main())
