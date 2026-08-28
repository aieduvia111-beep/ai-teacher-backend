# -*- coding: utf-8 -*-
"""User: real-test Sprawdzianu z Trygonometrii pokazal, ze samo
wykrywanie+odrzucanie (Warstwa 1.5 - patrz test_latex_structural_validation.py)
jest ZA AGRESYWNE: 15/20 (75%) wygenerowanych pozycji mialo komende LaTeX
poza $ $ w polu "opcje"/"final_answer" (np. "a) 5\\sqrt{3}" zamiast
"a) $5\\sqrt{3}$"), co przy odrzucaniu-bez-naprawy dalo niedobor (4/10
zamiast 10/10, budzet 60s wyczerpany).

Naprawiono: PRZED walidacja, auto_wrap_bare_latex/_in_question probuje
NAPRAWIC (owinac w $ ... $) BEZPIECZNE, krotkie pola jednowartosciowe
(opcje/final_answer) - NIE pola mieszajace proze z matematyka
(tresc/pytanie/wyjasnienie), gdzie slepe owijanie calego pola byloby
niebezpieczne. Odrzucenie zostaje jako ostatecznosc, gdy naprawa jest
niemozliwa (np. pole juz ma NIEPARZYSTA liczbe $ - cos innego jest
zepsute, nie "brak $ w ogole").

Ten plik testuje SAM auto-repair (auto_wrap_bare_latex/
auto_wrap_bare_latex_in_question) oraz pelny pipeline
napraw-a-potem-waliduj, w odroznieniu od test_latex_structural_validation.py
ktory testuje WYLACZNIE czysty detektor."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.openai_exam import (
    auto_wrap_bare_latex,
    auto_wrap_bare_latex_in_question,
    validate_latex_formatting,
    validate_question_latex,
)

print("=" * 70)
print("Real przypadek (Pytanie 6, Sprawdzian: Trygonometria) - auto-naprawa")
print("=" * 70)
fixed = auto_wrap_bare_latex("a) 5\\sqrt{3}")
check("'a) 5\\sqrt{3}' -> owiniete w $ z zachowaniem prefiksu 'a) '",
      fixed == "a) $5\\sqrt{3}$", fixed)
check("Po naprawie, walidacja przechodzi",
      validate_latex_formatting(fixed)[0] is True, fixed)

fixed_no_prefix = auto_wrap_bare_latex("5\\sqrt{3}")
check("Bez prefiksu 'x) ' (np. final_answer) -> cale pole owiniete",
      fixed_no_prefix == "$5\\sqrt{3}$", fixed_no_prefix)

print()
print("=" * 70)
print("Nie dotyka tekstu, ktory juz jest poprawny lub nie ma LaTeX-a")
print("=" * 70)
already_ok = "a) $5\\sqrt{3}$"
check("Juz poprawnie owiniete -> bez zmian",
      auto_wrap_bare_latex(already_ok) == already_ok)

plain = "a) Warszawa"
check("Zwykly tekst bez komend LaTeX -> bez zmian",
      auto_wrap_bare_latex(plain) == plain)

print()
print("=" * 70)
print("Nie maskuje GENUINE zepsutych pol (nieparzysta liczba $) -")
print("naprawa dziala TYLKO gdy $ w ogole nie ma")
print("=" * 70)
broken = "a) $5\\sqrt{3}"
fixed_broken = auto_wrap_bare_latex(broken)
check("Pole z NIEPARZYSTA liczba $ (cos innego zepsute) -> auto-repair NIE rusza",
      fixed_broken == broken, fixed_broken)
check("...wiec walidacja nadal poprawnie odrzuca (brak fałszywego 'naprawiono')",
      validate_latex_formatting(fixed_broken)[0] is False)

print()
print("=" * 70)
print("auto_wrap_bare_latex_in_question - pola-listy (np. 'options'/'opcje')")
print("=" * 70)
q = {
    "question": "Oblicz.",
    "options": ["a) 5\\sqrt{3}", "b) $5$", "c) $6$", "d) $7$"],
    "explanation": "OK",
}
auto_wrap_bare_latex_in_question(q, ["options"])
check("Zla opcja w liscie -> naprawiona",
      q["options"][0] == "a) $5\\sqrt{3}$", q["options"])
check("Juz poprawne opcje w liscie -> bez zmian",
      q["options"][1:] == ["b) $5$", "c) $6$", "d) $7$"], q["options"])

print()
print("=" * 70)
print("Pelny pipeline: napraw -> waliduj (dokladnie jak w produkcji)")
print("=" * 70)
q_pipeline = {
    "question": "Oblicz $x^2$.",
    "options": ["a) 5\\sqrt{3}", "b) $5$", "c) $6$", "d) $7$"],
    "explanation": "Wzór: $\\sqrt{4}=2$.",
}
auto_wrap_bare_latex_in_question(q_pipeline, ["options"])
ok, reason = validate_question_latex(q_pipeline, ["question", "options", "explanation"])
check("Po naprawie 'options', pelna walidacja pytania przechodzi (bylaby FAIL bez naprawy)",
      ok is True, reason)

q_pipeline_final_answer = {"tresc": "Oblicz.", "final_answer": "5\\sqrt{3}"}
auto_wrap_bare_latex_in_question(q_pipeline_final_answer, ["final_answer"])
ok2, reason2 = validate_question_latex(q_pipeline_final_answer, ["tresc", "final_answer"])
check("Otwarte zadanie: 'final_answer' naprawione -> walidacja przechodzi",
      ok2 is True, reason2)

print()
print("=" * 70)
print("Pola nie objete auto-repair (tresc/wyjasnienie) NIE sa owijane")
print("(mieszaja proze z matematyka - slepe owijanie calego pola byloby")
print("niebezpieczne, np. zepsuloby polskie zdania dookola wzoru)")
print("=" * 70)
q_prose = {
    "question": "Oblicz $x^2$, wiedząc że x to \\sqrt{2}.",
    "options": ["a) $1$", "b) $2$", "c) $3$", "d) $4$"],
}
auto_wrap_bare_latex_in_question(q_prose, ["options"])
ok3, reason3 = validate_question_latex(q_prose, ["question", "options"])
check("'question' z golym \\sqrt w prozie -> auto-repair NIE stosowany do niej, wiec nadal FAIL (celowo - to nie jest bezpieczne pole)",
      ok3 is False and "question" in reason3, reason3)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
