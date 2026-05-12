from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json

router = APIRouter()

# Prosta baza subskrypcji w pamięci
push_subscriptions = {}

class PushSubscription(BaseModel):
    subscription: dict
    uid: Optional[str] = None

class PushMessage(BaseModel):
    title: str = "Eduvia AI"
    body: str = "Czas na naukę! 🎓"
    uid: Optional[str] = None

@router.post("/api/push/subscribe")
async def push_subscribe(data: PushSubscription):
    if data.uid and data.subscription:
        push_subscriptions[data.uid] = data.subscription
    return {"ok": True}

@router.post("/api/push/send")
async def push_send(data: PushMessage):
    try:
        from pywebpush import webpush, WebPushException
        VAPID_PRIVATE = "-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgNiXYtLA7sb2oAVYI
JUa8XIjdyIbJkD+jYC4g55QI+/GhRANCAASuaDAZtyY3GrW1tOWKovUvRQ1xIw8G
Z0cVOB25tqpheyUi7Wigl7x2d//ndS7Eg812kcp6/zpE51jjDVmTUli8
-----END PRIVATE KEY-----"
        VAPID_EMAIL = "mailto:aieduvia111@gmail.com"
        targets = [push_subscriptions[data.uid]] if data.uid and data.uid in push_subscriptions else list(push_subscriptions.values())
        sent = 0
        for sub in targets:
            try:
                webpush(
                    subscription_info=sub,
                    data=json.dumps({"title": data.title, "body": data.body}),
                    vapid_private_key=VAPID_PRIVATE,
                    vapid_claims={"sub": VAPID_EMAIL}
                )
                sent += 1
            except Exception as e:
                print(f"Push error: {e}")
        return {"ok": True, "sent": sent}
    except ImportError:
        return {"ok": False, "error": "pywebpush not installed"}

# ═══ DAILY SCHEDULER ═══
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

def send_daily_reminder():
    """Wysyła codzienne powiadomienie o 18:00"""
    from pywebpush import webpush, WebPushException
    import json
    
    messages = [
        ("📚 Czas na naukę!", "Twój streak czeka — zaloguj się i ucz się z AI!"),
        ("🧠 Quiz czas!", "Sprawdź swoją wiedzę — wygeneruj quiz w 10 sekund!"),
        ("🎓 Eduvia czeka!", "Nie przerywaj passy nauki. Ucz się dziś!"),
        ("⚡ Zdobądź XP!", "Rozwiąż quiz i awansuj na wyższy poziom!"),
        ("📝 Nowe notatki?", "Wrzuć zdjęcie i AI zrobi notatki w PDF!"),
    ]
    
    import random
    title, body = random.choice(messages)
    
    VAPID_PRIVATE = open('/home/teacheraipro/ai-teacher-backend/vapid_private.pem').read()
    VAPID_EMAIL = "mailto:aieduvia111@gmail.com"
    
    sent = 0
    for uid, sub in push_subscriptions.items():
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=VAPID_PRIVATE,
                vapid_claims={"sub": VAPID_EMAIL}
            )
            sent += 1
        except Exception as e:
            print(f"Push error {uid}: {e}")
    
    print(f"✅ Wysłano {sent} powiadomień")

# Uruchom scheduler
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Warsaw'))
scheduler.add_job(send_daily_reminder, CronTrigger(hour=18, minute=0))
scheduler.start()

# KEEP ALIVE - ping co 10 minut aby Render nie zasypial
import httpx
async def keepalive_ping():
    try:
        async with httpx.AsyncClient() as client:
            await client.get('https://ai-teacher-backend-1.onrender.com/health', timeout=10)
            print("Keep-alive OK")
    except Exception as e:
        print(f"Keep-alive error: {e}")

scheduler.add_job(keepalive_ping, 'interval', minutes=5)

print("✅ Scheduler powiadomień uruchomiony - codziennie o 18:00")
