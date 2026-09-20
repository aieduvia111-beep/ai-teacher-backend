# -*- coding: utf-8 -*-
"""Offline (Stripe zamockowany): sciezka 'Popros rodzica' - zdarzenia lejka po stronie serwera,
wspolny checkout z przyciskiem 'Kup Pro', czytelny komunikat przy aktywnej subskrypcji,
wygasly link, nowe zdarzenia w whitelist analityki."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import User, FunnelEvent
import app.api.payments as pay
import app.api.parent_share as ps
import app.api.analytics as an

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()
FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, detail))
def events(): return [(e.event, e.user_id) for e in db.query(FunnelEvent).order_by(FunnelEvent.id).all()]

# 1) dziecko tworzy link
r = ps.create_share_link(db, {"uid": "kid1", "email": "kid@x.pl"})
check("utworzenie linku: sukces + token", r["success"] and r["token"], r)
check("utworzenie linku: zdarzenie parent_link_created", ("parent_link_created", "kid1") in events(), events())
token = r["token"]

# 2) rodzic kupuje - wspolny checkout
CALLS = []
def fake_run_checkout(uid, email, db_, aff="", success_url=None, cancel_url=None):
    CALLS.append((uid, email, success_url, cancel_url))
    return CALLS_RESULT["r"]
CALLS_RESULT = {"r": {"success": True, "checkout_url": "https://stripe/x", "session_id": "cs_1"}}
pay._run_checkout = fake_run_checkout
r = ps.checkout_from_share_link(token, db)
check("checkout rodzica: wspolna sciezka _run_checkout dla konta dziecka", r["success"] and CALLS and CALLS[-1][0] == "kid1", (r, CALLS))
check("po platnosci rodzic wraca na SWOJA strone (rodzic.html?t=..&paid=1), nie na dashboard dziecka", CALLS[-1][2].endswith("/rodzic.html?t=" + token + "&paid=1") and "dashboard" not in CALLS[-1][2], CALLS[-1])
check("anulowanie platnosci wraca na strone rodzica", CALLS[-1][3].endswith("/rodzic.html?t=" + token), CALLS[-1])
check("checkout rodzica: zdarzenie parent_checkout_created", ("parent_checkout_created", "kid1") in events())

CALLS_RESULT["r"] = {"success": False, "error": "boom"}
r = ps.checkout_from_share_link(token, db)
check("blad checkoutu: parent_checkout_failed", r["success"] is False and ("parent_checkout_failed", "kid1") in events(), events())

CALLS_RESULT["r"] = {"success": False, "already_subscribed": True, "error": "Masz juz aktywna subskrypcje. Zarzadzaj nia w ustawieniach konta."}
r = ps.checkout_from_share_link(token, db)
check("aktywna subskrypcja: komunikat dla rodzica (nie 'zarzadzaj w ustawieniach')", r["success"] is False and "To konto ma" in r["error"] and "ustawieniach" not in r["error"], r)

# 3) wygasly link
u = db.query(User).filter(User.firebase_uid == "kid1").first()
u.parent_share_token_expires = datetime.now(timezone.utc) - timedelta(hours=1); db.commit()
try:
    ps.checkout_from_share_link(token, db); ok = False
except HTTPException as e:
    ok = (e.status_code == 410)
check("wygasly link: 410, bez checkoutu", ok)

# 4) whitelist analityki
for ev in ("limit_hit", "ask_parent_click", "parent_page_view", "parent_checkout_click"):
    check(f"analityka przyjmuje '{ev}'", ev in an._ALLOWED_EVENTS)
r = an.track_event(an.TrackEventRequest(event="parent_page_view", meta={"source": "parent_share"}), db)
check("track_event zapisuje parent_page_view", r["success"] and any(e[0] == "parent_page_view" for e in events()), r)
r = an.track_event(an.TrackEventRequest(event="cokolwiek_innego"), db)
check("nieznane zdarzenie nadal ignorowane", r.get("ignored") is True, r)

# 5) diagnostyka statystyk (Firestore niedostepny w tescie -> flaga fdb_connected=False, zero wartosci danych)
import json
tok2 = ps.create_share_link(db, {"uid": "kid2", "email": "k2@x.pl"})["token"]
r = ps.read_share_link(tok2, db)
dbg = [e for e in db.query(FunnelEvent).all() if e.event == "parent_stats_debug"]
check("odczyt statystyk zwraca zera i zapisuje diagnostyke z flagami", r["success"] and r["xp"] == 0 and dbg and "fdb_connected" in dbg[-1].meta, (r, [e.meta for e in dbg]))
check("diagnostyka nie zawiera wartosci danych ucznia (tylko flagi/nazwy pol)", all(set(e.meta.keys()) <= {"fdb_connected","doc_exists","keys","xp_type","history_sizes","error"} for e in dbg))

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
