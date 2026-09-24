# -*- coding: utf-8 -*-
"""Offline (push zamockowany): przypomnienie dla subskrypcji past_due - max 2 na sub, drugie po 72h."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import FunnelEvent, User, Subscription
import app.database as dbm
import app.api.notifications as notif
FAILED = []
def check(n, c, d=None):
    print(("  OK   " if c else "  FAIL ") + n)
    if not c: FAILED.append((n, str(d)[:300]))
eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
SL = sessionmaker(bind=eng); dbm.SessionLocal = SL
db = SL()
def add(uid, status, premium=False):
    db.add(User(firebase_uid=uid, email=uid+"@x.pl", is_premium=premium))
    db.add(Subscription(user_id=uid, stripe_subscription_id="sub_"+uid, provider="stripe", status=status)); db.commit()
    return db.query(Subscription).filter_by(user_id=uid).first().id
a = add("u_pd", "past_due"); add("u_active", "active", True); add("u_pd_premium", "past_due", True); add("u_notif_old", "past_due"); add("u_notif_new", "past_due"); add("u_done", "past_due")
def ev(uid, sid, hours_ago, n=1):
    db.add(FunnelEvent(event="past_due_notified", user_id=uid, meta={"sub_id": sid, "n": n}, created_at=datetime.utcnow() - timedelta(hours=hours_ago))); db.commit()
sid = lambda u: db.query(Subscription).filter_by(user_id=u).first().id
ev("u_notif_old", sid("u_notif_old"), 80); ev("u_notif_new", sid("u_notif_new"), 10)
ev("u_done", sid("u_done"), 200, 1); ev("u_done", sid("u_done"), 100, 2)
db.close()
SENT = []
notif.send_push_notification = lambda uid, t, b: (SENT.append(uid), {"success": True})[1]
notif._run_past_due_reminder()
check("past_due bez wczesniejszego push -> dostaje", "u_pd" in SENT, SENT)
check("active -> nie", "u_active" not in SENT)
check("past_due ale is_premium -> nie", "u_pd_premium" not in SENT)
check("pierwszy push >72h temu -> drugi", "u_notif_old" in SENT, SENT)
check("pierwszy push 10h temu -> jeszcze nie", "u_notif_new" not in SENT, SENT)
check("juz 2 przypomnienia -> koniec", "u_done" not in SENT, SENT)
SENT.clear(); notif._run_past_due_reminder()
check("kolejny przebieg: nikt nie dostaje ponownie", SENT == [], SENT)
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
