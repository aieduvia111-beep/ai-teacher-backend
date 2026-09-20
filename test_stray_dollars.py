# -*- coding: utf-8 -*-
"""Offline (zero AI): zbłąkane '$' w opcjach z jezykow obcych ("went$") nie odrzuca juz calego pytania; LaTeX zostaje nietkniety."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from app.openai_exam import strip_stray_dollars, strip_stray_dollars_in_question, validate_question_latex

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

check("'went$' -> 'went'", strip_stray_dollars("went$") == "went")
check("'$was/were$' (parzysta) bez zmian", strip_stray_dollars("$was/were$") == "$was/were$")
check("'$x^2' (nieparzysta, ale wzor) bez zmian", strip_stray_dollars("$x^2") == "$x^2")
check("'\\frac{1}{2}$' bez zmian", strip_stray_dollars("\\frac{1}{2}$") == "\\frac{1}{2}$")
check("'$x$' bez zmian", strip_stray_dollars("$x$") == "$x$")
check("tekst bez '$' bez zmian", strip_stray_dollars("go, went, gone") == "go, went, gone")

# prawdziwe opcje z produkcji: przed = odrzucone, po = przechodza walidator
for opts in (['goed$', 'went$', 'gone$', 'goned$'], ['saw$', 'seen$', 'sawen$', 'see$'], ['taked$', 'took$', 'taken$', 'taks$'], ['$was/were$', 'beed$', 'was$', 'bent$']):
    q = {"question": "Podaj formę przeszłą czasownika.", "options": list(opts), "explanation": "Forma przeszła."}
    before_ok, _ = validate_question_latex(q, ["question", "options", "explanation"])
    strip_stray_dollars_in_question(q, ["options", "question", "explanation"])
    after_ok, why = validate_question_latex(q, ["question", "options", "explanation"])
    check(f"opcje {opts[:2]}...: przed odrzucone, po przechodzi", before_ok is False and after_ok is True, (before_ok, after_ok, why, q["options"]))

# prawdziwy LaTeX w pytaniu z matematyki nie jest zmieniany
q = {"question": "Oblicz $\\frac{1}{2} + \\frac{1}{3}$.", "options": ["$\\frac{5}{6}$", "$\\frac{2}{5}$", "$1$", "$\\frac{1}{6}$"], "explanation": "Suma to $\\frac{5}{6}$."}
snapshot = repr(q)
strip_stray_dollars_in_question(q, ["options", "question", "explanation"])
check("poprawny LaTeX w pytaniu z matematyki nietkniety", repr(q) == snapshot, q)

# podpiecie w kodzie
src_q = open("app/openai_exam.py", encoding="utf-8").read()
src_e = open("app/exam_pdf_generator.py", encoding="utf-8").read()
check("quiz: strip przed auto_wrap dla options/question/explanation", 'strip_stray_dollars_in_question(q, ["options", "question", "explanation"])' in src_q)
check("sprawdzian (zamkniete i otwarte): strip przed walidacja", 'strip_stray_dollars_in_question(pyt, ["opcje", "tresc", "wyjasnienie"])' in src_e and 'strip_stray_dollars_in_question(pyt, ["tresc", "odpowiedz_modelowa", "final_answer"])' in src_e)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
