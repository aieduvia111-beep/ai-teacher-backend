"""Lokalne testy (zero kosztu API) dla nowego mechanizmu validation_rule
(Warstwa 2 dla zadan tekstowych) w app/math_verify.py.

Uruchomienie: python test_validation_rule.py
"""
import sys

sys.path.insert(0, ".")

from app.math_verify import (
    safe_eval_validation_expression,
    verify_word_problem_validation_rule,
)
from app.math_verify import extract_number_from_answer_text as _extract_number_from_answer_text
from app.openai_exam import _blind_verify_one_closed_quiz
from app.exam_pdf_generator import _blind_verify_one_closed as _blind_verify_one_closed_exam
import asyncio

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


print("=== safe_eval_validation_expression: poprawna matematyka ===")
check("odejmowanie", safe_eval_validation_expression("a - b", {"a": 50, "b": 18}) == 32)
check("mnozenie", safe_eval_validation_expression("predkosc * czas", {"predkosc": 90, "czas": 2}) == 180)
check("nawiasy i kolejnosc", safe_eval_validation_expression("(a + b) * c", {"a": 2, "b": 3, "c": 4}) == 20)
check("dzielenie", safe_eval_validation_expression("a / b", {"a": 10, "b": 4}) == 2.5)
check("potega", safe_eval_validation_expression("a ** 2", {"a": 5}) == 25)
check("unary minus", safe_eval_validation_expression("-a + b", {"a": 3, "b": 10}) == 7)
check("stale liczbowe bez zmiennych", safe_eval_validation_expression("100 - 37", {}) == 63)
check("modulo", safe_eval_validation_expression("a % b", {"a": 10, "b": 3}) == 1)

def rejects(expr, variables=None):
    try:
        safe_eval_validation_expression(expr, variables or {})
        return False
    except ValueError:
        return True


print("=== safe_eval_validation_expression: geometria (sqrt, pi) ===")
check("pole kola (pi * r**2)", abs(safe_eval_validation_expression("pi * r**2", {"r": 3}) - 28.274333882308138) < 1e-9)
check("obwod kola (2*pi*r)", abs(safe_eval_validation_expression("2*pi*r", {"r": 5}) - 31.41592653589793) < 1e-9)
check("tw. Pitagorasa (przeciwprostokatna)", safe_eval_validation_expression("sqrt(a**2 + b**2)", {"a": 3, "b": 4}) == 5.0)
check("sqrt z wyrazenia zlozonego", abs(safe_eval_validation_expression("sqrt(pole / pi)", {"pole": 78.53981633974483}) - 5.0) < 1e-6)

print("=== safe_eval_validation_expression: proby obejscia bialej listy funkcji ===")
check("inna funkcja (abs) nadal odrzucona", rejects("abs(-5)"))
check("inna funkcja (sin) nadal odrzucona", rejects("sin(0)"))
check("sqrt z 2 argumentami odrzucony", rejects("sqrt(4, 9)"))
check("sqrt z keyword argumentem odrzucony", rejects("sqrt(x=4)", {"x": 4}))
check("sqrt zagniezdzony w innej niedozwolonej funkcji", rejects("eval(sqrt(4))"))
check("sqrt z liczby ujemnej odrzucony (poza dziedzina)", rejects("sqrt(-1)"))
check("pi jako nazwa zmiennej NADPISUJE stala (variables ma pierwszenstwo)",
      safe_eval_validation_expression("pi", {"pi": 3}) == 3.0)

print("=== safe_eval_validation_expression: proby wstrzykniecia / atak ===")

check("wywolanie funkcji __import__", rejects("__import__('os').system('dir')"))
check("wywolanie open()", rejects("open('c:/windows/win.ini').read()"))
check("wywolanie dowolnej funkcji", rejects("abs(-5)"))
check("dostep do atrybutu", rejects("a.__class__", {"a": 1}))
check("subskrypcja/indeksowanie", rejects("a[0]", {"a": 1}))
check("string literal", rejects("'rm -rf /'"))
check("lambda", rejects("(lambda: 1)()"))
check("list comprehension", rejects("[x for x in range(10)]"))
check("porownanie (nieobslugiwane)", rejects("a == b", {"a": 1, "b": 1}))
check("nieznana zmienna", rejects("x + 1", {}))
check("zmienna nie-liczbowa", rejects("a + 1", {"a": "tekst"}))
check("dzielenie przez zero", rejects("a / b", {"a": 1, "b": 0}))
check("puste wyrazenie", rejects(""))
check("za dlugie wyrazenie", rejects("1" + "+1" * 200))
check("zla skladnia", rejects("a + * b", {"a": 1, "b": 1}))

print("=== verify_word_problem_validation_rule: pelny przeplyw (trojstanowy wynik) ===")

ok, reason = verify_word_problem_validation_rule(
    {"variables": {"cena": 50, "rabat": 18}, "expression": "cena - rabat", "expected": 32},
    claimed_answer=32,
)
check("poprawne zadanie -> True", ok is True)

ok, reason = verify_word_problem_validation_rule(
    {"variables": {"cena": 50, "rabat": 18}, "expression": "cena - rabat", "expected": 32},
    claimed_answer=99,
)
check("niezgodnosc claimed_answer vs expected -> False (potwierdzony blad)", ok is False)

ok, reason = verify_word_problem_validation_rule(
    {"variables": {"cena": 50, "rabat": 18}, "expression": "cena - rabat", "expected": 99},
    claimed_answer=99,
)
check("niezgodnosc expression vs expected (zle przepisany wzor) -> False", ok is False)

