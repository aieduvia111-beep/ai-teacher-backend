from openai import AsyncOpenAI
from .config import settings
from .level_config import (
    describe_level, validate_generic_topic, get_forced_fallback_topic,
    get_quadratic_difficulty_anchor, is_quadratic_equation_topic,
)
from .math_verify import verify_and_fix_math_question, force_correct_from_final_answer
from .difficulty import DifficultyAnalyzer
from typing import List, Dict, Optional
import json
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
    # \b... (backslash+b bywa "zjadany" jako backspace)
    'beta', 'bar', 'binom', 'bmod', 'boxed', 'bullet',
    # \f... (backslash+f bywa "zjadany" jako formfeed)
    'frac', 'forall', 'flat',
    # \n... (backslash+n bywa "zjadany" jako nowa linia)
    'neq', 'nabla', 'notin', 'nu',
    # \r... (backslash+r bywa "zjadany" jako powrot karetki)
    'rho', 'rightarrow',
    # inne czeste, ktore i tak warto podwoic zawczasu
    'sqrt', 'cdot', 'div', 'sum', 'int', 'left', 'right', 'alpha', 'gamma',
    'delta', 'pi', 'infty', 'leq', 'geq', 'approx', 'pm', 'mathrm',
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
            quiz_data, num_questions, lambda n: _raw_call(max(n, _MIN_FILL_BATCH)), t_start=t_start, difficulty=difficulty
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
        if _MATH_INDICATOR_RE.search(content):
            out.append(t[i:j + 1])
            i = j + 1
        else:
            i += 1  # sierocy $ - pomin, NIE konsumuj drugiego $
    return ''.join(out)

def fix_latex_in_quiz(quiz_data):
    """Naprawia typowe bledy LaTeX zanim dotrze do frontendu"""
    def fix(t):
        if not t: return t
        # Napraw $1 jako pm/plus-minus
        t = t.replace('$1 ', '$\\pm$').replace('=$1', '=$\\pm$').replace('= $1', '= $\\pm$')
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
    num_questions: int, difficulty: str, wlasne_instrukcje: str
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
    quadratic_anchor_blok = ""
    if is_quadratic_equation_topic(topic):
        anchor_text = get_quadratic_difficulty_anchor(difficulty)
        if anchor_text:
            quadratic_anchor_blok = f"\n{anchor_text}\n"

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
{quadratic_anchor_blok}
{instrukcje_blok}
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
            "explanation": "Bo $x = \\pm 2$"
        }}
    ]
}}

