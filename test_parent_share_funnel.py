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
def fake_create_checkout(req, db_, fu):
    CALLS.append((req.user_id, req.email, fu))
    return CALLS_RESULT["r"]
CALLS_RESULT = {"r": {"success": True, "checkout_url": "https://stripe/x", "session_id": "cs_1"}}
pay.create_checkout = fake_create_checkout
r = ps.checkout_from_share_link(token, db)
check("checkout rodzica: uzywa create_checkout (nowa sciezka) dla konta dziecka", r["success"] and CALLS and CALLS[-1][0] == "kid1" and CALLS[-1][2]["uid"] == "kid1", (r, CALLS))
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

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
