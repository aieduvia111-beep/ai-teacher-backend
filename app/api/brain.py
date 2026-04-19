"""
🧠 EDUVIA BRAIN API
Analizuje dane użytkownika z Firebase i zwraca mapę wiedzy
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI
from typing import List, Optional, Dict, Any
import json
from app.config import settings

router = APIRouter(prefix="/api/v1/brain", tags=["brain"])
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# ── MODELE ──────────────────────────────────────────────────────────────────

class BrainRequest(BaseModel):
    uid: str
    quizHistory: Optional[List[Dict[str, Any]]] = []
    notesHistory: Optional[List[Dict[str, Any]]] = []
    understandingHistory: Optional[List[Dict[str, Any]]] = []
    examHistory: Optional[List[Dict[str, Any]]] = []
    examResults: Optional[List[Dict[str, Any]]] = []
    chatHistory: Optional[List[Dict[str, Any]]] = []
    lessonProgress: Optional[List[Dict[str, Any]]] = []


# ── ENDPOINT ─────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_brain(req: BrainRequest):
    """
    Analizuje wszystkie dane użytkownika i zwraca mapę wiedzy
    """
    try:
        # Sprawdź czy użytkownik ma jakieś dane
        has_data = (
            len(req.quizHistory or []) > 0 or
            len(req.notesHistory or []) > 0 or
            len(req.understandingHistory or []) > 0 or
            len(req.examHistory or []) > 0 or
            len(req.lessonProgress or []) > 0
        )

        if not has_data:
            return {
                "success": True,
                "overall_pct": 0,
                "subjects": [],
                "holes": [],
                "summary": "Zacznij robić quizy i notatki, a Brain przeanalizuje Twoją wiedzę!",
                "no_data": True
            }

        # Zbuduj podsumowanie danych
        data_summary = _build_data_summary(req)

        # Wyślij do OpenAI
        prompt = f"""Jesteś Eduvia Brain — AI analizującym wiedzę ucznia na podstawie jego aktywności w aplikacji edukacyjnej.

Dane ucznia:
{data_summary}

Odpowiedz TYLKO w formacie JSON (bez markdown):
{{
  "overall_pct": liczba 0-100 (ogólny % gotowości),
  "subjects": [
    {{
      "name": "Matematyka",
      "pct": 75,
      "color": "green|yellow|red",
      "icon": "➗",
      "quizzes_done": 3,
      "avg_score": 72,
      "status": "Dobra robota! Powtórz ułamki.",
      "trend": "up|down|stable"
    }}
  ],
  "holes": [
    {{
      "subject": "Historia",
      "topic": "Potop Szwedzki",
      "severity": "high|medium|low",
      "reason": "Błędna odpowiedź 3 razy w quizach",
      "fix_time_min": 5
    }}
  ],
  "summary": "Krótkie zdanie 1-2 zdania o stanie wiedzy ucznia",
  "strongest_subject": "Biologia",
  "weakest_subject": "Historia",
  "weekly_trend": "improving|declining|stable"
}}

ZASADY:
- color "green" gdy pct >= 70, "yellow" gdy 40-69, "red" gdy < 40
- holes to konkretne tematy które uczeń nie rozumie (max 5)
- severity "high" gdy błędne > 2 razy lub ocena 😰, "medium" gdy 1-2 razy, "low" gdy ocena 😐
- Uwzględnij WSZYSTKIE źródła danych: quizy, notatki, ankiety, sprawdziany, plan nauki
- Podaj TYLKO przedmioty które uczeń faktycznie robił
- overall_pct to średnia ważona ze wszystkich przedmiotów"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content
        result = json.loads(raw)

        return {
            "success": True,
            **result
        }

    except Exception as e:
        print(f"❌ Brain analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_data_summary(req: BrainRequest) -> str:
    """Buduje czytelne podsumowanie danych dla OpenAI"""
    lines = []
    rating_map = {1: "Nie rozumiem", 2: "Troche", 3: "Rozumiem", 4: "Swietnie"}

    # Quizy
    if req.quizHistory:
        lines.append(f"\n=== QUIZY ({len(req.quizHistory)} quizow) ===")
        for q in req.quizHistory[-20:]:
            correct = q.get('correct', 0)
            total = q.get('total', 1) or 1
            pct = q.get('pct') or round(correct / total * 100)
            subject = q.get('subject', 'inne')
            title = q.get('title', 'Quiz')
            wrong = [w.get('question', '')[:50] for w in (q.get('wrongQuestions') or [])][:3]
            line = f"- {subject}: '{title}' — {pct}% ({correct}/{total})"
            if wrong:
                line += f" | Bledne: {', '.join(wrong)}"
            lines.append(line)

    # Notatki
    if req.notesHistory:
        lines.append(f"\n=== NOTATKI ({len(req.notesHistory)} notatek) ===")
        for n in req.notesHistory[-15:]:
            lines.append(f"- {n.get('subject','inne')}: '{n.get('topic','')}'")

    # Ankiety
    if req.understandingHistory:
        lines.append(f"\n=== OCENY WIEDZY ===")
        for u in req.understandingHistory[-15:]:
            level = u.get('level', 2)
            lines.append(f"- {u.get('subject','inne')}: '{u.get('topic','')}' -> {rating_map.get(level, '?')}")

    # Sprawdziany
    if req.examHistory:
        lines.append(f"\n=== SPRAWDZIANY ({len(req.examHistory)}) ===")
        for e in req.examHistory[-10:]:
            lines.append(f"- {e.get('subject','inne')}: '{e.get('topic','')}'")

    # Wyniki sprawdzianow
    if req.examResults:
        lines.append(f"\n=== WYNIKI SPRAWDZIANOW ===")
        for r in req.examResults[-10:]:
            level = r.get('level', 2)
            lines.append(f"- {r.get('subject','inne')}: '{r.get('topic','')}' -> {rating_map.get(level, '?')}")

    # Chat
    if req.chatHistory:
        lines.append(f"\n=== TEMATY CZATU ({len(req.chatHistory)}) ===")
        for c in req.chatHistory[-15:]:
            lines.append(f"- '{c.get('title','')}'")

    # Plan nauki
    if req.lessonProgress:
        lines.append(f"\n=== PLAN NAUKI — UKONCZONE DNI ({len(req.lessonProgress)}) ===")
        for l in req.lessonProgress[-10:]:
            tasks = l.get('tasks', [])
            tasks_str = ', '.join(tasks[:2]) if tasks else ''
            lines.append(f"- {l.get('subject','inne')}: Dzien {l.get('dayNum',1)} — {tasks_str}")

    return '\n'.join(lines) if lines else "Brak danych"


@router.get("/health")
async def brain_health():
    return {"status": "ok", "service": "eduvia-brain"}
