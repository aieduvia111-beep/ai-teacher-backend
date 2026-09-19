"""
POPROŚ RODZICA O PRO - link ktory dziecko wysyla rodzicowi (WhatsApp/SMS),
rodzic otwiera BEZ logowania i moze od razu kupic Pro dla dziecka.

Trzy endpointy:
- POST /api/v1/parent-share/create   (autoryzowany - dziecko generuje link)
- GET  /api/v1/parent-share/{token}  (publiczny - rodzic czyta stan dziecka)
- POST /api/v1/parent-share/{token}/checkout (publiczny - rodzic kupuje Pro)

Statystyki (streak/tydzien/XP) sa liczone NAPRAWDE z Firestore (te same
tablice historii co reszta apki zapisuje przez window._fbSave/_fbSaveQuiz),
nie zmyslane ani nie brane z niesynchronizowanego localStorage klienta -
"streak" w tym pliku to REKONSTRUKCJA z realnych znacznikow czasu w
historii, bo sam localStorage (eduvia_streak, patrz dashboard_FINAL.html)
nigdy nie jest zapisywany do Firestore i backend nie ma do niego dostepu.
Celowo BRAK "ulubionego przedmiotu" - zadna z tablic historii nie zapisuje
ustrukturyzowanego pola przedmiotu (tylko wolny tekst tytulu/tematu), wiec
zgadywanie go byloby zmyslaniem danych, nie realnym pomiarem.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..firebase_auth import get_verified_firebase_user
from ..services.stripe_service import _fdb
from ..services.blik_service import BlikService

router = APIRouter(prefix="/api/v1/parent-share", tags=["parent-share"])

# NOWE (user: "chce zeby wygladalo profesjonalnie") - link dla rodzica
# celowo NIE uzywa settings.FRONTEND_URL (surowy adres
# eduvia-backend-2.onrender.com, uzywany dzis do przekierowan Stripe) -
# eduviaai.pl to prawdziwa, wlasna domena usera (zweryfikowane: juz
# poprawnie wskazuje na ten sam backend, /static/pricing.html dziala
# na zywo pod ta domena). Osobna stala (nie nadpisujemy FRONTEND_URL
# globalnie), zeby nie ruszac juz dzialajacych przekierowan platnosci
# Stripe/BLIK gdzie indziej w kodzie - zmiana ograniczona TYLKO do tego,
# o co poprosil user.
PARENT_SHARE_DOMAIN = os.getenv("PARENT_SHARE_DOMAIN", "https://eduviaai.pl/static")

TOKEN_TTL_HOURS = 48
HISTORY_KEYS = [
    "quizHistory", "notesHistory", "examHistory",
    "lessonPlansHistory", "voiceHistory", "whiteboardHistory", "visionHistory",
]


def _get_student_stats(firebase_uid: str) -> dict:
    defaults = {"name": None, "xp": 0, "streak_days": 0, "week_activity": [False] * 7, "actions_this_week": 0}
    if not _fdb:
        return defaults
    try:
        doc = _fdb.collection("users").document(firebase_uid).get()
    except Exception as e:
        print(f"[parent-share] Firestore read blad: {e}")
        return defaults
    if not doc.exists:
        return defaults
    data = doc.to_dict() or {}

    all_days = set()
    actions_this_week = 0
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    for key in HISTORY_KEYS:
        for entry in (data.get(key) or []):
            ts = entry.get("timestamp") if isinstance(entry, dict) else None
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            all_days.add(dt.date())
            if dt >= week_ago:
                actions_this_week += 1

    today = now.date()
    streak = 0
    cursor = today if today in all_days else today - timedelta(days=1)
    while cursor in all_days:
        streak += 1
        cursor -= timedelta(days=1)

    week_activity = [(today - timedelta(days=(6 - i))) in all_days for i in range(7)]

    return {
        "name": data.get("name") or data.get("displayName") or None,
        "xp": int(data.get("xp") or 0),
        "streak_days": streak,
        "week_activity": week_activity,
        "actions_this_week": actions_this_week,
    }


@router.post("/create")
def create_share_link(
    db: Session = Depends(get_db),
    firebase_user: dict = Depends(get_verified_firebase_user),
):
    """Dziecko (zalogowane) generuje nowy link do wyslania rodzicowi.
    Kazde wywolanie naklada NOWY token - poprzedni link przestaje dzialac."""
    uid = firebase_user["uid"]
    email = firebase_user.get("email") or ""

    user = db.query(User).filter(User.firebase_uid == uid).first()
    if not user:
        user = User(firebase_uid=uid, email=email or f"{uid}@eduvia.local", is_premium=False)
        db.add(user)
        db.commit()
        db.refresh(user)

    token = secrets.token_urlsafe(24)
    user.parent_share_token = token
    user.parent_share_token_expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    db.commit()

    url = f"{PARENT_SHARE_DOMAIN}/rodzic.html?t={token}"
    return {"success": True, "token": token, "url": url, "expires_in_hours": TOKEN_TTL_HOURS}


def _resolve_token(token: str, db: Session) -> User:
    user = db.query(User).filter(User.parent_share_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Link nieprawidłowy lub już nieaktywny.")
    expires = user.parent_share_token_expires
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not expires or expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Ten link wygasł. Poproś dziecko o nowy.")
    return user


@router.get("/{token}")
def read_share_link(token: str, db: Session = Depends(get_db)):
    """Publiczny - rodzic otwiera link bez logowania. Zwraca TYLKO minimum
    potrzebne do pokazania strony (imię, XP, seria, aktywność tygodnia) -
    zero danych kontaktowych/wrazliwych ucznia."""
    user = _resolve_token(token, db)
    stats = _get_student_stats(user.firebase_uid)
    return {"success": True, **stats}


@router.post("/{token}/checkout")
def checkout_from_share_link(token: str, db: Session = Depends(get_db)):
    """Publiczny - rodzic kupuje Pro DLA DZIECKA spod tego linku, bez
    zakladania wlasnego konta. Uzywa DOKLADNIE tej samej sciezki co zwykly
    przycisk 'Kup Pro' w apce (karta+BLIK, ten sam webhook aktywuje
    is_premium na koncie dziecka) - zero osobnej, rownoleglej logiki
    platnosci do utrzymania."""
    user = _resolve_token(token, db)
    result = BlikService.create_setup_session(
        user_id=user.firebase_uid,
        email=user.email,
        db=db,
    )
    return result
