# -*- coding: utf-8 -*-
"""Offline (Stripe zamockowany): /create-checkout zapisuje wynik do funnel_events
(checkout_created / checkout_failed) i nie psuje odpowiedzi, gdy zapis sie nie uda."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import FunnelEvent
import app.api.payments as pay

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, detail))

REQ = pay.CreateCheckoutRequest(user_id="x", email="a@b.pl")
USER = {"uid": "uid_test_1", "email": "a@b.pl"}
def events(): return [(e.event, e.meta) for e in db.query(FunnelEvent).order_by(FunnelEvent.id).all()]

# 1) sukces
pay.StripeService.create_checkout_session = staticmethod(lambda **k: {"success": True, "checkout_url": "https://x", "session_id": "cs_1"})
r = pay.create_checkout(REQ, db, USER)
ev = events()
check("sukces: odpowiedz bez zmian", r["success"] and r["checkout_url"] == "https://x", r)
check("sukces: zapisano checkout_created", ev and ev[-1][0] == "checkout_created" and ev[-1][1]["fallback"] is False, ev)

# 2) blad Stripe -> fallback (setup) tez pada -> checkout_failed z pierwszym bledem
pay.StripeService.create_checkout_session = staticmethod(lambda **k: {"success": False, "error": "No such price: 'price_x'"})
pay.StripeService.trial_eligibility = staticmethod(lambda *a, **k: {"has_active": False, "trial_allowed": True})
pay.BlikService.create_setup_session = staticmethod(lambda **k: {"success": False, "error": "setup boom"})
r = pay.create_checkout(REQ, db, USER)
ev = events()
check("fallback nieudany: odpowiedz success=False", r["success"] is False, r)
check("fallback nieudany: checkout_failed + pierwszy blad + fallback=True",
      ev[-1][0] == "checkout_failed" and ev[-1][1]["fallback"] is True and "No such price" in (ev[-1][1]["first_error"] or ""), ev[-1])

# 3) fallback ratuje -> checkout_created z fallback=True
pay.BlikService.create_setup_session = staticmethod(lambda **k: {"success": True, "checkout_url": "https://y", "session_id": "cs_2"})
r = pay.create_checkout(REQ, db, USER)
ev = events()
check("fallback udany: checkout_created, fallback=True, first_error zapisany", r["success"] and ev[-1][0] == "checkout_created" and ev[-1][1]["fallback"] is True and ev[-1][1]["first_error"], ev[-1])

# 4) blokada (juz ma subskrypcje)
pay.StripeService.create_checkout_session = staticmethod(lambda **k: {"success": False, "already_subscribed": True, "error": "Masz juz aktywna subskrypcje."})
r = pay.create_checkout(REQ, db, USER)
ev = events()
check("blokada: bez fallbacku, zapis checkout_failed z already_subscribed", r.get("already_subscribed") and ev[-1][0] == "checkout_failed" and ev[-1][1]["already_subscribed"] is True and ev[-1][1]["fallback"] is False, ev[-1])

# 5) blad zapisu do bazy nie psuje odpowiedzi
class BrokenDB:
    def query(self, *a, **k): return db.query(*a, **k)
    def add(self, *a, **k): raise RuntimeError("db down")
    def commit(self): raise RuntimeError("db down")
    def rollback(self): pass
pay.StripeService.create_checkout_session = staticmethod(lambda **k: {"success": True, "checkout_url": "https://z", "session_id": "cs_3"})
r = pay.create_checkout(REQ, BrokenDB(), USER)
check("blad zapisu logu: checkout nadal dziala", r["success"] and r["checkout_url"] == "https://z", r)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
