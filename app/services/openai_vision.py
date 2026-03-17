import base64
from openai import OpenAI
from ..config import settings


client = OpenAI(api_key=settings.OPENAI_API_KEY)


def analyze_image(image_base64: str, prompt: str = None) -> dict:
    """
    Analizuje obraz używając GPT-4 Vision
    
    Args:
        image_base64: Obraz zakodowany w base64
        prompt: Opcjonalne pytanie (domyślnie: analizuj zadanie)
    
    Returns:
        dict z odpowiedzią AI
    """
    
    # Domyślny prompt jeśli nie podano
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
        # Wywołaj GPT-4 Vision API
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        # Wyciągnij odpowiedź
        answer = response.choices[0].message.content
        
        return {
            "success": True,
            "analysis": answer,
            "model": "gpt-4-vision-preview",
            "tokens_used": response.usage.total_tokens
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def analyze_math_problem(image_base64: str) -> dict:
    """Wyspecjalizowana funkcja do analizy zadań matematycznych"""
    
    prompt = """
    Jesteś ekspertem od matematyki. Przeanalizuj to zadanie:
    
    1. Jaki to typ zadania? (równanie, geometria, etc.)
    2. Jakie dane są podane?
    3. Co trzeba obliczyć?
    4. Rozwiąż krok po kroku
    5. Podaj odpowiedź końcową
    
    Formatuj wzory czytelnie. Odpowiadaj po polsku.
    """
    
    return analyze_image(image_base64, prompt)


def check_homework(image_base64: str) -> dict:
    """Sprawdza pracę domową - szuka błędów"""
    
    prompt = """
    Sprawdź tę pracę domową:
    
    1. Które zadania są rozwiązane poprawnie? ✅
    2. Gdzie są błędy? ❌ (wskaż konkretną linię)
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
    """
    Rozwiazuje zadanie ze zdjecia krok po kroku.
    Zwraca structured JSON z problems[].
    """
    if "base64," in image_base64:
        image_base64 = image_base64.split("base64,")[1]

    subject_rules = {
        "matematyka": "Uzywaj LaTeX dla wzorow: $x^2$. Podaj dokladne obliczenia.",
        "fizyka": "Podaj wzory fizyczne, jednostki, podstaw liczby.",
        "chemia": "Podaj rownania chemiczne, wzory, stechiometrie.",
        "biologia": "Opisz procesy biologiczne, nazwy lacinckie jezeli istotne.",
        "historia": "Podaj daty, postaci, zwiazki przyczynowo-skutkowe.",
        "polski": "Analizuj jezyk, stylistyke, srodki wyrazu.",
        "angielski": "Correct grammar, explain rules in Polish.",
        "inne": "Odpowiedz merytorycznie na zadane pytanie.",
    }

    mode_instruction = {
        "solve": "Rozwiaz kazde zadanie krok po kroku.",
        "check": "Sprawdz czy rozwiazania sa poprawne. Znajdz bledy i popraw je.",
        "explain": "Wyjasni temat ogolnie, nie rozwiazuj zadan.",
        "grade": "Ocen rozwiazanie ucznia. Napisz co jest dobrze, co zle, ile punktow by dostal (0-10) i jak poprawic bledy.",
    }.get(mode, "Rozwiaz kazde zadanie krok po kroku.")

    similar_instruction = (
        'Dla kazdego zadania dodaj "similar_problems": ["podobne zadanie 1", "podobne zadanie 2"]'
        if generate_similar else
        '"similar_problems": []'
    )

    prompt = f"""Jestes ekspertem z przedmiotu: {subject}.
{subject_rules.get(subject, "")}

INSTRUKCJA: {mode_instruction}

Przeanalizuj WSZYSTKIE zadania na zdjeciu i rozwiaz je.

ODPOWIEDZ TYLKO W JSON (bez markdown, bez ```, tylko czysty JSON):
{{
  "problems": [
    {{
      "question": "Tresc zadania przepisana z obrazka",
      "solution": {{
        "steps": [
          "Krok 1: ...",
          "Krok 2: ...",
          "Krok 3: ..."
        ],
        "final_answer": "Ostateczna odpowiedz",
        "explanation": "{'Krotkie wyjasnienie teorii potrzebnej do tego zadania' if show_explanation else ''}"
      }},
      {similar_instruction}
    }}
  ]
}}

ZASADY:
- Jezeli zadanie jest po polsku - odpowiadaj po polsku
- Kroki musza byc KONKRETNE z obliczeniami, nie ogolniki
- Jezeli nie widzisz zadnego zadania - zwroc {{"problems": [], "error": "Nie wykryto zadan na zdjeciu"}}
- TYLKO JSON, zero komentarzy
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
