# -*- coding: utf-8 -*-
"""User: "idziemy dalej rob to dobrze prosze" - piate rozszerzenie Safe
Parameter Generation tego samego dnia (po trygonometrii x2, ciagach
arytmetycznych/geometrycznych, twierdzeniu cosinusow). Temat: rownanie
z wartoscia bezwzgledna, poziom trudny.

SWIADOMA REDUKCJA ZAKRESU (ujawniona userowi w kodzie i w rozmowie):
oficjalny "trudny" przyklad programowy to $|2x-3|+|x+1|\\le 6$
(nierownosc, DWIE wartosci bezwzgledne, 3 przedzialy) - zbyt zlozone do
niezawodnego zbudowania w tym samym dniu. Zbudowano zamiast tego
rownanie $|x+b|=cx+d$ (JEDNA wartosc bezwzgledna) - ten sam rdzen
umiejetnosci (rozbicie na przypadki + odrzucenie pierwiastka pozornego),
prostszy przypadek brzegowy.

Ten plik testuje SAMA logike (zero AI, zero kosztu): poprawnosc
(niezalezna sciezka - sympy solveset z Abs, nie reimplementacja case-
analysis), brak kolizji miedzy 4 opcjami, gating w obu miejscach."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import build_safe_abs_value_equation, verify_abs_value_equation

print("=" * 70)
print("Przyklad + poprawnosc na 500 losowych probach (niezalezna sciezka -")
print("sympy solveset z Abs, sprawdza ZBIOR rozwiazan = {x1} dokladnie)")
print("=" * 70)
none_count = 0
bad = []
for _ in range(500):
    sk = build_safe_abs_value_equation()
    if sk is None:
        none_count += 1
        continue
    if not verify_abs_value_equation(sk["b"], sk["c"], sk["d"], sk["x1"], sk["correct_text"]):
        bad.append(sk)
check("build_safe_abs_value_equation nigdy nie zwraca None (max_tries=100 wystarcza)",
      none_count == 0, none_count)
check(f"{500 - len(bad)}/500 poprawne (jedyne, jednoznaczne rozwiazanie potwierdzone przez sympy)",
      not bad, bad[:2] if bad else None)

print()
print("=" * 70)
print("Dystraktory - zero kolizji na 500 probach (w tym pierwiastek pozorny x2)")
print("=" * 70)
collision = []
for _ in range(500):
    sk = build_safe_abs_value_equation()
    all_texts = [sk["correct_text"]] + sk["distractors"]
    if sk["correct_text"] in sk["distractors"] or len(set(all_texts)) != 4:
        collision.append(sk)
check("500 prob - zero kolizji miedzy 4 opcjami", not collision, collision[:2] if collision else None)

print()
print("=" * 70)
print("Real przyklad (recznie zweryfikowany, wzor niezalezny od losowania):")
print("b=8, c=-2, x1=3 -> d = x1*(1-c)+b = 3*3+8 = 17 -> |x+8|=-2x+17 -> x=3,")
print("pierwiastek pozorny (odrzucony) x=25 - to ON jest jednym z dystraktorow")
print("=" * 70)
import sympy as sp
b_ex, c_ex, x1_ex = 8, -2, 3
d_ex = x1_ex * (1 - c_ex) + b_ex
check("d = x1*(1-c)+b wg wzoru z build_safe_abs_value_equation daje d=17",
      d_ex == 17, d_ex)
check("Formula odtwarza real przyklad: sympy solveset({|x+8|=-2x+17}) == {3}",
      verify_abs_value_equation(b_ex, c_ex, d_ex, x1_ex, "x = 3"))
x_sym = sp.Symbol('x', real=True)
sols_ex = sp.solveset(sp.Eq(sp.Abs(x_sym + b_ex), c_ex * x_sym + d_ex), x_sym, domain=sp.S.Reals)
check("Rownolegle: bezposredni sympy solveset na |x+8|=-2x+17 daje dokladnie {3} (x=25 odrzucone jako pierwiastek pozorny)",
      sols_ex == sp.FiniteSet(3), sols_ex)

print()
print("=" * 70)
print("Gating: _is_hard_abs_value (Quiz) - samo 'bezwzgledn(a)' + trudny")
print("=" * 70)
from app.openai_exam import _is_hard_abs_value
check("'wartość bezwzględna' + trudny -> True",
      _is_hard_abs_value("Matematyka: wartość bezwzględna", "trudny") is True)
check("'wartosc bezwzgledna' (bez diakrytykow) + trudny -> True",
      _is_hard_abs_value("wartosc bezwzgledna", "trudny") is True)
check("'wartość bezwzględna' + srednia -> False",
      _is_hard_abs_value("wartość bezwzględna", "srednia") is False)
check("inny temat + trudny -> False",
      _is_hard_abs_value("Rownania kwadratowe", "trudny") is False)

print()
print("=" * 70)
print("Gating: _is_hard_abs_value_exam (Sprawdzian) - identyczna logika")
print("=" * 70)
from app.exam_pdf_generator import _is_hard_abs_value_exam
check("'wartość bezwzględna' + trudna -> True",
      _is_hard_abs_value_exam("Matematyka: wartość bezwzględna", "trudna") is True)
check("inny temat + trudna -> False",
      _is_hard_abs_value_exam("Prawdopodobienstwo", "trudna") is False)

print()
print("=" * 70)
print("Warstwa 2/2.5 EXEMPTION - dziedziczona automatycznie z 'safe_generated'")
print("=" * 70)
import asyncio
from app.openai_exam import _verify_and_fix_quiz_math

fake_safe_q = {
    "question": "Rozwiąż równanie |x+8|=-2x+17.",
    "options": ["x = 3", "x = 25", "x = -3", "x = 25/3"],
    "correct": 0, "final_answer": "x = 3", "explanation": "test",
    "diversity_tag": {"skill": "s", "concept": "c", "task_type": "t", "reasoning": "r"},
    "_safe_generated": True,
}
result = asyncio.run(_verify_and_fix_quiz_math({"questions": [dict(fake_safe_q)]}))
check("Pytanie _safe_generated (archetyp wartosci bezwzglednej) -> zaakceptowane bez blind-check",
      len(result.get("questions", [])) == 1, result)

print()
print("=" * 70)
print("Regresja sanitize_latex_json_backslashes: falszywy pozytyw \\u bez 4")
print("cyfr hex po nim (real-test tego archetypu, sierpien 2026 -")
print("'Invalid \\uXXXX escape' psulo caly regen mimo sanitizera)")
print("=" * 70)
import json as _json_check
from app.openai_exam import sanitize_latex_json_backslashes

raw_bad_u = r'{"a": "tekst z \upharpoonright dziwna komenda"}'
fixed = sanitize_latex_json_backslashes(raw_bad_u)
try:
    parsed = _json_check.loads(fixed)
    check("'\\upharpoonright' (nie jest prawdziwym \\uXXXX) - sanitizer naprawia, json.loads() nie rzuca",
          True)
except Exception as e:
    check("'\\upharpoonright' (nie jest prawdziwym \\uXXXX) - sanitizer naprawia, json.loads() nie rzuca",
          False, str(e))

raw_good_u = '{"a": "znak ' + chr(92) + 'u00f3 unicode"}'  # dosłowne ó (backslash+u+4 hex)
fixed2 = sanitize_latex_json_backslashes(raw_good_u)
parsed2 = _json_check.loads(fixed2)
check("Prawdziwy \\u00f3 (4 cyfry hex) - NADAL dziala jako poprawny unicode escape (bez regresji)",
      parsed2["a"] == "znak ó unicode", parsed2)

print()
print("=" * 70)
print("Regresja _fix_latex (Sprawdzian): '\\ge'/'\\le' (poprawny LaTeX, ale")
print("NIEZNANY dla matplotlib mathtext - real-test PDF zglosil")
print("ParseFatalException) -> normalizowane do '\\geq'/'\\leq'; '\\left'/")
print("'\\right'/juz-poprawne '\\geq'/'\\leq' NIE zmieniane (regresja)")
print("=" * 70)
from app.exam_pdf_generator import _fix_latex

check("'$x \\ge -8$' -> '$x \\geq -8$'",
      _fix_latex(r"$x \ge -8$") == r"$x \geq -8$", _fix_latex(r"$x \ge -8$"))
check("'$x \\le 5$' -> '$x \\leq 5$'",
      _fix_latex(r"$x \le 5$") == r"$x \leq 5$", _fix_latex(r"$x \le 5$"))
check("Juz-poprawne '\\geq'/'\\leq' NIE sa zmieniane (brak podwojenia q)",
      _fix_latex(r"$x \geq -8$ i $x \leq 5$") == r"$x \geq -8$ i $x \leq 5$",
      _fix_latex(r"$x \geq -8$ i $x \leq 5$"))
check("'\\left(' i '\\right)' NIE sa dotykane (regresja - lookahead na litere po le/ge)",
      _fix_latex(r"\left(x\right)") == r"\left(x\right)", _fix_latex(r"\left(x\right)"))

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
