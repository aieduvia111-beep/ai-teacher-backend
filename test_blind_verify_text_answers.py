# -*- coding: utf-8 -*-
"""User: "a działa poza matematyka?" (czy Warstwa 2.5 dziala poza
matematyka) - real-test na biologii ujawnil, ze POPRAWNA odpowiedz
tekstowa "Mitochondrium" byla ODRZUCANA jako niezgodna z "mitochondrium"
(sympy parsuje pojedyncze slowo jako Symbol i porownuje go case-
SENSITIVE) - values_match dzialalo poprawnie TYLKO dla matematyki.

Naprawiono: values_match probuje najpierw PROSTE porownanie tekstowe
(case/whitespace-insensitive), dopiero potem sympy (dla matematyki,
gdzie format moze sie roznic: 'm = -3' vs '-3'). Wszystkie testy sa
JEDNOSTKOWE (zero AI)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.blind_verify import values_match

print("=" * 70)
print("NAPRAWIONE: odpowiedzi tekstowe (spoza matematyki)")
print("=" * 70)
check("Real przypadek (biologia): 'Mitochondrium' vs 'mitochondrium' (rozna wielkosc liter) -> True",
      values_match("Mitochondrium", "mitochondrium") is True)
check("Wieloslowna odpowiedz z biala spacja/kropka koncowa: '  Warszawa  ' vs 'warszawa.' -> True",
      values_match("  Warszawa  ", "warszawa.") is True)
check("Genuinie ROZNE odpowiedzi tekstowe -> False (nie zgadywanie)",
      values_match("Aparat Golgiego", "Mitochondrium") is False)
check("Wieloslowna, POPRAWNIE identyczna odpowiedz -> True",
      values_match("Zygmunt III Waza", "zygmunt iii waza") is True)

print()
print("=" * 70)
print("Regresja: matematyka (liczby/wyrazenia) dziala jak wczesniej")
print("=" * 70)
check("Regresja: 'm = -3' vs '-3' (format) -> True", values_match("m = -3", "-3") is True)
check("Regresja: '5/7' vs '0.7142857142857143' (rownowaznosc liczbowa) -> True",
      values_match("5/7", "0.7142857142857143") is True)
check("Regresja: 'b = 2, c = 4' vs '2, 4' (wielowartosciowa) -> True",
      values_match("b = 2, c = 4", "2, 4") is True)
check("Regresja: genuinie ROZNA matematyka -> False", values_match("m = 5", "-3") is False)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
