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
import random
import sympy as sp
from sympy import Eq, Poly, S, Symbol
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor,
)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

_EQ_IN_DOLLARS = re.compile(r'\$([^$]+)\$')

# Unicode operatory bez LaTeX odpowiednika juz obslugiwanego w _clean_latex
# (ktore ma tam tylko "\leq"/"\geq" - forme LaTeX, nie znak unicode).
_UNICODE_OPERATOR_MAP = str.maketrans({
    "≤": "<=",  # ≤
    "≥": ">=",  # ≥
    "∞": "oo",  # ∞ (sympy rozpoznaje "oo" jako nieskonczonosc)
})


def _clean_latex(s: str) -> str:
    """Zamienia najczestsze konstrukcje LaTeX na skladnie parsowalna przez sympy."""
    s = s.strip().strip('$').strip()
    s = s.replace('\\left', '').replace('\\right', '')
    # NAPRAWIONE (audyt realnej generacji, trygonometria): "\pi" (LaTeX)
    # nie bylo w ogole normalizowane - sympy parse_expr rozpoznaje bare
    # "pi" jako sp.pi natywnie, ale zostawiony backslash psul parsowanie
    # calkowicie (SyntaxError). Bez tego kazdy argument w radianach
    # (np. "\frac{\pi}{6}") byl nieparsowalny.
    s = s.replace('\\pi', 'pi')
    s = s.replace('\\cdot', '*').replace('\\times', '*').replace('·', '*')
    # NAPRAWIONE (audyt realnej generacji, sierpien 2026): "\sqrt{...}"
    # NIGDZIE nie bylo normalizowane w calym module - sympy rozpoznaje
    # bare "sqrt(...)" natywnie, ale zostawiony "\sqrt{" psul parsowanie
    # CALKOWICIE (SyntaxError), tak samo jak nieobslugiwane "\pi" wyzej.
    # To dotyczylo KAZDEJ opcji odpowiedzi z pierwiastkiem (np. "$\frac{
    # \sqrt{2}}{2}$" - bardzo czeste w trygonometrii/deltcie rownan
    # kwadratowych) w CALYM potoku _parse_expr/_clean_latex - opcja z
    # pierwiastkiem po prostu nigdy sie nie parsowala (any_parsed=False
    # dla NIEJ, choc inne opcje bez pierwiastka mogly sie parsowac, co
    # prowadzilo do falszywego "no_option_matches" mimo obecnosci
    # poprawnej odpowiedzi). MUSI byc PRZED petla \frac ponizej - inaczej
    # zagniezdzone "\frac{\sqrt{2}}{2}" nie dopasowuje sie do regexu frac
    # (klamry \sqrt psuja parowanie [^{}]*).
    for _ in range(3):
        s = re.sub(r'\\sqrt\{([^{}]*)\}', r'sqrt(\1)', s)
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
    # NAPRAWIONE (przy tej samej okazji): pozostale czeste unicode
    # operatory - LaTeX "\leq"/"\geq" juz obslugiwane wyzej, ale nie ich
    # unicode odpowiedniki (ten sam wzorzec luki co przy "!="/superscript
    # powyzej). Nieskonczonosc (unicode) -> "oo", ktore sympy rozpoznaje
    # natywnie w parse_expr.
    s = s.translate(_UNICODE_OPERATOR_MAP)
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
    B = parsed["B"]
    if param in B.free_symbols and B != param:
        # NAPRAWIONE (audyt realnej generacji V1, sierpien 2026): parametr
        # WEWNATRZ WYRAZENIA jako wspolczynnik przy x (np. "(m-4)x",
        # "(2m-1)x", "(4-m)x"), nie sam parametr ("mx"). Wymaga rozwiniecia
        # kwadratu dwumianu PRZED policzeniem delty (delta =
        # (wyrazenie)^2 - 4AC) - realny test (n=10/20, "sredni") pokazal
        # AI systematycznie zgaduje "ladny", symetryczny przedzial (np.
        # "m<2 lub m>6") zamiast poprawnie rozwinac kwadrat i podac
        # prawdziwy (czesto niesymetryczny/niewymierny) wynik - ~70-90%
        # bledny klucz dla tego podwzorca mimo oznaczenia "sredni". Ten
        # sam wzorzec fixu co linijka wyzej (parametr w A) i co wczesniej
        # w tej sesji dla "parametr jako wspolczynnik przy x^2".
        return "7-8"
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


# =================================================================
# STANDARD ARCHITEKTONICZNY (sierpien 2026, obowiazuje w CALYM systemie -
# Quiz i Sprawdzian, wszystkie tematy): BACKEND (kod) JEST ZRODLEM PRAWDY
# DLA LICZB - AI NIGDY nie decyduje "ile juz mamy" ani "ile brakuje".
#
# Zasada: AI generuje TRESC (pytania/dystraktory/wyjasnienia), ale KAZDA
# liczba uzywana do sterowania przeplywem (ile zaakceptowano, ile brakuje,
# ile prosic w kolejnej rundzie) jest liczona WYLACZNIE przez prosty kod
# (len() na FAKTYCZNIE zweryfikowanej/zaakceptowanej liscie), NIGDY nie
# jest odczytywana z odpowiedzi AI ani AI nie jest pytane "ile
# wygenerowales". Konkretnie, w petli dogenerowania (patrz
# _verify_and_fill_quiz_math w openai_exam.py i
# _fill_missing_exam_questions w exam_pdf_generator.py - obie maja
# IDENTYCZNY wzorzec):
#     current = len(zaakceptowane_pytania)          # KOD liczy, nie AI
#     missing = requested_count - current            # KOD liczy brak
#     extra = regenerate(missing)                     # KOD mowi AI ile ma dogenerowac
# Po kazdej rundzie dogenerowania stosuje sie DOKLADNIE ta sama weryfikacja
# (Warstwa 1/2/3 + Diversity Engine) co do pierwszej partii - AI nie
# dostaje "kredytu zaufania" za to, ze to runda uzupelniajaca. Na koncu
# ewentualna nadwyzka (rundy licza brakujace NIEZALEZNIE, wiec drobny
# nadmiar jest mozliwy) jest przycinana rowniez PRZEZ KOD (slice/pop),
# nigdy przez prosbe do AI "zostaw tylko N".
#
# Dlaczego to wazne: to DOKLADNIE ten sam powod co przy Safe Parameter
# Generation ponizej - AI jest DOBRE w tresci, ale NIEWIARYGODNE jako
# zrodlo prawdy dla liczb/matematyki pod presja (np. moze "zgubic" ile
# faktycznie wygenerowalo w duzej partii, albo zaokraglic). Safe Parameter
# Generation stosuje te zasade do POJEDYNCZEGO wyniku matematycznego
# (kod liczy warunek na Delte, nie AI) - ta sekcja opisuje TA SAMA zasade
# zastosowana do LICZENIA CALEJ PARTII zadan. Zweryfikowane realnym
# testem (audyt Sprawdzian, user zglosil 13 zamowionych / 8 dostarczonych)
# - przyczyna NIE byla w tej logice (juz poprawna, identyczna w Quizie
# i Sprawdzianie), tylko w brakujacych Sprawdzianowi mechanizmach
# (Diversity Engine/Safe Param Gen/bufor/timeout) ponizej - po ich
# dodaniu realny test potwierdzil 13/13.
# =================================================================


# ---------------------------------------------------------------
# SAFE PARAMETER GENERATION (sierpien 2026) - dla JEDNEGO, potwierdzonego
# realnymi testami najtrudniejszego podwzorca: rownanie x^2+mx+C=0,
# parametr JAKO GOLY WSPOLCZYNNIK LINIOWY (nie w wyrazie wolnym, nie
# wewnatrz wyrazenia - te dzialaja juz dobrze, NIE SA tu ruszane).
#
# Odwrocenie kolejnosci: zamiast prosic AI o wygenerowanie CALEGO
# pytania (rownanie + policzenie warunku Delta>0 + opcje) i dopiero
# POTEM sprawdzac czy AI policzylo poprawnie (co dawalo ~50% odrzucen
# w realnych testach - AI systematycznie gubilo czynnik 4 albo
# wybieralo C, dla ktorego prawdziwa granica jest niewymierna, np.
# C=20 -> 2*sqrt(20), i tak zgadywalo "ladna" bledna liczbe), KOD
# (nie AI) wybiera C ze zbioru KWADRATOW IDEALNYCH - gwarantuje to, ze
# 2*sqrt(C) jest ZAWSZE liczba calkowita - i liczy PRAWDZIWY warunek
# PRZEZ ISTNIEJACY solve_discriminant_condition (bez duplikowania
# logiki). AI dostaje JUZ POPRAWNY wynik i ma TYLKO sformulowac
# pytanie + wymyslic 3 bledne dystraktory - nie liczy juz samej
# matematyki, wiec nie ma jak jej pomylic.
_SAFE_PERFECT_SQUARES = [1, 4, 9, 16, 25, 36, 49, 64, 81, 100]
_SAFE_PARAM_LETTERS = list("mnpqrstkbc")


def pick_safe_param_values(pool: list, used: set, count: int) -> list:
    """Losuje `count` wartosci z `pool`, BEZ POWTORZEN wzgledem `used`
    (mutowany w miejscu - kolejne wywolania, np. w kolejnych rundach
    dogenerowania TEGO SAMEGO dokumentu, "widza" juz zuzyte wartosci).

    NAPRAWIONE (user zglosil: Pytanie 6 i 7 w wygenerowanym Sprawdzianie
    uzywaly IDENTYCZNEJ stalej C=25, rozne tylko litery parametru) -
    dotychczas litery byly losowane bez powtorzen TYLKO w obrebie
    jednej partii (jednego wywolania _raw_generate_safe_linear_param_quadratic_batch),
    a stale C w ogole (random.choice z powtorzeniami, nawet w obrebie
    jednej partii) - zaden z nich nie pamietal, co zostalo juz uzyte w
    POPRZEDNIEJ partii (np. pierwsza generacja + runda dogenerowania to
    DWA OSOBNE wywolania w tym samym dokumencie). Te dwa
    zestawy-dystraktory sa dokladnie tym samym schematem, ktory
    Diversity Engine celowo POMIJA dla _safe_generated (patrz
    _verify_and_fix_exam_math/_verify_and_fix_quiz_math) - wiec bez
    tego mechanizmu nic innego nie chronilo przed powtorzeniem stalej.

    Jesli pula (10 liter / 10 kwadratow) wyczerpie sie w obrebie
    JEDNEGO dokumentu (rzadkie - trzeba by >10 zadan tego podwzorca w
    jednym sprawdzianie/quizie) - dopiero WTEDY dopuszczamy powtorzenia
    (cyklicznie), bo unikniecie ich staje sie matematycznie niemozliwe."""
    fresh = [v for v in pool if v not in used]
    random.shuffle(fresh)
    fallback = list(pool)
    random.shuffle(fallback)
    picks = []
    for i in range(count):
        v = fresh[i] if i < len(fresh) else fallback[i % len(fallback)]
        picks.append(v)
    used.update(picks)
    return picks


def build_safe_linear_param_quadratic(param_letter: str = None, c_value: int = None) -> dict:
    """Buduje JEDEN bezpieczny (gwarantowanie poprawny) szkielet pytania
    dla x^2 + {param}x + {C} = 0 (parametr jako goly wspolczynnik
    liniowy). C dobierany z kwadratow idealnych, jesli nie podano -
    gwarantuje wymierna (calkowita) granice 2*sqrt(C). Warunek liczony
    PRZEZ solve_discriminant_condition (ten sam kod co Warstwa 2 dla
    zwyklej weryfikacji - zero duplikacji logiki). Zwraca dict z
    gotowym tekstem pytania, poprawnym tekstem odpowiedzi i surowym
    sympy Set (do ewentualnej dalszej weryfikacji)."""
    if c_value is None:
        c_value = random.choice(_SAFE_PERFECT_SQUARES)
    if param_letter is None:
        param_letter = random.choice(_SAFE_PARAM_LETTERS)
    param = Symbol(param_letter)
    true_set = solve_discriminant_condition(S.One, param, sp.Integer(c_value), param, 'pos')
    bound = int(2 * sp.sqrt(c_value))
    correct_text = f"${param_letter} < -{bound}$ lub ${param_letter} > {bound}$"
    question_text = (
        f"Dla jakich wartości parametru {param_letter} równanie "
        f"$x^2 + {param_letter}x + {c_value} = 0$ ma dwa różne pierwiastki?"
    )
    return {
        "param_letter": param_letter,
        "c_value": c_value,
        "bound": bound,
        "question": question_text,
        "correct_text": correct_text,
        "true_set": true_set,
    }


