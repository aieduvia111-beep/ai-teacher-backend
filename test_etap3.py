"""
Test regresyjny ETAPU 3 (kontynuacja Universal Difficulty Engine):
1. Adaptacyjny oversampling (_buffered_count / _buffered_question_count).
2. Deduplikacja (_question_fingerprint + integracja w
   _verify_and_fix_quiz_math / _verify_and_fix_exam_math).

Uruchom: python test_etap3.py

Zgodnie z priorytetami usera (jakosc > oszczednosc, ale madrze): to sa
CZYSTO deterministyczne, lokalne mechanizmy (matematyka + normalizacja
tekstu) - testowane tu jednostkowo, BEZ wywolan AI, bo unit test daje
TAKA SAMA pewnosc jak realna generacja dla samej LOGIKI. Osobny,
krotki test z realna generacja (nie w tym pliku) potwierdza integracje
z prawdziwym pipeline'em end-to-end.
"""
import sys
sys.path.insert(0, ".")

from app.openai_exam import _buffered_count, _question_fingerprint as _q_fp_quiz, _verify_and_fix_quiz_math
from app.exam_pdf_generator import _buffered_question_count, _question_fingerprint as _q_fp_exam, _verify_and_fix_exam_math

FAILED = []


def check(name, condition, detail=""):
    if condition:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


# ============================================================
# 1. Adaptacyjny oversampling - Quiz (_buffered_count)
# ============================================================
print("=== Adaptacyjny oversampling: Quiz (_buffered_count) ===")

r = _buffered_count(20, topic="Równania kwadratowe", difficulty="hard")
check("hard + rownania kwadratowe (parametr) -> +60% (20+12=32)", r == 32, r)

# NAPRAWIONE (audyt realnej generacji V1, sierpien 2026 - problem N!=N):
# medium+parametr (goly, po naprawie klasyfikacji) nadal ma podwyzszony
# rejection rate (sympy_mismatch, normalna zmiennosc AI) - podniesiono
# bufor z +30% do +50% (patrz komentarz w _buffered_count). Zaktualizowano
# wartosc oczekiwana - to CELOWA, swiadoma zmiana, nie regresja.
r = _buffered_count(20, topic="Równania kwadratowe", difficulty="medium")
check("medium + rownania kwadratowe -> podniesiony bufor +50% (20+10=30)", r == 30, r)

r = _buffered_count(20, topic="Trygonometria", difficulty="hard")
check("hard + INNY temat (nie kwadratowe) -> dotychczasowe +30% (26)", r == 26, r)

r = _buffered_count(20)
check("brak topic/difficulty (np. sciezka z obrazka) -> domyslne +30% (26)", r == 26, r)

r = _buffered_count(2, topic="Równania kwadratowe", difficulty="trudny")
check("male n (2), hard+kwadratowe -> nadal min +2 respektowane (2+2=4, bo ceil(2*0.6)=2)", r == 4, r)

r_easy = _buffered_count(10, topic="Równania kwadratowe", difficulty="easy")
check("easy + rownania kwadratowe -> dotychczasowe +30% (10+3=13, easy NIE jest w _HARD_DIFFICULTY_WORDS)", r_easy == 13, r_easy)


# ============================================================
# 2. Adaptacyjny oversampling - Sprawdzian (_buffered_question_count)
# ============================================================
print()
print("=== Adaptacyjny oversampling: Sprawdzian (_buffered_question_count) ===")

r = _buffered_question_count(10, temat="Matematyka: Równania kwadratowe", trudnosc="trudna")
check("trudna + rownania kwadratowe (z prefiksem przedmiotu) -> +60% (10+6=16)", r == 16, r)

r = _buffered_question_count(10, temat="Matematyka: Równania kwadratowe", trudnosc="srednia")
check("srednia + rownania kwadratowe -> dotychczasowe +30% (10+3=13)", r == 13, r)

r = _buffered_question_count(10, temat="Fizyka: Dynamika", trudnosc="trudna")
check("trudna + INNY temat -> dotychczasowe +30% (13)", r == 13, r)

r = _buffered_question_count(10)
check("brak temat/trudnosc -> domyslne +30% (13)", r == 13, r)


# ============================================================
# 3. Fingerprint - normalizacja i wykrywanie duplikatow
# ============================================================
print()
print("=== _question_fingerprint: normalizacja ===")

q1 = "Dla jakich wartości parametru $a$ równanie $x^2+(a-2)x+a=0$ ma dwa różne pierwiastki?"
q2 = "Dla jakich wartości parametru $a$ równanie $x^2+(a-2)x+a=0$ ma dwa różne pierwiastki?"  # identyczne
q3 = "Dla jakich wartości parametru $b$ równanie $x^2+(b-3)x+b=0$ ma dwa różne pierwiastki?"  # inny parametr I inne liczby
q4 = "  Dla JAKICH wartości  parametru $a$ równanie $x^2+(a-2)x+a=0$ ma dwa różne pierwiastki?  "  # ta sama tresc, inne biale znaki/wielkosc liter