ZASADY:
- Pytania konkretne i merytoryczne
- correct = indeks (0-3)
- final_answer = doslowna kopia poprawnej opcji z "options" (patrz wyzej)
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
    wchodzic w rundy dogenerowania."""
    t_start = time.monotonic()
    quiz_data = await _raw_generate_quiz_topic_once(
        topic, effective_topic_is_forced, subject, level,
        _buffered_count(num_questions, topic=topic, difficulty=difficulty), difficulty, wlasne_instrukcje
    )
    quiz_data = await _verify_and_fill_quiz_math(
        quiz_data, num_questions,
        lambda n: _raw_generate_quiz_topic_once(
            topic, effective_topic_is_forced, subject, level, max(n, _MIN_FILL_BATCH), difficulty, wlasne_instrukcje
        ),
        t_start=t_start, difficulty=difficulty,
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


def _buffered_count(n: int, topic: str = None, difficulty: str = None) -> int:
    """Ile pytan zamowic za pierwszym razem, zeby po odrzuceniu blednych
    (weryfikacja sympy/trudnosc) prawdopodobnie zostalo >= n bez potrzeby
    rund dogenerowania. Domyslnie +30% (min +2) - +60% dla "hard" rownan
    kwadratowych z parametrem (patrz komentarz wyzej). `topic`/`difficulty`
    sa opcjonalne - gdy nieznane (np. sciezka z obrazka, gdzie temat nie
    jest jeszcze znany), uzywa dotychczasowego +30%."""
    is_hard_quadratic = (
        topic is not None
        and (difficulty or "").strip().lower() in _HARD_DIFFICULTY_WORDS
        and is_quadratic_equation_topic(topic)
    )
    numerator = 6 if is_hard_quadratic else 3
    return n + max(2, -(-n * numerator // 10))  # ceil(n * numerator/10), min 2


# Minimalny rozmiar partii w rundzie dogenerowania - NIGDY nie prosimy o
# dokladnie 1 brakujace pytanie. Empirycznie (test na najtrudniejszym
# znanym przypadku): partie 1-pytaniowe mialy w praktyce ~0% szans na
# przejscie weryfikacji dla tematow typu "rownania kwadratowe z
# parametrem", podczas gdy partia 4-pytaniowa miala ~50%. Prosimy wiec
# zawsze o co najmniej tyle - nadmiar i tak zostaje przyciety do
# requested_count na koncu.
_MIN_FILL_BATCH = 4


async def _verify_and_fill_quiz_math(quiz_data: dict, requested_count: int, regenerate, t_start: float = None, difficulty: str = None) -> dict:
    """Po weryfikacji sympy (_verify_and_fix_quiz_math) niektore pytania
    moga zostac usuniete (bledny klucz bez poprawki wsrod opcji). User
    zamawiajac np. 10 pytan MA DOSTAC 10, bez wyjatkow - kompletnosc i
    poprawnosc sa wazniejsze niz szybkosc, wiec dogenerowujemy brakujace
    az osiagniemy `requested_count` ALBO wyczerpiemy `max_rounds` LUB
    `max_seconds` (bezpieczniki: user nigdy nie powinien czekac dluzej
    niz ok. 30s NA CALY PROCES - `t_start` liczony jest od POCZATKU
    pierwszego (buforowanego) wywolania AI, nie tylko od poczatku petli
    dogenerowania, zeby limit faktycznie obejmowal caly czas generowania
    zgodnie z wymaganiem, nie tylko rundy uzupelniajace. Jesli caller nie
    poda t_start (np. stary kod), liczymy od tego miejsca jako fallback.

    ETAP 3: `seen_fingerprints` zyje przez CALA petle (jeden zbior,
    mutowany w kazdym wywolaniu _verify_and_fix_quiz_math) - dogenerowane
    w kolejnych rundach pytanie-duplikat zostanie odrzucone tak samo jak
    blad matematyczny czy zla trudnosc, i policzone do `missing`."""
    seen_fingerprints = set()
    quiz_data = _verify_and_fix_quiz_math(quiz_data, difficulty=difficulty, seen_fingerprints=seen_fingerprints)
    max_rounds = 10
    max_seconds = 30.0
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
        try:
            extra_data = await regenerate(missing)
        except Exception as e:
            print(f"[MathVerify] blad dogenerowania: {e}")
            continue
        extra_data = _verify_and_fix_quiz_math(extra_data, difficulty=difficulty, seen_fingerprints=seen_fingerprints)
        quiz_data.setdefault("questions", []).extend(extra_data.get("questions", []))

    final_count = len(quiz_data.get("questions", []))
    if final_count < requested_count:
        # Bardzo rzadki przypadek - wyczerpano max_rounds ALBO max_seconds
        # i nadal brakuje. Uczciwy komunikat zamiast cichego podania
        # niepelnego quizu.
        total_elapsed = time.monotonic() - t_start
        reason = "przekroczono limit czasu (30s)" if total_elapsed >= max_seconds else f"wyczerpano {max_rounds} prob dogenerowania"
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


def _verify_and_fix_quiz_math(quiz_data: dict, difficulty: str = None, seen_fingerprints: set = None) -> dict:
    """Trzywarstwowa weryfikacja - AI NIGDY nie decyduje samo, ktora
    opcja jest "correct" (architektura ustalona z userem, patrz commit):

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
    zachowanie jest identyczne jak przed Etapem 3."""
    questions = quiz_data.get("questions")
    if not isinstance(questions, list):
        return quiz_data
    kept = []
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
            kept.append(q)
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
        else:
            kept.append(q)

    # WARSTWA 3: walidacja skali trudnosci 1-10 (TYLKO rownania kwadratowe)
    if difficulty:
        kept2 = []
        for q in kept:
            text = q.get("question", "")
            try:
                score = _difficulty_analyzer.analyze(
                    text, option_texts=q.get("options", []), requested_difficulty_word=difficulty,
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
                continue
            kept2.append(q)
        kept = kept2

    # DEDUPLIKACJA (ETAP 3) - patrz docstring wyzej.
    if seen_fingerprints is not None:
        deduped = []
        for q in kept:
            fp = _question_fingerprint(q.get("question", ""))
            if fp in seen_fingerprints:
                print(f"[MathVerify][Dedup] USUNIETO duplikat: '{q.get('question', '')[:60]}...'")
                continue
            seen_fingerprints.add(fp)
            deduped.append(q)
        kept = deduped

    for i, q in enumerate(kept, start=1):
        q["id"] = i
    quiz_data["questions"] = kept
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
