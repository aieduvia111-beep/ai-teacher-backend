"""
Test regresyjny ETAPU 5 (kalibracja 24 poziomow edukacyjnych) - w
izolacji, NIE podlaczone jeszcze do prawdziwego pipeline'u
(openai_exam.py / exam_pdf_generator.py nietkniete - zgodnie z
instrukcja, to bedzie OSOBNY, kolejny krok).

Uruchom: python test_etap5.py

Sprawdza:
1. level_index() - normalizacja "roku nauki" 0.0-1.0, liceum/technikum
   na tych samych latach (kluczowa poprawka wzgledem naiwnej pozycji-w-
   liscie omowiona w planie).
2. LEVEL_THRESHOLDS - dokladnie 24 wpisy zgodne z level_config.py,
   monotoniczne granice, wartosci brzegowe dokladnie takie jak w planie.
3. calibrate(score, level) - ten sam score inaczej klasyfikowany dla
   roznych poziomow.
4. level_adjusted_tier_shift() - shift=0 dla baseline (liceum_2), 0 dla
   None/nieznanego poziomu (bezpieczny fallback), niezerowy dla poziomow
   odleglejszych od baseline.
5. QuadraticEquationModifier.evaluate() z level=None -> DOKLADNIE
   identyczny wynik jak validate_quadratic_difficulty (zero regresji).
6. KLUCZOWY TEST (zadanie usera): to samo pytanie (rownanie kwadratowe,
   tier 5-6) oceniane dla podstawowka_7 / liceum_2 / studia_1 - test
   RAPORTUJE PRAWDZIWY wynik (moze pokazac identyczna klasyfikacje, jesli
   te trzy konkretne poziomy wypadaja blisko siebie na osi "rok nauki" -
   patrz komentarz w asercji), PLUS dodatkowy test na bardziej odleglych
   poziomach (podstawowka_1 vs studia_5) potwierdzajacy, ze mechanizm
   PRZESUNIECIA faktycznie dziala, gdy poziomy sa dostatecznie odlegle.
"""
import sys
sys.path.insert(0, ".")

from app.difficulty.calibration import (
    level_index, LEVEL_THRESHOLDS, LEVEL_YEAR, calibrate,
    level_adjusted_tier_shift, QUADRATIC_BASELINE_LEVEL, QUADRATIC_MAX_SHIFT,
)
from app.difficulty.modifiers.math_quadratic import QuadraticEquationModifier
from app.math_verify import validate_quadratic_difficulty, classify_quadratic_difficulty
from app import level_config

FAILED = []


def check(name, condition, detail=""):
    if condition:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


# ============================================================
# 1. level_index() - "rok nauki", liceum/technikum rownolegle
# ============================================================
print("=== level_index(): normalizacja roku nauki ===")

check("podstawowka_1 -> index 0.0 (najlatwiejszy)", level_index("podstawowka_1") == 0.0, level_index("podstawowka_1"))
check("studia_5 -> index 1.0 (najtrudniejszy)", level_index("studia_5") == 1.0, level_index("studia_5"))
check("liceum_2 i technikum_2 -> IDENTYCZNY index (rownolegle sciezki, ten sam rok)",
      level_index("liceum_2") == level_index("technikum_2"), (level_index("liceum_2"), level_index("technikum_2")))
check("liceum_4 < technikum_5 (technikum ma 5 lat, liceum 4)",
      level_index("liceum_4") < level_index("technikum_5"), (level_index("liceum_4"), level_index("technikum_5")))
check("nieznany poziom -> None", level_index("nieistniejacy_xyz") is None, level_index("nieistniejacy_xyz"))
check("koszyk ogolny bez numeru ('liceum') -> None (celowo, patrz docstring)", level_index("liceum") is None, level_index("liceum"))

# Monotonicznosc wewnatrz podstawowki
podst_indices = [level_index(f"podstawowka_{i}") for i in range(1, 9)]
check("indeksy podstawowka_1..8 SCISLE rosnace", podst_indices == sorted(podst_indices) and len(set(podst_indices)) == 8, podst_indices)


# ============================================================
# 2. LEVEL_THRESHOLDS - zgodnosc z level_config.py, wartosci brzegowe
# ============================================================
print()
print("=== LEVEL_THRESHOLDS: kompletnosc i wartosci brzegowe ===")

# level_config.py trzyma opisy pod tymi samymi kluczami (LEVEL_DESC) -
# sprawdzamy, ze KAZDY klucz konkretnej klasy (nie koszyk ogolny) tam
# obecny ma tez wpis w LEVEL_THRESHOLDS, i na odwrot.
concrete_keys_in_level_config = {
    k for k in level_config.LEVEL_DESC.keys()
    if k not in ("podstawowka", "liceum", "technikum", "matura", "studia", "gimnazjum")
}
check("LEVEL_THRESHOLDS ma dokladnie 24 poziomy", len(LEVEL_THRESHOLDS) == 24, len(LEVEL_THRESHOLDS))
check("LEVEL_THRESHOLDS pokrywa DOKLADNIE te same klucze co konkretne klasy w level_config.LEVEL_DESC",
      set(LEVEL_THRESHOLDS.keys()) == concrete_keys_in_level_config,
      (set(LEVEL_THRESHOLDS.keys()) - concrete_keys_in_level_config, concrete_keys_in_level_config - set(LEVEL_THRESHOLDS.keys())))