for fp_fn, label in [(_q_fp_quiz, "Quiz"), (_q_fp_exam, "Sprawdzian")]:
    check(f"[{label}] identyczne pytania -> identyczny fingerprint", fp_fn(q1) == fp_fn(q2), (fp_fn(q1), fp_fn(q2)))
    check(f"[{label}] rozny parametr I rozne liczby -> INNY fingerprint (legalna roznica)", fp_fn(q1) != fp_fn(q3), (fp_fn(q1), fp_fn(q3)))
    check(f"[{label}] roznica TYLKO w bialych znakach/wielkosci liter -> identyczny fingerprint", fp_fn(q1) == fp_fn(q4), (fp_fn(q1), fp_fn(q4)))

# Ten sam szkielet, ale RÓŻNE liczby -> NIE duplikat (legalna wersja tego samego typu zadania)
q5 = "Rozwiąż równanie $x^2 - 5x + 6 = 0$"
q6 = "Rozwiąż równanie $x^2 - 7x + 12 = 0$"
check("ten sam szkielet, inne liczby -> NIE duplikat", _q_fp_quiz(q5) != _q_fp_quiz(q6), (_q_fp_quiz(q5), _q_fp_quiz(q6)))


# ============================================================
# 4. Integracja dedup w _verify_and_fix_quiz_math (Quiz)
# ============================================================
print()
print("=== Integracja: _verify_and_fix_quiz_math usuwa duplikaty ===")
# UWAGA: uzywamy tresci NIE-matematycznej (Warstwa 2 zwraca "unverifiable"
# i przepuszcza bez zmian), zeby izolowac test WYLACZNIE do warstwy
# dedup - poprawnosc matematyczna Warstwy 1/2 jest juz osobno pokryta w
# test_math_verify.py. final_answer dokladnie odpowiada jednej opcji,
# zeby Warstwa 1 tez przepuscila bez interwencji.
lit1 = "Kto napisał powieść 'Lalka'?"
lit1_dup = "Kto napisał powieść 'Lalka'?"
lit2 = "Kto napisał powieść 'Quo Vadis'?"
opts_lit = ["Bolesław Prus", "Henryk Sienkiewicz", "Adam Mickiewicz", "Juliusz Słowacki"]

def _make_q(text, correct_option):
    return {"question": text, "options": list(opts_lit), "correct": opts_lit.index(correct_option), "final_answer": correct_option}

seen = set()
result = _verify_and_fix_quiz_math(
    {"questions": [_make_q(lit1, "Bolesław Prus"), _make_q(lit1_dup, "Bolesław Prus"), _make_q(lit2, "Henryk Sienkiewicz")]},
    seen_fingerprints=seen,
)
kept_texts = [q["question"] for q in result["questions"]]
check("dedup: z 3 pytan (1 duplikat) zostaja 2 unikalne", len(result["questions"]) == 2, kept_texts)
check("dedup: pierwsze wystapienie zachowane, duplikat usuniety", kept_texts == [lit1, lit2], kept_texts)

# Bez seen_fingerprints (domyslne None) - brak regresji, duplikaty NIE usuwane
result_no_dedup = _verify_and_fix_quiz_math({"questions": [_make_q(lit1, "Bolesław Prus"), _make_q(lit1_dup, "Bolesław Prus")]})
check("bez seen_fingerprints (None) -> dedup wylaczony, brak regresji", len(result_no_dedup["questions"]) == 2, result_no_dedup["questions"])


# ============================================================
# 5. Integracja dedup w _verify_and_fix_exam_math (Sprawdzian)
# ============================================================
print()
print("=== Integracja: _verify_and_fix_exam_math usuwa duplikaty ===")

def _make_pyt(text, correct_letter_option):
    letters = ["a", "b", "c", "d"]
    idx = opts_lit.index(correct_letter_option)
    return {"tresc": text, "opcje": [f"{letters[i]}) {o}" for i, o in enumerate(opts_lit)],
            "odpowiedz": letters[idx], "final_answer": correct_letter_option}

seen_exam = set()
exam_data = {
    "sekcje": [{
        "typ": "zamkniete",
        "pytania": [
            _make_pyt(lit1, "Bolesław Prus"),
            _make_pyt(lit1_dup, "Bolesław Prus"),  # duplikat
            _make_pyt(lit2, "Henryk Sienkiewicz"),
        ],
    }]
}
result_exam = _verify_and_fix_exam_math(exam_data, seen_fingerprints=seen_exam)
kept_exam_texts = [p["tresc"] for p in result_exam["sekcje"][0]["pytania"]]
check("dedup (Sprawdzian): z 3 zadan (1 duplikat) zostaja 2 unikalne", len(kept_exam_texts) == 2, kept_exam_texts)
check("dedup (Sprawdzian): pierwsze wystapienie zachowane, duplikat usuniety", kept_exam_texts == [lit1, lit2], kept_exam_texts)


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
