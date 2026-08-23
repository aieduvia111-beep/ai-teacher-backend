# -*- coding: utf-8 -*-
"""Niezalezna, symboliczna weryfikacja (sympy) kluczy odpowiedzi do zadan
z rownaniami kwadratowymi - patrz uzycie w openai_exam.py (Quiz) i
exam_pdf_generator.py (Sprawdzian).

KONTEKST: audyt tej sesji wykazal, ze AI (nawet z instrukcja "sprawdz
swoje obliczenia przed odpowiedzia" w prompcie) regularnie generuje
BLEDNY klucz odpowiedzi dla rownan kwadratowych z parametrem - typowo
"opcje" nie zawieraja prawdziwej odpowiedzi, albo "correct"/"odpowiedz"
wskazuje na inna opcje niz ta, ktora AI samo poprawnie wyliczylo we
wlasnym wyjasnieniu. Prompt-based samo-weryfikacja (w jednym przebiegu)
tego nie naprawia - generowanie opcji i wybor finalnego indeksu sa w
praktyce czesciowo rozlaczone od faktycznego wyniku obliczen.

Ten modul NIE pyta AI ponownie - liczy PRAWDZIWY wynik przez sympy i
porownuje z tym, co AI zwrocilo. Rozpoznaje:
  1. Rownania kwadratowe z JEDNYM parametrem + warunek na liczbe
     pierwiastkow (delta > 0 / = 0 / < 0 / >= 0) - najczestszy
     zglaszany przypadek ("dla jakich wartosci m rownanie... ma dwa
     rozne pierwiastki").
  2. Zwykle (liczbowe) rownania kwadratowe bez parametru - weryfikacja
     przez bezposrednie rozwiazanie i porownanie z opcjami.

Wzorce spoza tych dwoch (inny przedmiot, bardziej zlozona matematyka,
wiecej niz jeden parametr) sa swiadomie POMIJANE (funkcje zwracaja
None/"unverifiable") - nie zgadujemy, nie fal szywie korygujemy. Prompt-
based samo-weryfikacja zostaje jako jedyne (niepewne) zabezpieczenie dla
tych przypadkow, zgodnie z decyzja uzytkownika.
"""
import re
import sympy as sp
from sympy import Eq, Poly, S, Symbol
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor,
)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

_EQ_IN_DOLLARS = re.compile(r'\$([^$]+)\$')


def _clean_latex(s: str) -> str:
    """Zamienia najczestsze konstrukcje LaTeX na skladnie parsowalna przez sympy."""
    s = s.strip().strip('$').strip()
    s = s.replace('\\left', '').replace('\\right', '')
    s = s.replace('\\cdot', '*').replace('\\times', '*')
    for _ in range(3):
        s = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'((\1)/(\2))', s)
    s = s.replace('\\leq', '<=').replace('\\geq', '>=').replace('\\neq', '!=')
    s = s.replace('{', '(').replace('}', ')')
    return s.strip()


def _parse_expr(s: str):
    return parse_expr(_clean_latex(s), transformations=_TRANSFORMS)


def _parse_relational(s: str):
    """'m < 3' / 'm <= 4' / 'm = 4' -> obiekt Relational sympy. Rozdziela
    RECZNIE na operatorze (nie przez Pythonowe ==, ktore dla sympy
    Symboli NIE tworzy rownania tylko robi strukturalne porownanie)."""
    s = _clean_latex(s)
    for op, builder in (('<=', sp.Le), ('>=', sp.Ge), ('!=', sp.Ne), ('<', sp.Lt), ('>', sp.Gt), ('=', sp.Eq)):
        if op in s:
            lhs_s, rhs_s = s.split(op, 1)
            try:
                lhs = _parse_expr(lhs_s)
                rhs = _parse_expr(rhs_s)
            except Exception:
                return None
            return builder(lhs, rhs)
    return None


