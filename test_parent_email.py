# -*- coding: utf-8 -*-
"""Offline (Stripe zamockowany): e-mail rodzica na stronie 'Poproś rodzica' - potwierdzenia Stripe
ida do rodzica (customer_email), subskrypcja dalej na konto dziecka (metadata.user_id)."""
import os, sys, io, types
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
import app.services.stripe_service as ss
import app.api.payments as pay
import app.api.parent_share as ps

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()
FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, detail))

_cnt = iter(range(1, 1000))
ss.stripe.Customer.create = lambda **k: types.SimpleNamespace(id=f"cus_{next(_cnt)}")
ss.stripe.Subscription.list = lambda **k: types.SimpleNamespace(data=[])
CREATED = []
ss.stripe.checkout.Session.create = lambda **kw: (CREATED.append(kw), types.SimpleNamespace(url="https://x", id="cs_x"))[1]

# 1) bez e-maila rodzica: klient dziecka (stare zachowanie)
r = ss.StripeService.create_checkout_session("kid1", "kid@x.pl", db)
kw = CREATED[-1]
check("bez e-maila rodzica: uzywa klienta dziecka (customer)", r["success"] and "customer" in kw and "customer_email" not in kw, kw.keys())

# 2) z e-mailem rodzica: customer_email, bez customer; metadata nadal na dziecko; BLIK zostaje
r = ss.StripeService.create_checkout_session("kid2", "kid2@x.pl", db, payer_email="rodzic@poczta.pl")
kw = CREATED[-1]
check("z e-mailem rodzica: customer_email = adres rodzica, bez customer", r["success"] and kw.get("customer_email") == "rodzic@poczta.pl" and "customer" not in kw, kw.keys())
check("subskrypcja nadal przypisana do konta dziecka (metadata.user_id)", kw["metadata"]["user_id"] == "kid2", kw["metadata"])
check("BLIK nadal w metodach", "blik" in kw["payment_method_types"], kw["payment_method_types"])

# 3) endpoint rodzica: walidacja e-maila, przekazanie do wspolnej sciezki
RUNS = []
pay._run_checkout = lambda uid, email, db_, aff="", success_url=None, cancel_url=None, payer_email=None: (RUNS.append(payer_email), {"success": True, "checkout_url": "https://y"})[1]
tok = ps.create_share_link(db, {"uid": "kid3", "email": "k3@x.pl"})["token"]

r = ps.checkout_from_share_link(tok, db, ps.ParentCheckoutRequest(email="  Rodzic@Poczta.PL "))
check("poprawny e-mail (znormalizowany do malych liter) trafia do checkoutu", r["success"] and RUNS[-1] == "rodzic@poczta.pl", RUNS)

for bad in ("bez-malpy", "a@b", "a b@c.pl", "@x.pl", "x" * 250 + "@y.pl"):
    n = len(RUNS)
    r = ps.checkout_from_share_link(tok, db, ps.ParentCheckoutRequest(email=bad))
    check(f"zly e-mail odrzucony: {bad[:16]!r}", r["success"] is False and "e-mail" in r["error"] and len(RUNS) == n, r)

r = ps.checkout_from_share_link(tok, db, ps.ParentCheckoutRequest(email=""))
check("puste pole: checkout bez e-maila rodzica", r["success"] and RUNS[-1] is None, RUNS)
r = ps.checkout_from_share_link(tok, db)
check("brak body (stary klient): dziala jak dotad", r["success"] and RUNS[-1] is None, RUNS)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
