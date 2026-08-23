"""
Test regresyjny Universal Difficulty Engine - ETAP 1 (silnik + adapter
rownan kwadratowych), TESTOWANY W IZOLACJI - app/difficulty/ NIE jest dzis
podlaczony do prawdziwego pipeline'u Quiz/Sprawdzian (openai_exam.py,
exam_pdf_generator.py sa nietkniete).

Uruchom: python test_difficulty_engine.py

Sprawdza:
1. scoring.py: normalizacja cech, suma wag = 100, compute_score na
   skrajnych przypadkach (wszystko zero -> 0, wszystko maksymalne -> 100).
2. calibration.py: mapowanie score -> easy/medium/hard, granice przedzialow.
3. features.py: ekstrakcja cech (has_parameter, cases, conditions,
   methods, steps z/bez wyjasnienia) na konkretnych przykladach.
4. modifiers/math_quadratic.py: adapter daje DOKLADNIE TAKI SAM wynik jak
   bezposrednie wywolanie math_verify.validate_quadratic_difficulty /
   classify_quadratic_difficulty (regresja - adapter NIE zmienia logiki).
5. DifficultyAnalyzer.analyze() end-to-end: te same przypadki co w
   test_math_verify.py (easy/medium/hard, rownanie w opcjach, brak
   rownania) - domain_verdict musi sie zgadzac z istniejacym,
   przetestowanym zachowaniem Warstwy 3.
6. Confidence: wysoka (1.0) gdy domain modifier trafil, nizsza gdy nie,
   bardzo niska gdy brak jakichkolwiek cech matematycznych.
"""
import sys
sys.path.insert(0, ".")

from app.difficulty import DifficultyAnalyzer, DifficultyBreakdown, DifficultyScore, DifficultyConfidence
from app.difficulty.scoring import compute_score, feature_contributions, _FEATURE_SPECS
from app.difficulty.calibration import calibrate, DEFAULT_THRESHOLDS
from app.difficulty.features import extract_features
from app.difficulty.modifiers.math_quadratic import QuadraticEquationModifier
from app.math_verify import validate_quadratic_difficulty, classify_quadratic_difficulty

FAILED = []


def check(name, condition, detail=""):
    if condition:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


# ============================================================
# 1. scoring.py
# ============================================================
print("=== scoring.py: normalizacja i suma wag ===")

check("wagi cech sumuja sie do 100", sum(w for _, w, _, _ in _FEATURE_SPECS) == 100, sum(w for _, w, _, _ in _FEATURE_SPECS))

empty = DifficultyBreakdown()
check("wszystko-zero -> score 0", compute_score(empty) == 0, compute_score(empty))

maxed = DifficultyBreakdown(steps=99, operations=99, conditions=99, methods=99, cases=99, has_parameter=True, abstraction_level=99)
check("wszystko-maksymalne -> score 100", compute_score(maxed) == 100, compute_score(maxed))

only_param = DifficultyBreakdown(has_parameter=True)
check("tylko has_parameter=True -> score = waga has_parameter (10)", compute_score(only_param) == 10, compute_score(only_param))

contrib = feature_contributions(empty)
check("feature_contributions zwraca wpis dla kazdej cechy", set(contrib.keys()) == {n for n, _, _, _ in _FEATURE_SPECS}, contrib.keys())


# ============================================================
# 2. calibration.py
# ============================================================
print()
print("=== calibration.py: mapowanie score -> poziom ===")

check("score 0 -> easy", calibrate(0) == "easy", calibrate(0))
check("score 34 -> easy (granica dolna medium)", calibrate(34) == "easy", calibrate(34))
check("score 35 -> medium (dokladnie na granicy)", calibrate(35) == "medium", calibrate(35))
check("score 64 -> medium", calibrate(64) == "medium", calibrate(64))
check("score 65 -> hard", calibrate(65) == "hard", calibrate(65))
check("score 100 -> hard", calibrate(100) == "hard", calibrate(100))
check("nieznany poziom -> fallback na DEFAULT_THRESHOLDS", calibrate(50, level="nieistniejacy_poziom_xyz") == calibrate(50, level=None), (calibrate(50, "x"), calibrate(50)))


# ============================================================
# 3. features.py
# ============================================================
print()
print("=== features.py: ekstrakcja cech ===")

b, has_f = extract_features(
    "Dla jakich wartości parametru $m$ równanie $x^2+(m-3)x+m=0$ ma dwa różne pierwiastki?",
    option_texts=["$m<1$", "$m>9$", "$m<1$ lub $m>9$", "$1<m<9$"],
)
check("wykrywa has_parameter=True (litera m)", b.has_parameter is True, b)
check("wykrywa formuly (has_formulas=True)", has_f is True, has_f)

b2, has_f2 = extract_features("Rozwiąż równanie $x^2-5x+6=0$", option_texts=["$x=2$ i $x=3$", "a", "b", "c"])
check("bez parametru (tylko x) -> has_parameter=False", b2.has_parameter is False, b2)

b3, _ = extract_features(
    "Dla jakich wartości parametru $k$ równanie ma dokładnie jedno rozwiązanie? "
    "Rozważ osobno przypadek gdy $k=0$."
)
check("wykrywa 'rozważ osobno' i 'gdy' -> cases>=1 i conditions>=1", b3.cases >= 1 and b3.conditions >= 1, b3)

b4, _ = extract_features("Oblicz pochodną i deltę tego wyrażenia korzystając ze wzorów Viete")
check("wykrywa slowa-klucze metod (pochodna/delta/viete) -> methods>=2", b4.methods >= 2, b4)

