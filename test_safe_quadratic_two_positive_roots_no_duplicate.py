"""Lokalny test (zero kosztu) - naprawa duplikacji w archetypie 'dwa
dodatnie pierwiastki' (build_safe_quadratic_two_positive_roots).

User zauwazyl real przypadek w wygenerowanym PDF: Zadanie 1 i Zadanie 6
byly IDENTYCZNE ($x^2-(param+10)x+10\\cdot param=0$), rozna TYLKO litera
parametru (b vs c) - DOKLADNIE ten sam bug, ktory byl juz raz znaleziony
i naprawiony dla _raw_generate_safe_linear_param_quadratic_batch (patrz
komentarz tam), ale nigdy nie dostal tej samej poprawki tutaj - funkcja
losowala k_value/param_letter CALKOWICIE NIEZALEZNIE (random.choice bez
sledzenia), wiec kolizja stalej K byla mozliwa nawet W OBREBIE JEDNEJ
partii."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import asyncio

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import pick_safe_param_values

print("=" * 70)
print("pick_safe_param_values: k_pool (1..10) bez powtorzen dla n<=10")
print("=" * 70)
used = set()
picks = pick_safe_param_values(list(range(1, 11)), used, 8)
check("8 wybranych wartosci wszystkie unikalne", len(set(picks)) == 8, picks)
check("wszystkie wartosci w puli 1..10", all(1 <= v <= 10 for v in picks), picks)

print()
print("=" * 70)
print("Sprawdzian (exam_pdf_generator.py): _raw_generate_safe_quadratic_two_positive_roots_batch")
print("z used_letters/used_constants -> ZERO powtorzonych k_value w jednej partii")
print("=" * 70)
import app.exam_pdf_generator as epg

gen = epg.ExamGenerator(openai_api_key="fake-key-not-used-in-this-test")


class _FakeCompletions:
    @staticmethod
    def create(*a, **kw):
        # Buduje odpowiedz AI zawierajaca dokladnie tyle "pytan" ile
        # promptem poproszono (parsowanie liczy sie po numeracji w
        # promptcie - mockujemy najprostszy poprawny JSON z N elementami).
        import re
        prompt = kw["messages"][1]["content"]
        n = len(re.findall(r'^\d+\. Rownanie:', prompt, re.MULTILINE))
        questions = [
            {"nr": i + 1, "tresc": f"Q{i}", "wyjasnienie": "bo tak", "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"}}
            for i in range(n)
        ]
        import json as _json

        class _Msg:
            content = _json.dumps({"sekcje": [{"typ": "zamkniete", "pytania": questions}]})

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()


class _FakeChat:
    completions = _FakeCompletions()


gen.client = type("C", (), {"chat": _FakeChat()})()

used_letters = set()
used_constants = set()
result = gen._raw_generate_safe_quadratic_two_positive_roots_batch(8, used_letters=used_letters, used_constants=used_constants)
questions = result.get("sekcje", [{}])[0].get("pytania", [])
k_values_used = sorted(used_constants)
check("8 zadan zwrocone (buffer n+3=11 wygenerowane, 8 potrzebne)", len(questions) >= 8, len(questions))
check("used_constants zawiera 8 UNIKALNYCH wartosci k (brak duplikatu jak Zadanie1/6)",
      len(used_constants) == len(set(used_constants)) and len(used_constants) >= 8, used_constants)

print()
print("=" * 70)
print("Quiz (openai_exam.py): _raw_generate_safe_quadratic_two_positive_roots_batch")
print("z used_letters/used_constants -> ZERO powtorzonych k_value")
print("=" * 70)
import app.openai_exam as oai


class _FakeQuizCompletions:
    @staticmethod
    async def create(*a, **kw):
        import re, json as _json
        prompt = kw["messages"][0]["content"]
        n = len(re.findall(r'^\d+\. Rownanie:', prompt, re.MULTILINE))
        questions = [
            {"id": i + 1, "question": f"Q{i}", "explanation": "bo tak",
             "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"}}
            for i in range(n)
        ]

        class _Msg:
            content = _json.dumps({"title": "T", "questions": questions})

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()


class _FakeQuizChat:
    completions = _FakeQuizCompletions()


_real_oai_client = oai.client
oai.client = type("C", (), {"chat": _FakeQuizChat()})()


async def _run_quiz():
    used_letters2 = set()
    used_constants2 = set()
    return await oai._raw_generate_safe_quadratic_two_positive_roots_batch(8, used_letters=used_letters2, used_constants=used_constants2), used_constants2


result2, used_constants2 = asyncio.run(_run_quiz())
oai.client = _real_oai_client
check("Quiz: used_constants zawiera >=8 unikalnych wartosci k",
      len(used_constants2) == len(set(used_constants2)) and len(used_constants2) >= 8, used_constants2)

print()
print("=" * 70)
print("Regresja: bez used_letters/used_constants (None) -> stare zachowanie, bez crasha")
print("=" * 70)
result3 = gen._raw_generate_safe_quadratic_two_positive_roots_batch(3)
check("Dziala tez bez podania used_letters/used_constants (fallback random)",
      isinstance(result3, dict) and result3.get("sekcje"), result3)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
