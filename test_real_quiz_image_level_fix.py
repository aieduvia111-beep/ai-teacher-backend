# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: "0 na 5 wygenerowanych" +
"poziom ma byc odpowiedni" przy Quizie ze zdjecia) - potwierdza, ze
naprawa (przekazanie level/topic do generate_quiz_from_image) faktycznie
dziala: to samo zdjecie, dwa rozne poziomy - trudnosc pytan MUSI sie
roznic, jesli level naprawde dociera do promptu.

Tanie: n=3, jeden prosty wygenerowany obrazek (PIL, bez kosztu), 2
wywolania pelnego pipeline'u (z prawdziwa weryfikacja AI-2)."""
import asyncio
import base64
import io
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from PIL import Image, ImageDraw
from app.openai_exam import generate_quiz_from_image


def make_test_image() -> str:
    img = Image.new("RGB", (900, 500), "white")
    d = ImageDraw.Draw(img)
    lines = [
        "Notatki: Geometria plaska",
        "- Pole prostokata: P = a * b",
        "- Pole trojkata: P = (a * h) / 2",
        "- Pole kola: P = pi * r^2",
        "- Obwod prostokata: Obw = 2(a+b)",
        "- Obwod kola: Obw = 2 * pi * r",
    ]
    y = 30
    for line in lines:
        d.text((30, y), line, fill="black")
        y += 60
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


async def run(level_label, level):
    print(f"\n{'='*70}\nQuiz ze zdjecia - level={level!r} ({level_label})\n{'='*70}")
    img_b64 = make_test_image()
    t0 = time.time()
    result = await generate_quiz_from_image(
        img_b64, num_questions=3, difficulty="medium",
        level=level, subject="matematyka", topic="Pole i obwod figur",
    )
    elapsed = time.time() - t0
    print(f"Czas: {elapsed:.1f}s, success: {result.get('success')}")
    if not result.get("success"):
        print(f"BLAD: {result.get('error')}")
        return
    questions = result["quiz"].get("questions", [])
    print(f"Otrzymano: {len(questions)}/3")
    for i, q in enumerate(questions, 1):
        print(f"\n--- Pytanie {i} ---")
        print(f"  Tresc: {q.get('question')}")
        print(f"  Opcje: {q.get('options')}")


async def main():
    # Brak level - stare zachowanie (baseline liceum_2, tak jak przed fixem)
    await run("BEZ level (stare zachowanie)", None)
    # Bardzo niski poziom - pytania MUSZA byc wyraznie prostsze
    await run("podstawowka_4 (10-latek)", "podstawowka_4")
    # Wysoki poziom - pytania MOGA byc trudniejsze / bardziej zlozone
    await run("liceum_3 (zaawansowany)", "liceum_3")


if __name__ == "__main__":
    asyncio.run(main())
