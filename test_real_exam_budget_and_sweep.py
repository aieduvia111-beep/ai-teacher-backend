# -*- coding: utf-8 -*-
"""REALNY test (koszt API, user 04.09.2026: "przetestuj sprawdzian i
quizy oszczednie ale profesjonalnie... jak znajdziesz blad nawet
minimalny to popraw") - dwie czesci:
1) potwierdza naprawe budzetu czasu Sprawdzianu (identyczny blad jak w
   Quizie - budzet nie skalowal sie z liczba_pytan) na duzym n=20.
2) krotki przeglad kilku popularnych tematow (n=8, w normie), zeby
   zlapac inne ewentualne bledy."""
import asyncio
import sys
import time

sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
sys.stdout.reconfigure(encoding='utf-8')

from app.exam_pdf_generator import ExamGenerator
from app.config import settings

API_KEY = getattr(settings, "OPENAI_API_KEY", None)


def run_one(temat, klasa, trudnosc, n):
    gen = ExamGenerator(API_KEY)
    t0 = time.time()
    try:
        data = gen._get_exam_data(temat, klasa, trudnosc, n)
    except Exception as e:
        print(f"  WYJATEK: {e}")
        return False, time.time() - t0
    elapsed = time.time() - t0
    sekcje = data.get("sekcje", [])
    zamkniete = [s for s in sekcje if s.get("typ") == "zamkniete"]
    otwarte = [s for s in sekcje if s.get("typ") == "otwarte"]
    pz = zamkniete[0].get("pytania", []) if zamkniete else []
    po = otwarte[0].get("pytania", []) if otwarte else []
    total = len(pz) + len(po)
    ok = total == n
    print(f"  {'OK' if ok else 'NIEPELNY'}: {total}/{n} w {elapsed:.1f}s" + (f" shortfall={data.get('_shortfall_warning')}" if data.get('_shortfall_warning') else ""))
    return ok, elapsed


def main():
    print("="*70)
    print("CZESC 1: budzet czasu, n=20 (max), temat latwy/sprawdzony")
    print("="*70)
    run_one("Pole i obwod figur plaskich", "podstawowka_6", "srednia", 20)

    print("\n" + "="*70)
    print("CZESC 2: przeglad tematow, n=8")
    print("="*70)
    cases = [
        ("Procenty i proporcje", "podstawowka_7", "srednia"),
        ("Funkcje trygonometryczne", "liceum_2", "srednia"),
        ("Ciagi arytmetyczne i geometryczne", "liceum_2", "srednia"),
        ("Rownania kwadratowe", "podstawowka_7", "srednia"),
    ]
    for temat, klasa, trudnosc in cases:
        print(f"\n'{temat}' ({klasa}, {trudnosc}, n=8)")
        run_one(temat, klasa, trudnosc, 8)


if __name__ == "__main__":
    main()
