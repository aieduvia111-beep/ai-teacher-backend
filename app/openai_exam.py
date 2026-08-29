from openai import AsyncOpenAI
from .config import settings
from .level_config import (
    describe_level, validate_generic_topic, get_forced_fallback_topic,
    get_quadratic_difficulty_anchor, is_quadratic_equation_topic,
    get_sequence_difficulty_anchor, is_sequence_topic,
    get_trig_difficulty_anchor, is_trigonometry_topic,
    get_linear_function_difficulty_anchor, is_linear_function_topic,
    get_quadratic_function_difficulty_anchor, is_quadratic_function_topic,
    get_exponential_function_difficulty_anchor, is_exponential_function_topic,
)
from .math_verify import (
    verify_and_fix_math_question, force_correct_from_final_answer,
    shuffle_options_preserving_correct, log_unverifiable_diagnostic,
    log_no_option_matches_diagnostic, log_final_answer_mismatch_diagnostic,
    is_too_similar_diversity_tag, build_safe_linear_param_quadratic,
    pick_safe_param_values, format_avoid_diversity_block,
)
from .blind_verify import (
    BLIND_VERIFY_SYSTEM_PROMPT, build_blind_verify_prompt_closed,
    parse_blind_verify_letter, safe_json_loads,
)
from .difficulty import DifficultyAnalyzer
from typing import List, Dict, Optional
import asyncio
import json
import random
import time
import re as _re_sanitize

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# ETAP 2 Universal Difficulty Engine: podlaczony TYLKO jako zamiennik
# bezposredniego wywolania validate_quadratic_difficulty w Warstwie 3
# (patrz _verify_and_fix_quiz_math nizej) - domain modifier
# math_quadratic.py wywoluje ten sam, niezmieniony kod z math_verify.py,
# wiec zachowanie jest identyczne. Jeden, wspoldzielony instancja -
# DifficultyAnalyzer nie trzyma zadnego stanu miedzy wywolaniami.
_difficulty_analyzer = DifficultyAnalyzer()


_LATEX_CMDS_AT_RISK = [
    # \t... (backslash+t bywa "zjadany" jako tabulator)
    'times', 'text', 'tan', 'theta', 'tau', 'triangle', 'to', 'top', 'tilde',
    # NAPRAWIONE (audyt realnej generacji V1, sierpien 2026): "text" nie
    # chroni "\textbackslash" ani innych wariantow "\text*" - regex ma
    # negative lookahead (?![a-zA-Z]), ktory dla "\textbackslash" NIE
    # przechodzi (po "text" jest litera "b", nie granica slowa), wiec
    # pierwszy backslash "\t" byl mylony z prawdziwym escape'em JSON
    # (tabulator) - obcinalo to reszte tekstu ("extbackslash..."). Kazdy
    # taki dluzszy wariant potrzebuje WLASNEGO wpisu na liscie, nie
    # dziedziczy ochrony po krotszym prefiksie.
    'textbackslash', 'textbf', 'textit', 'textrm', 'texttt', 'textsf',
    # \b... (backslash+b bywa "zjadany" jako backspace)
    'beta', 'bar', 'binom', 'bmod', 'boxed', 'bullet',
    # \f... (backslash+f bywa "zjadany" jako formfeed)
    'frac', 'forall', 'flat',
    # \n... (backslash+n bywa "zjadany" jako nowa linia)
    'neq', 'nabla', 'notin', 'nu',
    # \r... (backslash+r bywa "zjadany" jako powrot karetki)
    'rho', 'rightarrow',
    # \u... (backslash+u bywa mylony z unicode escape \uXXXX)
    'underline', 'underbrace', 'usepackage',
    # inne czeste, ktore i tak warto podwoic zawczasu
    'sqrt', 'cdot', 'div', 'sum', 'int', 'left', 'right', 'alpha', 'gamma',
    'delta', 'pi', 'infty', 'leq', 'geq', 'approx', 'pm', 'mathrm',
    # NAPRAWIONE (ta sama luka co "text" wyzej): "mathrm" byl juz na
    # liscie, ale inne warianty "\math*" (rowniez czeste w notacji
    # zbiorow/funkcji, np. \mathbb{R}) nie byly - ta sama podatnosc.
    'mathbf', 'mathit', 'mathcal', 'mathbb', 'mathfrak',
    'overline', 'over', 'vec', 'hat', 'dot', 'quad', 'qquad', 'ldots',
    'sigma', 'omega', 'lambda', 'partial', 'prod', 'mu', 'phi', 'chi', 'psi',
    'subset', 'cup', 'cap', 'exists', 'in',
]


def sanitize_latex_json_backslashes(raw: str) -> str:
    """Naprawia surowy tekst JSON od GPT PRZED parsowaniem.

    Problem: komendy LaTeX zaczynajace sie od liter b/f/n/r/t (np. \\times,
    \\text, \\frac, \\triangle, \\rho) sa dla json.loads() nierozroznialne od
    prawdziwych escape'ow JSON (\\t = tabulator, \\n = nowa linia, itd.) -
    jesli GPT nie zdwoi backslasha (\\\\times zamiast \\times), parser po cichu
    "zjada" litere b/f/n/r/t jako znak specjalny, zostawiajac reszte slowa
    (np. "imes" zamiast "\\times").

    Dwuetapowa naprawa (dziala na SUROWYM stringu, przed json.loads):
    1. Kazda znana komenda LaTeX z pojedynczym backslashem -> podwojony
       backslash (nie rusza juz poprawnie podwojonych).
    2. Kazdy pozostaly pojedynczy backslash w stringach, ktory nie jest
       poprawnym escape'em JSON (\\\\, \\", \\n, \\r, \\t, \\b, \\f, \\u) ->
       tez podwojony (bezpieczny domyslny wybor).
    """
    for cmd in _LATEX_CMDS_AT_RISK:
        # (?![a-zA-Z]) zamiast \b - \b nie dziala miedzy litera a cyfra
        # (np. "\\to0"), a to bardzo czeste w tresci matematycznej.
        raw = _re_sanitize.sub(r'(?<!\\)\\' + cmd + r'(?![a-zA-Z])', r'\\\\' + cmd, raw)

    B = chr(92)
    result, i, in_str = [], 0, False
    while i < len(raw):
        c = raw[i]
        if not in_str:
            if c == '"':
                in_str = True
            result.append(c); i += 1; continue
        if c == '"':
            in_str = False; result.append(c); i += 1; continue
        if c == B:
            nc = raw[i + 1] if i + 1 < len(raw) else ''
            if nc in (B, '"', 'n', 'r', 't', 'b', 'f', 'u'):
                result.append(c); result.append(nc); i += 2
            else:
                result.append(B); result.append(B); i += 1
        else:
            result.append(c); i += 1
    return ''.join(result)


# NAPRAWIONE (user, sierpien 2026: "będziemy naprawiać błędy pojedyncze,
# których są miliard... cały system ma być profesjonalny" - po TRZECIM z
# rzedu, waskim zgloszonym przypadku zlego renderowania $/LaTeX w tej
# samej sesji - osierocony dolar, gola litera, literalny "\sqrt{3}" bez
# $ - Question 6 real-testu Trygonometrii): zamiast bez konca dopisywac
# kolejny waski regex-patch dla kolejnego KONKRETNEGO ksztaltu zlego
# LaTeX-a (dokladnie ta sama slepa uliczka co przy matematyce, ktora
# doprowadzila do Warstwy 2.5 - patrz blind_verify.py), JEDNA, OGOLNA
# bramka walidacyjna: sprawdza STRUKTURALNA poprawnosc, nie konkretny
# wzorzec. Zero AI - to czysta, deterministyczna walidacja tekstu,
# uzywajaca JUZ istniejacej, wyczerpujacej listy komend
# (_LATEX_CMDS_AT_RISK) jako zrodla prawdy "co jest komenda LaTeX".
_LATEX_CMDS_AT_RISK_SET = frozenset(_LATEX_CMDS_AT_RISK)
_LATEX_CMD_TOKEN_RE = _re_sanitize.compile(r'\\([a-zA-Z]+)')


_OPTION_PREFIX_RE = _re_sanitize.compile(r'^([a-dA-D]\)\s*)')


def auto_wrap_bare_latex(text: str) -> str:
    """NAPRAWIONE (real-test, sierpien 2026 - Trygonometria: 15 z 20
    wygenerowanych zadan mialy komende LaTeX POZA $ $ - 75%, NIE rzadki
    przypadek): pierwsza wersja tej naprawy TYLKO wykrywala i ODRZUCALA
    (patrz validate_latex_formatting) - przy tak wysokiej czestotliwosci
    odrzucanie zamiast naprawy powodowalo powazny shortfall (4/10 zamiast
    10/10, budzet czasowy wyczerpany na bezowocne rundy dogenerowania).
    Zamiast tylko wykrywac, PROBUJEMY NAJPIERW naprawic automatycznie -
    jesli caly tekst (typowo KROTKIE pole - opcja lub final_answer, NIE
    tresc/wyjasnienie, ktore mieszaja proze z matematyka) ma ZERO znakow
    '$' w ogole, ale ZAWIERA znana komende LaTeX, to (niemal na pewno)
    CALA wartosc miala byc jednym wzorem, ktoremu AI zapomnialo dodac $.
    Owijamy CALA tresc (po opcjonalnym prefiksie 'a) ') w $ ... $.
    BEZPIECZNE: dziala TYLKO gdy $ jest ZERO (nie probuje zgadywac
    granic w tekscie, ktory JUZ ma jakis $ - taki przypadek zostaje przy
    walidacji/odrzuceniu, bo tam granice sa niejednoznaczne)."""
    if not text or '$' in text:
        return text
    if not any(('\\' + cmd) in text for cmd in _LATEX_CMDS_AT_RISK_SET):
        return text
    m = _OPTION_PREFIX_RE.match(text)
    if m:
        return f"{m.group(1)}${text[m.end():]}$"
    return f"${text}$"


def auto_wrap_bare_latex_in_question(item: dict, text_fields: list) -> None:
    """Stosuje auto_wrap_bare_latex do WSZYSTKICH podanych pol (w tym list -
    opcje/options) - MUTUJE `item` w miejscu. Wywolac PRZED validate_
    question_latex, zeby wiekszosc przypadkow byla naprawiona zanim
    dojdzie do (kosztownego - marnuje juz wygenerowana tresc) odrzucenia."""
    for field in text_fields:
        val = item.get(field)
        if val is None:
            continue
        if isinstance(val, list):
            item[field] = [auto_wrap_bare_latex(str(v)) for v in val]
        else:
            item[field] = auto_wrap_bare_latex(str(val))


def validate_latex_formatting(text: str):
    """Zwraca (is_valid: bool, reason: str). Dwa niezalezne sprawdzenia:

    1. Parzysta liczba znakow '$' - nieparzysta oznacza, ze renderowanie
       na pewno sie rozjedzie (albo literalny '$' zostanie w tekscie,
       albo cala reszta tekstu przypadkiem wpadnie "w tryb matematyczny"
       matplotlib mathtext).
    2. ZADNA znana komenda LaTeX (ta sama lista co sanityzacja JSON
       wyzej - '\\sqrt', '\\frac', '\\cdot', itd.) nie wystepuje POZA
       $ ... $ - jesli wystapi, matplotlib renderuje ja jako LITERALNY
       tekst ("5\\sqrt{3}" zamiast symbolu pierwiastka), bo mathtext
       parsuje TYLKO wnetrze $ $, nie zwykly tekst.

    Zwraca PIERWSZY znaleziony problem - wystarczy jeden do odrzucenia."""
    if not text:
        return True, ""
    if text.count('$') % 2 != 0:
        return False, "nieparzysta liczba znakow '$' (renderowanie na pewno sie rozjedzie)"
    for m in _LATEX_CMD_TOKEN_RE.finditer(text):
        cmd = m.group(1)
        if cmd not in _LATEX_CMDS_AT_RISK_SET:
            continue
        if text[:m.start()].count('$') % 2 == 0:
            return False, f"komenda LaTeX '\\{cmd}' poza $ ... $ (bedzie wyrenderowana jako literalny tekst)"
    return True, ""


def validate_question_latex(item: dict, text_fields: list):
    """Sprawdza validate_latex_formatting() na WSZYSTKICH podanych polach
    pytania (w tym listach - np. opcje/options) - zwraca (is_valid, reason)
    dla PIERWSZEGO znalezionego problemu, albo (True, '') jesli wszystko
    OK. `text_fields` = lista nazw kluczy do sprawdzenia (rozne dla
    Quiz/Sprawdzian, zamknietych/otwartych - patrz callerzy)."""
    for field in text_fields:
        val = item.get(field)
        if val is None:
            continue
        values = val if isinstance(val, list) else [val]
        for v in values:
            ok, reason = validate_latex_formatting(str(v))
            if not ok:
                return False, f"pole '{field}': {reason}"
    return True, ""


