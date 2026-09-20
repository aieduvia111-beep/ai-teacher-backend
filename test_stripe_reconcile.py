# -*- coding: utf-8 -*-
"""Offline (Stripe zamockowany): codzienne uzgadnianie subskrypcji ze Stripe poprawia rozjazdy tak jak
webhook customer.subscription.updated, nie rusza zamknietych/Apple/BLIK, a blad jednego wiersza nie
zatrzymuje reszty."""
import os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import User, Subscription
import app.services.stripe_service as ss

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()
FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

FB = []
ss._update_firebase_plan = lambda uid, is_pro: FB.append((uid, is_pro))

now = int(time.time())
def user(uid, prem=False): db.add(User(firebase_uid=uid, email=f"{uid}@x.pl", is_premium=prem)); db.commit()
def sub(uid, sid, status, provider="stripe", end=None, cancel=False):
    db.add(Subscription(user_id=uid, stripe_subscription_id=sid, status=status, provider=provider,
                        current_period_end=datetime.fromtimestamp(end or now - 3600), cancel_at_period_end=cancel)); db.commit()

for u in ("u_trial", "u_active", "u_same", "u_err", "u_closed", "u_apple", "u_cancel"): user(u, prem=True)
sub("u_trial", "sub_trial", "trialing")                       # stary trial -> Stripe mowi 'active' z nowym okresem
sub("u_active", "sub_active", "active")                       # -> Stripe mowi 'canceled'
sub("u_same", "sub_same", "active", end=now + 86400)          # bez zmian
sub("u_err", "sub_err", "trialing")                           # Stripe rzuca blad
sub("u_closed", "sub_closed", "canceled")                     # zamknieta - nie ruszamy
sub("u_apple", "apple_1", "active", provider="apple")         # inny dostawca - nie ruszamy
sub("u_cancel", "sub_cancel", "active", end=now + 86400)      # -> Stripe: cancel_at_period_end=True

NEW_END = now + 30 * 86400
REMOTE = {
    "sub_trial": {"id": "sub_trial", "status": "active", "current_period_end": NEW_END, "cancel_at_period_end": False},
    "sub_active": {"id": "sub_active", "status": "canceled", "current_period_end": now - 100, "cancel_at_period_end": False},
    "sub_same": {"id": "sub_same", "status": "active", "current_period_end": now + 86400, "cancel_at_period_end": False},
    "sub_cancel": {"id": "sub_cancel", "status": "active", "current_period_end": now + 86400, "cancel_at_period_end": True},
}
CALLED = []
def fake_retrieve(sid):
    CALLED.append(sid)
    if sid == "sub_err": raise RuntimeError("Stripe niedostepny")
    return REMOTE[sid]
ss.stripe.Subscription.retrieve = fake_retrieve

r = ss.StripeService.reconcile_subscriptions(db)
g = lambda sid: db.query(Subscription).filter_by(stripe_subscription_id=sid).first()
gu = lambda uid: db.query(User).filter_by(firebase_uid=uid).first()

check("sprawdzono 5 aktywnych wierszy Stripe (zamknieta i Apple pominiete)", r["checked"] == 5 and "sub_closed" not in CALLED and "apple_1" not in CALLED, (r, CALLED))
check("trialing -> active, koniec okresu przesuniety o ~30 dni", g("sub_trial").status == "active" and abs(g("sub_trial").current_period_end.timestamp() - NEW_END) < 5, g("sub_trial").current_period_end)
check("uzytkownik po platnosci: is_premium=True, premium_until = nowy koniec", gu("u_trial").is_premium and abs(gu("u_trial").premium_until.timestamp() - NEW_END) < 5, gu("u_trial").premium_until)
check("active -> canceled: is_premium wylaczone", g("sub_active").status == "canceled" and gu("u_active").is_premium is False, (g("sub_active").status, gu("u_active").is_premium))
check("plan w Firebase zsynchronizowany (pro dla oplaconego, free dla zamknietego)", ("u_trial", True) in FB and ("u_active", False) in FB, FB)
check("cancel_at_period_end z Stripe zapisane", g("sub_cancel").cancel_at_period_end is True)
check("blad jednego wiersza NIE zatrzymuje reszty (errors=1, pozostale poprawione)", r["errors"] == 1 and g("sub_err").status == "trialing" and g("sub_trial").status == "active", r)
check("podsumowanie: poprawiono 3 (trial, active->canceled, cancel_at_period_end), bez zmian sub_same", r["changed"] == 3 and all(c["id"] != g("sub_same").id for c in r["changes"]), r["changes"])
check("zamknieta i Apple nietkniete", g("sub_closed").status == "canceled" and g("apple_1").status == "active")

CALLED.clear()
r2 = ss.StripeService.reconcile_subscriptions(db)
check("drugie uruchomienie: zero zmian (idempotentne)", r2["changed"] == 0, r2)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
