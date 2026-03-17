import base64
from openai import OpenAI
from .config import settings


client = OpenAI(api_key=settings.OPENAI_API_KEY)


def analyze_image(image_base64: str, prompt: str = None) -> dict:
    if not prompt:
        prompt = """
        Jesteś nauczycielem matematyki i fizyki. 
        Przeanalizuj to zdjęcie i powiedz:
        1. Co widzisz? (zadanie, wzór, notatkę?)
        2. Czy są jakieś błędy?
        3. Jak to rozwiązać krok po kroku?
        
        Odpowiadaj po polsku, zwięźle i konkretnie.
        """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            }],
            max_tokens=1000
        )
        answer = response.choices[0].message.content
        return {"success": True, "analysis": answer, "model": "gpt-4-vision-preview", "tokens_used": response.usage.total_tokens}
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_math_problem(image_base64: str) -> dict:
    prompt = """
    Jesteś ekspertem od matematyki. Przeanalizuj to zadanie:
    1. Jaki to typ zadania?
    2. Jakie dane są podane?
    3. Co trzeba obliczyć?
    4. Rozwiąż krok po kroku
    5. Podaj odpowiedź końcową
    Formatuj wzory czytelnie. Odpowiadaj po polsku.
    """
    return analyze_image(image_base64, prompt)


def check_homework(image_base64: str) -> dict:
    prompt = """
    Sprawdź tę pracę domową:
    1. Które zadania są rozwiązane poprawnie?
    2. Gdzie są błędy? (wskaż konkretną linię)
    3. Jak naprawić błędy?
    4. Oceń ogólnie (1-10)
    Bądź konstruktywny. Po polsku.
    """
    return analyze_image(image_base64, prompt)


def solve_homework_vision(
    image_base64: str,
    subject: str = "matematyka",
    mode: str = "solve",
    show_steps: bool = True,
    generate_similar: bool = True,
    show_explanation: bool = True,
) -> dict:
    if "base64," in image_base64:
        image_base64 = image_base64.split("base64,")[1]

    subject_rules = {
        "matematyka": "WSZYSTKIE wyrażenia matematyczne MUSISZ zapisywać w LaTeX otoczonym dolarami: $x^2$, $\\frac{a}{b}$, $\\sqrt{x}$, $x_1$, $ax^3+bx^2+cx+d$. Nigdy nie pisz x^2 bez dolarów.",
        "fizyka": "Wzory fizyczne w LaTeX: $F=ma$, $v^2=v_0^2+2as$. Podaj jednostki. Podstaw liczby.",
        "chemia": "Równania chemiczne, wzory sumaryczne, stechiometria.",
        "biologia": "Opisz procesy biologiczne, nazwy łacińskie jeżeli istotne.",
        "historia": "Podaj daty, postaci, związki przyczynowo-skutkowe.",
        "polski": "Analizuj język, stylistykę, środki wyrazu.",
        "angielski": "Correct grammar, explain rules in Polish.",
        "inne": "Odpowiedz merytorycznie na zadane pytanie.",
    }

    mode_instruction = {
        "solve": "Rozwiąż każde zadanie krok po kroku z pełnymi obliczeniami.",
        "check": "Sprawdź czy rozwiązania są poprawne. Znajdź błędy i popraw je.",
        "explain": "Wyjaśnij temat ogólnie, nie rozwiązuj zadań.",
        "grade": "Oceń rozwiązanie ucznia. Napisz co jest dobrze, co źle, ile punktów by dostał (0-10).",
    }.get(mode, "Rozwiąż każde zadanie krok po kroku.")

    similar_instruction = (
        '"similar_problems": ["Podobne zadanie 1 (bez LaTeX w treści)", "Podobne zadanie 2"]'
        if generate_similar else
        '"similar_problems": []'
    )

    explanation_field = "Krótkie wyjaśnienie teorii potrzebnej do tego zadania" if show_explanation else ""

    prompt = f"""Jesteś ekspertem z przedmiotu: {subject}.

FORMATOWANIE MATEMATYKI — KRYTYCZNE:
{subject_rules.get(subject, "")}
- Każdy wzór, równanie, wyrażenie algebraiczne MUSI być w $...$
- Przykłady POPRAWNE: $x^2 + 5x - 6 = 0$, $W(x) = 9x^3 - 21x^2 + 16x - 4$, $x = \\frac{{-b \\pm \\sqrt{{b^2-4ac}}}}{{2a}}$
- Przykłady BŁĘDNE: x^2 + 5x - 6 = 0 (bez dolarów), W(x) = 9x^3 (bez dolarów)
- W krokach rozwiązania: każde obliczenie w osobnym $...$

INSTRUKCJA: {mode_instruction}

Przeanalizuj WSZYSTKIE zadania na zdjęciu i rozwiąż je.

ODPOWIEDZ TYLKO W JSON (bez markdown, bez ```, tylko czysty JSON):
{{
  "problems": [
    {{
      "question": "Treść zadania przepisana z obrazka (wzory w $...$)",
      "solution": {{
        "steps": [
          "Krok 1: opis ... $wzor = wynik$",
          "Krok 2: opis ... $wzor = wynik$"
        ],
        "final_answer": "Odpowiedź z wzorami w $...$",
        "explanation": "{explanation_field}"
      }},
      {similar_instruction}
    }}
  ]
}}

ZASADY:
- Odpowiadaj po polsku
- Kroki muszą być KONKRETNE z obliczeniami
- Jeżeli nie widzisz żadnego zadania: {{"problems": [], "error": "Nie wykryto zadań na zdjęciu"}}
- TYLKO JSON, zero komentarzy poza JSON
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=4000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        import json
        raw = response.choices[0].message.content
        data = json.loads(raw)
        data["success"] = True
        print(f"Vision solve: {len(data.get('problems', []))} problemow")
        return data

    except Exception as e:
        print(f"Vision error: {e}")
        return {"success": False, "error": str(e), "problems": []}


# Aliasy dla kompatybilności z main.py
analyze_image_with_gpt4_vision = analyze_image
vision_analyze_homework = check_homework
vision_analyze_diagram = analyze_image