async def generate_exam_from_image(
    image_data: str,
    difficulty: str = "medium",
    num_questions: int = 10,
    include_open_questions: bool = True
) -> Dict:
    """
    ðŸŽ“ Generuje sprawdzian z obrazka
    
    Args:
        image_data: Base64 encoded image
        difficulty: easy/medium/hard
        num_questions: Liczba pytaÅ„
        include_open_questions: Czy dodaÄ‡ pytania otwarte
    
    Returns:
        Dict z pytaniami, odpowiedziami, kluczem
    """
    try:
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]
        
        # Prompt dla generatora sprawdzianÃ³w
        prompt = f"""
        JesteÅ› doÅ›wiadczonym nauczycielem. Na podstawie tego materiału stwÃ³rz PROFESJONALNY SPRAWDZIAN.
        
        WYMAGANIA:
        - Poziom trudnoÅ›ci: {difficulty}
        - ÅÄ…czna liczba pytaÅ„: {num_questions} (BEZWZGLEDNIE {num_questions} pytan - nie mniej, nie wiecej!)
        - {'Zawiera pytania otwarte' if include_open_questions else 'Tylko test jednokrotnego wyboru'}
        
        FORMAT ODPOWIEDZI (TYLKO JSON, nic wiÄ™cej):
        {{
            "title": "TytuÅ‚ sprawdzianu",
            "subject": "Przedmiot",
            "topic": "Temat",
            "time_limit": 45,
            "total_points": 30,
            "sections": [
                {{
                    "name": "CzÄ™Å›Ä‡ A - Test",
                    "type": "multiple_choice",
                    "points_per_question": 1,
                    "questions": [
                        {{
                            "id": 1,
                            "question": "Treść pytania",
                            "options": ["a) opcja1", "b) opcja2", "c) opcja3", "d) opcja4"],
                            "correct_answer": "c",
                            "explanation": "Wyjaśnienie dlaczego c jest poprawne"
                        }}
                    ]
                }},
                {{
                    "name": "CzÄ™Å›Ä‡ B - Zadania otwarte",
                    "type": "open_ended",
                    "questions": [
                        {{
                            "id": 1,
                            "question": "Treść zadania",
                            "points": 5,
                            "answer": "PrzykÅ‚adowa odpowiedÅº",
                            "grading_criteria": [
                                "Kryterium 1 (2 pkt)",
                                "Kryterium 2 (2 pkt)",
                                "Kryterium 3 (1 pkt)"
                            ]
                        }}
                    ]
                }}
            ]
        }}
        
        WAŻNE:
        - Pytania muszÄ… byÄ‡ KONKRETNE i zwiÄ…zane z materiaÅ‚em na obrazku
        - Dystraktory (zÅ‚e odpowiedzi) muszÄ… byÄ‡ REALISTYCZNE
        - WyjaÅ›nienia muszÄ… byÄ‡ KRÃ“TKIE ale JASNE
        - Zwróć TYLKO JSON, bez dodatkowego tekstu
        """
        
        print(f"ðŸ“‹ GenerujÄ™ sprawdzian (poziom: {difficulty}, pytaÅ„: {num_questions})...")
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "low"
                            }
                        }
                    ]
                }
            ],
            max_tokens=3000,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        result = sanitize_latex_json_backslashes(response.choices[0].message.content)
        exam_data = json.loads(result)
        
        print(f"âœ… Sprawdzian wygenerowany: {exam_data.get('title', 'Bez tytuÅ‚u')}")
        
        return {
            "success": True,
            "exam": exam_data
        }
        
    except Exception as e:
        error_msg = f"âŒ BÅ‚Ä…d generowania sprawdzianu: {str(e)}"
        print(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


async def generate_notes_from_image(
    image_data: str,
    style: str = "academic"
) -> Dict:
    """
    ðŸ“ Generuje notatki z obrazka
    
    Args:
        image_data: Base64 encoded image
        style: academic/simple/visual
    
    Returns:
        Dict z notatkami w Markdown
    """
    try:
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]
        
        style_prompts = {
            "academic": "StwÃ³rz szczegÃ³Å‚owe, akademickie notatki z nagÅ‚Ã³wkami, definicjami i przykÅ‚adami.",
            "simple": "StwÃ³rz proste, zwiÄ™zÅ‚e notatki - punkty i krÃ³tkie wyjaÅ›nienia.",
            "visual": "StwÃ³rz notatki z diagramami (uÅ¼ywaj Mermaid syntax), schematami i wizualizacjami."
        }
        
        prompt = f"""
        {style_prompts.get(style, style_prompts['academic'])}
        
        FORMAT:
        - UÅ¼yj Markdown (nagÅ‚Ã³wki ##, listy -, pogrubienie **)
        - Oznacz kluczowe pojÄ™cia: **POJÄ˜CIE**
        - Dodaj przykÅ‚ady w osobnych sekcjach
        - JeÅ›li to matematyka - uÅ¼yj LaTeX: $x^2$
        
        STRUKTURA:
        ## Temat gÅ‚Ã³wny
        
        ### Definicje
        - **PojÄ™cie 1**: wyjaÅ›nienie
        
        ### Kluczowe informacje
        - Punkt 1
        - Punkt 2
        
        ### PrzykÅ‚ady
        1. PrzykÅ‚ad pierwszy...
        
        ### Podsumowanie
        - NajwaÅ¼niejsze wnioski
        
        Zwróć TYLKO Markdown, bez dodatkowego tekstu.
        """
        
        print(f"ðŸ“ GenerujÄ™ notatki (styl: {style})...")
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "low"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        notes_markdown = response.choices[0].message.content
        
        print(f"âœ… Notatki wygenerowane ({len(notes_markdown)} znakÃ³w)")
        
        return {
            "success": True,
            "notes": notes_markdown,
            "style": style
        }
        
    except Exception as e:
        error_msg = f"âŒ BÅ‚Ä…d generowania notatek: {str(e)}"
        print(error_msg)
        return {
            "success": False,
            "error": error_msg
        }




async def generate_notes_from_topic(
    topic: str,
    level: str = "liceum",
    subject: str = "matematyka",
    style: str = "academic",
    details: str = ""
) -> Dict:
    """
    ðŸ“ Generuje notatki z podanego tematu (bez obrazka)
    """
    try:
        style_prompts = {
            "academic": "SzczegÃ³Å‚owe notatki z definicjami, wzorami i przykÅ‚adami.",
            "simple": "ZwiÄ™zÅ‚e punkty - tylko najwaÅ¼niejsze informacje.",
            "visual": "Notatki z diagramami i wizualizacjami."
        }
        
        prompt = f"""
StwÃ³rz KOMPLETNE, PROFESJONALNE NOTATKI na temat: "{topic}"

WYMAGANIA:
- Przedmiot: {subject}
- Poziom: {describe_level(level, subject=subject)}
- Styl: {style_prompts.get(style, style_prompts['academic'])}
{f'- Dodatkowe szczegÃ³Å‚y: {details}' if details else ''}

FORMAT MARKDOWN:
## {topic}

### Wprowadzenie
[Czym jest to pojÄ™cie?]

### Definicje
- **PojÄ™cie 1**: wyjaÅ›nienie

### Kluczowe informacje
[Fakty, wzory, prawa]

### PrzykÅ‚ady
1. **PrzykÅ‚ad 1**: [rozwiÄ…zanie]

### Podsumowanie
- NajwaÅ¼niejsze wnioski

### WskazÃ³wki do nauki
[Jak siÄ™ tego nauczyÄ‡?]

WAŻNE:
- Markdown (##, -, **)
- PojÄ™cia: **POJÄ˜CIE**
- Wzory matematyczne ZAWSZE w dolarach: $x^2$, $\\frac{{a}}{{b}}$, $\\sqrt{{x}}$ — ZAKAZ wzorów bez dolarów
- Do mnozenia uzywaj $\\cdot$ lub $\\times$ — NIGDY nie pisz samego 1 jako operatora
- Calki ZAWSZE: $\\int_{{0}}^{{1}}$ — NIGDY nie pisz $int bez backslasha
- Sumy ZAWSZE: $\\sum_{{i=1}}^{{n}}$ — NIGDY $sum bez backslasha
- Granice ZAWSZE: $\\lim_{{x \\to 0}}$ — NIGDY $lim bez backslasha
- Min 300 sÅ‚Ã³w
- PO POLSKU!

Zwróć TYLKO Markdown.
"""
        
        print(f"ðŸ“ GenerujÄ™ notatki: {topic} ({level}, {subject})...")
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
            temperature=0.7
        )
        
        notes = response.choices[0].message.content
        print(f"âœ… Notatki: {len(notes)} znakÃ³w")
        
        return {
            "success": True,
            "notes": notes,
            "topic": topic,
            "level": level,
            "subject": subject,
            "style": style
        }
        
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d: {str(e)}")
        return {"success": False, "error": str(e)}



async def generate_quiz_from_image(
    image_data: str,
    num_questions: int = 5,
    difficulty: str = "medium"
) -> Dict:
    """ðŸŽ“ Generuje quiz z obrazka"""
    try:
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]

        async def _raw_call(n: int) -> dict:
            return await _raw_generate_quiz_from_image_call(image_data, n, difficulty)

        t_start = time.monotonic()
        quiz_data = await _raw_call(_buffered_count(num_questions))
        print(f"âœ… Quiz: {quiz_data.get('title', 'Quiz')}")
        quiz_data = fix_latex_in_quiz(quiz_data)
        quiz_data = await _verify_and_fill_quiz_math(
            quiz_data, num_questions, lambda n, avoid_block="": _raw_call(max(n, _MIN_FILL_BATCH)), t_start=t_start, difficulty=difficulty
        )
        return {"success": True, "quiz": quiz_data}

    except Exception as e:
        print(f"âŒ BÅ‚Ä…d: {str(e)}")
        return {"success": False, "error": str(e)}


async def _raw_generate_quiz_from_image_call(image_data: str, num_questions: int, difficulty: str) -> dict:
    """Jedno 'surowe' wywolanie AI (bez weryfikacji sympy) dla
    generate_quiz_from_image - wydzielone, zeby dogenerowywanie
    brakujacych pytan moglo to wywolywac wielokrotnie."""
    prompt = f"""
StwÃ³rz QUIZ na podstawie tego materiału.

PARAMETRY:
- Liczba pytaÅ„: {num_questions}
- TrudnoÅ›Ä‡: {difficulty}

FORMAT (TYLKO JSON):
{{
    "title": "TytuÅ‚ quizu",
    "questions": [
    {{
        "id": 1,
        "question": "Treść pytania",
        "options": ["A", "B", "C", "D"],
        "correct": 0,
        "explanation": "Wyjaśnienie"
    }}
    ]
}}

WAŻNE:
- Pytania z materiału na obrazku
- Na początku JSON dodaj pole "subject" z wykrytym przedmiotem (matematyka/biologia/fizyka/chemia/historia)
- "correct" = index (0-3)
- Wzory matematyczne ZAWSZE w dolarach: $x^2$, $\\frac{{a}}{{b}}$, $\\sqrt{{x}}$
- Zwróć TYLKO JSON
"""
    
    print(f"ðŸŽ“ Quiz z obrazka ({num_questions} pytaÅ„)...")
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "low"
                        }
                    }
                ]
            }
        ],
        # Skalujemy z liczba pytan - patrz analogiczny fix i komentarz w
        # _raw_generate_quiz_topic_once (bufor moze prosic o 20+ pytan).
        max_tokens=min(8000, max(2000, 500 + num_questions * 350)),
        temperature=0.7,
        response_format={"type": "json_object"}
    )

    raw_content = sanitize_latex_json_backslashes(response.choices[0].message.content)
    quiz_data = json.loads(raw_content)
    return quiz_data




import re as re_module

# Polskie laczniki/czasowniki, ktore MUSZA zostac poza $...$ (inaczej KaTeX
# czyta je jako sklejone zmienne, np. "lub" -> l*u*b, "wynosi" -> w*y*n*o*s*i).
# Dzielimy po nich tekst i opakowujemy w $...$ tylko fragmenty MIEDZY nimi,
# ktore zawieraja LaTeX. Rozszerzone o czasowniki typowe w zdaniach z wynikiem
# liczbowym ("X wynosi ..."), nie tylko czyste spojniki.
_LATEX_CONNECTOR_RE = re_module.compile(
    r'\s+(lub|i|oraz|albo|gdy|dla|wynosi|wynoszą|jest równ[ea]|są równe|to)\s+'
)
def _wrap_plain_segment(segment):
    """Opakowuje w $...$ fragmenty z komendami LaTeX w TEKSCIE BEZ zadnych
    istniejacych dolarow - z podzialem na polskich lacznikach jak wyzej."""
    if '\\' not in segment:
        return segment
    parts = _LATEX_CONNECTOR_RE.split(segment)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(' ' + part + ' ')
            continue
        stripped = part.strip()
        if stripped and '\\' in stripped:
            leading = part[:len(part) - len(part.lstrip())]
            trailing = part[len(part.rstrip()):]
            out.append(leading + '$' + stripped + '$' + trailing)
        else:
            out.append(part)
    return ''.join(out)

def _wrap_naked_latex(t):
    """Opakowuje w $...$ fragmenty zawierajace komendy LaTeX (\\frac, \\pm...),
    ktore model zwrocil bez dolarow. Dzieli string po KAZDYM pojedynczym $
    (nie po parach) - parzyste indeksy (0, 2, 4...) sa ZAWSZE poza $...$,
    nieparzyste ZAWSZE wewnatrz, zgodnie z tym jak faktycznie dziala
    naprzemienne parowanie delimiterow (tak samo jak KaTeX je interpretuje)."""
    if not t or '\\' not in t:
        return t
    parts = t.split('$')
    out = [_wrap_plain_segment(part) if i % 2 == 0 else part for i, part in enumerate(parts)]
    return '$'.join(out)


_MATH_INDICATOR_RE = re_module.compile(r'[\d\\=+\-*/^<>_{}]')
# NAPRAWIONE (port fixu ze Sprawdzianu, sierpien 2026 - user zglosil
# realny przypadek "pierwszych n$ wyrazów"): pojedyncza litera zmiennej
# w LaTeX, np. "$n$", nie pasowala do _MATH_INDICATOR_RE - w pelni
# poprawna para $n$ byla wiec uznawana za "pomylkowy" pojedynczy dolar,
# co (przez zamierzone dzialanie skanowania - wraca do sprawdzania OD
# zamykajacego $, bo moze byc otwarciem kolejnego wzoru) kaskadowo
# gubilo otwierajacy $ NASTEPNEGO, oddzielnego "$n$" gdzies dalej w
# tekscie (jesli tresc miedzy nimi zawierala cyfry - falszywie zaliczana
# jako "matematyka"), zostawiajac osierocony ZAMYKAJACY dolar - dajac
# dokladnie literalny "n$" w koncowym tekscie. Pelne uzasadnienie i
# identyczna naprawa - patrz komentarz w exam_pdf_generator.py.
_BARE_VARIABLE_RE = re_module.compile(r'^[a-zA-Z]$')


def _strip_mistaken_dollar_pairs(t):
    """Usuwa POJEDYNCZE "sieroce" dolary, ktore nie maja prawdziwego
    partnera - typowo model wstawia zbedny $ tuz PRZED prawdziwym wzorem
    (np. "Liczymy delte:$ $\\Delta=5$" - pierwszy $ nie powinien tam byc).

    Skanuje string ZNAK PO ZNAKU zamiast parowac dolary z gory sekwencyjnie
    (1-2, 3-4, 5-6...) - sekwencyjne parowanie zawodzi tutaj, bo KAZDY
    sierocy dolar przesuwa numeracje WSZYSTKICH kolejnych par o jeden, wiec
    prawdziwa tresc wzoru zaczyna wygladac jak "para" z sasiednim sierocym
    dolarem, a jej WLASCIWY partner zostaje osierocony z kolei - kaskada
    bledow. Zamiast tego: dla kazdego napotkanego $, patrzymy TYLKO na
    tekst do NASTEPNEGO $ - jesli wyglada na matematyke (cyfra, backslash,
    operator, indeks dolny, nawias klamrowy), zostawiamy pare nietknieta i
    skaczemy ZA nia; jesli nie, ten JEDEN $ jest sierocy - usuwamy go i
    wracamy do skanowania od zaraz po nim (NIE konsumujemy $, na ktory
    patrzylismy jako "koniec" - moze on byc prawdziwym otwarciem kolejnego,
    realnego wzoru, tak jak w przykladzie wyzej)."""
    out = []
    i, n = 0, len(t)
    while i < n:
        if t[i] != '$':
            out.append(t[i])
            i += 1
            continue
        j = t.find('$', i + 1)
        if j == -1:
            out.append(t[i])
            i += 1
            continue
        content = t[i + 1:j]
        if _MATH_INDICATOR_RE.search(content) or _BARE_VARIABLE_RE.match(content):
            out.append(t[i:j + 1])
            i = j + 1
        else:
            i += 1  # sierocy $ - pomin, NIE konsumuj drugiego $
    return ''.join(out)