# SAFE PARAMETER GENERATION - TRYGONOMETRIA (29.08.2026) - PORT tego
# samego wzorca (patrz komentarz nad build_safe_linear_param_quadratic)
# na DRUGI, potwierdzony realnymi testami najtrudniejszy podwzorzec:
# rownanie A*sin^2(x) + B*cos(x) + C = 0 na x w [0, 2pi), sprowadzalne
# do rownania kwadratowego wzgledem cos(x) (podstawienie sin^2=1-cos^2).
#
# User (real-test, trudna trygonometria, 29.08.2026): "bez jaj nie
# mozemy tak zrobic ze czekac 5 minut na sprawdzian musimy miec inne
# rozwiazanie" - podnoszenie budzetu czasowego bylo leczeniem objawu.
# Logi tego samego dnia pokazaly PRAWDZIWA przyczyne: AI samo, WOLNO
# generujac trudna trygonometrie, WIELOKROTNIE probowalo dokladnie TEGO
# podwzorca (np. "2sin^2(x) - 3cos(x) = 0" pojawilo sie w TRZECH
# oddzielnych rundach tego samego dnia, za kazdym razem w innym,
# czesto blednym warioncie) - to jest wiec NIE hipotetyczny, tylko
# NAJCZESCIEJ generowany i NAJCZESCIEJ psuty archetyp dla tego tematu.
#
# Jak przy rownaniach kwadratowych: zamiast prosic AI o wymyslenie
# CALEGO zadania (rownanie + rozwiazanie) i sprawdzac POTEM czy policzylo
# poprawnie, KOD wybiera "ladny" kat (cos ktorego jest liczba wymierna z
# malej puli: 1/2 lub -1/2) jako JEDYNY poprawny pierwiastek u0, oraz
# DRUGI pierwiastek u1 CELOWO POZA [-1,1] (wiec automatycznie odrzucany
# jako niepoprawny dla cosinusa - dokladnie ten sam mechanizm, ktory
# organicznie wystapil w prawdziwym przykladzie AI: cos(x)=-2 zostal
# odrzucony, zostawiajac TYLKO cos(x)=1/2). Z Vieta: A*u^2 - B*u -
# (A+C) = 0 ma pierwiastki u0,u1 <=> B = A*(u0+u1), C = -A*(u0*u1+1).
# A jest ZAWSZE parzyste (pula {2,4,6,8}) - to GWARANTUJE, ze B i C
# wyjda CALKOWITE (u0 ma mianownik 2), bez zadnego zaokraglania.
_TRIG_QUADRATIC_NICE_COS = [sp.Rational(1, 2), sp.Rational(-1, 2)]
# arccos(1/2) = pi/3, arccos(-1/2) = 2pi/3 - drugie rozwiazanie na
# [0, 2pi) to zawsze 2*pi - arccos(u0) (symetria cosinusa).
_TRIG_QUADRATIC_ANGLE_TEXT = {
    sp.Rational(1, 2): (r"\frac{\pi}{3}", r"\frac{5\pi}{3}"),
    sp.Rational(-1, 2): (r"\frac{2\pi}{3}", r"\frac{4\pi}{3}"),
}
_TRIG_QUADRATIC_A_POOL = [2, 4, 6, 8]
_TRIG_QUADRATIC_EXTRANEOUS_POOL = [-3, -2, 2, 3]

# DYSTRAKTORY LICZONE KODEM (nie przez AI) - user: "dystraktory (błędne
# opcje) - to też można liczyć kodem, nie wymyślać przez AI... to jest
# drugie miejsce, gdzie wpuszczacie niepewność, obok samego rozwiązania".
# Pelna pula "ladnych" katow z ich symetrycznym drugim rozwiazaniem na
# [0, 2pi) - dokladnie takiego ksztaltu bledne opcje AI generowalo
# organicznie w real-logach tego samego dnia (np. "x = pi/4, 7pi/4"
# jako bledna opcja dla poprawnego "x = pi/3, 5pi/3"). Dystraktory =
# 3 INNE katy z tej puli (rozne od poprawnego) - deterministycznie
# roznia sie od poprawnej odpowiedzi (inny kat), wiec NIE MOGA
# przypadkiem kolidowac z poprawnym wynikiem (co bylo realnym ryzykiem
# przy "AI, wymysl 3 blednych dystraktorow").
_TRIG_QUADRATIC_ALL_ANGLES = {
    sp.Rational(1, 6): (r"\frac{\pi}{6}", r"\frac{11\pi}{6}"),
    sp.Rational(1, 4): (r"\frac{\pi}{4}", r"\frac{7\pi}{4}"),
    sp.Rational(1, 3): (r"\frac{\pi}{3}", r"\frac{5\pi}{3}"),
    sp.Rational(1, 2): (r"\frac{\pi}{2}", r"\frac{3\pi}{2}"),
    sp.Rational(2, 3): (r"\frac{2\pi}{3}", r"\frac{4\pi}{3}"),
    sp.Rational(3, 4): (r"\frac{3\pi}{4}", r"\frac{5\pi}{4}"),
    sp.Rational(5, 6): (r"\frac{5\pi}{6}", r"\frac{7\pi}{6}"),
}
# u0 (poprawne cos(x)) mapuje sie na "ulamek kata" pi/3 dla u0=1/2 i
# 2pi/3 dla u0=-1/2 - klucz do _TRIG_QUADRATIC_ALL_ANGLES.
_TRIG_QUADRATIC_U0_TO_ANGLE_FRACTION = {
    sp.Rational(1, 2): sp.Rational(1, 3),
    sp.Rational(-1, 2): sp.Rational(2, 3),
}


def build_safe_trig_quadratic_distractors(u0) -> list:
    """Zwraca 3 TEKSTOWO gotowe, bledne opcje (kazda w formacie
    "x = A, x = B", identycznym jak correct_text) - kazda uzywa INNEGO
    "ladnego" kata niz poprawna odpowiedz, wiec z definicji nie moze
    byc matematycznie rowna poprawnemu wynikowi. Deterministyczne (poza
    losowym WYBOREM ktorych 3 z 6 pozostalych katow uzyc) - zero AI."""
    correct_fraction = _TRIG_QUADRATIC_U0_TO_ANGLE_FRACTION[u0]
    other_fractions = [f for f in _TRIG_QUADRATIC_ALL_ANGLES if f != correct_fraction]
    chosen = random.sample(other_fractions, 3)
    return [f"x = {a}, x = {b}" for a, b in (_TRIG_QUADRATIC_ALL_ANGLES[f] for f in chosen)]


def build_safe_trig_quadratic_equation(u0=None, u1: int = None, a_coeff: int = None) -> dict:
    """Buduje JEDEN bezpieczny (gwarantowanie poprawny) szkielet zadania
    dla A*sin^2(x) + B*cos(x) + C = 0 na x w [0, 2pi) - patrz komentarz
    wyzej po pelne uzasadnienie. A/B/C sa WYLICZONE z wybranych
    pierwiastkow u0 (poprawny, w [-1,1]) i u1 (odrzucany, poza [-1,1])
    PRZEZ wzory Viete'a - poprawnosc jest gwarantowana przez konstrukcje,
    nie przez AI ani przez ponowne rozwiazywanie rownania. Zwraca dict z
    gotowym tekstem rownania (LaTeX) i poprawnym tekstem odpowiedzi."""
    if u0 is None:
        u0 = random.choice(_TRIG_QUADRATIC_NICE_COS)
    if u1 is None:
        pool = [v for v in _TRIG_QUADRATIC_EXTRANEOUS_POOL if v != u0]
        u1 = random.choice(pool)
    if a_coeff is None:
        a_coeff = random.choice(_TRIG_QUADRATIC_A_POOL)
    A = a_coeff
    B = int(A * (u0 + u1))
    C = int(-A * (u0 * u1 + 1))
    b_sign = '+' if B >= 0 else '-'
    equation_latex = f"{A}\\sin^2(x) {b_sign} {abs(B)}\\cos(x)"
    if C > 0:
        equation_latex += f" + {C}"
    elif C < 0:
        equation_latex += f" - {abs(C)}"
    equation_latex += " = 0"
    angle1, angle2 = _TRIG_QUADRATIC_ANGLE_TEXT[u0]
    correct_text = f"x = {angle1}, x = {angle2}"
    distractors = build_safe_trig_quadratic_distractors(u0)
    return {
        "A": A, "B": B, "C": C, "u0": u0, "u1": u1,
        "equation_latex": equation_latex,
        "correct_text": correct_text,
        "distractors": distractors,
    }


# SAFE PARAMETER GENERATION - TRYGONOMETRIA, DRUGI ARCHETYP (29.08.2026,
# user: "rozwin" - rozszerzenie po pierwszym udanym real-tescie 15/15).
# "Dla jakich wartosci parametru {litera} rownanie {sin/cos/tan}(x)={litera}
# ma rozwiazanie?" - DRUGI, obok rownania kwadratowego wzgledem cos(x),
# najczesciej wystepujacy w dzisiejszych real-logach wzorzec ("Dla
# jakich wartosci parametru a rownanie sin(x)=a...", "...parametru b
# rownanie tan(x)=b...") - i tez czesto psuty (AI mylilo dziedzine
# tan(x) - ktora jest zbiorem WSZYSTKICH liczb rzeczywistych - z
# dziedzina sin/cos, ktora jest ograniczona do [-1,1]).
# Odpowiedz zalezy WYLACZNIE od wybranej funkcji (sin/cos -> [-1,1],
# tan -> R) - zero obliczen, czysta tabela faktow, wiec zero ryzyka
# bledu AI od samego poczatku (nawet bezpieczniejsze niz pierwszy
# archetyp, ktory przynajmniej wymagal Viete'a).
_TRIG_SOLVABILITY_FUNCS = ["sin", "cos", "tan"]
_TRIG_SOLVABILITY_LETTERS = list("abcmk")
_TRIG_SOLVABILITY_BOUNDED_CORRECT = r"${letter} \in [-1, 1]$"
_TRIG_SOLVABILITY_BOUNDED_DISTRACTORS = [
    r"${letter} \in (-1, 1)$",
    r"${letter} \in [0, 1]$",
    r"${letter} \in (-\infty, -1) \cup (1, \infty)$",
    r"${letter} \in [-2, 2]$",
    r"${letter} \in \mathbb{{R}}$",
]
_TRIG_SOLVABILITY_UNBOUNDED_CORRECT = r"${letter} \in \mathbb{{R}}$"
_TRIG_SOLVABILITY_UNBOUNDED_DISTRACTORS = [
    r"${letter} \in [-1, 1]$",
    r"${letter} \in (-1, 1)$",
    r"${letter} \in [0, \infty)$",
    r"${letter} \in (-\infty, 0]$",
    r"${letter} \in [-2, 2]$",
]


def build_safe_trig_solvability_range(func: str = None, letter: str = None) -> dict:
    """Buduje JEDEN bezpieczny szkielet zadania 'dla jakich wartosci
    parametru {letter} rownanie {func}(x)={letter} ma rozwiazanie' - patrz
    komentarz wyzej. Zero obliczen (czysta tabela faktow o dziedzinach
    funkcji trygonometrycznych) - poprawnosc jest oczywista z definicji
    funkcji, nie wymaga nawet niezaleznej weryfikacji sympy."""
    if func is None:
        func = random.choice(_TRIG_SOLVABILITY_FUNCS)
    if letter is None:
        letter = random.choice(_TRIG_SOLVABILITY_LETTERS)
    if func in ("sin", "cos"):
        correct_text = _TRIG_SOLVABILITY_BOUNDED_CORRECT.format(letter=letter)
        distractor_pool = _TRIG_SOLVABILITY_BOUNDED_DISTRACTORS
    else:
        correct_text = _TRIG_SOLVABILITY_UNBOUNDED_CORRECT.format(letter=letter)
        distractor_pool = _TRIG_SOLVABILITY_UNBOUNDED_DISTRACTORS
    distractors = [d.format(letter=letter) for d in random.sample(distractor_pool, 3)]
    question_text = (
        f"Dla jakich wartości parametru {letter} równanie "
        f"$\\{func}(x) = {letter}$ ma rozwiązanie?"
    )
    return {
        "func": func, "letter": letter,
        "question_text": question_text,
        "correct_text": correct_text,
        "distractors": distractors,
    }


# SAFE PARAMETER GENERATION - CIAGI ARYTMETYCZNE, TRUDNY (29.08.2026,
# user: "rozszerz... aby caly system byl profesjonalny" - kontynuacja
# tego samego wzorca na kolejny temat po trygonometrii). Archetyp
# wybrany na podstawie OFICJALNEGO, juz istniejacego w tym systemie
# kryterium poziomu 4-5 dla ciagow (patrz SEQUENCE_DIFFICULTY_TIERS w
# level_config.py): "Uklad DWOCH warunkow jednoczesnie... dwa rozne
# wyrazy ciagu" - przyklad tam wprost: "W ciagu arytmetycznym a3=10,
# a7=22. Wyznacz pierwszy wyraz i roznice." - DOKLADNIE ten wzorzec.
#
# KOD wybiera a1 i r (pierwszy wyraz i roznica) JAKO PIERWSZE, liczy
# PRAWDZIWE wartosci dwoch wyrazow a_m, a_n z tych parametrow (m<n,
# oba >= 2 - patrz nizej dlaczego), i DOPIERO wtedy formuluje pytanie
# "podane sa a_m i a_n, wyznacz a1 i r" - student (i AI formulujace
# pytanie) widzi problem w ODWROTNEJ kolejnosci niz go zbudowano,
# ale poprawnosc jest gwarantowana przez konstrukcje (identyczny
# wzorzec co build_safe_linear_param_quadratic/
# build_safe_trig_quadratic_equation).
_SEQ_A1_POOL = list(range(-9, 10))  # -9..9, wyklucza tylko przez retry a1==r
_SEQ_R_POOL = [v for v in range(-6, 7) if v != 0]  # roznica NIGDY 0 (nie byloby "ciagiem" w praktyce zadania)
_SEQ_INDEX_POOL = list(range(2, 10))  # m,n >= 2 - GWARANTUJE a_m != a1 (patrz distraktor 3 nizej)


