"""Lokalne testy (zero kosztu) - Universal Difficulty Engine rozszerzony
o calki nieoznaczone (30.08.2026, user: "co z poziomem, jest odpowiedni,
sprawdz dobrze" po live-tescie ktory pokazal "studia"+"trudna" = w
calosci PODSTAWOWE wzory calkowania, np. ∫e^2x dx, ∫1/x dx - dokladnie
to samo pasmo co "latwy"). Wczesniej Universal Difficulty Engine mial
domain modifiery TYLKO dla rownan/funkcji/ciagow/trygonometrii - calki
nie mialy ZADNEJ programowej weryfikacji trudnosci."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import classify_integral_difficulty, validate_integral_difficulty
from app.level_config import is_integral_topic, get_integral_difficulty_anchor
from app.difficulty.analyzer import DifficultyAnalyzer

print("=" * 70)
print("classify_integral_difficulty: DOKLADNE przypadki z real-testu 30.08.2026")
print("=" * 70)
basic_cases = [
    (r"\int (3x^2 - 2x + 1) \, dx", "wielomian"),
    (r"\int e^{2x} \, dx", "e^(liniowe)"),
    (r"\int \sin(3x) \, dx", "sin(liniowe)"),
    (r"\int \frac{1}{x} \, dx", "1/x"),
    (r"\int (x^3 - 4x^2 + 6x - 8) \, dx", "wielomian"),
    (r"\int \frac{1}{(x+1)^2} \, dx", "(liniowe)^n"),
    (r"\int \frac{2x-3}{x^2} \, dx", "rozklada sie na potegi x"),
    (r"\int \cos(2x) \, dx", "cos(liniowe)"),
]
for expr, note in basic_cases:
    got = classify_integral_difficulty(expr)
    check(f"'{note}' -> tier 1 (podstawowe): {expr}", got == "1", got)

advanced_cases = [
    (r"\int \cos^2(x) \, dx", "tozsamosc trygonometryczna"),
    (r"\int \frac{x}{x^2+1} \, dx", "podstawienie"),
    (r"\int \tan(x) \, dx", "podstawienie (tan=sin/cos)"),
    (r"\int (2x+3)e^{x^2+3x} \, dx", "podstawienie (pochodna wykladnika)"),
    # NAPRAWIONE (live-test 30.08.2026): ln(x) BLEDNIE klasyfikowane jako
    # tier 1 (argument liniowy = sam x), mimo ze ZAWSZE wymaga calkowania
    # przez czesci (x*ln(x)-x+C) - w odroznieniu od sin/cos/exp liniowego
    # argumentu, ktorych antypochodna zostaje w tej samej rodzinie funkcji.
    (r"\int \ln(x) \, dx", "ln(cokolwiek) zawsze wymaga przez czesci"),
    (r"\int \ln(2x+3) \, dx", "ln(liniowe) tez wymaga przez czesci"),
    (r"\int x \cdot e^{x^2} \, dx", "podstawienie (pochodna wykladnika)"),
    (r"\int e^{2x} \sin(3x) \, dx", "podwojne przez czesci"),
]
for expr, note in advanced_cases:
    got = classify_integral_difficulty(expr)
    check(f"'{note}' -> tier 3 (zaawansowane): {expr}", got == "3", got)

print()
print("=" * 70)
print("classify_integral_difficulty: bezpieczny abstain")
print("=" * 70)
check("brak calki w tekscie -> None", classify_integral_difficulty("Ile to jest 2+2?") is None)
check("pusty string -> None", classify_integral_difficulty("") is None)
check("nierozpoznawalny/uszkodzony wzor -> None (nie crash)",
      classify_integral_difficulty(r"\int @#$%^& \, dx") is None)

print()
print("=" * 70)
print("validate_integral_difficulty: dokladny real przypadek (studia+trudna+basic=FAIL)")
print("=" * 70)
result = validate_integral_difficulty(r"\int e^{2x} \, dx", "trudna")
check("basic integral zadane jako 'trudna' -> status=fail", result["status"] == "fail", result)
check("reason wspomina 'za latwe'", "za latwe" in result.get("reason", ""), result)

result2 = validate_integral_difficulty(r"\int (2x+3)e^{x^2+3x} \, dx", "trudna")
check("advanced integral zadane jako 'trudna' -> status=ok", result2["status"] == "ok", result2)

result3 = validate_integral_difficulty(r"\int e^{2x} \, dx", "latwa")
check("basic integral zadane jako 'latwa' -> status=ok", result3["status"] == "ok", result3)

result4 = validate_integral_difficulty("Ile to jest 2+2?", "trudna")
check("nie-calka -> status=not_integral (abstain, nie blokuje)", result4["status"] == "not_integral", result4)

print()
print("=" * 70)
print("is_integral_topic / get_integral_difficulty_anchor")
print("=" * 70)
check("'Matematyka: całki nieoznaczone' -> True", is_integral_topic("Matematyka: całki nieoznaczone"))
check("'Równania kwadratowe' -> False", not is_integral_topic("Równania kwadratowe"))
check("anchor dla 'trudna' istnieje i wspomina technike", "technik" in (get_integral_difficulty_anchor("trudna") or "").lower())
check("anchor dla nierozpoznanego slowa -> None", get_integral_difficulty_anchor("cokolwiek") is None)

print()
print("=" * 70)
print("DifficultyAnalyzer: pelna integracja (modifier zarejestrowany, wplywa na wynik)")
print("=" * 70)
analyzer = DifficultyAnalyzer()
score = analyzer.analyze(
    r"Oblicz całkę nieoznaczoną $\int e^{2x} \, dx$.", option_texts=None,
    requested_difficulty_word="trudna", level="studia",
)
check("domain == 'math_integral'", score.domain == "math_integral", score.domain)
check("domain_detail status == 'fail' (dokladnie ten real przypadek)",
      score.domain_detail and score.domain_detail.get("status") == "fail", score.domain_detail)

score_ok = analyzer.analyze(
    r"Oblicz całkę nieoznaczoną $\int \tan(x) \, dx$.", option_texts=None,
    requested_difficulty_word="trudna", level="studia",
)
check("advanced integral jako 'trudna' -> status=ok przez pelny analyzer",
      score_ok.domain_detail and score_ok.domain_detail.get("status") == "ok", score_ok.domain_detail)

print()
print("=" * 70)
print("Regresja: DifficultyAnalyzer nadal poprawnie obsluguje rownania kwadratowe")
print("=" * 70)
score_quad = analyzer.analyze(
    "Dla jakich wartości parametru m równanie $x^2+mx+16=0$ ma dwa różne pierwiastki?",
    option_texts=["$m<-8$ lub $m>8$", "$m<-4$ lub $m>4$", "$m=8$", "$m<8$"],
    requested_difficulty_word="hard", level=None,
)
check("rownanie kwadratowe nadal rozpoznawane jako domain='math_quadratic' (nie zderzenie z integral)",
      score_quad.domain == "math_quadratic", score_quad.domain)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