b5, _ = extract_features("Kto napisał Pana Tadeusza?", option_texts=["Mickiewicz", "Słowacki", "Kochanowski", "Sienkiewicz"])
check("tresc bez matematyki -> brak formul, brak parametru, brak metod", b5.has_parameter is False and b5.methods == 0, b5)

expl_text = "Liczymy deltę: $\\Delta=9$. Warunek: $\\Delta>0$. Rozwiązując, mamy $m<1$ lub $m>9$."
b6, _ = extract_features("Dla jakich $m$ ...?", explanation_text=expl_text)
check("steps liczone z wyjasnienia (3 zdania z formula)", b6.steps == 3, b6.steps)


# ============================================================
# 4. modifiers/math_quadratic.py - REGRESJA wzgledem math_verify.py
# ============================================================
print()
print("=== math_quadratic.py: adapter = identyczny wynik co bezposrednie wywolanie ===")

modifier = QuadraticEquationModifier()

cases = [
    ("Dla jakich wartości parametru $m$ równanie $x^2+(m-3)x+m=0$ ma dwa różne pierwiastki?", None, "medium"),
    ("Rozwiąż równanie $x^2-5x+6=0$", None, "easy"),
    ("Które z poniższych równań ma dwa różne pierwiastki rzeczywiste?",
     ["$x^2-5x+6=0$", "$x^2+4=0$", "$x^2-2x+5=0$", "$x^2+9=0$"], "easy"),
    ("Kto napisał Pana Tadeusza?", ["Mickiewicz", "Słowacki", "Kochanowski", "Sienkiewicz"], "hard"),
]
for text, opts, diff in cases:
    direct = validate_quadratic_difficulty(text, diff, option_texts=opts)
    via_adapter = modifier.evaluate(text, opts, diff)
    check(
        f"adapter.evaluate() == validate_quadratic_difficulty() dla '{text[:40]}...' ({diff})",
        via_adapter == direct,
        (via_adapter, direct),
    )
    direct_applies = classify_quadratic_difficulty(text, option_texts=opts) is not None
    check(
        f"adapter.applies() zgodny z classify_quadratic_difficulty() dla '{text[:40]}...'",
        modifier.applies(text, opts) == direct_applies,
        (modifier.applies(text, opts), direct_applies),
    )

check("adapter.evaluate() bez requested_difficulty_word -> None (nie zgaduje)",
      modifier.evaluate("Rozwiąż $x^2-5x+6=0$", None, None) is None,
      modifier.evaluate("Rozwiąż $x^2-5x+6=0$", None, None))


# ============================================================
# 5. DifficultyAnalyzer end-to-end
# ============================================================
print()
print("=== DifficultyAnalyzer.analyze() end-to-end ===")

analyzer = DifficultyAnalyzer()

r = analyzer.analyze(
    "Dla jakich wartości parametru $m$ równanie $x^2+(m-3)x+m=0$ ma dwa różne pierwiastki?",
    option_texts=["$m<1$", "$m>9$", "$m<1$ lub $m>9$", "$1<m<9$"],
    requested_difficulty_word="medium", level="liceum_2",
)
check("medium+parametr+prosty warunek -> domain_verdict=ok", r.domain_verdict == "ok", r.domain_verdict)
check("domain='math_quadratic'", r.domain == "math_quadratic", r.domain)
check("confidence=1.0 gdy domain trafil", r.confidence.value == 1.0, r.confidence)
check("score jest int 0-100", isinstance(r.score, int) and 0 <= r.score <= 100, r.score)
check("level jest jedna z easy/medium/hard", r.level in ("easy", "medium", "hard"), r.level)

r2 = analyzer.analyze("Rozwiąż równanie $x^2-5x+6=0$", option_texts=["$x=2$ i $x=3$", "a", "b", "c"],
                       requested_difficulty_word="hard", level="liceum_2")
check("za latwe rownanie vs 'hard' -> domain_verdict=fail", r2.domain_verdict == "fail", r2.domain_verdict)
check("domain_detail zawiera reason przy fail", "reason" in (r2.domain_detail or {}), r2.domain_detail)

r3 = analyzer.analyze("Kto napisał Pana Tadeusza?", option_texts=["Mickiewicz", "Słowacki", "Kochanowski", "Sienkiewicz"],
                       requested_difficulty_word="hard", level="liceum_2")
check("tresc bez matematyki -> domain=None (zaden modifier nie pasuje)", r3.domain is None, r3.domain)
check("tresc bez matematyki -> domain_verdict=None", r3.domain_verdict is None, r3.domain_verdict)
check("tresc bez matematyki -> niska confidence (<=0.3)", r3.confidence.value <= 0.3, r3.confidence)
check("tresc bez matematyki -> score nisk (0, brak cech)", r3.score == 0, r3.score)

r4 = analyzer.analyze("Dla jakich wartości parametru $k$ równanie $kx^2-(k+2)x+2=0$ ma dokładnie jedno rozwiązanie rzeczywiste? Rozważ osobno przypadek $k=0$.",
                       option_texts=["a", "b", "c", "d"])  # brak requested_difficulty_word
check("brak requested_difficulty_word -> domain_verdict=None (adapter nie zgaduje)", r4.domain_verdict is None, r4.domain_verdict)
check("brak requested_difficulty_word -> domain nadal wykryty (applies() dziala niezaleznie)", r4.domain == "math_quadratic", r4.domain)
check("wysoka zlozonosc (parametr+przypadek) -> score > 20", r4.score > 20, r4.score)


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
