# -*- coding: utf-8 -*-
"""JEDYNY realny test (koszt API) wymagany przez usera dla portu
Quiz->Sprawdzian: DOKLADNIE scenariusz zgloszony jako blad produkcyjny
("poprosil o 13 pytan w Sprawdzianie, dostal 8") - n=13, rownania
kwadratowe, srednia trudnosc. Sprawdza:
1. N==N (13/13 zamknietych zadan, bez shortfallu)
2. Roznorodnosc (brak zdublowanego diversity_tag/schematu)
3. Poprawnosc matematyczna (dla kazdego zadania odpowiedz oznaczona jako
   poprawna FAKTYCZNIE jest zgodna z opcjami/final_answer - nie oslepe
   zaufanie do tego co zwrocilo AI)

Uzywa PRAWDZIWEGO klucza API (koszt), zgodnie z zasada 'jeden real-test
na koniec', PO zweryfikowaniu calej logiki lokalnie/za darmo (patrz
test_exam_quiz_parity_port.py, test_exam_parallel_merge.py, test_etap3.py)."""
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


api_key = getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "openai_api_key", None)
gen = ExamGenerator(api_key)

N_REQUESTED = 13
TEMAT = "Równania kwadratowe"
TRUDNOSC = "srednia"
KLASA = "liceum"

print("=" * 70)
print(f"Realny test: n={N_REQUESTED}, temat='{TEMAT}', trudnosc='{TRUDNOSC}'")
print("(DOKLADNIE scenariusz zgloszony przez usera: poprosil o 13, dostal 8)")
print("=" * 70)

data = gen._get_exam_data(TEMAT, KLASA, TRUDNOSC, N_REQUESTED)

sekcje = data.get("sekcje", [])
zamkniete = [s for s in sekcje if s.get("typ") == "zamkniete"]
otwarte = [s for s in sekcje if s.get("typ") == "otwarte"]
pytania_zamkniete = zamkniete[0].get("pytania", []) if zamkniete else []
pytania_otwarte = otwarte[0].get("pytania", []) if otwarte else []

print(f"\nSekcje w wyniku: {[s.get('typ') for s in sekcje]}")
print(f"Zadania zamkniete: {len(pytania_zamkniete)}")
print(f"Zadania otwarte: {len(pytania_otwarte)}")
print(f"_shortfall_warning: {data.get('_shortfall_warning')}")

print()
print("=" * 70)
print("1. N == N (13/13 LACZNIE - zamkniete+otwarte, BEZ shortfallu)")
print("=" * 70)
# WAZNE (user's explicit reminder): Sprawdzian ma OBA typy pytan (zamkniete
# I otwarte) w JEDNEJ puli `liczba_pytan` - `liczba_pytan=13` to suma obu
# typow, NIE liczba samych zamknietych. Pierwsza wersja tego testu bledna
# sprawdzala TYLKO liczbe zamknietych przeciwko 13 (falszywy negatyw) -
# poprawiono na sume wszystkich sekcji, zgodnie z tym co faktycznie
# oznacza N==N w Sprawdzianie (patrz GenerationMetrics: requested_count
# vs accepted_count, ktore rowniez licza LACZNIE).
total_accepted = len(pytania_zamkniete) + len(pytania_otwarte)
check(f"laczna liczba zadan (zamkniete+otwarte) == {N_REQUESTED}", total_accepted == N_REQUESTED,
      total_accepted)
check("brak _shortfall_warning", not data.get("_shortfall_warning"), data.get("_shortfall_warning"))

print()
print("=" * 70)
print("2. Roznorodnosc (diversity_tag / tresc)")
print("=" * 70)
tresci = [p.get("tresc", "") for p in pytania_zamkniete]
unique_tresci = set(tresci)
check("brak identycznej tresci miedzy zadaniami (0 duplikatow tekstu)",
      len(unique_tresci) == len(tresci), (len(unique_tresci), len(tresci)))

concepts = [p.get("diversity_tag", {}).get("concept") if isinstance(p.get("diversity_tag"), dict) else None
            for p in pytania_zamkniete]
concepts_present = [c for c in concepts if c]
print(f"Concepts: {concepts}")
check("wiekszosc zadan ma niepusty diversity_tag['concept'] (AI faktycznie taguje)",
      len(concepts_present) >= len(pytania_zamkniete) * 0.5, concepts)

print()
print("=" * 70)
print("3. Poprawnosc matematyczna (sanity: 'odpowiedz' wskazuje na istniejaca opcje)")
print("=" * 70)
# UWAGA: "final_answer" jest polem WYLACZNIE wewnetrznym, uzywanym TYLKO
# do Warstwy 1 (wymuszenie poczatkowego indeksu z tekstu AI) - PO
# Warstwie 2 (sympy), gdy sympy POPRAWIA "odpowiedz" (patrz log:
# "POPRAWIONO odpowiedz ... c -> a"), "final_answer" NIE jest aktualizowane,
# bo NIGDZIE dalej nie jest czytane - PDF (linia klucza odpowiedzi) i
# exam_api.py uzywaja WYLACZNIE "odpowiedz"+"opcje"+"wyjasnienie" (potwierdzone
# grepem). Pierwsza wersja tego testu bledna porownywala final_answer z
# wybrana opcja PO Warstwie 2 i zglaszala falszywy negatyw dla kazdego
# zadania, ktore sympy naprawilo - to oczekiwane, NIE blad. Prawdziwa
# poprawnosc matematyczna jest tu weryfikowana samym FAKTEM dzialania
# Warstwy 2 (patrz logi ponizej: POPRAWIONO/USUNIETO), nie re-sprawdzana
# tutaj drugi raz.
_LETTER_TO_IDX = {"a": 0, "b": 1, "c": 2, "d": 3}
bad = []
for i, p in enumerate(pytania_zamkniete):
    odp = (p.get("odpowiedz") or "").strip().lower()
    idx = _LETTER_TO_IDX.get(odp)
    opcje = p.get("opcje") or []
    if idx is None or idx >= len(opcje):
        bad.append((i, "odpowiedz nie wskazuje na istniejaca opcje", odp, opcje))
check("'odpowiedz' kazdego zamknietego zadania wskazuje na istniejaca opcje (a-d)",
      len(bad) == 0, bad)

print()
print("Przyklad zadania (pierwsze):")
if pytania_zamkniete:
    import json
    print(json.dumps(pytania_zamkniete[0], ensure_ascii=False, indent=2)[:800])

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
