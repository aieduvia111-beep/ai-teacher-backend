# -*- coding: utf-8 -*-
"""Offline (push zamockowany): przypomnienie o porzuconym checkoucie (23.09.2026, real prod:
22.09.2026 - 17 checkoutow, 0 dokonczonych, 16 zniknelo w ciszy). Sprawdza: okno 1-24h,
pomija juz oplaconych (payment_success LUB is_premium), pomija juz powiadomionych (jeden
checkout = jedno powiadomienie), dedup do najnowszego checkoutu na usera w oknie, zapisuje
funnel_events niezaleznie od sukcesu wysylki."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import FunnelEvent, User
import app.api.notifications as notif

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
SessionLocal = sessionmaker(bind=eng)
notif.SessionLocal = SessionLocal  # patrzy na modul zaimportowany W FUNKCJI (from ..database import SessionLocal) - patchujemy zrodlo
import app.database as dbm
dbm.SessionLocal = SessionLocal

now = datetime.utcnow()
db = SessionLocal()

def add_user(uid, premium=False):
    db.add(User(firebase_uid=uid, email=f"{uid}@x.pl", is_premium=premium)); db.commit()

def add_event(event, uid, hours_ago, meta=None):
    db.add(FunnelEvent(event=event, user_id=uid, meta=meta, created_at=now - timedelta(hours=hours_ago))); db.commit()

# Kandydaci:
add_user("u_warm")             # checkout 3h temu, nic wiecej -> DOSTAJE przypomnienie
add_event("checkout_created", "u_warm", 3)

add_user("u_paid", premium=False)  # checkout 3h temu, POTEM payment_success -> pomijamy
add_event("checkout_created", "u_paid", 5)
add_event("payment_success", "u_paid", 4)

add_user("u_already_premium", premium=True)  # checkout 3h temu, is_premium=True (zlapane inna sciezka) -> pomijamy
add_event("checkout_created", "u_already_premium", 3)

add_user("u_notified")         # checkout 3h temu, JUZ powiadomiony wczesniej -> pomijamy (bez 2. powiadomienia)
add_event("checkout_created", "u_notified", 3)
add_event("abandoned_checkout_notified", "u_notified", 1)

add_user("u_too_recent")       # checkout 20 MINUT temu (< 1h) -> ZA WCZESNIE, pomijamy w tym przebiegu
add_event("checkout_created", "u_too_recent", 20 / 60.0)

add_user("u_too_old")          # checkout 30h temu (> 24h) -> ZA PoZNO, pomijamy
add_event("checkout_created", "u_too_old", 30)

add_user("u_double_click")     # DWA checkouty w oknie -> tylko NAJNOWSZY liczy sie do dedupu, ALE user i tak dostaje 1 powiadomienie
add_event("checkout_created", "u_double_click", 10)
add_event("checkout_created", "u_double_click", 3)

add_user("u_no_token")         # checkout 3h temu, brak tokenu FCM -> proba wysylki, ale bez sukcesu; i tak zapisujemy "notified" (nie spamujemy w kolko)
add_event("checkout_created", "u_no_token", 3)

db.close()

SENT_TO = []
def fake_send(uid, title, body):
    if uid == "u_no_token":
        return {"success": False, "error": "Brak tokenu FCM dla tego uzytkownika"}
    SENT_TO.append(uid)
    return {"success": True, "message_id": "msg_" + uid}
notif.send_push_notification = fake_send

notif._run_abandoned_checkout_reminder()

db2 = SessionLocal()
check("u_warm (bez platnosci, 3h temu) -> dostal przypomnienie", "u_warm" in SENT_TO, SENT_TO)
check("u_paid (juz zaplacil) -> POMINIETY, brak wysylki", "u_paid" not in SENT_TO, SENT_TO)
check("u_already_premium (is_premium=True) -> POMINIETY", "u_already_premium" not in SENT_TO, SENT_TO)
check("u_notified (juz powiadomiony wczesniej) -> POMINIETY, bez 2. powiadomienia", "u_notified" not in SENT_TO, SENT_TO)
check("u_too_recent (checkout 20 min temu, < 1h) -> POMINIETY w tym przebiegu", "u_too_recent" not in SENT_TO, SENT_TO)
check("u_too_old (checkout 30h temu, > 24h) -> POMINIETY", "u_too_old" not in SENT_TO, SENT_TO)
check("u_double_click (2 checkouty w oknie) -> dostal DOKLADNIE 1 powiadomienie (nie 2)", SENT_TO.count("u_double_click") == 1, SENT_TO)
check("u_no_token (brak tokenu) -> proba wyslana, ale bez sukcesu (nie w SENT_TO)", "u_no_token" not in SENT_TO, SENT_TO)

notified_events = db2.query(FunnelEvent).filter(FunnelEvent.event == "abandoned_checkout_notified").all()
notified_uids = [e.user_id for e in notified_events]
check("u_no_token MIMO braku sukcesu ma zapisany event 'notified' (nie bedzie spamowany co 30 min)", "u_no_token" in notified_uids, notified_uids)
check("u_warm ma zapisany event 'notified' z push_sent=True w meta", any(e.user_id == "u_warm" and e.meta.get("push_sent") is True for e in notified_events), [(e.user_id, e.meta) for e in notified_events])
check("dokladnie 4 eventy 'notified' razem (1 wstepnie zaladowany dla u_notified + 3 nowe: u_warm, u_double_click, u_no_token)", len(notified_events) == 4, notified_uids)
check("u_notified ma TYLKO SWOJ WLASNY, wczesniejszy event 'notified' (jeden, nie drugi)", notified_uids.count("u_notified") == 1, notified_uids)

# Druga runda tego samego zadania (symulacja kolejnego uruchomienia co 30 min) - u_warm NIE dostaje drugiego powiadomienia
SENT_TO.clear()
notif._run_abandoned_checkout_reminder()
check("kolejny przebieg zadania: u_warm juz NIE dostaje 2. powiadomienia", "u_warm" not in SENT_TO, SENT_TO)

db2.close()

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
