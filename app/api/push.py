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
