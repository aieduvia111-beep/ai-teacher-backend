# -*- coding: utf-8 -*-
"""Offline (Stripe zamockowany): POST /billing-portal (22.09.2026, samoobslugowa aktualizacja
karty/BLIK-a bez przechodzenia przez caly checkout od nowa) - zwraca link portalu dla Stripe
klienta, czytelny blad dla Apple/brakujacego klienta/subskrypcji, nigdy nie crashuje endpointu."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import User, Subscription
import app.api.payments as pay

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

def add_user(uid, customer_id=None):
    u = User(firebase_uid=uid, email=f"{uid}@x.pl", is_premium=True, stripe_customer_id=customer_id)
    db.add(u); db.commit(); return u

def add_sub(uid, provider="stripe"):
    db.add(Subscription(user_id=uid, provider=provider, status="active")); db.commit()

CALLS = []
def fake_portal_create(**kw):
    CALLS.append(kw)
    return type("S", (), {"url": "https://billing.stripe.com/session/test_123"})()
pay.stripe.billing_portal = type("BP", (), {"Session": type("Sess", (), {"create": staticmethod(fake_portal_create)})()})()

# 1) user Stripe z klientem i subskrypcja -> link portalu, prawidlowe parametry
add_user("u1", customer_id="cus_abc"); add_sub("u1", "stripe")
r = pay.create_billing_portal_session(db, {"uid": "u1"})
check("Stripe + klient + subskrypcja: success=True, jest url", r.get("success") is True and r.get("url") == "https://billing.stripe.com/session/test_123", r)
check("wywolano Stripe z poprawnym customer i return_url", CALLS and CALLS[-1].get("customer") == "cus_abc" and "settings.html" in CALLS[-1].get("return_url", ""), CALLS[-1] if CALLS else None)

# 2) brak stripe_customer_id (np. platnik Apple) -> czytelny blad, BEZ wywolania Stripe
CALLS.clear()
add_user("u2", customer_id=None); add_sub("u2", "apple")
r2 = pay.create_billing_portal_session(db, {"uid": "u2"})
check("brak stripe_customer_id: success=False, wskazuje App Store, zero wywolan Stripe", r2.get("success") is False and "App Store" in r2.get("error", "") and not CALLS, r2)

# 3) user nie istnieje w naszej bazie -> czytelny blad, nie crash
r3 = pay.create_billing_portal_session(db, {"uid": "nieistniejacy"})
check("user nie istnieje: success=False, brak wyjatku", r3.get("success") is False, r3)

# 4) ma stripe_customer_id, ale ZERO subskrypcji Stripe w naszej bazie -> czytelny blad
CALLS.clear()
add_user("u4", customer_id="cus_orphan")
r4 = pay.create_billing_portal_session(db, {"uid": "u4"})
check("klient bez zadnej subskrypcji Stripe w bazie: success=False, zero wywolan Stripe", r4.get("success") is False and not CALLS, r4)

# 5) blad samego Stripe (np. nieprawidlowy customer po stronie Stripe) -> nie crashuje, zwraca error
def boom(**kw): raise RuntimeError("No such customer: 'cus_abc'")
pay.stripe.billing_portal.Session.create = staticmethod(boom)
r5 = pay.create_billing_portal_session(db, {"uid": "u1"})
check("blad wywolania Stripe: success=False, komunikat bledu, brak wyjatku na zewnatrz", r5.get("success") is False and "No such customer" in r5.get("error", ""), r5)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
