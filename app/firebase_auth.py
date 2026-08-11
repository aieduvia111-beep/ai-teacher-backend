"""Wspolna weryfikacja tokenu logowania Firebase dla chronionych endpointow."""
import base64
import json
import os

import firebase_admin
from fastapi import Header, HTTPException
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials


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
