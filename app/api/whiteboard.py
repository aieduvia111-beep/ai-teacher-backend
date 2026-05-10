"""WHITEBOARD API - generuje szczegółowe wyjaśnienia krok po kroku dla tablicy AI"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from ..config import settings
import json

router = APIRouter(prefix="/api/v1/whiteboard", tags=["whiteboard"])

class WhiteboardRequest(BaseModel):
    topic: str = ""
    level: str = "liceum"
    tempo: str = "srednia"  # szybka, srednia, szczegolowa
    images: Optional[List[str]] = None
    wlasne_instrukcje: Optional[str] = None

class ExplainRequest(BaseModel):
    element_text: str
    element_type: str
    topic: str
    level: str = "liceum"

LEVEL_DESC = {
    "kid": "dla dziecka w wieku 10-13 lat — BARDZO prosty język, analogie z życia codziennego, krótkie zdania, bez skomplikowanych terminów",
    "liceum": "poziom liceum — pełne definicje, wzory matematyczne, przykłady obliczeń krok po kroku",
    "matura": "poziom matura — definicje słownikowe, wszystkie wzory i prawa, przykłady zadań maturalnych z rozwiązaniem, tipy egzaminacyjne",
    "studia": "poziom studencki — pełna teoria, wyprowadzenia wzorów, zaawansowane zastosowania, notacja matematyczna"
}

SYSTEM_PROMPT = """Jesteś najlepszym nauczycielem matematyki i nauk ścisłych. 
Tłumaczysz SZCZEGÓŁOWO i KONKRETNIE. 
Nigdy nie piszesz ogólników jak "to ważny temat" lub "warto to znać".
Zawsze podajesz konkretne wzory, definicje, przykłady obliczeń.
Odpowiadasz TYLKO jako JSON bez markdown, bez komentarzy."""

def build_whiteboard_prompt(topic: str, level: str, tempo: str = "srednia", extra: str = "") -> str:
    level_desc = LEVEL_DESC.get(level, LEVEL_DESC["liceum"])
    extra_txt = f"\nDodatkowe instrukcje od ucznia: {extra}" if extra else ""
    
    TEMPO_MAP = {
        "szybka": ("4-5", "Krótkie narration (1-2 zdania). Tylko najważniejsze wzory i definicje. Bez rozbudowanych przykładów."),
        "srednia": ("5-6", "Narration 2-3 zdania. Pełne definicje, wzory, jeden przykład obliczeniowy per krok."),
        "szczegolowa": ("7-8", "Narration 3-4 zdania. Szczegółowe wyprowadzenia, wiele przykładów z liczbami, ćwiczenia, wskazówki egzaminacyjne.")
    }
    n_steps, tempo_desc = TEMPO_MAP.get(tempo, TEMPO_MAP["srednia"])
    
    return f"""Wytłumacz SZCZEGÓŁOWO i KONKRETNIE temat "{topic}" {level_desc}.{extra_txt}

ZASADY narration (co mówisz podczas rysowania):
- Mów KONKRETNIE co właśnie rysujesz: wzory, definicje, przykłady
- Np. dla całek: "Całka oznaczona to pole pod wykresem funkcji. Obliczamy ją wzorem: całka od a do b z f(x) dx równa się F(b) minus F(a)"
- NIE mów: "to ważne pojęcie", "warto zapamiętać", "jest to fundamentalne"
- Podawaj liczby, jednostki, przykłady konkretnych obliczeń
- 2-4 zdania per krok

ZASADY elementów na tablicy:
- Min 8-10 elementów per krok
- Zawsze: stepnum, title, divider na początku kroku
- Używaj formula dla wzorów matematycznych
- Używaj box dla definicji i kluczowych pojęć  
- Używaj circle dla oznczeń zmiennych (a, b, x, n)
- Używaj arrow dla pokazania zależności
- Używaj highlight dla podkreślenia ważnych fragmentów
- Tekst w elementach type=text max 70 znaków na linię
- Y rośnie o 240px z każdym krokiem

