import json
from datetime import date
from sqlalchemy.orm import Session
from .models import User

FREE_DAILY_LIMITS = {
    "chat": 5,
    "quiz": 3,
    "notes": 2,
    "exam": 1,
    "lesson": 2,
    # NAPRAWIONE (audyt "Kup Pro" CTA, sierpien 2026): "vision" byl juz
    # od dawna chroniony przez require_feature_limit("vision") w
    # app/api/vision.py, ale nie mial tu wpisu - w praktyce dostawal
    # domyslny fallback FREE_DAILY_LIMITS.get(feature, 5) = 5/dzien,
    # NIEZGODNY z tym, co frontend (static/vision.html LIMITS_FREE)
    # od dawna zaklada (2/dzien) i pokazuje w swoim kliencie pre-check.
    "vision": 2,
    # NAPRAWIONE: "voice" mial KOMPLETNY BRAK egzekwowania po stronie
    # serwera - /api/v1/voice/respond/stream (jedyny faktycznie uzywany
    # endpoint Voice AI, patrz app/api/voice.py) mial TYLKO
    # Depends(get_current_app_user) (kto to jest), bez
    # require_feature_limit (czy ma jeszcze uzycia). Klient mial ladny
    # popup (checkLimit/showLimitPopup, LIMITS_FREE.voice=3), ale to byl
    # WYLACZNIE kosmetyczny, lokalny licznik - kazdy user mogl go obejsc
    # czyszczac localStorage lub wolajac API bezposrednio, bez
    # jakiegokolwiek ograniczenia po stronie serwera.
    "voice": 3,
}

LIMIT_MESSAGES = {
    "chat": "Wykorzystałeś już dzisiejszy darmowy limit Chatu AI (5 wiadomości). Kup Pro i ucz się bez limitów!",
    "quiz": "Wykorzystałeś już dzisiejszy darmowy limit Quizów AI (3 quizy). Kup Pro i ucz się bez limitów!",
    "notes": "Wykorzystałeś już dzisiejszy darmowy limit Notatek AI (2 notatki). Kup Pro i ucz się bez limitów!",
    "exam": "Wykorzystałeś już dzisiejszy darmowy limit Sprawdzianów AI (1 sprawdzian). Kup Pro i ucz się bez limitów!",
    "lesson": "Wykorzystałeś już dzisiejszy darmowy limit Planu Nauki (2 plany). Kup Pro i ucz się bez limitów!",
    # NAPRAWIONE: bez tego wpisu 429 dla Vision zwracal generyczny fallback
    # "Wykorzystales dzisiejszy darmowy limit." (patrz require_feature_limit
    # w app/firebase_auth.py) - BEZ CTA do Pro, w przeciwienstwie do
    # WSZYSTKICH pozostalych funkcji.
    "vision": "Wykorzystałeś już dzisiejszy darmowy limit Vision AI (2 analizy). Kup Pro i ucz się bez limitów!",
    "voice": "Wykorzystałeś już dzisiejszy darmowy limit Voice AI (3 sesje). Kup Pro i ucz się bez limitów!",
}

def _load_usage(user: User) -> dict:
    if not user.daily_usage:
        return {}
    try:
        return json.loads(user.daily_usage)
    except (json.JSONDecodeError, TypeError):
        return {}

def check_and_use_limit(user: User, db: Session, feature: str):
    if user.is_premium:
        return True, None
    limit = FREE_DAILY_LIMITS.get(feature, 5)
    today = date.today().isoformat()
    usage = _load_usage(user)
    feature_data = usage.get(feature, {})
    if feature_data.get("date") != today:
        feature_data = {"date": today, "count": 0}
    used = feature_data.get("count", 0)
    remaining = limit - used
    if remaining <= 0:
        return False, 0
    feature_data["count"] = used + 1
    usage[feature] = feature_data
    user.daily_usage = json.dumps(usage)
    db.commit()
    return True, remaining - 1

def get_remaining(user: User, feature: str) -> dict:
    if user.is_premium:
        return {"is_premium": True, "unlimited": True}
    limit = FREE_DAILY_LIMITS.get(feature, 5)
    today = date.today().isoformat()
    usage = _load_usage(user)
    feature_data = usage.get(feature, {})
    used = feature_data.get("count", 0) if feature_data.get("date") == today else 0
    return {"is_premium": False, "unlimited": False, "used": used, "limit": limit, "remaining": max(limit - used, 0)}
