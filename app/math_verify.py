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
    # NAPRAWIONE (zgloszony realny bug): unicode "≠" (U+2260) nie byl
    # rownowazny "!=" - AI czesto pisze warunki jak "c≠0" (unicode znak),
    # nie tylko LaTeX "\neq" (juz obslugiwane wyzej). Bez tego
    # parse_option_as_param_set (weryfikacja rownan kwadratowych z
    # parametrem) nie potrafil sparsowac takiej opcji (SyntaxError w
    # sympy), co przy WSZYSTKICH 4 opcjach nierozpoznanych prowadzilo do
    # "unverifiable" - Warstwa 2 nie mogla nic zawetowac.
    s = s.replace('\u2260', '!=')
    # NAPRAWIONE (ten sam zglobszony bug): unicode superscript ("e²>1",
    # "f²>24") tez nie parsowal sie w tej sciezce - _normalize_subscripts
    # (uzywany gdzie indziej) NIE jest wolany tutaj. _clean_latex jest
    # jedynym wspolnym punktem normalizacji przed parse_expr w CALEJ
    # sciezce rownan kwadratowych (z parametrem i bez), wiec to
    # najbezpieczniejsze miejsce - dziala identycznie dla obu.
    s = _SUPERSCRIPT_RE.sub(lambda m: '^' + m.group(0).translate(_SUPERSCRIPT_MAP), s)
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


_FUNC_DEF_LHS_RE = re.compile(r'^[fgh]\s*\(\s*x\s*\)$')


def _find_equation_in_text(text: str):
    """Pierwszy fragment $...$ w tekscie wygladajacy na rownanie kwadratowe
    (zawiera 'x', '=' i 'x^2'/'x**2'). Zwraca (lhs_str, rhs_str) albo None.

    NAPRAWIONE (Etap 8, wykryte realna generacja): "f(x) = x^2-4x+3" (DEFINICJA
    funkcji, nie rownanie do rozwiazania) spelnialo wszystkie 3 warunki
    powyzej i bylo bledne interpretowane jako rownanie - _parse_expr
    parsuje "f(x)" jako NIEJAWNE MNOZENIE "f*x" (nie wywolanie funkcji,
    bo transformacje sympy tu uzyte nie rozpoznaja 'f' jako nazwy
    funkcji), wiec 'f' ladowal jako "parametr" rownania kwadratowego -
    to bezposrednio kolidowalo z nowym classify_quadratic_function_difficulty
    (Etap 8), ktory oczekuje TAKIEJ WLASNIE notacji "f(x)=...". Jawne
    wykluczenie LHS=="f(x)" (definicja funkcji) z detekcji rownania -
    prawdziwe rownania kwadratowe w tej apce zawsze maja wielomian po
    lewej stronie (np. "x^2-5x+6=0"), nigdy bare "f(x)"."""
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
            lhs_s, rhs_s = parts
            if _FUNC_DEF_LHS_RE.match(lhs_s.strip()):
                continue
            return lhs_s, rhs_s
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
# ETAP 7 (audyt architektury): wspolny szkielet kontraktu Warstwy 3
# ("czy wygenerowane pytanie odpowiada zadanej trudnosci") - wyodrebniony
# po tym, jak validate_quadratic_difficulty/validate_sequence_difficulty
# (i teraz validate_trig_difficulty) okazaly sie 3 niemal identycznymi
# kopiami tej samej logiki (5 tematow docelowo = 5 kopii bez tego).
# Wylacznie boilerplate kontraktu - detekcja tieru (classify_X_difficulty)
# ZOSTAJE w pelni tematyczna, wolana PRZED tym helperem przez kazdy
# validate_X_difficulty z osobna (temat nadal decyduje SAM, jak rozpoznac
# swoj tier - to jest jedyna rzecz, ktora NIE jest uniwersalna).
#
# NAPRAWIONE PRZY OKAZJI: validate_quadratic_difficulty porownywal tiery
# przez zwykle porownanie stringow ("7-8" < "9-10"), co dzialalo tylko
# przypadkiem dla tej konkretnej etykiety pasm (kazda zaczyna sie od
# rosnacej cyfry 1,3,5,7,9). validate_sequence_difficulty uzywal juz
# bezpieczniejszego tier_order.index() - teraz WSZYSTKIE 3 tematy uzywaja
# tej samej, poprawnej metody porownania (zero zmiany faktycznego wyniku -
# dla obecnego zestawu etykiet obie metody dawaly identyczne odpowiedzi,
# patrz snapshot przed/po w teście regresyjnym).
# ---------------------------------------------------------------
def _generic_validate_difficulty(
    detected_tier, acceptable_tiers, tier_order: list,
    abstain_status: str, too_easy_reason: str, too_hard_reason: str,
) -> dict:
    """Wspolny szkielet: `detected_tier` (albo None - abstain) i
    `acceptable_tiers` (zbior stringow-tierow, albo pusty/None - abstain)
    juz WYLICZONE przez wywolujacego (kazdy temat robi to po swojemu).
    `tier_order` - pelna, uporzadkowana lista mozliwych tierow dla tego
    tematu (np. ["1-2","3-4","5-6","7-8","9-10"] albo ["1".."5"]).
    `too_easy_reason`/`too_hard_reason` - szablony z {detected_tier}/
    {requested_label} do podstawienia (kazdy temat ma wlasny tekst)."""
    if not acceptable_tiers or detected_tier is None:
        return {"status": abstain_status}
    requested_label = "/".join(sorted(acceptable_tiers))
    if detected_tier in acceptable_tiers:
        return {"status": "ok", "detected_tier": detected_tier, "requested_tier": requested_label}
    if tier_order.index(detected_tier) < tier_order.index(min(acceptable_tiers, key=tier_order.index)):
        reason = too_easy_reason.format(detected_tier=detected_tier, requested_label=requested_label)
    else:
        reason = too_hard_reason.format(detected_tier=detected_tier, requested_label=requested_label)
    return {"status": "fail", "reason": reason, "detected_tier": detected_tier, "requested_tier": requested_label}


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
_QUADRATIC_TIER_ORDER = ["1-2", "3-4", "5-6", "7-8", "9-10"]


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
    detected_tier = classify_quadratic_difficulty(question_text, option_texts=option_texts)
    return _generic_validate_difficulty(
        detected_tier, acceptable, _QUADRATIC_TIER_ORDER, "not_quadratic",
        "za latwe - brak parametru/zlozonego warunku (wykryto {detected_tier}, oczekiwano {requested_label})",
        "za trudne - zbyt zlozona analiza jak na ta trudnosc (wykryto {detected_tier}, oczekiwano {requested_label})",
    )


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
# NAPRAWIONE (Etap 8, wykryte przy budowie funkcji kwadratowej): AI
# czesto pisze "x²" (unicode superscript), nie "x^2"/"x**2" - sympy
# parse_expr nie rozumie unicode superscriptow w ogole (SyntaxError).
# Dotyczylo to tez ISTNIEJACEGO kodu rownan kwadratowych
# (_find_equation_in_text wymaga literalnie "^2"/"**2"), wiec ta
# naprawa (w jedynym wspolnym punkcie normalizacji) korzysta WSZYSTKIM
# tematom naraz, nie tylko funkcjom.
_SUPERSCRIPT_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_SUPERSCRIPT_RE = re.compile(r'[⁰¹²³⁴⁵⁶⁷⁸⁹]+')


def _normalize_subscripts(s: str) -> str:
    s = s.translate(_SUBSCRIPT_MAP)
    s = re.sub(r'a_(\d)', r'a\1', s)
    return _SUPERSCRIPT_RE.sub(lambda m: '^' + m.group(0).translate(_SUPERSCRIPT_MAP), s)


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
_SEQUENCE_TIER_ORDER = ["1", "2", "3", "4", "5"]


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
    detected_tier = classify_sequence_difficulty(question_text)
    return _generic_validate_difficulty(
        detected_tier, acceptable, _SEQUENCE_TIER_ORDER, "not_sequence",
        "za latwe - brak zlozonosci oczekiwanej na tym poziomie (wykryto {detected_tier}, oczekiwano {requested_label})",
        "za trudne jak na ta trudnosc (wykryto {detected_tier}, oczekiwano {requested_label})",
    )


