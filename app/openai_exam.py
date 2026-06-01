from openai import AsyncOpenAI
from .config import settings
from typing import List, Dict, Optional
import json

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

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
        JesteÅ› doÅ›wiadczonym nauczycielem. Na podstawie tego materiaÅ‚u stwÃ³rz PROFESJONALNY SPRAWDZIAN.
        
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
                            "question": "TreÅ›Ä‡ pytania",
                            "options": ["a) opcja1", "b) opcja2", "c) opcja3", "d) opcja4"],
                            "correct_answer": "c",
                            "explanation": "WyjaÅ›nienie dlaczego c jest poprawne"
                        }}
                    ]
                }},
                {{
                    "name": "CzÄ™Å›Ä‡ B - Zadania otwarte",
                    "type": "open_ended",
                    "questions": [
                        {{
                            "id": 1,
                            "question": "TreÅ›Ä‡ zadania",
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
        
        WAÅ»NE:
        - Pytania muszÄ… byÄ‡ KONKRETNE i zwiÄ…zane z materiaÅ‚em na obrazku
        - Dystraktory (zÅ‚e odpowiedzi) muszÄ… byÄ‡ REALISTYCZNE
        - WyjaÅ›nienia muszÄ… byÄ‡ KRÃ“TKIE ale JASNE
        - ZwrÃ³Ä‡ TYLKO JSON, bez dodatkowego tekstu
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
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=3000,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        result = response.choices[0].message.content
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
        
        ZwrÃ³Ä‡ TYLKO Markdown, bez dodatkowego tekstu.
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
                                "detail": "high"
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
        level_prompts = {
            "podstawowka": "WyjaÅ›nij jak dla ucznia podstawÃ³wki (kl. 4-8) - prosto, z przykÅ‚adami z Å¼ycia.",
            "gimnazjum": "WyjaÅ›nij jak dla ucznia gimnazjum - Å›redni poziom szczegÃ³Å‚owoÅ›ci.",
            "liceum": "WyjaÅ›nij jak dla ucznia liceum - wiÄ™cej teorii i wzorÃ³w.",
            "studia": "Akademicki poziom - szczegÃ³Å‚owo, z zaawansowanymi konceptami."
        }
        
        style_prompts = {
            "academic": "SzczegÃ³Å‚owe notatki z definicjami, wzorami i przykÅ‚adami.",
            "simple": "ZwiÄ™zÅ‚e punkty - tylko najwaÅ¼niejsze informacje.",
            "visual": "Notatki z diagramami i wizualizacjami."
        }
        
        prompt = f"""
StwÃ³rz KOMPLETNE, PROFESJONALNE NOTATKI na temat: "{topic}"

WYMAGANIA:
- Przedmiot: {subject}
- Poziom: {level_prompts.get(level, level_prompts['liceum'])}
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

WAÅ»NE:
- Markdown (##, -, **)
- PojÄ™cia: **POJÄ˜CIE**
- Wzory: $x^2$
- Min 300 sÅ‚Ã³w
- PO POLSKU!

ZwrÃ³Ä‡ TYLKO Markdown.
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
        
        prompt = f"""Jestes ekspertem matematycznym i nauczycielem. Przeanalizuj obrazek ze zdjeciami zadan matematycznych.

ZADANIE:
1. Przeczytaj WSZYSTKIE zadania na obrazku
2. Rozwiaz kazde zadanie krok po kroku
3. Na podstawie tresci i rozwiazan stwórz {num_questions} pytan quizowych

WAZNE:
- NIE pytaj o numery zadan (np. "Co bylo w zadaniu 3?")
- Pytaj o MATEMATYCZNE KONCEPTY z tych zadan (np. "Ile wynosi x w rownaniu 2x+4=10?")
- Kazde pytanie musi miec konkretna odpowiedz matematyczna
- KRYTYCZNE: Kazdy wzor matematyczny MUSI byc w dolarach np: $x^2$, $b/(2a)$
- ZAKAZ pisania wzorow bez dolarow

FORMAT (TYLKO JSON):
{{
    "title": "Quiz matematyczny",
    "questions": [
        {{
            "id": 1,
            "question": "Tresc pytania z konkretnymi liczbami i wzorami",
            "options": ["$a$", "$b$", "$c$", "$d$"],
            "correct": 0,
            "explanation": "Krok po kroku: ..."
        }}
    ]
}}

Zwroc TYLKO JSON."""
        
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
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        quiz_data = json.loads(response.choices[0].message.content)
        print(f"âœ… Quiz: {quiz_data.get('title', 'Quiz')}")
        
        return {"success": True, "quiz": quiz_data}
        
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d: {str(e)}")
        return {"success": False, "error": str(e)}




import re as re_module

def fix_latex_in_quiz(quiz_data):
    """Naprawia typowe bledy LaTeX zanim dotrze do frontendu"""
    def fix(t):
        if not t: return t
        # Napraw rac{ -> \frac{
        t = t.replace("\\rac{", "\\frac{")
        t = re_module.sub(r"(?<![a-zA-Z\\])rac\{", r"\\frac{", t)
        # Napraw ext{ -> \text{
        t = t.replace("\\ext{", "\\text{")
        t = re_module.sub(r"(?<![a-zA-Z\\])ext\{", r"\\text{", t)
        # Usun \text{...} - zamien na sam tekst bez komendy
        t = re_module.sub(r"\\text\{([^}]*)\}", r"\1", t)
        t = re_module.sub(r"(?<![a-zA-Z\\\\])imes\\b", r"\\\\times", t)
        t = re_module.sub(r"(?<![a-zA-Z\\\\])riangle\\b", r"\\\\triangle", t)
        t = re_module.sub(r"(?<![a-zA-Z\\\\])cdot\\b", r"\\\\cdot", t)
        return t
    if "questions" in quiz_data:
        for q in quiz_data["questions"]:
            if "question" in q: q["question"] = fix(q["question"])
            if "explanation" in q:
                exp = fix(q["explanation"])
                # Usun nierenderowany LaTeX - znaki jak x=, b^2 itp bez dolarow
                exp = re_module.sub(r'(?<!\$)\\[a-zA-Z]+(?!\$)', lambda m: '', exp)
                exp = re_module.sub(r'\s+', ' ', exp).strip()
                q["explanation"] = exp
            if "options" in q: q["options"] = [fix(o) for o in q["options"]]
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
    try:
        level_map = {
            "podstawowka": "dla ucznia podstawÃ³wki",
            "gimnazjum": "dla ucznia gimnazjum",
            "liceum": "dla ucznia liceum",
            "studia": "akademicki poziom"
        }
        
        # Budujemy opis poziomu + trudności razem
        combo_map = {
            ("podstawowka", "easy"):   "Klasa 4-5 szkoły podstawowej. Dodawanie ułamków, proste równania x+3=7, procenty do 100%.",
            ("podstawowka", "medium"): "Klasa 6-7 szkoły podstawowej. Równania liniowe, potęgi, proste geometria.",
            ("podstawowka", "hard"):   "Klasa 8 szkoły podstawowej. Układy równań 2x2, twierdzenie Pitagorasa, pierwiastki.",
            ("liceum", "easy"):        "Liceum klasa 1. Funkcja liniowa, równania kwadratowe, trygonometria podstawowa.",
            ("liceum", "medium"):      "Liceum klasa 2-3. Pochodne, logarytmy, ciągi, geometria analityczna.",
            ("liceum", "hard"):        "Matura rozszerzona. Całki, kombinatoryka, dowody, zaawansowane trygonometria.",
            ("technikum", "easy"):     "Technikum klasa 1-2. Algebra, funkcje, podstawy statystyki.",
            ("technikum", "medium"):   "Technikum klasa 3. Rachunek różniczkowy w zastosowaniach technicznych.",
            ("technikum", "hard"):     "Technikum klasa 4. Zaawansowana matematyka techniczna, całki oznaczone.",
            ("studia", "easy"):        "Studia rok 1 semestr 1. Granice, pochodne wyższego rzędu, podstawy algebry liniowej.",
            ("studia", "medium"):      "Studia rok 2. Całki wielokrotne, szeregi Taylora, przestrzenie wektorowe, macierze.",
            ("studia", "hard"):        "Studia zaawansowane / magisterskie. Równania różniczkowe cząstkowe, analiza funkcjonalna, topologia.",
        }
        poziom_opis = combo_map.get((level, difficulty), f"poziom {level}, trudnosc {difficulty}")

        # Wlasne instrukcje
        instrukcje_blok = ""
        if wlasne_instrukcje and wlasne_instrukcje.strip():
            instrukcje_blok = (
                "\n=== WLASNE INSTRUKCJE (NAJWYZSZY PRIORYTET) ===\n"
                "Uczen podal nastepujace instrukcje. MUSISZ je bezwzglednie uwzglednic:\n"
                + wlasne_instrukcje.strip() + "\n"
                + "Dostosuj CALY quiz do powyzszych wskazowek.\n"
            )

        prompt = f"""Stwórz quiz na temat: "{topic}"

PARAMETRY:
- Przedmiot: {subject}
- Liczba pytań: {num_questions}
- DOKŁADNY POZIOM: {poziom_opis}
{instrukcje_blok}
KRYTYCZNE: Pytania MUSZĄ pasować do opisu poziomu powyżej.
Jeśli poziom to studia — pytaj o całki, macierze, szeregi — NIE o równania kwadratowe.
Jeśli poziom to podstawówka — NIE pytaj o pochodne ani logarytmy.

WZORY MATEMATYCZNE - KRYTYCZNE:
- Kazdy wzor w $...$ np: $x^2 + 3x = 0$
- ZAWSZE \\frac{{ nie rac{{ nie \\rac{{
- NIE uzywaj \\underbrace \\usepackage ani innych komend z \\u na poczatku
- NIE uzywaj cudzyslowow wewnatrz tekstu pytan

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
        
        difficulty_map = {
            "easy": "łatwy",
            "medium": "średni",
            "hard": "trudny"
        }

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
        
        return {"success": True, "quiz": quiz_data}
        
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d: {str(e)}")
        return {"success": False, "error": str(e)}