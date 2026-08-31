"""Lokalne testy (zero kosztu) - weryfikacja nierownosci wymiernych/
wielomianowych (31.08.2026, user live-test znalazl realne bledy w kluczu
odpowiedzi dla klasy 'algebra_symbolic', ktora nie miala ZADNEJ automatycznej
weryfikacji - patrz komentarz nad verify_inequality_question w math_verify.py).
Testuje DOKLADNIE przypadki z realnego zgloszenia (recenzja sprawdzianu)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import verify_inequality_question, _parse_interval_notation, _find_inequality_in_text

print("=" * 70)
print("Zadanie 1 z realnego zgloszenia: (2x-3)/(x+1)>1")
print("Poprawna odpowiedz: x<-1 lub x>4. Klucz mial BLEDNIE x<-1 lub x>2.")
print("=" * 70)
q1 = r"Rozwiaz nierownosc $\frac{2x-3}{x+1}>1$"
opts_wrong = [
    r"a) $(-\infty,-1)$",
    r"b) $(-\infty,-1)\cup(2,\infty)$",  # BLEDNA opcja z realnego sprawdzianu
    r"c) $(2,4)$",
    r"d) $(-\infty,-1)\cup(4,\infty)$",  # POPRAWNA
]
r1 = verify_inequality_question(q1, opts_wrong)
check("wykrywa poprawna opcje (d, indeks 3) jako prawdziwa", r1.get("status") == "match_index" and r1.get("true_index") == 3, r1)

opts_only_wrong = [
    r"a) $(-\infty,-1)$",
    r"b) $(-\infty,-1)\cup(2,\infty)$",  # BLEDNA (dokladnie jak w realnym sprawdzianie)
    r"c) $(2,4)$",
    r"d) $(-1,4)$",
]
r1b = verify_inequality_question(q1, opts_only_wrong)
check("gdy ZADNA opcja nie jest poprawna (jak w realnym bledzie) -> no_option_matches (odrzucenie)",
      r1b.get("status") == "no_option_matches", r1b)

print()
print("=" * 70)
print("Zadanie 8 z realnego zgloszenia: (x^2-3x+2)/(x-1) >= 0, x=1 wykluczone")
print("Poprawna odpowiedz: [2, oo). Klucz mial dodatkowo blednie (-oo,1).")
print("=" * 70)
q8 = r"Rozwiaz nierownosc $\frac{x^2-3x+2}{x-1}\geq0$"
opts8 = [
    r"a) $(-\infty,1)\cup[2,\infty)$",  # BLEDNA (jak w realnym sprawdzianie)
    r"b) $[2,\infty)$",  # POPRAWNA
    r"c) $(-\infty,2]$",
    r"d) $[1,2]$",
]
r8 = verify_inequality_question(q8, opts8)
check("wykrywa poprawna opcje (b, indeks 1) jako prawdziwa, odrzuca [2,oo)+(-oo,1)",
      r8.get("status") == "match_index" and r8.get("true_index") == 1, r8)

print()
print("=" * 70)
print("Regresja: zwykla nierownosc kwadratowa bez ulamka (x^2-5x+6<0 -> (2,3))")
print("=" * 70)
q5 = r"Rozwiaz nierownosc $x^2-5x+6<0$"
opts5 = [r"a) $(-\infty,2)$", r"b) $(2,3)$", r"c) $(3,\infty)$", r"d) $(2,\infty)$"]
r5 = verify_inequality_question(q5, opts5)
check("nierownosc wielomianowa (bez ulamka) tez dziala: (2,3) = indeks 1",
      r5.get("status") == "match_index" and r5.get("true_index") == 1, r5)

print()
print("=" * 70)
print("Bezpieczny abstain (nie crashuje, nie zgaduje)")
print("=" * 70)
check("brak nierownosci w tekscie -> unverifiable",
      verify_inequality_question("Ile to jest 2+2?", ["a) 4"]).get("status") == "unverifiable")
check("pusty tekst -> unverifiable",
      verify_inequality_question("", []).get("status") == "unverifiable")
check("rownanie (nie nierownosc) -> unverifiable (to inna funkcja)",
      verify_inequality_question(r"Rozwiaz $x^2-5x+6=0$", ["a) x=2"]).get("status") == "unverifiable")

print()
print("=" * 70)
print("_parse_interval_notation - parsowanie surowe")
print("=" * 70)
s1 = _parse_interval_notation(r"$(-\infty,-2)\cup(3,\infty)$")
check("(-oo,-2) U (3,oo) parsuje sie poprawnie", s1 is not None and str(s1) == "Union(Interval.open(-oo, -2), Interval.open(3, oo))", s1)
s2 = _parse_interval_notation(r"$[-\frac{3}{2},1)$")
check("polprzedzial domkniety-otwarty z ulamkiem [-3/2, 1) parsuje sie", s2 is not None, s2)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
