# -*- coding: utf-8 -*-
"""Offline (zero AI): generatory ogolnej matematyki liceum/technikum - poprawnosc sprawdzana NIEZALEZNYM
sedzia: dane odczytywane z TRESCI pytania i przeliczane sympy / symulacja petla (nie z kluczy generatora)."""
import os, sys, io, re, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)
import sympy as sp
import app.math_verify as mv

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:500]))

SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
x = sp.Symbol("x")

def ex(s):
    """tekst wyrazenia -> sympy"""
    s = s.translate(SUB).replace("−", "-").replace("·", "*").replace("÷", "/").replace("²", "**2").replace("^", "**").replace("°", "*pi/180")
    s = re.sub(r"√(\d+)", r"sqrt(\1)", s).replace("√(", "sqrt(")
    s = re.sub(r"\btg\b", "tan", s)
    s = re.sub(r"(sin|cos|tan)\*\*2\s+(\d+\*pi/180)", r"(\1(\2))**2", s)
    s = re.sub(r"(sin|cos|tan)\s+(\d+\*pi/180)", r"\1(\2)", s)
    s = re.sub(r"(?<=\d)(sqrt)", r"*\1", s)
    s = re.sub(r"(\d)x", r"\1*x", s).replace("−x", "-x")
    return sp.sympify(s, locals={"x": x})

def nums(s): return [int(n) for n in re.findall(r"-?\d+", s.translate(SUB).replace("−", "-"))]

def same(a, b):
    try:
        return sp.simplify(ex(a) - ex(b)) == 0
    except Exception:
        return False

def line_fn(text):
    """'y = 3x − 2' -> funkcja sympy w x"""
    return ex(text.split("=", 1)[1].strip())