def build_safe_sequence_two_terms(a1: int = None, r: int = None, m: int = None, n: int = None) -> dict:
    """Buduje JEDEN bezpieczny szkielet zadania 'w ciagu arytmetycznym
    a_m=X, a_n=Y - wyznacz pierwszy wyraz i roznice' (patrz komentarz
    wyzej). a1/r wybrane PRZED policzeniem a_m/a_n - poprawnosc
    gwarantowana przez konstrukcje, nie przez odwrotne rozwiazywanie
    ukladu rownan (student/AI musi to zrobic, kod nie musi)."""
    if a1 is None:
        a1 = random.choice(_SEQ_A1_POOL)
    if r is None:
        r = random.choice(_SEQ_R_POOL)
        while r == a1:  # unika kolizji z dystraktorem 1 (zamiana a1<->r)
            r = random.choice(_SEQ_R_POOL)
    if m is None or n is None:
        m, n = sorted(random.sample(_SEQ_INDEX_POOL, 2))
    a_m_val = a1 + (m - 1) * r
    a_n_val = a1 + (n - 1) * r
    correct_text = f"a_1 = {a1}, r = {r}"
    # DYSTRAKTORY - typowe, realne bledy uczniow przy tym wzorcu (nie
    # losowy tekst): (1) zamiana a1 i r miejscami, (2) zly znak roznicy,
    # (3) potraktowanie PIERWSZEGO podanego wyrazu jako a1 wprost
    # (zapomnienie przesuniecia o (m-1)) - m>=2 gwarantuje, ze a_m_val
    # jest RZECZYWISCIE inne od a1, wiec ten dystraktor nigdy nie
    # koliduje z poprawna odpowiedzia.
    distractors = [
        f"a_1 = {r}, r = {a1}",
        f"a_1 = {a1}, r = {-r}",
        f"a_1 = {a_m_val}, r = {r}",
    ]
    question_text = (
        f"W ciągu arytmetycznym $a_{{{m}}} = {a_m_val}$, $a_{{{n}}} = {a_n_val}$. "
        f"Wyznacz pierwszy wyraz i różnicę tego ciągu."
    )
    return {
        "a1": a1, "r": r, "m": m, "n": n, "a_m_val": a_m_val, "a_n_val": a_n_val,
        "question_text": question_text,
        "correct_text": correct_text,
        "distractors": distractors,
    }


# SAFE PARAMETER GENERATION - TWIERDZENIE COSINUSOW, TRUDNY (29.08.2026,
# user: "rozpiszmy to porzadnie, krok po kroku" - trzecie rozszerzenie
# tego samego dnia). Archetyp z OFICJALNEGO przykladu w level_config.py
# (technikum_3/liceum_3, "PRZYKLADY TRUDNYCH ZADAN"): "W trojkacie boki
# maja dlugosc a=7, b=9, kat miedzy nimi gamma=50°. Oblicz dlugosc
# trzeciego boku oraz pole trojkata." - w ODROZNIENIU od trygonometrii
# (rownania) i ciagow, kat gamma tu jest CELOWO "nieladny" (50°, nie
# 30/45/60/90) - dokladnie jak w oficjalnym przykladzie, wiec wynik jest
# NATURALNIE przyblizeniem dziesietnym (userzy uzywaja kalkulatora), nie
# czysta liczba wymierna/pierwiastkiem - stad zaokraglanie do 2 miejsc +
# tolerancja +-0.01 zamiast dokladnego dopasowania tekstu jak wczesniej.
#
# Decyzja architektoniczna (ustalona z userem PRZED kodowaniem, patrz
# rozmowa): DWA OSOBNE mini-archetypy (bok c ALBO pole P), nie jedno
# pytanie z para "c, P" - mniej ruchomych czesci, kazdy to prosty
# "1 liczba + 3 dystraktory" wzorzec, ktory juz mamy sprawdzony.
_LOC_SIDE_POOL = list(range(4, 16))  # a,b w [4,15]
# Katy CELOWO "nieladne" (bez 30/45/60/90/120/135/150 i sasiadow) -
# dokladnie taki ksztalt, jaki ma oficjalny przyklad programowy (gamma=50°).
_LOC_ANGLE_POOL_DEG = [40, 50, 55, 65, 70, 75, 80, 100, 105, 110, 115, 125, 140, 145, 155]
_LOC_ROUND_DIGITS = 2


def build_safe_law_of_cosines_triangle(a: int = None, b: int = None, gamma_deg: int = None, ask: str = None) -> dict:
    """Buduje JEDEN bezpieczny szkielet zadania o trojkacie SAS (dwa
    boki + kat miedzy nimi) - bok c z twierdzenia cosinusow, POLE
    liczone NIEZALEZNIE ze wzoru $P=\\frac{{1}}{{2}}ab\\sin(\\gamma)$
    (NIE z Herona na podstawie zaokraglonego c - unika propagacji bledu
    zaokraglenia z jednej wartosci do drugiej, ustalone z userem PRZED
    kodowaniem). `ask` ('c' albo 'P') wybiera, o KTORA z dwoch wartosci
    pyta TO KONKRETNE pytanie - druga jest liczona i tak (potrzebna do
    part-of-formula distraktorow), ale nie pojawia sie w tresci."""
    if a is None:
        a = random.choice(_LOC_SIDE_POOL)
    if b is None:
        b = random.choice(_LOC_SIDE_POOL)
    if gamma_deg is None:
        gamma_deg = random.choice(_LOC_ANGLE_POOL_DEG)
    if ask is None:
        ask = random.choice(["c", "P"])
    gamma_rad = sp.rad(gamma_deg)
    cos_g = sp.cos(gamma_rad)
    sin_g = sp.sin(gamma_rad)
    c_val = round(float(sp.sqrt(a ** 2 + b ** 2 - 2 * a * b * cos_g)), _LOC_ROUND_DIGITS)
    area_val = round(float(sp.Rational(1, 2) * a * b * sin_g), _LOC_ROUND_DIGITS)
    # DYSTRAKTORY - typowe, realne bledy uczniow (nie losowy tekst),
    # osobna klasa dla c i dla P (ustalone z userem PRZED kodowaniem):
    c_pyth = round(float(sp.sqrt(a ** 2 + b ** 2)), _LOC_ROUND_DIGITS)  # pomylony wzor z Pitagorasem (calkowicie pominiety kat)
    c_sign = round(float(sp.sqrt(abs(a ** 2 + b ** 2 + 2 * a * b * cos_g))), _LOC_ROUND_DIGITS)  # zly znak przy cos(gamma)
    c_rad_confuse = round(float(sp.sqrt(abs(a ** 2 + b ** 2 - 2 * a * b * sp.cos(gamma_deg)))), _LOC_ROUND_DIGITS)  # cos(gamma_deg) w RADIANACH zamiast stopni
    # abs() - identyczny powod co przy area_rad_confuse ponizej: cos(gamma)
    # jest UJEMNY dla katow rozwartych (>90°) - bez abs() ten dystraktor
    # bylby oczywiscie bledny (pole nie moze byc ujemne), wiec przestalby
    # byc realistyczna pulapka.
    area_cos_confuse = round(abs(float(sp.Rational(1, 2) * a * b * cos_g)), _LOC_ROUND_DIGITS)  # cos zamiast sin (pomylony wzor z bokiem)
    area_no_half = round(float(a * b * sin_g), _LOC_ROUND_DIGITS)  # brak dzielenia przez 2
    # abs() - pole NIGDY nie moze wygladac na ujemne w opcji odpowiedzi
    # (sin(gamma_deg potraktowany jako radiany) moze wypasc ujemny dla
    # niektorych katow - user by od razu odrzucil oczywiscie bledna,
    # ujemna opcje, co oslabia dystraktor jako "realistyczna pulapke").
    area_rad_confuse = round(abs(float(sp.Rational(1, 2) * a * b * sp.sin(gamma_deg))), _LOC_ROUND_DIGITS)  # sin(gamma_deg) w radianach
    if ask == "c":
        correct_text = f"{c_val:.2f}"
        distractors = [f"{c_pyth:.2f}", f"{c_sign:.2f}", f"{c_rad_confuse:.2f}"]
        question_text = (
            f"W trójkącie boki mają długość $a = {a}$, $b = {b}$, kąt między nimi "
            f"$\\gamma = {gamma_deg}°$. Oblicz długość trzeciego boku $c$ (z dokładnością do dwóch miejsc po przecinku)."
        )
    else:
        correct_text = f"{area_val:.2f}"
        distractors = [f"{area_cos_confuse:.2f}", f"{area_no_half:.2f}", f"{area_rad_confuse:.2f}"]
        question_text = (
            f"W trójkącie boki mają długość $a = {a}$, $b = {b}$, kąt między nimi "
            f"$\\gamma = {gamma_deg}°$. Oblicz pole tego trójkąta (z dokładnością do dwóch miejsc po przecinku)."
        )
    return {
        "a": a, "b": b, "gamma_deg": gamma_deg, "ask": ask,
        "c_val": c_val, "area_val": area_val,
        "question_text": question_text,
        "correct_text": correct_text,
        "distractors": distractors,
    }


def verify_law_of_cosines_triangle(a: int, b: int, gamma_deg: int, ask: str, claimed_text: str) -> bool:
    """Niezalezna weryfikacja (dla testow/audytu, INNA sciezka niz
    build_safe_law_of_cosines_triangle - liczy PRAWDZIWA wartosc od
    zera z surowych a/b/gamma_deg/ask i porownuje z tekstem odpowiedzi
    z tolerancja +-0.01, zgodnie z ustalona z userem konwencja
    zaokraglania)."""
    gamma_rad = sp.rad(gamma_deg)
    if ask == "c":
        true_val = float(sp.sqrt(a ** 2 + b ** 2 - 2 * a * b * sp.cos(gamma_rad)))
    else:
        true_val = float(sp.Rational(1, 2) * a * b * sp.sin(gamma_rad))
    try:
        claimed_val = float(claimed_text)
    except (TypeError, ValueError):
        return False
    return abs(round(true_val, _LOC_ROUND_DIGITS) - claimed_val) <= 0.01


# SAFE PARAMETER GENERATION - CIAGI GEOMETRYCZNE, TRUDNY (29.08.2026,
# user: "robimy, bezpiecznie" - czwarte rozszerzenie tego samego dnia,
# port wzorca z ciagow arytmetycznych - patrz
# build_safe_sequence_two_terms wyzej po pelne uzasadnienie ogolnej
# zasady i oficjalne kryterium poziomu 4-5).
#
# WAZNA ROZNICA wzgledem ciagow arytmetycznych (znaleziona PRZED
# kodowaniem, nie po): a_m=a1+(m-1)r jest UKLADEM LINIOWYM - zawsze
# dokladnie jedno rozwiazanie. a_m=a1*q^(m-1) jest NIELINIOWY -
# q=(a_n/a_m)^(1/(n-m)); jesli q byloby UJEMNE, a (n-m) PARZYSTE, to
# q^(n-m) jest DODATNIE - z SAMYCH a_m,a_n NIE DA SIE jednoznacznie
# odzyskac znaku q (i q, i -q sa spojne z tymi samymi dwoma wyrazami) -
# zadanie mialoby DWIE poprawne odpowiedzi, co jest bledem projektowym,
# nie akceptowalnym uproszczeniem. Naprawiono NIE laataniem przypadku
# brzegowego, tylko usunieciem go u zrodla: q jest TU ZAWSZE dodatnie
# (pula {2,3}, tylko calkowite - bez uzasadnienia dla ulamkow na V1,
# zeby a_m/a_n zawsze wyszly czystymi liczbami calkowitymi, bez
# dodatkowej zlozonosci formatowania ulamkow) - wieloznacznosc znaku q
# jest wiec strukturalnie niemozliwa, nie tylko rzadka.
_GEO_A1_POOL = [v for v in range(-9, 10) if v != 0]
_GEO_Q_POOL = [sp.Integer(2), sp.Integer(3)]
_GEO_INDEX_POOL = list(range(2, 6))  # m,n >= 2 - GWARANTUJE a_m != a1 (jak w ciagach arytmetycznych)


def build_safe_geometric_sequence_two_terms(a1: int = None, q=None, m: int = None, n: int = None) -> dict:
    """Buduje JEDEN bezpieczny szkielet zadania 'w ciagu geometrycznym
    a_m=X, a_n=Y - wyznacz pierwszy wyraz i iloraz' (patrz komentarz
    wyzej). a1/q wybrane PRZED policzeniem a_m/a_n - poprawnosc
    gwarantowana przez konstrukcje, identyczny wzorzec co
    build_safe_sequence_two_terms (ciagi arytmetyczne)."""
    if a1 is None:
        a1 = random.choice(_GEO_A1_POOL)
    if q is None:
        q = random.choice(_GEO_Q_POOL)
        while a1 == q:  # unika kolizji z dystraktorem 1 (zamiana a1<->q) - TYLKO gdy q losowane, nie gdy jawnie podane (testy)
            q = random.choice(_GEO_Q_POOL)
    if m is None or n is None:
        m, n = sorted(random.sample(_GEO_INDEX_POOL, 2))
    a_m_val = int(a1 * q ** (m - 1))
    a_n_val = int(a1 * q ** (n - 1))
    correct_text = f"a_1 = {a1}, q = {q}"
    # DYSTRAKTORY - typowe bledy uczniow (zero AI), analogicznie do
    # ciagow arytmetycznych: (1) zamiana a1<->q, (2) zly znak ilorazu
    # (student "zapomina", ze q w tym zadaniu jest zawsze dodatnie),
    # (3) potraktowanie PIERWSZEGO podanego wyrazu jako a1 wprost.
    distractors = [
        f"a_1 = {q}, q = {a1}",
        f"a_1 = {a1}, q = {-q}",
        f"a_1 = {a_m_val}, q = {q}",
    ]
    question_text = (
        f"W ciągu geometrycznym $a_{{{m}}} = {a_m_val}$, $a_{{{n}}} = {a_n_val}$. "
        f"Wyznacz pierwszy wyraz i iloraz tego ciągu (przyjmij, że iloraz jest dodatni)."
    )
    return {
        "a1": a1, "q": q, "m": m, "n": n, "a_m_val": a_m_val, "a_n_val": a_n_val,
        "question_text": question_text,
        "correct_text": correct_text,
        "distractors": distractors,
    }


