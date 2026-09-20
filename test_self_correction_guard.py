# -*- coding: utf-8 -*-
"""Offline (zero AI): odrzucanie pytan ze SLADAMI SAMOKOREKTY AI w kluczu (real-test 20.09.2026, sprawdzian
z zadaniem 8: 'Zadanie bledne. Poprawmy: ...') + brak falszywych alarmow na uczciwych wyjasnieniach."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from app.openai_exam import detect_self_correction, validate_question_latex
from app import math_verify as mv

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

BAD = [
    # prawdziwy klucz z produkcyjnego PDF (zadanie 8)
    "Największa wartość to $q = -\\frac{\\Delta}{4a}$. Ta wartość nie zależy od $m$ i wynosi 1, nie 5. Zadanie błędne. Poprawmy: $y=-x^2+4mx-4m^2+5$",
    "Ostatecznie zmieniamy na: y = -x^2 + 2mx + 4, wtedy wynik to 5.",
    "Żadna z odpowiedzi nie jest poprawna, więc poprawmy treść zadania.",
    "Wynik nie zgadza się z opcjami, brak poprawnej odpowiedzi.",
    "Przepraszam, pomyliłem się w obliczeniach.",
    "Nie ma poprawnej odpowiedzi wśród opcji a-d.",
]
GOOD = [
    # uczciwe klucze z tego samego PDF (nie moga byc odrzucone)
    "Ze wzorów Viete'a suma pierwiastków $x_1+x_2 = 2m = 4$, stąd $m=2$. Sprawdzenie: dla $m=2$ delta wynosi 0 — pierwiastek podwójny, suma 4.",
    "Ponieważ $a=1>0$, funkcja ma wartość najmniejszą w wierzchołku. Zatem wartość minimalna wynosi $-4$ niezależnie od $m$. Aby była równa $-9$, musiałoby zachodzić $-4=-9$, co jest sprzeczne. Odpowiedź: nie istnieje takie $m$.",
    "Współrzędna wierzchołka $x_w = 2$, a $y_w = m-4$. Skoro $y_w=1$, to $m=5$.",
    "Aby funkcja była kwadratowa, współczynnik przy $x^2$ musi być różny od zera, czyli $m \\neq 1$.",
    "Rozwiązaniem nierówności jest przedział otwarty; poprawna odpowiedź to b) — pozostałe opcje są błędne, bo wynikają z pominięcia założenia $m\\neq 2$.",
    "Zmieniamy zmienną: podstawiamy $t = \\sin x$ i rozwiązujemy równanie kwadratowe.",
    "Oznaczmy przez $x$ długość krawędzi. Poprawnie obliczona objętość to 54 cm³.",
]
for t in BAD: check(f"wykryto slad samokorekty: {t[:55]}...", detect_self_correction(t) is not None, t)
for t in GOOD: check(f"NIE odrzuca uczciwego klucza: {t[:55]}...", detect_self_correction(t) is None, detect_self_correction(t))

# ---- integracja z walidatorem uzywanym przez quiz i sprawdzian (pola explanation / wyjasnienie / odpowiedz_modelowa) ----
ok, why = validate_question_latex({"wyjasnienie": BAD[0]}, ["wyjasnienie"])
check("sprawdzian (zamkniete): wyjasnienie z samokorekta -> pytanie odrzucone", ok is False and "samokorekty" in why, why)
ok, why = validate_question_latex({"explanation": BAD[1]}, ["explanation"])
check("quiz: explanation z samokorekta -> odrzucone", ok is False, why)
ok, why = validate_question_latex({"odpowiedz_modelowa": BAD[2]}, ["odpowiedz_modelowa"])
check("sprawdzian (otwarte): odpowiedz_modelowa z samokorekta -> odrzucone", ok is False, why)
ok, why = validate_question_latex({"tresc": BAD[0], "wyjasnienie": GOOD[0]}, ["tresc", "wyjasnienie"])
check("marker w polu 'tresc' (nie klucz) NIE jest sprawdzany tym mechanizmem", ok is True, why)
ok, why = validate_question_latex({"wyjasnienie": GOOD[1]}, ["wyjasnienie"])
check("uczciwe wyjasnienie przechodzi walidator", ok is True, why)

# ---- zero falszywych alarmow na wyjasnieniach z naszych generatorow kodowych (kilkaset pytan) ----
seen = flagged = 0
for lvl in ("liceum_1", "liceum_2", "liceum_3", "technikum_1", "technikum_2", "technikum_3", "technikum_5"):
    if not mv.hs_math_level_supported(lvl): continue
    for q in mv.generate_safe_hs_math_batch(60, lvl):
        seen += 1
        m = detect_self_correction(q.get("explanation", ""))
        if m: flagged += 1; print("   falszywy alarm:", m, q.get("explanation", "")[:100])
check(f"zero falszywych alarmow na {seen} wyjasnieniach z generatorow kodowych", seen > 100 and flagged == 0, (seen, flagged))

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
