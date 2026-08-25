# -*- coding: utf-8 -*-
"""NAPRAWA (znaleziony PRZY realnym tescie Universal Diversity Engine,
sierpien 2026): "\textbackslash" (i inne warianty "\text*"/"\math*")
nie byly na liscie _LATEX_CMDS_AT_RISK w sanitize_latex_json_
backslashes - "text" tam byl, ale regex ma negative lookahead
(?![a-zA-Z]), ktory NIE przechodzi dla "\textbackslash" (po "text"
jest litera "b", nie granica slowa) - pierwszy backslash "\t" byl wiec
mylony z prawdziwym escape'em JSON (tabulator) przez json.loads(),
obcinajac reszte tekstu. REALNY, zaobserwowany skutek: final_answer
w wygenerowanym pytaniu ("$a < -2\\textbackslash sqrt5$") stawal sie
"$a < -2<TAB>extbackslash sqrt5$" po json.loads(), co nigdy nie
pasowalo do zadnej opcji (final_answer_no_match) - 12/46 odrzuconych
pytan w jednym realnym tescie mialo TEN wlasnie powod, nie realny
blad matematyczny AI."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import json
from app.openai_exam import sanitize_latex_json_backslashes

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


def _roundtrip(raw_json_text: str) -> dict:
    """Symuluje dokladnie to, co robi produkcyjny kod: sanitize, potem
    json.loads."""
    cleaned = sanitize_latex_json_backslashes(raw_json_text)
    return json.loads(cleaned)


print("=" * 70)
print("Realny, zaobserwowany przypadek: \\textbackslash w final_answer")
print("=" * 70)

# Doslowny, uproszczony odpowiednik realnego JSON-a od AI (pojedynczy
# backslash przed komendami LaTeX - typowe surowe wyjscie modelu).
raw = r'{"final_answer": "$a < -2\textbackslash sqrt5$ lub $a > 2\textbackslash sqrt5$"}'
parsed = _roundtrip(raw)
value = parsed["final_answer"]
print(f"  Sparsowana wartosc: {value!r}")
check("BRAK znaku tabulacji (\\t) w sparsowanej wartosci", "\t" not in value, value)
# UWAGA: "textbackslash" jako string ZAWIERA podciag "extbackslash"
# (samo "t"+"extbackslash") - sprawdzenie "extbackslash not in value"
# byloby FALSZYWYM FAIL nawet dla POPRAWNEGO wyniku. Prawdziwy test
# uszkodzenia to obecnosc znaku tabulacji (juz sprawdzone wyzej) I
# to, ze "\textbackslash" (z WIODACYM backslashem+t) jest CALE, nie
# rozerwane na sam tabulator + resztke.
check("obecne '\\textbackslash' jako CALA, nieuszkodzona komenda (z wiodacym \\t)",
      "\\textbackslash" in value, value)
check("obecne 'sqrt5' bez rozerwania", "sqrt5" in value, value)

print()
print("=" * 70)
print("Warianty \\text*/\\math* - kazdy osobno (ta sama luka strukturalna)")
print("=" * 70)

CASES = [
    (r'\textbackslash', 'textbackslash'),
    (r'\textbf', 'textbf'),
    (r'\textit', 'textit'),
    (r'\textrm', 'textrm'),
    (r'\texttt', 'texttt'),
    (r'\mathbf', 'mathbf'),
    (r'\mathcal', 'mathcal'),
    (r'\mathbb', 'mathbb'),
    (r'\underline', 'underline'),
    (r'\underbrace', 'underbrace'),
    (r'\usepackage', 'usepackage'),
]
for cmd, name in CASES:
    raw = '{"x": "przed ' + cmd + '{tresc} po"}'
    parsed = _roundtrip(raw)
    value = parsed["x"]
    ok = "\t" not in value and name in value and "przed" in value and "po" in value
    check(f"'{cmd}' przezywa roundtrip nienaruszony", ok, value)

print()
print("=" * 70)
print("Regresja: juz chronione komendy nadal dzialaja (brak wplywu ubocznego)")
print("=" * 70)

raw = r'{"x": "$\frac{1}{2}$ i $\sqrt{2}$ i $\text{cos}$"}'
parsed = _roundtrip(raw)
value = parsed["x"]
check("\\frac/\\sqrt/\\text nadal dzialaja poprawnie razem", "\t" not in value and "frac" in value and "sqrt" in value, value)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
