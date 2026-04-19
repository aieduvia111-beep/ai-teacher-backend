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
    """Buduje zagregowane podsumowanie danych dla OpenAI.
    Zamiast listować każdy wpis osobno, agreguje per przedmiot
    — dzięki temu prompt jest ~10x krótszy niezależnie od liczby wpisów.
    """
    from collections import defaultdict
    lines = []
    rating_map = {1: "Nie rozumiem", 2: "Troche", 3: "Rozumiem", 4: "Swietnie"}

    # ── QUIZY — agregacja per przedmiot ──────────────────────────────────────
    if req.quizHistory:
        subj_quiz = defaultdict(lambda: {'scores': [], 'wrong': [], 'titles': []})
        for q in req.quizHistory:  # bierzemy WSZYSTKIE, ale agregujemy
            s = q.get('subject', 'inne')
            correct = q.get('correct', 0)
            total = q.get('total', 1) or 1
            pct = q.get('pct') or round(correct / total * 100)
            subj_quiz[s]['scores'].append(pct)
            subj_quiz[s]['titles'].append(q.get('title', '')[:30])
            for w in (q.get('wrongQuestions') or [])[:3]:
                subj_quiz[s]['wrong'].append(w.get('question', '')[:50])

        lines.append(f"\n=== QUIZY (łącznie {len(req.quizHistory)}, zagregowane per przedmiot) ===")
        for subj, data in subj_quiz.items():
            avg = round(sum(data['scores']) / len(data['scores']))
            # ostatnie 3 unikalne błędy
            wrong_uniq = list(dict.fromkeys(data['wrong']))[:3]
            wrong_str = ' | '.join(wrong_uniq) if wrong_uniq else 'brak'
            # trend: ostatnie 3 vs poprzednie 3
            scores = data['scores']
            trend = ''
            if len(scores) >= 6:
                old_avg = sum(scores[-6:-3]) / 3
                new_avg = sum(scores[-3:]) / 3
                trend = ' [TREND: rośnie]' if new_avg > old_avg + 5 else (' [TREND: spada]' if new_avg < old_avg - 5 else ' [TREND: stabilny]')
            lines.append(f"- {subj}: {len(scores)} quizów, avg {avg}%{trend} | Najczęstsze błędy: {wrong_str}")

    # ── NOTATKI — agregacja per przedmiot ────────────────────────────────────
    if req.notesHistory:
        subj_notes = defaultdict(list)
        for n in req.notesHistory:
            subj_notes[n.get('subject', 'inne')].append(n.get('topic', ''))
        lines.append(f"\n=== NOTATKI (łącznie {len(req.notesHistory)}) ===")
        for subj, topics in subj_notes.items():
            lines.append(f"- {subj}: {len(topics)} notatek | Tematy: {', '.join(topics[-3:])}")

    # ── ANKIETY PO NOTATKACH — agregacja per przedmiot ───────────────────────
    if req.understandingHistory:
        subj_und = defaultdict(list)
        for u in req.understandingHistory:
            subj_und[u.get('subject', 'inne')].append({
                'topic': u.get('topic', ''),
                'level': u.get('level', 2)
            })
        lines.append(f"\n=== OCENY ZROZUMIENIA (łącznie {len(req.understandingHistory)}) ===")
        for subj, items in subj_und.items():
            avg_level = sum(i['level'] for i in items) / len(items)
            # tematy z niskim zrozumieniem (level 1-2)
            weak = [i['topic'] for i in items if i['level'] <= 2][:3]
            weak_str = ', '.join(weak) if weak else 'brak'
            lines.append(f"- {subj}: avg zrozumienie {avg_level:.1f}/4 | Słabe tematy: {weak_str}")

    # ── SPRAWDZIANY — agregacja per przedmiot ────────────────────────────────
    if req.examHistory:
        subj_exam = defaultdict(list)
        for e in req.examHistory:
            subj_exam[e.get('subject', 'inne')].append(e.get('topic', ''))
        lines.append(f"\n=== SPRAWDZIANY (łącznie {len(req.examHistory)}) ===")
        for subj, topics in subj_exam.items():
            lines.append(f"- {subj}: {len(topics)} sprawdzianów | Tematy: {', '.join(topics[-3:])}")

    # ── WYNIKI SPRAWDZIANÓW — agregacja per przedmiot ────────────────────────
    if req.examResults:
        subj_res = defaultdict(list)
        for r in req.examResults:
            subj_res[r.get('subject', 'inne')].append({
                'topic': r.get('topic', ''),
                'level': r.get('level', 2)
            })
        lines.append(f"\n=== WYNIKI SPRAWDZIANÓW (łącznie {len(req.examResults)}) ===")
        for subj, items in subj_res.items():
            avg_level = sum(i['level'] for i in items) / len(items)
            # tematy zakończone słabo (level 1)
            failed = [i['topic'] for i in items if i['level'] == 1][:3]
            failed_str = ', '.join(failed) if failed else 'brak'
            lines.append(f"- {subj}: avg wynik {avg_level:.1f}/4 | Oblane tematy: {failed_str}")

    # ── CHAT — tylko unikalne tematy ─────────────────────────────────────────
    if req.chatHistory:
        titles = list(dict.fromkeys(c.get('title', '') for c in req.chatHistory))[:10]
        lines.append(f"\n=== TEMATY CZATU (łącznie {len(req.chatHistory)}, unikalne) ===")
        lines.append(f"- {', '.join(titles)}")

    # ── PLAN NAUKI — agregacja per przedmiot ─────────────────────────────────
    if req.lessonProgress:
        subj_plan = defaultdict(int)
        for l in req.lessonProgress:
            subj_plan[l.get('subject', 'inne')] += 1
        lines.append(f"\n=== PLAN NAUKI — UKOŃCZONE DNI (łącznie {len(req.lessonProgress)}) ===")
        for subj, days in subj_plan.items():
            lines.append(f"- {subj}: {days} dni ukończonych")

    return '\n'.join(lines) if lines else "Brak danych"


@router.get("/health")
async def brain_health():
    return {"status": "ok", "service": "eduvia-brain"}
