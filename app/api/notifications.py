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
        sa_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')
        if sa_b64:
            cred = credentials.Certificate(json.loads(base64.b64decode(sa_b64).decode('utf-8')))
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

# ═══ BLIK - codzienne pobieranie naleznych oplat (03:00, Europe/Warsaw) ═══
# NOWE (wrzesien 2026, BLIK recurring - patrz app/services/blik_service.py):
# BLIK nie ma obiektu Stripe Subscription, wiec MY jestesmy "robotem", ktory
# raz dziennie recznie zleca kazde nalezne obciazenie. Rejestrowane na TYM
# SAMYM, juz istniejacym _scheduler (nie druga instancja BackgroundScheduler -
# unikamy dwoch konkurujacych watkow). Inna godzina niz push (18:00), zeby
# logi billingowe nie mieszaly sie z marketingowymi. max_instances=1 - druga
# warstwa ochrony przed nakladajacymi sie uruchomieniami (pierwsza to
# blik_charge_in_progress w samej bazie).
def _run_blik_charge_sweep():
    from ..services.blik_service import charge_due_blik_subscriptions
    charge_due_blik_subscriptions()


_scheduler.add_job(_run_blik_charge_sweep, CronTrigger(hour=3, minute=0), id='blik_charge_sweep', replace_existing=True, max_instances=1)

# ═══ PRZYPOMNIENIE O PORZUCONYM CHECKOUCIE (co 30 min) ═══
# NOWE (23.09.2026, user: "musimy duzo dostawac subskrypcje"): real prod (22.09.2026) - 17
# checkoutow utworzonych jednego dnia, 0 dokonczonych, tylko 1 jawne anulowanie - reszta (16
# osob) po prostu zniknela w ciszy w trakcie platnosci na stronie Stripe (patrz funnel_events:
# checkout_created bez pozniejszego payment_success ani payment_cancelled). To juz "cieplejsi"
# ludzie niz nowy odwiedzajacy - jedno przypomnienie push moze odzyskac czesc z nich.
#
# Okno 1-24h po checkout_created (zbyt szybko = user moze byc wciaz w trakcie platnosci; po 24h
# sesja Stripe i tak juz wygasla - nowe przypomnienie nie mialoby dokad prowadzic). KAZDY user
# dostaje TYLKO JEDNO przypomnienie na dany checkout (wlasny event abandoned_checkout_notified w
# tej samej tabeli funnel_events, sprawdzany PRZED wyslaniem) - zadanie odpala sie co 30 min, ale
# nie zaleje tej samej osoby powiadomieniami. Pomija userow, ktorzy juz maja is_premium=True
# (zaplacili jakakolwiek droga, niekoniecznie z payment_success - np. odnowienie zlapane przez
# reconcile) - patrz identyczny duch co StripeService.reconcile_subscriptions kilka linii wyzej.
def _run_abandoned_checkout_reminder():
    from ..database import SessionLocal
    from ..models import FunnelEvent, User
    from datetime import datetime, timedelta
    db = SessionLocal()
    sent = skipped = 0
    try:
        window_start = datetime.utcnow() - timedelta(hours=24)
        window_end = datetime.utcnow() - timedelta(hours=1)
        candidates = (
            db.query(FunnelEvent)
            .filter(
                FunnelEvent.event == 'checkout_created',
                FunnelEvent.user_id.isnot(None),
                FunnelEvent.created_at >= window_start,
                FunnelEvent.created_at <= window_end,
            )
            .order_by(FunnelEvent.created_at.desc())
            .all()
        )
        seen_uids = set()
        for ev in candidates:
            uid = ev.user_id
            if uid in seen_uids:
                continue  # tylko najnowszy checkout danego usera w tym oknie
            seen_uids.add(uid)

            already_paid = db.query(FunnelEvent).filter(
                FunnelEvent.event == 'payment_success', FunnelEvent.user_id == uid,
                FunnelEvent.created_at >= ev.created_at,
            ).first()
            already_notified = db.query(FunnelEvent).filter(
                FunnelEvent.event == 'abandoned_checkout_notified', FunnelEvent.user_id == uid,
                FunnelEvent.created_at >= ev.created_at,
            ).first()
            if already_paid or already_notified:
                skipped += 1
                continue

            user = db.query(User).filter(User.firebase_uid == uid).first()
            if user and user.is_premium:
                skipped += 1
                continue

            result = send_push_notification(
                uid, "Twoja subskrypcja czeka 🎓",
                "Zostało kilka kroków — dokończ w minutę i ucz się bez limitów.",
            )
            # Zapisujemy PROBE (niezaleznie od sukcesu wysylki) - brak tokenu FCM teraz nie
            # zmieni sie za 30 min, wiec nie probujemy ponownie tego samego checkoutu w kolko.
            db.add(FunnelEvent(event='abandoned_checkout_notified', user_id=uid, meta={"push_sent": bool(result.get("success"))}))
            db.commit()
            if result.get("success"):
                sent += 1
            else:
                skipped += 1
        print(f"[abandoned checkout] wyslano {sent}, pominieto {skipped}")
    except Exception as e:
        print(f"[abandoned checkout] blad zadania: {e}")
    finally:
        db.close()


_scheduler.add_job(_run_abandoned_checkout_reminder, CronTrigger(minute='*/30'), id='abandoned_checkout_reminder', replace_existing=True, max_instances=1)

# ═══ STRIPE - uzgadnianie subskrypcji co 2h (Europe/Warsaw) ═══
# 20.09.2026: samonaprawa po zgubionym/opoznionym webhooku (patrz StripeService.reconcile_subscriptions).
# ZAGESZCZONE (23.09.2026, KOSZTY subskrypcji, NIE API): user zglosil DRUGI real przypadek w tym
# tygodniu (#10, potem #11/#12) - webhook customer.subscription.updated dla przejscia trial->active/
# past_due po prostu nie dotarl, wiec is_premium/status w naszej bazie byly bledne przez GODZINY
# (do nastepnego uruchomienia o 4:00) - klient placil, a apka pokazywala plan darmowy (albo odwrotnie:
# nieudana platnosc, a dostep premium zostawal). Prawdziwa przyczyna (dostarczanie webhookow przez
# Stripe, poza naszym kodem - patrz panel Stripe -> Developers -> Webhooks -> ten endpoint) jeszcze
# NIE ustalona - to jest siatka bezpieczenstwa, ktora skraca okno bledu z do 24h na do 2h, NIEZALEZNIE
# od przyczyny. Codzienne 04:00 zastapione co-2h; koszt: 12x wiecej wywolan Stripe API dziennie (tylko
# odczyty subskrypcji, nie generowanie AI - bez wplywu na koszt OpenAI/DeepSeek).
def _run_stripe_reconcile():
    from ..database import SessionLocal
    from ..services.stripe_service import StripeService
    db = SessionLocal()
    try:
        r = StripeService.reconcile_subscriptions(db)
        print(f"[Reconcile] sprawdzono {r['checked']}, poprawiono {r['changed']}, bledy {r['errors']}")
    except Exception as e:
        print(f"[Reconcile] blad zadania: {e}")
    finally:
        db.close()


_scheduler.add_job(_run_stripe_reconcile, CronTrigger(hour='*/2', minute=7), id='stripe_reconcile', replace_existing=True, max_instances=1)

_scheduler.start()
print("✅ Harmonogram powiadomien push uruchomiony - codziennie o 18:00")
print("✅ Harmonogram pobierania platnosci BLIK uruchomiony - codziennie o 3:00")
print("✅ Harmonogram uzgadniania subskrypcji Stripe uruchomiony - codziennie o 4:00")