# ---------------------------------------------------------------
# ETAP 7 Universal Difficulty Engine: trygonometria.
#
# Warstwa 2 (weryfikacja sympy) - SWIADOMIE zawezona do JEDNEGO,
# bezpiecznego podzbioru: ewaluacja funkcji trygonometrycznej dla KATA
# SPECJALNEGO w STOPNIACH (np. "sin(30°)=?") - dokladnie ten przypadek,
# ktory wywolal ten Etap (zbyt latwe "sin(30)" akceptowane jako
# "medium"). Rownania i tozsamosci CELOWO NIE sa tu weryfikowane
# (unverifiable/abstain) - sympy.simplify/trigsimp moze nie zredukowac
# rownowaznych wyrazen trygonometrycznych do wspolnej postaci, co
# grozi FALSZYWYM odrzuceniem poprawnej odpowiedzi (gorsze niz brak
# weryfikacji). Notacja radianowa (pi) rowniez CELOWO poza zakresem
# Warstwy 2 na start - rzadsza dla pytan easy-tier, mozna dodac pozniej
# na bazie realnych danych (ta sama filozofia co sparametryzowane ciagi
# w Etapie 6 - abstain zamiast zgadywania).
#
# Warstwa 3 (klasyfikacja trudnosci) ma SZERSZY zakres niz Warstwa 2 -
# rozpoznaje tez trojkat prostokatny, tozsamosci, rownania (z/bez
# parametru) - do samej KLASYFIKACJI nie potrzeba symbolicznej
# weryfikacji poprawnosci, tylko wzorcowego rozpoznania TYPU zadania
# (tak jak detect_sequence_intent w Etapie 6).
# ---------------------------------------------------------------
# NAPRAWIONE (wykryte realna generacja): AI uzywa tez sec/csc (sekans/
# kosekans) - rzadsze w polskim programie (czesciej 1/cos, 1/sin), ale
# sympy obsluguje je natywnie (sp.sec/sp.csc), wiec dodanie kosztuje
# zero dodatkowego ryzyka.
_TRIG_FUNC_MAP = {
    "sin": sp.sin, "cos": sp.cos,
    "tg": sp.tan, "tan": sp.tan,
    "ctg": sp.cot, "cot": sp.cot,
    "sec": sp.sec, "csc": sp.csc,
}
_TRIG_DEG_RE = re.compile(
    # NAPRAWIONE (wykryte realna generacja): "^{\circ}" (nawias klamrowy
    # PRZED \circ, np. "30^{\circ}") jest tak samo powszechny jak
    # "^\circ" (bez nawiasu) - oryginalny wzorzec dopuszczal nawias
    # TYLKO po "circ", nie przed, wiec "^{\circ}" nie pasowalo w ogole.
    r'\\?(sin|cos|tg|ctg|tan|cot|sec|csc)\s*\(?\s*(-?\d+(?:[.,]\d+)?)\s*(?:°|\^\s*\{?\s*\\?circ\}?|\^\s*o|stopni)',
    re.I,
)


