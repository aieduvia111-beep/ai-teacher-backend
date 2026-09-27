# -*- coding: utf-8 -*-
"""Offline, zero kosztow (czysta funkcja, brak OpenAI): user testowal jakosc
tlumaczenia Chatu AI po naprawie poziomu/LaTeX-a i zlapal $$F = m [TAB]imes a$$
zamiast \\times. Przyczyna: model czasem pisze w JSON-ie POJEDYNCZY backslash
przed komenda LaTeX (\\times, \\tan, \\frac, \\theta...) zamiast wymaganego
przez JSON podwojnego - json.loads() parsuje \\t/\\r/\\b/\\f jako PRAWDZIWE
znaki kontrolne (tab/CR/backspace/formfeed) i "zjada" litere, zostawiajac np.
"imes" zamiast "\\times". To dotyczy KAZDEJ komendy LaTeX zaczynajacej sie na
t/r/b/f (\\tan, \\to, \\theta, \\tau, \\beta, \\big, \\binom, \\forall, \\frac,
\\right, \\rangle...), nie tylko \\times - test sprawdza kilka z nich naraz,
zeby udowodnic ze naprawa dziala u zrodla (parsowanie JSON), nie na pojedynczym
przypadku. Sprawdza tez, ze \\n (prawdziwa nowa linia, celowo uzywana przez
model do akapitow w markdownie) NIE jest ruszane."""
import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from app.api.chat import _fix_stray_json_escapes

BS = chr(92)  # jeden, jednoznaczny znak backslash - zero wieloznacznosci przez cudzyslowy/powloki

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:200]))

# 1) BLEDNY JSON: pojedynczy backslash przed "times" (dokladnie realny bug z prod)
raw1 = '{"text": "$$F = m ' + BS + 'times a$$"}'
assert raw1.count(BS) == 1, raw1
parsed1 = json.loads(_fix_stray_json_escapes(raw1))
expected1 = "$$F = m " + BS + "times a$$"
check("pojedynczy \\ przed times -> naprawiony do poprawnego \\times", parsed1["text"] == expected1, parsed1["text"])

# 2) JUZ POPRAWNY JSON (podwojny backslash) - nie moze sie zepsuc przez naprawe
raw2 = '{"text": "$$F = m ' + BS*2 + 'times a$$"}'
assert raw2.count(BS) == 2, raw2
parsed2 = json.loads(_fix_stray_json_escapes(raw2))
check("juz poprawny podwojny \\\\times -> bez zmian, dalej poprawny", parsed2["text"] == expected1, parsed2["text"])

# 3) \n (prawdziwa nowa linia) - POPRAWNY, celowy JSON escape - NIE MOZE byc ruszony
raw3 = '{"text": "Linia 1' + BS + 'nLinia 2"}'
assert raw3.count(BS) == 1, raw3
parsed3 = json.loads(_fix_stray_json_escapes(raw3))
check("\\n (prawdziwa nowa linia) NIETKNIETE - dekoduje sie jako realny newline, nie tekst", parsed3["text"] == "Linia 1\nLinia 2", repr(parsed3["text"]))

# 4) inne podatne komendy LaTeX zaczynajace sie na t/r/b/f (nie tylko times)
for cmd, tail in [("tan", "(x)"), ("theta", ""), ("frac", "{1}{2}"), ("beta", ""), ("forall", " x"), ("right", "]"), ("tau", "")]:
    raw = '{"text": "$$' + BS + cmd + tail + '$$"}'
    assert raw.count(BS) == 1, (cmd, raw)
    parsed = json.loads(_fix_stray_json_escapes(raw))
    expected = "$$" + BS + cmd + tail + "$$"
    check(f"\\{cmd} (pojedynczy \\) -> naprawiony poprawnie", parsed["text"] == expected, parsed["text"])

# 5) zwykly tekst bez zadnych backslashy - bez zmian
raw5 = '{"text": "Zwykly tekst bez wzorow."}'
check("zwykly tekst bez backslashy - bez zmian", json.loads(_fix_stray_json_escapes(raw5))["text"] == "Zwykly tekst bez wzorow.")

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
