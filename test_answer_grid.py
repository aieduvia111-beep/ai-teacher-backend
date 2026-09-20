# -*- coding: utf-8 -*-
"""Offline (zero AI): kratka (zamiast linii) w miejscu na odpowiedz dla zadan otwartych z matematyki i fizyki;
polski/historia/reszta zostaja z liniami."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)
os.environ["MATH_PROVIDER"] = "openai"

import app.exam_pdf_generator as eg

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

def sample(przedmiot):
    return {"tytul": "Sprawdzian", "przedmiot": przedmiot, "klasa": "liceum_2", "czas": 45, "punkty_lacznie": 8,
            "sekcje": [{"nazwa": "Część B — Zadania otwarte", "typ": "otwarte", "instrukcja_sekcji": "Rozwiąż zadania.",
                        "pytania": [{"nr": 1, "tresc": "Oblicz $2+2$.", "punkty": 4, "miejsce_na_odpowiedz": 6,
                                     "odpowiedz_modelowa": "4", "schemat_oceniania": ["1 pkt — wynik"]},
                                    {"nr": 2, "tresc": "Oblicz $3\\cdot 3$.", "punkty": 4, "miejsce_na_odpowiedz": 4,
                                     "odpowiedz_modelowa": "9", "schemat_oceniania": ["1 pkt — wynik"]}]}]}

calls = {"grid": 0, "lines": 0}
orig_grid, orig_lines = eg.AnswerGrid.draw, eg.AnswerLines.draw
def g_draw(self): calls["grid"] += 1; orig_grid(self)
def l_draw(self): calls["lines"] += 1; orig_lines(self)
eg.AnswerGrid.draw, eg.AnswerLines.draw = g_draw, l_draw

for przedmiot, expect_grid in (("Matematyka", True), ("Fizyka", True), ("fizyka", True), ("Język polski", False), ("Historia", False), ("Chemia", True), ("Biologia", False)):
    calls["grid"] = calls["lines"] = 0
    pdf = eg._build_exam_pages(sample(przedmiot))
    ok = (calls["grid"] == 2 and calls["lines"] == 0) if expect_grid else (calls["lines"] == 2 and calls["grid"] == 0)
    check(f"{przedmiot}: {'kratka' if expect_grid else 'linie'} (grid={calls['grid']}, linie={calls['lines']}), PDF {len(pdf)//1024} KB", ok and pdf[:4] == b"%PDF", calls)

# geometria kratki: 5 mm, komorki calkowite, miesci sie w szerokosci strony
g = eg.AnswerGrid(eg.PW - 80, lines=6)
check("kratka: komorka 5 mm (14.17 pt), cols*komorka <= szerokosc, wysokosc = rows*komorka", abs(g.CELL - 14.17) < 0.01 and g.cols * g.CELL <= eg.PW - 80 and abs(g.height - g.rows * g.CELL) < 1e-6, (g.cols, g.rows, g.height))
check("kratka: wysokosc zblizona do linii (6 linii = 138 pt)", abs(g.height - (6 * 22 + 6)) < 15, g.height)

# zapis probki PDF do obejrzenia
out = os.path.join(HERE, "_scratch")
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "grid_matematyka.pdf"), "wb").write(eg._build_exam_pages(sample("Matematyka")))

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
