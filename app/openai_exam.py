from openai import AsyncOpenAI
from .config import settings
from .level_config import describe_level, validate_generic_topic, get_forced_fallback_topic
from .math_verify import verify_and_fix_math_question
from typing import List, Dict, Optional
import json
import re as _re_sanitize

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


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

        quiz_data = await _raw_call(num_questions)
        print(f"âœ… Quiz: {quiz_data.get('title', 'Quiz')}")
        quiz_data = fix_latex_in_quiz(quiz_data)
        quiz_data = await _verify_and_fill_quiz_math(quiz_data, num_questions, _raw_call)
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
        max_tokens=2000,
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
# Znajduje JUZ poprawnie opakowane wzory $...$ - te zostawiamy calkowicie
# nietkniete, opakowujemy tylko to co lezy MIEDZY nimi (poza istniejacymi
# dolarami). Bez tego np. "Rozwiaz rownanie $\log_2(x)=3$" (poprawne, tylko
# przedrostek "Rozwiaz rownanie " jest poza wzorem) bylo blednie traktowane
# jako "nie w pelni opakowane" (bo caly string nie zaczynal sie od $) i
# dostawalo DODATKOWY dolar na obu koncach: "$Rozwiaz rownanie $...$$".
_EXISTING_DOLLAR_RE = re_module.compile(r'\$[^$]*\$')

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
    ktore model zwrocil bez dolarow. Najpierw wydziela JUZ poprawnie opakowane
    $...$ (te zostaja bez zmian), a dopiero potem naprawia to, co zostalo
    poza nimi - zeby nie podwajac dolarow przy czesciowo opakowanym tekscie."""
    if not t or '\\' not in t:
        return t
    delimited = _EXISTING_DOLLAR_RE.findall(t)
    plain_parts = _EXISTING_DOLLAR_RE.split(t)
    out = []
    for i, plain in enumerate(plain_parts):
        out.append(_wrap_plain_segment(plain))
        if i < len(delimited):
            out.append(delimited[i])
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
        # Napraw podwojne dolary na pojedyncze
        t = t.replace("$$", "$")
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

WZORY MATEMATYCZNE - KRYTYCZNE:
- Kazdy wzor w $...$ np: $x^2 + 3x = 0$
- ZAWSZE \\frac{{ nie rac{{ nie \\rac{{
- NIE uzywaj \\underbrace \\usepackage ani innych komend z \\u na poczatku
- NIE uzywaj cudzyslowow wewnatrz tekstu pytan
- NIGDY nie wstawiaj polskich slow (np. "i", "lub", "oraz", "gdy") do srodka $...$ -
  pisz je jako zwykly tekst POZA wzorem. POPRAWNIE: "$x = 2$ i $x = 3$".
  BLEDNIE: "$x = 2 i x = 3$" (slowo "i" wewnatrz wzoru wyglada wtedy jak zmienna).

FORMAT (TYLKO JSON):
{{
    "title": "{topic} - Quiz",
    "questions": [
        {{
            "id": 1,
            "question": "Pytanie $x^2 = 4$",
            "options": ["$x = 2$", "$x = -2$", "$x = \\pm 2$", "$x = 4$"],
            "correct": 2,
            "explanation": "Bo $x = \\pm 2$"
        }}
    ]
}}

ZASADY:
- Pytania konkretne i merytoryczne
- correct = indeks (0-3)
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
        max_tokens=2500,
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
    w generate_quiz_from_topic."""
    quiz_data = await _raw_generate_quiz_topic_once(
        topic, effective_topic_is_forced, subject, level, num_questions, difficulty, wlasne_instrukcje
    )
    quiz_data = await _verify_and_fill_quiz_math(
        quiz_data, num_questions,
        lambda n: _raw_generate_quiz_topic_once(
            topic, effective_topic_is_forced, subject, level, n, difficulty, wlasne_instrukcje
        ),
    )
    return quiz_data


async def _verify_and_fill_quiz_math(quiz_data: dict, requested_count: int, regenerate) -> dict:
    """Po weryfikacji sympy (_verify_and_fix_quiz_math) niektore pytania
    moga zostac usuniete (bledny klucz bez poprawki wsrod opcji). User
    zamawiajac np. 10 pytan ma dostac 10, nie mniej - wiec dogenerowujemy
    brakujace, az osiagniemy `requested_count` ALBO wyczerpiemy
    `max_rounds` (zeby nie zapetlic sie w nieskonczonosc, gdyby temat byl
    uporczywie podatny na bledne klucze)."""
    quiz_data = _verify_and_fix_quiz_math(quiz_data)
    max_rounds = 3
    for round_i in range(1, max_rounds + 1):
        current = len(quiz_data.get("questions", []))
        missing = requested_count - current
        if missing <= 0:
            break
        print(f"[MathVerify] brakuje {missing} pytan po weryfikacji (runda {round_i}/{max_rounds}) - dogenerowuje...")
        try:
            extra_data = await regenerate(missing)
        except Exception as e:
            print(f"[MathVerify] blad dogenerowania: {e}")
            continue
        extra_data = _verify_and_fix_quiz_math(extra_data)
        quiz_data.setdefault("questions", []).extend(extra_data.get("questions", []))

    questions = quiz_data.get("questions", [])[:requested_count]
    for i, q in enumerate(questions, start=1):
        q["id"] = i
    quiz_data["questions"] = questions
    return quiz_data


def _verify_and_fix_quiz_math(quiz_data: dict) -> dict:
    """Niezalezna weryfikacja sympy (patrz math_verify.py) dla pytan z
    rozpoznawalnym rownaniem kwadratowym - audyt wykazal, ze prompt-based
    samo-weryfikacja NIE wystarcza (model potrafi poprawnie wyprowadzic
    wynik w "explanation" i mimo to wskazac inny, bledny index w
    "correct"). Dla kazdego pytania: jesli wzorzec rozpoznany i AI mial
    zly index ale prawidlowa odpowiedz JEST wsrod opcji -> poprawiamy
    index (+ wyjasnienie, zeby nie zostalo niespojne ze star treascia).
    Jesli prawidlowej odpowiedzi NIE MA wsrod opcji -> pytanie jest
    nieoprawialne, usuwamy je z quizu (lepszy krotszy quiz niz quiz z
    blednym kluczem)."""
    questions = quiz_data.get("questions")
    if not isinstance(questions, list):
        return quiz_data
    kept = []
    for q in questions:
        try:
            text = q.get("question", "")
            options = q.get("options", [])
            result = verify_and_fix_math_question(text, options)
        except Exception as e:
            print(f"[MathVerify] blad weryfikacji pytania: {e}")
            kept.append(q)
            continue
        if result["status"] == "unverifiable":
            kept.append(q)
        elif result["status"] == "match_index":
            true_idx = result["true_index"]
            if q.get("correct") != true_idx:
                print(f"[MathVerify] POPRAWIONO odpowiedz: '{text[:60]}...' correct {q.get('correct')} -> {true_idx}")
                q["correct"] = true_idx
                if result.get("explanation"):
                    q["explanation"] = result["explanation"]
            kept.append(q)
        elif result["status"] == "no_option_matches":
            print(f"[MathVerify] USUNIETO pytanie (brak poprawnej opcji wsrod podanych): '{text[:60]}...'")
        else:
            kept.append(q)
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
