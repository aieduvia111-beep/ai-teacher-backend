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
}

LIMIT_MESSAGES = {
    "chat": "Wykorzystałeś już dzisiejszy darmowy limit Chatu AI (5 wiadomości). Kup Pro i ucz się bez limitów!",
    "quiz": "Wykorzystałeś już dzisiejszy darmowy limit Quizów AI (3 quizy). Kup Pro i ucz się bez limitów!",
    "notes": "Wykorzystałeś już dzisiejszy darmowy limit Notatek AI (2 notatki). Kup Pro i ucz się bez limitów!",
    "exam": "Wykorzystałeś już dzisiejszy darmowy limit Sprawdzianów AI (1 sprawdzian). Kup Pro i ucz się bez limitów!",
    "lesson": "Wykorzystałeś już dzisiejszy darmowy limit Planu Nauki (2 plany). Kup Pro i ucz się bez limitów!",
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
