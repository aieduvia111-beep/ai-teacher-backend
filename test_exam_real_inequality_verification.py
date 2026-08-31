# -*- coding: utf-8 -*-
"""Realny test (koszt API, maly - n=6, jedna generacja) dla nowego
verify_inequality_question (31.08.2026) - potwierdza ze weryfikacja
nierownosci FAKTYCZNIE dziala na prawdziwej generacji, nie tylko na
recznie napisanych przypadkach testowych. Temat celowo dobrany zeby
wymusic pytania typu 'algebra_symbolic' z odpowiedzia-przedzialem
(nierownosci wymierne/kwadratowe) - dokladnie ta klasa co byla
zglosznona jako zepsuta.

Sprawdza:
1. Generacja konczy sie sukcesem (N==N, bez calkowitego bledu)
2. Dla kazdego zadania zamknietego z problem_class inne niz
   'algebra_symbolic'-bez-przedzialu: sprawdzamy czy matematyka
   faktycznie sie zgadza (verify_and_fix_math_question na WYNIKU -
   nie ufamy slepo kluczowi ktory AI zwrocilo, liczymy jeszcze raz
   niezaleznie)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.config import settings
from app.exam_pdf_generator import ExamGenerator
from app.math_verify import verify_and_fix_math_question

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


api_key = getattr(settings, "OPENAI_API_KEY", None)
gen = ExamGenerator(api_key)

N_REQUESTED = 6
TEMAT = "Nierownosci wymierne i kwadratowe z parametrem"
TRUDNOSC = "trudna"
KLASA = "liceum_2"

print("=" * 70)
print(f"Realny test: n={N_REQUESTED}, temat='{TEMAT}', trudnosc='{TRUDNOSC}'")
print("Cel: potwierdzic ze verify_inequality_question dziala na prawdziwej generacji")
print("=" * 70)

data = gen._get_exam_data(TEMAT, KLASA, TRUDNOSC, N_REQUESTED)

sekcje = data.get("sekcje", [])
zamkniete = [s for s in sekcje if s.get("typ") == "zamkniete"]
pytania_zamkniete = zamkniete[0].get("pytania", []) if zamkniete else []

check(f"generacja zwrocila zadania zamkniete (dostal {len(pytania_zamkniete)})", len(pytania_zamkniete) > 0)

print()
print(f"Wygenerowano {len(pytania_zamkniete)} zadan zamknietych. Klasy problem_class:")
for p in pytania_zamkniete:
    print(f"  - #{p.get('nr')}: problem_class={p.get('problem_class')!r}, tresc={p.get('tresc','')[:70]!r}")

print()
print("Niezalezna re-weryfikacja matematyki KAZDEGO zadania zamknietego (verify_and_fix_math_question):")
any_inequality_verified = False
for p in pytania_zamkniete:
    tresc = p.get("tresc", "")
    opcje = p.get("opcje", [])
    odp_letter = (p.get("odpowiedz") or "").strip().lower()
    result = verify_and_fix_math_question(tresc, opcje)
    status = result.get("status")
    if status == "match_index":
        true_letter = "abcd"[result["true_index"]]
        ok = (true_letter == odp_letter)
        check(f"  #{p.get('nr')}: klucz='{odp_letter}', sympy mowi='{true_letter}' {'(zgadza sie)' if ok else '(NIEZGODNE!)'}", ok, result)
        any_inequality_verified = True
    elif status == "no_option_matches":
        check(f"  #{p.get('nr')}: sympy - ZADNA opcja nie jest poprawna (blad klucza, powinno byc juz odfiltrowane)", False, result)
        any_inequality_verified = True
    else:
        print(f"  ..  #{p.get('nr')}: unverifiable (poza zasiegiem sympy - nie liczy sie do tego testu)")

print()
check("przynajmniej jedno zadanie dalo sie niezaleznie zweryfikowac przez sympy (potwierdza ze weryfikator faktycznie dziala na prawdziwej generacji, nie tylko recznych przypadkach)",
      any_inequality_verified)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