t1 = LEVEL_THRESHOLDS["podstawowka_1"]
check("podstawowka_1: easy/medium granica = 15 (z planu)", t1["easy"] == (0, 15.0), t1)
check("podstawowka_1: medium/hard granica = 35 (z planu)", t1["medium"] == (15.0, 35.0), t1)

t5 = LEVEL_THRESHOLDS["studia_5"]
check("studia_5: easy/medium granica = 45 (z planu)", t5["easy"] == (0, 45.0), t5)
check("studia_5: medium/hard granica = 75 (z planu)", t5["medium"] == (45.0, 75.0), t5)

# Monotonicznosc: granice rosna wraz z poziomem (trudniej osiagnac "hard")
b1_values = [LEVEL_THRESHOLDS[lvl]["easy"][1] for lvl in sorted(LEVEL_YEAR, key=lambda l: LEVEL_YEAR[l])]
check("granice easy/medium NIE MALEJACE wraz z rosnacym poziomem", b1_values == sorted(b1_values), b1_values)


# ============================================================
# 3. calibrate(score, level) - ten sam score, inny wynik per poziom
# ============================================================
print()
print("=== calibrate(): ten sam score, rozny poziom -> rozny wynik ===")

check("score=40: 'hard' dla podstawowka_1 (b2=35, 40>=35)", calibrate(40, "podstawowka_1") == "hard", calibrate(40, "podstawowka_1"))
check("score=40: 'easy' dla studia_5 (b1=45, 40<45)", calibrate(40, "studia_5") == "easy", calibrate(40, "studia_5"))
check("score=40 bez poziomu -> DEFAULT_THRESHOLDS (35-65) -> 'medium'", calibrate(40, None) == "medium", calibrate(40, None))


# ============================================================
# 4. level_adjusted_tier_shift()
# ============================================================
print()
print("=== level_adjusted_tier_shift() ===")

check("shift(liceum_2) == 0 (to jest baseline)", level_adjusted_tier_shift("liceum_2") == 0, level_adjusted_tier_shift("liceum_2"))
check("shift(None) == 0 (bezpieczny fallback)", level_adjusted_tier_shift(None) == 0, level_adjusted_tier_shift(None))
check("shift(nieznany) == 0 (bezpieczny fallback)", level_adjusted_tier_shift("xyz") == 0, level_adjusted_tier_shift("xyz"))
check("shift(podstawowka_1) < 0 (latwiejszy niz baseline)", level_adjusted_tier_shift("podstawowka_1") < 0, level_adjusted_tier_shift("podstawowka_1"))
check("shift(studia_5) > 0 (trudniejszy niz baseline)", level_adjusted_tier_shift("studia_5") > 0, level_adjusted_tier_shift("studia_5"))
print(f"    (QUADRATIC_BASELINE_LEVEL={QUADRATIC_BASELINE_LEVEL}, QUADRATIC_MAX_SHIFT={QUADRATIC_MAX_SHIFT})")


# ============================================================
# 5. Zero regresji: level=None -> identyczny wynik jak dzis
# ============================================================
print()
print("=== QuadraticEquationModifier.evaluate(): zero regresji bez level ===")

modifier = QuadraticEquationModifier()
cases = [
    ("Dla jakich wartości parametru $m$ równanie $x^2+(m-3)x+m=0$ ma dwa różne pierwiastki?", None, "medium"),
    ("Rozwiąż równanie $x^2-5x+6=0$", None, "easy"),
    ("Kto napisał Pana Tadeusza?", ["Mickiewicz", "Słowacki", "Kochanowski", "Sienkiewicz"], "hard"),
]
for text, opts, diff in cases:
    direct = validate_quadratic_difficulty(text, diff, option_texts=opts)
    via_adapter_no_level = modifier.evaluate(text, opts, diff)  # level domyslnie None
    via_adapter_liceum2 = modifier.evaluate(text, opts, diff, level="liceum_2")  # baseline, shift=0
    check(f"level=None: adapter == validate_quadratic_difficulty ('{text[:35]}...', {diff})", via_adapter_no_level == direct, (via_adapter_no_level, direct))
    check(f"level='liceum_2' (baseline): adapter == validate_quadratic_difficulty ('{text[:35]}...', {diff})", via_adapter_liceum2 == direct, (via_adapter_liceum2, direct))