def analyze_trig_special_angle_question(question_text: str):
    """Rozpoznaje pytanie o wartosc funkcji trygonometrycznej dla KATA
    SPECJALNEGO w STOPNIACH (wielokrotnosc 15°, np. 30/45/60/90/...).
    Zwraca {"func", "deg", "value"} (value = dokladna wartosc sympy)
    albo None (nie rozpoznano / kat nie jest "specjalny" / wartosc
    niezdefiniowana np. tg(90°) - abstain, nie zgadujemy)."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text)
    m = _TRIG_DEG_RE.search(text)
    if not m:
        return None
    func_name = m.group(1).lower()
    deg = _to_num(m.group(2))
    if deg is None or deg != int(deg):
        return None
    deg = int(deg) % 360
    if deg % 15 != 0:
        return None  # nie jest to "kat specjalny" z programu nauczania
    func = _TRIG_FUNC_MAP.get(func_name)
    if not func:
        return None
    try:
        value = sp.nsimplify(func(sp.rad(deg)))
    except Exception:
        return None
    if not value.is_finite or value.has(sp.zoo, sp.oo, -sp.oo):
        return None  # niezdefiniowane, np. tg(90°)/ctg(0°)
    return {"func": func_name, "deg": deg, "value": value}


def verify_trig_special_angle_question(question_text: str, options: list):
    """Weryfikacja Warstwy 2 dla katow specjalnych w stopniach - ten sam
    kontrakt co verify_sequence_question (match_index/no_option_matches/
    unverifiable)."""
    parsed = analyze_trig_special_angle_question(question_text)
    if not parsed:
        return {"status": "unverifiable"}
    true_value = parsed["value"]
    matches = []
    any_parsed = False
    for idx, opt in enumerate(options or []):
        try:
            opt_val = sp.nsimplify(_parse_expr(_option_text(opt)))
        except Exception:
            opt_val = None
        if opt_val is None:
            continue
        any_parsed = True
        try:
            equal = bool(sp.simplify(opt_val - true_value) == 0)
        except Exception:
            equal = False
        if equal:
            matches.append(idx)
    if not any_parsed:
        return {"status": "unverifiable"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    if len(matches) > 1:
        return {"status": "unverifiable"}
    return {"status": "no_option_matches"}


# Pasma trudnosci (skala 1-5, jak SEQUENCE_DIFFICULTY_TIERS) - rozpoznanie
# WZORCOWE (regex/slowa kluczowe), nie symboliczne - patrz TRIG_DIFFICULTY_TIERS
# w level_config.py po pelny opis kazdego pasma:
#   1 - wartosc dla kata specjalnego (analyze_trig_special_angle_question)
#   2-3 - trojkat prostokatny (SOH-CAH-TOA), tw. sinusow/cosinusow, prosta
#         tozsamosc (Pitagorasa), zamiana stopnie<->radiany
#   4-5 - rownanie trygonometryczne (4 bez parametru, 5 z parametrem ALBO
#         dowod tozsamosci) - CELOWO 2 rozne wzorce w "hard", nie jeden
#         powtarzalny typ (ta sama zasada co przy ciagach w Etapie 6)
_TRIG_RIGHT_TRIANGLE_MARKERS = (
    'przeciwprostokątn', 'przeciwprostokatn', 'przyprostokątn', 'przyprostokatn',
    'trójkącie prostokątnym', 'trojkacie prostokatnym', 'twierdzeni sinus', 'twierdzeni cosinus',
    'twierdzenie sinusów', 'twierdzenie sinusow', 'twierdzenie cosinusów', 'twierdzenie cosinusow',
)
_TRIG_CONVERSION_MARKERS = ('na radiany', 'na stopnie', 'zamień', 'zamien')
_TRIG_PROOF_MARKERS = ('udowodnij', 'wykaż', 'wykaz', 'uzasadnij', 'udowodnic', 'udowodnić')
# NAPRAWIONE (wykryte realna generacja): rdzen "równani"/"rownani" (nie
# pelne slowo "równanie") - polski jest fleksyjny, "rozwiązania równania"
# (dopelniacz) nie zawiera podciagu "równanie" (mianownik), przez co
# rownania w tej formie gramatycznej przechodzily jako nierozpoznane
# (abstain) zamiast poprawnie tier 4/5.
_TRIG_EQUATION_MARKERS = ('równani', 'rownani', 'rozwiąż', 'rozwiaz')
_TRIG_IDENTITY_MARKERS = ('tożsam', 'tozsam')
_TRIG_FUNC_MENTION_RE = re.compile(r'\\?(sin|cos|tg|ctg|tan|cot|sec|csc)\b', re.I)
# NAPRAWIONE (wykryte realna generacja): czesty wzorzec "medium" - dana
# JEDNA wartosc funkcji trygonometrycznej ("sin(x)=3/5"), szukana INNA
# (tozsamosc Pitagorasa/wzor na tangens) - BEZ slowa "rownanie"/"tozsamosc"
# (AI pisze "znajdz"/"oblicz", nie uzywa tych slow-kluczy). Odrozniony od
# rownania do ROZWIAZANIA (has_equation) przez brak markera rownania -
# sprawdzany PO nim w classify_trig_difficulty.
# NAPRAWIONE (wykryte realna generacja): AI czasem uzywa theta (\theta)
# zamiast x jako nazwy zmiennej kata - rownie standardowa konwencja w
# trygonometrii.
_TRIG_GIVEN_VALUE_RE = re.compile(r'\\?(sin|cos|tg|ctg|tan|cot|sec|csc)\s*\(?\s*(?:x|\\?theta)\s*\)?\s*=', re.I)
# Izolowana pojedyncza litera (nie x/y/z - zmienna glowna) - dzieki
# lookaroundom NIE dopasowuje liter WEWNATRZ "sin"/"cos"/"tg"/"ctg" (te
# sa wieloliterowe, wiec kazda ich litera ma sasiada-litere po jednej
# ze stron). Ten sam wzorzec co _PARAMETER_SYMBOL_RE w features.py.
# NAPRAWIONE: granice [a-zA-Z] NIE obejmowaly polskich znakow
# diakrytycznych - "r" w "równanie" mial "ó" po prawej, ktore NIE jest
# w [a-zA-Z], wiec lookahead falszywie uznawal "r" za IZOLOWANA litere
# (parametr!). Rozszerzono klase o polskie znaki, zeby granica slowa
# byla rozpoznawana poprawnie.
# NAPRAWIONE (wykryte realna generacja): "w"/"i"/"o"/"u" sa czeste polskie
# JEDNOLITEROWE przyimki/spojniki ("w przedziale", "i różnicę"...) - jako
# izolowane litery falszywie lapaly sie jako "parametr". Wykluczone z
# zakresu (nigdy nie sa realnymi nazwami parametrow w tej aplikacji -
# konwencja to a/b/c/k/m/n/p/t). "a" ZOSTAJE mimo bycia tez spojnikiem
# ("a nie") - to zbyt czesta, realna nazwa parametru, zeby ja wykluczyc
# bez utraty wykrywania prawdziwych przypadkow. Etap 8: wspolna dla
# wszystkich tematow (nie jest w niczym specyficzna dla trygonometrii),
# uzywana tez przez classify_exponential_function_difficulty.
# Etap 8: dodatkowo wykluczone "(" z lookaheada - litera BEZPOSREDNIO
# przed nawiasem to wywolanie funkcji (np. "f(x)"), nie izolowany
# parametr. Bez tego "f" w KAZDYM pytaniu o funkcji ("f(x)=...",
# "oblicz f(3)") falszywie lapalo sie jako parametr.
_ISOLATED_LETTER_PARAMETER_RE = re.compile(r'(?<![a-zA-Ząćęłńóśźż\\])[a-hj-np-tvA-HJ-NP-TV](?![a-zA-Ząćęłńóśźż{(])')


def classify_trig_difficulty(question_text: str):
    """Szacuje pasmo trudnosci ('1'..'5') pytania o trygonometrii, na
    bazie wzorcow tekstowych. None jesli tresc nie zawiera rozpoznawalnego
    wzorca (nie wygenerowano falszywej klasyfikacji - bezpieczny abstain,
    ta sama filozofia co classify_sequence_difficulty)."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text).lower()
    has_right_triangle = any(w in text for w in _TRIG_RIGHT_TRIANGLE_MARKERS)
    has_func_mention = bool(_TRIG_FUNC_MENTION_RE.search(text))
    has_conversion = any(w in text for w in _TRIG_CONVERSION_MARKERS)
    # NAPRAWIONE: zadania o trojkacie prostokatnym (np. "przeciwprostokątna
    # ma dlugosc 10...") oraz zamiana stopnie<->radiany czesto NIE pisza
    # literalnie "sin("/"cos(" w tresci (funkcja trygonometryczna jest
    # UKRYTA w sposobie rozwiazania albo nieistotna dla samej konwersji
    # jednostek) - brama abstain nie moze wymagac tego od kazdego wzorca.
    if not has_right_triangle and not has_func_mention and not has_conversion:
        return None

    if analyze_trig_special_angle_question(question_text) is not None:
        return "1"

    has_proof = any(w in text for w in _TRIG_PROOF_MARKERS)
    has_identity = any(w in text for w in _TRIG_IDENTITY_MARKERS)
    has_equation = any(w in text for w in _TRIG_EQUATION_MARKERS)

    if has_func_mention and has_proof and has_identity:
        return "5"
    if has_func_mention and has_equation:
        has_param = bool(_ISOLATED_LETTER_PARAMETER_RE.search(text))
        return "5" if has_param else "4"
    if has_right_triangle:
        return "3" if ('sinus' in text or 'cosinus' in text) else "2"
    # NAPRAWIONE: zamiana stopnie<->radiany (has_conversion) czesto NIE
    # wspomina zadnej funkcji trygonometrycznej - to pytanie o same
    # jednostki kata, nie wymaga func_mention (inaczej niz prosta
    # tozsamosc, ktora bez wzmianki sin/cos/tg nie ma sensu).
    if has_conversion or (has_func_mention and has_identity):
        return "2"
    if bool(_TRIG_GIVEN_VALUE_RE.search(text)):
        return "2"
    return None


_TRIG_ACCEPTABLE_TIERS = {
    "easy": {"1"}, "latwy": {"1"}, "łatwy": {"1"}, "latwa": {"1"}, "łatwa": {"1"},
    "medium": {"2", "3"}, "sredni": {"2", "3"}, "średni": {"2", "3"}, "srednia": {"2", "3"}, "średnia": {"2", "3"},
    "hard": {"4", "5"}, "trudny": {"4", "5"}, "trudna": {"4", "5"},
}
_TRIG_TIER_ORDER = ["1", "2", "3", "4", "5"]


def validate_trig_difficulty(question_text: str, requested_difficulty_word: str):
    """Sprawdza, czy wygenerowane pytanie o trygonometrii odpowiada
    ZADANEJ trudnosci - identyczny kontrakt do validate_sequence_difficulty
    (status ok/fail/not_trig + reason/detected_tier/requested_tier)."""
    acceptable = _TRIG_ACCEPTABLE_TIERS.get((requested_difficulty_word or "").strip().lower())
    detected_tier = classify_trig_difficulty(question_text)
    return _generic_validate_difficulty(
        detected_tier, acceptable, _TRIG_TIER_ORDER, "not_trig",
        "za latwe - brak zlozonosci oczekiwanej na tym poziomie (wykryto {detected_tier}, oczekiwano {requested_label})",
        "za trudne jak na ta trudnosc (wykryto {detected_tier}, oczekiwano {requested_label})",
    )


