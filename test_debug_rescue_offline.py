# -*- coding: utf-8 -*-
"""DEBUG OFFLINE (zero kosztu API) - sprawdza, czy petla ratunkowa w
_fill_missing_exam_questions w ogole sie uruchamia, przez monkeypatch
metod generujacych (zero prawdziwych wywolan OpenAI)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from app.exam_pdf_generator import ExamGenerator
from app.config import settings

gen = ExamGenerator(settings.OPENAI_API_KEY)

# Symuluj stan PO wyczerpaniu normalnych/grace rund: 4 zamkniete zaakceptowane, 0 otwartych, cel 8.
data = {
    "sekcje": [
        {"nazwa": "Czesc A", "typ": "zamkniete", "instrukcja_sekcji": "x", "pytania": [
            {"tresc": f"Zadanie {i}", "opcje": ["a","b","c","d"], "odpowiedz": "a", "final_answer": "a", "wyjasnienie": "x"} for i in range(4)
        ]},
    ]
}

call_log = []

def fake_raw_parallel(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block="", only_open=False):
    call_log.append(("raw_parallel", n, only_open))
    print(f"  [FAKE] _get_exam_data_raw_parallel wywolane: n={n} only_open={only_open}")
    return {"sekcje": []}  # symuluj: nic nie wygenerowano (zawsze pusto)

gen._get_exam_data_raw_parallel = fake_raw_parallel

import time
t_start = time.monotonic() - 999  # symuluj: budzet JUZ dawno przekroczony, zeby petla glowna od razu przeszla do konca

result = gen._fill_missing_exam_questions(
    data, "Rownania kwadratowe", "podstawowka_7", "srednia", 8,
    wlasne_instrukcje=None, przedmiot="matematyka", t_start=t_start,
)

print(f"\nWywolania fake_raw_parallel: {len(call_log)}")
for c in call_log:
    print(f"  {c}")
total = sum(len(s.get("pytania", [])) for s in result.get("sekcje", []))
print(f"\nWynik koncowy: {total}/8")
print(f"shortfall_warning: {result.get('_shortfall_warning')}")
