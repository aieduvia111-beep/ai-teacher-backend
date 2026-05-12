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

        prompt = f"""Wygeneruj szczegolowy plan nauki dla ucznia liceum.
Temat: {request.topic}
Przedmiot: {request.subject}
Poziom: {request.level}
Liczba dni: {safe_days}
Minut dziennie: {safe_min}
Dodatkowe info: {request.additional_info or "brak"}

WAZNE: Kazdy dzien musi miec INNY konkretny temat zwiazany z {request.topic}.
Nie powtarzaj tresci. Ukladaj od podstaw do zaawansowanych.

Zwroc TYLKO JSON bez markdown:
{{
  "title": "Plan nauki: {request.topic}",
  "description": "Plan nauki przedmiotu {request.subject} na poziomie {request.level}",
  "total_days": {safe_days},
  "minutes_per_day": {safe_min},
  "level": "{request.level}",
  "days": [
    {{
      "day": 1,
      "title": "Dzien 1: [konkretny temat]",
      "goal": "Co osiagniesz dzisiaj - konkretnie",
      "steps": [
        {{"type": "reading", "title": "Przeczytaj", "content": "Konkretny material do przestudiowania", "duration": {safe_min // 2}}},
        {{"type": "practice", "title": "Cwiczenia", "content": "Konkretne zadania do wykonania", "duration": {safe_min // 2}}}
      ],
      "review_topics": []
    }}
  ],
  "review_schedule": []
}}"""

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
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
