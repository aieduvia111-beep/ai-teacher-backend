# -*- coding: utf-8 -*-
"""Offline E2E: zamowienie 'Matematyka' bez tematu dla liceum/technikum przy ZABLOKOWANYM OpenAI:
dokladnie N pytan, zero wywolan AI, zakres zgodny z poziomem. Poziomy nieobslugiwane (podstawowka)
i trudnosc 'hard' NIE moga isc sciezka generatora (zachowanie bez zmian)."""
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

import app.openai_exam as oe

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

for lv in ["liceum_1", "technikum_1", "liceum_2", "technikum_2", "technikum_3", "matura_podstawowa"]:
    for n in (10, 20):
        AI_CALLS.clear()
        try:
            res = asyncio.run(oe.generate_quiz_from_topic(topic="Matematyka", subject="matematyka", level=lv, num_questions=n, difficulty="medium"))
            qs = (res.get("quiz") or {}).get("questions", [])
            ok = res.get("success") and len(qs) == n and len({q["question"] for q in qs}) == n
            check(f"{lv} n={n}: dokladnie {n} unikalnych pytan, zero AI", ok and not AI_CALLS, (res.get("success"), len(qs), AI_CALLS, res.get("error")))
        except Exception as e:
            check(f"{lv} n={n}", False, repr(e))

check("dispatch: podstawowka NIE uzywa generatora", not oe._is_generic_hs_math("Matematyka", "matematyka", "podstawowka_6", "medium"))
check("dispatch: trudnosc 'hard' NIE uzywa generatora", not oe._is_generic_hs_math("Matematyka", "matematyka", "liceum_1", "hard"))
check("dispatch: konkretny temat NIE uzywa generatora", not oe._is_generic_hs_math("Funkcja kwadratowa", "matematyka", "liceum_1", "medium"))
check("dispatch: inny przedmiot NIE uzywa generatora", not oe._is_generic_hs_math("Fizyka", "fizyka", "liceum_1", "medium"))
check("dispatch: liceum_1 + ogolna matematyka + medium UZYWA generatora", oe._is_generic_hs_math("Matematyka", "matematyka", "liceum_1", "medium"))

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
