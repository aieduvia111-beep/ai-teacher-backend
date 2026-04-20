"""
🧠 EDUVIA BRAIN API
Analizuje dane użytkownika z Firebase i zwraca mapę wiedzy
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI
from typing import List, Optional, Dict, Any
import json
import math
from collections import defaultdict
from app.config import settings

router = APIRouter(prefix="/api/v1/brain", tags=["brain"])
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# ── MODELE ───────────────────────────────────────────────────────────────────

class BrainRequest(BaseModel):
    uid: str
    quizHistory: Optional[List[Dict[str, Any]]] = []
    notesHistory: Optional[List[Dict[str, Any]]] = []
    understandingHistory: Optional[List[Dict[str, Any]]] = []
    examHistory: Optional[List[Dict[str, Any]]] = []
    examResults: Optional[List[Dict[str, Any]]] = []
    chatHistory: Optional[List[Dict[str, Any]]] = []
    lessonProgress: Optional[List[Dict[str, Any]]] = []


class PredictRequest(BaseModel):
    uid: str
    exam_topic: str        # np. "Fotosynteza"
    exam_subject: str      # np. "Biologia"
    quizHistory: Optional[List[Dict[str, Any]]] = []
    understandingHistory: Optional[List[Dict[str, Any]]] = []
    examResults: Optional[List[Dict[str, Any]]] = []


# ── BRAIN SCORE & LEVEL ──────────────────────────────────────────────────────

LEVELS = [
    (0,    1,  "Nowicjusz",        "gray"),
    (50,   2,  "Uczen",            "gray"),
    (100,  3,  "Badacz",           "blue"),
    (180,  4,  "Odkrywca",         "blue"),
    (280,  5,  "Mysliciel",        "purple"),
    (400,  6,  "Analityk",         "purple"),
    (550,  7,  "Ekspert",          "purple"),
    (720,  8,  "Mistrz",           "gold"),
    (900,  9,  "Geniusz",          "gold"),
    (1100, 10, "Wizjoner",         "gold"),
    (1300, 11, "Legenda",          "rainbow"),
    (1500, 12, "Fenomen",          "rainbow"),
    (1700, 13, "Tytan Wiedzy",     "rainbow"),
    (1850, 14, "Absolutny Mistrz", "rainbow"),
    (1950, 15, "BRAIN GOD",        "rainbow"),
]

def _calc_brain_score(req: BrainRequest) -> dict:
    """
    Brain Score = avg_quiz_pct * log2(quizy+1) * activity_bonus
    Level 1-15 na podstawie score 0-2000
    """
    scores = []
    for q in (req.quizHistory or []):
        correct = q.get('correct', 0)
        total = q.get('total', 1) or 1
        pct = q.get('pct') or round(correct / total * 100)
        scores.append(pct)

    if not scores:
        return {
            "brain_score": 0,
            "brain_level": 1,
            "brain_level_name": "Nowicjusz",
            "brain_level_color": "gray",
            "score_to_next": 50,
            "next_threshold": 50
        }

    avg_pct = sum(scores) / len(scores)
    quiz_count = len(scores)
    notes_count = len(req.notesHistory or [])
    exam_count = len(req.examHistory or [])

    raw = avg_pct * math.log(quiz_count + 1, 2) * (1 + notes_count * 0.05 + exam_count * 0.1)
    brain_score = min(2000, round(raw))

    current = LEVELS[0]
    next_threshold = LEVELS[1][0]
    for i, entry in enumerate(LEVELS):
        if brain_score >= entry[0]:
            current = entry
            next_threshold = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else 2000

    return {
        "brain_score": brain_score,
        "brain_level": current[1],
        "brain_level_name": current[2],
        "brain_level_color": current[3],
        "score_to_next": max(0, next_threshold - brain_score),
        "next_threshold": next_threshold
    }


# ── ENDPOINT: ANALYZE ────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_brain(req: BrainRequest):
    """Analizuje wszystkie dane użytkownika i zwraca mapę wiedzy + Brain Level"""
    try:
        has_data = (
            len(req.quizHistory or []) > 0 or
            len(req.notesHistory or []) > 0 or
            len(req.understandingHistory or []) > 0 or
            len(req.examHistory or []) > 0 or
            len(req.lessonProgress or []) > 0
        )

        # Zawsze oblicz Brain Score (nawet bez danych)
        level_data = _calc_brain_score(req)

        if not has_data:
            return {
                "success": True,
                "overall_pct": 0,
                "subjects": [],
                "holes": [],
                "summary": "Zacznij robic quizy i notatki, a Brain przeanalizuje Twoja wiedze!",
                "no_data": True,
                **level_data
            }

        data_summary = _build_data_summary(req)

        prompt = f"""Jestes Eduvia Brain — AI analizujacym wiedze ucznia na podstawie jego aktywnosci w aplikacji edukacyjnej.

