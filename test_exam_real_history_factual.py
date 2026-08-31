# -*- coding: utf-8 -*-
"""Realny test (koszt API, maly - n=6) POZA matematyka - Historia, zeby
sprawdzic mechanizm blind-verify-factual (problem_class='factual'),
jeszcze nie testowany live w tej sesji. Nie ma tu sympy - poprawnosc
faktograficzna trzeba ocenic recznie (czyta czlowiek/Claude po
wygenerowaniu), test tylko potwierdza ze generacja dziala i
klasyfikacja problem_class jest sensowna."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.config import settings
from app.exam_pdf_generator import ExamGenerator

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


api_key = getattr(settings, "OPENAI_API_KEY", None)
gen = ExamGenerator(api_key)

N_REQUESTED = 6
TEMAT = "Historia: II wojna światowa - najważniejsze wydarzenia i daty"
TRUDNOSC = "srednia"
KLASA = "liceum_2"

print("=" * 70)
print(f"Realny test: n={N_REQUESTED}, temat='{TEMAT}', trudnosc='{TRUDNOSC}'")
print("=" * 70)

data = gen._get_exam_data(TEMAT, KLASA, TRUDNOSC, N_REQUESTED)

sekcje = data.get("sekcje", [])
zamkniete = [s for s in sekcje if s.get("typ") == "zamkniete"]
otwarte = [s for s in sekcje if s.get("typ") == "otwarte"]
pytania_zamkniete = zamkniete[0].get("pytania", []) if zamkniete else []
pytania_otwarte = otwarte[0].get("pytania", []) if otwarte else []

check(f"generacja zwrocila zadania zamkniete (dostal {len(pytania_zamkniete)})", len(pytania_zamkniete) > 0)
check(f"generacja zwrocila zadania otwarte (dostal {len(pytania_otwarte)})", len(pytania_otwarte) > 0)

print()
print("=== ZAMKNIETE ===")
for p in pytania_zamkniete:
    print(f"\n#{p.get('nr')} [{p.get('problem_class')}] {p.get('tresc')}")
    for o in p.get('opcje', []):
        print(f"    {o}")
    print(f"    -> odpowiedz oznaczona jako poprawna: {p.get('odpowiedz','?').upper()}) / final_answer={p.get('final_answer')!r}")
    print(f"    wyjasnienie: {p.get('wyjasnienie','')}")

print()
print("=== OTWARTE ===")
for p in pytania_otwarte:
    print(f"\n#{p.get('nr')} [{p.get('problem_class')}] {p.get('tresc')}")
    print(f"    final_answer={p.get('final_answer')!r}")
    print(f"    odpowiedz_modelowa: {p.get('odpowiedz_modelowa','')}")

all_classes = [p.get('problem_class') for p in pytania_zamkniete + pytania_otwarte]
check("wiekszosc pytan poprawnie zaklasyfikowana jako 'factual' (nie np. arithmetic_word_problem)",
      all_classes.count('factual') >= len(all_classes) * 0.5, all_classes)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: Generacja OK. SPRAWDZ RECZNIE powyzsze pytania pod katem faktografii.")