def verify_geometric_sequence_two_terms(a1: int, q, m: int, n: int, a_m_val: int, a_n_val: int) -> bool:
    """Niezalezna weryfikacja (dla testow/audytu, INNA sciezka niz
    build_safe_geometric_sequence_two_terms) - sprawdza wprost, czy
    a1*q^(m-1)==a_m_val ORAZ a1*q^(n-1)==a_n_val (rownania, nie
    "solve", bo geometryczny uklad ma wielowartosciowy odwrot dla
    ogolnego q - dokladnie problem opisany w komentarzu wyzej)."""
    return (a1 * q ** (m - 1) == a_m_val) and (a1 * q ** (n - 1) == a_n_val)


def verify_sequence_two_terms(a1: int, r: int, m: int, n: int, a_m_val: int, a_n_val: int) -> bool:
    """Niezalezna weryfikacja (dla testow/audytu, INNA sciezka obliczeniowa
    niz build_safe_sequence_two_terms - rozwiazuje uklad rownan PRZEZ
    sympy zamiast ufac, ze konstrukcja byla poprawna) - sprawdza, czy
    (a1, r) jest JEDYNYM rozwiazaniem ukladu a1+(m-1)*r=a_m_val,
    a1+(n-1)*r=a_n_val."""
    A1, R = sp.symbols('A1 R')
    sol = sp.solve([
        Eq(A1 + (m - 1) * R, a_m_val),
        Eq(A1 + (n - 1) * R, a_n_val),
    ], [A1, R])
    if not sol:
        return False
    return sol.get(A1) == a1 and sol.get(R) == r


def build_safe_trig_skeleton() -> dict:
    """Losuje JEDEN z dwoch dostepnych, bezpiecznych archetypow trudnej
    trygonometrii (build_safe_trig_quadratic_equation lub
    build_safe_trig_solvability_range) i normalizuje wynik do WSPOLNEGO
    ksztaltu ("correct_text", "distractors", "prompt_context",
    "default_question") - zeby Quiz (openai_exam.py) i Sprawdzian
    (exam_pdf_generator.py) mogly uzywac JEDNEJ, dzielonej petli
    budowania promptu/parsowania odpowiedzi, niezaleznie od tego, ktory
    archetyp wylosowano dla danej pozycji w partii (naturalne mieszanie
    obu archetypow w JEDNEJ partii - lepsza roznorodnosc niz partia
    zlozona z jednego typu, BEZ potrzeby Diversity Engine, bo oba
    archetypy z definicji nie sa do siebie podobne)."""
    if random.random() < 0.5:
        sk = build_safe_trig_quadratic_equation()
        sk["prompt_context"] = f"Rownanie: $${sk['equation_latex']}$$ dla $x \\in [0, 2\\pi)$."
        sk["default_question"] = f"Rozwiąż równanie ${sk['equation_latex']}$ dla $x \\in [0, 2\\pi)$."
    else:
        sk = build_safe_trig_solvability_range()
        sk["prompt_context"] = f"Pytanie o dziedzine funkcji: {sk['question_text']}"
        sk["default_question"] = sk["question_text"]
    return sk


_TRIG_ANSWER_FRAC_RE = re.compile(r'\\frac\{(-?\d+)?\\pi\}\{(\d+)\}')
_TRIG_ANSWER_BARE_PI_RE = re.compile(r'(?<!\{)(-?\d+)\\pi(?!\})')


def verify_trig_quadratic_equation(A: int, B: int, C: int, claimed_text: str) -> bool:
    """Niezalezna weryfikacja (dla testow/audytu): rozwiazuje
    A*sin^2(x) + B*cos(x) + C = 0 na [0, 2pi) PRZEZ sympy (nie przez
    wzory uzyte w build_safe_trig_quadratic_equation - inna sciezka
    obliczeniowa jako dodatkowe zabezpieczenie) i porownuje zbior
    rozwiazan z tymi zawartymi w `claimed_text`. Rozpoznaje LaTeX w
    formacie uzywanym przez ten modul i real dane z produkcji:
    "\\frac{\\pi}{3}" (pi/3), "\\frac{5\\pi}{3}" (5*pi/3), "2\\pi" (bare,
    NIE wewnatrz \\frac{..})."""
    x = Symbol('x', real=True)
    eq = Eq(A * sp.sin(x) ** 2 + B * sp.cos(x) + C, 0)
    sols = sp.solveset(eq, x, domain=sp.Interval.Ropen(0, 2 * sp.pi))
    true_vals = set(sp.simplify(s) for s in sols)
    claimed_vals = set()
    for num, den in _TRIG_ANSWER_FRAC_RE.findall(claimed_text):
        coeff = sp.Integer(num) if num else sp.Integer(1)
        claimed_vals.add(sp.simplify(coeff * sp.pi / int(den)))
    frac_spans = {m.span() for m in _TRIG_ANSWER_FRAC_RE.finditer(claimed_text)}
    for m in _TRIG_ANSWER_BARE_PI_RE.finditer(claimed_text):
        if any(m.start() >= s and m.end() <= e for s, e in frac_spans):
            continue
        claimed_vals.add(sp.simplify(sp.Integer(m.group(1)) * sp.pi))
    if not claimed_vals:
        return False
    return (len(claimed_vals) == len(true_vals) and
            all(any(sp.simplify(cv - tv) == 0 for tv in true_vals) for cv in claimed_vals))


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
    # NAPRAWIONE (zgloszony realny bug): true_set JEST JUZ policzone - gdy
    # ZADNA z 4 opcji sie nie sparsowala, to nie jest "nie da sie
    # zweryfikowac" tylko "znamy prawidlowa odpowiedz, ale AI nie
    # dostarczylo zadnej parsowalnej opcji" = no_option_matches
    # (odrzucenie), NIE cicha akceptacja. Patrz identyczna naprawa w
    # _match_single_value_option.
    if not any_option_parsed:
        return {"status": "no_option_matches", "true_set": true_set}
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
    # NAPRAWIONE (zgloszony realny bug): true_roots JUZ policzone -
    # brak parsowalnej opcji = no_option_matches (odrzucenie), nie
    # cicha akceptacja. Patrz identyczna naprawa w _match_single_value_option.
    if not any_option_parsed:
        return {"status": "no_option_matches"}
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
# NAPRAWIONE (real-test, sierpien 2026 - user zglosil Quiz/ciagi/klasa 3
# liceum/trudny - real-test pokazal "S10=150" w wyjasnieniu, ale "S10=135"
# oznaczone jako poprawne): ta generacja KONSEKWENTNIE uzywala litery "d"
# ("$d = 3$", "$d = 4$") dla roznicy ciagu arytmetycznego - regex lapal
# WYLACZNIE "r", nigdy "d", wiec `ratio` bylo ZAWSZE None dla kazdego
# pytania o ciag arytmetyczny w calej tej partii (8/8 pytan), niezaleznie
# od intencji - Warstwa 2 byla calkowicie slepa. "d" (od "roznica") jest
# co najmniej tak samo standardowe w polskich podrecznikach jak "r" -
# dodano jako rownowazna alternatywe. Bezpieczne: uzywane WYLACZNIE dla
# kind=="arithmetic" (patrz analyze_sequence_question), zero ryzyka
# kolizji z ciagami geometrycznymi (_SEQ_Q_RE). Nie koliduje tez z
# zapisem wyrazu ciagu nazwanego "d" (np. "$d_1 = 7$") - underscore+cyfra
# miedzy "d" a "=" nie pasuje do tego wzorca (wymaga "d"/"r" WPROST przed "=").
_SEQ_R_RE = re.compile(r'(?<![a-zA-Z])[rd]\s*=\s*(-?\d+(?:[.,]\d+)?)')
_SEQ_Q_RE = re.compile(r'(?<![a-zA-Z])q\s*=\s*(-?\d+(?:[.,]\d+)?)')
# NAPRAWIONE (real-test, sierpien 2026 - user real-testowal Quiz po
# poprzedniej naprawie i wkleil kolejna partie, w ktorej WIELE pytan
# bylo napisanych CZYSTA PROZA, bez ZADNEGO LaTeX/symbolu ("pierwszy
# wyraz wynosi 7, ostatni wyraz wynosi 47, a różnica wynosi 4" zamiast
# "$a_1=7$"/"$d=4$") - _SEQ_TERM_RE/_SEQ_R_RE/_SEQ_Q_RE/_SEQ_LAST_TERM_RE
# wymagaja WSZYSTKIE formy "litera[_indeks]=liczba", wiec byly calkowicie
# slepe na ta (rownie czesta) forme jezykowa. Dodano UZUPELNIAJACE
# (nie zastepujace - patrz uzycie w analyze_sequence_question, TYLKO gdy
# forma symboliczna nic nie znalazla) wzorce prozy dla najczestszych 4
# danych: pierwszy wyraz, roznica/iloraz, ostatni wyraz. "(?:wynosi\s+)?"
# jest OPCJONALNE, bo obserwowano oba warianty w tej samej partii:
# "pierwszy wyraz wynosi 7" ORAZ "pierwszy wyraz 2" (bez czasownika).
_SEQ_PROSE_A1_RE = re.compile(r'pierwsz\w+\s+wyraz\w*\s+(?:wynosi\s+)?(-?\d+(?:[.,]\d+)?)')
_SEQ_PROSE_RATIO_ARITH_RE = re.compile(r'r[oó]żnic\w*\s+(?:wynosi\s+)?(-?\d+(?:[.,]\d+)?)')
_SEQ_PROSE_RATIO_GEOM_RE = re.compile(r'iloraz\w*\s+(?:wynosi\s+)?(-?\d+(?:[.,]\d+)?)')
_SEQ_PROSE_LAST_TERM_RE = re.compile(r'ostatni\s+wyraz\w*\s+(?:wynosi\s+)?(-?\d+(?:[.,]\d+)?)')
# NAPRAWIONE (ten sam real-test jak wyzej): "suma jego pierwszych n
# wyrazow wynosi 65" - slowo "jego"/"tego ciagu" miedzy "suma" a
# "pierwszych" lamalo sztywne \s+ w _SEQ_SUM_VALUE_UNKNOWN_N_RE ponizej -
# dodano OPCJONALNY, ograniczony zbior typowych wypelniaczy (nie
# dowolny tekst - unika falszywych dopasowan).
_SEQ_SUM_FILLER = r'(?:jego\s+|tego\s+ciągu\s+|tego\s+ciagu\s+)?'
# NAPRAWIONE (ten sam real-test jak wyzej - Pytanie 7, "Oblicz sume
# dziesieciu pierwszych wyrazow..."): 2 niezalezne luki naraz -
# (1) tylko cyfra (\d+), nigdy slowna forma liczebnika ("dziesieciu",
# "pieciu" - dokladnie taki sam gatunek bledu jak juz naprawiony dla
# _SEQ_NTH_ASK_ORDINAL_RE/_SEQ_ORDINAL_WORDS, ale to sa slowa w INNYM
# przypadku gramatycznym - liczebnik glowny w dopelniaczu, nie porzadkowy);
# (2) sztywna kolejnosc "pierwszych <N>" - naturalne polskie "sume <N>
# pierwszych wyrazow" (liczebnik PRZED "pierwszych") nie pasowalo wcale.
# Skutek: intent dla Pytania 7 (sum_given_n) nigdy nie zostal rozpoznany -
# unverifiable, mimo ze to prosty, w pelni obliczalny przypadek.
_SEQ_CARDINAL_WORDS = {
    "dwóch": 2, "dwoch": 2, "trzech": 3, "czterech": 4,
    "pięciu": 5, "pieciu": 5, "sześciu": 6, "szesciu": 6, "siedmiu": 7,
    "ośmiu": 8, "osmiu": 8, "dziewięciu": 9, "dziewieciu": 9,
    "dziesięciu": 10, "dziesieciu": 10, "jedenastu": 11, "dwunastu": 12,
    "trzynastu": 13, "czternastu": 14, "piętnastu": 15, "pietnastu": 15,
    "szesnastu": 16, "siedemnastu": 17, "osiemnastu": 18,
    "dziewiętnastu": 19, "dziewietnastu": 19, "dwudziestu": 20,
}


def _cardinal_to_int(s: str) -> int:
    """'10' -> 10, 'dziesięciu' -> 10 (patrz _SEQ_CARDINAL_WORDS)."""
    s = s.strip()
    return int(s) if s.isdigit() else _SEQ_CARDINAL_WORDS[s.lower()]


