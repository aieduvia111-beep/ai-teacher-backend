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
    Symboli NIE tworzy rownania tylko robi strukturalne porownanie).
    UWAGA: nie obsluguje podwojnych nierownosci ('0 < m < 2') - do tego
    sluzy _parse_relational_list, ktory NAJPIERW probuje to rozpoznac
    zanim tu w ogole trafi (patrz komentarz w _parse_relational_list -
    zwykle wywolanie tej funkcji na fragmencie z DWOMA operatorami
    powodowalo TypeError w sympy, bo Python 'a op b op c' parsuje 'b op c'
    jako zagniezdzony Relational, ktory potem probowano porownac jako
    zwykly Expr)."""
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


_COMPOUND_INEQ_RE = re.compile(r'^(.+?)(<=|>=|<|>)([a-zA-Z]\w*)(<=|>=|<|>)(.+)$')
_DIRECT_OP = {'<': sp.Lt, '<=': sp.Le, '>': sp.Gt, '>=': sp.Ge}
_FLIPPED_OP = {'<': sp.Gt, '<=': sp.Ge, '>': sp.Lt, '>=': sp.Le}


def _parse_relational_list(s: str):
    """Jak _parse_relational, ale ROZPOZNAJE podwojne nierownosci typu
    '0 < m < 2' / '-1 <= m <= 5' PRZED probą zwyklego parsowania -
    zwraca liste Relational do przeciecia (AND). Zwykle 1-elementowa
    lista, 2-elementowa dla podwojnej nierownosci. None jesli nie
    rozpoznano w ogole."""
    cleaned = _clean_latex(s)
    m = _COMPOUND_INEQ_RE.match(cleaned.replace(' ', ''))
    if m:
        lower_s, op1, var_s, op2, upper_s = m.groups()
        try:
            lower = _parse_expr(lower_s)
            upper = _parse_expr(upper_s)
            var = _parse_expr(var_s)
        except Exception:
            return None
        try:
            rel1 = _FLIPPED_OP[op1](var, lower)   # "0 < m"  -> m > 0
            rel2 = _DIRECT_OP[op2](var, upper)    # "m < 2"  -> m < 2
        except Exception:
            return None
        return [rel1, rel2]
    rel = _parse_relational(s)
    return [rel] if rel is not None else None


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


def analyze_quadratic_question(question_text: str, option_texts=None):
    """Rozpoznaje rownanie kwadratowe w tresci pytania. Zwraca dict
    {x, param, A, B, C} (param=None gdy rownanie czysto liczbowe) albo
    None gdy nie rozpoznano (niewspierany wzorzec - abstain).

    Jesli w tresci pytania nie ma rownania (np. "Ktore z ponizszych
    rownan..." - rownania sa w opcjach odpowiedzi, nie w tresci),
    a przekazano `option_texts`, szuka rownania w PIERWSZEJ pasujacej
    opcji zamiast od razu abstain-owac."""
    found = _find_equation_in_text(question_text)
    if not found and option_texts:
        for opt in option_texts:
            found = _find_equation_in_text(_option_text(opt))
            if found:
                break
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


# ---------------------------------------------------------------
# ITERACJA 2: skala trudnosci 1-10 dla rownan kwadratowych -
# walidacja PO wygenerowaniu, PRZED pokazaniem userowi (osobna od
# weryfikacji poprawnosci klucza odpowiedzi powyzej). Klasyfikuje
# wygenerowane pytanie w jedno z 5 pasm (patrz level_config.py
# QUADRATIC_DIFFICULTY_TIERS) na podstawie rozpoznawalnych cech tekstu,
# porownuje z pasmem oczekiwanym dla zadanej trudnosci (easy/medium/
# hard - Quiz; latwy/latwa/sredni/srednia/trudny/trudna - Sprawdzian).
# Dziala TYLKO dla rownan kwadratowych (uzywa analyze_quadratic_question
# do wykrycia) - inne tematy zwracaja "not_quadratic" i nie sa dotkniete.
# ---------------------------------------------------------------
_CASE_ANALYSIS_MARKERS = (
    "rozważ osobno", "rozwaz osobno", "osobno przypadek", "w zależności od przypadku",
    "w zaleznosci od przypadku", "udowodnij", "wykaż", "wykaz twierdzenie",
)
_SIGN_ANALYSIS_MARKERS = (
    "przeciwnych znak", "tego samego znak", "pierwiastki dodatnie", "pierwiastki ujemne",
    "iloczyn pierwiastk", "suma pierwiastk", "mniejszy od", "większy od", "wiekszy od",
)

_QUADRATIC_ACCEPTABLE_TIERS = {
    "easy": {"1-2", "3-4"}, "latwy": {"1-2", "3-4"}, "łatwy": {"1-2", "3-4"}, "latwa": {"1-2", "3-4"}, "łatwa": {"1-2", "3-4"},
    "medium": {"5-6"}, "sredni": {"5-6"}, "średni": {"5-6"}, "srednia": {"5-6"}, "średnia": {"5-6"},
    "hard": {"7-8", "9-10"}, "trudny": {"7-8", "9-10"}, "trudna": {"7-8", "9-10"},
}


def classify_quadratic_difficulty(question_text: str, option_texts=None):
    """Szacuje pasmo trudnosci ('1-2'/'3-4'/'5-6'/'7-8'/'9-10')
    wygenerowanego pytania o rownaniu kwadratowym. None jesli tekst nie
    zawiera rozpoznawalnego rownania kwadratowego (walidacja nie ma
    zastosowania - nie blokujemy). `option_texts` pozwala znalezc
    rownanie tez wtedy, gdy jest tylko w opcjach (patrz
    analyze_quadratic_question)."""
    parsed = analyze_quadratic_question(question_text, option_texts=option_texts)
    if not parsed:
        return None
    text_lower = (question_text or "").lower()

    if any(marker in text_lower for marker in _CASE_ANALYSIS_MARKERS):
        return "9-10"

    param, A = parsed["param"], parsed["A"]

    if param is None:
        # Bez parametru: "ladny" rozklad na czynniki (calkowite
        # pierwiastki) = bezposrednie podstawienie (1-2), inaczej
        # standardowy wzor na delte (3-4).
        try:
            x = parsed["x"]
            roots = sp.solve(Eq(A * x ** 2 + parsed["B"] * x + parsed["C"], 0), x)
            nice = bool(roots) and all(r.is_Integer for r in roots)
        except Exception:
            nice = False
        return "1-2" if nice else "3-4"

    # Z parametrem.
    if param in A.free_symbols:
        return "7-8"  # parametr jako wspolczynnik wiodacy - zawsze zlozony przypadek
    if any(marker in text_lower for marker in _SIGN_ANALYSIS_MARKERS):
        return "7-8"  # warunek na znak/sume/iloczyn pierwiastkow (Viete)
    if detect_discriminant_condition(question_text) is not None:
        return "5-6"  # prosty warunek na delte
    return "7-8"  # parametr + nierozpoznany warunek - ostroznie w gore, nie w dol


def validate_quadratic_difficulty(question_text: str, requested_difficulty_word: str, option_texts=None):
    """Sprawdza, czy wygenerowane pytanie o rownaniu kwadratowym
    odpowiada ZADANEJ trudnosci (nie tylko czy jest matematycznie
    poprawne - to osobna weryfikacja powyzej). `option_texts` (opcjonalne)
    pozwala wykryc rownanie tez wtedy, gdy jest podane w opcjach
    odpowiedzi zamiast w tresci pytania (np. "Ktore z ponizszych rownan
    ma dwa rozne pierwiastki?"). Zwraca dict:
      {"status": "not_quadratic"} - pytanie nie jest o rownaniu
          kwadratowym (ani w tresci, ani w opcjach) ALBO slowo trudnosci
          nierozpoznane - walidacja nie ma zastosowania, nie blokujemy.
      {"status": "ok", "detected_tier": ..., "requested_tier": ...}
      {"status": "fail", "reason": ..., "detected_tier": ...,
          "requested_tier": ...} - do odrzucenia/dogenerowania."""
    acceptable = _QUADRATIC_ACCEPTABLE_TIERS.get((requested_difficulty_word or "").strip().lower())
    if not acceptable:
        return {"status": "not_quadratic"}
    detected_tier = classify_quadratic_difficulty(question_text, option_texts=option_texts)
    if detected_tier is None:
        return {"status": "not_quadratic"}
    requested_label = "/".join(sorted(acceptable))
    if detected_tier in acceptable:
        return {"status": "ok", "detected_tier": detected_tier, "requested_tier": requested_label}
    if detected_tier < min(acceptable):
        reason = f"za latwe - brak parametru/zlozonego warunku (wykryto {detected_tier}, oczekiwano {requested_label})"
    else:
        reason = f"za trudne - zbyt zlozona analiza jak na ta trudnosc (wykryto {detected_tier}, oczekiwano {requested_label})"
    return {"status": "fail", "reason": reason, "detected_tier": detected_tier, "requested_tier": requested_label}


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
        rels = _parse_relational_list(p)
        if not rels or any(param not in rel.free_symbols for rel in rels):
            return None
        try:
            rel_sets = [sp.solveset(rel, param, domain=S.Reals) for rel in rels]
        except Exception:
            return None
        part_set = rel_sets[0]
        for rs in rel_sets[1:]:
            part_set = part_set.intersect(rs)
        sets.append(part_set)
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


# NAPRAWIONE (wykryte realna generacja Etapu 6): litera zmiennej wyrazu
# NIE zawsze jest 'a' - AI dla urozmaicenia kilku pytan w tej samej
# partii uzywa tez b/c/d/e_1=... - dowolna mala litera, nie tylko 'a'
# (bezpieczne: wymagany cyfrowy indeks w dolnym indeksie odroznia to od
# _SEQ_R_RE/_SEQ_Q_RE, ktore nie maja indeksu).
_SEQ_TERM_RE = re.compile(r'[a-z]_?\{?(\d+)\}?\s*=\s*(-?\d+(?:[.,]\d+)?)')
_SEQ_LAST_TERM_RE = re.compile(r'[a-z]_?\{?n\}?\s*=\s*(-?\d+(?:[.,]\d+)?)')
_SEQ_R_RE = re.compile(r'(?<![a-zA-Z])r\s*=\s*(-?\d+(?:[.,]\d+)?)')
_SEQ_Q_RE = re.compile(r'(?<![a-zA-Z])q\s*=\s*(-?\d+(?:[.,]\d+)?)')
# NAPRAWIONE (wykryte realna generacja Etapu 6): "suma" (mianownik, np.
# "Ile wynosi suma pierwszych 6 wyrazów...") obok "sumę"/"sume" (biernik,
# np. "Oblicz sumę pierwszych 6 wyrazów...") - ten sam sum_given_n,
# inny przypadek gramatyczny zaleznie od pozycji w zdaniu.
_SEQ_SUM_N_RE = re.compile(r'sum[aeę]\s+pierwszych\s+(\d+)\s+wyraz')
_SEQ_SUM_VALUE_RE = re.compile(r'suma\s+pierwszych\s+(\d+)\s+wyraz\w*[^.]*?wynosi\s+(-?\d+(?:[.,]\d+)?)')
# NAPRAWIONE (wykryte realna generacja Etapu 6): oprocz "oblicz" AI rowniez
# naturalnie pisze "wyznacz"/"znajdz"/"jaki jest" N-ty wyraz - te same
# pytanie o find_nth_term, inny czasownik.
_SEQ_NTH_ASK_VERB = r'(?:oblicz|wyznacz|znajd\w*|jaki jest)'
_SEQ_NTH_ASK_RE = re.compile(_SEQ_NTH_ASK_VERB + r'\s+(\d+)[-.]?\s*(?:ty|szy|-ty|-szy)?\s*wyraz')
# ETAP 6 (naprawa wykryta realna generacja - "easy" AI naturalnie pisze
# "Oblicz piąty wyraz", nie "Oblicz 5. wyraz"): to samo co _SEQ_NTH_ASK_RE,
# ale slownie zamiast cyfra - odrebny regex/slownik (nie mieszamy grupy
# cyfrowej ze slowna w jednym wzorcu).
_SEQ_ORDINAL_WORDS = {
    # UWAGA: celowo BEZ "pierwszy":1 - "wyznacz/oblicz pierwszy wyraz" w
    # praktyce ZAWSZE oznacza "znajdz a1" (two_term_to_a1_ratio/
    # find_a1_given_sum), nigdy dosl. "policz wyraz o indeksie 1"
    # (degenerowane, nikt tak nie pyta) - dodanie tu "pierwszy" powodowalo
    # falszywe dopasowanie find_nth_term zamiast two_term_to_a1_ratio dla
    # "Wyznacz pierwszy wyraz i różnicę" (zlapany przez test_math_verify.py).
    "drugi": 2, "trzeci": 3, "czwarty": 4,
    "piąty": 5, "piaty": 5, "szósty": 6, "szosty": 6,
    "siódmy": 7, "siodmy": 7, "ósmy": 8, "osmy": 8,
    "dziewiąty": 9, "dziewiaty": 9, "dziesiąty": 10, "dziesiaty": 10,
    "jedenasty": 11, "dwunasty": 12, "trzynasty": 13, "czternasty": 14,
    "piętnasty": 15, "pietnasty": 15, "szesnasty": 16, "siedemnasty": 17,
    "osiemnasty": 18, "dziewiętnasty": 19, "dziewietnasty": 19, "dwudziesty": 20,
}
_SEQ_NTH_ASK_ORDINAL_RE = re.compile(_SEQ_NTH_ASK_VERB + r'\s+(' + '|'.join(_SEQ_ORDINAL_WORDS.keys()) + r')\s+wyraz')
# ETAP 6: "suma pierwszych N wyrazow ... wynosi X" GDZIE N JEST SZUKANE
# (litera "n", nie cyfra) - odroznione od _SEQ_SUM_VALUE_RE (ktory
# wymaga cyfry - tam N JEST DANE, szukane jest a1).
_SEQ_SUM_VALUE_UNKNOWN_N_RE = re.compile(r'suma\s+pierwszych\s+n\s+wyraz\w*[^.]*?wynosi\s+(-?\d+(?:[.,]\d+)?)')


def analyze_sequence_question(question_text: str):
    """Rozpoznaje zadanie o ciagu arytmetycznym/geometrycznym. Zwraca
    dict z rozpoznanymi danymi albo None (nie wyglada na takie
    zadanie/brak rozpoznawalnych danych - abstain)."""
    if not question_text:
        return None
    # NAPRAWIONE: text musi byc lowercase PRZED regex-extraction, nie tylko
    # lokalnie w kind-checku - zdaniowo-poczatkowa wielka litera ("Suma
    # pierwszych...") inaczej nie pasowala do _SEQ_SUM_VALUE_RE (i innych),
    # ktore oczekuja malych liter (tak jak juz robi detect_sequence_intent).
    text = _normalize_subscripts(question_text).lower()
    is_arithmetic = 'arytmetyczn' in text
    is_geometric = 'geometryczn' in text
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


def _sequence_a1_given(text: str) -> bool:
    """True jesli a1 jest PODANE wprost w tresci (np. 'a_1=3', 'a1 = 3') -
    wywolywane na juz-lowercased/znormalizowanym tekscie (patrz
    detect_sequence_intent). Uzywane do odroznienia 'pierwszy wyraz' jako
    OPISU danej wartosci od 'pierwszy wyraz' jako SZUKANEJ wartosci."""
    return any(int(m.group(1)) == 1 for m in _SEQ_TERM_RE.finditer(text))


def detect_sequence_intent(question_text: str):
    """Zwraca dict opisujacy co jest pytaniem, albo None (nierozpoznany
    typ pytania o ciagu - abstain). Kolejnosc sprawdzania ma znaczenie -
    od najbardziej specyficznych wzorcow do najbardziej ogolnych, zeby
    np. "suma...znajdz pierwszy wyraz" nie zostalo zle sklasyfikowane
    jako zwykle "two_term_to_a1_ratio".

    ETAP 6: dodane 2 nowe, minimalne rozszerzenia (bez nowego parsera -
    reuzywaja istniejace an_expr/sn_expr w verify_sequence_question):
      find_n_from_sum - "suma pierwszych n wyrazow... wynosi X" gdzie n
          jest SZUKANE (litera, nie cyfra) - inny przypadek niz
          find_a1_given_sum (tam n jest DANE, szukane a1).
      term_and_sum_to_a1_ratio - jeden KONKRETNY wyraz + suma, szukane
          a1 I r/q razem (uklad 2 rownan) - musi byc sprawdzone PRZED
          find_a1_given_sum, ktory zaklada ze r/q jest juz dane wprost.

    NAPRAWIONE (wykryte realna generacja Etapu 6 - "easy" pytania typu
    "ma pierwszy wyraz a1=3 i różnicę r=5. Oblicz piąty wyraz." byly
    falszywie lapane jako two_term_to_a1_ratio, bo fraza 'pierwszy wyraz'
    tam tylko OPISUJE juz PODANE a1, nie prosi o jego wyznaczenie): gdy
    a1 jest juz PODANE wprost w tresci (patrz _sequence_a1_given), frazy
    'pierwszy wyraz'/'znajdz'/'wyznacz a1'/'oblicz a1' NIE licza sie jako
    sygnal "a1 jest szukane" dla two_term_to_a1_ratio/find_a1_given_sum/
    term_and_sum_to_a1_ratio."""
    text = _normalize_subscripts(question_text).lower()

    m = _SEQ_NTH_ASK_RE.search(text)
    if m and 'suma' not in text:
        return {"intent": "find_nth_term", "n": int(m.group(1))}

    m = _SEQ_NTH_ASK_ORDINAL_RE.search(text)
    if m and 'suma' not in text:
        return {"intent": "find_nth_term", "n": _SEQ_ORDINAL_WORDS[m.group(1)]}

    m = _SEQ_SUM_VALUE_UNKNOWN_N_RE.search(text)
    if m:
        return {"intent": "find_n_from_sum", "sum_value": _to_num(m.group(1))}

    a1_given = _sequence_a1_given(text)
    asks_for_a1 = not a1_given and (
        'pierwszy wyraz' in text or 'wyznacz a1' in text or 'znajd' in text or 'oblicz a1' in text
    )

    if (_SEQ_SUM_VALUE_RE.search(text) and _SEQ_TERM_RE.search(text) and asks_for_a1 and
        ('różnic' in text or 'roznic' in text or 'iloraz' in text)):
        return {"intent": "term_and_sum_to_a1_ratio"}

    if 'suma' in text and asks_for_a1:
        return {"intent": "find_a1_given_sum"}

    m = _SEQ_SUM_N_RE.search(text)
    if m and 'przekracza' not in text and 'najmniejsz' not in text:
        return {"intent": "sum_given_n", "n": int(m.group(1))}

    if ('ile wyraz' in text or ('liczb' in text and 'wyraz' in text)) and 'przekracza' not in text:
        return {"intent": "find_n_from_last_term"}

    if asks_for_a1 and ('różnic' in text or 'roznic' in text or 'iloraz' in text):
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
        # NAPRAWIONE (test regresyjny): "$a_{10} = 48$" ma $ na koncu, wiec
        # kotwica konca-stringu \s*$ nie pasowala tuz po liczbie (byl tam
        # jeszcze znak $) - regex nigdy nie trafial, a fallback probowal
        # sparsowac CALY tekst "a_(10) = 48" jako JEDNO wyrazenie sympy,
        # co zawsze rzucalo SyntaxError (bare "=" nie jest wyrazeniem) i
        # bylo cicho polykane przez zewnetrzny except, dajac "unverifiable".
        text = _normalize_subscripts(_option_text(opt)).strip().strip('$').strip()
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
        elif intent["intent"] == "find_n_from_sum":
            # ETAP 6: dla arytmetycznych S_n jest kwadratowe wzgledem n -
            # ma jednoznaczne rozwiazanie sympy.solve. Dla geometrycznych
            # rownanie jest transcendentalne (r^n) - swiadomie NIE
            # probujemy tego rozwiazywac (abstain), zeby nie zgadywac.
            if kind != "arithmetic":
                return {"status": "unverifiable"}
            if 1 not in terms or ratio is None:
                return {"status": "unverifiable"}
            sol = sp.solve(Eq(sn_expr(terms[1], ratio, n_sym), intent["sum_value"]), n_sym)
            real_sol = [s for s in sol if s.is_real and s > 0]
            if len(real_sol) != 1:
                return {"status": "unverifiable"}
            true_value = sp.nsimplify(real_sol[0])
            option_parser = lambda opt: _parse_expr(_option_text(opt))
        elif intent["intent"] == "term_and_sum_to_a1_ratio":
            # ETAP 6: naturalne rozszerzenie two_term_to_a1_ratio - zamiast
            # DWOCH konkretnych wyrazow, mamy JEDEN wyraz + sume - wciaz
            # uklad 2 rownan/2 niewiadome (a1, r/q), ten sam sympy.solve.
            if len(terms) != 1 or parsed["sum_value"] is None:
                return {"status": "unverifiable"}
            term_idx = next(iter(terms))
            term_val = terms[term_idx]
            sv = parsed["sum_value"]
            sol = sp.solve([
                Eq(an_expr(a1_sym, r_sym, term_idx), term_val),
                Eq(sn_expr(a1_sym, r_sym, sv["n"]), sv["value"]),
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
# ETAP 6 Universal Difficulty Engine: skala trudnosci dla ciagow
# arytmetycznych/geometrycznych - ten sam wzorzec co
# classify_quadratic_difficulty/validate_quadratic_difficulty powyzej,
# ale zbudowany na 7 rozpoznawalnych (intent, kind) kombinacjach zamiast
# ogolnego parsera symbolicznego (ciagi go dzis nie maja - patrz
# detect_sequence_intent). 5 pasm (SEQUENCE_DIFFICULTY_TIERS w
# level_config.py), naprawiony "hard" celowo obejmuje WIELE roznych
# wzorcow (nie jeden powtarzalny typ - wymog usera): 2 warianty
# two_term_to_a1_ratio (wg kind), term_and_sum_to_a1_ratio,
# find_n_from_sum.
# ---------------------------------------------------------------
_SEQUENCE_ACCEPTABLE_TIERS = {
    "easy": {"1"}, "latwy": {"1"}, "łatwy": {"1"}, "latwa": {"1"}, "łatwa": {"1"},
    "medium": {"2", "3"}, "sredni": {"2", "3"}, "średni": {"2", "3"}, "srednia": {"2", "3"}, "średnia": {"2", "3"},
    "hard": {"4", "5"}, "trudny": {"4", "5"}, "trudna": {"4", "5"},
}


def classify_sequence_difficulty(question_text: str):
    """Szacuje pasmo trudnosci ('1'..'5') pytania o ciagu arytmetycznym/
    geometrycznym, na bazie (intent, kind) - patrz SEQUENCE_DIFFICULTY_TIERS
    w level_config.py po pelny opis kazdego pasma. None jesli tresc nie
    zawiera rozpoznawalnego wzorca pytania o ciag (analyze_sequence_question/
    detect_sequence_intent zwrocily None) - walidacja nie ma zastosowania,
    nie blokujemy (ta sama filozofia co przy rownaniach kwadratowych -
    bezpieczny abstain, nie zgadywanie)."""
    parsed = analyze_sequence_question(question_text)
    if not parsed:
        return None
    intent = detect_sequence_intent(question_text)
    if not intent:
        return None
    kind = parsed["kind"]
    name = intent["intent"]

    if name == "find_nth_term":
        return "1"
    if name in ("sum_given_n", "find_n_from_last_term", "find_a1_given_sum"):
        return "3" if kind == "geometric" else "2"
    if name == "two_term_to_a1_ratio":
        return "5" if kind == "geometric" else "4"
    if name == "term_and_sum_to_a1_ratio":
        return "4"
    if name == "find_n_from_sum":
        return "5"
    return None


def validate_sequence_difficulty(question_text: str, requested_difficulty_word: str):
    """Sprawdza, czy wygenerowane pytanie o ciagu odpowiada ZADANEJ
    trudnosci - identyczny kontrakt do validate_quadratic_difficulty
    (status ok/fail/not_sequence + reason/detected_tier/requested_tier)."""
    acceptable = _SEQUENCE_ACCEPTABLE_TIERS.get((requested_difficulty_word or "").strip().lower())
    if not acceptable:
        return {"status": "not_sequence"}
    detected_tier = classify_sequence_difficulty(question_text)
    if detected_tier is None:
        return {"status": "not_sequence"}
    requested_label = "/".join(sorted(acceptable))
    if detected_tier in acceptable:
        return {"status": "ok", "detected_tier": detected_tier, "requested_tier": requested_label}
    tier_order = ["1", "2", "3", "4", "5"]
    if tier_order.index(detected_tier) < tier_order.index(min(acceptable, key=tier_order.index)):
        reason = f"za latwe - brak zlozonosci oczekiwanej na tym poziomie (wykryto {detected_tier}, oczekiwano {requested_label})"
    else:
        reason = f"za trudne jak na ta trudnosc (wykryto {detected_tier}, oczekiwano {requested_label})"
    return {"status": "fail", "reason": reason, "detected_tier": detected_tier, "requested_tier": requested_label}


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
