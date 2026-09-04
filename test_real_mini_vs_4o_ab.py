# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user poprosil "przetestuj ale oszczednie" 04.09.2026):
porownanie gpt-4o vs gpt-4o-mini na DWOCH najwiekszych, jeszcze nie zmienionych
funkcjach: Czat (rozwiazywanie zadan) i Quiz/Fiszki (dziela ten sam silnik
generate_quiz_from_topic w openai_exam.py).

Male N wszedzie (3 zadania w czacie, n=3 w quizie x2 modele) - to sprawdzenie
CZY MINI DAJE RADE, nie pelny sprawdzian produkcyjny. Dla Quizu uzywamy
prawdziwego pipeline'u (generate_quiz_from_topic, z prawdziwa weryfikacja AI-2),
tylko podmieniamy model AI-1 przez monkeypatch klienta - zeby test byl 1:1
z tym, co faktycznie by sie stalo po zmianie modelu w kodzie.
"""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from openai import AsyncOpenAI
from app.config import settings
import app.openai_exam as oai
from app.api.chat import SYSTEM_PROMPT as CHAT_SYSTEM_PROMPT

REAL_CLIENT = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class _ForcedModelChat:
    """Owija .completions.create i wymusza podany model na kazdym wywolaniu -
    pozwala odpalic PRAWDZIWY pipeline (generate_quiz_from_topic, wliczajac
    AI-2/blind-verify) tak, jakby caly kod mial ten model na stale."""
    def __init__(self, real_completions, forced_model):
        self._real = real_completions
        self._forced_model = forced_model

    async def create(self, *a, **kw):
        kw["model"] = self._forced_model
        return await self._real.create(*a, **kw)


class _ForcedModelClientWrapper:
    def __init__(self, real_client, forced_model):
        self.chat = type("C", (), {"completions": _ForcedModelChat(real_client.chat.completions, forced_model)})()


# =====================================================================
# CZESC 1: CZAT - 3 zadania tekstowe (bez zdjec, zeby nie placic za vision),
# ten sam SYSTEM_PROMPT co produkcja (app/api/chat.py)
# =====================================================================
CHAT_PROBLEMS = [
    "Rozwiaz rownanie kwadratowe: 2x^2 - 8x + 6 = 0. Podaj oba rozwiazania.",
    "Oblicz pole trojkata prostokatnego o przyprostokatnych 6 cm i 8 cm.",
    "Oblicz pochodna funkcji f(x) = x^3 + 2x^2 - 5x + 1.",
]
# Oczekiwane odpowiedzi (do reczej weryfikacji poprawnosci):
#  1) x=1, x=3  (2x^2-8x+6=0 -> x^2-4x+3=0 -> (x-1)(x-3)=0)
#  2) Pole = 6*8/2 = 24 cm^2
#  3) f'(x) = 3x^2 + 4x - 5


async def run_chat_test(model_name):
    print(f"\n{'='*70}\nCZAT - model: {model_name}\n{'='*70}")
    results = []
    for i, problem in enumerate(CHAT_PROBLEMS, 1):
        t0 = time.time()
        resp = await REAL_CLIENT.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": problem},
            ],
            max_tokens=1500,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        elapsed = time.time() - t0
        text = resp.choices[0].message.content
        print(f"\n--- Zadanie {i} ({elapsed:.1f}s) ---\n{problem}\n>>> {text[:900]}")
        results.append(text)
    return results


# =====================================================================
# CZESC 2: QUIZ/FISZKI (wspolny silnik) - n=3, temat sredniej trudnosci,
# ten sam co uzywany w fiszkach i quizie
# =====================================================================
QUIZ_TOPIC = "Trygonometria - podstawowe tozsamosci"
QUIZ_LEVEL = "liceum_1"
QUIZ_DIFFICULTY = "medium"
QUIZ_N = 3


async def run_quiz_test(model_name, forced=False):
    print(f"\n{'='*70}\nQUIZ/FISZKI - model: {model_name}\n{'='*70}")
    original_client = oai.client
    if forced:
        oai.client = _ForcedModelClientWrapper(REAL_CLIENT, model_name)
    t0 = time.time()
    try:
        result = await oai.generate_quiz_from_topic(
            topic=QUIZ_TOPIC, subject="matematyka", level=QUIZ_LEVEL,
            num_questions=QUIZ_N, difficulty=QUIZ_DIFFICULTY,
        )
    finally:
        oai.client = original_client
    elapsed = time.time() - t0
    print(f"Czas: {elapsed:.1f}s, success: {result.get('success')}")
    if not result.get("success"):
        print(f"BLAD: {result.get('error')}")
        return result
    questions = result.get("quiz", {}).get("questions", [])
    print(f"Otrzymano: {len(questions)}/{QUIZ_N}")
    for i, q in enumerate(questions, 1):
        print(f"\n--- Pytanie {i} ---")
        print(f"  Tresc: {q.get('question')}")
        print(f"  Opcje: {q.get('options')}")
        print(f"  Poprawna (index): {q.get('correct')}")
        print(f"  final_answer: {q.get('final_answer')}")
    return result


async def main():
    print("### CZESC 1: CZAT (gpt-4o - baseline) ###")
    chat_4o = await run_chat_test("gpt-4o")

    print("\n\n### CZESC 1: CZAT (gpt-4o-mini - kandydat) ###")
    chat_mini = await run_chat_test("gpt-4o-mini")

    print("\n\n### CZESC 2: QUIZ/FISZKI (gpt-4o - baseline, bez zmian) ###")
    quiz_4o = await run_quiz_test("gpt-4o", forced=False)

    print("\n\n### CZESC 2: QUIZ/FISZKI (gpt-4o-mini - kandydat, wymuszony) ###")
    quiz_mini = await run_quiz_test("gpt-4o-mini", forced=True)

    print("\n\n" + "=" * 70)
    print("KONIEC TESTU - patrz output powyzej do recznej oceny jakosci")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