_SEQ_CARDINAL_NUM_PATTERN = r'(?:\d+|' + '|'.join(_SEQ_CARDINAL_WORDS.keys()) + r')'
# NAPRAWIONE (wykryte realna generacja Etapu 6): "suma" (mianownik, np.
# "Ile wynosi suma pierwszych 6 wyrazów...") obok "sumę"/"sume" (biernik,
# np. "Oblicz sumę pierwszych 6 wyrazów...") - ten sam sum_given_n,
# inny przypadek gramatyczny zaleznie od pozycji w zdaniu.
_SEQ_SUM_N_RE = re.compile(
    r'sum[aeę]\s+' + _SEQ_SUM_FILLER + r'(?:pierwszych\s+(' + _SEQ_CARDINAL_NUM_PATTERN + r')'
    r'|(' + _SEQ_CARDINAL_NUM_PATTERN + r')\s+pierwszych)\s+wyraz'
)
_SEQ_SUM_VALUE_RE = re.compile(
    r'suma\s+' + _SEQ_SUM_FILLER + r'(?:pierwszych\s+(' + _SEQ_CARDINAL_NUM_PATTERN + r')'
    r'|(' + _SEQ_CARDINAL_NUM_PATTERN + r')\s+pierwszych)\s+wyraz\w*[^.]*?wynosi\s+(-?\d+(?:[.,]\d+)?)'
)
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
_SEQ_SUM_VALUE_UNKNOWN_N_RE = re.compile(r'suma\s+' + _SEQ_SUM_FILLER + r'pierwszych\s+n\s+wyraz\w*[^.]*?wynosi\s+(-?\d+(?:[.,]\d+)?)')


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
    else:
        # NAPRAWIONE: fallback do prozy ("ostatni wyraz wynosi 47") -
        # patrz komentarz przy _SEQ_PROSE_LAST_TERM_RE. TYLKO gdy forma
        # symboliczna nic nie znalazla - zero ryzyka nadpisania.
        m = _SEQ_PROSE_LAST_TERM_RE.search(text)
        if m:
            last_term = _to_num(m.group(1))

    terms = {}
    for m in _SEQ_TERM_RE.finditer(text):
        terms[int(m.group(1))] = _to_num(m.group(2))
    if 1 not in terms:
        # NAPRAWIONE: fallback do prozy ("pierwszy wyraz wynosi 7"/
        # "pierwszy wyraz 2") - patrz komentarz przy _SEQ_PROSE_A1_RE.
        m = _SEQ_PROSE_A1_RE.search(text)
        if m:
            terms[1] = _to_num(m.group(1))

    ratio = None
    m = (_SEQ_R_RE if kind == "arithmetic" else _SEQ_Q_RE).search(text)
    if m:
        ratio = _to_num(m.group(1))
    else:
        # NAPRAWIONE: fallback do prozy ("różnica wynosi 4"/"różnicę 3") -
        # patrz komentarz przy _SEQ_PROSE_RATIO_ARITH_RE/_GEOM_RE.
        m = (_SEQ_PROSE_RATIO_ARITH_RE if kind == "arithmetic" else _SEQ_PROSE_RATIO_GEOM_RE).search(text)
        if m:
            ratio = _to_num(m.group(1))

    sum_value = None
    m = _SEQ_SUM_VALUE_RE.search(text)
    if m:
        n_str = m.group(1) or m.group(2)
        sum_value = {"n": _cardinal_to_int(n_str), "value": _to_num(m.group(3))}

    if not terms and last_term is None and sum_value is None:
        return None
    return {"kind": kind, "terms": terms, "ratio": ratio, "last_term": last_term, "sum_value": sum_value}


def _sequence_a1_given(text: str) -> bool:
    """True jesli a1 jest PODANE wprost w tresci (np. 'a_1=3', 'a1 = 3',
    LUB proza 'pierwszy wyraz wynosi 3' - patrz _SEQ_PROSE_A1_RE) -
    wywolywane na juz-lowercased/znormalizowanym tekscie (patrz
    detect_sequence_intent). Uzywane do odroznienia 'pierwszy wyraz' jako
    OPISU danej wartosci od 'pierwszy wyraz' jako SZUKANEJ wartosci.

    NAPRAWIONE (real-test, sierpien 2026 - partia pytan w czystej prozie):
    bez sprawdzania formy prozy, pytanie z a1 podanym WYLACZNIE prozą
    ("pierwszy wyraz wynosi 7, ... oblicz różnicę") bylo BLEDNIE uznawane
    za "a1 nie jest podane" (bo _SEQ_TERM_RE nic nie znalazlo) - fraza
    'pierwszy wyraz' (ktora w rzeczywistosci tylko OPISUJE juz podane a1)
    falszywie sygnalizowalaby "a1 jest szukane"."""
    if any(int(m.group(1)) == 1 for m in _SEQ_TERM_RE.finditer(text)):
        return True
    return bool(_SEQ_PROSE_A1_RE.search(text))


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
        return {"intent": "sum_given_n", "n": _cardinal_to_int(m.group(1) or m.group(2))}

    if ('ile wyraz' in text or ('liczb' in text and 'wyraz' in text)) and 'przekracza' not in text:
        return {"intent": "find_n_from_last_term"}

    # NAPRAWIONE (KRYTYCZNY, POTWIERDZONY BLAD - audyt V1, sierpien 2026):
    # ta galaz wymagala DOSLOWNEGO slowa "roznice"/"iloraz" w tresci,
    # mimo ze wyznaczenie a1 z DWOCH podanych wyrazow MATEMATYCZNIE
    # wymaga policzenia r/q jako kroku posredniego, niezaleznie czy
    # pytanie o to prosi wprost. Realny, najbardziej naturalny wariant
    # pytania ("Wyznacz pierwszy wyraz tego ciagu." - BEZ wzmianki o
    # "roznicy") nigdy nie trafial do tej galezi -> intent=None ->
    # verify_sequence_question zwracalo "unverifiable" -> ZERO
    # weryfikacji Warstwy 2 -> AI mogl podac dowolnie bledne a1 bez
    # zadnego zabezpieczenia (potwierdzony przypadek: a3=11, a7=27,
    # prawdziwe a1=3, AI/Warstwa 1 przyjelo bledne a1=5 bez sprzeciwu).
    # Usunieto wymog slowa-klucza - BEZPIECZNE, bo verify_sequence_question
    # i tak NIEZALEZNIE sprawdza `len(idxs) != 2` przed faktycznym
    # rozwiazywaniem (patrz galaz two_term_to_a1_ratio tam) - falszywe
    # dopasowanie intencji nie moze wiec dac falszywego wyniku, tylko
    # co najwyzej poprawne odrzucenie/abstain.
    if asks_for_a1:
        return {"intent": "two_term_to_a1_ratio"}

    # NAPRAWIONE (ten sam real-test jak _SEQ_R_RE/_SEQ_SUM_N_RE wyzej -
    # Pytania 3 i 4: "c1=4, c3=16, oblicz iloraz" / "d1=7, d5=19, oblicz
    # roznice"): gdy a1 jest JUZ PODANE wprost (a1_given=True), asks_for_a1
    # jest z definicji False, wiec zaden z powyzszych intentow nigdy sie
    # nie dopasowywal - pytanie o SAM r/q (bez pytania tez o a1) nie mialo
    # ZADNEGO intencji -> unverifiable, mimo ze to identyczny, w pelni
    # rozwiazywalny uklad 2 rownan/2 niewiadome co two_term_to_a1_ratio,
    # tylko interesuje nas DRUGA niewiadoma (r/q) zamiast pierwszej (a1).
    #
    # NAPRAWIONE (real-test, kolejna partia): pierwsza wersja tego
    # sprawdzenia sprawdzala czasownik i "różnic"/"iloraz" NIEZALEZNIE
    # gdziekolwiek w tekscie - falszywie lapala "Znajdź sumę wszystkich
    # wyrazów..., a różnica wynosi 5" (pytanie o SUME, "różnica" tam
    # tylko OPISUJE juz DANA wartosc, daleko od czasownika "znajdź").
    # Wymagane teraz: czasownik BEZPOSREDNIO PRZED "różnicę"/"iloraz"
    # (tak jak w faktycznych zgloszonych przypadkach: "oblicz różnicę
    # tego ciągu", "oblicz iloraz tego ciągu") - eliminuje falszywe
    # dopasowania, gdzie "różnica"/"iloraz" to tylko dana, nie pytanie.
    if a1_given and re.search(r'(?:oblicz|wyznacz|znajd\w*|jaki jest)\s+(?:różnic\w*|roznic\w*|iloraz\w*)', text):
        return {"intent": "two_term_to_ratio_only"}
    return None


def _option_a1_ratio(option_text: str, kind: str):
    """'a) a1 = 4, r = 3' -> (a1, ratio) albo None (nie sparsowano)."""
    text = _normalize_subscripts(_option_text(option_text))
    m1 = re.search(r'a1\s*=\s*(-?\d+(?:[.,]\d+)?)', text)
    m2 = (_SEQ_R_RE if kind == "arithmetic" else _SEQ_Q_RE).search(text)
    if not m1 or not m2:
        return None
    return (_to_num(m1.group(1)), _to_num(m2.group(1)))


def _option_value_after_equals(opt):
    """'$a_{10} = 48$' -> 48 (wyciaga wartosc PO ostatnim '=', nie probuje
    parsowac calego tekstu jako jedno wyrazenie sympy - bare '=' nie jest
    poprawnym wyrazeniem, zawsze rzucaloby SyntaxError). PROMOWANE do
    poziomu modulu (real-test, sierpien 2026) - byla to lokalna funkcja
    zagniezdzona w verify_sequence_question, ale verify_sequence_formula_
    parameter (INNA funkcja modulowa) tez jej potrzebowala - nie
    duplikujemy identycznej logiki drugi raz."""
    text = _normalize_subscripts(_option_text(opt)).strip().strip('$').strip()
    m = re.search(r'=\s*(-?\d+(?:[.,]\d+)?)\s*$', text)
    if m:
        return _to_num(m.group(1))
    return _parse_expr(text)


# NAPRAWIONE (user zglosil realny przypadek, sierpien 2026): ciag
# geometryczny podany WPROST jako wzor ogolny "$b_n = k^n$" (parametr k
# jako WYKLADNIK) nie ma ZADNYCH konkretnych wyrazow (np. brak "b_1=..."),
# wiec analyze_sequence_question ponizej (ktora wymaga terms/last_term/
# sum_value) zawsze zwraca None dla tego ksztaltu pytania - cala
# weryfikacja Warstwy 2 dla ciagow byla wiec calkowicie slepa na ten
# podwzorzec. Potwierdzony realny blad: AI poprawnie wyprowadzilo k=4 w
# WYJASNIENIU, ale WSKAZALO (final_answer) blednie k=2 - Warstwa 1 nie
# ma dostepu do tresci wyjasnienia (tylko final_answer vs opcje), wiec
# nie mogla zlapac tej sprzecznosci.
_SEQ_POWER_FORM_RE = re.compile(r'[a-z]_?\{?n\}?\s*=\s*[a-z]\s*\^\s*\{?n\}?')
_SEQ_RATIO_VALUE_RE = re.compile(r'iloraz\w*\s+(?:r[oó]wn\w*|wynosi)\s+(-?\d+(?:[.,]\d+)?)')


