# -*- coding: utf-8 -*-
"""Offline (Stripe zamockowany): zapis typu metody platnosci nowej subskrypcji (card/blik) do lejka."""
import os, sys, io, types
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import FunnelEvent
import app.services.stripe_service as ss

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()
FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, detail))
def last():
    e = db.query(FunnelEvent).order_by(FunnelEvent.id.desc()).first()
    return (e.event, e.user_id, e.meta) if e else None

PMS = {"pm_blik": types.SimpleNamespace(type="blik"), "pm_card": types.SimpleNamespace(type="card")}
ss.stripe.PaymentMethod.retrieve = lambda i: PMS[i]
ss.stripe.PaymentMethod.list = lambda **k: types.SimpleNamespace(data=[types.SimpleNamespace(type="card")])

ss.StripeService._record_payment_method(types.SimpleNamespace(default_payment_method="pm_blik", customer="cus_1"), "u1", db)
check("BLIK: zapisano type=blik", last() == ("payment_method_used", "u1", {"type": "blik"}), last())
ss.StripeService._record_payment_method(types.SimpleNamespace(default_payment_method="pm_card", customer="cus_1"), "u2", db)
check("karta: zapisano type=card", last() == ("payment_method_used", "u2", {"type": "card"}), last())
ss.StripeService._record_payment_method(types.SimpleNamespace(default_payment_method=None, customer="cus_1"), "u3", db)
check("brak default_payment_method: typ z listy metod klienta", last()[2] == {"type": "card"}, last())

def boom(i): raise RuntimeError("stripe down")
ss.stripe.PaymentMethod.retrieve = boom
n = db.query(FunnelEvent).count()
ss.StripeService._record_payment_method(types.SimpleNamespace(default_payment_method="pm_x", customer="cus_1"), "u4", db)
check("blad Stripe: nie rzuca wyjatku, nic nie zapisuje", db.query(FunnelEvent).count() == n)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