# ---------------------------------------------------------------
# ETAP 8 Universal Difficulty Engine: funkcje (liniowa, kwadratowa jako
# FUNKCJA - nie rownanie, wykladnicza podstawowa).
#
# Warstwa 2 (weryfikacja sympy) - SWIADOMIE zawezona do BEZPIECZNYCH,
# closed-form podzbiorow (ta sama filozofia co trygonometria w Etapie 7):
#   liniowa: ewaluacja f(k) dla danego k, ORAZ wyznaczenie rownania
#       prostej przez 2 punkty.
#   kwadratowa-jako-funkcja: wierzcholek (p,q) z postaci ogolnej.
#   wykladnicza: ewaluacja f(k) dla calkowitego k, ORAZ rownanie przy tej
#       samej podstawie (a^E = liczba bedaca "ladna" potega a).
# Rownania/nierownosci z parametrem, podstawieniem, dowody, zadania
# optymalizacyjne - CELOWO pozostaja abstain (jak rownania/tozsamosci
# trygonometryczne w Etapie 7).
# ---------------------------------------------------------------
# Przechwytuje RHS definicji NIEZACHLANNIE, zatrzymujac sie na pierwszym
# z: przecinek/kropka/znak zapytania/wykrzyknik/$, ALBO granicy slowa
# przed 2+ literowym "slowem" (kontynuacja zdania po polsku, np.
# "f(x)=3x-6 jest rosnąca?" - bez tego zachlanny [^,.$]+ probowal
# sparsowac CALE zdanie jako wyrazenie sympy i zawsze sie wywalal).
# NAPRAWIONE (wykryte realna generacja): AI nie zawsze uzywa "f" - czesto
# "g"/"h" (zwlaszcza gdy w tym samym zadaniu jest juz inna funkcja, albo
# po prostu dla urozmaicenia) - [fgh] zamiast literalnego "f" wszedzie
# tam, gdzie oczekujemy definicji funkcji.
_FUNC_DEF_RE = re.compile(
    r'[fgh]\s*\(\s*x\s*\)\s*=\s*([^,.$?!]+?)(?=\s+[a-zżąćęłńóśźA-ZŻĄĆĘŁŃÓŚŹ]{2,}\b|[,.$?!]|$)'
)
_FUNC_EVAL_RE = re.compile(r'[fgh]\s*\(\s*(-?\d+(?:[.,]\d+)?)\s*\)')
_POINT_RE = re.compile(r'\(\s*(-?\d+(?:[.,]\d+)?)\s*,\s*(-?\d+(?:[.,]\d+)?)\s*\)')
# _ISOLATED_LETTER_PARAMETER_RE zdefiniowana wyzej (Etap 7, przy
# classify_trig_difficulty) - uzywana tez przez
# classify_exponential_function_difficulty ponizej.


def _find_function_poly(question_text: str, degree: int):
    """Znajduje 'f(x) = <wyrazenie>' w tresci i sprawdza, ze <wyrazenie>
    jest wielomianem STOPNIA `degree` wzgledem x (dziala tez gdy
    wspolczynniki sa symboliczne - parametr, np. 'f(x)=(m-2)x+3' -
    Poly(expr,x) traktuje 'm' jako czesc wspolczynnika, degree() liczy
    TYLKO wzgledem x). Zwraca (x, Poly) albo None (nie rozpoznano -
    abstain). Wspolne dla liniowej (degree=1) i kwadratowej-jako-funkcji
    (degree=2)."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text)
    m = _FUNC_DEF_RE.search(text)
    if not m:
        return None
    try:
        expr = _parse_expr(m.group(1))
        x = Symbol('x')
        poly = Poly(expr, x)
    except Exception:
        return None
    if poly.degree() != degree:
        return None
    return x, poly


def _find_function_eval_target(question_text: str):
    """Znajduje wystapienie 'f(liczba)' w tresci - pytanie o wartosc
    funkcji w konkretnym punkcie (NIGDY nie dopasowuje 'f(x)' - wymaga
    liczby w nawiasie, wiec definicja funkcji jest naturalnie pomijana).
    Zwraca liczbe albo None."""
    text = _normalize_subscripts(question_text)
    m = _FUNC_EVAL_RE.search(text)
    if not m:
        return None
    return _to_num(m.group(1))


def _match_single_value_option(true_value, options: list) -> dict:
    """Wspolna petla dopasowania POJEDYNCZEJ wartosci sympy do listy
    opcji (parsowanych jako wyrazenia) - identyczny ksztalt/kontrakt co
    verify_trig_special_angle_question (wyodrebnione do ponownego
    uzycia - liniowa/wykladnicza maja ten sam ksztalt weryfikacji:
    JEDNA liczba do znalezienia wsrod opcji)."""
    matches = []
    any_parsed = False
    for idx, opt in enumerate(options or []):
        try:
            opt_val = sp.nsimplify(_parse_expr(_option_text(opt)))
        except Exception:
            opt_val = None
        if opt_val is None:
            continue
        any_parsed = True
        try:
            equal = bool(sp.simplify(opt_val - true_value) == 0)
        except Exception:
            equal = False
        if equal:
            matches.append(idx)
    if not any_parsed:
        return {"status": "unverifiable"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    if len(matches) > 1:
        return {"status": "unverifiable"}
    return {"status": "no_option_matches"}


# =================================================================
# 8a. FUNKCJA LINIOWA
# =================================================================
def analyze_linear_function_question(question_text: str):
    """Rozpoznaje funkcje liniowa f(x)=ax+b w tresci pytania. Zwraca
    {"x","a","b"} albo None (brak rozpoznanego wzoru - abstain)."""
    found = _find_function_poly(question_text, degree=1)
    if not found:
        return None
    x, poly = found
    a, b = poly.all_coeffs()
    return {"x": x, "a": a, "b": b}


def verify_linear_function_evaluate(question_text: str, options: list):
    """Warstwa 2: f(x)=ax+b, pytanie 'oblicz f(k)' dla konkretnego k."""
    parsed = analyze_linear_function_question(question_text)
    if not parsed:
        return {"status": "unverifiable"}
    if parsed["a"].free_symbols or parsed["b"].free_symbols:
        return {"status": "unverifiable"}  # parametr - nie da sie policzyc liczby
    k = _find_function_eval_target(question_text)
    if k is None:
        return {"status": "unverifiable"}
    true_value = sp.nsimplify(parsed["a"] * k + parsed["b"])
    return _match_single_value_option(true_value, options)


def analyze_linear_two_points_question(question_text: str):
    """Rozpoznaje zadanie 'wyznacz rownanie prostej przez 2 punkty' -
    wymaga DOKLADNIE 2 par (x,y) w tresci i wzmianki o prostej/funkcji
    liniowej (odroznienie od przypadkowych wspolrzednych w innym
    kontekscie, np. geometrii). Zwraca {"x1","y1","x2","y2"} albo None."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text)
    text_lower = text.lower()
    if not ('prost' in text_lower or ('funkcj' in text_lower and 'liniow' in text_lower)):
        return None
    points = _POINT_RE.findall(text)
    if len(points) != 2:
        return None
    (x1, y1), (x2, y2) = points
    x1, y1, x2, y2 = _to_num(x1), _to_num(y1), _to_num(x2), _to_num(y2)
    if x1 is None or x2 is None or x1 == x2:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


_OPTION_LINEAR_RE = re.compile(r'(?:[fgh]\s*\(\s*x\s*\)|y)\s*=\s*(.+)')


def _option_linear_ab(option_text):
    """Parsuje opcje sformatowana jako 'y=Ax+B'/'f(x)=Ax+B' (albo samo
    wyrazenie bez prefiksu) na (a,b). None jesli sie nie da (nie stopnia
    1 wzgledem x, blad parsowania)."""
    text = _normalize_subscripts(_option_text(option_text)).strip().strip('$').strip()
    m = _OPTION_LINEAR_RE.search(text)
    rhs = m.group(1) if m else text
    try:
        expr = _parse_expr(rhs)
        x = Symbol('x')
        poly = Poly(expr, x)
        if poly.degree() != 1:
            return None
        a, b = poly.all_coeffs()
        return sp.nsimplify(a), sp.nsimplify(b)
    except Exception:
        return None


