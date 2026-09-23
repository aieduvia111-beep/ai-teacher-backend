# -*- coding: utf-8 -*-
"""Offline: _sub_period() (23.09.2026, real prod - potwierdzone kodem 400 w Stripe: webhook
customer.subscription.updated -> KeyError na 'current_period_end' na gornym poziomie obiektu
Subscription w API 2026-01-28.clover, gdzie to pole istnieje TYLKO w items.data[0]). Sprawdza
obie ksztalty payloadu (stary z gornym polem, nowy - tylko w items) i realny webhook end-to-end
(_handle_subscription_updated na PRAWDZIWYM, wklejonym z produkcji ksztalcie eventu bez gornego
pola) NIE rzuca juz wyjatku."""
import os, sys, io
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

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

# ---- 1) _sub_period: ksztalt STARY (gorny poziom obecny) ----
old_shape = {"id": "sub_x", "current_period_end": 1790000000, "items": {"data": [{"current_period_end": 999}]}}
check("stary ksztalt: bierze GORNY poziom (nie items, mimo ze tez jest)", ss._sub_period(old_shape, "current_period_end") == 1790000000, ss._sub_period(old_shape, "current_period_end"))

# ---- 2) _sub_period: ksztalt NOWY (API 2026-01-28.clover - brak gornego pola, patrz real event z produkcji) ----
new_shape = {"id": "sub_1UGK8oD1RWr87QNIAN7foqiz", "items": {"data": [{"current_period_end": 1792766934, "current_period_start": 1790174934}]}}
check("nowy ksztalt: brak gornego pola -> spada do items[0]", ss._sub_period(new_shape, "current_period_end") == 1792766934, ss._sub_period(new_shape, "current_period_end"))
check("nowy ksztalt: dziala tez dla current_period_start", ss._sub_period(new_shape, "current_period_start") == 1790174934, ss._sub_period(new_shape, "current_period_start"))

# ---- 3) brak pola WSZEDZIE -> czytelny blad, nie cichy None/crash niejasnym wyjatkiem ----
broken = {"id": "sub_broken", "items": {"data": []}}
try:
    ss._sub_period(broken, "current_period_end")
    check("brak pola nigdzie -> podnosi wyjatek (nie zwraca cicho None)", False)
except ValueError as e:
    check("brak pola nigdzie -> ValueError z czytelnym komunikatem (id w tresci)", "sub_broken" in str(e), str(e))
except Exception as e:
    check("brak pola nigdzie -> ValueError (nie inny typ wyjatku)", False, f"{type(e).__name__}: {e}")

# ---- 4) END-TO-END: PRAWDZIWY ksztalt eventu z produkcji (evt_1UIrUWD1RWr87QNIICdN2EmE,
#          customer.subscription.updated, 23.09.2026) - _handle_subscription_updated NIE crashuje ----
eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()
db.add(User(firebase_uid="Lks0si5osrdiwmVQ1w4hrFLlA5T2", email="c@x.pl", is_premium=True))
db.add(Subscription(user_id="Lks0si5osrdiwmVQ1w4hrFLlA5T2", stripe_subscription_id="sub_1UGK8oD1RWr87QNIAN7foqiz",
                     provider="stripe", status="trialing"))
db.commit()

# Uproszczony, ale STRUKTURALNIE identyczny ksztalt realnego payloadu Stripe (brak current_period_end/
# start na gornym poziomie obiektu subskrypcji - dokladnie to, co przyszlo z produkcji 23.09.2026).
REAL_EVENT = {
    "data": {
        "object": {
            "id": "sub_1UGK8oD1RWr87QNIAN7foqiz",
            "status": "active",
            "cancel_at_period_end": False,
            "customer": "cus_VGriDliY0NpOdn",
            "items": {"data": [{"id": "si_VGrsCYkslGVdTm", "current_period_end": 1792766934, "current_period_start": 1790174934}]},
        }
    }
}
try:
    result = ss.StripeService._handle_subscription_updated(REAL_EVENT, db)
    check("real event (bez gornego current_period_end): _handle_subscription_updated NIE rzuca wyjatku", result.get("success") is True, result)
except Exception as e:
    check(f"real event: _handle_subscription_updated NIE rzuca wyjatku (dostal: {type(e).__name__}: {e})", False, str(e))

sub_row = db.query(Subscription).filter_by(stripe_subscription_id="sub_1UGK8oD1RWr87QNIAN7foqiz").first()
check("status zaktualizowany do 'active'", sub_row.status == "active", sub_row.status)
check("current_period_end poprawnie ustawiony z items[0] (timestamp 1792766934)", sub_row.current_period_end == datetime.fromtimestamp(1792766934), sub_row.current_period_end)
user = db.query(User).filter_by(firebase_uid="Lks0si5osrdiwmVQ1w4hrFLlA5T2").first()
check("user.is_premium=True, premium_until ustawiony", user.is_premium is True and user.premium_until == sub_row.current_period_end, (user.is_premium, user.premium_until))

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