ok, reason = verify_word_problem_validation_rule(
    {"variables": {"a": 1}, "expression": "a.__class__", "expected": 1},
    claimed_answer=1,
)
check("zlosliwy expression -> None (nierozstrzygalne, nie wyjatek)", ok is None)

ok, reason = verify_word_problem_validation_rule({}, claimed_answer=1)
check("pusty validation_rule -> None", ok is None)

ok, reason = verify_word_problem_validation_rule(None, claimed_answer=1)
check("None jako validation_rule -> None", ok is None)

ok, reason = verify_word_problem_validation_rule(
    {"variables": {"predkosc": 90, "czas": 2}, "expression": "predkosc * czas", "expected": 180},
    claimed_answer="180",
)
check("claimed_answer jako string liczbowy -> True", ok is True)

ok, reason = verify_word_problem_validation_rule(
    {"variables": {"a": 10}, "expression": "a / 0", "expected": 5},
    claimed_answer=5,
)
check("dzielenie przez zero w expression -> None (nierozstrzygalne)", ok is None)

ok, reason = verify_word_problem_validation_rule(
    {"variables": {"a": 100, "b": 3}, "expression": "a / b", "expected": 33.33},
    claimed_answer=33.33,
)
check("tolerancja dla liczb niecalkowitych -> True", ok is True)

ok, reason = verify_word_problem_validation_rule(
    {"variables": {"a": 100, "b": 3}, "expression": "a / b", "expected": "nie liczba"},
    claimed_answer=33.33,
)
check("nieliczbowe 'expected' -> None (nierozstrzygalne, nie wyjatek)", ok is None)

print("=== _extract_number_from_answer_text ===")
check("prosta liczba", _extract_number_from_answer_text("32") == 32.0)
check("z jednostka", _extract_number_from_answer_text("32 zl") == 32.0)
check("z LaTeX", _extract_number_from_answer_text("$32$") == 32.0)
check("przecinek dziesietny", _extract_number_from_answer_text("12,5 km") == 12.5)
check("ujemna", _extract_number_from_answer_text("-7") == -7.0)
check("warunek symboliczny -> None (dwie liczby)", _extract_number_from_answer_text("$m < -8$ lub $m > 8$") is None)
check("brak liczby -> None", _extract_number_from_answer_text("brak rozwiazania") is None)
check("nietekst -> None", _extract_number_from_answer_text(None) is None)

print("=== _blind_verify_one_closed_quiz: wpiecie validation_rule (bez wywolania AI) ===")


async def _run_blind_verify_tests():
    q_pass = {
        "question": "Bilet kosztowal 50 zl, rabat 18 zl. Ile zaplacono?",
        "options": ["30 zl", "32 zl", "35 zl", "40 zl"],
        "correct": 1,
        "final_answer": "32 zl",
        "validation_rule": {"variables": {"cena": 50, "rabat": 18}, "expression": "cena - rabat", "expected": 32},
    }
    ok = await _blind_verify_one_closed_quiz(q_pass, client="SENTINEL_SHOULD_NOT_BE_CALLED")
    check("poprawny validation_rule -> True BEZ wywolania AI-2", ok is True)

    q_fail = dict(q_pass)
    q_fail["final_answer"] = "99 zl"
    q_fail["options"] = ["30 zl", "32 zl", "35 zl", "99 zl"]
    q_fail["correct"] = 3
    ok = await _blind_verify_one_closed_quiz(q_fail, client="SENTINEL_SHOULD_NOT_BE_CALLED")
    check("bledny validation_rule (potwierdzona niezgodnosc) -> False BEZ wywolania AI-2", ok is False)

    q_no_rule = {
        "question": "Dla jakich m rownanie ma dwa pierwiastki?",
        "options": ["a", "b", "c", "d"],
        "correct": 0,
        "final_answer": "$m < -8$ lub $m > 8$",
    }
    # client=None -> istniejace zachowanie (brak AI-2 w ogole -> zawsze True), sprawdzamy ze
    # brak validation_rule NIE psuje dotychczasowej sciezki
    ok = await _blind_verify_one_closed_quiz(q_no_rule, client=None)
    check("brak validation_rule, client=None -> True (zachowanie bez zmian)", ok is True)


asyncio.run(_run_blind_verify_tests())

print("=== _blind_verify_one_closed (Sprawdzian, synchroniczny): wpiecie validation_rule ===")


class _SentinelClient:
    class chat:
        class completions:
            @staticmethod
            def create(*a, **kw):
                raise AssertionError("AI-2 NIE powinno byc wywolane - validation_rule mialo rozstrzygnac")


pyt_pass = {
    "tresc": "Bilet kosztowal 50 zl, rabat 18 zl. Ile zaplacono?",
    "opcje": ["a) 30 zl", "b) 32 zl", "c) 35 zl", "d) 40 zl"],
    "odpowiedz": "b",
    "final_answer": "32 zl",
    "validation_rule": {"variables": {"cena": 50, "rabat": 18}, "expression": "cena - rabat", "expected": 32},
}
check("Exam: poprawny validation_rule -> True BEZ wywolania AI-2", _blind_verify_one_closed_exam(_SentinelClient, pyt_pass) is True)

pyt_fail = dict(pyt_pass)
pyt_fail["final_answer"] = "99 zl"
check("Exam: bledny validation_rule -> False BEZ wywolania AI-2", _blind_verify_one_closed_exam(_SentinelClient, pyt_fail) is False)

print(f"\n=== WYNIK: {passed} OK, {failed} FAIL ===")
sys.exit(1 if failed else 0)
