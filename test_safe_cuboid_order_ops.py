# -*- coding: utf-8 -*-
"""Offline (zero AI): generatory prostopadloscianu i kolejnosci dzialan - poprawnosc liczona NIEZALEZNIE
od generatora (wzory z kluczy faktow / sympy), unikalnosc opcji i pytan, pelna liczba pytan w partii."""
import os, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

import math, random
import sympy as sp
import app.math_verify as mv

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:400]))

def num(s): return int(re.match(r"-?\d+", str(s)).group(0))

# ---------- PROSTOPADLOSCIAN: niezalezne przeliczenie z klucza faktow ----------
def true_from_key(k):
    kind = k[0]
    if kind == "volume": _, a, b, c = k; return a * b * c
    if kind == "surface": _, a, b, c = k; return 2 * (a*b + b*c + c*a)
    if kind == "edges_sum": _, a, b, c = k; return 4 * (a + b + c)
    if kind == "diagonal": _, dims, d = k; return math.isqrt(sum(x*x for x in dims))
    if kind == "missing_edge": _, a, b, c = k; return c
    if kind == "base_diagonal": _, a, b, h, d = k; return math.isqrt(a*a + b*b)
    if kind == "cube_from_edges": _, a = k; return a ** 3
    if kind == "cube_surface_from_volume": _, a = k; return 6 * a * a
    if kind == "ratio_edges": _, p, q, r, kk = k; return kk**3 * p*q*r
    if kind == "cubes_fit": _, e, na, nb, nc = k; return na*nb*nc
    raise ValueError(kind)

random.seed(1234)
bad, kinds = [], set()
for _ in range(4000):
    q = mv.build_safe_cuboid_question()
    k = q.pop("_fact_key"); kinds.add(k[0])
    t = true_from_key(k)
    opts = q["options"]
    ok = (num(q["final_answer"]) == t and len(opts) == 4 and len(set(opts)) == 4
          and opts[q["correct"]] == q["final_answer"] and all(num(o) > 0 for o in opts))
    if k[0] == "diagonal":
        ok = ok and sum(x*x for x in k[1]) == k[2]**2
    if not ok: bad.append((k, q["final_answer"], opts))
check("cuboid: 4000 pytan - poprawna odpowiedz == niezalezne przeliczenie, 4 unikalne dodatnie opcje", not bad, bad[:2])
check("cuboid: wystepuje wszystkie 10 typow zadan", len(kinds) == 10, kinds)

for n in (5, 10, 15, 20):
    b = mv.generate_safe_cuboid_batch(n)
    check(f"cuboid: partia n={n} ma DOKLADNIE {n} unikalnych pytan", len(b) == n and len({x['question'] for x in b}) == n, len(b))

# ---------- KOLEJNOSC DZIALAN: sympy jako niezalezny sedzia ----------
def sympy_val(expr):
    s = expr.replace("×", "*").replace("÷", "/").replace("−", "-")
    s = re.sub(r"(\d+)²", r"(\1**2)", s)
    s = re.sub(r"\)²", r")**2", s)
    return sp.nsimplify(sp.sympify(s))

bad = []
for _ in range(4000):
    q = mv.build_safe_order_ops_question()
    expr = q.pop("_fact_key")
    v = sympy_val(expr)
    opts = q["options"]
    ok = (v.is_integer and int(v) == int(q["final_answer"]) and len(opts) == 4 and len(set(opts)) == 4
          and opts[q["correct"]] == q["final_answer"] and q["question"].endswith(expr))
    if not ok: bad.append((expr, q["final_answer"], v, opts))
check("kolejnosc dzialan: 4000 pytan - wynik == sympy, 4 unikalne opcje, pytanie zawiera wyrazenie", not bad, bad[:2])

for n in (5, 10, 15, 20):
    b = mv.generate_safe_order_ops_batch(n)
    check(f"kolejnosc dzialan: partia n={n} ma DOKLADNIE {n} unikalnych wyrazen", len(b) == n and len({x['question'] for x in b}) == n, len(b))

q = mv.build_safe_order_ops_question(); q.pop("_fact_key")
check("wyjasnienie jest niepuste i tekstowe", isinstance(q["explanation"], str) and len(q["explanation"]) > 10)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