def _find_equation_in_text(text: str):
    """Pierwszy fragment $...$ w tekscie wygladajacy na rownanie kwadratowe
    (zawiera 'x', '=' i 'x^2'/'x**2'). Zwraca (lhs_str, rhs_str) albo None."""
    if not text:
        return None
    for m in _EQ_IN_DOLLARS.finditer(text):
        chunk = m.group(1)
        if 'x' not in chunk or '=' not in chunk:
            continue
        if not re.search(r'x\s*\^\s*2|x\s*\*\*\s*2', chunk):
            continue
        parts = chunk.split('=')
        if len(parts) == 2:
            return parts[0], parts[1]
    return None


def analyze_quadratic_question(question_text: str):
    """Rozpoznaje rownanie kwadratowe w tresci pytania. Zwraca dict
    {x, param, A, B, C} (param=None gdy rownanie czysto liczbowe) albo
    None gdy nie rozpoznano (niewspierany wzorzec - abstain)."""
    found = _find_equation_in_text(question_text)
    if not found:
        return None
    lhs_s, rhs_s = found
    try:
        lhs = _parse_expr(lhs_s)
        rhs_s_stripped = rhs_s.strip()
        rhs = sp.Integer(0) if rhs_s_stripped in ('', '0') else _parse_expr(rhs_s)
        expr = sp.expand(lhs - rhs)
    except Exception:
        return None

    free = expr.free_symbols
    x_syms = [s for s in free if str(s) == 'x']
    if not x_syms:
        return None
    x = x_syms[0]
    others = [s for s in free if s != x]
    if len(others) > 1:
        return None  # wiecej niz jeden parametr - zbyt zlozone, abstain
    param = others[0] if others else None

    try:
        poly = Poly(expr, x)
    except Exception:
        return None
    if poly.degree() != 2:
        return None
    A, B, C = poly.all_coeffs()
    return {"x": x, "param": param, "A": A, "B": B, "C": C}


_CONDITION_PATTERNS = [
    (re.compile(r'brak pierwiastk\w+ rzeczywist|nie ma pierwiastk\w+ rzeczywist|nie ma rozwi[aą]zań?\b', re.I), 'neg'),
    (re.compile(
        r'dok[lł]adnie jeden pierwiastek|jeden pierwiastek\s*\(podw[oó]jny\)|podw[oó]jny pierwiastek|'
        r'podw[oó]jne (rozwi[aą]zanie|pierwiastek)|jedno rozwi[aą]zanie|jeden podw[oó]jny pierwiastek|'
        r'dwa r[oó]wne pierwiastki|jedno rozwi[aą]zanie rzeczywiste|dwa takie same pierwiastki|'
        r'dwa jednakowe pierwiastki|dwa identyczne pierwiastki',
        re.I), 'zero'),
    (re.compile(
        r'dwa r[oó][zż]ne pierwiastki rzeczywist|dwa r[oó][zż]ne rozwi[aą]zania rzeczywist|'
        r'dwa r[oó][zż]ne pierwiastki|dwa r[oó][zż]ne rozwi[aą]zania',
        re.I), 'pos'),
    (re.compile(r'dwa pierwiastki rzeczywist|co\s*najmniej jeden pierwiastek|przynajmniej jeden pierwiastek', re.I), 'nonneg'),
]


def detect_discriminant_condition(question_text: str):
    """Zwraca 'pos'/'zero'/'neg'/'nonneg' na podstawie tekstu pytania,
    albo None jesli nie rozpoznano warunku (abstain)."""
    for pattern, kind in _CONDITION_PATTERNS:
        if pattern.search(question_text):
            return kind
    return None


