"""Wspolna weryfikacja tokenu logowania Firebase dla chronionych endpointow."""
import base64
import json
import os

import firebase_admin
from fastapi import Depends, Header, HTTPException
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .usage_limits import LIMIT_MESSAGES, check_and_use_limit


def _ensure_firebase_app():
    if firebase_admin._apps:
        return
    sa_b64 = os.environ.get("FIREBASE_KEY_B64")
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if sa_b64:
        cred = credentials.Certificate(json.loads(base64.b64decode(sa_b64).decode("utf-8")))
    elif sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
    else:
        cred = credentials.Certificate(
            os.environ.get(
                "FIREBASE_SERVICE_ACCOUNT_PATH",
                "app/eduvia-c69bc-firebase-adminsdk-fbsvc-be39724e72.json",
            )
        )
    firebase_admin.initialize_app(cred)


def get_verified_firebase_user(authorization: str = Header(None)) -> dict:
    """Dependency FastAPI: weryfikuje token Firebase z naglowka Authorization.

    Zwraca zdekodowany token (m.in. 'uid', 'email') albo rzuca 401.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Brak tokenu autoryzacji")

    token = authorization.split(" ", 1)[1].strip()
    _ensure_firebase_app()

    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Nieprawidlowy lub wygasly token logowania")

    return decoded


def get_current_app_user(
    firebase_user: dict = Depends(get_verified_firebase_user),
    db: Session = Depends(get_db),
) -> User:
    """Dependency FastAPI: zwraca (lub tworzy) rekord User w SQL dla zweryfikowanego
    uzytkownika Firebase. Uzywane tam, gdzie trzeba sledzic dzienne limity uzycia."""
    uid = firebase_user["uid"]
    user = db.query(User).filter(User.firebase_uid == uid).first()
    if not user:
        email = firebase_user.get("email") or f"{uid}@firebase.local"
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.firebase_uid = uid
        else:
            user = User(firebase_uid=uid, email=email, is_premium=False)
            db.add(user)
        db.commit()
        db.refresh(user)
    return user


def require_feature_limit(feature: str):
    """Zwraca dependency FastAPI, ktora wymaga logowania I sprawdza dzienny limit
    darmowego planu dla danej funkcji (np. 'chat', 'quiz', 'notes', 'exam')."""

    def _dependency(
        user: User = Depends(get_current_app_user),
        db: Session = Depends(get_db),
    ) -> User:
        allowed, _remaining = check_and_use_limit(user, db, feature)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=LIMIT_MESSAGES.get(feature, "Wykorzystales dzisiejszy darmowy limit."),
            )
        return user

    return _dependency
