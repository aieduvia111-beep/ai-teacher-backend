"""
Test regresyjny naprawy renderowania "explanation"/"wyjasnienie" -
zgloszony problem: wielokrokowe wyjasnienia (np. delta -> warunek ->
wzory Viete'a) czasem zawieraly literalne \\newline jako separator
krokow, co razem z naiwnym "$$"->"$" psulo parzystosc dolarow i
objawialo sie w przegladarce/PDF jako zdublowany, nieczytelny tekst.

Uruchom: python test_latex_explanation_fix.py

Sprawdza:
1. openai_exam.fix_latex_in_quiz() usuwa \\newline i \\\\ z "explanation"
   PRZED zwijaniem "$$" -> "$", wiec parzystosc dolarow zostaje
   zachowana (bez tego niesparowane $ psuly renderowanie KaTeX).
2. exam_pdf_generator._fix_latex() robi to samo dla pojedynczego stringa.
3. exam_pdf_generator._fix_latex_in_exam_data() stosuje to do WSZYSTKICH
   pol (tresc, opcje, wyjasnienie, final_answer, odpowiedz_modelowa,
   schemat_oceniania) we wszystkich sekcjach/pytaniach - nie tylko tam,
   gdzie akurat wywolywany jest _math_line.
4. Poprawnie sformatowany tekst (bez \\newline) przechodzi bez zmian
   (brak regresji).
"""
import sys
sys.path.insert(0, ".")

from app.openai_exam import fix_latex_in_quiz
from app.exam_pdf_generator import _fix_latex, _fix_latex_in_exam_data

FAILED = []


def check(name, condition, detail=""):
    if condition:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


# ============================================================
# 1. Quiz: fix_latex_in_quiz usuwa \newline z explanation
# ============================================================
print("=== Quiz: \\newline w explanation (zgloszony przypadek) ===")

broken = (
    "Aby rownanie mialo dwa rozne pierwiastki dodatnie, musza byc spelnione warunki: "
    "1) $a \\neq 0$ (rownanie musi byc kwadratowe), 2) $delta > 0$, 3) oba pierwiastki $x_1, x_2 > 0$$. "
    "\\newline Liczymy delte:$ $\\Delta = (2a + 3)^2 - 4a(a+2) = 4a^2 + 12a + 9 - 4a^2 - 8a = 4a + 9$"
    "$\\newline Warunek$ $delta > 0$: $4a + 9 > 0 \\Rightarrow a > -\\frac{9}{4}$"
)
quiz_data = {"questions": [{"question": "test", "options": ["a", "b", "c", "d"], "explanation": broken}]}
fixed = fix_latex_in_quiz(quiz_data)["questions"][0]["explanation"]
check("\\newline usuniety z explanation", "\\newline" not in fixed, fixed)
check("brak podwojnych dolarow $$ po naprawie", "$$" not in fixed, fixed)
check("parzysta liczba $ w naprawionym explanation", fixed.count("$") % 2 == 0, (fixed.count("$"), fixed))

from app.openai_exam import _strip_mistaken_dollar_pairs
check(
    "_strip_mistaken_dollar_pairs: usuwa sierocy $ przed prawdziwym wzorem, zachowuje wzor poprawnie opakowany",
    _strip_mistaken_dollar_pairs("Liczymy delte:$ $\\Delta = 5$") == "Liczymy delte: $\\Delta = 5$",
    _strip_mistaken_dollar_pairs("Liczymy delte:$ $\\Delta = 5$"),
)
check(
    "_strip_mistaken_dollar_pairs: NIE rusza dwoch prawdziwych sasiadujacych wzorow",
    _strip_mistaken_dollar_pairs("$x=2$ $y=3$") == "$x=2$ $y=3$",
    _strip_mistaken_dollar_pairs("$x=2$ $y=3$"),
)

# Poprawnie sformatowany tekst (bez \newline) - brak regresji.
clean = "Liczymy delte: $\\Delta = (m-3)^2 - 4m = m^2 - 10m + 9$. Warunek: $\\Delta > 0$, czyli $m < 1$ lub $m > 9$."
quiz_data2 = {"questions": [{"question": "test", "options": ["a", "b", "c", "d"], "explanation": clean}]}
fixed2 = fix_latex_in_quiz(quiz_data2)["questions"][0]["explanation"]
check("poprawny tekst (bez \\newline) przechodzi bez zmian", fixed2 == clean, (clean, fixed2))


# ============================================================
# 2. Sprawdzian: _fix_latex usuwa \newline z pojedynczego stringa
# ============================================================
print()
print("=== Sprawdzian: _fix_latex usuwa \\newline ===")

broken_pl = "Liczymy delte:$ $\\Delta = (2m+1)^2 - 4m^2$$. \\newline Warunek: $\\Delta > 0$"
fixed_pl = _fix_latex(broken_pl)
check("\\newline usuniety (Sprawdzian, _fix_latex)", "\\newline" not in fixed_pl, fixed_pl)

check("pusty string -> pusty string (brak crasha)", _fix_latex("") == "", repr(_fix_latex("")))
check("None -> None (brak crasha)", _fix_latex(None) is None, _fix_latex(None))


# ============================================================
# 3. Sprawdzian: _fix_latex_in_exam_data normalizuje WSZYSTKIE pola
# ============================================================
print()
print("=== Sprawdzian: _fix_latex_in_exam_data obejmuje wszystkie pola ===")

data = {
    "sekcje": [
        {
            "typ": "zamkniete",
            "pytania": [{
                "tresc": "Rozwiaz $x^2-4=0$",
                "opcje": ["a) $x=2$", "b) $x=-2$$ \\newline zle$", "c) tak", "d) nie"],
                "wyjasnienie": "Delta: $\\Delta=16$$. \\newline Zatem$ $x=\\pm 2$",
                "final_answer": "$x=\\pm 2$",
            }],
        },
        {
            "typ": "otwarte",
            "pytania": [{
                "tresc": "Rozwiaz $x^2-9=0$ krok po kroku.",
                "odpowiedz_modelowa": "Liczymy:$ $x^2=9$$. \\newline Zatem$ $x=\\pm 3$",
                "schemat_oceniania": ["1 pkt$ $za delte$$. \\newline reszta$"],
            }],
        },
    ]
}
result = _fix_latex_in_exam_data(data)
zamkniete = result["sekcje"][0]["pytania"][0]
otwarte = result["sekcje"][1]["pytania"][0]

check("zamkniete: wyjasnienie bez \\newline", "\\newline" not in zamkniete["wyjasnienie"], zamkniete["wyjasnienie"])
check("zamkniete: opcje bez \\newline", all("\\newline" not in o for o in zamkniete["opcje"]), zamkniete["opcje"])
check("otwarte: odpowiedz_modelowa bez \\newline", "\\newline" not in otwarte["odpowiedz_modelowa"], otwarte["odpowiedz_modelowa"])
check("otwarte: schemat_oceniania bez \\newline", all("\\newline" not in s for s in otwarte["schemat_oceniania"]), otwarte["schemat_oceniania"])


print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
    sys.exit(0)