def fix_latex_in_quiz(quiz_data):
    """Naprawia typowe bledy LaTeX zanim dotrze do frontendu"""
    def fix(t):
        if not t: return t
        # Napraw $1 jako pm/plus-minus - TYLKO gdy "1" jest CALA
        # zawartoscia wyrazenia (np. "$1$", "$1 $", "=$1$") - NIGDY gdy
        # jest czescia dluzszego, prawdziwego wyrazenia liczbowego.
        # NAPRAWIONE (zgloszony realny bug, potwierdzony realnym testem
        # generacji trygonometrii, sierpien 2026): poprzednia wersja
        # robila BEZWARUNKOWY string-replace kazdego "$1 " GDZIEKOLWIEK
        # w tekscie - psulo to KAZDE rownanie zaczynajace sie od cyfry 1
        # (np. prawdziwa tozsamosc "$1 - 2\\sin^2(x) = \\cos(2x)$")
        # zamieniajac na uszkodzone "$\\pm$- 2\\sin^2(x)...", z dodatkowym
        # rozjechaniem parzystosci dolarow w reszcie tekstu (dokladnie
        # zgloszony objaw "±±..." + polamane "$"). Regex z kotwicami do
        # konca wyrazenia ($) eliminuje ten falszywy alarm, zachowujac
        # oryginalny, historyczny przypadek (samotne "$1$" zamiast "±").
        t = re_module.sub(r'\$\s*1\s*\$', '$\\\\pm$', t)
        t = re_module.sub(r'=\s*\$\s*1\s*\$', '=$\\\\pm$', t)
        # Napraw spacje w frac
        import re as _r3
        t = _r3.sub(r'\\frac\{\s*-\s*', r'\\frac{-', t)
        t = _r3.sub(r'\\frac\{\s*', r'\\frac{', t)
        # Napraw znak funkcji (⁡) i stopnie (o -> °)
        t = t.replace('\u2061', '')  # invisible function application
        t = _r3.sub(r'(sin|cos|tan|log|ln)(\d+)o\b', r'\\1(\2°)', t)
        # Usun \newline / \\ (komendy lamania linii) - model czasem wstawia
        # je jako separator krokow w wielokrokowych wyjasnieniach (np. Viete),
        # co razem z ponizszym naiwnym "$$"->"$" psuje parzystosc dolarow i
        # objawia sie w przegladarce jako zdublowany/polamany tekst (KaTeX
        # renderuje $...$ pary przesuniete o jeden segment). Usuwamy PRZED
        # zwijaniem "$$", zeby nie zostawiac dziury w parzystosci dolarow.
        t = t.replace('\\newline', ' ').replace('\\\\', ' ')
        # Napraw podwojne (lub wiecej) dolary na pojedyncze - regex (nie
        # str.replace, ktory nie usuwa NIEPARZYSTYCH ciagow jak "$$$" w
        # jednym przebiegu) lapie caly ciag naraz.
        t = _r3.sub(r'\${2,}', '$', t)
        # Usun $...$ pary, ktorych zawartosc nie wyglada na matematyke (patrz
        # _strip_mistaken_dollar_pairs) - to niemal zawsze "sierocy" dolar
        # wstawiony tuz przed prawdziwym wzorem, ktory inaczej przesuwa
        # parzystosc WSZYSTKICH kolejnych par (patrz docstring funkcji).
        # Kolejny \${2,} sprzata ewentualna nowa przyleglosc po usunieciu.
        t = _strip_mistaken_dollar_pairs(t)
        t = _r3.sub(r'\${2,}', '$', t)
        # Napraw rac{ -> \frac{
        t = t.replace("\\rac{", "\\frac{")
        t = re_module.sub(r"(?<![a-zA-Z\\])rac\{", r"\\frac{", t)
        # Napraw ext{ -> \text{
        t = t.replace("\\ext{", "\\text{")
        t = re_module.sub(r"(?<![a-zA-Z\\])ext\{", r"\\text{", t)
        # Napraw imes -> \times (backslash+t z \times bywa "zjadany" jak tabulator)
        # UWAGA: \b nie dziala miedzy litera a cyfra (np. "4imes1"), stad lookahead na litere
        t = t.replace("\\imes", "\\times")
        t = re_module.sub(r"(?<![a-zA-Z\\])imes(?![a-zA-Z])", r"\\times", t)
        # Usun \text{...} - zamien na sam tekst bez komendy
        t = re_module.sub(r"\\text\{([^}]*)\}", r"\1", t)
        # Opakuj "nagie" wzory LaTeX w $...$, jesli model zapomnial dolarow.
        # UWAGA: poprzedni warunek sprawdzal podwojny backslash ("\\\\" w
        # zrodle Pythona = dwa literalne znaki \\), a po json.loads() wzor
        # ma TYLKO pojedynczy backslash (\frac) - warunek nigdy sie nie
        # spelnial i "nagie" wzory (np. w opcjach odpowiedzi z ulamkami)
        # trafialy na frontend bez dolarow, wiec KaTeX ich nie renderowal.
        t = _wrap_naked_latex(t)
        # Ostatni bezpiecznik: _wrap_naked_latex czasem opakowuje "zewnetrzny"
        # fragment, ktory zaczyna sie TUZ PO juz istniejacym $ (np. gdy caly
        # fragment miedzy wzorami zawiera "\") - to tworzy NOWY, przypadkowy
        # "$$" na styku. KaTeX auto-render traktuje "$$" jako poczatek
        # DISPLAY math (szuka NASTEPNEGO "$$"), wiec taki przypadkowy styk
        # potrafi polknac cala reszte tekstu jako jeden zle sformatowany
        # wzor - stad finalny collapse PO wszystkich innych krokach.
        t = _r3.sub(r'\${2,}', '$', t)
        return t
    if "questions" in quiz_data:
        for q in quiz_data["questions"]:
            if "question" in q: q["question"] = fix(q["question"])
            if "explanation" in q: q["explanation"] = fix(q["explanation"])
            if "options" in q: q["options"] = [fix(o) for o in q["options"]]
    return quiz_data



