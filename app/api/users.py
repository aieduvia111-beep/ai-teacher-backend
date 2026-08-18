"""USERS API - profil ucznia (ankieta onboardingowa: klasa, przedmiot, data egzaminu)."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..firebase_auth import get_current_app_user
from ..level_config import is_known_level, label_for_level
from ..models import User

router = APIRouter(prefix="/users", tags=["Users"])


class OnboardingRequest(BaseModel):
    education_level: str
    favorite_subject: Optional[str] = None
    exam_date: Optional[str] = None  # "YYYY-MM-DD", opcjonalne - ekran 3 mozna pominac


def _profile_dict(user: User) -> dict:
    return {
        "email": user.email,
        "is_premium": bool(user.is_premium),
        "education_level": user.education_level,
        "education_level_label": label_for_level(user.education_level) if user.education_level else None,
        "favorite_subject": user.favorite_subject,
        "exam_date": user.exam_date.date().isoformat() if user.exam_date else None,
        "onboarding_completed": bool(user.onboarding_completed),
    }


@router.get("/me")
def get_me(user: User = Depends(get_current_app_user)):
    """Zwraca profil ucznia - w tym dane z ankiety onboardingowej, jesli juz ja wypelnil."""
    return {"success": True, "profile": _profile_dict(user)}


@router.post("/onboarding")
def save_onboarding(
    req: OnboardingRequest,
    user: User = Depends(get_current_app_user),
    db: Session = Depends(get_db),
):
    """Zapisuje odpowiedzi z ankiety onboardingowej przy koncie usera."""
    if not is_known_level(req.education_level):
        return {"success": False, "error": f"Nieznany poziom: {req.education_level}"}

    user.education_level = req.education_level
    if req.favorite_subject:
        user.favorite_subject = req.favorite_subject.strip()[:50]
    if req.exam_date:
        try:
            user.exam_date = datetime.fromisoformat(req.exam_date)
        except ValueError:
            return {"success": False, "error": "Nieprawidlowy format daty (oczekiwano YYYY-MM-DD)."}
    user.onboarding_completed = True

    db.commit()
    db.refresh(user)
    return {"success": True, "profile": _profile_dict(user)}
