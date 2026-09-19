# -*- coding: utf-8 -*-
"""Offline (Stripe zamockowany, zero sieci): ten sam user nie dostaje triala
drugi raz; user z aktywna subskrypcja nie zaklada drugiej; blad Stripe przy
sprawdzaniu historii = brak triala."""
import os, sys, io, datetime, types
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import User, Subscription
import app.services.stripe_service as ss

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()

STRIPE_SUBS = {"list": []}
CREATED = []
class FakeSub:
    def __init__(self, status): self.status = status
_cnt = iter(range(1, 1000))
ss.stripe.Customer.create = lambda **k: types.SimpleNamespace(id=f"cus_{next(_cnt)}")
ss.stripe.Subscription.list = lambda **k: types.SimpleNamespace(data=[FakeSub(x) for x in STRIPE_SUBS["list"]]) if STRIPE_SUBS["list"] != "ERR" else (_ for _ in ()).throw(RuntimeError("stripe down"))
def fake_session_create(**kw):
    CREATED.append(kw); return types.SimpleNamespace(url="https://x", id="cs_x")
ss.stripe.checkout.Session.create = fake_session_create

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, detail))

def trial_of(kw): return (kw.get("subscription_data") or {}).get("trial_period_days")

# 1) nowy user -> trial
r = ss.StripeService.create_checkout_session("new1", "n@x.pl", db)
check("nowy user dostaje trial", r["success"] and trial_of(CREATED[-1]) in (7, 14), CREATED[-1].get("subscription_data"))

# 2) ten sam user po zakonczonej subskrypcji (lokalny wiersz 'canceled') -> BEZ triala
db.add(Subscription(user_id="old1", stripe_subscription_id="sub_1", status="canceled",
                    current_period_end=datetime.datetime.utcnow() - datetime.timedelta(days=3))); db.commit()
r = ss.StripeService.create_checkout_session("old1", "o@x.pl", db)
check("user z zakonczona subskrypcja: checkout BEZ triala", r["success"] and trial_of(CREATED[-1]) is None, CREATED[-1].get("subscription_data"))

# 3) aktywna (trialujaca) subskrypcja -> blokada
db.add(Subscription(user_id="act1", stripe_subscription_id="sub_2", status="trialing",
                    current_period_end=datetime.datetime.utcnow() + datetime.timedelta(days=5))); db.commit()
n = len(CREATED)
r = ss.StripeService.create_checkout_session("act1", "a@x.pl", db)
check("user z aktywnym trialem: blokada, brak nowej sesji Stripe", (not r["success"]) and r.get("already_subscribed") and len(CREATED) == n, r)

# 4) anulowana na koniec okresu, ale jeszcze trwa -> tez blokada (nie dubluj)
db.add(Subscription(user_id="can1", stripe_subscription_id="sub_3", status="trialing", cancel_at_period_end=True,
                    current_period_end=datetime.datetime.utcnow() + datetime.timedelta(days=2))); db.commit()
r = ss.StripeService.create_checkout_session("can1", "c@x.pl", db)
check("anulowana ale trwajaca subskrypcja: blokada", r.get("already_subscribed") is True, r)

# 5) brak lokalnego wiersza, ale Stripe pamieta stara subskrypcje -> BEZ triala
u = User(firebase_uid="lost1", email="l@x.pl", is_premium=False, stripe_customer_id="cus_lost"); db.add(u); db.commit()
STRIPE_SUBS["list"] = ["canceled"]
r = ss.StripeService.create_checkout_session("lost1", "l@x.pl", db)
check("historia tylko w Stripe: BEZ triala", r["success"] and trial_of(CREATED[-1]) is None, CREATED[-1].get("subscription_data"))

# 6) Stripe pamieta AKTYWNA subskrypcje -> blokada
STRIPE_SUBS["list"] = ["active"]
r = ss.StripeService.create_checkout_session("lost1", "l@x.pl", db)
check("aktywna tylko w Stripe: blokada", r.get("already_subscribed") is True, r)

# 7) blad Stripe przy sprawdzaniu -> checkout dziala, ale BEZ triala
STRIPE_SUBS["list"] = "ERR"
r = ss.StripeService.create_checkout_session("lost1", "l@x.pl", db)
check("blad Stripe przy sprawdzaniu: checkout BEZ triala", r["success"] and trial_of(CREATED[-1]) is None, r)

# 8) porzucony checkout (klient utworzony, brak subskrypcji) -> nadal trial
db.add(User(firebase_uid="aband1", email="ab@x.pl", is_premium=False, stripe_customer_id="cus_ab")); db.commit()
STRIPE_SUBS["list"] = []
r = ss.StripeService.create_checkout_session("aband1", "ab@x.pl", db)
check("porzucony wczesniej checkout (bez subskrypcji): trial przyznany", r["success"] and trial_of(CREATED[-1]) in (7, 14), CREATED[-1].get("subscription_data"))

# 9) BLIK nadal w metodach platnosci
check("BLIK nadal w metodach", "blik" in CREATED[-1]["payment_method_types"], CREATED[-1]["payment_method_types"])

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