def verify_linear_two_points_question(question_text: str, options: list):
    """Warstwa 2: wyznaczenie (a,b) prostej y=ax+b przez 2 dane punkty,
    dopasowanie do opcji sformatowanych jako 'y=Ax+B'/'f(x)=Ax+B'."""
    parsed = analyze_linear_two_points_question(question_text)
    if not parsed:
        return {"status": "unverifiable"}
    a_sym, b_sym = sp.symbols('a b')
    try:
        sol = sp.solve([
            Eq(a_sym * parsed["x1"] + b_sym, parsed["y1"]),
            Eq(a_sym * parsed["x2"] + b_sym, parsed["y2"]),
        ], [a_sym, b_sym])
        true_a, true_b = sp.nsimplify(sol[a_sym]), sp.nsimplify(sol[b_sym])
    except Exception:
        return {"status": "unverifiable"}

    matches = []
    any_parsed = False
    for idx, opt in enumerate(options or []):
        opt_ab = _option_linear_ab(opt)
        if opt_ab is None:
            continue
        any_parsed = True
        if opt_ab == (true_a, true_b):
            matches.append(idx)
    if not any_parsed:
        return {"status": "unverifiable"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    if len(matches) > 1:
        return {"status": "unverifiable"}
    return {"status": "no_option_matches"}


_LINEAR_PERPENDICULAR_PARALLEL_MARKERS = ('prostopadł', 'prostopadl', 'równoległ', 'rownolegl')
_LINEAR_MONOTONICITY_MARKERS = ('rosnąc', 'rosnac', 'malejąc', 'malejac', 'monotoniczn', 'miejsce zerow')
_LINEAR_SYSTEM_MARKERS = ('układ', 'uklad')


def classify_linear_function_difficulty(question_text: str):
    """Szacuje pasmo trudnosci ('1'..'5') pytania o funkcji liniowej, na
    bazie wzorcow tekstowych + rozpoznanego wzoru. None jesli tresc nie
    zawiera rozpoznawalnego wzorca (bezpieczny abstain)."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text).lower()
    parsed = analyze_linear_function_question(question_text)
    two_points = analyze_linear_two_points_question(question_text)
    has_perp_parallel = any(w in text for w in _LINEAR_PERPENDICULAR_PARALLEL_MARKERS)
    has_system = any(w in text for w in _LINEAR_SYSTEM_MARKERS) and 'prost' in text
    # NAPRAWIONE: pytania o prostej prostopadlej/rownoleglej/ukladzie
    # prostych czesto NIE uzywaja "f(x)=" (pisza "y=...") ani nie maja 2
    # par (x,y) w tresci - brama nie moze wymagac zadnego z powyzszych,
    # gdy inny jednoznaczny marker kontekstu prostej juz jest obecny.
    has_context = parsed is not None or two_points is not None or has_perp_parallel or has_system or (
        'funkcj' in text and 'liniow' in text
    )
    if not has_context:
        return None

    has_param = bool(parsed and (parsed["a"].free_symbols or parsed["b"].free_symbols))
    has_monotonicity = any(w in text for w in _LINEAR_MONOTONICITY_MARKERS)

    if has_param:
        return "5"
    if has_system:
        return "4"
    if two_points is not None or has_perp_parallel:
        return "3"
    if has_monotonicity:
        return "2"
    if parsed is not None and _find_function_eval_target(question_text) is not None:
        return "1"
    return None


_LINEAR_FUNCTION_ACCEPTABLE_TIERS = {
    "easy": {"1"}, "latwy": {"1"}, "łatwy": {"1"}, "latwa": {"1"}, "łatwa": {"1"},
    "medium": {"2", "3"}, "sredni": {"2", "3"}, "średni": {"2", "3"}, "srednia": {"2", "3"}, "średnia": {"2", "3"},
    "hard": {"4", "5"}, "trudny": {"4", "5"}, "trudna": {"4", "5"},
}
_LINEAR_FUNCTION_TIER_ORDER = ["1", "2", "3", "4", "5"]


def validate_linear_function_difficulty(question_text: str, requested_difficulty_word: str):
    """Sprawdza, czy wygenerowane pytanie o funkcji liniowej odpowiada
    ZADANEJ trudnosci - identyczny kontrakt do validate_trig_difficulty
    (status ok/fail/not_linear_function + reason/detected_tier/requested_tier)."""
    acceptable = _LINEAR_FUNCTION_ACCEPTABLE_TIERS.get((requested_difficulty_word or "").strip().lower())
    detected_tier = classify_linear_function_difficulty(question_text)
    return _generic_validate_difficulty(
        detected_tier, acceptable, _LINEAR_FUNCTION_TIER_ORDER, "not_linear_function",
        "za latwe - brak zlozonosci oczekiwanej na tym poziomie (wykryto {detected_tier}, oczekiwano {requested_label})",
        "za trudne jak na ta trudnosc (wykryto {detected_tier}, oczekiwano {requested_label})",
    )


# =================================================================
# 8b. FUNKCJA KWADRATOWA JAKO FUNKCJA (nie rownanie - patrz Iteracja 2
# wyzej dla rozwiazywania ax^2+bx+c=0. Ten modul dotyczy WLASCIWOSCI
# funkcji: wierzcholek, monotonicznosc, zbior wartosci, transformacje.
# Gating (is_quadratic_function_topic w level_config.py) jest CELOWO
# odrebny od is_quadratic_equation_topic, zeby oba modifiery NIE
# nakladaly sie na to samo pytanie).
# =================================================================
def analyze_quadratic_function_question(question_text: str):
    """Rozpoznaje funkcje kwadratowa f(x)=Ax^2+Bx+C (postac ogolna,
    rozwinieta - dziala tez gdy zapisana byla w postaci kanonicznej,
    Poly() i tak jest zawsze w postaci rozwinietej) w tresci pytania.
    Zwraca {"x","A","B","C"} albo None."""
    found = _find_function_poly(question_text, degree=2)
    if not found:
        return None
    x, poly = found
    A, B, C = poly.all_coeffs()
    return {"x": x, "A": A, "B": B, "C": C}


def verify_quadratic_function_vertex(question_text: str, options: list):
    """Warstwa 2: wierzcholek (p,q) paraboli z postaci ogolnej -
    p=-B/2A, q=f(p). Dopasowanie do opcji sformatowanych jako '(p,q)'."""
    parsed = analyze_quadratic_function_question(question_text)
    if not parsed:
        return {"status": "unverifiable"}
    A, B, C = parsed["A"], parsed["B"], parsed["C"]
    if A.free_symbols or B.free_symbols or C.free_symbols:
        return {"status": "unverifiable"}  # parametr - wierzcholek nie jest liczba
    try:
        p = sp.nsimplify(-B / (2 * A))
        q = sp.nsimplify(A * p ** 2 + B * p + C)
    except Exception:
        return {"status": "unverifiable"}

    matches = []
    any_parsed = False
    for idx, opt in enumerate(options or []):
        text = _normalize_subscripts(_option_text(opt))
        m = _POINT_RE.search(text)
        if not m:
            continue
        try:
            opt_p, opt_q = sp.nsimplify(_to_num(m.group(1))), sp.nsimplify(_to_num(m.group(2)))
        except Exception:
            continue
        any_parsed = True
        if opt_p == p and opt_q == q:
            matches.append(idx)
    if not any_parsed:
        return {"status": "unverifiable"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    if len(matches) > 1:
        return {"status": "unverifiable"}
    return {"status": "no_option_matches"}


# "wierzchołek" (mianownik/biernik) + rdzen "wierzchołk" (dopelniacz/
# celownik/narzednik/miejscownik: wierzchołka/wierzchołkowi/wierzchołkiem/
# wierzchołku) - polska odmiana z ruchoma samogloska "e" (wypada w
# przypadkach zaleznych), wiec NIE ma jednego wspolnego podciagu
# obejmujacego WSZYSTKIE formy - trzeba obu wariantow osobno.
_QUAD_FUNC_VERTEX_MARKERS = (
    'wierzchołek', 'wierzchołk', 'wierzcholek', 'wierzcholk',
    'postać kanoniczn', 'postac kanoniczn',
)
_QUAD_FUNC_MONOTONICITY_MARKERS = ('monotoniczn', 'rosnąc', 'rosnac', 'malejąc', 'malejac', 'przedział')
_QUAD_FUNC_RANGE_MARKERS = ('zbiór wartości', 'zbior wartosci')
_QUAD_FUNC_OPTIMIZATION_MARKERS = ('maksymaln', 'minimaln', 'najwięks', 'najwieks', 'najmniejsz')
_QUAD_FUNC_CANONICAL_RE = re.compile(r'\(\s*x\s*[+-]\s*\d+(?:[.,]\d+)?\s*\)\s*\^?\s*2')


def classify_quadratic_function_difficulty(question_text: str):
    """Szacuje pasmo trudnosci ('1'..'5') pytania o funkcji kwadratowej
    JAKO FUNKCJI (wierzcholek/monotonicznosc/zbior wartosci - NIE
    rozwiazywanie rownania). Wymaga co najmniej jednego markera
    wlasciwosci funkcji - inaczej to prawdopodobnie rownanie (inny
    modifier), nie ta klasyfikacja (bezpieczny abstain, brak nakladania
    sie z classify_quadratic_difficulty)."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text).lower()
    has_vertex = any(w in text for w in _QUAD_FUNC_VERTEX_MARKERS)
    has_mono = any(w in text for w in _QUAD_FUNC_MONOTONICITY_MARKERS)
    has_range = any(w in text for w in _QUAD_FUNC_RANGE_MARKERS)
    has_opt = any(w in text for w in _QUAD_FUNC_OPTIMIZATION_MARKERS)
    if not (has_vertex or has_mono or has_range or has_opt):
        return None

    parsed = analyze_quadratic_function_question(question_text)
    has_param = bool(parsed and (
        parsed["A"].free_symbols or parsed["B"].free_symbols or parsed["C"].free_symbols
    ))
    if has_param or has_opt:
        return "5"
    is_canonical_given = bool(_QUAD_FUNC_CANONICAL_RE.search(text))
    if has_vertex and is_canonical_given:
        return "1"
    if sum([has_vertex, has_mono, has_range]) >= 2:
        return "3"
    return "2"


_QUADRATIC_FUNCTION_ACCEPTABLE_TIERS = {
    "easy": {"1"}, "latwy": {"1"}, "łatwy": {"1"}, "latwa": {"1"}, "łatwa": {"1"},
    "medium": {"2", "3"}, "sredni": {"2", "3"}, "średni": {"2", "3"}, "srednia": {"2", "3"}, "średnia": {"2", "3"},
    "hard": {"4", "5"}, "trudny": {"4", "5"}, "trudna": {"4", "5"},
}
_QUADRATIC_FUNCTION_TIER_ORDER = ["1", "2", "3", "4", "5"]


def validate_quadratic_function_difficulty(question_text: str, requested_difficulty_word: str):
    """Sprawdza, czy wygenerowane pytanie o funkcji kwadratowej (JAKO
    FUNKCJI) odpowiada ZADANEJ trudnosci - identyczny kontrakt do
    validate_linear_function_difficulty."""
    acceptable = _QUADRATIC_FUNCTION_ACCEPTABLE_TIERS.get((requested_difficulty_word or "").strip().lower())
    detected_tier = classify_quadratic_function_difficulty(question_text)
    return _generic_validate_difficulty(
        detected_tier, acceptable, _QUADRATIC_FUNCTION_TIER_ORDER, "not_quadratic_function",
        "za latwe - brak zlozonosci oczekiwanej na tym poziomie (wykryto {detected_tier}, oczekiwano {requested_label})",
        "za trudne jak na ta trudnosc (wykryto {detected_tier}, oczekiwano {requested_label})",
    )


# =================================================================
# 8c. FUNKCJA WYKLADNICZA PODSTAWOWA
# =================================================================
_EXP_DEF_RE = re.compile(r'[fgh]\s*\(\s*x\s*\)\s*=\s*(\d+(?:[.,]\d+)?)\s*\^\s*\{?\s*x\s*\}?')
_EXP_EQ_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*\^\s*\{?\(?\s*([^=)}]+?)\s*\)?\}?\s*=\s*(-?\d+(?:[.,]\d+)?)')


