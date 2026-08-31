"""Lokalne testy (zero kosztu) - verify_param_quadratic_always_inequality_question
(31.08.2026, znaleziona real-testem: temat "nierownosci z parametrem" generuje
pytania typu "dla jakich m nierownosc ... jest spelniona dla wszystkich x",
ktorych verify_inequality_question NIE lapie - dwie zmienne (x i m) naraz)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import verify_param_quadratic_always_inequality_question, verify_and_fix_math_question

print("=" * 70)
print("Dokladnie pytanie z realnej generacji (real-test 31.08.2026):")
print(r"x^2 + (m-3)x + m^2 > 0 dla wszystkich x. AI odpowiedziało m>3 (BLEDNIE -")
print("prawdziwa odpowiedz to m<-3 lub m>1, zadna z 4 opcji AI jej nie mial).")
print("=" * 70)
q = r"Dla jakich wartości parametru $m$ nierówność $x^2 + (m-3)x + m^2 > 0$ jest spełniona dla wszystkich $x \in \mathbb{R}$?"
opts_ai_real = [
    r"a) $m < 3$",
    r"b) $m > 3$",  # AI's (BLEDNA) odpowiedz
    r"c) $m = 3$",
    r"d) $m \geq 3$",
]
r1 = verify_param_quadratic_always_inequality_question(q, opts_ai_real)
check("realny przypadek: ZADNA z 4 opcji AI nie jest poprawna -> no_option_matches (odrzucenie)",
      r1.get("status") == "no_option_matches", r1)

opts_with_correct = [
    r"a) $m < -3$ lub $m > 1$",  # POPRAWNA
    r"b) $m > 3$",
    r"c) $m = 3$",
    r"d) $-3 < m < 1$",
]
r2 = verify_param_quadratic_always_inequality_question(q, opts_with_correct)
check("z poprawna opcja wsrod 4 -> wykrywa ja (indeks 0)",
      r2.get("status") == "match_index" and r2.get("true_index") == 0, r2)

print()
print("=" * 70)
print("Regresja: verify_and_fix_math_question nadal poprawnie obsluguje")
print("rownania kwadratowe z parametrem (istniejacy wzorzec, nie ten nowy)")
print("=" * 70)
q_eq = r"Dla jakich wartości parametru $m$ równanie $x^2+mx+16=0$ ma dwa różne pierwiastki?"
opts_eq = [r"a) $m<-8$ lub $m>8$", r"b) $m<-4$ lub $m>4$", r"c) $m=8$", r"d) $m<8$"]
r3 = verify_and_fix_math_question(q_eq, opts_eq)
check("rownanie z parametrem (istniejacy wzorzec) nadal dziala: opcja a (indeks 0)",
      r3.get("status") == "match_index" and r3.get("true_index") == 0, r3)

print()
print("=" * 70)
print("Bezpieczny abstain")
print("=" * 70)
check("brak frazy 'dla wszystkich x' -> unverifiable",
      verify_param_quadratic_always_inequality_question(r"Rozwiąż $x^2+(m-3)x+m^2>0$", opts_with_correct).get("status") == "unverifiable")
check("wspolczynnik wiodacy zawiera parametr -> abstain (zbyt zlozone)",
      verify_param_quadratic_always_inequality_question(
          r"Dla jakich $a$ nierówność $ax^2+2x+1>0$ jest spełniona dla wszystkich $x$?", opts_with_correct
      ).get("status") == "unverifiable")
check("A>0 z operatorem '<' (matematycznie niemozliwe) -> abstain, nie zgaduje",
      verify_param_quadratic_always_inequality_question(
          r"Dla jakich $m$ nierówność $x^2+mx+1<0$ jest spełniona dla wszystkich $x$?", opts_with_correct
      ).get("status") == "unverifiable")

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
