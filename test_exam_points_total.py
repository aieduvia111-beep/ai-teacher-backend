# -*- coding: utf-8 -*-
"""User (po wizualnej inspekcji dwoch real-testow, trygonometria I
prawdopodobienstwo): "i punkty sie nie zgadzaja". Real bug, NIEZALEZNY
od dzisiejszej pracy nad trygonometria (wystapil w OBU testach, w tym
w calkowicie niezwiazanym temacie prawdopodobienstwo) - naglowek
sprawdzianu pokazywal "30 pkt" (goly domyslny/AI-zgadniety
"punkty_lacznie" z SUROWEJ, pierwszej odpowiedzi AI - patrz przyklad w
EXAM_PROMPT), mimo ze suma faktycznych "punkty" pojedynczych zadan w
finalnej, po-weryfikacji liscie wynosila 21 albo 24 - "punkty_lacznie"
NIGDY nie bylo przeliczane na nowo po odrzuceniach/dogenerowaniu/
przycieciu.

Naprawiono: exam_pdf_generator._fill_missing_exam_questions liczy TERAZ
"punkty_lacznie" jako sume "punkty" WSZYSTKICH zadan w finalnej liscie,
PO wszystkich krokach weryfikacji/uzupelniania/przyciecia - kod, nie AI,
jest zrodlem prawdy (identyczny standard co reszta tego modulu).

Ten plik testuje SAMA logike (zero AI) - buduje syntetyczne dane
sprawdzianu (z celowo BLEDNYM/przestarzalym "punkty_lacznie" od AI, tak
jak w real przypadku) i woła _fill_missing_exam_questions bezposrednio."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.exam_pdf_generator import ExamGenerator

gen = ExamGenerator(openai_api_key="fake-key-not-used-in-this-test")

print("=" * 70)
print("Real przypadek: AI zgadlo 'punkty_lacznie': 30, prawdziwa suma inna")
print("=" * 70)
# 8 zadan zamknietych x 1 pkt + 4 zadania otwarte x 4 pkt = 8 + 16 = 24,
# ALE AI (w SUROWEJ odpowiedzi) zapisalo "punkty_lacznie": 30 (goly
# przyklad z EXAM_PROMPT, real przypadek - prawdopodobienstwo).
data = {
    "tytul": "Sprawdzian: Prawdopodobienstwo",
    "punkty_lacznie": 30,  # BLEDNE - AI zgadlo, nie przeliczono
    "sekcje": [
        {
            "typ": "zamkniete",
            "pytania": [
                {"nr": i, "tresc": f"Pytanie {i}", "opcje": ["a) 1", "b) 2", "c) 3", "d) 4"],
                 "odpowiedz": "a", "final_answer": "1", "punkty": 1}
                for i in range(1, 9)
            ],
        },
        {
            "typ": "otwarte",
            "pytania": [
                {"nr": i, "tresc": f"Zadanie {i}", "punkty": 4,
                 "odpowiedz_modelowa": "test", "final_answer": "42"}
                for i in range(9, 13)
            ],
        },
    ],
}
result = gen._fill_missing_exam_questions(
    data, temat="Matematyka: prawdopodobienstwo", klasa="liceum_3",
    trudnosc="srednia", liczba_pytan=12, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=1, t_start=None,
)
prawdziwa_suma = sum(p.get("punkty", 1) for s in result["sekcje"] for p in s["pytania"])
check("Prawdziwa suma punktow w danych = 24 (8*1 + 4*4)", prawdziwa_suma == 24, prawdziwa_suma)
check("'punkty_lacznie' PO fixie = 24 (przeliczone), NIE 30 (stare od AI)",
      result.get("punkty_lacznie") == 24, result.get("punkty_lacznie"))

print()
print("=" * 70)
print("Regresja: brakujace/None 'punkty' na pojedynczym zadaniu -> domyslnie 1 pkt")
print("=" * 70)
data2 = {
    "tytul": "Test",
    "punkty_lacznie": 999,
    "sekcje": [{"typ": "zamkniete", "pytania": [
        {"nr": 1, "tresc": "P1", "opcje": ["a) 1", "b) 2", "c) 3", "d) 4"], "odpowiedz": "a", "final_answer": "1"},
        {"nr": 2, "tresc": "P2", "opcje": ["a) 1", "b) 2", "c) 3", "d) 4"], "odpowiedz": "a", "final_answer": "1", "punkty": 2},
    ]}],
}
result2 = gen._fill_missing_exam_questions(
    data2, temat="X", klasa="liceum_3", trudnosc="srednia", liczba_pytan=2,
    wlasne_instrukcje=None, przedmiot="Matematyka", max_rounds=1, t_start=None,
)
check("Brak 'punkty' -> domyslnie 1, suma = 1+2 = 3 (nie 999 z AI)",
      result2.get("punkty_lacznie") == 3, result2.get("punkty_lacznie"))

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
