# -*- coding: utf-8 -*-
"""Offline E2E: pelna sciezka QUIZU i SPRAWDZIANU dla tematow 'prostopadloscian' i 'kolejnosc dzialan'
przy ZABLOKOWANYM dostepie do OpenAI (kazde wywolanie AI = blad testu). Dowodzi: dokladnie N pytan, zero AI, zero kosztu."""
import os, sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from openai.resources.chat.completions import Completions, AsyncCompletions
AI_CALLS = []
def _boom(self, *a, **k): AI_CALLS.append(k.get("model")); raise RuntimeError("AI wywolane - test zablokowal")
async def _aboom(self, *a, **k): AI_CALLS.append(k.get("model")); raise RuntimeError("AI wywolane - test zablokowal")
Completions.create = _boom
AsyncCompletions.create = _aboom

from app.config import settings
import app.openai_exam as oe
from app.exam_pdf_generator import ExamGenerator

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

TOPICS = ["Matematyka: prostopadłościan", "Kolejność wykonywania działań"]
for topic in TOPICS:
    for n in (10, 15, 20):
        AI_CALLS.clear()
        try:
            res = asyncio.run(oe.generate_quiz_from_topic(topic=topic, subject="matematyka", level="technikum_5", num_questions=n, difficulty="hard"))
            qs = (res.get("quiz") or {}).get("questions", [])
            ok = res.get("success") and len(qs) == n and len({q["question"] for q in qs}) == n
            check(f"QUIZ '{topic[:24]}' n={n}: dokladnie {n} unikalnych pytan, zero AI", ok and not AI_CALLS, (res.get("success"), len(qs), AI_CALLS, res.get("error")))
        except Exception as e:
            check(f"QUIZ '{topic[:24]}' n={n}", False, repr(e))

    for n in (10, 15):
        AI_CALLS.clear()
        try:
            gen = ExamGenerator(settings.OPENAI_API_KEY or "sk-test")
            data = gen._get_exam_data(topic, "technikum_5", "trudna", n)
            total = sum(len(s.get("pytania", [])) for s in data.get("sekcje", []))
            check(f"SPRAWDZIAN '{topic[:24]}' n={n}: dokladnie {n} pytan, zero AI", total == n and not AI_CALLS, (total, AI_CALLS, data.get("_shortfall_warning")))
        except Exception as e:
            check(f"SPRAWDZIAN '{topic[:24]}' n={n}", False, repr(e))

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
