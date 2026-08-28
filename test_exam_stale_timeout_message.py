# -*- coding: utf-8 -*-
"""User real-test (n=6, rownania kwadratowe z parametrem, srednia) i
przeglad kodu przy okazji audytu Fiszek/limitow (sierpien 2026) ujawnily,
ze komunikat shortfallu Sprawdzianu mial NA STALE zaszyte "(30s)" w
_fill_missing_exam_questions (exam_pdf_generator.py), mimo ze budzet
zostal juz wczesniej tego samego dnia podniesiony do jednolitych 60s
(_TIMEOUT_SECONDS_EXAM, patrz commit "Podnies budzet czasowy Sprawdzianu
do jednolitych 60s"). User widzialby wiec mylacy komunikat "limit 30s",
mimo ze realnie egzekwowany budzet byl juz inny - test ponizej pilnuje,
zeby tekst zawsze odzwierciedlal PRAWDZIWA wartosc _TIMEOUT_SECONDS_EXAM,
a nie liczbe zaszyta na stale w stringu."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


import re
from app.exam_pdf_generator import _TIMEOUT_SECONDS_EXAM
with open(r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend\app\exam_pdf_generator.py", encoding="utf-8") as f:
    src = f.read()

check("brak zaszytego na stale '(30s)' w komunikacie shortfallu Sprawdzianu",
      '"przekroczono limit czasu (30s)"' not in src, None)
check("komunikat shortfallu uzywa PRAWDZIWEJ wartosci max_seconds (f-string z {max_seconds...)",
      "f\"przekroczono limit czasu ({max_seconds" in src, None)
check("_TIMEOUT_SECONDS_EXAM nadal 60.0 (zgodnie z jednolitym budzetem ustalonym przez usera)",
      _TIMEOUT_SECONDS_EXAM == 60.0, _TIMEOUT_SECONDS_EXAM)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