async def generate_quiz_from_text(
    text: str,
    num_questions: int = 5,
    difficulty: str = "medium",
    level: str = "liceum"
) -> Dict:
    """Generuje quiz z tekstu PDF przez GPT-4o"""
    try:
        prompt = f"""Stwórz QUIZ na podstawie tego tekstu.

PARAMETRY:
- Liczba pytań: {num_questions}
- Trudność: {difficulty}
- Poziom: {level}

TEKST:
{text[:7000]}

FORMAT (TYLKO JSON):
{{
    "title": "Tytuł quizu",
    "questions": [
        {{
            "id": 1,
            "question": "Treść pytania",
            "options": ["A", "B", "C", "D"],
            "correct": 0,
            "explanation": "Wyjaśnienie"
        }}
    ]
}}

WAŻNE:
- Pytania TYLKO z podanego tekstu
- "correct" = index (0-3)
- Wzory matematyczne ZAWSZE w dolarach: $x^2$, $\\frac{{a}}{{b}}$
- Zwróć TYLKO JSON
"""
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3
        )

        import json as _json, re as _re
        raw = response.choices[0].message.content
        # NAPRAWIONE (kilka bledow na raz):
        # 1. Podwojne klamry {{ }} POZA f-stringiem promptu (linie ponizej
        #    byly zwyklym kodem Pythona, nie f-stringiem) - kazde uzycie
        #    "{{...}}" tworzylo w Pythonie ZBIOR zawierajacy slownik, co
        #    zawsze rzucalo "TypeError: unhashable type: 'dict'". Ta funkcja
        #    nigdy nie dzialala - kazde wywolanie (generowanie quizu z PDF)
        #    konczylo sie bledem, jeszcze zanim doszlo do OpenAI.
        # 2. Brakowalo sanitize_latex_json_backslashes() (patrz
        #    generate_quiz_from_topic - identyczny problem z "\neq" itp.
        #    mylonym z escape'em JSON \n).
        # 3. fix_latex_in_quiz() oczekuje SLOWNIKA z kluczem "questions",
        #    a dostawal samą listę pytań - warunek "questions" in quiz_data
        #    byl wiec zawsze falszywy i naprawa LaTeX nigdy sie nie wykonywala.
        raw = sanitize_latex_json_backslashes(raw)
        match = _re.search(r'\{.*\}', raw, _re.DOTALL)
        if not match:
            return {"success": False, "error": "Błąd parsowania"}
        data = _json.loads(match.group())
        data = fix_latex_in_quiz(data)
        return {"success": True, "quiz": {"title": data.get("title", "Quiz z PDF"), "questions": data.get("questions", [])}}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def _raw_generate_quiz_topic_once(
    topic: str, effective_topic_is_forced: bool, subject: str, level: str,
    num_questions: int, difficulty: str, wlasne_instrukcje: str, diversity_hint: str = "",
    avoid_block: str = ""
) -> Dict:
    """Jedno 'surowe' wywolanie AI (bez weryfikacji sympy) dla
    generate_quiz_from_topic - zbudowanie prompta, wywolanie modelu i
    parsowanie JSON. Wydzielone, zeby dogenerowywanie brakujacych pytan
    (patrz _verify_and_fill_quiz_math) moglo to wywolywac wielokrotnie
    bez rekurencyjnego uruchamiania calego cyklu weryfikacja+uzupelnianie."""
    difficulty_map = {"easy": "łatwy", "medium": "średni", "hard": "trudny"}
    poziom_opis = describe_level(level, subject=subject)
    trudnosc_opis = difficulty_map.get(difficulty, difficulty)

    # NOWE: "gated injection" skali trudnosci 1-10 - TYLKO dla tematu
    # "rownania kwadratowe" (jedyny z pelna infrastruktura weryfikacji -
    # math_verify.py + final_answer). Inne tematy dzialaja jak dotychczas
    # (samo slowo trudnosci) - to swiadomie ograniczone rozszerzenie.
    difficulty_anchor_blok = ""
    if is_quadratic_equation_topic(topic):
        anchor_text = get_quadratic_difficulty_anchor(difficulty)
        if anchor_text:
            difficulty_anchor_blok = f"\n{anchor_text}\n"

    # ETAP 6: analogiczna "gated injection" dla ciagow arytmetycznych/
    # geometrycznych - dziala TYLKO gdy temat nie zostal juz rozpoznany
    # jako rownanie kwadratowe (temat nie moze byc jednoczesnie obiema).
    elif is_sequence_topic(topic):
        anchor_text = get_sequence_difficulty_anchor(difficulty)
        if anchor_text:
            difficulty_anchor_blok = f"\n{anchor_text}\n"

    # ETAP 7: analogiczna "gated injection" dla trygonometrii.
    elif is_trigonometry_topic(topic):
        anchor_text = get_trig_difficulty_anchor(difficulty)
        if anchor_text:
            difficulty_anchor_blok = f"\n{anchor_text}\n"

    # ETAP 8: analogiczna "gated injection" dla funkcji (liniowej,
    # kwadratowej JAKO FUNKCJI, wykladniczej). is_quadratic_function_topic
    # sprawdzany PO is_quadratic_equation_topic - rownania zachowuja
    # pierwszenstwo dla tematow, ktore wygladaja jak obie naraz.
    elif is_linear_function_topic(topic):
        anchor_text = get_linear_function_difficulty_anchor(difficulty)
        if anchor_text:
            difficulty_anchor_blok = f"\n{anchor_text}\n"
    elif is_quadratic_function_topic(topic):
        anchor_text = get_quadratic_function_difficulty_anchor(difficulty)
        if anchor_text:
            difficulty_anchor_blok = f"\n{anchor_text}\n"
    elif is_exponential_function_topic(topic):
        anchor_text = get_exponential_function_difficulty_anchor(difficulty)
        if anchor_text:
            difficulty_anchor_blok = f"\n{anchor_text}\n"

    instrukcje_blok = ""
    if wlasne_instrukcje and wlasne_instrukcje.strip():
        instrukcje_blok = (
            "\n=== WLASNE INSTRUKCJE (NAJWYZSZY PRIORYTET) ===\n"
            "Uczen podal nastepujace instrukcje. MUSISZ je bezwzglednie uwzglednic:\n"
            + wlasne_instrukcje.strip() + "\n"
            + "Dostosuj CALY quiz do powyzszych wskazowek.\n"
        )

    if effective_topic_is_forced:
        temat_instrukcja = (
            f'KRYTYCZNE: Temat "{topic}" ma NAJWYZSZY PRIORYTET — generuj TYLKO '
            f'pytania o ten temat.\nPoziom okresla trudnosc i jezyk pytan, NIE '
            f'zmienia tematu.\nNIGDY nie zmieniaj tematu na inny.'
        )
    else:
        temat_instrukcja = (
            f'KRYTYCZNE: User nie podal konkretnego tematu (podal tylko przedmiot). '
            f'Spojrz na liste tematow w "Zakres materialu z przedmiotu" w opisie '
            f'DOKLADNY POZIOM ponizej - to jedyne dozwolone tematy. Wybierz z NIEJ '
            f'DOKLADNIE JEDEN temat (skopiuj go, nie parafrazuj) i podaj go w polu '
            f'"title" quizu. ZAKAZ: NIE wybieraj tematu, ktorego nie ma doslownie w '
            f'tej liscie - w szczegolnosci NIE wybieraj automatycznie "rownan '
            f'kwadratowych" ani innego "typowego" skojarzenia z matematyka liceum, '
            f'jesli nie ma go w podanym zakresie tej konkretnej klasy. Caly quiz '
            f'musi byc TYLKO o tym jednym, wybranym temacie - NIE mieszaj kilku '
            f'roznych tematow w jednym quizie.'
        )

    prompt = f"""Stwórz quiz na temat: "{topic}"

PARAMETRY:
- Przedmiot: {subject}
- Liczba pytań: {num_questions}
- DOKŁADNY POZIOM: {poziom_opis}
- Trudność: {trudnosc_opis}
{difficulty_anchor_blok}
{instrukcje_blok}
{diversity_hint}
{avoid_block}
{temat_instrukcja}
SPOJNOSC TRUDNOSCI: wszystkie pytania w quizie musza byc na TYM SAMYM poziomie
trudnosci - NIE mieszaj jednego trudnego pytania z parametrem/dowodem z drugim
pytaniem, ktore jest banalnym dzialaniem arytmetycznym (np. dodawaniem ulamkow
prostszym niz material tej klasy). Kazde pytanie ma osobno spelniac wymagania
z "DOKLADNY POZIOM" i "Trudnosc" powyzej.
KAZDE pytanie musi byc kompletne i jednoznaczne — nigdy nie urywaj zdania ani wzoru.
Nigdy nie pisz 'cos 14?' bez kontekstu — zawsze pelne rownanie np. 'cos(x) = 0.5'.
Jeśli poziom to podstawówka — NIE pytaj o pochodne ani logarytmy.

WERYFIKACJA OBLICZEN - KRYTYCZNE (bledny klucz odpowiedzi to powazny blad,
tak samo powazny jak zbyt latwe pytanie): Dla KAZDEGO pytania z obliczeniami
(rownania, nierownosci, delta/wyroznik, pierwiastki, prawdopodobienstwo,
pochodne, calki itp.) MUSISZ, ZANIM zapiszesz "correct": 1) rozwiazac
zadanie NAPRAWDE krok po kroku, 2) PODSTAWIC otrzymany wynik z powrotem do
pierwotnego rownania/warunku i sprawdzic, czy sie zgadza (nie tylko "czy
wyglada podobnie"), 3) upewnic sie, ze "correct" wskazuje DOKLADNIE ta
opcje z "options", ktora odpowiada Twojemu sprawdzonemu wynikowi - jesli
zadna opcja nie pasuje, POPRAW opcje zamiast zostawiac bledny klucz. Jesli
po podstawieniu wynik sie NIE zgadza - przelicz jeszcze raz od nowa, NIE
zgaduj.

KOLEJNOSC TWORZENIA OPCJI (zeby nie powtorzyc powyzszego bledu): NAJPIERW
rozwiaz zadanie i zapisz sobie prawdziwy wynik, DOPIERO POTEM wymysl 3
bledne dystraktory wokol niego. NIGDY nie rob tego odwrotnie (najpierw
4 "prawdopodobnie wygladajace" opcje, potem zgadywanie ktora pasuje) -
to najczestsza przyczyna sytuacji, w ktorej PRAWDZIWA odpowiedz nie
znajduje sie wsrod opcji wcale. Jesli rownanie z parametrem ma parametr
jako WSPOLCZYNNIK PRZY x^2 (np. $ax^2+...=0$) - to trudniejszy przypadek:
pamietaj o zalozeniu wspolczynnik != 0 (inaczej rownanie przestaje byc
kwadratowe) w obliczeniach delty I w opcjach.

POLE "final_answer" - NOWE, OBOWIAZKOWE: oprocz "correct" i "explanation",
KAZDE pytanie MUSI miec pole "final_answer" - skopiuj do niego DOKLADNIE
(znak w znak, razem z $...$) tekst TEJ JEDNEJ opcji z "options", ktora
jest Twoja sprawdzona, poprawna odpowiedzia. NIE parafrazuj, NIE skracaj,
NIE pisz wlasnymi slowami - to ma byc doslowna kopia jednej z 4 opcji.
System automatycznie sprawdza to pole i ODRZUCA pytanie, jesli
"final_answer" nie jest identyczny z zadna opcja - wiec musi dokladnie
pasowac.

GRAMATYKA - KRYTYCZNE (czesty blad): gdy odpowiedzia jest ZBIOR/
PRZEDZIAL/NIEROWNOSC (nie jedna liczba), pytanie o parametr MUSI byc w
LICZBIE MNOGIEJ: "Dla jakich wartości parametru {{x}}..." - NIGDY "Dla
jakiej wartości parametru {{x}}..." (liczba pojedyncza jest gramatycznie
bledna, bo sugeruje jedna wartosc, a szukamy calego zbioru). Ta sama
zasada dotyczy KAZDEGO tematu z parametrem (rownania, funkcje,
nierownosci, trygonometria), nie tylko rownan kwadratowych.
POPRAWNIE: "Dla jakich wartości parametru m równanie ... ma dwa różne pierwiastki?"
BLEDNIE: "Dla jakiej wartości parametru m równanie ... ma dwa różne pierwiastki?"

WZORY MATEMATYCZNE - KRYTYCZNE:
- Kazdy wzor w $...$ np: $x^2 + 3x = 0$
- ZAWSZE \\frac{{ nie rac{{ nie \\rac{{
- NIE uzywaj \\underbrace \\usepackage ani innych komend z \\u na poczatku
- NIE uzywaj cudzyslowow wewnatrz tekstu pytan
- NIGDY nie wstawiaj polskich slow (np. "i", "lub", "oraz", "gdy") do srodka $...$ -
  pisz je jako zwykly tekst POZA wzorem. POPRAWNIE: "$x = 2$ i $x = 3$".
  BLEDNIE: "$x = 2 i x = 3$" (slowo "i" wewnatrz wzoru wyglada wtedy jak zmienna).

POLE "explanation" - WIELOKROKOWE OBLICZENIA (KRYTYCZNE, czesty blad):
Gdy wyjasnienie ma kilka krokow (np. licz delte, potem warunek, potem
wzory Viete'a) - pisz je jako JEDNO, CIAGLE zdanie/akapit zwyklej prozy
PO POLSKU, w ktorym TYLKO pojedyncze wzory sa opakowane w $...$ (kazdy
z osobna, krotko). NIGDY nie uzywaj \\newline, \\\\ ani zadnej innej
komendy LaTeX do lamania linii wewnatrz "explanation" - to psuje
renderowanie (dublowanie tekstu, widoczne surowe komendy). NIGDY nie
opakowuj calego zdania ani wielu wzorow naraz w jeden $...$ - kazdy
wzor ma miec WLASNA, osobna pare $...$.
POPRAWNIE: "Liczymy deltę: $\\Delta = (m-3)^2 - 4m = m^2 - 10m + 9$. Warunek na dwa różne pierwiastki: $\\Delta > 0$, czyli $m^2 - 10m + 9 > 0$, co daje $m < 1$ lub $m > 9$."
BLEDNIE: "Liczymy deltę:$ $\\Delta = ...$ $\\newline Warunek$ $\\Delta > 0$$. \\newline ..." (zlamane dolary, \\newline, dublowanie).

POLE "diversity_tag" - NOWE, OBOWIAZKOWE (pomaga systemowi pilnowac
roznorodnosci w quizie): dla KAZDEGO pytania podaj obiekt z 4 KROTKIMI
(kilka slow, NIE zdaniami) polami opisujacymi WLASNYMI slowami typ
rozumowania w TYM pytaniu:
  "skill" - glowna umiejetnosc/wzor uzyty (np. "wzor na delte", "wzory Viete'a", "twierdzenie sinusow")
  "concept" - kluczowe pojecie/wariant (np. "parametr jako wspolczynnik liniowy", "parametr jako wyraz wolny", "kat specjalny w radianach")
  "task_type" - co dokladnie trzeba zrobic (np. "wyznacz parametr z warunku na delte", "oblicz wartosc wyrazenia", "rozwiaz rownanie")
  "reasoning" - krotki opis krokow (np. "oblicz delte, rozwiaz nierownosc, zapisz przedzial")
KRYTYCZNE: jesli w JEDNEJ partii generujesz WIELE pytan, CELOWO
ROZNICUJ te 4 pola miedzy pytaniami tego samego tematu - to jest
sygnal dla systemu, ktory pilnuje, zeby quiz nie skladal sie z 10
pytan o tym samym schemacie (tylko z innymi liczbami/literami).
Jesli dwa pytania maja NAPRAWDE ten sam typ rozumowania - ich tagi
tez powinny to szczerze odzwierciedlac (nie oszukuj systemu sztucznie
roznymi slowami dla identycznego zadania).

FORMAT (TYLKO JSON):
{{
    "title": "{topic} - Quiz",
    "questions": [
        {{
            "id": 1,
            "question": "Pytanie $x^2 = 4$",
            "options": ["$x = 2$", "$x = -2$", "$x = \\pm 2$", "$x = 4$"],
            "correct": 2,
            "final_answer": "$x = \\pm 2$",
            "explanation": "Bo $x = \\pm 2$",
            "diversity_tag": {{
                "skill": "pierwiastkowanie rownania kwadratowego czystego",
                "concept": "rownanie postaci x^2=a",
                "task_type": "rozwiaz rownanie",
                "reasoning": "pierwiastkuj obie strony, uwzglednij znak plus-minus"
            }}
        }}
    ]
}}

ZASADY:
- Pytania konkretne i merytoryczne
- correct = indeks (0-3)
- final_answer = doslowna kopia poprawnej opcji z "options" (patrz wyzej)
- diversity_tag = 4 krotkie pola opisujace typ rozumowania (patrz wyzej) - ROZNE dla roznych pytan w tej samej partii
- Po polsku
- TYLKO JSON"""

    print(f"ðŸŽ“ Quiz: {topic} ({num_questions} pytaÅ„)...")

    system = (
        "Jestes generatorem quizow edukacyjnych. Zwracasz TYLKO poprawny JSON.\n"
        "ZAKAZ: nie uzywaj cudzyslowow wewnatrz tekstu pytania - psuja JSON.\n"
        "ZAKAZ: nie pisz backslash-u (\\u) w wzorach - psuje JSON.\n"
        "Zamiast \\underbrace, \\usepackage itp - opisz slownie.\n\n"
        "POZIOM - dostosuj pytania scisle:\n"
        "studia = calki, macierze, szeregi, rownania rozniczkowe\n"
        "liceum = material maturalny\n"
        "podstawowka = ulamki, procenty\n\n"
        "WZORY: kazdy wzor w $...$ lub $$...$$\n"
        "ZAWSZE \\\\frac{ nie rac{ nie \\\\rac{\n"
        "ZAWSZE \\\\text{ nie ext{\n"
        "Dobry przyklad opcji: [$x = \\\\frac{1}{2}$, $x = 2$, $x = -1$, $x = 0$]"
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        # NAPRAWIONE: stale max_tokens=2500 wystarczalo dla malych partii,
        # ale przy buforowaniu (_buffered_count moze prosic o 20+ pytan
        # naraz) odpowiedz AI byla ucinana w polowie generowania, co
        # psulo JSON calkowicie (blad "Unterminated string" - caly quiz
        # padal, nie tylko nadmiarowe pytania). Skalujemy z liczba pytan.
        max_tokens=min(8000, max(2500, 500 + num_questions * 350)),
        temperature=0.7,
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content
    # NAPRAWIONE: brakowalo tu sanitize_latex_json_backslashes() (juz
    # uzywanego w generate_exam_from_image/generate_quiz_from_image).
    # Bez tego np. "\neq" (pojedynczy backslash) jest dla json.loads()
    # NIEODROZNIALNE od poprawnego escape'a JSON \n (nowa linia) - parser
    # PO CICHU (bez wyjatku, wiec "Proba 1" zawsze "sie udawala") zjadal
    # "\n" jako prawdziwa nowa linie, zostawiajac samo "eq" - w quizie
    # wychodzilo to jako zlamane "$a \n eq 1$" zamiast "$a \neq 1$".
    raw = sanitize_latex_json_backslashes(raw)
    # Proba 1: bezposrednio
    try:
        quiz_data = json.loads(raw)
    except Exception:
        # Proba 2: napraw \u ktore nie sa unicode escape
        import re as _re2
        raw2 = _re2.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', raw)
        try:
            quiz_data = json.loads(raw2)
        except Exception:
            # Proba 3: agresywne czyszczenie - zamien wszystkie \ na \\
            raw3 = raw.replace('\\', '\\\\')
            raw3 = raw3.replace('\\\\\'"', '\\\\\\\\"')
            quiz_data = json.loads(raw3)
    quiz_data = fix_latex_in_quiz(quiz_data)
    print(f"Quiz: {quiz_data.get('title')}")
    return quiz_data


# NAPRAWIONE (audyt realnej generacji V1, sierpien 2026 - znany problem
# czasowy dla duzych partii): JEDNO wywolanie AI proszace o ~26 pytan
# naraz (typowy bufor dla n=20) trwalo w praktyce 35-45s SAMO W SOBIE -
# zjadalo to niemal caly globalny budzet 30s (_verify_and_fill_quiz_math),
# zanim petla dogenerowania zdazyla wykonac choc jedna runde. Zmierzone
# tempo generowania jest w przyblizeniu LINIOWE wzgledem liczby pytan
# (~1.5-2s/pytanie, niezaleznie od tematu) - NIE ma sensu podnosic
# limitu czasowego (user: nie podnosic slepo limitow), tylko skrocic
# CZAS ZEGAROWY samego wywolania. Rozwiazanie: zamiast JEDNEGO
# sekwencyjnego wywolania na `total_n` pytan, dzielimy na kilka
# MNIEJSZYCH wywolan i odpalamy je ROWNOLEGLE (asyncio.gather) - laczna
# liczba zamawianych pytan (i tokenow wyjsciowych/kosztu) jest
# IDENTYCZNA, ale czas zegarowy spada do czasu NAJWOLNIEJSZEGO
# pojedynczego wywolania zamiast sumy wszystkich.
def _parallel_batch_sizes(total: int, target_chunk: int = 13, max_chunks: int = 3) -> list:
    """Dzieli `total` na az `max_chunks` w przyblizeniu rownych czesci,
    kazda okolo `target_chunk` pytan. Zwraca [total] bez zmian (brak
    podzialu), jesli `total` juz miesci sie w jednym docelowym batchu -
    male partie i typowe rundy dogenerowania (missing < target_chunk)
    zachowuja sie DOKLADNIE jak przed ta zmiana, jeden request."""
    if total <= target_chunk:
        return [total]
    n_chunks = min(max_chunks, -(-total // target_chunk))  # ceil division
    base, remainder = divmod(total, n_chunks)
    return [base + (1 if i < remainder else 0) for i in range(n_chunks)]


_CHUNK_LETTER_POOLS = ["a, b, c, d, e, f, g, h", "i, j, k, l, m, n, o, p", "q, r, s, t, u, w, z"]


def _chunk_diversity_hint(chunk_index: int, n_chunks: int) -> str:
    """NAPRAWIONE (znaleziony PRZY WDRAZANIU rownoleglego generowania,
    sierpien 2026): pierwsza wersja rownoleglych wywolan (bez tej
    funkcji) NIE mowila kazdemu wywolaniu, ze jest jednym z kilku
    ROWNOLEGLYCH, NIEZALEZNYCH wywolan na TEN SAM temat/trudnosc - w
    realnym tescie (n=20, rownania kwadratowe, medium, 2 rownolegle
    wywolania po 13) dalo to 17/34 DUPLIKATOW (obie partie "zgodnie"
    wybraly niemal te same, "typowe" przyklady), co wymusilo dodatkowa
    runde dogenerowania i skasowalo caly zysk czasowy z rownoleglosci.
    Kazdy fragment dostaje WLASNA, ROZLACZNA pule liter parametrow i
    zakres stalych liczbowych - naturalnie zmniejsza to
    prawdopodobienstwo kolizji miedzy rownoleglymi partiami, bez
    zadnej zmiany w weryfikacji/dedup/limitach czasowych."""
    if n_chunks <= 1:
        return ""
    pool = _CHUNK_LETTER_POOLS[chunk_index % len(_CHUNK_LETTER_POOLS)]
    lo = 2 + chunk_index * 15
    hi = lo + 20
    return (
        f"\nROZNORODNOSC MIEDZY ROWNOLEGLYMI PARTIAMI (KRYTYCZNE): to jest "
        f"czesc {chunk_index + 1} z {n_chunks} ROWNOLEGLYCH, NIEZALEZNYCH partii "
        f"tego samego zamowienia, wygenerowanych OSOBNO - zeby uniknac "
        f"duplikatow miedzy partiami, w TEJ partii uzywaj TYLKO liter "
        f"parametrow z tej puli: {pool}, oraz stalych liczbowych "
        f"(wspolczynniki, wyrazy wolne) w przyblizeniu z zakresu {lo}-{hi}.\n"
    )


async def _raw_generate_quiz_topic_batch(
    topic: str, effective_topic_is_forced: bool, subject: str, level: str,
    total_n: int, difficulty: str, wlasne_instrukcje: str, avoid_block: str = ""
) -> Dict:
    """Jak _raw_generate_quiz_topic_once, ale dla wiekszych `total_n`
    dzieli zadanie na kilka mniejszych, ROWNOLEGLYCH wywolan AI (patrz
    _parallel_batch_sizes i komentarz wyzej) zamiast jednego, dlugiego.
    Dla malych `total_n` (<= target_chunk) zachowanie jest DOKLADNIE
    identyczne jak bezposrednie wywolanie _raw_generate_quiz_topic_once
    (jeden request, bez zadnej zmiany). Zwraca dodatkowy, prywatny klucz
    "_api_request_count" (ile faktycznych wywolan AI wykonano) - czytany
    przez callerow do dokladnych metryk (patrz uzycie nizej)."""
    sizes = _parallel_batch_sizes(total_n)
    if len(sizes) == 1:
        return await _raw_generate_quiz_topic_once(
            topic, effective_topic_is_forced, subject, level, sizes[0], difficulty, wlasne_instrukcje,
            avoid_block=avoid_block,
        )
    print(f"[MathVerify] rownolegle generowanie: {total_n} pytan podzielone na {len(sizes)} wywolan {sizes}")
    results = await asyncio.gather(*[
        _raw_generate_quiz_topic_once(
            topic, effective_topic_is_forced, subject, level, size, difficulty, wlasne_instrukcje,
            diversity_hint=_chunk_diversity_hint(i, len(sizes)), avoid_block=avoid_block,
        )
        for i, size in enumerate(sizes)
    ])
    merged_questions = []
    for r in results:
        merged_questions.extend(r.get("questions", []))
    title = next((r.get("title") for r in results if r.get("title")), f"{topic} - Quiz")
    return {"title": title, "questions": merged_questions, "_api_request_count": len(sizes)}


# SAFE PARAMETER GENERATION (sierpien 2026) - dla JEDNEGO, potwierdzonego
# realnymi testami najtrudniejszego podwzorca (rownanie x^2+mx+C=0,
# parametr jako goly wspolczynnik liniowy, medium): ODWROCENIE
# kolejnosci wzgledem reszty systemu. Wszedzie indziej AI generuje
# CALE pytanie (rownanie + wynik + opcje) i DOPIERO POTEM sympy
# sprawdza, czy AI policzylo poprawnie. Dla TEGO JEDNEGO podwzorca
# realne testy pokazaly ~50% odrzucen (AI systematycznie gubilo
# czynnik 4 w delcie albo losowalo C, dla ktorego prawdziwa granica
# jest niewymierna) - wiec tutaj KOD (build_safe_linear_param_quadratic
# w math_verify.py) wybiera C jako kwadrat idealny i liczy PRAWDZIWY
# warunek PRZED wywolaniem AI. AI dostaje gotowy, JUZ POPRAWNY wynik i
# ma TYLKO sformulowac pytanie jezykowo + wymyslic 3 bledne dystraktory
# - Warstwa 2 (verify_and_fix_math_question) NADAL robi koncowa
# weryfikacje jako dodatkowe zabezpieczenie (patrz wywolanie w
# _verify_and_fix_quiz_math - ten kod NIE omija Warstwy 2, tylko
# radykalnie zmniejsza szanse, ze cokolwiek trafi do niej bledne).
async def _raw_generate_safe_linear_param_quadratic_batch(n: int, level: str = None, used_letters: set = None, used_constants: set = None) -> Dict:
    """Generuje `n` pytan dla podwzorca x^2+mx+C=0 (parametr jako goly
    wspolczynnik liniowy) metoda 'safe parameter generation' - patrz
    komentarz wyzej. Jedno wywolanie AI dla calej partii (n <= ok. 15
    w praktyce, bo to tylko dogenerowanie brakujacych, nie caly quiz).

    `used_letters`/`used_constants` (opcjonalne, patrz call site w
    _generate_quiz_topic_once - zyja przez CALY quiz jako closure nad
    `regenerate`) - jesli podane, ZADNA litera/stala nie powtorzy sie w
    obrebie tego samego quizu, MIEDZY roznymi wywolaniami tej funkcji
    (kazda runda dogenerowania to osobne wywolanie) - patrz
    pick_safe_param_values w math_verify.py. Ten sam mechanizm co w
    porcie do Sprawdzianu (exam_pdf_generator.py) - user zglosil tam
    realny przypadek dwoch pytan z ta sama stala C w jednym dokumencie."""
    # NAPRAWIONE (znalezione PRZY realnym tescie n=20 - dokladna analiza
    # utraconego 1 pytania): oryginalna wersja losowala (litera, C) jako
    # PLASKA kombinacja z 10x10=100 par, wiec dla n<=10 (typowy rozmiar
    # rundy dogenerowania) LITERA mogla sie powtorzyc kilka razy w tej
    # samej partii (sparowana z INNA stala C) - dawalo to kosmetyczne
    # powtorzenia szkieletu tresci (litera jest jedynym elementem, ktory
    # szkielet NIE normalizuje - liczby sa zastepowane placeholderem).
    # Litery sa teraz losowane BEZ POWTORZEN w obrebie jednej partii
    # (dla n > liczba dostepnych liter, dopiero wtedy zaczynaja sie
    # cyklicznie powtarzac, sparowane za kazdym razem z INNA stala C).
    #
    # NAPRAWIONE (znalezione PRZY realnym tescie PO powyzszej naprawie -
    # litery-bez-powtorzen NIE wystarczyly): utracone pytanie okazalo
    # sie kolizja MIEDZY RUNDAMI - ta funkcja nie wie, jakich (litera, C)
    # juz probowala runda 1 (wolna generacja) ani co Diversity Engine juz
    # tam odrzucil - jej fingerprint i tak zostal "zuzyty" w
    # seen_fingerprints. Zamiast przekazywac cały stan miedzy rundami
    # (inwazyjna zmiana kontraktu regenerate() w calym potoku), stosujemy
    # TEN SAM, juz istniejacy wzorzec co _buffered_count (Etap 3) -
    # maly bufor nadmiarowy, zeby pojedyncza, rzadka kolizja nie
    # kosztowala calej brakujacej partii.
    buffered_n = n + 3
    letters_pool = list("mnpqrstkbc")
    squares_pool = [1, 4, 9, 16, 25, 36, 49, 64, 81, 100]
    if used_letters is not None and used_constants is not None:
        letters = pick_safe_param_values(letters_pool, used_letters, buffered_n)
        constants = pick_safe_param_values(squares_pool, used_constants, buffered_n)
    else:
        random.shuffle(letters_pool)
        letters = [letters_pool[i % len(letters_pool)] for i in range(buffered_n)]
        constants = [random.choice(squares_pool) for _ in range(buffered_n)]
    skeletons = [
        build_safe_linear_param_quadratic(
            param_letter=letters[i],
            c_value=constants[i],
        )
        for i in range(buffered_n)
    ]
    items_desc = "\n".join(
        f"{i + 1}. Rownanie: $x^2 + {sk['param_letter']}x + {sk['c_value']} = 0$. "
        f"POPRAWNY, JUZ OBLICZONY warunek na dwa rozne pierwiastki (NIE PRZELICZAJ, NIE ZMIENIAJ): "
        f"{sk['correct_text']}"
        for i, sk in enumerate(skeletons)
    )
    prompt = f"""Dla KAZDEGO z {len(skeletons)} ponizszych rownan kwadratowych z parametrem,
poprawny warunek na DWA ROZNE PIERWIASTKI zostal JUZ OBLICZONY (przez
niezalezny system matematyczny) - Twoje jedyne zadania to:
1. Sformulowac naturalne, poprawne pytanie po polsku o podane rownanie.
2. Wymyslic 3 SENSOWNE, ale MATEMATYCZNIE BLEDNE dystraktory (inne
   liczby/znaki, realistyczne, ale niepoprawne) - NIE kopiuj poprawnej
   wartosci do dystraktorow.
3. Napisac krotkie wyjasnienie (1-2 zdania) odwolujace sie do wzoru na
   delte.
4. Podac diversity_tag (skill/concept/task_type/reasoning, krotkie
   frazy) - dla WSZYSTKICH tych pytan concept to zawsze "parametr jako
   wspolczynnik liniowy" (to jest ten sam podwzorzec, celowo).

KRYTYCZNE: NIE PRZELICZAJ podanego warunku od nowa i NIE ZMIENIAJ go w
zadnym stopniu - jest juz zweryfikowany przez niezalezny system. Twoja
rola to TYLKO jezyk i dystraktory, nie matematyka.

{items_desc}

FORMAT (TYLKO JSON):
{{
    "title": "Rownania kwadratowe - Quiz",
    "questions": [
        {{
            "id": 1,
            "question": "Dla jakich wartości parametru m równanie $x^2 + mx + 16 = 0$ ma dwa różne pierwiastki?",
            "options": ["$m < -8$ lub $m > 8$", "$m < -4$ lub $m > 4$", "$m = 8$", "$m < 8$"],
            "correct": 0,
            "final_answer": "$m < -8$ lub $m > 8$",
            "explanation": "Delta rownania to $m^2-64$, warunek $\\Delta>0$ daje $m<-8$ lub $m>8$.",
            "diversity_tag": {{
                "skill": "wzor na delte", "concept": "parametr jako wspolczynnik liniowy",
                "task_type": "wyznacz parametr z warunku na delte",
                "reasoning": "oblicz delte, rozwiaz nierownosc, zapisz przedzial"
            }}
        }}
    ]
}}

ZASADY:
- Dokladnie {len(skeletons)} pytan, po jednym na kazde podane rownanie, w tej samej kolejnosci
- "final_answer" MUSI byc DOSLOWNA kopia podanego poprawnego warunku (patrz wyzej)
- "correct" = indeks poprawnej opcji w "options" (dowolna pozycja, urozmaicaj)
- Po polsku
- TYLKO JSON"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=min(8000, max(2000, 400 + len(skeletons) * 300)),
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    raw = sanitize_latex_json_backslashes(response.choices[0].message.content)
    quiz_data = json.loads(raw)
    quiz_data = fix_latex_in_quiz(quiz_data)
    # Oznacz kazde pytanie jako bezpiecznie wygenerowane - czytane przez
    # _verify_and_fix_quiz_math, zeby wylaczyc je z Diversity Engine
    # (patrz komentarz tam) - CELOWO generujemy tu wiele pytan TEGO
    # SAMEGO podwzorca, wiec ogolna kontrola roznorodnosci nie ma tu
    # zastosowania.
    for q in quiz_data.get("questions", []):
        q["_safe_generated"] = True
    return quiz_data


def _is_medium_linear_param_quadratic(topic: str, difficulty: str) -> bool:
    """Warunek gatujacy 'safe parameter generation' - TYLKO rownania
    kwadratowe na poziomie medium (ten sam warunek co _buffered_count/
    _max_generation_seconds dla tego podwzorca). Nie odrozniamy tu
    jeszcze SUBWZORCA (parametr jako wspolczynnik liniowy vs wyraz
    wolny) na poziomie promptu - oba wystepuja naturalnie w wolnej
    generacji (dobre dla roznorodnosci), safe-generation jest UZYWANA
    TYLKO w rundach dogenerowania (patrz _generate_quiz_topic_once),
    gdzie zastepuje wolna generacje CALKOWICIE dla tych rund - to
    swiadomy wybor: skoro te rundy istnieja WLASNIE dlatego, ze wolna
    generacja regularnie zawodzi dla tego tematu/trudnosci, bezpieczna
    metoda jest tam lepszym zakladem niz kolejna proba wolnej generacji."""
    is_quadratic = topic is not None and is_quadratic_equation_topic(topic)
    diff_word = (difficulty or "").strip().lower()
    return is_quadratic and diff_word in _MEDIUM_DIFFICULTY_WORDS


async def _generate_quiz_topic_once(
    topic: str, effective_topic_is_forced: bool, subject: str, level: str,
    num_questions: int, difficulty: str, wlasne_instrukcje: str
) -> Dict:
    """Surowa generacja + weryfikacja sympy + dogenerowanie brakujacych
    pytan, jesli weryfikacja cos usunela (patrz _verify_and_fill_quiz_math).
    Nazwa zachowana bez zmian - to funkcja, ktora wolaja wszyscy callerzy
    w generate_quiz_from_topic.

    NAPRAWIONE: pierwsze wywolanie prosi o troche WIECEJ pytan niz
    zamowiono (patrz _buffered_count) - empirycznie wieksze partie maja
    wyzszy odsetek pytan przechodzacych weryfikacje sympy niz partie
    jednopytaniowe, wiec to zmniejsza szanse, ze w ogole trzeba bedzie
    wchodzic w rundy dogenerowania.

    ETAP 4: tworzy GenerationMetrics tutaj (jedyne miejsce, ktore zna
    `batch_size` PRZED pierwszym wywolaniem AI) i przekazuje dalej do
    _verify_and_fill_quiz_math, ktora dolicza rundy dogenerowania i
    finalnie loguje jedna linie JSON. Jesli SUROWE (pierwsze) wywolanie
    AI calkowicie sie wywali (np. crash JSON, patrz realny przypadek z
    tej sesji) - metryki i tak sa zalogowane przed ponownym rzuceniem
    wyjatku, zeby nie stracic obserwowalnosci nawet w calkowitej porazce."""
    from .metrics import GenerationMetrics, _Timer
    t_start = time.monotonic()
    batch_size = _buffered_count(num_questions, topic=topic, difficulty=difficulty)
    metrics = GenerationMetrics(requested_count=num_questions, batch_size=batch_size)
    try:
        with _Timer(metrics, "generation_time"):
            quiz_data = await _raw_generate_quiz_topic_batch(
                topic, effective_topic_is_forced, subject, level, batch_size, difficulty, wlasne_instrukcje
            )
        metrics.api_request_count += quiz_data.pop("_api_request_count", 1)
        metrics.generated_count += len(quiz_data.get("questions", []))
    except Exception:
        metrics.record_rejection("json_crash")
        metrics.total_time = time.monotonic() - t_start
        metrics.log("[GenerationMetrics][Quiz]")
        raise
    # SAFE PARAMETER GENERATION (patrz komentarz przy
    # _raw_generate_safe_linear_param_quadratic_batch): dla rund
    # dogenerowania TEGO JEDNEGO, potwierdzonego trudnego tematu/
    # trudnosci, uzywamy metody z gotowym, poprawnym wynikiem zamiast
    # kolejnej proby wolnej generacji, ktora regularnie zawodzi wlasnie
    # dla tego przypadku (stad w ogole rundy dogenerowania sa
    # potrzebne). Pierwsza partia (wyzej) zostaje WOLNA generacja -
    # naturalny mix podwzorcow, dobry dla roznorodnosci; TYLKO
    # uzupelnianie brakujacych przelacza sie na bezpieczna metode.
    if _is_medium_linear_param_quadratic(topic, difficulty):
        # Zyje przez CALY quiz (closure nad `regenerate`, wywolywanym raz
        # per runda dogenerowania) - patrz docstring
        # _raw_generate_safe_linear_param_quadratic_batch i identyczny
        # mechanizm w exam_pdf_generator.py.
        used_safe_letters = set()
        used_safe_constants = set()
        regenerate = lambda n, avoid_block="": _raw_generate_safe_linear_param_quadratic_batch(max(n, _MIN_FILL_BATCH), level, used_letters=used_safe_letters, used_constants=used_safe_constants)
    else:
        regenerate = lambda n, avoid_block="": _raw_generate_quiz_topic_batch(
            topic, effective_topic_is_forced, subject, level, max(n, _MIN_FILL_BATCH), difficulty, wlasne_instrukcje,
            avoid_block=avoid_block,
        )
    quiz_data = await _verify_and_fill_quiz_math(
        quiz_data, num_questions, regenerate,
        t_start=t_start, difficulty=difficulty, metrics=metrics, level=level, topic=topic,
    )
    return quiz_data


# ETAP 3: adaptacyjny oversampling. Dzisiejsze realne testy (patrz
# commity Etapu 2) pokazaly konsekwentnie WYZSZY rejection rate dla
# "hard" rownan kwadratowych z parametrem niz dla reszty (kumulacja
# odrzucen Warstwy 2 - sympy - i Warstwy 3 - trudnosc), co wielokrotnie
# prowadzilo do wyczerpania limitu 30s przy standardowym buforze +30%.
# Dla TEGO konkretnego, zmierzonego przypadku uzywamy wiekszego bufora
# (+60%) - dla wszystkiego innego zostaje dotychczasowe +30% (brak
# danych uzasadniajacych wieksze bufory gdzie indziej, nie zgadujemy).
_HARD_DIFFICULTY_WORDS = {"hard", "trudny", "trudna"}

# NAPRAWIONE (audyt realnej generacji V1, sierpien 2026 - problem N!=N
# mimo naprawy rownoleglosci/duplikatow): PO naprawie klasyfikacji
# trudnosci (parametr wewnatrz wyrazenia -> hard, patrz commit a3545fc)
# "medium" rownania kwadratowe z parametrem sa juz ZAWSZE golym
# parametrem ("mx", nie "(m-4)x") - ALE nadal maja WYZSZY niz przecietny
# rejection rate (sympy_mismatch) niz reszta tematow - realne testy
# tego samego dnia pokazaly 12%-50% partii odrzucanej w roznych
# przebiegach (normalna zmiennosc AI, nie blad weryfikatora - kazdy
# sprawdzony recznie przypadek byl PRAWDZIWYM bledem matematycznym AI).
# Nie tak ekstremalne jak "hard" (+60%), ale wyrazne ponad bazowe +30% -
# dajemy posredni bufor +50%, zeby WIEKSZOSC partii miala wystarczajaco
# kandydatow bez potrzeby rundy dogenerowania (ktora i tak ma niewiele
# czasu, patrz limit 30s).
_MEDIUM_DIFFICULTY_WORDS = {"medium", "sredni", "średni", "srednia", "średnia"}


def _buffered_count(n: int, topic: str = None, difficulty: str = None) -> int:
    """Ile pytan zamowic za pierwszym razem, zeby po odrzuceniu blednych
    (weryfikacja sympy/trudnosc) prawdopodobnie zostalo >= n bez potrzeby
    rund dogenerowania. Domyslnie +30% (min +2) - +60% dla "hard" rownan
    kwadratowych z parametrem, +50% dla "medium" rownan kwadratowych z
    parametrem (patrz komentarze wyzej), +40% dla "trudny"/"hard" NA
    KAZDYM innym temacie (patrz _HARD_TIMEOUT_SECONDS - realny test,
    sierpien 2026, ciagi geometryczne+trudny). `topic`/`difficulty` sa
    opcjonalne - gdy nieznane (np. sciezka z obrazka, gdzie temat nie
    jest jeszcze znany), uzywa dotychczasowego +30%."""
    is_quadratic = topic is not None and is_quadratic_equation_topic(topic)
    diff_word = (difficulty or "").strip().lower()
    if is_quadratic and diff_word in _HARD_DIFFICULTY_WORDS:
        numerator = 6
    elif is_quadratic and diff_word in _MEDIUM_DIFFICULTY_WORDS:
        numerator = 5
    elif diff_word in _HARD_DIFFICULTY_WORDS:
        numerator = 4
    else:
        numerator = 3
    return n + max(2, -(-n * numerator // 10))  # ceil(n * numerator/10), min 2


# Minimalny rozmiar partii w rundzie dogenerowania - NIGDY nie prosimy o
# dokladnie 1 brakujace pytanie. Empirycznie (test na najtrudniejszym
# znanym przypadku): partie 1-pytaniowe mialy w praktyce ~0% szans na
# przejscie weryfikacji dla tematow typu "rownania kwadratowe z
# parametrem", podczas gdy partia 4-pytaniowa miala ~50%. Prosimy wiec
# zawsze o co najmniej tyle - nadmiar i tak zostaje przyciety do
# requested_count na koncu.
_MIN_FILL_BATCH = 4


# NAPRAWIONE (audyt realnej generacji V1, sierpien 2026 - swiadoma,
# udokumentowana decyzja usera PO pelnej analizie, NIE ciche/globalne
# podniesienie limitu): rownania kwadratowe z parametrem na poziomie
# MEDIUM maja POTWIERDZONY REALNYMI TESTAMI wysoki i uporczywy wskaznik
# odrzucen (sympy_mismatch - normalna zmiennosc trafnosci AI dla tego
# KONKRETNEGO podwzorca, patrz komentarze przy _buffered_count i
# QUADRATIC_DIFFICULTY_TIERS["5-6"] w level_config.py). Nawet po
# zwiekszonym buforze (+50%) i rownoleglych wywolaniach (patrz
# _raw_generate_quiz_topic_batch) pojedyncza partia czasem potrzebuje
# JEDNEJ dodatkowej rundy dogenerowania, ktora juz nie miesci sie w
# standardowych 30s. Zamiast cicho przekraczac limit (co system i tak
# juz robil - runda w toku nie jest przerywana w polowie, patrz petla
# nizej) - dla TEGO JEDNEGO, znanego przypadku budzet jest JAWNIE
# ustawiony na 45s. Wszystko inne (inne tematy, "easy"/"hard", brak
# tematu) zostaje przy dotychczasowych 30s - to NIE jest globalna zmiana.
_EXTENDED_TIMEOUT_SECONDS = 45.0
_DEFAULT_TIMEOUT_SECONDS = 30.0

# NAPRAWIONE (user real-test, sierpien 2026 - zgloszony bug "5/6 pytan,
# ciagi geometryczne, klasa 3 liceum, TRUDNY, limit 30s" - odtworzony
# 1:1 realnym testem): w odroznieniu od rownan kwadratowych+medium
# (wyzej), tu PIERWSZE, SUROWE wywolanie AI samo w sobie zajelo 35.3s -
# wiecej niz caly budzet 30s - wiec petla dogenerowania (ponizej) nie
# dostala ANI JEDNEJ szansy (retry_count=0), niezaleznie od tego, jak
# dobry byl bufor. To NIE jest ten sam mechanizm co "wysoki rejection
# rate" (choc czesciowo tez wystapil: 3/8 odrzucone) - to zwyczajnie
# WOLNIEJSZA odpowiedz AI dla trudniejszych zadan (dluzsze rozumowanie
# -> wiecej tokenow -> dluzej). User potwierdzil (po pokazaniu realnego
# testu i pytaniu o zakres): zamiast waskiego wyjatku TYLKO dla ciagow,
# rozszerzamy na KAZDY temat na poziomie "trudny"/"hard" - budzet 60s
# (ta sama wartosc, ktora user juz wczesniej tego samego dnia
# zaakceptowal jako jednolity budzet dla calego Sprawdzianu - nie nowy,
# nieprzetestowany numer) + bufor +40% (patrz _buffered_count) zamiast
# domyslnych +30%, zeby zmniejszyc szanse, ze w ogole potrzebna bedzie
# runda dogenerowania. "Latwy"/"medium" (poza juz istniejacym, waskim
# wyjatkiem rownan kwadratowych+medium) zostaja bez zmian.
#
# ZWIEKSZONE (user, 29.08.2026 - real-test Sprawdzianu z trudnej
# trygonometrii PO naprawie avoid-block/client buga, patrz komentarz nad
# _HARD_TIMEOUT_SECONDS_EXAM w exam_pdf_generator.py - IDENTYCZNA zmiana
# tutaj dla parytetu Quiz/Sprawdzian): 60s bylo ustalone PRZED Warstwa
# 2.5 (slepa weryfikacja przez drugie AI) dzialala poprawnie w kazdej
# rundzie dogenerowania - teraz kazda taka runda robi DWA realne
# wywolania AI (generacja + weryfikacja) zamiast jednego, wiec trudne
# tematy (duzy rejection rate + dluzsze rozumowanie) regularnie nie
# miescily sie w starym budzecie nawet bez ukonczenia. User: priorytet
# to niezawodnosc/kompletnosc ponad szybkosc dla trudnych tematow.
_HARD_TIMEOUT_SECONDS = 120.0


def _max_generation_seconds(topic: str = None, difficulty: str = None) -> float:
    """Zwraca globalny budzet czasu (sekundy) dla CALEGO procesu
    generowania+weryfikacji+dogenerowania. 45s dla rownan kwadratowych
    z parametrem na poziomie medium (waski, historyczny wyjatek - patrz
    komentarz wyzej); 60s dla KAZDEGO tematu na poziomie "trudny"/"hard"
    (patrz _HARD_TIMEOUT_SECONDS - realny test, sierpien 2026); 30s dla
    wszystkiego innego."""
    is_quadratic = topic is not None and is_quadratic_equation_topic(topic)
    diff_word = (difficulty or "").strip().lower()
    if is_quadratic and diff_word in _MEDIUM_DIFFICULTY_WORDS:
        return _EXTENDED_TIMEOUT_SECONDS
    if diff_word in _HARD_DIFFICULTY_WORDS:
        return _HARD_TIMEOUT_SECONDS
    return _DEFAULT_TIMEOUT_SECONDS


async def _verify_and_fill_quiz_math(quiz_data: dict, requested_count: int, regenerate, t_start: float = None, difficulty: str = None, metrics=None, level: str = None, topic: str = None) -> dict:
    """STANDARD ARCHITEKTONICZNY (patrz komentarz nad SAFE PARAMETER
    GENERATION w math_verify.py): `current`/`missing` ponizej sa liczone
    WYLACZNIE przez len() na faktycznie zaakceptowanej liscie - kod, nie
    AI, jest zrodlem prawdy ile juz mamy i ile dogenerowac.

    Po weryfikacji sympy (_verify_and_fix_quiz_math) niektore pytania
    moga zostac usuniete (bledny klucz bez poprawki wsrod opcji). User
    zamawiajac np. 10 pytan MA DOSTAC 10, bez wyjatkow - kompletnosc i
    poprawnosc sa wazniejsze niz szybkosc, wiec dogenerowujemy brakujace
    az osiagniemy `requested_count` ALBO wyczerpiemy `max_rounds` LUB
    `max_seconds` (bezpieczniki: user nigdy nie powinien czekac dluzej
    niz ok. 30s NA CALY PROCES (45s dla jednego, udokumentowanego
    wyjatku - patrz _max_generation_seconds powyzej) - `t_start` liczony
    jest od POCZATKU pierwszego (buforowanego) wywolania AI, nie tylko
    od poczatku petli dogenerowania, zeby limit faktycznie obejmowal
    caly czas generowania zgodnie z wymaganiem, nie tylko rundy
    uzupelniajace. Jesli caller nie poda t_start (np. stary kod), liczymy
    od tego miejsca jako fallback.

    ETAP 3: `seen_fingerprints` zyje przez CALA petle (jeden zbior,
    mutowany w kazdym wywolaniu _verify_and_fix_quiz_math) - dogenerowane
    w kolejnych rundach pytanie-duplikat zostanie odrzucone tak samo jak
    blad matematyczny czy zla trudnosc, i policzone do `missing`.

    ETAP 4: `metrics` (GenerationMetrics) jest tworzone przez callera
    (patrz _generate_quiz_topic_once - juz zna batch_size i pierwsze
    api_request_count/generation_time z surowego wywolania PRZED tym
    miejscem) i mutowane dalej tutaj - kazda runda dogenerowania to
    +1 do retry_count i api_request_count, czas w regenerate() liczy sie
    do generation_time, a blad calego wywolania AI (np. crash JSON) do
    rejection_reasons["json_crash"]. Jesli caller nie poda `metrics`,
    tworzymy lokalna, jednorazowa instancje (zero zmiany zachowania -
    po prostu nic jej nie loguje)."""
    from .metrics import GenerationMetrics, _Timer
    if metrics is None:
        metrics = GenerationMetrics(requested_count=requested_count)
    seen_fingerprints = set()
    seen_diversity_tags = []
    # NOWE (patrz format_avoid_diversity_block w math_verify.py): oprocz
    # tokenow do Jaccard (seen_diversity_tags), trzymamy TEZ surowe
    # diversity_tag (dict skill/concept/task_type) kazdego zaakceptowanego
    # pytania - zeby kolejna runda dogenerowania mogla powiedziec AI
    # WPROST, jakich schematow juz nie powtarzac, zamiast pytac od zera.
    seen_diversity_tag_dicts = []
    quiz_data = await _verify_and_fix_quiz_math(quiz_data, difficulty=difficulty, seen_fingerprints=seen_fingerprints, metrics=metrics, level=level, seen_diversity_tags=seen_diversity_tags, client=client, seen_diversity_tag_dicts=seen_diversity_tag_dicts)
    max_rounds = 10
    max_seconds = _max_generation_seconds(topic, difficulty)
    if t_start is None:
        t_start = time.monotonic()
    for round_i in range(1, max_rounds + 1):
        current = len(quiz_data.get("questions", []))
        missing = requested_count - current
        if missing <= 0:
            break
        elapsed = time.monotonic() - t_start
        if elapsed >= max_seconds:
            print(f"[MathVerify] przekroczono limit czasu ({elapsed:.1f}s >= {max_seconds}s) - przerywam dogenerowanie")
            break
        print(f"[MathVerify] brakuje {missing} pytan po weryfikacji (runda {round_i}/{max_rounds}, {elapsed:.1f}s) - dogenerowuje...")
        metrics.retry_count += 1
        avoid_block = format_avoid_diversity_block(seen_diversity_tag_dicts)
        try:
            with _Timer(metrics, "generation_time"):
                extra_data = await regenerate(missing, avoid_block)
            metrics.api_request_count += extra_data.pop("_api_request_count", 1)
            metrics.generated_count += len(extra_data.get("questions", []))
        except Exception as e:
            print(f"[MathVerify] blad dogenerowania: {e}")
            metrics.record_rejection("json_crash")
            continue
        extra_data = await _verify_and_fix_quiz_math(extra_data, difficulty=difficulty, seen_fingerprints=seen_fingerprints, metrics=metrics, level=level, seen_diversity_tags=seen_diversity_tags, client=client, seen_diversity_tag_dicts=seen_diversity_tag_dicts)
        quiz_data.setdefault("questions", []).extend(extra_data.get("questions", []))

    final_count = len(quiz_data.get("questions", []))
    if final_count < requested_count:
        # Bardzo rzadki przypadek - wyczerpano max_rounds ALBO max_seconds
        # i nadal brakuje. Uczciwy komunikat zamiast cichego podania
        # niepelnego quizu.
        total_elapsed = time.monotonic() - t_start
        # NAPRAWIONE (ten sam blad co w exam_pdf_generator.py - patrz
        # commit "Napraw myslacy komunikat shortfallu Sprawdzianu"):
        # tekst NIE moze miec zaszytej na stale liczby - max_seconds
        # teraz zalezy od tematu/trudnosci (patrz _max_generation_seconds),
        # wiec musi byc pokazywana PRAWDZIWA wartosc.
        reason = f"przekroczono limit czasu ({max_seconds:.0f}s)" if total_elapsed >= max_seconds else f"wyczerpano {max_rounds} prob dogenerowania"
        quiz_data["_shortfall_warning"] = (
            f"Udalo sie wygenerowac i zweryfikowac {final_count} z {requested_count} "
            f"zamowionych pytan - {reason}, pozostale okazaly sie bledne. "
            f"Sprobuj ponownie albo zmien temat/trudnosc."
        )
        print(f"[MathVerify] SHORTFALL: {final_count}/{requested_count} po {total_elapsed:.1f}s ({reason})")

    questions = quiz_data.get("questions", [])[:requested_count]
    for i, q in enumerate(questions, start=1):
        q["id"] = i
    quiz_data["questions"] = questions

    metrics.accepted_count = len(questions)
    metrics.total_time = time.monotonic() - t_start
    metrics.log("[GenerationMetrics][Quiz]")

    return quiz_data


def _question_fingerprint(text: str):
    """ETAP 3: prosty fingerprint do wykrywania duplikatow/bardzo
    podobnych pytan w obrebie jednego requestu (patrz uzycie w
    _verify_and_fix_quiz_math). Normalizuje tekst (lowercase, liczby
    zastapione placeholderem, interpunkcja/biale znaki scalone) i OSOBNO
    wyciaga faktyczne liczby - dwa pytania licza sie jako duplikat TYLKO
    gdy maja IDENTYCZNY szkielet slowny ORAZ IDENTYCZNE liczby (typowy
    przypadek: AI zwrocilo w jednej partii dwa niemal identyczne
    pytania). Te same slowa z INNYMI liczbami/parametrem to legalna,
    rozna wersja tego samego typu zadania - NIE duplikat."""
    t = (text or "").lower()
    numbers = tuple(re_module.findall(r'-?\d+(?:[.,]\d+)?', t))
    skeleton = re_module.sub(r'-?\d+(?:[.,]\d+)?', '#', t)
    skeleton = re_module.sub(r'[^a-ząćęłńóśźż#]+', ' ', skeleton)
    skeleton = ' '.join(skeleton.split())
    return (skeleton, numbers)


_QUIZ_LETTER_TO_IDX = {"a": 0, "b": 1, "c": 2, "d": 3}


# WARSTWA 2.5 (patrz app/blind_verify.py po pelne uzasadnienie architektury,
# identyczny mechanizm co exam_pdf_generator._blind_verify_one_closed -
# user: "QUIZ MUSI miec TEN SAM mechanizm co Sprawdzian"). Wersja ASYNC,
# bo Quiz uzywa AsyncOpenAI (w odroznieniu od Sprawdzianu - sync klient).
#
# `client` jest jawnym PARAMETREM (nie bezposrednim uzyciem modulowego
# globala) - domyslnie None = POMIN blind-check (identyczny wzorzec co
# `client=None` w exam_pdf_generator._verify_and_fix_exam_math). KRYTYCZNE
# dla testow: dziesiatki istniejacych testow jednostkowych (zero-AI)
# wywoluja _verify_and_fix_quiz_math BEZPOSREDNIO na pytaniach spoza
# rozpoznawanych wzorcow sympy (status "unverifiable") - bez tego
# escape-hatcha KAZDY taki test zaczalby cicho robic PRAWDZIWE, PLATNE
# wywolania API. Prawdziwa generacja (2 miejsca w
# _verify_and_fill_quiz_math nizej) jawnie przekazuje modulowy `client`.
async def _blind_verify_one_closed_quiz(q: dict, client=None) -> bool:
    """True = zaakceptuj (brak client -> pominiete; AI-2 sie zgadza; LUB
    wywolanie/parsowanie sie nie udalo - bezpieczny fallback, patrz
    identyczny komentarz w exam_pdf_generator.py)."""
    if client is None:
        return True
    try:
        r = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": BLIND_VERIFY_SYSTEM_PROMPT},
                {"role": "user", "content": build_blind_verify_prompt_closed(q.get("question", ""), q.get("options", []))},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=600,
        )
        parsed = safe_json_loads(r.choices[0].message.content)
    except Exception as e:
        print(f"[BlindVerify] blad wywolania AI-2: {e}")
        return True
    letter = parse_blind_verify_letter(parsed)
    if letter is None:
        return True
    ai2_idx = _QUIZ_LETTER_TO_IDX.get(letter)
    if ai2_idx is None:
        return True
    return ai2_idx == q.get("correct")


async def _blind_verify_batch_closed_quiz(candidates: list, client=None) -> list:
    """Rownolegle (asyncio.gather), zeby dodatkowe wywolania NIE wydluzaly
    liniowo czasu generacji. Zwraca liste bool w TEJ SAMEJ kolejnosci co
    `candidates`."""
    if not candidates:
        return []
    return await asyncio.gather(*(_blind_verify_one_closed_quiz(q, client=client) for q in candidates))


async def _verify_and_fix_quiz_math(quiz_data: dict, difficulty: str = None, seen_fingerprints: set = None, metrics=None, level: str = None, seen_diversity_tags: list = None, client=None, seen_diversity_tag_dicts: list = None) -> dict:
    """Trzywarstwowa weryfikacja - AI NIGDY nie decyduje samo, ktora
    opcja jest "correct" (architektura ustalona z userem, patrz commit):

    WARSTWA 2.5 (NOWE, sierpien 2026 - ten sam mechanizm co Sprawdzian,
    patrz app/blind_verify.py i identyczny komentarz w
    exam_pdf_generator._verify_and_fix_exam_math - user: "QUIZ MUSI miec
    TEN SAM mechanizm co Sprawdzian"): "slepe" AI-2 rozwiazuje pytanie
    samodzielnie, TYLKO gdy Warstwa 2 (sympy) nie ma zdania
    ("unverifiable") - pytania juz potwierdzone/poprawione przez sympy z
    pelna pewnoscia NIE dostaja dodatkowego wywolania. Rownolegle
    (asyncio.gather - Quiz uzywa AsyncOpenAI), zeby nie wydluzac liniowo
    czasu generacji.

    WARSTWA 1 (kazdy przedmiot): "correct" jest ZAWSZE przeliczany na
    nowo z dopasowania pola "final_answer" (doslowna kopia poprawnej
    opcji, ktora AI ma teraz obowiazek podac) do "options" -
    force_correct_from_final_answer(). To lapie najczestszy blad z
    audytu tej sesji: AI poprawnie wyprowadza wynik w "explanation", ale
    "correct" wskazuwalo inny, bledny indeks. Brak final_answer, brak
    dopasowania do zadnej opcji, albo dopasowanie do wiecej niz jednej -
    pytanie jest odrzucane (dogenerowywane w innym miejscu potoku).

    WARSTWA 2 (tylko rozpoznane wzorce matematyczne - rownania
    kwadratowe, ciagi): NIEZALEZNA weryfikacja sympy (math_verify.py),
    ktora liczy prawdziwy wynik z tresci pytania (nie z tego, co
    zadeklarowal AI) i porownuje z opcjami - dodatkowa siatka
    bezpieczenstwa nawet jesli final_answer AI bylo samo w sobie
    matematycznie bledne (a jedynie wewnetrznie spojne z jedna z opcji).

    WARSTWA 3 (ETAP 2 Universal Difficulty Engine, TYLKO rownania
    kwadratowe na razie): walidacja skali trudnosci - osobna od
    poprawnosci matematycznej. Sprawdza, czy wygenerowane pytanie
    FAKTYCZNIE odpowiada zadanej trudnosci (easy/medium/hard), nie tylko
    czy jest matematycznie poprawne. Uzywa DifficultyAnalyzer
    (app/difficulty/) z domain modifierem math_quadratic.py, ktory
    wewnatrz wywoluje NIEZMIENIONY validate_quadratic_difficulty z
    math_verify.py - zachowanie identyczne jak przed Etapem 2, zmienila
    sie tylko struktura kodu (patrz test_difficulty_engine.py - regresja
    potwierdzona na identycznych przypadkach). Szuka rownania zarowno w
    tresci pytania, jak i w opcjach odpowiedzi (obsluguje tez format
    "Ktore z ponizszych rownan..."). FAIL -> pytanie odrzucone
    (dogenerowywane w innym miejscu potoku, tak samo jak Warstwa 1/2).

    DEDUPLIKACJA (ETAP 3, opcjonalna - tylko gdy `seen_fingerprints`
    podane): odrzuca pytania, ktorych fingerprint (patrz
    _question_fingerprint) juz wystapil w TYM SAMYM requescie - w tej
    partii albo w ktorejkolwiek wczesniejszej rundzie dogenerowania
    (zbior jest przekazywany i mutowany przez cala petle w
    _verify_and_fill_quiz_math). Bez podania `seen_fingerprints`
    zachowanie jest identyczne jak przed Etapem 3.

    METRYKI (ETAP 4, opcjonalne - tylko gdy `metrics` podane): kazde
    odrzucenie zwieksza metrics.rejected_count i histogram
    metrics.rejection_reasons (klucze: final_answer_no_match,
    sympy_mismatch, difficulty_fail, duplicate). Caly czas tej funkcji
    liczy sie do metrics.validation_time, a sam czas Warstwy 3 - do
    metrics.difficulty_time (podzbior validation_time, nie osobna pula).

    KALIBRACJA POZIOMU (ETAP 5, opcjonalna - tylko gdy `level` podane):
    Warstwa 3 przekazuje `level` do DifficultyAnalyzer, ktory dla rownan
    kwadratowych przesuwa okno akceptowalnych tierow wzgledem poziomu
    ucznia (patrz app/difficulty/calibration.py
    level_adjusted_tier_shift) - to samo pytanie moze wiec zostac
    zaakceptowane dla jednego poziomu i odrzucone dla innego. Bez
    `level` (albo dla liceum_2 - baseline kalibracji) zachowanie jest
    DOKLADNIE identyczne jak przed Etapem 5."""
    from .metrics import _Timer
    questions = quiz_data.get("questions")
    if not isinstance(questions, list):
        return quiz_data
    _validation_timer = _Timer(metrics, "validation_time") if metrics else None
    if _validation_timer:
        _validation_timer.__enter__()
    kept = []
    needs_blind_check = []
    for q in questions:
        text = q.get("question", "")

        # WARSTWA 1: wymus "correct" z "final_answer" (wszystkie przedmioty)
        try:
            fa_status = force_correct_from_final_answer(q)
        except Exception as e:
            print(f"[MathVerify] blad wymuszania final_answer: {e}")
            fa_status = "no_final_answer"
        if fa_status in ("no_match", "ambiguous", "no_final_answer"):
            print(f"[MathVerify] USUNIETO pytanie (final_answer={fa_status}): '{text[:60]}...'")
            log_final_answer_mismatch_diagnostic("[MathVerify]", quiz_data.get("title", ""), text, q.get("options", []), q.get("final_answer"), fa_status)
            if metrics:
                metrics.record_rejection("final_answer_no_match")
            continue

        # WARSTWA 1.5 (NOWE): strukturalna poprawnosc LaTeX/$ - patrz
        # validate_latex_formatting wyzej. NAJPIERW proba automatycznej
        # naprawy dla "options" (real-test: 75% partii Trygonometrii mialo
        # TU brakujacy $ - zbyt czeste, zeby po prostu odrzucac, patrz
        # auto_wrap_bare_latex) - TYLKO dla options (krotka, pojedyncza
        # wartosc), NIE dla "question"/"explanation" (mieszaja proze z
        # matematyka - owijanie calosci byloby niebezpieczne zgadywanie
        # granic). Sprawdzone PRZED Warstwa 2/2.5, zeby nie marnowac
        # (platnego) blind-check na pytanie, ktore i tak nie wyrenderuje
        # sie poprawnie.
        auto_wrap_bare_latex_in_question(q, ["options"])
        latex_ok, latex_reason = validate_question_latex(q, ["question", "options", "explanation"])
        if not latex_ok:
            print(f"[LatexValidate] USUNIETO pytanie ({latex_reason}): '{text[:60]}...'")
            if metrics:
                metrics.record_rejection("latex_malformed")
            continue

        # WARSTWA 2: niezalezna weryfikacja sympy tam, gdzie rozpoznajemy wzorzec
        try:
            options = q.get("options", [])
            result = verify_and_fix_math_question(text, options)
        except Exception as e:
            print(f"[MathVerify] blad weryfikacji sympy: {e}")
            kept.append(q)
            continue
        if result["status"] == "unverifiable":
            log_unverifiable_diagnostic("[MathVerify]", quiz_data.get("title", ""), text, options, q.get("final_answer"))
            # WARSTWA 2.5: sympy nie ma zdania - odlozone do blind-check
            # AI-2 (batch, rownolegle, PO tej petli) - patrz nizej.
            needs_blind_check.append(q)
        elif result["status"] == "match_index":
            true_idx = result["true_index"]
            if q.get("correct") != true_idx:
                print(f"[MathVerify] POPRAWIONO odpowiedz (sympy nie zgadza sie z final_answer): '{text[:60]}...' correct {q.get('correct')} -> {true_idx}")
                q["correct"] = true_idx
                if result.get("explanation"):
                    q["explanation"] = result["explanation"]
            kept.append(q)
        elif result["status"] == "no_option_matches":
            print(f"[MathVerify] USUNIETO pytanie (sympy: brak poprawnej opcji wsrod podanych): '{text[:60]}...'")
            log_no_option_matches_diagnostic("[MathVerify]", quiz_data.get("title", ""), text, options, q.get("final_answer"))
            if metrics:
                metrics.record_rejection("sympy_mismatch")
        else:
            kept.append(q)

    # WARSTWA 2.5 (patrz app/blind_verify.py): blind-check AI-2, TYLKO dla
    # pytan, gdzie sympy nie mial zdania - batch, rownolegle (asyncio.gather).
    if needs_blind_check:
        agree_list = await _blind_verify_batch_closed_quiz(needs_blind_check, client=client)
        for q, agree in zip(needs_blind_check, agree_list):
            if agree:
                kept.append(q)
            else:
                print(f"[BlindVerify] USUNIETO pytanie (AI-2 nie zgadza sie z AI-1): '{q.get('question', '')[:60]}...'")
                if metrics:
                    metrics.record_rejection("blind_ai_mismatch")

    # WARSTWA 3: walidacja skali trudnosci (rownania kwadratowe skala 1-10,
    # ETAP 6: ciagi arytmetyczne/geometryczne skala 1-5) - topic-agnostyczne,
    # kazdy zarejestrowany domain modifier (DEFAULT_MODIFIERS) sam
    # rozpoznaje, czy dotyczy danego pytania (applies()).
    if difficulty:
        _difficulty_timer = _Timer(metrics, "difficulty_time") if metrics else None
        if _difficulty_timer:
            _difficulty_timer.__enter__()
        kept2 = []
        for q in kept:
            text = q.get("question", "")
            try:
                score = _difficulty_analyzer.analyze(
                    text, option_texts=q.get("options", []), requested_difficulty_word=difficulty, level=level,
                )
                # domain_detail to DOKLADNIE to, co zwrocilo
                # validate_quadratic_difficulty - jesli zaden domain
                # modifier nie pasowal (np. nie rownanie kwadratowe),
                # domain_detail jest None -> traktujemy jak "not_quadratic"
                # (ta sama semantyka co bezposrednie wywolanie wczesniej).
                diff_result = score.domain_detail or {"status": "not_quadratic"}
            except Exception as e:
                print(f"[MathVerify][Difficulty] blad walidacji trudnosci: {e}")
                kept2.append(q)
                continue
            if diff_result["status"] == "fail":
                print(
                    f"[MathVerify][Difficulty] FAIL: '{text[:60]}...' "
                    f"REASON={diff_result['reason']} "
                    f"REQUESTED_TIER={diff_result['requested_tier']} "
                    f"DETECTED_TIER={diff_result['detected_tier']}"
                )
                if metrics:
                    metrics.record_rejection("difficulty_fail")
                continue
            kept2.append(q)
        kept = kept2
        if _difficulty_timer:
            _difficulty_timer.__exit__(None, None, None)

    # DEDUPLIKACJA (ETAP 3) - patrz docstring wyzej.
    if seen_fingerprints is not None:
        deduped = []
        for q in kept:
            fp = _question_fingerprint(q.get("question", ""))
            if fp in seen_fingerprints:
                print(f"[MathVerify][Dedup] USUNIETO duplikat: '{q.get('question', '')[:60]}...'")
                if metrics:
                    metrics.record_rejection("duplicate")
                continue
            seen_fingerprints.add(fp)
            deduped.append(q)
        kept = deduped

    # UNIVERSAL DIVERSITY ENGINE (Krok 3) - wyzszy poziom abstrakcji niz
    # dedup wyzej: dedup lapie IDENTYCZNY tekst (rozne liczby/litery to
    # legalna, rozna wersja - patrz jego docstring), to sprawdza, czy
    # dwa pytania maja TEN SAM SCHEMAT/TYP ROZUMOWANIA (np. "10 pytan o
    # rownaniach kwadratowych, wszystkie ten sam podwzorzec, tylko z
    # innymi literami parametru" - zgloszony problem, ktorego zwykly
    # dedup NIE lapie z definicji). AI samo opisuje kazde pytanie
    # 4-polowym tagiem "diversity_tag" (patrz prompt w
    # _raw_generate_quiz_topic_once) - is_too_similar_diversity_tag
    # porownuje go (Jaccard na znormalizowanych tokenach) z KAZDYM juz
    # zaakceptowanym tagiem w TEJ SAME partii. Dziala dla KAZDEGO tematu
    # bez zadnej konfiguracji per przedmiot - brak tagu (stary format,
    # blad AI) -> nie da sie ocenic -> nie blokujemy (bezpieczny
    # abstain, ta sama filozofia co reszta modulu).
    # NAPRAWIONE (znalezione PRZY realnym tescie Safe Parameter
    # Generation, sierpien 2026): Safe Parameter Generation (patrz
    # _raw_generate_safe_linear_param_quadratic_batch) CELOWO generuje
    # WIELE pytan tego samego, jednego podwzorca (to jest cel - dogenerowac
    # NIEZAWODNIE poprawne pytania dla tematu, w ktorym wolna generacja
    # regularnie zawodzi) - to z definicji koliduje z Diversity Engine,
    # ktora rowniez CELOWO odrzuca wiele pytan tego samego schematu.
    # Realny test pokazal: prawie WSZYSTKIE bezpiecznie wygenerowane
    # pytania byly odrzucane jako "zbyt podobne" do PIERWSZEGO
    # bezpiecznie wygenerowanego pytania, przez co runda dogenerowania
    # dawala 1-2 pytania zamiast potrzebnych kilkunastu. Safe-generated
    # pytania (oznaczone prywatnym kluczem "_safe_generated" przez
    # regenerate()) sa WYLACZONE z tej konkretnej kontroli - juz
    # PRZESZLY etap "chcemy roznorodnosci" (byl w pierwszej, wolnej
    # partii) i teraz swiadomie priorytetyzujemy KOMPLETNOSC+POPRAWNOSC
    # nad dalsza roznorodnoscia dla tego jednego, trudnego przypadku.
    if seen_diversity_tags is not None:
        diverse = []
        for q in kept:
            if q.pop("_safe_generated", False):
                diverse.append(q)
                continue
            too_similar, tokens = is_too_similar_diversity_tag(q.get("diversity_tag"), seen_diversity_tags, question_text=q.get("question"))
            if too_similar:
                print(f"[MathVerify][Diversity] USUNIETO - zbyt podobny schemat do juz zaakceptowanego pytania: '{q.get('question', '')[:60]}...' tag={q.get('diversity_tag')}")
                if metrics:
                    metrics.record_rejection("diversity_too_similar")
                continue
            if tokens:
                seen_diversity_tags.append(tokens)
                if seen_diversity_tag_dicts is not None and isinstance(q.get("diversity_tag"), dict):
                    seen_diversity_tag_dicts.append(q["diversity_tag"])
            diverse.append(q)
        kept = diverse

    # LOSOWANIE POZYCJI POPRAWNEJ ODPOWIEDZI - PO wszystkich warstwach
    # weryfikacji (1/2/3), zeby `correct` uzyte tutaj bylo juz OSTATECZNE
    # (ewentualnie poprawione przez Warstwe 2). Przeciwdziala tendencji AI
    # do faworyzowania okreslonych pozycji (np. A/B) - patrz
    # shuffle_options_preserving_correct.
    for q in kept:
        options = q.get("options")
        correct = q.get("correct")
        if isinstance(options, list) and isinstance(correct, int):
            new_options, new_correct = shuffle_options_preserving_correct(options, correct)
            q["options"] = new_options
            q["correct"] = new_correct

    for i, q in enumerate(kept, start=1):
        q["id"] = i
    quiz_data["questions"] = kept
    if _validation_timer:
        _validation_timer.__exit__(None, None, None)
    return quiz_data


async def generate_quiz_from_topic(
    topic: str,
    subject: str = "matematyka",
    level: str = "liceum",
    num_questions: int = 5,
    difficulty: str = "medium",
    wlasne_instrukcje: str = ""
) -> Dict:
    """ðŸŽ“ Generuje quiz z podanego tematu"""
    # NAPRAWIONE: gdy "topic" to w rzeczywistosci tylko nazwa przedmiotu
    # (tak wysyla karta "Nastepny krok" na Dashboardzie, gdy nie ma
    # konkretnego sugerowanego tematu - np. topic="Matematyka"), pozwalamy
    # AI samo wybrac temat z zakresu klasy. Audyt 24 poziomow pokazal, ze
    # samo instruowanie AI "wybierz z listy" nie jest niezawodne - model
    # czasem i tak wybiera "typowy" temat spoza zakresu (np. rownania
    # kwadratowe dla liceum_2, ktorej realny zakres to trygonometria).
    # Zamiast ufac AI za kazdym razem, WALIDUJEMY wynik programowo
    # (validate_generic_topic - prosty substring-match, BEZ kolejnego
    # wywolania AI) i przy zlym temacie probujemy ponownie (max 3 proby).
    # Jesli nadal sie nie uda - wymuszamy KONKRETNY, sprawdzony temat z
    # FORCED_FALLBACK_TOPICS zamiast dalej pozwalac AI "wybierac samemu"
    # (ta sciezka - temat jako sztywny priorytet - jest w praktyce dużo
    # bardziej niezawodna niz "wybierz cokolwiek z listy").
    is_generic_topic = topic.strip().lower() == subject.strip().lower()

    if not is_generic_topic:
        try:
            quiz_data = await _generate_quiz_topic_once(
                topic, True, subject, level, num_questions, difficulty, wlasne_instrukcje
            )
            return {"success": True, "quiz": quiz_data}
        except Exception as e:
            print(f"âŒ BÅ‚Ä…d: {str(e)}")
            return {"success": False, "error": str(e)}

    last_quiz_data = None
    last_error = None
    MAX_ATTEMPTS = 3
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            quiz_data = await _generate_quiz_topic_once(
                topic, False, subject, level, num_questions, difficulty, wlasne_instrukcje
            )
        except Exception as e:
            last_error = e
            print(f"âŒ Quiz-Scope proba {attempt}/{MAX_ATTEMPTS} - blad generacji: {e}")
            continue
        last_quiz_data = quiz_data
        if validate_generic_topic(quiz_data, level, subject):
            return {"success": True, "quiz": quiz_data}
        print(
            f"[Quiz-Scope] proba {attempt}/{MAX_ATTEMPTS}: temat "
            f"'{quiz_data.get('title')}' NIE pasuje do zakresu {level}/{subject} - ponawiam"
        )

    fallback_topic = get_forced_fallback_topic(level, subject)
    if fallback_topic:
        try:
            quiz_data = await _generate_quiz_topic_once(
                fallback_topic, True, subject, level, num_questions, difficulty, wlasne_instrukcje
            )
            print(f"[Quiz-Scope] wymuszony fallback temat: '{fallback_topic}'")
            return {"success": True, "quiz": quiz_data}
        except Exception as e:
            last_error = e
            print(f"âŒ Quiz-Scope fallback - blad generacji: {e}")

    # Nic lepszego sie nie udalo - zwroc ostatni wygenerowany quiz (nawet
    # jesli nie przeszedl walidacji) zamiast twardego bledu. Lepiej dac
    # userowi quiz o niepewnym temacie niz pusty ekran bledu.
    if last_quiz_data is not None:
        return {"success": True, "quiz": last_quiz_data}
    print(f"âŒ BÅ‚Ä…d: {str(last_error)}")
    return {"success": False, "error": str(last_error) if last_error else "unknown error"}