def analyze_exponential_function_question(question_text: str):
    """Rozpoznaje funkcje wykladnicza f(x)=a^x (a - liczba > 0, a != 1)
    w tresci pytania. Zwraca {"a"} albo None."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text)
    m = _EXP_DEF_RE.search(text)
    if not m:
        return None
    a = _to_num(m.group(1))
    if a is None or a <= 0 or a == 1:
        return None
    return {"a": a}


def verify_exponential_function_evaluate(question_text: str, options: list):
    """Warstwa 2: f(x)=a^x, pytanie 'oblicz f(k)' dla calkowitego k."""
    parsed = analyze_exponential_function_question(question_text)
    if not parsed:
        return {"status": "unverifiable"}
    k = _find_function_eval_target(question_text)
    if k is None or k != int(k):
        return {"status": "unverifiable"}
    true_value = sp.nsimplify(sp.nsimplify(parsed["a"]) ** int(k))
    return _match_single_value_option(true_value, options)


def verify_exponential_same_base_equation(question_text: str, options: list):
    """Warstwa 2: rownanie a^E(x) = L, gdzie L jest 'ladna' (wymierna)
    potega a - closed form, rozwiazanie x przez porownanie wykladnikow
    (log_a(L) = E(x), rozwiazane wzgledem x)."""
    if not question_text:
        return {"status": "unverifiable"}
    text = _normalize_subscripts(question_text)
    m = _EXP_EQ_RE.search(text)
    if not m:
        return {"status": "unverifiable"}
    base = _to_num(m.group(1))
    rhs = _to_num(m.group(3))
    if base is None or base <= 0 or base == 1 or rhs is None or rhs <= 0:
        return {"status": "unverifiable"}
    try:
        exponent_expr = _parse_expr(m.group(2))
        k = sp.nsimplify(sp.log(rhs, base))
        if not k.is_rational:
            return {"status": "unverifiable"}
        x = Symbol('x')
        sol = sp.solve(Eq(exponent_expr, k), x)
        real_sol = [s for s in sol if s.is_real]
        if len(real_sol) != 1:
            return {"status": "unverifiable"}
        true_value = sp.nsimplify(real_sol[0])
    except Exception:
        return {"status": "unverifiable"}
    return _match_single_value_option(true_value, options)


_EXP_SUBSTITUTION_MARKERS = ('podstawiając', 'podstawiajac', 'podstawienie')
_EXP_INEQUALITY_MARKERS = ('nierówność', 'nierownosc', '≤', '≥')
_EXP_SHIFT_MARKERS = ('przesuni', 'wykres')
_EXP_GROWTH_DECAY_MARKERS = ('rosnąc', 'rosnac', 'malejąc', 'malejac', 'wzrost', 'spadek')
_EXP_EQUATION_MARKERS = ('równani', 'rownani', 'rozwiąż', 'rozwiaz')
# Dwie alternatywy: liczbowa podstawa + '^' (dowolny wykladnik, np.
# "2^x", "2^(x+1)") ALBO literowa podstawa (parametr) + '^' + wykladnik
# zaczynajacy sie od x (np. "a^x") - bez tej drugiej alternatywy zadania
# z parametryzowana podstawa ("dla jakich a rownanie a^x=8...") w ogole
# nie byly rozpoznawane jako trescia o funkcji wykladniczej.
_EXP_MENTION_RE = re.compile(r'\d+(?:[.,]\d+)?\s*\^|[a-zA-Z]\s*\^\s*\{?\(?\s*x\b', re.I)


def classify_exponential_function_difficulty(question_text: str):
    """Szacuje pasmo trudnosci ('1'..'5') pytania o funkcji
    wykladniczej, na bazie wzorcow tekstowych. None jesli tresc nie
    zawiera rozpoznawalnego wzorca (brak wzmianki 'liczba^...' -
    bezpieczny abstain)."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text).lower()
    if not _EXP_MENTION_RE.search(text):
        return None

    has_param = bool(_ISOLATED_LETTER_PARAMETER_RE.search(text))
    has_substitution = any(w in text for w in _EXP_SUBSTITUTION_MARKERS)
    has_inequality = any(w in text for w in _EXP_INEQUALITY_MARKERS)
    has_equation = any(w in text for w in _EXP_EQUATION_MARKERS)
    has_shift = any(w in text for w in _EXP_SHIFT_MARKERS)
    has_growth_decay = any(w in text for w in _EXP_GROWTH_DECAY_MARKERS)

    if has_param or has_substitution or has_inequality:
        return "5"
    if has_equation:
        return "3"
    if has_shift or has_growth_decay:
        return "2"
    if _find_function_eval_target(question_text) is not None:
        return "1"
    return None


