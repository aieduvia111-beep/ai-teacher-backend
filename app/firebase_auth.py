"""Wspolna weryfikacja tokenu logowania Firebase dla chronionych endpointow."""
import base64
import json
import os
import threading
import time

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
    sa_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
    if sa_b64:
        cred = credentials.Certificate(json.loads(base64.b64decode(sa_b64).decode("utf-8")))
    elif sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
    elif sa_path:
        cred = credentials.Certificate(sa_path)
    else:
        raise RuntimeError(
            "Brak danych logowania Firebase Admin - ustaw FIREBASE_KEY_B64 "
            "(zalecane) lub FIREBASE_SERVICE_ACCOUNT_JSON/FIREBASE_SERVICE_ACCOUNT_PATH."
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


# NAPRAWIONE (user, 29.08.2026, alarm kosztowy w OpenAI - "jakim cudem
# 660zl?"): darmowe konta maja dzienny limit (FREE_DAILY_LIMITS), ale
# konta PREMIUM nie maja ZADNEGO ograniczenia czestotliwosci - nic nie
# chronilo przed podwojnym kliknieciem "Generuj" (albo błędem UI), gdzie
# DRUGIE zadanie startuje zanim pierwsze sie skonczylo, dublujac PELNY
# koszt AI (partia + Warstwa 2.5 per pytanie + ewentualne rundy
# dogenerowania - realnie kilkadziesiat sekund/kilkanascie wywolan AI
# KAZDE). Prosty, w pamieci procesu bezpiecznik: TYLKO jedno aktywne
# zadanie generowania na (user, feature) naraz - drugie, jednoczesne
# zadanie dostaje jasny blad 429 zamiast po cichu dublowac koszt.
_inflight_generations: set = set()
_inflight_lock = threading.Lock()

# Tylko NAPRAWDE kosztowne funkcje generowania AI (partia + Warstwa 2.5
# PER PYTANIE + rundy dogenerowania) dostaja te ochrone - nie kazda
# funkcja z require_feature_limit (np. "chat" moze zasadnie miec kilka
# rownoleglych rozmow, to nie ten sam wzorzec kosztowy).
_CONCURRENCY_GUARDED_FEATURES = {"quiz", "exam"}

# NAPRAWIONE (ta sama luka co _inflight_generations wyzej, ale dla
# INNEGO wzorca naduzycia): blokada wspolbieznosci chroni TYLKO przed
# DWOMA jednoczesnymi zadaniami - nie chroni przed userem klikajacym
# "Generuj" 50 razy POD RZAD (kazde nastepne startuje dopiero PO
# zakonczeniu poprzedniego, wiec _inflight_generations nigdy tego nie
# zlapie). Dla kont premium (brak dziennego limitu w ogole) to byla
# CALKOWICIE otwarta furtka. Prosty, w pamieci procesu licznik w oknie
# kroczacym: max _RATE_LIMIT_MAX_PER_WINDOW zadan na (user, feature) w
# ostatnie _RATE_LIMIT_WINDOW_SECONDS - hojny (nie ma byc uciazliwy dla
# normalnego uzycia), ale eliminuje nieograniczone powtarzanie.
_RATE_LIMIT_WINDOW_SECONDS = 3600.0
_RATE_LIMIT_MAX_PER_WINDOW = 15
_rate_limit_history: dict = {}
_rate_limit_lock = threading.Lock()


def _check_rate_limit(user_id, feature: str) -> bool:
    """True = OK (zapisuje probe), False = przekroczono limit w oknie."""
    key = (user_id, feature)
    now = time.monotonic()
    with _rate_limit_lock:
        history = [t for t in _rate_limit_history.get(key, []) if now - t < _RATE_LIMIT_WINDOW_SECONDS]
        if len(history) >= _RATE_LIMIT_MAX_PER_WINDOW:
            _rate_limit_history[key] = history
            return False
        history.append(now)
        _rate_limit_history[key] = history
        return True


def require_feature_limit(feature: str):
    """Zwraca dependency FastAPI, ktora wymaga logowania I sprawdza dzienny
    limit darmowego planu dla danej funkcji (np. 'chat', 'quiz', 'notes',
    'exam'). Dla feature w _CONCURRENCY_GUARDED_FEATURES DODATKOWO:
    (1) blokuje DRUGIE, jednoczesne zadanie od TEGO SAMEGO usera - yield-
    dependency (FastAPI gwarantuje wykonanie kodu PO 'yield' w finally,
    NAWET przy wyjatku/timeout w samym endpoincie, wiec user nigdy nie
    zostaje trwale zablokowany, tylko na czas faktycznego trwania
    requestu); (2) ogranicza CZESTOTLIWOSC (_RATE_LIMIT_MAX_PER_WINDOW
    zadan / _RATE_LIMIT_WINDOW_SECONDS) - chroni konta premium (bez
    dziennego limitu) przed nieograniczonym powtarzaniem SEKWENCYJNYM
    (jedno po drugim, nie jednoczesnie - tego blokada wspolbieznosci NIE
    lapie)."""

    def _dependency(
        user: User = Depends(get_current_app_user),
        db: Session = Depends(get_db),
    ):
        allowed, _remaining = check_and_use_limit(user, db, feature)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=LIMIT_MESSAGES.get(feature, "Wykorzystales dzisiejszy darmowy limit."),
            )
        if feature in _CONCURRENCY_GUARDED_FEATURES and not _check_rate_limit(user.id, feature):
            raise HTTPException(
                status_code=429,
                detail=f"Zbyt wiele zadan generowania w krotkim czasie (max {_RATE_LIMIT_MAX_PER_WINDOW}/godzine). Sprobuj ponownie za chwile.",
            )
        if feature not in _CONCURRENCY_GUARDED_FEATURES:
            yield user
            return
        key = (user.id, feature)
        with _inflight_lock:
            if key in _inflight_generations:
                raise HTTPException(
                    status_code=429,
                    detail="Poprzednie generowanie jeszcze trwa - poczekaj na jego zakonczenie przed zamowieniem kolejnego.",
                )
            _inflight_generations.add(key)
        try:
            yield user
        finally:
            with _inflight_lock:
                _inflight_generations.discard(key)

    return _dependency