Dane ucznia:
{data_summary}

Odpowiedz TYLKO w formacie JSON (bez markdown):
{{
  "overall_pct": liczba 0-100,
  "subjects": [
    {{
      "name": "Matematyka",
      "pct": 75,
      "color": "green|yellow|red",
      "icon": "emoji pasujacy do przedmiotu",
      "quizzes_done": 3,
      "avg_score": 72,
      "status": "krotki komentarz 1 zdanie",
      "trend": "up|down|stable"
    }}
  ],
  "holes": [
    {{
      "subject": "Historia",
      "topic": "Potop Szwedzki",
      "severity": "high|medium|low",
      "reason": "krotkie wyjasnienie",
      "fix_time_min": 5
    }}
  ],
  "summary": "1-2 zdania o stanie wiedzy ucznia",
  "strongest_subject": "Biologia",
  "weakest_subject": "Historia",
  "weekly_trend": "improving|declining|stable"
}}

ZASADY:
- color green gdy pct>=70, yellow gdy 40-69, red gdy <40
- holes MUSI zawierac KAZDY temat gdzie "Bledy w ostatnim" > 0 — nie pomijaj zadnego tematu z bledami
- holes max 5, tylko konkretne tematy
- severity high gdy bledy >=1 raz lub ocena slabo (nawet 1 quiz wystarczy!), medium gdy pct<50%, low gdy ocena ujdzie
- WAZNE: nawet 1 quiz z bledami to wystarczy zeby temat trafil do holes — nie czekaj na wiele quizow
- KLUCZOWE: jesli pytanie jest w "Naprawione" — znaczy ze uczen juz je opanowal — ZMNIEJSZ severity lub usun z holes
- Jesli wszystkie bledy z danego tematu sa w "Naprawione" — USUN ten temat z holes calkowicie
- Jesli polowa bledow naprawiona — zmien severity z high na medium lub medium na low
- BARDZO WAZNE: patrz na "Ostatni quiz" i "Bledy w ostatnim"
- Jesli "Bledy w ostatnim" = 0 — uczen naprawil ten temat — NIE dodawaj do holes lub USUN z holes
- Jesli "Ostatni quiz" >= 90% — przedmiot jest opanowany, NIE dodawaj do holes
- Jesli "Bledy w ostatnim" > 0 — dodaj do holes z odpowiednim severity
- To jest NAJWAZNIEJSZA zasada — ostatni wynik ma priorytet nad srednia
- Uwzglednij WSZYSTKIE zrodla: quizy, notatki, ankiety, sprawdziany, plan nauki
- Podaj TYLKO przedmioty ktore uczen faktycznie robil"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        return {
            "success": True,
            **result,
            **level_data
        }

    except Exception as e:
        print(f"Brain analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── ENDPOINT: PREDICT GRADE ──────────────────────────────────────────────────

@router.post("/predict")
async def predict_grade(req: PredictRequest):
    """
    Uczeń wpisuje temat jutrzejszego sprawdzianu.
    AI analizuje jego historię z tego tematu i przewiduje ocenę 1-6
    + mówi co powtórzyć.
    """
    try:
        topic = req.exam_topic.strip()
        subject = req.exam_subject.strip()
        topic_low = topic.lower()
        subject_low = subject.lower()

        # Zbierz dane pasujące do tematu/przedmiotu
        relevant_quizzes = []
        for q in (req.quizHistory or []):
            q_subject = (q.get('subject', '')).lower()
            q_title = (q.get('title', '')).lower()
            if subject_low in q_subject or topic_low in q_title or q_subject in subject_low:
                correct = q.get('correct', 0)
                total = q.get('total', 1) or 1
                pct = q.get('pct') or round(correct / total * 100)
                wrong = [w.get('question', '')[:60] for w in (q.get('wrongQuestions') or [])][:3]
                relevant_quizzes.append({"pct": pct, "title": q.get('title',''), "wrong": wrong})

        relevant_understanding = []
        for u in (req.understandingHistory or []):
            u_subject = (u.get('subject', '')).lower()
            u_topic = (u.get('topic', '')).lower()
            if subject_low in u_subject or topic_low in u_topic:
                relevant_understanding.append({
                    "topic": u.get('topic',''),
                    "level": u.get('level', 2)
                })

        relevant_exams = []
        for e in (req.examResults or []):
            e_subject = (e.get('subject', '')).lower()
            e_topic = (e.get('topic', '')).lower()
            if subject_low in e_subject or topic_low in e_topic:
                relevant_exams.append({
                    "topic": e.get('topic',''),
                    "level": e.get('level', 2)
                })

        # Zbuduj kontekst dla AI
        context_lines = [f"Uczen ma sprawdzian z: {subject} — temat: {topic}"]

        if relevant_quizzes:
            avg_quiz = round(sum(q['pct'] for q in relevant_quizzes) / len(relevant_quizzes))
            all_wrong = []
            for q in relevant_quizzes:
                all_wrong.extend(q['wrong'])
            wrong_uniq = list(dict.fromkeys(all_wrong))[:5]
            context_lines.append(f"Quizy z tego przedmiotu/tematu: {len(relevant_quizzes)} quizow, avg {avg_quiz}%")
            if wrong_uniq:
                context_lines.append(f"Najczestsze bledy: {' | '.join(wrong_uniq)}")
        else:
            context_lines.append("Brak quizow z tego tematu/przedmiotu")

        if relevant_understanding:
            avg_und = sum(u['level'] for u in relevant_understanding) / len(relevant_understanding)
            weak_topics = [u['topic'] for u in relevant_understanding if u['level'] <= 2][:3]
            context_lines.append(f"Oceny zrozumienia z tego przedmiotu: avg {avg_und:.1f}/4")
            if weak_topics:
                context_lines.append(f"Tematy gdzie nie rozumie: {', '.join(weak_topics)}")

        if relevant_exams:
            avg_exam = sum(e['level'] for e in relevant_exams) / len(relevant_exams)
            failed = [e['topic'] for e in relevant_exams if e['level'] == 1][:3]
            context_lines.append(f"Poprzednie sprawdziany z tego przedmiotu: avg poziom {avg_exam:.1f}/4")
            if failed:
                context_lines.append(f"Oblane tematy: {', '.join(failed)}")

        context = '\n'.join(context_lines)

        prompt = f"""Jestes Eduvia Brain — AI przewidujacym wynik ucznia na sprawdzianie.

{context}

Na podstawie tych danych przewidz jaka ocene dostanie uczen na sprawdzianie z "{topic}" ({subject}).
Skala ocen polska: 1 (niedostateczny), 2 (dopuszczajacy), 3 (dostateczny), 4 (dobry), 5 (bardzo dobry), 6 (celujacy).

Odpowiedz TYLKO w formacie JSON:
{{
  "predicted_grade": liczba 1-6,
  "predicted_grade_label": "np. 3+ lub 4-",
  "confidence": "wysoka|srednia|niska",
  "confidence_reason": "1 zdanie dlaczego taka pewnosc",
  "analysis": "2-3 zdania analizy - co uczen umie a czego nie",
  "topics_to_review": ["temat1", "temat2", "temat3"],
  "topics_to_review_reason": "1 zdanie dlaczego te tematy",
  "encouragement": "1 krotkie zdanie motywacyjne dla ucznia",
  "can_improve": true/false
}}

ZASADY:
- Bazuj TYLKO na danych ktore masz, nie wymyslaj
- Jesli brak danych z tego tematu — confidence "niska", przewiduj srednio (3)
- topics_to_review to konkretne zagadnienia z tematu sprawdzianu ktore wydaja sie slabe
- Bądź szczery ale motywujacy"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        return {
            "success": True,
            "topic": topic,
            "subject": subject,
            "data_found": len(relevant_quizzes) > 0 or len(relevant_understanding) > 0,
            **result
        }

    except Exception as e:
        print(f"Brain predict error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── BUDOWANIE PODSUMOWANIA ────────────────────────────────────────────────────

def _build_data_summary(req: BrainRequest) -> str:
    """Buduje zagregowane podsumowanie danych dla OpenAI.
    Agreguje per przedmiot — prompt ~10x krotszy niezaleznie od liczby wpisow.
    """
    lines = []

    # QUIZY
    if req.quizHistory:
        # Sortuj po czasie — najnowsze pierwsze
        sorted_quizzes = sorted(req.quizHistory, key=lambda x: x.get('timestamp', ''), reverse=True)

        subj_quiz = defaultdict(lambda: {
            'scores': [], 'wrong': [], 'wrong_valid': 0,
            'last_pct': 0, 'last_wrong_count': 0, 'last_timestamp': ''
        })

        for q in sorted_quizzes:
            s = q.get('subject', 'inne')
            correct = q.get('correct', 0)
            total = q.get('total', 1) or 1
            pct = q.get('pct') or round(correct / total * 100)
            subj_quiz[s]['scores'].append(pct)
            ts = q.get('timestamp', '')

            wrong_qs = q.get('wrongQuestions') or []
            valid_wrong = [w for w in wrong_qs if w.get('options') and len(w.get('options', [])) >= 2]

            for w in valid_wrong[:3]:
                subj_quiz[s]['wrong'].append(w.get('question', '')[:50])
            if valid_wrong:
                subj_quiz[s]['wrong_valid'] += len(valid_wrong)

            # Zapisz dane ostatniego (najnowszego) quizu per przedmiot
            if ts > subj_quiz[s]['last_timestamp']:
                subj_quiz[s]['last_pct'] = pct
                subj_quiz[s]['last_wrong_count'] = len(valid_wrong)
                subj_quiz[s]['last_timestamp'] = ts

        lines.append(f"\n=== QUIZY (lacznie {len(req.quizHistory)}) ===")
        for subj, data in subj_quiz.items():
            avg = round(sum(data['scores']) / len(data['scores']))
            wrong_uniq = list(dict.fromkeys(data['wrong']))[:3]
            wrong_str = ' | '.join(wrong_uniq) if wrong_uniq else 'brak'
            scores = data['scores']
            trend = ''
            if len(scores) >= 6:
                old_avg = sum(scores[-6:-3]) / 3
                new_avg = sum(scores[-3:]) / 3
                trend = ' [rosnie]' if new_avg > old_avg + 5 else (' [spada]' if new_avg < old_avg - 5 else ' [stabilny]')
            last_pct = data['last_pct']
            last_wrong = data['last_wrong_count']
            lines.append(f"- {subj}: {len(scores)} quizow, avg {avg}%{trend} | Ostatni quiz: {last_pct}% | Bledy w ostatnim: {last_wrong} | Przykladowe bledy: {wrong_str}")

    # NOTATKI
    if req.notesHistory:
        subj_notes = defaultdict(list)
        for n in req.notesHistory:
            subj_notes[n.get('subject', 'inne')].append(n.get('topic', ''))
        lines.append(f"\n=== NOTATKI (lacznie {len(req.notesHistory)}) ===")
        for subj, topics in subj_notes.items():
            lines.append(f"- {subj}: {len(topics)} notatek | Tematy: {', '.join(topics[-3:])}")

    # ANKIETY
    if req.understandingHistory:
        subj_und = defaultdict(list)
        for u in req.understandingHistory:
            subj_und[u.get('subject', 'inne')].append({'topic': u.get('topic',''), 'level': u.get('level', 2)})
        lines.append(f"\n=== OCENY ZROZUMIENIA (lacznie {len(req.understandingHistory)}) ===")
        for subj, items in subj_und.items():
            avg_level = sum(i['level'] for i in items) / len(items)
            weak = [i['topic'] for i in items if i['level'] <= 2][:3]
            lines.append(f"- {subj}: avg {avg_level:.1f}/4 | Slabe: {', '.join(weak) if weak else 'brak'}")

    # SPRAWDZIANY
    if req.examHistory:
        subj_exam = defaultdict(list)
        for e in req.examHistory:
            subj_exam[e.get('subject', 'inne')].append(e.get('topic', ''))
        lines.append(f"\n=== SPRAWDZIANY (lacznie {len(req.examHistory)}) ===")
        for subj, topics in subj_exam.items():
            lines.append(f"- {subj}: {len(topics)} sprawdzianow | Tematy: {', '.join(topics[-3:])}")

    # WYNIKI SPRAWDZIANOW
    if req.examResults:
        subj_res = defaultdict(list)
        for r in req.examResults:
            subj_res[r.get('subject', 'inne')].append({'topic': r.get('topic',''), 'level': r.get('level', 2)})
        lines.append(f"\n=== WYNIKI SPRAWDZIANOW (lacznie {len(req.examResults)}) ===")
        for subj, items in subj_res.items():
            avg_level = sum(i['level'] for i in items) / len(items)
            failed = [i['topic'] for i in items if i['level'] == 1][:3]
            lines.append(f"- {subj}: avg {avg_level:.1f}/4 | Oblane: {', '.join(failed) if failed else 'brak'}")

    # CHAT
    if req.chatHistory:
        titles = list(dict.fromkeys(c.get('title', '') for c in req.chatHistory))[:10]
        lines.append(f"\n=== TEMATY CZATU ({len(req.chatHistory)}) ===")
        lines.append(f"- {', '.join(titles)}")

    # PLAN NAUKI
    if req.lessonProgress:
        subj_plan = defaultdict(int)
        for l in req.lessonProgress:
            subj_plan[l.get('subject', 'inne')] += 1
        lines.append(f"\n=== PLAN NAUKI ({len(req.lessonProgress)} dni) ===")
        for subj, days in subj_plan.items():
            lines.append(f"- {subj}: {days} dni ukonczonych")

    return '\n'.join(lines) if lines else "Brak danych"


@router.get("/health")
async def brain_health():
    return {"status": "ok", "service": "eduvia-brain"}