# ============================================================
# 6. KLUCZOWY TEST: to samo pytanie, rozne poziomy
# ============================================================
print()
print("=== KLUCZOWY TEST: rownanie kwadratowe (tier 5-6) dla roznych poziomow ===")

# Realny przyklad tier 5-6 (parametr + prosty warunek na delte) - uzywany
# przez caly dzien do testowania (test_math_verify.py, test_difficulty_engine.py).
tier_56_question = "Dla jakich wartości parametru $m$ równanie $x^2+(m-3)x+m=0$ ma dwa różne pierwiastki?"
detected = classify_quadratic_difficulty(tier_56_question)
check("kontrola: tresc testowa faktycznie klasyfikuje sie jako tier 5-6", detected == "5-6", detected)

print()
print("  6a) Zadana trojka z zadania (podstawowka_7 / liceum_2 / studia_1), request 'medium':")
print("      (MAX_SHIFT podniesiony z 2 na 4 po feedbacku usera - patrz komentarz w calibration.py -")
print("       pierwsza wersja NIE lapala tej bliskiej roznicy, teraz musi.)")
results_requested_trio = {}
requested_tiers_trio = {}
for lvl in ["podstawowka_7", "liceum_2", "studia_1"]:
    r = modifier.evaluate(tier_56_question, None, "medium", level=lvl)
    results_requested_trio[lvl] = r["status"]
    requested_tiers_trio[lvl] = r.get("requested_tier")
    shift = level_adjusted_tier_shift(lvl)
    print(f"      {lvl:15s} shift={shift:+d}  status={r['status']:5s} requested_tier={r.get('requested_tier')}")

check("podstawowka_7 vs liceum_2: RUZNE shifty (nie 0 dla obu, jak przy MAX_SHIFT=2)",
      level_adjusted_tier_shift("podstawowka_7") != level_adjusted_tier_shift("liceum_2"), results_requested_trio)
check("studia_1 vs liceum_2: RUZNE shifty", level_adjusted_tier_shift("studia_1") != level_adjusted_tier_shift("liceum_2"), results_requested_trio)
check("GLOWNY CEL ETAPU 5 SPELNIONY: to samo pytanie (tier 5-6) dla podstawowka_7/liceum_2/studia_1 -> 3 RUZNE wyniki",
      len(set(results_requested_trio.values())) >= 2 and len(set(requested_tiers_trio.values())) == 3,
      (results_requested_trio, requested_tiers_trio))
check("liceum_2 (baseline) nadal 'ok' - pytanie DOKLADNIE trafia w tier 5-6 = 'medium' tam, gdzie skala byla kalibrowana",
      results_requested_trio["liceum_2"] == "ok", results_requested_trio)
check("podstawowka_7 (mlodszy uczen): to samo pytanie liczy sie jako ZA TRUDNE na 'medium'",
      results_requested_trio["podstawowka_7"] == "fail", results_requested_trio)
check("studia_1 (starszy uczen): to samo pytanie liczy sie jako ZA LATWE na 'medium'",
      results_requested_trio["studia_1"] == "fail", results_requested_trio)

print()
print("  6b) Skrajne poziomy (podstawowka_1 / studia_5) - kontrola braku 'przesadzenia':")
results_wide_trio = {}
for lvl in ["podstawowka_1", "liceum_2", "studia_5"]:
    r = modifier.evaluate(tier_56_question, None, "medium", level=lvl)
    results_wide_trio[lvl] = r
    shift = level_adjusted_tier_shift(lvl)
    print(f"      {lvl:15s} shift={shift:+d}  status={r['status']:5s} requested_tier={r.get('requested_tier')}")
check("podstawowka_1: shift wciaz w rozsadnym zakresie (-2, nie mniej - 5 tierow, nie przekracza skali)",
      level_adjusted_tier_shift("podstawowka_1") == -2, level_adjusted_tier_shift("podstawowka_1"))
check("studia_5: shift wciaz w rozsadnym zakresie (+2, nie wiecej)",
      level_adjusted_tier_shift("studia_5") == 2, level_adjusted_tier_shift("studia_5"))
check("podstawowka_1: requested_tier NIE jest pusty/zdegenerowany (nadal konkretne pasmo, tu '1-2')",
      results_wide_trio["podstawowka_1"]["requested_tier"] == "1-2", results_wide_trio["podstawowka_1"])
check("studia_5: requested_tier NIE jest pusty/zdegenerowany (nadal konkretne pasmo, tu '9-10')",
      results_wide_trio["studia_5"]["requested_tier"] == "9-10", results_wide_trio["studia_5"])
check("podstawowka_1 i studia_5 dalej ROZNE od liceum_2 (mechanizm z Czesci 6 poprzedniego testu nadal dziala)",
      results_wide_trio["podstawowka_1"]["status"] != results_wide_trio["liceum_2"]["status"] and
      results_wide_trio["studia_5"]["status"] != results_wide_trio["liceum_2"]["status"], results_wide_trio)


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
