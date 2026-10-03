"""POWTORKA DNIA (03.10.2026, user: "zrobmy aby ludzie bez kitu poprawiali oceny").

Kazde zle odpowiedziane pytanie z quizu trafia tu i wraca w rosnacych odstepach
(1 -> 3 -> 7 -> 14 dni), az uczen odpowie na nie poprawnie 4 razy z rzedu
("opanowane"). Zle odpowiedzi cofaja pytanie do poczatku drabinki. To zwykla
powtorka rozlozona w czasie (spaced repetition) - najlepiej przebadany sposob
na zapamietywanie. ZERO kosztu API: pytania sa juz wygenerowane i zweryfikowane,
tylko wracaja. Dane sa na koncie (Firebase UID), wiec dzialaja na kazdym urzadzeniu.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..firebase_auth import get_current_app_user
from ..models import ReviewItem, User

router = APIRouter(prefix="/api/v1/review", tags=["review"])

# Po ilu dniach wraca pytanie po N-tej poprawnej odpowiedzi z rzedu (N=0 to po bledzie).
INTERVALS_DAYS = [1, 3, 7, 14]
MASTERED_AFTER = len(INTERVALS_DAYS)  # 4 poprawne z rzedu = opanowane
MAX_OPEN_PER_USER = 300
MAX_ITEMS_PER_REQUEST = 30


class ReviewAddItem(BaseModel):
    question: str
    options: List[str]
    correct: int
    explanation: Optional[str] = ""
    subject: Optional[str] = None
    topic: Optional[str] = None


class ReviewAddRequest(BaseModel):
    items: List[ReviewAddItem]


class ReviewAnswerRequest(BaseModel):
    id: int
    correct: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _qhash(question: str) -> str:
    norm = re.sub(r"\s+", " ", (question or "").strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _valid(item: ReviewAddItem) -> bool:
    return (
        bool((item.question or "").strip())
        and 2 <= len(item.options) <= 6
        and 0 <= item.correct < len(item.options)
        and len((item.question or "")) <= 2000
    )


def _schedule_after_answer(item: ReviewItem, correct: bool) -> None:
    if correct:
        item.times_right = (item.times_right or 0) + 1
        item.streak = (item.streak or 0) + 1
        if item.streak >= MASTERED_AFTER:
            item.mastered = True
            item.next_review = None
        else:
            item.next_review = _now() + timedelta(days=INTERVALS_DAYS[item.streak])
    else:
        item.times_wrong = (item.times_wrong or 0) + 1
        item.streak = 0
        item.mastered = False
        item.next_review = _now() + timedelta(days=INTERVALS_DAYS[0])


def _public(item: ReviewItem) -> dict:
    import json
    try:
        options = json.loads(item.options)
    except (TypeError, ValueError):
        options = []
    return {
        "id": item.id,
        "question": item.question,
        "options": options,
        "correct": item.correct,
        "explanation": item.explanation or "",
        "subject": item.subject,
        "topic": item.topic,
        "streak": item.streak or 0,
    }


def _due_query(db: Session, uid: str):
    return (
        db.query(ReviewItem)
        .filter(ReviewItem.user_id == uid, ReviewItem.mastered == False,  # noqa: E712
                ReviewItem.next_review != None, ReviewItem.next_review <= _now())  # noqa: E711
    )


@router.post("/add")
async def review_add(req: ReviewAddRequest, user: User = Depends(get_current_app_user), db: Session = Depends(get_db)):
    """Zapisuje zle odpowiedziane pytania (upsert po tresci pytania)."""
    import json
    uid = user.firebase_uid
    if not uid:
        raise HTTPException(status_code=400, detail="Brak identyfikatora konta")
    saved = 0
    open_count = (
        db.query(ReviewItem).filter(ReviewItem.user_id == uid, ReviewItem.mastered == False).count()  # noqa: E712
    )
    for it in req.items[:MAX_ITEMS_PER_REQUEST]:
        if not _valid(it):
            continue
        h = _qhash(it.question)
        row = db.query(ReviewItem).filter(ReviewItem.user_id == uid, ReviewItem.qhash == h).first()
        if row is None:
            if open_count >= MAX_OPEN_PER_USER:
                continue
            row = ReviewItem(
                user_id=uid, qhash=h, question=it.question.strip(), options=json.dumps(it.options),
                correct=it.correct, explanation=(it.explanation or "")[:2000],
                subject=(it.subject or None), topic=((it.topic or "")[:200] or None),
                streak=0, times_wrong=0, times_right=0, mastered=False,
            )
            db.add(row)
            open_count += 1
        elif row.mastered:
            open_count += 1
        # wrocil blad - zaczynamy drabinke od nowa (i odswiezamy tresc pytania)
        row.options = json.dumps(it.options)
        row.correct = it.correct
        row.explanation = (it.explanation or "")[:2000]
        _schedule_after_answer(row, correct=False)
        saved += 1
    db.commit()
    return {"success": True, "saved": saved}


@router.get("/due")
async def review_due(limit: int = 10, user: User = Depends(get_current_app_user), db: Session = Depends(get_db)):
    """Pytania do powtorki na dzis (najdawniej zalegle najpierw)."""
    limit = max(1, min(limit, 20))
    uid = user.firebase_uid or ""
    rows = _due_query(db, uid).order_by(ReviewItem.next_review.asc()).limit(limit).all()
    return {"success": True, "items": [_public(r) for r in rows]}


@router.get("/summary")
async def review_summary(user: User = Depends(get_current_app_user), db: Session = Depends(get_db)):
    uid = user.firebase_uid or ""
    due = _due_query(db, uid).count()
    open_total = db.query(ReviewItem).filter(ReviewItem.user_id == uid, ReviewItem.mastered == False).count()  # noqa: E712
    mastered = db.query(ReviewItem).filter(ReviewItem.user_id == uid, ReviewItem.mastered == True).count()  # noqa: E712
    return {"success": True, "due": due, "open": open_total, "mastered": mastered}


@router.post("/answer")
async def review_answer(req: ReviewAnswerRequest, user: User = Depends(get_current_app_user), db: Session = Depends(get_db)):
    row = db.query(ReviewItem).filter(ReviewItem.id == req.id, ReviewItem.user_id == (user.firebase_uid or "")).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Nie ma takiego pytania w powtorce")
    _schedule_after_answer(row, bool(req.correct))
    db.commit()
    return {"success": True, "mastered": bool(row.mastered), "streak": row.streak,
            "next_in_days": None if row.mastered or row.next_review is None
            else max(0, (_aware(row.next_review) - _now()).days + 1)}