def solve_discriminant_condition(A, B, C, param, kind):
    """Prawdziwy zbior wartosci parametru spelniajacych warunek na delte.
    Zwraca sympy Set albo None (blad/niemozliwe do rozwiazania - abstain)."""
    if param is None:
        return None
    delta = sp.expand(B ** 2 - 4 * A * C)
    try:
        if kind == 'pos':
            base = sp.solveset(delta > 0, param, domain=S.Reals)
        elif kind == 'zero':
            base = sp.solveset(Eq(delta, 0), param, domain=S.Reals)
        elif kind == 'neg':
            base = sp.solveset(delta < 0, param, domain=S.Reals)
        elif kind == 'nonneg':
            base = sp.solveset(delta >= 0, param, domain=S.Reals)
        else:
            return None
    except Exception:
        return None
    # Gdy parametr jest (lub wystepuje w) wspolczynniku wiodacym A -
    # rownanie przestaje byc kwadratowe dla A=0 (degeneruje sie do
    # liniowego albo stalej), wiec te wartosci parametru NIGDY nie
    # naleza do prawdziwego rozwiazania, nawet jesli formalnie spelniaja
    # warunek na delte. Bez tego wykluczenia zbior bylby bledny dla
    # rownan typu "ax^2 + ... = 0" z parametrem jako wspolczynnikiem x^2.
    if param in A.free_symbols:
        try:
            a_zero = sp.solveset(Eq(A, 0), param, domain=S.Reals)
            base = base - a_zero
        except Exception:
            return None
    return base


def _sets_equal(a, b) -> bool:
    try:
        diff1 = a - b
        diff2 = b - a
        e1 = diff1.is_empty
        e2 = diff2.is_empty
        return bool(e1) and bool(e2)
    except Exception:
        return False


def _option_text(opt) -> str:
    return re.sub(r'^[a-dA-D]\)\s*', '', str(opt).strip())


def _split_lub(s: str):
    return [p.strip() for p in re.split(r'\blub\b', s) if p.strip()]


def parse_option_as_param_set(option_text: str, param):
    """'a) $m < 3$' -> sympy Set wzgledem `param`. Obsluguje 'A lub B'
    jako sume zbiorow. None jesli nie da sie sparsowac (abstain dla tej
    opcji, nie blokuje calej weryfikacji)."""
    if param is None:
        return None
    text = _option_text(option_text)
    parts = _split_lub(text)
    if not parts:
        return None
    sets = []
    for p in parts:
        rel = _parse_relational(p)
        if rel is None or param not in rel.free_symbols:
            return None
        try:
            sets.append(sp.solveset(rel, param, domain=S.Reals))
        except Exception:
            return None
    result = sets[0]
    for s2 in sets[1:]:
        result = result.union(s2)
    return result


def verify_param_quadratic_question(question_text: str, options: list):
    """Pelna weryfikacja jednego pytania typu 'rownanie kwadratowe z
    parametrem + warunek na delte'. Zwraca dict:
      {"status": "unverifiable"}                     - nie rozpoznano wzorca
      {"status": "no_match_index", "true_index": i}   - opcja i pasuje do
                                                          prawdziwego wyniku
      {"status": "no_option_matches"}                 - zadna z opcji nie
                                                          jest poprawna
    Nie modyfikuje niczego - tylko liczy i porownuje."""
    parsed = analyze_quadratic_question(question_text)
    if not parsed or parsed["param"] is None:
        return {"status": "unverifiable"}
    kind = detect_discriminant_condition(question_text)
    if kind is None:
        return {"status": "unverifiable"}
    true_set = solve_discriminant_condition(parsed["A"], parsed["B"], parsed["C"], parsed["param"], kind)
    if true_set is None:
        return {"status": "unverifiable"}

    matches = []
    any_option_parsed = False
    for idx, opt in enumerate(options or []):
        opt_set = parse_option_as_param_set(opt, parsed["param"])
        if opt_set is None:
            continue
        any_option_parsed = True
        if _sets_equal(opt_set, true_set):
            matches.append(idx)
    if not any_option_parsed:
        return {"status": "unverifiable"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0], "true_set": true_set}
    if len(matches) > 1:
        # opcje sie pokrywaja (nietypowe/zle sformulowane opcje) - abstain
        return {"status": "unverifiable"}
    return {"status": "no_option_matches", "true_set": true_set}