Odpowiedz TYLKO jako JSON:
{{
  "steps": [
    {{
      "title": "Krok 1: Definicja",
      "narration": "Konkretne 2-4 zdania co teraz tłumaczymy z wzorami",
      "elements": [
        {{"type":"stepnum","text":"1","x":28,"y":80}},
        {{"type":"title","text":"Tytuł kroku","x":55,"y":82,"size":22,"color":"#a78bfa"}},
        {{"type":"divider","x":40,"y":104,"x2":680,"y2":104}},
        {{"type":"text","text":"Konkretna definicja z treścią","x":55,"y":130,"size":14,"maxW":580}},
        {{"type":"box","text":"Kluczowe pojęcie: definicja","x":55,"y":155,"w":300,"h":58,"fill":"rgba(124,106,255,0.08)","stroke":"rgba(124,106,255,0.35)"}},
        {{"type":"formula","text":"wzór matematyczny","x":420,"y":184}},
        {{"type":"circle","text":"x","x":550,"y":184,"r":28,"color":"#7c6aff","fill":"rgba(124,106,255,0.08)"}},
        {{"type":"arrow","x1":210,"y1":184,"x2":380,"y2":184,"label":"oznacza","color":"#22d3a0"}},
        {{"type":"highlight","x":40,"y":152,"w":600,"h":62,"color":"rgba(245,166,35,0.07)","color2":"rgba(245,166,35,0.22)"}},
        {{"type":"text","text":"Przykład: konkretne obliczenie z liczbami","x":55,"y":228,"size":13,"maxW":580,"color":"#8888a0"}}
      ]
    }}
  ]
}}

Wygeneruj {n_steps} kroków dla "{topic}". {tempo_desc} Każdy krok Y o 240px wyżej niż poprzedni."""


def build_vision_prompt(level: str, extra: str = "") -> str:
    level_desc = LEVEL_DESC.get(level, LEVEL_DESC["liceum"])
    extra_txt = f"\nDodatkowe instrukcje: {extra}" if extra else ""
    return f"""Przeanalizuj to zdjęcie zadania/materiału edukacyjnego i wytłumacz je {level_desc}.{extra_txt}
Najpierw zidentyfikuj temat, potem wytłumacz krok po kroku rozwiązanie lub pojęcia.
Odpowiedz jako JSON z "steps" jak w standardowym formacie tablicy."""


@router.post("/generate")
async def generate_whiteboard(req: WhiteboardRequest):
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    try:
        # Buduj wiadomosc
        if req.images and len(req.images) > 0:
            content = []
            for img_b64 in req.images[:4]:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
            content.append({
                "type": "text",
                "text": build_vision_prompt(req.level, req.wlasne_instrukcje or "")
            })
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content}
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_whiteboard_prompt(req.topic, req.level, req.tempo, req.wlasne_instrukcje or "")}
            ]
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=4000,
            temperature=0.3,
            timeout=30
        )
        
        raw = response.choices[0].message.content.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()
        
        # Znajdz JSON
        s = raw.find('{')
        e = raw.rfind('}')
        if s >= 0 and e > s:
            data = json.loads(raw[s:e+1])
            return {"ok": True, "steps": data.get("steps", []), "topic": req.topic}
        else:
            raise ValueError("No JSON in response")
            
    except Exception as ex:
        print(f"[Whiteboard] Error: {ex}")
        return {"ok": False, "error": str(ex), "steps": []}


@router.post("/explain")
async def explain_element(req: ExplainRequest):
    """Wyjaśnij kliknięty element tablicy szczegółowo"""
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    level_desc = LEVEL_DESC.get(req.level, LEVEL_DESC["liceum"])
    
    prompt = f"""Uczeń kliknął element na tablicy edukacyjnej i chce dokładniejszego wyjaśnienia.

Temat główny: {req.topic}
Kliknięty element: "{req.element_text}" (typ: {req.element_type})
Poziom ucznia: {level_desc}

Wytłumacz ten element BARDZO SZCZEGÓŁOWO w 3-5 zdaniach.
Podaj: definicję, jak to działa, przykład z liczbami, zastosowanie.
Mów naturalnie jakbyś tłumaczył przy tablicy.
Odpowiedz TYLKO tekstem (nie JSON), po polsku."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.4,
            timeout=15
        )
        explanation = response.choices[0].message.content.strip()
        return {"ok": True, "explanation": explanation}
    except Exception as ex:
        return {"ok": False, "explanation": f"Nie udało się wytłumaczyć: {req.element_text}"}