_EXPONENTIAL_FUNCTION_ACCEPTABLE_TIERS = {
    "easy": {"1"}, "latwy": {"1"}, "łatwy": {"1"}, "latwa": {"1"}, "łatwa": {"1"},
    "medium": {"2", "3"}, "sredni": {"2", "3"}, "średni": {"2", "3"}, "srednia": {"2", "3"}, "średnia": {"2", "3"},
    "hard": {"4", "5"}, "trudny": {"4", "5"}, "trudna": {"4", "5"},
}
_EXPONENTIAL_FUNCTION_TIER_ORDER = ["1", "2", "3", "4", "5"]


def validate_exponential_function_difficulty(question_text: str, requested_difficulty_word: str):
    """Sprawdza, czy wygenerowane pytanie o funkcji wykladniczej
    odpowiada ZADANEJ trudnosci - identyczny kontrakt do
    validate_linear_function_difficulty."""
    acceptable = _EXPONENTIAL_FUNCTION_ACCEPTABLE_TIERS.get((requested_difficulty_word or "").strip().lower())
    detected_tier = classify_exponential_function_difficulty(question_text)
    return _generic_validate_difficulty(
        detected_tier, acceptable, _EXPONENTIAL_FUNCTION_TIER_ORDER, "not_exponential_function",
        "za latwe - brak zlozonosci oczekiwanej na tym poziomie (wykryto {detected_tier}, oczekiwano {requested_label})",
        "za trudne jak na ta trudnosc (wykryto {detected_tier}, oczekiwano {requested_label})",
    )


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


# ---------------------------------------------------------------
# NAPRAWA KRYTYCZNEGO BLEDU (zgloszony przez usera): zadania o
# prawdopodobienstwie/kombinatoryce mialy ZERO pokrycia Warstwy 2 -
# AI popelnilo blad arytmetyczny (P(oba tego samego koloru) dla urny
# 5 bialych + 3 czarne, losowanie 2 bez zwracania: prawdziwy wynik
# 13/28, AI podalo 10/28), a jego WLASNE pole final_answer bylo z tym
# bledem spojne, wiec Warstwa 1 (czysto tekstowe dopasowanie
# final_answer<->opcje) "poprawnie" wymusila bledna opcje - Warstwa 2
# nie miala JAK tego zawetowac, bo nie rozpoznawala tematu w ogole.
#
# Ta funkcja dodaje Warstwe 2 dla WASKIEGO, ale OGOLNEGO podzbioru:
# losowanie k elementow BEZ ZWRACANIA z populacji podzielonej na 2
# kategorie, prawdopodobienstwo zdarzenia okreslonego LICZBA elementow
# danej kategorii wsrod wylosowanych (rozklad hipergeometryczny) -
# DOWOLNE liczby, DOWOLNE nazwy kategorii (nie "urna"/"kule" specjalnie
# hardcodowane), NIE tylko k=2. Rownania/nierownosci prawdopodobienstwa,
# losowanie ZE zwracaniem, >2 kategorie, warunkowe prawdopodobienstwo -
# CELOWO poza zakresem (unverifiable/abstain), ta sama filozofia co
# rownania/tozsamosci trygonometryczne w Etapie 7.
# ---------------------------------------------------------------
_HYPERGEOM_WITHOUT_REPLACEMENT_RE = re.compile(r'bez\s+zwracania|bez\s+zwrotu')
_HYPERGEOM_NUM_WORD_RE = re.compile(r'(\d+)\s+((?:[a-ząćęłńóśźż]+\s*){1,2})', re.I)
_HYPERGEOM_CARDINAL_WORDS = {
    "jeden": 1, "jedną": 1, "jedna": 1,
    "dwie": 2, "dwa": 2, "dwóch": 2, "dwoch": 2, "obie": 2, "obu": 2, "oba": 2,
    "trzy": 3, "trzech": 3,
    "cztery": 4, "czterech": 4,
    "pięć": 5, "piec": 5, "pięciu": 5, "pieciu": 5,
    "sześć": 6, "szesc": 6, "sześciu": 6, "szesciu": 6,
}
_HYPERGEOM_CARDINAL_ALT = '|'.join(sorted(_HYPERGEOM_CARDINAL_WORDS.keys(), key=len, reverse=True))
_HYPERGEOM_DRAW_RE = re.compile(
    r'losuj\w*[^.]*?\b(\d+|' + _HYPERGEOM_CARDINAL_ALT + r')\b', re.I,
)
# NAPRAWIONE (zgloszony realny bug): pierwotna wersja byla lista
# DOSLOWNYCH fraz w JEDNYM przypadku gramatycznym ('tego samego',
# 'jednakowego'...) - polska fleksja ma wiele form tego samego
# przymiotnika/zaimka ('ten sam'/'tego samego'/'tym samym'/'takie
# same'...), wiec 5 z 7 realistycznych sformulowan AI nie bylo wcale
# rozpoznawanych (analyze zwracalo None -> Warstwa 2 nie mogla nic
# zawetowac -> bledny final_answer AI przechodzil bez kontroli - TEN
# SAM mechanizm, ktory naprawialismy wczesniej, tym razem w NOWYM
# kodzie). Naprawa: rdzenie odmiany zamiast calych sfleksowanych fraz.
#
# "jednego"/"innego" wymagaja bliskosci rzeczownika-kategorii (kolor/
# rodzaj/typ/gatunek), bo same w sobie sa zbyt ogolnymi, czestymi
# slowami (np. "innego ucznia") - zeby nie zgadywac tam, gdzie nie
# mozna bezpiecznie rozpoznac (WAZNE: unverifiable ma zostac
# domyslnym zachowaniem dla niejednoznacznych przypadkow).
_HYPERGEOM_CATEGORY_NOUN_STEM = r'(?:kolor\w*|rodzaj\w*|typ\w*|gatunk\w*)'
_HYPERGEOM_SAME_CATEGORY_RE = re.compile(
    r'tego\s+samego\b'                                          # "tego samego (koloru)" - dopelniacz
    r'|tej\s+samej\b'                                            # "tej samej (barwy)" - dopelniacz zenski
    r'|tym\s+samym\b'                                            # "w tym samym (kolorze)" - narzednik/miejscownik
    r'|ten\s+sam\b'                                               # "ten sam (kolor)" - mianownik
    r'|tak\w*\s+sam\w*'                                           # "taki sam"/"takie same"/"taka sama"/"takim samym"...
    r'|jednakow\w*'                                               # jednakowy/jednakowego/jednakowe...
    r'|identyczn\w*'                                              # identyczny/identycznego/identyczne...
    r'|jedn\w{0,3}\s+' + _HYPERGEOM_CATEGORY_NOUN_STEM,           # "jednego koloru"/"jednego rodzaju" (wymaga rzeczownika obok)
    re.I,
)
_HYPERGEOM_DIFFERENT_CATEGORY_RE = re.compile(
    r'różn\w*|rozn\w*'                                            # różny/różnych/różne/różnego... (jak wczesniej, tylko rdzen)
    r'|inn\w*\s+' + _HYPERGEOM_CATEGORY_NOUN_STEM,                # "innego koloru" (wymaga rzeczownika obok - "inny" samo w sobie zbyt ogolne)
    re.I,
)
# Opcjonalny czasownik-lacznik ("są"/"jest"/"będą") miedzy liczba a
# etykieta kategorii - "dokladnie 2 SA biale", nie tylko "dokladnie 2 biale".
_HYPERGEOM_EXACTLY_RE = re.compile(
    r'dokładnie\s+(\d+|' + _HYPERGEOM_CARDINAL_ALT + r')\s+(?:są|jest|będą|beda)?\s*([a-ząćęłńóśźż]+)', re.I,
)