def verify_geometric_power_form_ratio(question_text: str, options: list):
    """MINIMALNY, bezpieczny weryfikator dla JEDNEGO, potwierdzonego
    podwzorca: ciag geometryczny b_n=k^n (parametr jako wykladnik),
    pytanie o k dla ktorego iloraz kolejnych wyrazow rowna sie danej
    liczbie. Matematyka jest tu trywialna i bezpieczna: dla b_n=k^n,
    b_(n+1)/b_n = k^(n+1)/k^n = k dla KAZDEGO n - wiec "iloraz rowny X"
    oznacza WPROST k=X, bez zadnego rownania do rozwiazywania. Abstain
    (unverifiable) dla wszystkiego innego - patrz kontrakt
    verify_sequence_question."""
    text = _normalize_subscripts(question_text).lower()
    if 'geometryczn' not in text or not _SEQ_POWER_FORM_RE.search(text):
        return {"status": "unverifiable"}
    m_ratio = _SEQ_RATIO_VALUE_RE.search(text)
    if not m_ratio:
        return {"status": "unverifiable"}
    true_value = _to_num(m_ratio.group(1))

    matches = []
    any_parsed = False
    for idx, opt in enumerate(options or []):
        try:
            opt_val = _parse_expr(_option_text(opt))
        except Exception:
            opt_val = None
        if opt_val is None:
            continue
        any_parsed = True
        if opt_val == true_value:
            matches.append(idx)
    if not any_parsed:
        return {"status": "no_option_matches"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    return {"status": "no_option_matches"}


def _disambiguate_multi_solution(real_sols, options, option_parser):
    """NAPRAWIONE (real-test, sierpien 2026 - user real-testowal Quiz/
    ciagi geometryczne po poprzednich naprawach): uklad rownan dla
    two_term_to_a1_ratio/two_term_to_ratio_only czesto ma DWA
    matematycznie poprawne rozwiazania (np. q^2=9 -> q=+-3), bo
    parzysta potega ilorazu ma dwa pierwiastki - poprzednio kazdy
    taki przypadek zawsze abstainowal (bezpiecznie, ale marnujac
    informacje: pytanie z natury MA jedna, konkretna, zamierzona przez
    AI odpowiedz miedzy podanymi opcjami).

    Zamiast zawsze abstainowac, sprawdzamy, ktore z matematycznie
    poprawnych rozwiazan FAKTYCZNIE wystepuje wsrod podanych opcji.
    Jesli DOKLADNIE JEDNO z nich pasuje do DOKLADNIE JEDNEJ opcji -
    to bezpieczna odpowiedz (reszta matematycznie poprawnych rozwiazan
    po prostu nie byla WSROD wyboru, wiec nie moglaby byc "zamierzona"
    przez AI). W kazdym innym przypadku (0 pasuje, >=2 rozne rozwiazania
    pasuja, albo jedno rozwiazanie pasuje do >=2 opcji) - unverifiable,
    identycznie jak wczesniej - to NIE jest zgadywanie, tylko wyciaganie
    dodatkowej pewnosci z JUZ danych opcji."""
    matched_distinct = set()
    per_option = []
    for idx, opt in enumerate(options or []):
        try:
            opt_val = option_parser(opt)
        except Exception:
            opt_val = None
        per_option.append((idx, opt_val))
        if opt_val is not None and opt_val in real_sols:
            matched_distinct.add(opt_val)
    if len(matched_distinct) == 1:
        only_val = next(iter(matched_distinct))
        idxs = [idx for idx, v in per_option if v == only_val]
        if len(idxs) == 1:
            return idxs[0]
    return None


def verify_sequence_question(question_text: str, options: list):
    """Weryfikacja zadan o ciagach arytmetycznych/geometrycznych - ten
    sam kontrakt zwracany co verify_param_quadratic_question."""
    power_form_result = verify_geometric_power_form_ratio(question_text, options)
    if power_form_result["status"] != "unverifiable":
        return power_form_result

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

    # _option_value_after_equals - patrz definicja modulowa wyzej (obok
    # _option_a1_ratio) - promowana z lokalnej funkcji zagniezdzonej tutaj,
    # bo verify_sequence_formula_parameter (inna funkcja modulowa) tez
    # jej potrzebowala.

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
            # NAPRAWIONE (real-test, sierpien 2026 - Pytanie 7: S10=150
            # wyliczone poprawnie, ale "no_option_matches" mimo to): ten
            # sam blad co juz naprawiony dla find_a1_given_sum
            # (_option_value_after_equals) - opcje typu "$S_{10} = 150$"
            # maja $ na koncu, wiec probowanie sparsowac CALY tekst jako
            # jedno wyrazenie sympy zawsze rzucalo SyntaxError (bare "=").
            option_parser = _option_value_after_equals
        elif intent["intent"] == "find_n_from_last_term":
            if 1 not in terms or ratio is None or parsed["last_term"] is None:
                return {"status": "unverifiable"}
            sol = sp.solve(Eq(an_expr(terms[1], ratio, n_sym), parsed["last_term"]), n_sym)
            real_sol = [s for s in sol if s.is_real and s > 0]
            if len(real_sol) != 1:
                return {"status": "unverifiable"}
            true_value = sp.nsimplify(real_sol[0])
            # NAPRAWIONE: ten sam blad co w sum_given_n wyzej - patrz
            # komentarz tam.
            option_parser = _option_value_after_equals
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
            # NAPRAWIONE: ten sam blad co w sum_given_n wyzej - patrz
            # komentarz tam.
            option_parser = _option_value_after_equals
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
            if not real_sols:
                return {"status": "unverifiable"}
            # NAPRAWIONE (real-test, sierpien 2026): opcje CZASEM podaja
            # TYLKO a1 ("$a_1 = 3$"), nie pare a1+iloraz - _option_a1_ratio
            # wymaga OBU wartosci w kazdej opcji, wiec dla tego formatu
            # zawsze zwracal None (zero opcji do sparsowania, mimo ze
            # true_value bylo poprawnie policzone). Sprawdz najpierw, czy
            # JAKAKOLWIEK opcja w ogole zawiera wartosc ilorazu/roznicy -
            # jesli NIE, porownuj TYLKO po a1 (jedyne, co mozna bezpiecznie
            # zweryfikowac z tego, co user faktycznie widzi jako opcje).
            pair_parser = lambda opt: _option_a1_ratio(opt, kind)
            any_option_has_ratio = any(pair_parser(opt) is not None for opt in (options or []))
            if any_option_has_ratio:
                option_parser = pair_parser
                candidates = real_sols
            else:
                option_parser = _option_value_after_equals
                candidates = [a1v for a1v, _rv in real_sols]
            if len(candidates) > 1:
                idx = _disambiguate_multi_solution(candidates, options, option_parser)
                return {"status": "match_index", "true_index": idx} if idx is not None else {"status": "unverifiable"}
            true_value = candidates[0]
        elif intent["intent"] == "two_term_to_ratio_only":
            # Identyczny uklad rownan co two_term_to_a1_ratio (patrz
            # komentarz w detect_sequence_intent) - jedyna roznica to
            # KTORA z 2 niewiadomych nas interesuje (r/q, nie a1) i jak
            # parsowane sa opcje (pojedyncza wartosc "d = 3"/"q = 2", nie
            # para a1+ratio).
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
                    real_sols.append(sp.nsimplify(rv))
            option_parser = _option_value_after_equals
            if len(real_sols) > 1:
                idx = _disambiguate_multi_solution(real_sols, options, option_parser)
                return {"status": "match_index", "true_index": idx} if idx is not None else {"status": "unverifiable"}
            if len(real_sols) != 1:
                return {"status": "unverifiable"}
            true_value = real_sols[0]
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
    # NAPRAWIONE (zgloszony realny bug): true_value JUZ policzone -
    # brak parsowalnej opcji = no_option_matches (odrzucenie), nie
    # cicha akceptacja. Patrz identyczna naprawa w _match_single_value_option.
    if not any_parsed:
        return {"status": "no_option_matches"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    if len(matches) > 1:
        return {"status": "unverifiable"}
    return {"status": "no_option_matches"}


# NAPRAWIONE (real-test - user ocenial jakosc wygenerowanego Sprawdzianu
# PDF (Ciagi, klasa 3 liceum, trudny) i znalazl, ze 3 z 6 zadan zamknietych
# mialy zepsuty klucz odpowiedzi): zadania podajace wzor ciagu WPROST
# jako funkcje n z JEDNYM nieznanym parametrem (np. "a_n=3n+m",
# "c_n=pn+5") + JEDEN warunek liczbowy do rozwiazania wzgledem tego
# parametru - CALKOWICIE inny ksztalt niz analyze_sequence_question
# (ktora wymaga KONKRETNYCH wyrazow typu "a_1=5", nie samej formuly).
# Skutek PRZED ta naprawa: verify_and_fix_math_question zwracalo
# "unverifiable" dla tego wzorca -> ZERO niezaleznej weryfikacji ->
# jesli pole "final_answer" od AI bylo niezgodne z wlasnym wyjasnieniem
# AI (dokladnie ten sam blad klasy co "Zatem k=4, co daje k=2" z
# wczesniejszej naprawy dzis) - nic tego nie lapalo. Potwierdzone
# REALNYMI przypadkami z PDF: Zadanie 1 (a_n=3n+m, "ma pierwszy wyraz
# rowny 7" -> poprawne m=4, ale klucz oznaczyl inna litere) i Zadanie 3
# (c_n=pn+5, "roznica miedzy drugim a pierwszym wyrazem wynosi 3" ->
# poprawne p=3, znow zla litera).
#
# Obsluguje 2 typy warunkow (oba z real-testu): (a) "ma [X-ty] wyraz
# rowny V" - podstawia n=X do wzoru; (b) "roznica miedzy [X-tym] a
# [Y-tym] wyrazem wynosi V" - odejmuje wzor(n=X)-wzor(n=Y). Rozpoznawanie
# liczebnikow porzadkowych przez PREFIKS rdzenia (_ordinal_word_stem_to_
# index), nie caly wyraz - odporne na polska odmiane przez przypadki
# ("drugim"/"pierwszym" w bierniku, nie tylko mianownik "drugi"/
# "pierwszy"). Abstain (unverifiable) gdy formula ma !=1 nieznany symbol
# poza n, rownanie nie ma dokladnie 1 rozwiazania rzeczywistego, albo
# zaden warunek nie zostal rozpoznany - bezpieczny domyslny abstain,
# identyczny standard co reszta modulu.
_SEQ_FORMULA_RE = re.compile(r'[a-z]_?\{?n\}?\s*=\s*(.+?)(?=\s*(?:ma\b|jest\b|wynosi\b|,|\.|$))')
_SEQ_FORM_COND_TERM_RE = re.compile(r'\bma\s+(\w+)\s+wyraz\s+r[oó]wn\w*\s+(-?\d+(?:[.,]\d+)?)')
_SEQ_FORM_COND_DIFF_RE = re.compile(r'r[oó]żnic\w*\s+między\s+(\w+)\s+a\s+(\w+)\s+wyrazem[^.]*?wynosi\s+(-?\d+(?:[.,]\d+)?)')
# Warunek C (dodany przy okazji - real-test PDF mial 2 zadania tego
# ksztaltu: Zadanie 2 "suma pierwszych trzech wyrazow ... jest rowna 13"
# geometryczne b_n=k^n oraz Zadanie 4 "sume pierwszych dwoch wyrazow
# rowna 10" - oba reuzywaja juz istniejaca infrastrukture liczebnikow
# glownych z _SEQ_CARDINAL_NUM_PATTERN/_cardinal_to_int, budowana
# wczesniej dzisiaj dla innego celu (sum_given_n).
# "jest" opcjonalne - obserwowano oba warianty: "suma ... jest rowna V"
# (Zadanie 2) ORAZ "sume ... rowna V" bez "jest" (Zadanie 4, przymiotnik
# "rowna"/"rowny" bezposrednio przy "sume", bez lacznika).
_SEQ_FORM_COND_SUM_RE = re.compile(
    r'sum[aeę]\s+pierwszych\s+(' + _SEQ_CARDINAL_NUM_PATTERN + r')\s+wyraz\w*'
    r'[^.]*?(?:(?:jest\s+)?r[oó]wn\w*|wynosi)\s+(-?\d+(?:[.,]\d+)?)'
)
_SEQ_ORDINAL_STEMS = [
    ("pierwsz", 1), ("drug", 2), ("trzeci", 3), ("trzec", 3), ("czwart", 4),
    ("piat", 5), ("piąt", 5), ("szost", 6), ("szóst", 6), ("siodm", 7), ("siódm", 7),
    ("osm", 8), ("ósm", 8), ("dziewiat", 9), ("dziewiąt", 9), ("dziesiat", 10), ("dziesiąt", 10),
]


def _ordinal_word_stem_to_index(word: str):
    """'drugim'/'drugiego'/'drugi' -> 2 (dopasowanie po PREFIKSIE rdzenia,
    odporne na polska odmiane przez przypadki) - patrz komentarz przy
    verify_sequence_formula_parameter."""
    for stem, idx in _SEQ_ORDINAL_STEMS:
        if word.startswith(stem):
            return idx
    return int(word) if word.isdigit() else None


# NAPRAWIONE (user zglosil, po real-tescie DRUGIEGO Sprawdzianu: "wszedzie
# bledy w quizie i sprawdzianie"): odkryto, ze Warstwa 2 dla zadan
# OTWARTYCH (Czesc B, "odpowiedz_modelowa") w OGOLE nie istniala (patrz
# komentarz przy _verify_and_fix_exam_math: "Dziala tylko na sekcjach
# zamkniete... zadania otwarte nie sa jeszcze objete") - 4 z 7 zadan
# otwartych w zgloszonym PDF mialy BLEDNA odpowiedz koncowa (bledy
# arytmetyczne AI), zero niezaleznej weryfikacji ich nie lapalo.
#
# _sequence_formula_true_value() wyodrebnia SAMO OBLICZENIE prawdziwej
# wartosci (bez dopasowywania do opcji) z verify_sequence_formula_parameter,
# zeby dokladnie ta sama logika mogla byc uzyta TAKZE dla zadan otwartych
# (patrz check_sequence_formula_open_answer nizej) - jedno zrodlo prawdy,
# zero duplikacji.
#
# Dodano tez WARUNEK D (suma NIESKOŃCZONEGO ciagu geometrycznego rowna V) -
# real-test PDF pokazal Zadanie 2 tego ksztaltu z bledna odpowiedzia w
# kluczu (P=8 zamiast poprawnego P=4), nieobslugiwane przez Warunki A/B/C.
_SEQ_FORM_COND_INF_SUM_RE = re.compile(
    r'sum[aeę]\s+niesk[oó]ńczon\w*\s+ci[aą]gu[^.]*?(?:(?:jest\s+)?r[oó]wn\w*|wynosi)\s+(-?\d+(?:[.,]\d+)?)'
)


def _sequence_formula_true_value(text: str):
    """Zwraca (true_value, param_sym) albo (None, None) - patrz
    verify_sequence_formula_parameter/check_sequence_formula_open_answer.
    `text` juz znormalizowany/lowercase (_normalize_subscripts(...).lower())."""
    m_formula = _SEQ_FORMULA_RE.search(text)
    if not m_formula:
        return None, None
    n_sym = sp.symbols('n')
    try:
        rhs = _parse_expr(m_formula.group(1))
    except Exception:
        return None, None
    if n_sym not in rhs.free_symbols:
        return None, None
    free = rhs.free_symbols - {n_sym}
    if len(free) != 1:
        return None, None
    param_sym = next(iter(free))

    m_cond = _SEQ_FORM_COND_TERM_RE.search(text)
    if m_cond:
        idx = _ordinal_word_stem_to_index(m_cond.group(1))
        if idx is not None:
            try:
                sol = sp.solve(Eq(rhs.subs(n_sym, idx), _to_num(m_cond.group(2))), param_sym)
                real_sol = [s for s in sol if s.is_real]
                if len(real_sol) == 1:
                    return sp.nsimplify(real_sol[0]), param_sym
            except Exception:
                pass

    m_cond = _SEQ_FORM_COND_DIFF_RE.search(text)
    if m_cond:
        idx1 = _ordinal_word_stem_to_index(m_cond.group(1))
        idx2 = _ordinal_word_stem_to_index(m_cond.group(2))
        if idx1 is not None and idx2 is not None:
            try:
                sol = sp.solve(Eq(rhs.subs(n_sym, idx1) - rhs.subs(n_sym, idx2), _to_num(m_cond.group(3))), param_sym)
                real_sol = [s for s in sol if s.is_real]
                if len(real_sol) == 1:
                    return sp.nsimplify(real_sol[0]), param_sym
            except Exception:
                pass

    m_cond = _SEQ_FORM_COND_SUM_RE.search(text)
    if m_cond:
        count = _cardinal_to_int(m_cond.group(1))
        try:
            total = sum((rhs.subs(n_sym, i) for i in range(1, count + 1)), sp.Integer(0))
            sol = sp.solve(Eq(total, _to_num(m_cond.group(2))), param_sym)
            real_sol = [s for s in sol if s.is_real]
            if len(real_sol) == 1:
                return sp.nsimplify(real_sol[0]), param_sym
        except Exception:
            pass

    m_cond = _SEQ_FORM_COND_INF_SUM_RE.search(text)
    if m_cond:
        try:
            ratio_expr = sp.simplify(rhs.subs(n_sym, n_sym + 1) / rhs.subs(n_sym, n_sym))
            if not ratio_expr.free_symbols and abs(ratio_expr) < 1:
                a1_expr = rhs.subs(n_sym, 1)
                total = a1_expr / (1 - ratio_expr)
                sol = sp.solve(Eq(total, _to_num(m_cond.group(1))), param_sym)
                real_sol = [s for s in sol if s.is_real]
                if len(real_sol) == 1:
                    return sp.nsimplify(real_sol[0]), param_sym
        except Exception:
            pass

    return None, None


def verify_sequence_formula_parameter(question_text: str, options: list):
    text = _normalize_subscripts(question_text).lower()
    true_value, _param_sym = _sequence_formula_true_value(text)
    if true_value is None:
        return {"status": "unverifiable"}

    matches = []
    any_parsed = False
    for idx, opt in enumerate(options or []):
        try:
            opt_val = _option_value_after_equals(opt)
        except Exception:
            opt_val = None
        if opt_val is None:
            continue
        any_parsed = True
        if opt_val == true_value:
            matches.append(idx)
    if not any_parsed:
        return {"status": "no_option_matches"}
    if len(matches) == 1:
        return {"status": "match_index", "true_index": matches[0]}
    return {"status": "no_option_matches"}


# NAPRAWIONE (patrz komentarz nad _sequence_formula_true_value wyzej):
# odpowiednik verify_sequence_formula_parameter dla zadan OTWARTYCH -
# zamiast dopasowywac do listy opcji, wyciaga OSTATNIA liczbe po "="
# w "odpowiedz_modelowa" (typowo wynik koncowy w tekscie krok-po-kroku)
# i porownuje z niezaleznie policzona prawdziwa wartoscia. Konserwatywne
# z zalozenia: jesli nie da sie sparsowac ostatniej liczby, ABSTAIN
# (nie falszywie odrzucaj z powodu wlasnej niezdolnosci parsowania)."""
_TRAILING_EQUALS_NUMBER_RE = re.compile(r'=\s*(-?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)\s*[^=\d]*$')


def check_sequence_formula_open_answer(question_text: str, model_answer_text: str):
    """Zwraca {"status": "match"|"mismatch"|"unverifiable", "true_value":...,
    "claimed_value":...}. Uzywane WYLACZNIE dla zadan otwartych (Czesc B) -
    patrz wywolanie w exam_pdf_generator._verify_and_fix_exam_math."""
    text = _normalize_subscripts(question_text).lower()
    true_value, _param_sym = _sequence_formula_true_value(text)
    if true_value is None:
        return {"status": "unverifiable"}
    m = _TRAILING_EQUALS_NUMBER_RE.search(_normalize_subscripts(model_answer_text or ""))
    if not m:
        return {"status": "unverifiable"}
    try:
        claimed = _to_num(m.group(1).replace(' ', ''))
    except Exception:
        return {"status": "unverifiable"}
    if claimed == true_value:
        return {"status": "match", "true_value": true_value, "claimed_value": claimed}
    return {"status": "mismatch", "true_value": true_value, "claimed_value": claimed}


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
    if name in ("two_term_to_a1_ratio", "two_term_to_ratio_only"):
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


def _trig_special_value_from_deg(func_name: str, deg: int):
    """Wspolny 'ogon' rozpoznawania kata specjalnego - dzielony przez
    sciezke stopniowa i radianowa (patrz analyze_trig_special_angle_question
    nizej). Liczy dokladna wartosc sympy dla podanej funkcji i kata w
    stopniach, albo None jesli kat nie jest "specjalny" (wielokrotnosc
    15°) lub wartosc jest niezdefiniowana (np. tg(90°))."""
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


# NAPRAWIONE (wykryte realna generacja - audyt V1, sierpien 2026):
# analyze_trig_special_angle_question rozpoznawal WYLACZNIE zapis w
# STOPNIACH (np. "sin(30°)"). Realna generacja AI dla trygonometrii na
# poziomie liceum pisze niemal ZAWSZE w RADIANACH jako wielokrotnosc pi
# (np. "sin(pi/6)", "cos(3*pi/2)") - w praktyce Warstwa 2 dla katow
# specjalnych byla wiec MARTWA na prawdziwych danych (0/26 rozpoznanych
# w realnym tescie), mimo pelnego pokrycia testami jednostkowymi na
# syntetycznych, stopniowych przykladach. Ten regex + petla ponizej
# rozpoznaje argument w nawiasie po funkcji trygonometrycznej (np.
# "\frac{\pi}{6}", "\pi", "3\pi/2"), parsuje go przez ISTNIEJACY
# _parse_expr (ten sam, ktory juz parsuje opcje odpowiedzi gdzie
# indziej) i sprawdza, czy odpowiada wielokrotnosci 15°.
_TRIG_RAD_CALL_RE = re.compile(
    r'\\?(sin|cos|tg|ctg|tan|cot|sec|csc)\s*\(\s*([^()]*?)\s*\)',
    re.I,
)


def analyze_trig_special_angle_question(question_text: str):
    """Rozpoznaje pytanie o wartosc funkcji trygonometrycznej dla KATA
    SPECJALNEGO (wielokrotnosc 15°/pi/12) - w STOPNIACH (np. sin(30°))
    ALBO w RADIANACH jako wielokrotnosc pi (np. sin(pi/6), cos(3*pi/2)).
    Zwraca {"func", "deg", "value"} (value = dokladna wartosc sympy)
    albo None (nie rozpoznano / kat nie jest "specjalny" / wartosc
    niezdefiniowana np. tg(90°) - abstain, nie zgadujemy)."""
    if not question_text:
        return None
    text = _normalize_subscripts(question_text)

    m = _TRIG_DEG_RE.search(text)
    if m:
        func_name = m.group(1).lower()
        deg = _to_num(m.group(2))
        if deg is None or deg != int(deg):
            return None
        return _trig_special_value_from_deg(func_name, int(deg))

    for rm in _TRIG_RAD_CALL_RE.finditer(text):
        arg = rm.group(2)
        if 'pi' not in arg.replace('\\pi', 'pi').lower():
            continue
        func_name = rm.group(1).lower()
        try:
            deg_exact = sp.nsimplify(_parse_expr(arg) * 180 / sp.pi)
        except Exception:
            continue
        if not deg_exact.is_number or not deg_exact.is_real:
            continue
        deg_float = float(deg_exact)
        if abs(deg_float - round(deg_float)) > 1e-9:
            continue
        result = _trig_special_value_from_deg(func_name, int(round(deg_float)))
        if result:
            return result
    return None


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
    # NAPRAWIONE (zgloszony realny bug - "verifier chroni tylko czasami"):
    # tutaj `true_value` JEST JUZ policzone (skad wywolujacy zna
    # prawidlowa odpowiedz) - jesli ZADNA z 4 opcji sie nie sparsowala,
    # to NIE oznacza "nie da sie zweryfikowac" (co sugerowaloby wczesniej
    # zwrocone "unverifiable" z INNYCH miejsc, gdzie faktycznie NIE
    # wiadomo jaka jest prawidlowa odpowiedz) - oznacza "znamy prawde,
    # ale AI nie dostarczylo ZADNEJ parsowalnej/poprawnej opcji", co jest
    # rownowazne "no_option_matches" (odrzucenie + dogenerowanie), NIE
    # cichej akceptacji. To byl bezposredni mechanizm zgloszonego bledu:
    # "unverifiable" bylo tu traktowane jako bezpieczny sukces.
    if not any_parsed:
        return {"status": "no_option_matches"}
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
    # NAPRAWIONE (zgloszony realny bug): (true_a,true_b) JUZ policzone -
    # brak parsowalnej opcji = no_option_matches (odrzucenie), nie
    # cicha akceptacja. Patrz identyczna naprawa w _match_single_value_option.
    if not any_parsed:
        return {"status": "no_option_matches"}
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
    # NAPRAWIONE (zgloszony realny bug): (p,q) JUZ policzone -
    # brak parsowalnej opcji = no_option_matches (odrzucenie), nie
    # cicha akceptacja. Patrz identyczna naprawa w _match_single_value_option.
    if not any_parsed:
        return {"status": "no_option_matches"}
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
# LOSOWANIE POZYCJI POPRAWNEJ ODPOWIEDZI (zgloszony problem: AI ma
# tendencje umieszczac poprawna odpowiedz na okreslonych pozycjach,
# np. A/B czesciej niz C/D - udokumentowana cecha modeli LLM, nie blad
# w tym kodzie, ale system MA jej przeciwdzialac). Wywolywane PO
# wszystkich warstwach weryfikacji (1/2/3) - w momencie wywolania
# `correct_index` juz wskazuje NAPRAWDE poprawna opcje wzgledem
# BIEZACEJ kolejnosci `options`. Tasowanie:
#   - NIE zmienia tresci matematycznej zadnej opcji (tylko kolejnosc),
#   - poprawnie przelicza correct_index na nowa pozycje,
#   - jest bezpiecznym no-op gdy dane wejsciowe sa niepoprawne
#     (correct_index poza zakresem, options nie jest lista) - NIGDY nie
#     rzuca wyjatku i nigdy nie "zgaduje" nowego correct_index.
# ---------------------------------------------------------------
def shuffle_options_preserving_correct(options: list, correct_index, relabel_prefix: bool = False):
    """Losowo tasuje `options`, zwraca (nowe_options, nowy_correct_index).
    `relabel_prefix=True` (Sprawdzian/PDF, gdzie etykieta "a) "/"b) "/...
    bywa zapisana WEWNATRZ tekstu opcji, bo PDF nie ma frontu ktory
    dorysuje etykiete z pozycji w liscie) usuwa STARY litero-prefiks
    kazdej opcji (jesli obecny) i doklada NOWY, zgodny z pozycja PO
    przetasowaniu - to NIE jest zmiana tresci matematycznej, tylko
    korekta etykiety pozycji, bez ktorej PDF pokazywalby "a) X" na
    pozycji C. Quiz (`relabel_prefix=False`, domyslne) renderuje
    etykiety A/B/C/D z pozycji w tablicy po stronie frontu, wiec tam
    etykiety NIE sa zapisane w tekscie i nie trzeba ich przepisywac."""
    if not isinstance(options, list) or not isinstance(correct_index, int):
        return options, correct_index
    n = len(options)
    if n < 2 or not (0 <= correct_index < n):
        return options, correct_index
    texts = [_option_text(o) for o in options] if relabel_prefix else list(options)
    order = list(range(n))
    random.shuffle(order)
    shuffled_texts = [texts[i] for i in order]
    new_correct_index = order.index(correct_index)
    if relabel_prefix:
        letters = "abcdefghij"  # z zapasem - w praktyce zawsze 4 (a-d)
        new_options = [f"{letters[i]}) {t}" for i, t in enumerate(shuffled_texts)]
    else:
        new_options = shuffled_texts
    return new_options, new_correct_index


def log_unverifiable_diagnostic(prefix: str, topic: str, question_text: str, options: list, final_answer) -> None:
    """Diagnostyczny log dla przypadku, gdy Warstwa 2 zwraca
    "unverifiable" (zaden domain modifier nie rozpoznal wzorca w tym
    pytaniu, wiec przechodzi WYLACZNIE na podstawie Warstwy 1). Bez tego
    "unverifiable" byl calkowicie niewidoczny (w odroznieniu od odrzucen,
    ktore juz mialy print) - utrudnialo to diagnoze zgloszonych bledow
    (patrz Naprawa #1/#2/#3 w tej sesji, kazda wymagala rekonstrukcji
    "na slepo"). Same dane matematyczne (tresc zadania, opcje) - zero
    danych osobowych/sekretow, wiec bezpieczne do logowania."""
    opts_repr = " | ".join(f"[{i}]{str(o)[:80]}" for i, o in enumerate(options or []))
    print(
        f"{prefix} UNVERIFIABLE (brak rozpoznanego wzorca weryfikacji - przechodzi "
        f"tylko na podstawie Warstwy 1): temat='{topic}' pytanie='{(question_text or '')[:150]}' "
        f"opcje={opts_repr} final_answer='{final_answer}'"
    )


def log_final_answer_mismatch_diagnostic(prefix: str, topic: str, question_text: str, options: list, final_answer, fa_status: str) -> None:
    """Diagnostyczny log dla odrzucen Warstwy 1 (final_answer nie
    pasuje/brak/niejednoznaczny) - NAJWIEKSZA (najczestsza) kategoria
    odrzucen w audycie realnej generacji (sierpien 2026, do 80% partii
    dla jednego konkretnego wzorca rownan kwadratowych), a jednoczesnie
    do tej pory BEZ zadnego szczegolowego logu (tylko obcieta do 60
    znakow tresc pytania, bez opcji/final_answer) - uniemozliwialo to
    odroznienie: (a) AI faktycznie nie skopiowalo final_answer 1:1 z
    ktorejs opcji (naruszenie prompta) od (b) canonicalizacji w
    match_final_answer_index zbyt scisle porownujacej tekst mimo
    semantycznej rownowaznosci."""
    opts_repr = " | ".join(f"[{i}]{str(o)[:80]}" for i, o in enumerate(options or []))
    print(
        f"{prefix} FINAL_ANSWER_{fa_status.upper()} (Warstwa 1: final_answer nie "
        f"dopasowane do zadnej opcji - pytanie odrzucone): temat='{topic}' "
        f"pytanie='{(question_text or '')[:150]}' opcje={opts_repr} final_answer='{final_answer}'"
    )


def log_no_option_matches_diagnostic(prefix: str, topic: str, question_text: str, options: list, final_answer) -> None:
    """Diagnostyczny log - siostrzana funkcja log_unverifiable_diagnostic
    dla PRZECIWNEGO przypadku: Warstwa 2 ROZPOZNALA wzorzec, policzyla
    prawdziwa odpowiedz, ale ZADNA z 4 opcji AI jej nie odpowiada
    ("no_option_matches" - pytanie odrzucone). Dotychczasowy print przy
    odrzuceniu pokazywal TYLKO pierwsze 60 znakow tresci, bez opcji ani
    final_answer - audyt realnej generacji (sierpien 2026) pokazal, ze
    to uniemozliwia odroznienie realnego bledu AI (poprawna odpowiedz
    faktycznie nie byla wsrod opcji) od bledu parsera (opcje sa
    poprawne, ale weryfikator ich nie rozpoznal) bez ponownego
    odtwarzania calego zapytania od zera."""
    opts_repr = " | ".join(f"[{i}]{str(o)[:80]}" for i, o in enumerate(options or []))
    print(
        f"{prefix} NO_OPTION_MATCHES (wzorzec rozpoznany, prawdziwa odpowiedz "
        f"policzona, ale ZADNA opcja jej nie odpowiada - pytanie odrzucone): "
        f"temat='{topic}' pytanie='{(question_text or '')[:150]}' "
        f"opcje={opts_repr} final_answer='{final_answer}'"
    )


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

    result3b = verify_sequence_formula_parameter(question_text, options)
    if result3b["status"] in ("match_index", "no_option_matches"):
        return {**result3b, "explanation": None}

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


# ---------------------------------------------------------------
# UNIVERSAL DIVERSITY ENGINE (Krok 1-2, sierpien 2026): zgloszony
# problem "AI generuje 10 pytan tym samym schematem, tylko z innymi
# literami/liczbami" - dzisiejszy dedup (_question_fingerprint w
# openai_exam.py/exam_pdf_generator.py) CELOWO ignoruje rozne litery/
# liczby (to legalna, rozna wersja tego samego typu zadania wg jego
# wlasnej dokumentacji) - dziala WIEC na innym poziomie niz potrzeba
# tutaj: wykrywanie tego samego SCHEMATU/TYPU ROZUMOWANIA, nie tej
# samej tresci slowo-w-slowo.
#
# Zamiast recznie definiowac warianty per temat (V2/Skills odrzucone
# przez usera), AI SAMO opisuje kazde pytanie 4-polowym tagiem
# ("diversity_tag": skill/concept/task_type/reasoning - patrz prompt w
# _raw_generate_quiz_topic_once). Krok 1 (real test, ten sam dzien)
# potwierdzil: AI wypelnia to pole UCZCIWIE - partia 10 pytan "medium
# rownania kwadratowe" dala 9 identycznych tagow (naprawde ten sam
# schemat: "parametr jako wyraz wolny") i 1 realnie inny (parametr
# jako wspolczynnik liniowy) - dokladnie odzwierciedlajac faktyczna
# (nisk) roznorodnosc surowej generacji. To dziala dla KAZDEGO tematu
# bez zadnej dodatkowej konfiguracji - AI opisuje WLASNYMI slowami, nie
# wybiera z zaszytej w kodzie listy.
#
# Porownanie: Jaccard similarity na znormalizowanym zbiorze tokenow z
# 4 pol tagu - w pelni generyczne, topic-agnostic, zero logiki
# specyficznej dla przedmiotu/tematu.
_DIVERSITY_STOPWORDS = frozenset({
    "i", "w", "z", "dla", "na", "do", "o", "a", "za", "przy", "po", "od", "ze",
    "jak", "jakie", "jaki", "jaka", "ktory", "ktora", "ktore", "to", "sie",
    "tego", "tej", "tym", "ten", "ta",
})
_DIVERSITY_TAG_FIELDS = ("skill", "concept", "task_type", "reasoning")
_DIVERSITY_NON_WORD_RE = re.compile(r'[^a-ząćęłńóśźż]+')
_DIVERSITY_NUMBER_RE = re.compile(r'-?\d+(?:[.,]\d+)?')


def diversity_tag_tokens(tag, question_text: str = None) -> frozenset:
    """Zamienia diversity_tag (dict z polami skill/concept/task_type/
    reasoning, kazde krotka fraza wygenerowana przez AI) na
    znormalizowany zbior tokenow do porownania Jaccarda. Brakujace pola
    -> pusty string (nie crashuje). Zwraca PUSTY frozenset, jesli `tag`
    nie jest dictem w ogole (np. AI pominelo pole, albo stary format
    bez tego pola) - pusty zbior oznacza "nie da sie ocenic
    roznorodnosci tego pytania", NIE "identyczne z czymkolwiek" (patrz
    is_too_similar_diversity_tag nizej - pusty zbior nigdy nie blokuje,
    bezpieczny abstain, ta sama filozofia co reszta tego modulu).

    NAPRAWIONE (user zglosil PONOWNIE ten sam blad - najpierw w ciagach
    (Zadanie 4/5 "prawie duplikat" nie zlapany), potem w trygonometrii
    (real-test tego samego dnia odtworzyl: "kat 30°, przyprostokatna
    naprzeciw = 5" zadane DWA razy w jednym sprawdzianie, inaczej
    ZWERBALIZOWANE przez AI - "Oblicz dlugosc przeciwprostokatnej, jesli
    JEDNA Z przyprostokatnych ma dlugosc 5" vs "Jaka dlugosc ma
    przeciwprostokatna, jesli przyprostokatna NAPRZECIW TEGO KATA ma
    dlugosc 5" - te same 2 liczby {30, 5}, ale na tyle rozne slowa w
    "reasoning"/"task_type", ze Jaccard calego tagu NIE przekraczal progu
    0.85): opcjonalny `question_text` - liczby z TRESCI pytania (nie z
    opcji) sa dolaczane jako DODATKOWE tokeny (prefiks "num_", zeby nie
    mieszaly sie ze slowami z tagu). Uzywane przez is_too_similar_
    diversity_tag ponizej jako NIEZALEZNY, dodatkowy sygnal - identyczny
    zestaw >=2 liczb w DWOCH pytaniach jest silnym sygnalem duplikatu
    SAM W SOBIE, niezaleznie od tego, jak roznie AI opisalo "reasoning".
    Zweryfikowane na DOKLADNYM real przypadku (patrz wyzej) - zero
    falszywych trafien wsrod pozostalych 6 pytan tego samego sprawdzianu
    (kazde mialo inny zestaw liczb)."""
    if not isinstance(tag, dict):
        base = frozenset()
    else:
        text = " ".join(str(tag.get(k, "") or "") for k in _DIVERSITY_TAG_FIELDS).lower()
        text = _DIVERSITY_NON_WORD_RE.sub(' ', text)
        base = frozenset(t for t in text.split() if t and t not in _DIVERSITY_STOPWORDS)
    if question_text:
        numbers = _DIVERSITY_NUMBER_RE.findall(question_text)
        if numbers:
            base = base | frozenset(f"num_{n}" for n in numbers)
    return base


def jaccard_similarity(a: frozenset, b: frozenset) -> float:
    """Podobienstwo Jaccarda dwoch zbiorow tokenow: |przeciecie|/|suma|.
    0.0 jesli KTORYKOLWIEK zbior jest pusty (nie da sie ocenic ->
    "nie podobne", nigdy nie blokuje - patrz diversity_tag_tokens)."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# Prog PRZELICZONY (nie zgadniety) na podstawie Kroku 1 (realne tagi,
# patrz test_diversity_engine.py, Czesc 4) - pierwsza wersja tego progu
# (0.6) byla ZGADNIETA bez faktycznego przeliczenia i okazala sie
# BLEDNA: dwa NAPRAWDE rozne schematy ("parametr jako wspolczynnik
# liniowy" vs "parametr jako wyraz wolny") dzielily az 0.733 Jaccard,
# bo pola "skill"/"task_type"/"reasoning" sa czesto GENERYCZNYM
# szkieletem proceduralnym wspolnym dla CALEJ rodziny zadan na warunek
# delty ("oblicz delte, rozwiaz nierownosc, zapisz przedzial") -
# roznicuje je NAPRAWDE tylko pole "concept". 9 IDENTYCZNYCH tagow
# mialo Jaccard=1.0. Prog 0.85 lezy bezpiecznie w luce miedzy
# zmierzonym "rozne" (0.733) a "identyczne" (1.0) - WCIAZ do dalszej
# kalibracji w Kroku 4 na WIEKSZEJ realnej probce (ta jedna partia nie
# pokazala jeszcze przypadku "ten sam schemat, inne slowa" - realny
# test moze pokazac, ze potrzeba jeszcze wyzej, albo wagowania pol).
DIVERSITY_SIMILARITY_THRESHOLD = 0.85


def is_too_similar_diversity_tag(tag, seen_tag_tokens: list, threshold: float = DIVERSITY_SIMILARITY_THRESHOLD, question_text: str = None):
    """Sprawdza, czy `tag` (diversity_tag jednego pytania) jest ZBYT
    PODOBNY (Jaccard >= threshold) do KTOREGOKOLWIEK juz zaakceptowanego
    tagu w tej samej partii (`seen_tag_tokens` - lista frozensetow,
    analogiczny wzorzec do seen_fingerprints w openai_exam.py, ale
    LISTA nie SET, bo porownanie jest rozmyte/Jaccard, nie exact-match).
    Zwraca (is_too_similar: bool, tokens: frozenset) - `tokens` ma byc
    dopisany do `seen_tag_tokens` przez callera, JESLI pytanie zostanie
    finalnie zaakceptowane (ten sam wzorzec co _question_fingerprint).
    Brakujacy/niepoprawny tag -> zawsze (False, pusty frozenset) - NIE
    blokujemy pytania, ktorego roznorodnosci nie da sie ocenic.

    NAPRAWIONE (patrz pelny komentarz w diversity_tag_tokens): DRUGI,
    NIEZALEZNY warunek "za podobne" - identyczny zestaw liczb (>=2, z
    tresci pytania, prefiks "num_") w dwoch pytaniach, NIEZALEZNIE od
    Jaccarda calego tagu. Jaccard zostaje jako GLOWNY, ogolny sygnal
    (dziala nawet bez `question_text`) - to jest DODATKOWA siatka
    bezpieczenstwa dla przypadku, gdy AI opisuje TEN SAM material
    liczbowy na tyle roznymi slowami, ze semantyczne podobienstwo tagu
    nie wystarcza. `question_text` opcjonalny (domyslnie None) - bez
    niego zachowanie identyczne jak wczesniej (tylko Jaccard tagu).

    NAPRAWIONE (znalezione WLASNYM testem regresyjnym przy budowie tej
    funkcji - test_diversity_wiring.py/test_exam_quiz_parity_port.py
    zaczely FALSZYWIE PRZEPUSZCZAC znany, juz poprawnie wykrywany
    duplikat): pierwsza wersja mieszala tokeny "num_X" do TEGO SAMEGO
    zbioru, na ktorym liczony jest Jaccard z tagiem - to DEGRADOWALO
    (nie poprawialo) wykrywanie, bo dwa pytania z IDENTYCZNYM tagiem
    (Jaccard=1.0) ale ROZNYMI liczbami wlasnymi (np. syntetyczny test
    "Testowe pytanie 1?" vs "Testowe pytanie 2?") dostawaly SZTUCZNIE
    obnizony Jaccard (rozne "num_1"/"num_2" powiekszaly sume zbiorow),
    czasem spadajac PONIZEJ progu 0.85 mimo identycznego tagu. Naprawiono:
    Jaccard liczony WYLACZNIE na czesci slownej (bez prefiksu "num_") -
    dokladnie jak przed ta zmiana - liczby sa DRUGIM, NIEZALEZNYM
    warunkiem OR, nie skladnikiem tego samego zbioru."""
    tokens = diversity_tag_tokens(tag, question_text)
    if not tokens:
        return False, tokens
    my_words = frozenset(t for t in tokens if not t.startswith("num_"))
    my_numbers = frozenset(t for t in tokens if t.startswith("num_"))
    for prior in seen_tag_tokens:
        prior_words = frozenset(t for t in prior if not t.startswith("num_"))
        if jaccard_similarity(my_words, prior_words) >= threshold:
            return True, tokens
        if len(my_numbers) >= 2:
            prior_numbers = frozenset(t for t in prior if t.startswith("num_"))
            if my_numbers == prior_numbers:
                return True, tokens
    return False, tokens


def format_avoid_diversity_block(seen_diversity_tag_dicts: list) -> str:
    """User (real-test Sprawdzianu z trygonometrii, 29.08.2026): kazda
    runda dogenerowania ("brakuje N zadan... dogenerowuje") wolala AI
    OD ZERA, z DOKLADNIE tym samym promptem co pierwsza partia - AI nie
    mialo zadnej wiedzy, ktore schematy juz zostaly uzyte (i odrzucone
    jako duplikat/zbyt podobne przez Diversity Engine), wiec dla waskich/
    trudnych tematow (mala pula "oczywistych" pomyslow) w kolko trafialo
    w te same schematy, ktore znowu byly odrzucane - marnujac cala
    runde i budzet czasu (real-test: 11/16 odrzucen w jednej generacji
    to duplicate+diversity_too_similar, nie blad matematyczny).

    Zamiast waskiej poprawki DLA TRYGONOMETRII, ta funkcja jest OGOLNA:
    zamienia liste JUZ ZAAKCEPTOWANYCH diversity_tag (surowe dict-y z
    "skill"/"concept"/"task_type", jak podaje sama AI) na krotki blok
    tekstu do wstrzykniecia w prompt KOLEJNEJ rundy - dziala dla
    KAZDEGO tematu (Quiz i Sprawdzian, oba identycznie), bo diversity_tag
    juz jest generowany uniwersalnie przez AI dla kazdego tematu."""
    if not seen_diversity_tag_dicts:
        return ""
    lines = []
    for tag in seen_diversity_tag_dicts:
        if not isinstance(tag, dict):
            continue
        parts = [str(tag.get(k, "")).strip() for k in ("skill", "concept", "task_type") if tag.get(k)]
        if parts:
            lines.append("- " + " / ".join(parts))
    if not lines:
        return ""
    return (
        "\nJUZ UZYTE SCHEMATY W TYM SPRAWDZIANIE/QUIZIE (KRYTYCZNE - system "
        "JUZ ODRZUCIL probe powtorzenia ktoregokolwiek z nich - NIE generuj "
        "ponownie tych samych pomyslow pod innymi liczbami/literami/"
        "sformulowaniami, wymysl NAPRAWDE INNE podtematy/typy zadan na ten "
        "sam temat):\n" + "\n".join(lines) + "\n"
    )
