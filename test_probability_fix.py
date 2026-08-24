# -*- coding: utf-8 -*-
"""NAPRAWA KRYTYCZNEGO BLEDU (zgloszony przez usera): zadania o
prawdopodobienstwie mialy ZERO pokrycia Warstwy 2 - AI popelnilo blad
arytmetyczny (P(oba tego samego koloru), 5 bialych + 3 czarne, losowanie
2 bez zwracania: prawdziwy wynik 13/28, AI podalo 10/28), a jego WLASNE
final_answer bylo z tym bledem spojne, wiec Warstwa 1 (tekstowe
dopasowanie) "poprawnie" wymusila bledna opcje - Warstwa 2 nie miala jak
tego zawetowac.

Ten plik testuje NOWY, OGOLNY (nie hardcoded dla urny) weryfikator
Warstwy 2 dla rozkladu hipergeometrycznego: analyze_hypergeometric_
probability_question / verify_hypergeometric_probability_question, plus
pelny przeplyw AI output -> Warstwa 1 -> Warstwa 2 -> PASS/FAIL.

Plain script (bez pytest), wzorem test_etap6.py/test_etap7.py/test_etap8.py."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from app.math_verify import (
    analyze_hypergeometric_probability_question,
    verify_hypergeometric_probability_question,
    verify_and_fix_math_question,
    force_correct_from_final_answer,
)

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


# =================================================================
# 1. REGRESJA: DOKLADNY zgloszony przypadek (5 bialych + 3 czarne)
# =================================================================
print("=" * 70)
print("1. REGRESJA: zgloszony przypadek (5 białych + 3 czarne, k=2)")
print("=" * 70)

Q_URN = (
    "W urnie znajduje się 5 kul białych i 3 czarne. Losujemy bez zwracania "
    "dwie kule. Oblicz prawdopodobieństwo, że obie są tego samego koloru."
)

parsed = analyze_hypergeometric_probability_question(Q_URN)
check("rozpoznaje n1=5, n2=3, k=2, same_category",
      parsed == {"n1": 5, "n2": 3, "k": 2, "event": {"kind": "same_category"}}, parsed)

r = verify_hypergeometric_probability_question(Q_URN, ["10/28", "9/28", "1/2", "3/14"])
check("ODRZUCA 10/28 (prawdziwa odpowiedź 13/28 nie jest wśród opcji) -> no_option_matches",
      r["status"] == "no_option_matches", r)

r = verify_hypergeometric_probability_question(Q_URN, ["13/28", "9/28", "1/2", "3/14"])
check("AKCEPTUJE 13/28 -> match_index=0", r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_hypergeometric_probability_question(Q_URN, ["26/56", "9/28", "1/2", "3/14"])
check("26/56 uznane za RÓWNOWAŻNE 13/28 (matematycznie, nie tekstowo) -> match_index=0",
      r["status"] == "match_index" and r["true_index"] == 0, r)

r = verify_hypergeometric_probability_question(Q_URN, ["9/28", "13/28", "1/2", "3/14"])
check("13/28 na INNEJ pozycji (index 1) -> match_index=1", r["status"] == "match_index" and r["true_index"] == 1, r)

print()

# =================================================================
# 2. PELNY PRZEPLYW: AI output -> Warstwa 1 -> Warstwa 2 -> PASS/FAIL
# =================================================================
print("=" * 70)
print("2. Pelny przeplyw: symulacja dokladnie tego, co robi")
print("   _verify_and_fix_quiz_math (openai_exam.py:1206-1229)")
print("=" * 70)


def simulate_pipeline(question_dict):
    """Ta sama logika co openai_exam.py: Warstwa 1 (force_correct_from_
    final_answer), potem Warstwa 2 (verify_and_fix_math_question).
    Zwraca ('kept'|'rejected'|'corrected', question_dict)."""
    fa_status = force_correct_from_final_answer(question_dict)
    if fa_status in ("no_match", "ambiguous", "no_final_answer"):
        return "rejected_warstwa1", question_dict
    text = question_dict["question"]
    options = question_dict.get("options", [])
    result = verify_and_fix_math_question(text, options)
    if result["status"] == "unverifiable":
        return "kept_unverified", question_dict
    if result["status"] == "no_option_matches":
        return "rejected_warstwa2", question_dict
    if result["status"] == "match_index":
        true_idx = result["true_index"]
        if question_dict.get("correct") != true_idx:
            question_dict["correct"] = true_idx
            return "corrected", question_dict
        return "kept_confirmed", question_dict
    return "kept_unverified", question_dict


# Scenariusz A: DOKLADNIE zgloszony bug (AI samo-spojnie bledne, opcje
# BEZ prawdziwej odpowiedzi) - PRZED naprawa system by to zaakceptowal
# z correct=0 ("10/28"). PO naprawie: odrzucone.
q_bug = {
    "question": Q_URN,
    "options": ["10/28", "9/28", "1/2", "3/14"],
    "correct": 2,
    "final_answer": "10/28",
}
outcome, q_after = simulate_pipeline(q_bug)
check("Scenariusz A (zgloszony bug, bledne opcje) -> ODRZUCONE w Warstwie 2",
      outcome == "rejected_warstwa2", (outcome, q_after))

# Scenariusz B: AI generuje TE SAME liczby, ale tym razem prawidlowe
# opcje (13/28 obecne) i final_answer POPRAWNIE wskazuje 13/28 - system
# ma to zaakceptowac bez zadnej korekty.
q_correct = {
    "question": Q_URN,
    "options": ["13/28", "9/28", "1/2", "3/14"],
    "correct": 0,
    "final_answer": "13/28",
}
outcome, q_after = simulate_pipeline(q_correct)
check("Scenariusz B (poprawne dane) -> ZAAKCEPTOWANE bez zmian",
      outcome == "kept_confirmed" and q_after["correct"] == 0, (outcome, q_after))

# Scenariusz C: final_answer AI bledny (10/28), ale opcje ZAWIERAJA
# poprawna odpowiedz (13/28) na innej pozycji - Warstwa 2 ma to
# SKORYGOWAC (nie tylko odrzucic).
q_fixable = {
    "question": Q_URN,
    "options": ["10/28", "13/28", "1/2", "3/14"],
    "correct": 0,
    "final_answer": "10/28",
}
outcome, q_after = simulate_pipeline(q_fixable)
check("Scenariusz C (final_answer bledny, ale 13/28 wsrod opcji) -> SKORYGOWANE na index 1",
      outcome == "corrected" and q_after["correct"] == 1, (outcome, q_after))

print()

# =================================================================
# 3. INNE LICZBY - potwierdzenie ze mechanizm jest OGOLNY, nie
#    hardcoded dla "5 bialych + 3 czarne"
# =================================================================
print("=" * 70)
print("3. Inne liczby/kategorie/zdarzenia (dowod ogolnosci mechanizmu)")
print("=" * 70)

# 4 czerwone + 6 niebieskich, k=2, ten sam kolor -> 7/15
q2 = "W pudełku jest 4 kule czerwone i 6 niebieskich. Losujemy bez zwracania 2 kule. Jakie jest prawdopodobieństwo, że obie są tego samego koloru?"
r = verify_hypergeometric_probability_question(q2, ["7/15", "1/3", "8/15", "2/5"])
check("4 czerwone + 6 niebieskich, k=2, ten sam kolor -> 7/15", r["status"] == "match_index" and r["true_index"] == 0, r)

# 5 bialych + 3 czarne, k=3, dokladnie 2 biale -> 15/28
q3 = "W urnie jest 5 kul białych i 3 kule czarne. Losujemy bez zwracania trzy kule. Oblicz prawdopodobieństwo, że dokładnie 2 są białe."
parsed3 = analyze_hypergeometric_probability_question(q3)
check("rozpoznaje event 'dokladnie 2 biale' (which=1, j=2)",
      parsed3 is not None and parsed3["event"] == {"kind": "exactly", "which": 1, "j": 2}, parsed3)
r = verify_hypergeometric_probability_question(q3, ["15/28", "10/28", "3/28", "1/2"])
check("5 białych + 3 czarne, k=3, dokładnie 2 białe -> 15/28", r["status"] == "match_index" and r["true_index"] == 0, r)

# 5 bialych + 3 czarne, k=2, rozne kolory -> 15/28
q4 = "W urnie znajduje się 5 kul białych i 3 czarne. Losujemy bez zwracania dwie kule. Oblicz prawdopodobieństwo, że wylosowane kule są różnych kolorów."
r = verify_hypergeometric_probability_question(q4, ["15/28", "13/28", "1/2", "3/14"])
check("5 białych + 3 czarne, k=2, różne kolory -> 15/28", r["status"] == "match_index" and r["true_index"] == 0, r)

# 10 wadliwych + 40 sprawnych (NIE kolory - dowod ze etykiety kategorii
# sa dowolne, nie tylko "biale/czarne"), k=3, tego samego rodzaju -> 25/49
q5 = "W partii towaru jest 10 elementów wadliwych i 40 sprawnych. Losujemy bez zwracania trzy elementy. Oblicz prawdopodobieństwo, że wszystkie są tego samego rodzaju."
r = verify_hypergeometric_probability_question(q5, ["25/49", "1/2", "9/49", "3/49"])
check("10 wadliwych + 40 sprawnych, k=3, ten sam rodzaj -> 25/49 (DOWOD: dowolne etykiety, nie tylko kolory)",
      r["status"] == "match_index" and r["true_index"] == 0, r)

# Losowanie okreslone slownie ("dwie" zamiast "2")
q6 = "W koszyku jest 6 jabłek zielonych i 4 czerwone. Losujemy bez zwracania dwie sztuki. Jakie jest prawdopodobieństwo, że obie są tego samego koloru?"
parsed6 = analyze_hypergeometric_probability_question(q6)
check("rozpoznaje 'dwie' (slowna liczba losowan) jako k=2", parsed6 is not None and parsed6["k"] == 2, parsed6)

print()

# =================================================================
# 4. ABSTAIN dla nierozpoznanych/poza-zakresem przypadkow
# =================================================================
print("=" * 70)
print("4. Abstain (unverifiable) - poza zakresem")
print("=" * 70)

t = analyze_hypergeometric_probability_question("Kto napisał Pana Tadeusza?")
check("tresc niematematyczna -> None", t is None, t)

q_with_replacement = "W urnie jest 5 kul białych i 3 czarne. Losujemy ZE ZWRACANIEM dwie kule. Oblicz prawdopodobieństwo, że obie są tego samego koloru."
t = analyze_hypergeometric_probability_question(q_with_replacement)
check("losowanie ZE ZWRACANIEM (inny rozklad - dwumianowy) -> None (poza zakresem)", t is None, t)

q_no_event = "W urnie jest 5 kul białych i 3 czarne. Losujemy bez zwracania dwie kule."
t = analyze_hypergeometric_probability_question(q_no_event)
check("brak rozpoznawalnego zdarzenia (same/different/exactly) -> None", t is None, t)

r = verify_hypergeometric_probability_question("Rozwiąż równanie x²-5x+6=0.", ["2", "3", "1", "6"])
check("inny temat (rownanie kwadratowe) -> unverifiable", r["status"] == "unverifiable", r)

print()

print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
