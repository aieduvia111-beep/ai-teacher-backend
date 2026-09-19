# -*- coding: utf-8 -*-
"""Offline (zero AI): values_match akceptuje ROWNOWAZNE poprawne odpowiedzi (przecinek dziesietny, kolejnosc pierwiastkow, faktografia) i NIE zrownuje roznych."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
os.chdir(r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.blind_verify import values_match

# (a, b, oczekiwane, opis)  - True = te same odpowiedzi, False = ROZNE odpowiedzi
CASES = [
    ("2,5", "2.5", True, "przecinek dziesietny vs kropka"),
    ("1,5 m", "1.5 m", True, "przecinek dziesietny z jednostka"),
    ("0,75", "3/4", True, "ulamek dziesietny vs zwykly"),
    ("3,14", "3.14", True, "przecinek dziesietny"),
    ("2, 3", "3, 2", True, "pierwiastki w innej kolejnosci"),
    ("x = 2, x = 3", "x = 3, x = 2", True, "pierwiastki z 'x=' w innej kolejnosci"),
    ("Adam Mickiewicz", "Mickiewicz", True, "faktografia: nazwisko vs imie i nazwisko"),
    ("mitochondrium", "Mitochondrium", True, "wielkosc liter (juz dzialalo)"),
    ("b = 2, c = 4", "b = 4, c = 2", False, "ROZNE przypisania zmiennych - nie wolno zrownac"),
    ("2,5", "2.6", False, "rozne liczby"),
    ("2, 3", "2, 4", False, "rozne pierwiastki"),
    ("15", "150", False, "rozne liczby"),
    ("Kraków", "Warszawa", False, "rozne miasta"),
    ("chlor", "chlorek sodu", False, "krotkie slowo nie jest calym slowem w frazie? (chlor != chlorek)"),
    ("1410", "1411", False, "rozne lata"),
    ("150 J", "150", True, "jednostka (juz dzialalo)"),
    ("5/7", "0.7142857142857143", True, "przyblizenie (istniejace zachowanie, bez zmian)"),
]
bad = 0
for a, b, exp, why in CASES:
    got = values_match(a, b)
    ok = got == exp
    bad += (not ok)
    print(f"{'OK  ' if ok else 'FAIL'} {a!r} vs {b!r} -> {got} (oczekiwano {exp})  [{why}]")
print("bledy:", bad)
