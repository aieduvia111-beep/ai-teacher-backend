# -*- coding: utf-8 -*-
"""User (sierpien 2026, po TRZECIM z rzedu waskim zgloszeniem zlego
renderowania LaTeX/$ w TEJ SAMEJ sesji - osierocony dolar, gola litera,
teraz literalny "5\\sqrt{3}" bez $ w Pytaniu 6 real-testu Trygonometrii):
"będziemy naprawiać błędy pojedyncze, których są miliard... cały system
ma być profesjonalny". Zamiast kolejnego waskiego regex-patcha dla
KONKRETNEGO ksztaltu zlego LaTeX-a (dokladnie ta sama slepa uliczka co
przy matematyce, ktora doprowadzila do Warstwy 2.5), dodano JEDNA,
OGOLNA bramke walidacyjna (Warstwa 1.5): sprawdza STRUKTURALNA
poprawnosc (parzystosc $, zadna znana komenda LaTeX poza $ $), nie
konkretny wzorzec - lapie KAZDY przyszly przypadek tej klasy, nie tylko
juz-zaobserwowane. Zero AI (czysta, deterministyczna walidacja tekstu) -
wpiete w JUZ istniejacy mechanizm odrzucania/regeneracji (ten sam co
Warstwa 1/2/2.5), identycznie w Quizie i Sprawdzianie (zamkniete +
otwarte)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.openai_exam import validate_latex_formatting, validate_question_latex

print("=" * 70)
print("Real przypadek (Pytanie 6, Sprawdzian: Trygonometria)")
print("=" * 70)
ok, reason = validate_latex_formatting("a) 5\\sqrt{3}")
check("Literalny '\\sqrt{3}' BEZ $ -> wykryte jako niepoprawne", ok is False, reason)

ok2, reason2 = validate_latex_formatting("a) $5\\sqrt{3}$")
check("Ten sam wzor, POPRAWNIE owiniety w $ -> OK", ok2 is True, reason2)

print()
print("=" * 70)
print("Regresja: znane, juz naprawione dzis przypadki $ (osierocony dolar, gola litera)")
print("=" * 70)
check("Osierocony dolar (nieparzysta liczba) -> wykryte",
      validate_latex_formatting("Liczymy deltę:$ $Δ=5$")[0] is False)
check("Poprawna para z gola litera '$n$' -> OK (nie falszywy alarm)",
      validate_latex_formatting("Oblicz $n$-ty wyraz ciągu.")[0] is True)
check("Zwykly tekst bez LaTeX w ogole -> OK",
      validate_latex_formatting("To jest zwykłe zdanie po polsku, bez matematyki.")[0] is True)

print()
print("=" * 70)
print("Wieloznakowe komendy w POPRAWNYCH, oddzielnych parach $ $ -> OK")
print("=" * 70)
check("Dwie oddzielne, poprawne pary z komendami wewnatrz -> OK",
      validate_latex_formatting("Wzór: $S = \\frac{a+b}{2}$. Podstawiając: $S = \\frac{3+5}{2} = 4$.")[0] is True)

print()
print("=" * 70)
print("validate_question_latex - sprawdza WIELE pol naraz (w tym listy/opcje)")
print("=" * 70)
q_bad = {"question": "Oblicz.", "options": ["a) 5\\sqrt{3}", "b) $5$", "c) $6$", "d) $7$"], "explanation": "OK"}
ok3, reason3 = validate_question_latex(q_bad, ["question", "options", "explanation"])
check("Zla opcja WSROD listy 'options' -> wykryta (pole 'options')",
      ok3 is False and "options" in reason3, reason3)

q_good = {"question": "Oblicz $x^2$.", "options": ["a) $5$", "b) $6$", "c) $7$", "d) $8$"], "explanation": "Wzór: $\\sqrt{4}=2$."}
ok4, reason4 = validate_question_latex(q_good, ["question", "options", "explanation"])
check("Wszystkie pola poprawne -> OK", ok4 is True, reason4)

q_missing_field = {"question": "Bez opcji."}
ok5, reason5 = validate_question_latex(q_missing_field, ["question", "options", "explanation"])
check("Brakujace pola (None) -> nie crashuje, OK", ok5 is True, reason5)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