def oracle(q):
    t, ans = q["question"], q["final_answer"]
    T = t.translate(SUB).replace("−", "-")
    # ---- potegi/pierwiastki/logarytmy/trygonometria: "Oblicz ...: WYRAZENIE."
    if t.startswith("Oblicz wartość wyrażenia:") or t.startswith("Oblicz wartość:"):
        e = t.split(":", 1)[1].strip().rstrip(".")
        m_ = re.match(r"log_(\d+) \((.+)\)$", e.translate(SUB).replace("−", "-"))
        if m_:   # logarytm z argumentem w nawiasie, np. log_10 ((10^2)^3)
            return abs(float(sp.N(sp.log(ex(m_.group(2)), int(m_.group(1))))) - float(ans)) < 1e-9
        e = re.sub(r"log_(\d+) (\d+)", r"log(\2, \1)", e.translate(SUB).replace("−", "-"))
        v = sp.simplify(ex(e)) if "log(" not in e else sp.simplify(sp.expand_log(ex(e), force=True))
        if "log(" in e:
            v = sp.nsimplify(sp.N(ex(e), 30), rational=True)
        return same(str(v), ans.replace("/", "/")) or abs(float(sp.N(v)) - float(sp.N(ex(ans)))) < 1e-9
    if t.startswith("Oblicz log_"):
        b, n = re.findall(r"log_(\d+) (\d+)", t)[0]
        return int(ans) == round(sp.log(int(n), int(b)).evalf())
    if t.startswith("Wyznacz x, jeżeli log_"):
        b, k = nums(t)[:2]
        return int(ans) == b ** k
    if t.startswith("Zapisz liczbę √"):
        n = nums(t)[0]
        a_, b_ = re.match(r"(\d+)√(\d+)", ans).groups()
        return sp.sqrt(n) - int(a_) * sp.sqrt(int(b_)) == 0
    # ---- geometria analityczna
    if t.startswith("Oblicz odległość punktów"):
        x1, y1, x2, y2 = nums(T)[:4]
        return sp.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) == int(ans)
    if t.startswith("Wyznacz współrzędne środka odcinka"):
        x1, y1, x2, y2 = nums(T)[:4]
        return nums(ans) == [sp.Rational(x1 + x2, 2), sp.Rational(y1 + y2, 2)]
    if t.startswith("Wskaż równanie prostej przechodzącej przez punkty"):
        x1, y1, x2, y2 = nums(T)[:4]
        g = line_fn(ans)
        return g.subs(x, x1) == y1 and g.subs(x, x2) == y2
    # ---- funkcja liniowa
    if "współczynnik kierunkowy tej funkcji" in T:
        x1, y1, x2, y2 = nums(T)[:4]
        return sp.Rational(y2 - y1, x2 - x1) == int(ans)
    if t.startswith("Wyznacz miejsce zerowe"):
        f = ex(t.split("f(x) =")[1].strip().rstrip("."))
        return sp.solve(f, x) == [int(ans)]
    if t.startswith("Funkcja liniowa jest określona wzorem"):
        f = ex(t.split("f(x) =")[1].split(". Oblicz")[0].strip())
        at = nums(T.split("Oblicz f(")[1])[0]
        return f.subs(x, at) == int(ans)
    if t.startswith("Prosta przechodzi przez punkty"):
        x1, y1, x2, y2 = nums(T)[:4]
        g = line_fn(ans)
        return g.subs(x, x1) == y1 and g.subs(x, x2) == y2
    if "o współczynniku kierunkowym" in T:
        a_, x0, y0 = nums(T)[:3]
        g = line_fn(ans)
        return sp.diff(g, x) == a_ and g.subs(x, x0) == y0
    if t.startswith("Prosta k ma równanie"):
        k = line_fn(t.split("równanie", 1)[1].split(". Wskaż")[0])
        x0, y0 = nums(T.split("punkt")[1])[:2]
        g = line_fn(ans)
        return sp.diff(g, x) == sp.diff(k, x) and g.subs(x, x0) == y0 and sp.simplify(g - k) != 0
    # ---- funkcja kwadratowa
    if t.startswith("Rozwiąż równanie"):
        p = ex(t.split("równanie", 1)[1].split("= 0")[0])
        roots = sorted(sp.solve(p, x))
        got = sorted(nums(ans))
        return roots == got
    if t.startswith("Oblicz wyróżnik"):
        p = sp.Poly(ex(t.split("f(x) =")[1].strip().rstrip(".")), x)
        a_, b_, c_ = p.coeff_monomial(x**2), p.coeff_monomial(x), p.coeff_monomial(1)
        return b_ ** 2 - 4 * a_ * c_ == int(ans)
    if t.startswith("Wyznacz współrzędne wierzchołka"):
        f = ex(t.split("f(x) =")[1].strip().rstrip("."))
        p = sp.Poly(f, x)
        xv = -p.coeff_monomial(x) / (2 * p.coeff_monomial(x**2))
        return [xv, f.subs(x, xv)] == nums(ans)
    if "x₁ + x₂" in t or "x₁ · x₂" in t:
        p = ex(t.split("Równanie", 1)[1].split("= 0")[0])
        r = sp.solve(p, x)
        return (sum(r) if "x₁ + x₂" in t else r[0] * r[1]) == int(ans)
    if t.startswith("Funkcja kwadratowa jest określona wzorem"):
        f = ex(t.split("f(x) =")[1].split(". Oblicz")[0].strip())
        at = nums(T.split("Oblicz f(")[1])[0]
        return f.subs(x, at) == int(ans)
    # ---- ciagi (symulacja petla)
    if t.startswith("Ciąg arytmetyczny ma pierwszy wyraz"):
        _v = nums(T.split("Oblicz")[0]); a1, r, n = _v[1], _v[2], nums(T.split("Oblicz a")[1])[0]   # _v[0] = indeks "1" z "a1"
        v = a1
        for _ in range(n - 1): v += r
        return v == int(ans)
    if t.startswith("W ciągu arytmetycznym a"):
        m, am, n, an = nums(T.split("Oblicz")[0])[:4]
        cand = [r for r in range(-20, 21) if am + (n - m) * r == an]
        return cand == [int(ans)]
    if "Oblicz sumę" in t and t.startswith("Ciąg arytmetyczny"):
        _v = nums(T.split("Oblicz")[0]); a1, r = _v[1], _v[2]; n = nums(T.split("Oblicz sumę")[1])[0]
        v, s = a1, 0
        for _ in range(n): s += v; v += r
        return s == int(ans)
    if t.startswith("Ciąg geometryczny ma pierwszy wyraz"):
        _v = nums(T.split("Oblicz")[0]); b1, q_ = _v[1], _v[2]; n = nums(T.split("Oblicz b")[1])[0]
        v = b1
        for _ in range(n - 1): v *= q_
        return v == int(ans)
    if t.startswith("W ciągu geometrycznym b"):
        m, bm, n, bn = nums(T.split("Oblicz")[0])[:4]
        cand = [q_ for q_ in range(1, 30) if bm * q_ ** (n - m) == bn]
        return cand == [int(ans)]
    if "Oblicz sumę" in t and t.startswith("Ciąg geometryczny"):
        _v = nums(T.split("Oblicz")[0]); b1, q_ = _v[1], _v[2]; n = nums(T.split("Oblicz sumę")[1])[0]
        v, s = b1, 0
        for _ in range(n): s += v; v *= q_
        return s == int(ans)
    if "Który wyraz" in t:
        _v = nums(T.split("Który")[0]); a1, r = _v[1], _v[2]; target = nums(T.split("równy")[1])[0]
        v, i = a1, 1
        while v < target: v += r; i += 1
        return v == target and i == int(ans)
    return None  # nierozpoznane - test zglosi

