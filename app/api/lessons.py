from ..error_logger import log_error
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
from openai import OpenAI
from ..config import settings

router = APIRouter(prefix="/api/v1/lessons", tags=["lessons"])
client = OpenAI(api_key=settings.OPENAI_API_KEY)

class CreateLessonPlanRequest(BaseModel):
    topic: str
    subject: str
    level: str
    total_days: Optional[int] = 7
    minutes_per_day: Optional[int] = 30
    user_id: Optional[int] = 1
    additional_info: Optional[str] = ""

@router.post("/create-plan")
def create_lesson_plan(request: CreateLessonPlanRequest):
    try:
        safe_days = min(max(int(request.total_days or 7), 1), 60)
        safe_min = min(max(int(request.minutes_per_day or 30), 10), 240)

        prompt = f"""Jestes doswiadczonym nauczycielem tworzacym profesjonalny plan nauki.
Stworz szczegolowy plan nauki na {safe_days} dni dla ucznia.

DANE:
- Temat: {request.topic}
- Przedmiot: {request.subject}  
- Poziom: {request.level}
- Czas dziennie: {safe_min} minut
- Dodatkowe info: {request.additional_info or "brak"}

POZIOM UCZNIA - KRYTYCZNE:
Poziom: {request.level}
- klasa 1-3 = bardzo proste, konkretne przyklady z zycia, bez abstrakcji
- klasa 4-6 = proste, przyklady z zycia codziennego
- klasa 7-8 = sredni poziom, wprowadzaj abstrakcje
- liceum = zaawansowany, pelna teoria i wzory
- matura = bardzo zaawansowany, zadania maturalne
DOSTOSUJ trudnosc, jezyk i zadania do tego poziomu!

ZASADY (KRYTYCZNE):
0. ZAKAZ: nie pisz numerow stron ani nazw podrecznikow - uczen moze nie miec tego samego podrecznika!
1. Kazdy dzien = INNY, KONKRETNY podtemat z dziedziny {request.topic}
2. Ukladaj progresywnie: dzien 1 = podstawy, ostatni dzien = zaawansowane/powtorka
3. Kazdy krok musi miec KONKRETNA tresc - co dokladnie czytac/robic
4. NIE pisz ogolnikow jak "nauka materialu" - pisz np. "Przeczytaj rozdzial o fotosyntezie - reakcja jasna i ciemna"
5. Steps musza byc rozne: teoria, cwiczenia, powtorka, quiz, mapa mysli etc.
6. REALISTYCZNY CZAS: masz {safe_min} minut dziennie - dopasuj ilosc i dlugosc krokow do tego czasu
   - 15 min = 1-2 krotkie kroki (np. zapoznaj sie z definicja + zrob notatke)
   - 30 min = 2-3 kroki sredniej dlugosci
   - 60 min = 3-4 pelne kroki z cwiczeniami
   - NIE planuj wiecej niz mozna zrobic w {safe_min} minutach!

Przyklady dobrych steps:
- "Zapoznaj sie z teoria i zrob notatki: definicja i rodzaje {request.topic}"
- "Rozwiaz 5 zadan z {request.topic} - poziom podstawowy"  
- "Zrob mape mysli laczaca wszystkie pojecia z tego tygodnia"
- "Sprawdz sie - odpowiedz na 10 pytan z {request.topic}"

Zwroc TYLKO JSON bez markdown:
{{
  "title": "Plan nauki: {request.topic}",
  "description": "Profesjonalny {safe_days}-dniowy plan nauki - {request.subject}, {request.level}",
  "total_days": {safe_days},
  "minutes_per_day": {safe_min},
  "level": "{request.level}",
  "days": [
    {{
      "day": 1,
      "title": "Dzien 1: [bardzo konkretny podtemat]",
      "goal": "Dzisiaj opanujesz: [konkretnie co]",
      "steps": [
        {{"type": "reading", "title": "[Konkretny tytul]", "content": "[Co dokladnie robic - minimum 15 slow]", "duration": {safe_min // 3}}},
        {{"type": "practice", "title": "[Konkretny tytul]", "content": "[Co dokladnie robic - minimum 15 slow]", "duration": {safe_min // 3}}},
        {{"type": "review", "title": "Powtorka", "content": "Sprawdz czy opanowales material dnia - zrob krotki quiz lub wytlumacz temat wlasnym slowami", "duration": {safe_min // 3}}}
      ],
      "review_topics": ["[temat do powtorzenia pozniej]"]
    }}
  ],
  "review_schedule": []
}}"""

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=min(16000, max(4000, safe_days * 400)),
            temperature=0.7
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        s = raw.find("{"); e = raw.rfind("}")
        plan = json.loads(raw[s:e+1])
        return {"success": True, "lesson_id": None, "plan": plan}

    except Exception as e:
        return {"success": False, "error": str(e), "plan": {}}

@router.get("/my-plans/{user_id}")
def get_my_plans(user_id: int):
    return {"success": True, "plans": []}

@router.get("/plan/{lesson_id}/{user_id}")
def get_plan(lesson_id: int, user_id: int):
    return {"success": False, "error": "Plan nie znaleziony"}

@router.post("/complete-day")
def complete_day(request: dict):
    return {"success": True}
