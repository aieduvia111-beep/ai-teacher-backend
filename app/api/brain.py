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

class QuizEntry(BaseModel):
    title: str
    subject: str = "inne"
    correct: int = 0
    total: int = 1
    pct: Optional[int] = None
    wrongQuestions: Optional[List[Dict]] = []
    timestamp: Optional[str] = None

class NoteEntry(BaseModel):
    topic: str
    subject: str = "inne"
    timestamp: Optional[str] = None

class UnderstandingEntry(BaseModel):
    topic: str
    subject: str = "inne"
    level: int = 2
    understood: bool = False
    timestamp: Optional[str] = None

class ExamEntry(BaseModel):
    topic: str
    subject: str = "inne"
    timestamp: Optional[str] = None

class ExamResult(BaseModel):
    topic: str
    subject: str = "inne"
    level: int = 2
    passed: bool = False
    timestamp: Optional[str] = None

class ChatEntry(BaseModel):
    title: str
    topic_en: Optional[str] = ""
    timestamp: Optional[str] = None

class LessonEntry(BaseModel):
    planTitle: str
    subject: str = "inne"
    dayNum: int = 1
    tasks: Optional[List[str]] = []
    date: Optional[str] = None

class BrainRequest(BaseModel):
    uid: str
    quizHistory: Optional[List[QuizEntry]] = []
    notesHistory: Optional[List[NoteEntry]] = []
    understandingHistory: Optional[List[UnderstandingEntry]] = []
    examHistory: Optional[List[ExamEntry]] = []
    examResults: Optional[List[ExamResult]] = []
    chatHistory: Optional[List[ChatEntry]] = []
    lessonProgress: Optional[List[LessonEntry]] = []


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

    # Quizy
    if req.quizHistory:
        lines.append(f"\n=== QUIZY ({len(req.quizHistory)} quizów) ===")
        for q in req.quizHistory[-20:]:  # max 20 ostatnich
            pct = q.pct or (round(q.correct / q.total * 100) if q.total > 0 else 0)
            wrong = [w.get('question', '')[:50] for w in (q.wrongQuestions or [])][:3]
            line = f"- {q.subject}: '{q.title}' — {pct}% ({q.correct}/{q.total})"
            if wrong:
                line += f" | Błędne: {', '.join(wrong)}"
            lines.append(line)

    # Notatki
    if req.notesHistory:
        lines.append(f"\n=== NOTATKI ({len(req.notesHistory)} notatek) ===")
        for n in req.notesHistory[-15:]:
            lines.append(f"- {n.subject}: '{n.topic}'")

    # Ankiety po notatkach
    if req.understandingHistory:
        lines.append(f"\n=== OCENY WIEDZY PO NOTATKACH ===")
        rating_map = {1: "😰 Nie rozumiem", 2: "😐 Trochę", 3: "😊 Rozumiem", 4: "🔥 Świetnie!"}
        for u in req.understandingHistory[-15:]:
            lines.append(f"- {u.subject}: '{u.topic}' → {rating_map.get(u.level, '?')}")

    # Sprawdziany
    if req.examHistory:
        lines.append(f"\n=== SPRAWDZIANY ({len(req.examHistory)} sprawdzianów) ===")
        for e in req.examHistory[-10:]:
            lines.append(f"- {e.subject}: '{e.topic}'")

    # Wyniki sprawdzianów
    if req.examResults:
        lines.append(f"\n=== WYNIKI SPRAWDZIANÓW ===")
        rating_map = {1: "😰 Słabo", 2: "😐 Ujdzie", 3: "😊 Dobrze", 4: "🔥 Świetnie!"}
        for r in req.examResults[-10:]:
            lines.append(f"- {r.subject}: '{r.topic}' → {rating_map.get(r.level, '?')}")

    # Chat
    if req.chatHistory:
        lines.append(f"\n=== TEMATY ROZMÓW Z AI ({len(req.chatHistory)} rozmów) ===")
        for c in req.chatHistory[-15:]:
            lines.append(f"- '{c.title}'")

    # Plan nauki
    if req.lessonProgress:
        lines.append(f"\n=== PLAN NAUKI — UKOŃCZONE DNI ({len(req.lessonProgress)} dni) ===")
        for l in req.lessonProgress[-10:]:
            tasks = ', '.join(l.tasks[:2]) if l.tasks else ''
            lines.append(f"- {l.subject}: Dzień {l.dayNum} — {tasks}")

    return '\n'.join(lines) if lines else "Brak danych"


@router.get("/health")
async def brain_health():
    return {"status": "ok", "service": "eduvia-brain"}