# ---------------------------------------------------------------
# Rownania kwadratowe BEZ parametru (czysto liczbowe) - rozwiaz i
# porownaj z opcjami postaci "x = 2 i x = 3" / "x = \pm 2" / "x = 2".
# ---------------------------------------------------------------

def _parse_numeric_root_set(option_text: str):
    """'a) $x = 2$ i $x = -3$' / '$x = \\pm 2$' -> zbior liczb (set of
    sympy numbers) albo None jesli nie rozpoznano formatu."""
    text = _option_text(option_text)
    text = text.replace('\\pm', '\\pm ')
    # Rozdziel na fragmenty $...$ (kazdy to jedno "x = ..." lub podobne)
    chunks = _EQ_IN_DOLLARS.findall(text)
    if not chunks:
        chunks = [text]
    values = set()
    for chunk in chunks:
        c = _clean_latex(chunk)
        c = re.sub(r'^x\s*=\s*', '', c.strip())
        if '\\pm' in c or '+-' in c or '\u00b1' in c:
            base = re.sub(r'\\pm|\+-|\u00b1', '', c).strip()
            try:
                val = _parse_expr(base)
            except Exception:
                return None
            values.add(sp.simplify(val))
            values.add(sp.simplify(-val))
            continue
        # "2$ i $x = -3" moze po oczyszczeniu miec resztki "i x" w srodku -
        # rozdziel dodatkowo po polskim "i" pomiedzy liczbami jesli jest
        for sub in re.split(r'\bi\b(?=\s*x\s*=)|,', c):
            sub = re.sub(r'^x\s*=\s*', '', sub.strip()).strip()
            if not sub:
                continue
            try:
                val = _parse_expr(sub)
            except Exception:
                return None
            values.add(sp.simplify(val))
    return values if values else None


