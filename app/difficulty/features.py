# -*- coding: utf-8 -*-
"""Ekstrakcja UNIWERSALNYCH cech trudnosci z tekstu zadania - czysto
tekstowe/regexowe heurystyki, ZERO wywolan AI (wymog wydajnosciowy z
audytu, Czesc 5: silnik ma byc w 100% lokalny i deterministyczny).

Dziala na tresci PYTANIA (+ opcjach) - tak samo jak istniejacy
classify_quadratic_difficulty w math_verify.py analizuje tresc pytania,
nie wyjasnienie. Jesli podano `explanation_text` (opcjonalnie, gdy
wywolujacy kod je posiada), niektore cechy (przede wszystkim `steps`) sa
liczone dokladniej z faktycznego toku rozwiazania zamiast z samej tresci
pytania - i confidence to odzwierciedla (patrz analyzer.py).

UWAGA: te heurystyki sa PUNKTEM STARTOWYM (Etap 1) - kalibracja i
rozszerzanie ma nastapic po zebraniu realnych danych (Etap 3 audytu),
nie sa to ostateczne, doskonale wzorce."""
import re

_DOLLAR_FORMULA_RE = re.compile(r'\$[^$]+\$')
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
_OPERATOR_RE = re.compile(
    r'\\sqrt|\\frac|\\cdot|\\times|\\pm|\\geq|\\leq|\\neq|\\sum|\\int|\\lim|[+\-*/^]'
)

_CONDITION_MARKERS = (
    'gdy', 'jezeli', 'jeżeli', 'jesli', 'jeśli', 'dla ktorych', 'dla których',
    'pod warunkiem', 'o ile', 'wtedy i tylko wtedy', 'takich, ze', 'takich, że',
)
_CASE_MARKERS = (
    'rozważ osobno', 'rozwaz osobno', 'osobno przypadek', 'w zależności od przypadku',
    'w zaleznosci od przypadku', 'przypadek pierwszy', 'przypadek drugi', 'w obu przypadkach',
)
# Slowa kluczowe sygnalizujace ROZPOZNAWALNA metode/wzorzec matematyczny -
# celowo szeroka, ale plaska lista (bez podzialu na "rodziny tematyczne") -
# precyzyjniejsze rozpoznawanie nazw metod nalezy do domain modifierow.
# UWAGA: uzywamy RDZENI slow (nie pelnych form), bo polski jest silnie
# fleksyjny - "pochodna" nie jest podciagiem "pochodną"/"pochodnej" (inna
# koncowka), wiec dopasowanie po pelnym slowie w mianowniku gubi wiekszosc
# realnych zdan. Rdzen "pochod" lapie wszystkie odmiany.
_METHOD_MARKERS = (
    'delt', 'wyróżnik', 'wyroznik', 'viet', 'viète', 'viete',
    'pochod', 'całk', 'calk', 'granic', 'redukcyjn',
    'twierdzeni', 'tożsam', 'tozsam', 'uklad rowna', 'układ równa',
    'skrócon', 'skrocon', 'indukcj', 'kombinatoryk',
    'prawdopodobieństw', 'prawdopodobienstw', 'macierz', 'wektor',
)
_ABSTRACTION_MARKERS = (
    'udowodnij', 'wykaż', 'wykaz', 'uzasadnij', 'udowodnic', 'udowodnić',
)
# Zgrubne "rodziny tematyczne" do heurystyki cross_topic - jesli zadanie
# zawiera slowa-klucze z WIECEJ NIZ JEDNEJ rodziny, prawdopodobnie laczy
# tematy (np. trygonometria + rownania kwadratowe).
_TOPIC_FAMILIES = {
    "algebra": ("równanie", "rownanie", "nierówność", "nierownosc", "wielomian", "parametr"),
    "trygonometria": ("sin", "cos", "tan", "cot", "\\sin", "\\cos", "\\tan"),
    "analiza": ("pochodna", "całka", "calka", "granica", "ciąg", "ciag"),
    "geometria": ("trójkąt", "trojkat", "okrąg", "okrag", "pole", "obwód", "obwod", "kąt", "kat"),
    "prawdopodobienstwo": ("prawdopodobieńst", "prawdopodobienst", "kombinacj", "permutacj"),
}


def _find_formulas(question_text: str, option_texts=None) -> list:
    formulas = list(_DOLLAR_FORMULA_RE.findall(question_text or ""))
    for opt in (option_texts or []):
        formulas.extend(_DOLLAR_FORMULA_RE.findall(str(opt)))
    return formulas


def _count_markers(text_lower: str, markers) -> int:
    return sum(1 for m in markers if m in text_lower)


_PARAMETER_SYMBOL_RE = re.compile(r'(?<![a-zA-Z\\])[a-wA-W](?![a-zA-Z{])')


def _has_parameter(question_text: str, formulas: list) -> bool:
    """Wykrywa PARAMETR (litera inna niz x/y/z, uzyta jako zmienna w
    formule) - to samo pojecie co `param` w analyze_quadratic_question,
    ale bez ograniczenia do rownan kwadratowych. [a-w] celowo wyklucza
    x/y/z (najczestsze zmienne "glowne", nie parametry)."""
    return any(_PARAMETER_SYMBOL_RE.search(f) for f in formulas)


def extract_features(question_text: str, option_texts=None, explanation_text: str = None):
    """Zwraca DifficultyBreakdown wyliczony z tresci pytania (+opcjonalnie
    opcji i wyjasnienia). Import lokalny DifficultyBreakdown, zeby uniknac
    cyklicznego importu z scoring.py przy uzyciu tego modulu samodzielnie."""
    from .scoring import DifficultyBreakdown

    question_text = question_text or ""
    text_lower = question_text.lower()
    formulas = _find_formulas(question_text, option_texts)

    operations = sum(len(_OPERATOR_RE.findall(f)) for f in formulas)
    conditions = _count_markers(text_lower, _CONDITION_MARKERS)
    cases = _count_markers(text_lower, _CASE_MARKERS)
    methods = _count_markers(text_lower, _METHOD_MARKERS)
    has_parameter = _has_parameter(question_text, formulas)

    if explanation_text:
        # Dokladniejsze "steps" z faktycznego wyjasnienia - liczba zdan
        # zawierajacych przynajmniej jeden wzor $...$.
        sentences = [s for s in _SENTENCE_SPLIT_RE.split(explanation_text) if s.strip()]
        steps = sum(1 for s in sentences if _DOLLAR_FORMULA_RE.search(s)) or len(formulas)
    else:
        # Bez wyjasnienia: przyblizenie z liczby wzorow w tresci+opcjach -
        # mniej dokladne, patrz confidence w analyzer.py.
        steps = max(1, len(formulas)) if formulas else 0

    topic_families_hit = sum(
        1 for markers in _TOPIC_FAMILIES.values() if _count_markers(text_lower, markers) > 0
    )
    cross_topic = topic_families_hit > 1

    abstraction_level = 0
    if has_parameter:
        abstraction_level = 1
    if _count_markers(text_lower, _ABSTRACTION_MARKERS) > 0:
        abstraction_level = 2

    return DifficultyBreakdown(
        steps=steps,
        operations=operations,
        conditions=conditions,
        methods=methods,
        cases=cases,
        has_parameter=has_parameter,
        abstraction_level=abstraction_level,
        cross_topic=cross_topic,
    ), bool(formulas)