random.seed(20260920)
levels = ["liceum_1", "technikum_1", "liceum_2", "technikum_2", "technikum_3", "matura_podstawowa"]
bad, unknown, total = [], [], 0
for lv in levels:
    for _ in range(120):
        for q in mv.generate_safe_hs_math_batch(10, lv):
            total += 1
            try:
                ok = oracle(q)
            except Exception as e:
                ok = False; q = dict(q, _err=repr(e))
            opts = q["options"]
            struct = (len(opts) == 4 and len(set(opts)) == 4 and opts[q["correct"]] == q["final_answer"])
            if ok is None: unknown.append(q["question"])
            elif not (ok and struct): bad.append((lv, q["question"], q["final_answer"], opts, q.get("_err")))
check(f"{total} pytan: odpowiedz zgodna z NIEZALEZNYM sedzia, 4 unikalne opcje, poprawna na wskazanym miejscu", not bad, bad[:3])
check("kazde pytanie zostalo rozpoznane przez sedziego (zero 'nierozpoznanych')", not unknown, unknown[:3])

for lv in levels:
    for n in (5, 10, 20):
        b = mv.generate_safe_hs_math_batch(n, lv)
        check(f"{lv} n={n}: dokladnie {n} unikalnych pytan", len(b) == n and len({q['question'] for q in b}) == n, len(b))

from app.level_config import validate_generic_topic
for lv in levels:
    okc = sum(1 for _ in range(40) if validate_generic_topic({"title": mv.hs_math_title(lv), "questions": mv.generate_safe_hs_math_batch(10, lv)}, lv, "matematyka"))
    check(f"{lv}: mieszanka zgodna z zakresem poziomu (walidacja \"samo wybiera\") 40/40", okc == 40, okc)
check("poziomy nieobslugiwane -> puste (dispatch nie wlaczy generatora)", mv.generate_safe_hs_math_batch(10, "podstawowka_6") == [] and not mv.hs_math_level_supported("podstawowka_6"))
kinds = {q["diversity_tag"]["skill"] for lv in levels for q in mv.generate_safe_hs_math_batch(30, lv)}
check("wystepuja rozne dzialy: potegi, funkcja liniowa/kwadratowa, logarytmy, ciagi, trygonometria", len(kinds) >= 6, kinds)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