def verify_numeric_quadratic_question(question_text: str, options: list):
    """Jak verify_param_quadratic_question, ale dla rownan BEZ parametru -
    rozwiazuje rownanie wprost i porownuje zbior pierwiastkow z opcjami."""
    parsed = analyze_quadratic_question(question_text)
    if not parsed or parsed["param"] is not None:
        return {"status": "unverifiable"}
    x, A, B, C = parsed["x"], parsed["A"], parsed["B"], parsed["C"]
    if A == 0:
        return {"status": "unverifiable"}
    try:
        roots = sp.solveset(Eq(A * x ** 2 + B * x + C, 0), x, domain=S.Complexes)
        true_roots = {sp.simplify(r) for r in roots} if roots.is_FiniteSet else None
    except Exception:
        true_roots = None
    if not true_roots:
        return {"status": "unverifiable"}

    matches = []
    any_option_parsed = False
    for idx, opt in enumerate(options or []):
        opt_roots = _parse_numeric_root_set(opt)
        if opt_roots is None:
            continue
        any_option_parsed = True
        if opt_roots == true_roots:
            matches.append(idx)
    if not any_option_parsed:
        return {"status": "unverifiable"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    if len(matches) > 1:
        return {"status": "unverifiable"}
    return {"status": "no_option_matches"}


_KIND_LABEL = {
    "pos": ("$\\Delta > 0$", "dwa różne pierwiastki rzeczywiste"),
    "zero": ("$\\Delta = 0$", "dokładnie jeden pierwiastek (podwójny)"),
    "neg": ("$\\Delta < 0$", "brak pierwiastków rzeczywistych"),
    "nonneg": ("$\\Delta \\geq 0$", "co najmniej jeden pierwiastek rzeczywisty"),
}


def build_verified_explanation(parsed: dict, kind: str, true_set) -> str:
    """Generuje TEKSTOWO SPOJNE (z poprawiona odpowiedzia) wyjasnienie -
    zamiast zostawiac stara tresc AI, ktora odnosila sie do blednego
    indeksu/wyniku."""
    A, B, C, param = parsed["A"], parsed["B"], parsed["C"], parsed["param"]
    delta = sp.expand(B ** 2 - 4 * A * C)
    cond_latex, cond_desc = _KIND_LABEL.get(kind, ("", ""))
    return (
        f"Wyróżnik: $\\Delta = ({sp.latex(B)})^2 - 4 \\cdot ({sp.latex(A)}) \\cdot ({sp.latex(C)}) "
        f"= {sp.latex(delta)}$. Warunek na {cond_desc}: {cond_latex}. "
        f"Rozwiązując, otrzymujemy: ${sp.latex(param)} \\in {sp.latex(true_set)}$. "
        f"(Odpowiedź zweryfikowana automatycznie.)"
    )


# ---------------------------------------------------------------
# Ciagi arytmetyczne/geometryczne - drugi wzorzec po rownaniach
# kwadratowych, gdzie audyt (na zywym przykladzie: ciag arytmetyczny,
# liceum_2) wykazal DOKLADNIE ten sam blad - AI poprawnie liczy w
# "explanation", ale "correct" wskazuje na inna, nieprawidlowa opcje,
# albo prawdziwej odpowiedzi nie ma wsrod opcji wcale. Obslugujemy 3
# najczestsze, najbardziej rozpoznawalne wzorce pytan (nie kazdy
# mozliwy wariant - zlozone, wieloczesciowe pytania pozostaja
# "unverifiable", tak jak rownania z wiecej niz 1 parametrem).
# ---------------------------------------------------------------
_SUBSCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def _normalize_subscripts(s: str) -> str:
    s = s.translate(_SUBSCRIPT_MAP)
    return re.sub(r'a_(\d)', r'a\1', s)


def _to_num(s: str):
    return sp.nsimplify(s.replace(',', '.'))


_SEQ_TERM_RE = re.compile(r'a_?\{?(\d+)\}?\s*=\s*(-?\d+(?:[.,]\d+)?)')
_SEQ_LAST_TERM_RE = re.compile(r'a_?\{?n\}?\s*=\s*(-?\d+(?:[.,]\d+)?)')
_SEQ_R_RE = re.compile(r'(?<![a-zA-Z])r\s*=\s*(-?\d+(?:[.,]\d+)?)')
_SEQ_Q_RE = re.compile(r'(?<![a-zA-Z])q\s*=\s*(-?\d+(?:[.,]\d+)?)')
_SEQ_SUM_N_RE = re.compile(r'sum[eę]\s+pierwszych\s+(\d+)\s+wyraz')
_SEQ_SUM_VALUE_RE = re.compile(r'suma\s+pierwszych\s+(\d+)\s+wyraz\w*[^.]*?wynosi\s+(-?\d+(?:[.,]\d+)?)')
_SEQ_NTH_ASK_RE = re.compile(r'oblicz\s+(\d+)[-.]?\s*(?:ty|szy|-ty|-szy)?\s*wyraz')


def analyze_sequence_question(question_text: str):
    """Rozpoznaje zadanie o ciagu arytmetycznym/geometrycznym. Zwraca
    dict z rozpoznanymi danymi albo None (nie wyglada na takie
    zadanie/brak rozpoznawalnych danych - abstain)."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text)
    is_arithmetic = 'arytmetyczn' in text.lower()
    is_geometric = 'geometryczn' in text.lower()
    if not is_arithmetic and not is_geometric:
        return None
    kind = "arithmetic" if is_arithmetic else "geometric"

    last_term = None
    m = _SEQ_LAST_TERM_RE.search(text)
    if m:
        last_term = _to_num(m.group(1))

    terms = {}
    for m in _SEQ_TERM_RE.finditer(text):
        terms[int(m.group(1))] = _to_num(m.group(2))

    ratio = None
    m = (_SEQ_R_RE if kind == "arithmetic" else _SEQ_Q_RE).search(text)
    if m:
        ratio = _to_num(m.group(1))

    sum_value = None
    m = _SEQ_SUM_VALUE_RE.search(text)
    if m:
        sum_value = {"n": int(m.group(1)), "value": _to_num(m.group(2))}

    if not terms and last_term is None and sum_value is None:
        return None
    return {"kind": kind, "terms": terms, "ratio": ratio, "last_term": last_term, "sum_value": sum_value}


def detect_sequence_intent(question_text: str):
    """Zwraca dict opisujacy co jest pytaniem, albo None (nierozpoznany
    typ pytania o ciagu - abstain). Kolejnosc sprawdzania ma znaczenie -
    od najbardziej specyficznych wzorcow do najbardziej ogolnych, zeby
    np. "suma...znajdz pierwszy wyraz" nie zostalo zle sklasyfikowane
    jako zwykle "two_term_to_a1_ratio"."""
    text = _normalize_subscripts(question_text).lower()

    m = _SEQ_NTH_ASK_RE.search(text)
    if m and 'suma' not in text:
        return {"intent": "find_nth_term", "n": int(m.group(1))}

    if 'suma' in text and ('pierwszy wyraz' in text or 'wyznacz a1' in text or 'znajd' in text or 'oblicz a1' in text):
        return {"intent": "find_a1_given_sum"}

    m = _SEQ_SUM_N_RE.search(text)
    if m and 'przekracza' not in text and 'najmniejsz' not in text:
        return {"intent": "sum_given_n", "n": int(m.group(1))}

    if ('ile wyraz' in text or ('liczb' in text and 'wyraz' in text)) and 'przekracza' not in text:
        return {"intent": "find_n_from_last_term"}

    if ('pierwszy wyraz' in text or 'wyznacz a1' in text or 'znajd' in text or 'oblicz a1' in text) and (
        'różnic' in text or 'roznic' in text or 'iloraz' in text
    ):
        return {"intent": "two_term_to_a1_ratio"}
    return None


def _option_a1_ratio(option_text: str, kind: str):
    """'a) a1 = 4, r = 3' -> (a1, ratio) albo None (nie sparsowano)."""
    text = _normalize_subscripts(_option_text(option_text))
    m1 = re.search(r'a1\s*=\s*(-?\d+(?:[.,]\d+)?)', text)
    m2 = (_SEQ_R_RE if kind == "arithmetic" else _SEQ_Q_RE).search(text)
    if not m1 or not m2:
        return None
    return (_to_num(m1.group(1)), _to_num(m2.group(1)))


def verify_sequence_question(question_text: str, options: list):
    """Weryfikacja zadan o ciagach arytmetycznych/geometrycznych - ten
    sam kontrakt zwracany co verify_param_quadratic_question."""
    parsed = analyze_sequence_question(question_text)
    if not parsed:
        return {"status": "unverifiable"}
    intent = detect_sequence_intent(question_text)
    if not intent:
        return {"status": "unverifiable"}

    kind = parsed["kind"]
    terms = parsed["terms"]
    ratio = parsed["ratio"]
    a1_sym, r_sym, n_sym = sp.symbols('a1 r n')

    def an_expr(a1, rr, nn):
        return a1 + (nn - 1) * rr if kind == "arithmetic" else a1 * rr ** (nn - 1)

    def sn_expr(a1, rr, nn):
        if kind == "arithmetic":
            return nn * (2 * a1 + (nn - 1) * rr) / 2
        return a1 * (rr ** nn - 1) / (rr - 1)

    def _option_value_after_equals(opt):
        text = _normalize_subscripts(_option_text(opt))
        m = re.search(r'=\s*(-?\d+(?:[.,]\d+)?)\s*$', text)
        if m:
            return _to_num(m.group(1))
        return _parse_expr(text)

    try:
        if intent["intent"] == "find_nth_term":
            if 1 not in terms or ratio is None:
                return {"status": "unverifiable"}
            true_value = sp.nsimplify(an_expr(terms[1], ratio, intent["n"]))
            option_parser = _option_value_after_equals
        elif intent["intent"] == "find_a1_given_sum":
            sv = parsed["sum_value"]
            if ratio is None or sv is None:
                return {"status": "unverifiable"}
            sol = sp.solve(Eq(sn_expr(a1_sym, ratio, sv["n"]), sv["value"]), a1_sym)
            real_sol = [s for s in sol if s.is_real]
            if len(real_sol) != 1:
                return {"status": "unverifiable"}
            true_value = sp.nsimplify(real_sol[0])
            option_parser = _option_value_after_equals
        elif intent["intent"] == "sum_given_n":
            if 1 not in terms or ratio is None:
                return {"status": "unverifiable"}
            true_value = sp.nsimplify(sn_expr(terms[1], ratio, intent["n"]))
            option_parser = lambda opt: _parse_expr(_option_text(opt))
        elif intent["intent"] == "find_n_from_last_term":
            if 1 not in terms or ratio is None or parsed["last_term"] is None:
                return {"status": "unverifiable"}
            sol = sp.solve(Eq(an_expr(terms[1], ratio, n_sym), parsed["last_term"]), n_sym)
            real_sol = [s for s in sol if s.is_real and s > 0]
            if len(real_sol) != 1:
                return {"status": "unverifiable"}
            true_value = sp.nsimplify(real_sol[0])
            option_parser = lambda opt: _parse_expr(_option_text(opt))
        elif intent["intent"] == "two_term_to_a1_ratio":
            idxs = sorted(terms.keys())
            if len(idxs) != 2:
                return {"status": "unverifiable"}
            i, j = idxs
            vi, vj = terms[i], terms[j]
            sol = sp.solve([
                Eq(an_expr(a1_sym, r_sym, i), vi),
                Eq(an_expr(a1_sym, r_sym, j), vj),
            ], [a1_sym, r_sym])
            sols = sol if isinstance(sol, list) else [sol]
            real_sols = []
            for s in sols:
                a1v, rv = (s[a1_sym], s[r_sym]) if isinstance(s, dict) else s
                if a1v.is_real and rv.is_real:
                    real_sols.append((sp.nsimplify(a1v), sp.nsimplify(rv)))
            if len(real_sols) != 1:
                return {"status": "unverifiable"}
            true_value = real_sols[0]
            option_parser = lambda opt: _option_a1_ratio(opt, kind)
        else:
            return {"status": "unverifiable"}
    except Exception:
        return {"status": "unverifiable"}

    matches = []
    any_parsed = False
    for idx, opt in enumerate(options or []):
        try:
            opt_val = option_parser(opt)
        except Exception:
            opt_val = None
        if opt_val is None:
            continue
        any_parsed = True
        if opt_val == true_value:
            matches.append(idx)
    if not any_parsed:
        return {"status": "unverifiable"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    if len(matches) > 1:
        return {"status": "unverifiable"}
    return {"status": "no_option_matches"}


# ---------------------------------------------------------------
# WYMUSZANIE "correct" Z "final_answer" (dowolny przedmiot, nie tylko
# matematyka) - architektura zaproponowana przez usera (konsultacja z
# ChatGPT): zamiast ufac, ze AI samo poprawnie wskaze "correct" (co
# audyt tej sesji wielokrotnie obalil - AI potrafi poprawnie wyliczyc
# wynik w "explanation" i mimo to wskazac inny indeks), AI ma teraz
# dodatkowo zwracac "final_answer" - doslowna kopie tekstu poprawnej
# opcji. Backend NIGDY nie ufa polu "correct" wprost - zawsze
# przelicza je na nowo z dopasowania final_answer do options.
# ---------------------------------------------------------------
_WS_RE = re.compile(r'\s+')
_LEADING_LETTER_RE = re.compile(r'^[a-dA-D][\)\.]\s*')


def _canonical_answer(text: str) -> str:
    """Normalizuje tekst opcji/final_answer do porownania: usuwa prefiks
    'a) '/'b) ', $, biale znaki, wielkosc liter - zeby drobne roznice
    formatowania (spacje, $ wokol wzoru) nie psuly dopasowania miedzy
    final_answer a tekstem opcji, ktore powinny znaczyc to samo."""
    if text is None:
        return ""
    t = str(text).strip()
    t = _LEADING_LETTER_RE.sub('', t)
    t = t.replace('$', '')
    t = _WS_RE.sub('', t)
    return t.lower()


def match_final_answer_index(final_answer, options: list):
    """Rdzen dopasowania (bez modyfikowania niczego) - dopasowuje
    final_answer do listy opcji. Zwraca (status, index_albo_None):
      ("forced", i)          - dopasowano dokladnie jedna opcje o indeksie i
      ("no_final_answer", None) - brak/puste final_answer
      ("no_match", None)     - final_answer nie pasuje do ZADNEJ opcji
      ("ambiguous", None)    - final_answer pasuje do WIECEJ NIZ JEDNEJ opcji
                                (np. zduplikowane opcje) - nie da sie
                                bezpiecznie rozstrzygnac"""
    if not final_answer or not str(final_answer).strip():
        return "no_final_answer", None
    target = _canonical_answer(final_answer)
    if not target:
        return "no_final_answer", None
    matches = [i for i, opt in enumerate(options or []) if _canonical_answer(opt) == target]
    if len(matches) == 1:
        return "forced", matches[0]
    if len(matches) == 0:
        return "no_match", None
    return "ambiguous", None


def force_correct_from_final_answer(question: dict, options_key: str = "options", correct_key: str = "correct"):
    """Dopasowuje question[final_answer_key] do question[options_key] i
    NADPISUJE question[correct_key] indeksem dopasowanej opcji - AI NIGDY
    nie decyduje samo, ktora opcja jest poprawna, ten mechanizm robi to
    zamiast niego. Zwraca status - patrz match_final_answer_index."""
    status, idx = match_final_answer_index(question.get("final_answer"), question.get(options_key))
    if status == "forced":
        question[correct_key] = idx
    return status


def verify_and_fix_math_question(question_text: str, options: list):
    """Glowna funkcja uzywana przez Quiz/Sprawdzian. Probuje najpierw
    wzorca z parametrem, potem czysto liczbowego. Zwraca dict:
      {"status": "unverifiable"}
      {"status": "match_index", "true_index": int, "explanation": str|None}
      {"status": "no_option_matches"}
    "match_index" NIE oznacza, ze AI mial zle - caller sam porownuje
    true_index z aktualnym kluczem AI i decyduje, czy cokolwiek zmienic."""
    result = verify_param_quadratic_question(question_text, options)
    if result["status"] != "unverifiable":
        if result["status"] == "match_index":
            parsed = analyze_quadratic_question(question_text)
            kind = detect_discriminant_condition(question_text)
            expl = None
            if parsed and kind:
                try:
                    expl = build_verified_explanation(parsed, kind, result["true_set"])
                except Exception:
                    expl = None
            return {"status": "match_index", "true_index": result["true_index"], "explanation": expl}
        return {"status": result["status"], "explanation": None}

    result2 = verify_numeric_quadratic_question(question_text, options)
    if result2["status"] == "match_index":
        return {"status": "match_index", "true_index": result2["true_index"], "explanation": None}
    if result2["status"] == "no_option_matches":
        return {"status": "no_option_matches", "explanation": None}

    result3 = verify_sequence_question(question_text, options)
    if result3["status"] in ("match_index", "no_option_matches"):
        return {**result3, "explanation": None}
    return {"status": "unverifiable", "explanation": None}