def _hypergeom_cardinal(word: str):
    """'2'/'dwie'/'dwóch'... -> 2 (int). None jesli nierozpoznane."""
    word = word.strip().lower()
    if word.isdigit():
        return int(word)
    return _HYPERGEOM_CARDINAL_WORDS.get(word)


def _hypergeom_label_matches(word: str, category_words: str) -> bool:
    """Czy `word` (np. z 'dokladnie 2 bialych') pasuje do ktoregos ze
    slow opisujacych kategorie (np. 'kul bialych') - dopasowanie po
    4-znakowym rdzeniu, zeby tolerowac polska fleksje (bialych/biale/
    biala/bialy dziela wspolny rdzen 'biał')."""
    word = word.strip().lower()
    for cw in category_words.split():
        cw = cw.strip().lower()
        if not cw:
            continue
        if word == cw:
            return True
        if len(word) >= 4 and len(cw) >= 4 and (word[:4] == cw[:4]):
            return True
    return False


def _extract_hypergeom_categories(text: str):
    """Znajduje DOKLADNIE 2 wystapienia '<liczba> <slowo(-a)>' w
    PIERWSZYM zdaniu (populacja) - zwraca [(N1,slowa1),(N2,slowa2)]
    albo None. Nie zaklada KONKRETNYCH nazw kategorii (kule/kolory) -
    dziala dla dowolnych 2 grup (chlopcy/dziewczeta, wadliwe/sprawne,
    itd)."""
    first_sentence = text.split('.')[0]
    matches = _HYPERGEOM_NUM_WORD_RE.findall(first_sentence)
    if len(matches) != 2:
        return None
    (n1_s, w1), (n2_s, w2) = matches
    n1, n2 = int(n1_s), int(n2_s)
    if n1 <= 0 or n2 <= 0:
        return None
    return [(n1, w1.strip()), (n2, w2.strip())]


def analyze_hypergeometric_probability_question(question_text: str):
    """Rozpoznaje zadanie 'losujemy k elementow BEZ ZWRACANIA z populacji
    2 kategorii (N1,N2), pytanie o prawdopodobienstwo zdarzenia
    okreslonego liczba elementow danej kategorii wsrod wylosowanych'.
    Zwraca {"n1","n2","k","event"} albo None (nie rozpoznano - abstain).
    `event` to jeden z:
      {"kind": "same_category"}          - "oba/wszystkie tego samego koloru"
      {"kind": "different_category"}     - "rozne kolory" (co najmniej 1 z kazdej)
      {"kind": "exactly", "which": 1|2, "j": int} - "dokladnie j <kategoria>"."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text)
    if not _HYPERGEOM_WITHOUT_REPLACEMENT_RE.search(text):
        return None
    cats = _extract_hypergeom_categories(text)
    if not cats:
        return None
    (n1, words1), (n2, words2) = cats

    m = _HYPERGEOM_DRAW_RE.search(text)
    if not m:
        return None
    k = _hypergeom_cardinal(m.group(1))
    if not k or k <= 0 or k > n1 + n2:
        return None

    if _HYPERGEOM_SAME_CATEGORY_RE.search(text):
        event = {"kind": "same_category"}
    elif _HYPERGEOM_DIFFERENT_CATEGORY_RE.search(text):
        event = {"kind": "different_category"}
    else:
        m2 = _HYPERGEOM_EXACTLY_RE.search(text)
        if not m2:
            return None
        j = _hypergeom_cardinal(m2.group(1))
        label = m2.group(2)
        if j is None:
            return None
        if _hypergeom_label_matches(label, words1):
            which = 1
        elif _hypergeom_label_matches(label, words2):
            which = 2
        else:
            return None
        event = {"kind": "exactly", "which": which, "j": j}

    return {"n1": n1, "n2": n2, "k": k, "event": event}


def _hypergeom_pmf(n_a, n_b, k, j):
    """P(dokladnie j elementow kategorii A wsrod k losowan bez zwracania
    z populacji n_a+n_b) - standardowy wzor rozkladu hipergeometrycznego,
    DOWOLNE n_a/n_b/k/j (nie hardcodowane liczby)."""
    n_total = n_a + n_b
    if j < 0 or j > k or j > n_a or (k - j) > n_b or k > n_total:
        return sp.Integer(0)
    return sp.Rational(int(sp.binomial(n_a, j) * sp.binomial(n_b, k - j)), int(sp.binomial(n_total, k)))


def verify_hypergeometric_probability_question(question_text: str, options: list):
    """Warstwa 2: liczy PRAWDZIWE prawdopodobienstwo wzorem
    hipergeometrycznym i porownuje MATEMATYCZNIE (sympy) z opcjami - ten
    sam kontrakt co pozostale verify_X_question (match_index/
    no_option_matches/unverifiable)."""
    parsed = analyze_hypergeometric_probability_question(question_text)
    if not parsed:
        return {"status": "unverifiable"}
    n1, n2, k = parsed["n1"], parsed["n2"], parsed["k"]
    event = parsed["event"]
    try:
        if event["kind"] == "same_category":
            true_value = _hypergeom_pmf(n1, n2, k, k) + _hypergeom_pmf(n2, n1, k, k)
        elif event["kind"] == "different_category":
            p_same = _hypergeom_pmf(n1, n2, k, k) + _hypergeom_pmf(n2, n1, k, k)
            true_value = 1 - p_same
        elif event["kind"] == "exactly":
            j = event["j"]
            if event["which"] == 1:
                true_value = _hypergeom_pmf(n1, n2, k, j)
            else:
                true_value = _hypergeom_pmf(n2, n1, k, j)
        else:
            return {"status": "unverifiable"}
        true_value = sp.nsimplify(true_value)
    except Exception:
        return {"status": "unverifiable"}
    return _match_single_value_option(true_value, options)


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

    result4 = verify_trig_special_angle_question(question_text, options)
    if result4["status"] in ("match_index", "no_option_matches"):
        return {**result4, "explanation": None}

    result5 = verify_hypergeometric_probability_question(question_text, options)
    if result5["status"] in ("match_index", "no_option_matches"):
        return {**result5, "explanation": None}

    # NAPRAWIONE: Etap 8 (funkcje - liniowa/kwadratowa-jako-funkcja/
    # wykladnicza) mial gotowe, przetestowane funkcje Warstwy 2, ale
    # NIGDY nie zostaly podlaczone tutaj - byly wywolywane tylko
    # bezposrednio w testach jednostkowych, nigdy w prawdziwym potoku
    # Quiz/Sprawdzian. Skutek: cala Warstwa 2 dla funkcji byla martwym
    # kodem w produkcji (Warstwa 3/tiery dzialaly, ale bez niezaleznej
    # weryfikacji poprawnosci klucza odpowiedzi).
    result6 = verify_linear_function_evaluate(question_text, options)
    if result6["status"] in ("match_index", "no_option_matches"):
        return {**result6, "explanation": None}

    result7 = verify_linear_two_points_question(question_text, options)
    if result7["status"] in ("match_index", "no_option_matches"):
        return {**result7, "explanation": None}

    result8 = verify_quadratic_function_vertex(question_text, options)
    if result8["status"] in ("match_index", "no_option_matches"):
        return {**result8, "explanation": None}

    result9 = verify_exponential_function_evaluate(question_text, options)
    if result9["status"] in ("match_index", "no_option_matches"):
        return {**result9, "explanation": None}

    result10 = verify_exponential_same_base_equation(question_text, options)
    if result10["status"] in ("match_index", "no_option_matches"):
        return {**result10, "explanation": None}

    return {"status": "unverifiable", "explanation": None}
