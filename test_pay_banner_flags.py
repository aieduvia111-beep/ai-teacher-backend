# -*- coding: utf-8 -*-
"""Offline: GET /payments/subscription -> payment_issue / unfinished_checkout."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import FunnelEvent, User, Subscription
from app.api.payments import get_subscription
FAILED = []
def check(n, c, d=None):
    print(("  OK   " if c else "  FAIL ") + n)
    if not c: FAILED.append((n, str(d)[:300]))
eng = create_engine("sqlite://"); Base.metadata.create_all(eng); db = sessionmaker(bind=eng)()
def user(uid, premium=False): db.add(User(firebase_uid=uid, email=uid+"@x.pl", is_premium=premium)); db.commit()
def ev(uid, e, h): db.add(FunnelEvent(event=e, user_id=uid, meta={}, created_at=datetime.utcnow()-timedelta(hours=h))); db.commit()
def get(uid): return get_subscription(db=db, firebase_user={"uid": uid})
user("pd"); db.add(Subscription(user_id="pd", stripe_subscription_id="s1", provider="stripe", status="past_due")); db.commit()
user("open"); ev("open", "checkout_created", 5)
user("old"); ev("old", "checkout_created", 60)
user("paid"); ev("paid", "checkout_created", 5); ev("paid", "payment_success", 4)
user("prem", True); ev("prem", "checkout_created", 5)
user("none")
r = get("pd");   check("past_due bez Pro -> payment_issue, bez unfinished", r["payment_issue"] is True and r["unfinished_checkout"] is False, r)
r = get("open"); check("checkout 5h temu bez platnosci -> unfinished", r["unfinished_checkout"] is True and r["payment_issue"] is False, r)
r = get("old");  check("checkout 60h temu -> nie", r["unfinished_checkout"] is False, r)
r = get("paid"); check("payment_success po checkoucie -> nie", r["unfinished_checkout"] is False, r)
r = get("prem"); check("is_premium -> nie", r["unfinished_checkout"] is False and r["payment_issue"] is False, r)
r = get("none"); check("brak zdarzen -> nic", r["unfinished_checkout"] is False and r["payment_issue"] is False, r)
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
