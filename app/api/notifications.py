from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

def get_firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        import json, base64
        sa_b64 = os.environ.get('FIREBASE_KEY_B64')
        sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
        if sa_b64:
            cred = credentials.Certificate(json.loads(base64.b64decode(sa_b64).decode('utf-8')))
        elif sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
        else:
            cred = credentials.Certificate('app/eduvia-c69bc-firebase-adminsdk-fbsvc-be39724e72.json')
        firebase_admin.initialize_app(cred)
    return firestore.client()

class FCMTokenRequest(BaseModel):
    uid: str
    fcm_token: str

@router.post("/save-token")
def save_fcm_token(req: FCMTokenRequest):
    """Zapisuje token urzadzenia (FCM) w Firestore, do wysylania powiadomien push"""
    db = get_firestore()
    user_ref = db.collection('users').document(req.uid)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="Uzytkownik nie znaleziony")
    user_ref.update({'fcmToken': req.fcm_token})
    return {"success": True}

def send_push_notification(uid: str, title: str, body: str):
    """Wysyla prawdziwe powiadomienie push do konkretnego usera (po jego uid)"""
    import firebase_admin
    from firebase_admin import messaging

    db = get_firestore()
    user_doc = db.collection('users').document(uid).get()
    if not user_doc.exists:
        return {"success": False, "error": "Uzytkownik nie znaleziony"}

    user_data = user_doc.to_dict()
    token = user_data.get('fcmToken')
    if not token:
        return {"success": False, "error": "Brak tokenu FCM dla tego uzytkownika"}

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token,
    )
    try:
        response = messaging.send(message)
        return {"success": True, "message_id": response}
    except Exception as e:
        return {"success": False, "error": str(e)}

class TestNotificationRequest(BaseModel):
    uid: str
    title: str = "Eduvia AI"
    body: str = "To testowe powiadomienie!"

@router.post("/send-test")
def send_test_notification(req: TestNotificationRequest):
    """Endpoint testowy - wysyla prawdziwe powiadomienie do wskazanego usera"""
    result = send_push_notification(req.uid, req.title, req.body)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ═══ CODZIENNE PRZYPOMNIENIE (18:00, Europe/Warsaw) ═══
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import random

_DAILY_MESSAGES = [
    ("📚 Czas na naukę!", "Twój streak czeka — zaloguj się i ucz się z AI!"),
    ("🧠 Quiz czas!", "Sprawdź swoją wiedzę — wygeneruj quiz w 10 sekund!"),
    ("🎓 Eduvia czeka!", "Nie przerywaj passy nauki. Ucz się dziś!"),
    ("⚡ Zdobądź XP!", "Rozwiąż quiz i awansuj na wyższy poziom!"),
    ("📝 Nowe notatki?", "Wrzuć zdjęcie i AI zrobi notatki w PDF!"),
]


def send_daily_reminder():
    """Wysyla codzienne powiadomienie do wszystkich userow z zapisanym tokenem FCM."""
    from firebase_admin import messaging

    title, body = random.choice(_DAILY_MESSAGES)

    try:
        db = get_firestore()
    except Exception as e:
        print(f"[daily reminder] Brak Firestore: {e}")
        return

    sent, failed = 0, 0
    for doc in db.collection('users').stream():
        token = (doc.to_dict() or {}).get('fcmToken')
        if not token:
            continue
        try:
            messaging.send(messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=token,
            ))
            sent += 1
        except Exception as e:
            failed += 1
            print(f"[daily reminder] Blad wysylki do {doc.id}: {e}")

    print(f"[daily reminder] Wyslano {sent}, bledy {failed}")


_scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Warsaw'))
_scheduler.add_job(send_daily_reminder, CronTrigger(hour=18, minute=0), id='daily_push_reminder', replace_existing=True)
_scheduler.start()
print("✅ Harmonogram powiadomien push uruchomiony - codziennie o 18:00")
