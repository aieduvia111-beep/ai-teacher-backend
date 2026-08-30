"""Lokalny test (zero kosztu) - naprawa _canonical_answer (math_verify.py):
\\text{}/\\mathrm{}/\\textrm{}/\\operatorname{} wrapper wokol tekstu
(legalna, powszechna praktyka LaTeX) nie moze psuc dopasowania
final_answer <-> options.

Live-test Quizu (30.08.2026, poziom trudny -> B2 fallback na medium)
ujawnil realna porazke: AI napisalo final_answer jako
"$m < -4 \\text{ lub } m > 4$", CODE-owe options mialy
"$m < -4$ lub $m > 4$" - semantycznie IDENTYCZNE, ale \\text{lub} != lub
znakowo, wiec WSZYSTKIE 8 kandydatow w tej rundzie zostalo odrzuconych
(Warstwa 1: final_answer_no_match) mimo poprawnej matematyki - Quiz
dostarczyl 0/13 zamiast pelnego kompletu."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.math_verify import match_final_answer_index, _canonical_answer

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=== _canonical_answer: \\text{} i pokrewne wrappery ===")
check("\\text{ lub } -> rozpakowane do 'lub'",
      _canonical_answer(r"$m < -4 \text{ lub } m > 4$") == _canonical_answer("$m < -4$ lub $m > 4$"))
check("\\mathrm{lub} -> rozpakowane",
      _canonical_answer(r"$m < -4 \mathrm{lub} m > 4$") == _canonical_answer("$m < -4$ lub $m > 4$"))
check("\\textrm{i} -> rozpakowane",
      _canonical_answer(r"$a > 0 \textrm{i} b > 0$") == _canonical_answer("$a > 0$ i $b > 0$"))
check("\\operatorname{lub} -> rozpakowane",
      _canonical_answer(r"$x \operatorname{lub} y$") == _canonical_answer("$x$ lub $y$"))
check("Regresja: tekst bez \\text{} dziala jak wczesniej",
      _canonical_answer("$m < -8$ lub $m > 8$") == "m<-8lubm>8")
check("Regresja: prefiks litery nadal usuwany",
      _canonical_answer("b) $m < -8$ lub $m > 8$") == "m<-8lubm>8")

print()
print("=== match_final_answer_index: dokladny przypadek z real-testu ===")
options = ["$m < -4$ lub $m > 4$", "$m < -8$ lub $m > 8$", "$m = 8$", "$m < 8$"]
fa = r"$m < -4 \text{ lub } m > 4$"
status, idx = match_final_answer_index(fa, options)
check("PRZED naprawa: no_match (0/13 w real-tescie) - TERAZ: forced, idx=0",
      status == "forced" and idx == 0, (status, idx))

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
