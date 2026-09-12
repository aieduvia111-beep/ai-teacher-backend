# -*- coding: utf-8 -*-
"""Testy BLIK recurring (wrzesien 2026, patrz app/services/blik_service.py
i plan implementacji "BLIK jako druga metoda platnosci"). Sprawdza
LOGIKE stanu (upsert, blokada, sweep, przejscia webhookow) na
IZOLOWANEJ bazie SQLite w pamieci - zero prawdziwych wywolan Stripe
(wszystkie stripe.* funkcje zamockowane), zero dotykania prawdziwego
ai_teacher.db. Prawdziwy end-to-end (Stripe CLI + realny Checkout z
BLIK w Dashboardzie) to osobny, recznie wykonywany krok - patrz plan."""
import sys
from datetime import datetime, timedelta, timezone
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


def naive(dt):
    """SQLite (w odroznieniu od Postgresa produkcyjnego) gubi tzinfo przy
    zapisie/odczycie DateTime(timezone=True) - do porownan w tych testach
    normalizujemy WSZYSTKO do naive UTC, zeby uniknac
    'can't compare offset-naive and offset-aware datetimes'. To
    ograniczenie SQLite w tym skrypcie testowym, nie blad w kodzie
    aplikacji (produkcja to Postgres, ktory zachowuje tzinfo poprawnie;
    zapytania SQL w charge_due_blik_subscriptions poroownuja PO STRONIE
    SQL, nie jako dwa obiekty Python, wiec tam ten problem nie wystepuje)."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


NOW_NAIVE = datetime.utcnow()


# Izolowana baza w pamieci - TYLKO tabele User/Subscription.
from app.database import Base
from app.models import User, Subscription

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine, tables=[User.__table__, Subscription.__table__])
TestSession = sessionmaker(bind=engine)

import app.services.blik_service as blik_service
import app.services.stripe_service as stripe_service

# Firebase Admin nie jest zaladowany w tym srodowisku testowym (brak
# credentiali) - _update_firebase_plan już wtedy jest bezpiecznym no-op
# (patrz stripe_service._fdb is None), wiec nie trzeba go mockowac.

print("=" * 70)
print("1. _upsert_blik_subscription_row - insert, potem update tego samego wiersza")
print("=" * 70)
db = TestSession()
row1 = blik_service._upsert_blik_subscription_row(
    db, "user_A", blik_payment_method_id="pm_AAA", status="trialing",
    current_period_start=datetime.now(timezone.utc),
    current_period_end=datetime.now(timezone.utc) + timedelta(days=7),
    next_charge_at=datetime.now(timezone.utc) + timedelta(days=7),
)
check("Pierwszy upsert tworzy nowy wiersz z provider='blik'", row1.provider == "blik", row1.provider)
check("user_id ustawiony poprawnie", row1.user_id == "user_A", row1.user_id)
count_after_first = db.query(Subscription).count()
check("Dokladnie 1 wiersz po pierwszym upsert", count_after_first == 1, count_after_first)

row2 = blik_service._upsert_blik_subscription_row(
    db, "user_A", blik_payment_method_id="pm_AAA", status="active",
)
count_after_second = db.query(Subscription).count()
check("Drugi upsert (ten sam blik_payment_method_id) AKTUALIZUJE, nie duplikuje", count_after_second == 1, count_after_second)
check("Status zaktualizowany na 'active'", row2.status == "active", row2.status)
check("To dokladnie ten sam wiersz (id sie zgadza)", row2.id == row1.id, (row1.id, row2.id))
db.close()


print()
print("=" * 70)
print("2. _handle_setup_completed - nadaje Pro natychmiast, ustawia next_charge_at")
print("=" * 70)
db = TestSession()
user_b = User(firebase_uid="user_B", email="b@example.com", is_premium=False)
db.add(user_b)
db.commit()


class _FakeSetupIntent:
    payment_method = "pm_BBB"
    metadata = {"trial_days": "7"}


class _FakePaymentMethodBlik:
    type = "blik"


_orig_retrieve = blik_service.stripe.SetupIntent.retrieve
_orig_pm_retrieve = blik_service.stripe.PaymentMethod.retrieve
blik_service.stripe.SetupIntent.retrieve = staticmethod(lambda sid: _FakeSetupIntent())
# NOWE (12.09.2026, checkout wspolny karta+BLIK): _handle_setup_completed
# teraz NAJPIERW sprawdza PaymentMethod.type zeby rozgalezic na
# _activate_card_subscription vs _activate_blik_trial - musi byc
# zamockowane, inaczej realne wywolanie API rzuca "No such PaymentMethod".
blik_service.stripe.PaymentMethod.retrieve = staticmethod(lambda pmid: _FakePaymentMethodBlik())

fake_event = {"data": {"object": {
    "metadata": {"user_id": "user_B"},
    "setup_intent": "seti_fake_123",
    "customer": "cus_fake_B",
}}}
result = blik_service.BlikService._handle_setup_completed(fake_event, db)
blik_service.stripe.SetupIntent.retrieve = _orig_retrieve
blik_service.stripe.PaymentMethod.retrieve = _orig_pm_retrieve

check("_handle_setup_completed zwraca success", result.get("success") is True, result)
db.refresh(user_b)
check("user.is_premium ustawione na True natychmiast (bez oplaty)", user_b.is_premium is True, user_b.is_premium)
check("premium_until ustawione (~7 dni od teraz)", user_b.premium_until is not None, user_b.premium_until)

blik_row = db.query(Subscription).filter(Subscription.user_id == "user_B", Subscription.provider == "blik").first()
check("Wiersz Subscription utworzony z provider='blik'", blik_row is not None and blik_row.provider == "blik", blik_row)
check("status='trialing'", blik_row.status == "trialing", blik_row.status)
check("blik_payment_method_id zapisane z SetupIntent.payment_method", blik_row.blik_payment_method_id == "pm_BBB", blik_row.blik_payment_method_id)
check("next_charge_at ustawione ~7 dni w przyszlosc", naive(blik_row.next_charge_at) > NOW_NAIVE + timedelta(days=6), blik_row.next_charge_at)
db.close()


print()
print("=" * 70)
print("2b. _handle_setup_completed - user wybral KARTE na wspolnej stronie Stripe")
print("=" * 70)
db = TestSession()
user_card = User(firebase_uid="user_card", email="card@example.com", is_premium=False)
db.add(user_card)
db.commit()


class _FakePaymentMethodCard:
    type = "card"


class _FakeSubscription:
    id = "sub_fake_1"
    status = "trialing"
    current_period_start = int(NOW_NAIVE.timestamp())
    current_period_end = int((NOW_NAIVE + timedelta(days=7)).timestamp())


_sub_create_calls = []


def _fake_subscription_create(**kwargs):
    _sub_create_calls.append(kwargs)
    return _FakeSubscription()


blik_service.stripe.SetupIntent.retrieve = staticmethod(lambda sid: _FakeSetupIntent())
blik_service.stripe.PaymentMethod.retrieve = staticmethod(lambda pmid: _FakePaymentMethodCard())
_orig_sub_create = blik_service.stripe.Subscription.create
blik_service.stripe.Subscription.create = staticmethod(_fake_subscription_create)

fake_event_card = {"data": {"object": {
    "metadata": {"user_id": "user_card"},
    "setup_intent": "seti_fake_card",
    "customer": "cus_fake_card",
}}}
result_card = blik_service.BlikService._handle_setup_completed(fake_event_card, db)

blik_service.stripe.SetupIntent.retrieve = _orig_retrieve
blik_service.stripe.PaymentMethod.retrieve = _orig_pm_retrieve
blik_service.stripe.Subscription.create = _orig_sub_create

check("_handle_setup_completed (karta) zwraca success", result_card.get("success") is True, result_card)
check("Routing poprawny: PaymentMethod.type='card' -> stripe.Subscription.create wywolane dokladnie raz", len(_sub_create_calls) == 1, len(_sub_create_calls))
check("Subscription.create dostal default_payment_method z SetupIntent.payment_method", _sub_create_calls[0].get("default_payment_method") == "pm_BBB", _sub_create_calls)
check("Subscription.create dostal trial_period_days z metadata SetupIntentu", _sub_create_calls[0].get("trial_period_days") == 7, _sub_create_calls)

db.refresh(user_card)
check("user.is_premium=True (karta, przez wspolny setup)", user_card.is_premium is True, user_card.is_premium)

card_row = db.query(Subscription).filter(Subscription.user_id == "user_card").first()
check("Wiersz Subscription ma provider='stripe' (NIE 'blik') - jedzie normalnym mechanizmem karty", card_row is not None and card_row.provider == "stripe", card_row)
check("stripe_subscription_id zapisane z prawdziwej (zamockowanej) Subscription", card_row.stripe_subscription_id == "sub_fake_1", card_row.stripe_subscription_id if card_row else None)
check("status skopiowany z Subscription.status ('trialing')", card_row.status == "trialing", card_row.status if card_row else None)
db.close()


print()
print("=" * 70)
print("3. charge_due_subscription - blokada przed podwojnym obciazeniem")
print("=" * 70)
db = TestSession()
user_c = User(firebase_uid="user_C", email="c@example.com", is_premium=True, stripe_customer_id="cus_C")
db.add(user_c)
db.commit()
row_c = Subscription(
    user_id="user_C", provider="blik", blik_payment_method_id="pm_CCC",
    status="trialing", next_charge_at=datetime.now(timezone.utc) - timedelta(hours=1),
    blik_charge_in_progress=False,
)
db.add(row_c)
db.commit()

_pi_call_count = {"n": 0}


def _fake_price_retrieve(price_id):
    class _P:
        unit_amount = 3000
        currency = "pln"
    return _P()


def _fake_pi_create(**kwargs):
    _pi_call_count["n"] += 1

    class _PI:
        id = f"pi_fake_{_pi_call_count['n']}"
    return _PI()


_orig_price_retrieve = blik_service.stripe.Price.retrieve
_orig_pi_create = blik_service.stripe.PaymentIntent.create
blik_service.stripe.Price.retrieve = staticmethod(_fake_price_retrieve)
blik_service.stripe.PaymentIntent.create = staticmethod(_fake_pi_create)

blik_service.BlikService.charge_due_subscription(db, row_c)
check("Po 1. wywolaniu: PaymentIntent utworzony dokladnie raz", _pi_call_count["n"] == 1, _pi_call_count["n"])
db.refresh(row_c)
check("blik_charge_in_progress=True po wywolaniu (czeka na webhook)", row_c.blik_charge_in_progress is True, row_c.blik_charge_in_progress)
check("blik_last_payment_intent_id zapisane", row_c.blik_last_payment_intent_id == "pi_fake_1", row_c.blik_last_payment_intent_id)

# Drugie wywolanie na TYM SAMYM wierszu (symulacja nakladajacych sie
# uruchomien schedulera) - blokada MUSI to zatrzymac.
blik_service.BlikService.charge_due_subscription(db, row_c)
check("Po 2. (nakladajacym sie) wywolaniu: PaymentIntent NADAL utworzony tylko raz (blokada zadzialala)", _pi_call_count["n"] == 1, _pi_call_count["n"])

blik_service.stripe.Price.retrieve = _orig_price_retrieve
blik_service.stripe.PaymentIntent.create = _orig_pi_create
db.close()


print()
print("=" * 70)
print("4. charge_due_blik_subscriptions (sweep) - wybiera TYLKO nalezne, niezablokowane wiersze")
print("=" * 70)
db = TestSession()
now = datetime.now(timezone.utc)


def _mk_user(uid):
    u = User(firebase_uid=uid, email=f"{uid}@example.com", is_premium=True, stripe_customer_id=f"cus_{uid}")
    db.add(u)


for uid in ("due1", "due2", "not_due", "canceled_flag", "locked", "wrong_status"):
    _mk_user(uid)
db.commit()

db.add(Subscription(user_id="due1", provider="blik", blik_payment_method_id="pm_due1", status="trialing", next_charge_at=now - timedelta(hours=2), blik_charge_in_progress=False))
db.add(Subscription(user_id="due2", provider="blik", blik_payment_method_id="pm_due2", status="active", next_charge_at=now - timedelta(minutes=5), blik_charge_in_progress=False))
db.add(Subscription(user_id="not_due", provider="blik", blik_payment_method_id="pm_not_due", status="active", next_charge_at=now + timedelta(days=5), blik_charge_in_progress=False))
db.add(Subscription(user_id="canceled_flag", provider="blik", blik_payment_method_id="pm_cf", status="active", next_charge_at=now - timedelta(hours=1), cancel_at_period_end=True, blik_charge_in_progress=False))
db.add(Subscription(user_id="locked", provider="blik", blik_payment_method_id="pm_locked", status="active", next_charge_at=now - timedelta(hours=1), blik_charge_in_progress=True))
db.add(Subscription(user_id="wrong_status", provider="blik", blik_payment_method_id="pm_ws", status="canceled", next_charge_at=now - timedelta(hours=1), blik_charge_in_progress=False))
db.commit()

_charged_rows = []
_orig_charge = blik_service.BlikService.charge_due_subscription
blik_service.BlikService.charge_due_subscription = staticmethod(lambda db_, row: _charged_rows.append(row.user_id))

# charge_due_blik_subscriptions uzywa WLASNEJ sesji (SessionLocal na
# realnej bazie) - testujemy wiec bezposrednio zapytanie sweepu na
# naszej testowej sesji, tym samym wzorcem co produkcyjna funkcja.
due_rows = db.query(Subscription).filter(
    Subscription.provider == "blik",
    Subscription.status.in_(["trialing", "active"]),
    Subscription.cancel_at_period_end == False,  # noqa: E712
    Subscription.next_charge_at <= now,
    Subscription.blik_charge_in_progress == False,  # noqa: E712
).all()
due_user_ids = sorted(r.user_id for r in due_rows)

check("Sweep wybiera dokladnie ['due1', 'due2']", due_user_ids == ["due1", "due2"], due_user_ids)
check("'not_due' (przyszlosc) POMINIETY", "not_due" not in due_user_ids, due_user_ids)
check("'canceled_flag' (cancel_at_period_end=True) POMINIETY", "canceled_flag" not in due_user_ids, due_user_ids)
check("'locked' (blik_charge_in_progress=True) POMINIETY", "locked" not in due_user_ids, due_user_ids)
check("'wrong_status' (status='canceled') POMINIETY", "wrong_status" not in due_user_ids, due_user_ids)

blik_service.BlikService.charge_due_subscription = _orig_charge
db.close()


print()
print("=" * 70)
print("5. Auto-zwolnienie zawieszonej blokady (proces padl, updated_at stary)")
print("=" * 70)
db = TestSession()
u_stuck = User(firebase_uid="stuck_user", email="s@example.com", is_premium=True)
db.add(u_stuck)
db.commit()
row_stuck = Subscription(
    user_id="stuck_user", provider="blik", blik_payment_method_id="pm_stuck",
    status="active", next_charge_at=now - timedelta(days=1), blik_charge_in_progress=True,
)
db.add(row_stuck)
db.commit()
# Symulacja "starego" updated_at (proces padl >1h temu) - ustawiamy
# recznie w bazie, bo onupdate=func.now() nadpisalby to przy zwyklym save.
db.execute(
    Subscription.__table__.update().where(Subscription.id == row_stuck.id).values(
        updated_at=now - timedelta(hours=3)
    )
)
db.commit()

stuck_cutoff = now - timedelta(hours=blik_service._STUCK_LOCK_HOURS)
stuck = db.query(Subscription).filter(
    Subscription.provider == "blik",
    Subscription.blik_charge_in_progress == True,  # noqa: E712
    Subscription.updated_at < stuck_cutoff,
).all()
check("Wiersz ze starym updated_at (>1h) zostaje wykryty jako zawieszony", len(stuck) == 1 and stuck[0].id == row_stuck.id, [s.id for s in stuck])
db.close()


print()
print("=" * 70)
print("6. Webhook sukcesu obciazenia - przesuwa next_charge_at, user zostaje Pro")
print("=" * 70)
db = TestSession()
u_ok = User(firebase_uid="user_ok", email="ok@example.com", is_premium=True)
db.add(u_ok)
db.commit()
row_ok = Subscription(
    user_id="user_ok", provider="blik", blik_payment_method_id="pm_ok",
    status="trialing", blik_charge_in_progress=True, blik_last_payment_intent_id="pi_ok_1",
    current_period_end=now,
)
db.add(row_ok)
db.commit()

event_success = {"data": {"object": {
    "id": "pi_ok_1",
    "metadata": {"blik_charge": "true", "subscription_row_id": str(row_ok.id)},
}}}
result = blik_service.BlikService._handle_charge_succeeded(event_success, db)
check("_handle_charge_succeeded zwraca success", result.get("success") is True, result)
db.refresh(row_ok)
check("status='active' po sukcesie", row_ok.status == "active", row_ok.status)
check("blik_charge_in_progress zdjete (False)", row_ok.blik_charge_in_progress is False, row_ok.blik_charge_in_progress)
check("next_charge_at przesuniete ~30 dni w przod", naive(row_ok.next_charge_at) > naive(now) + timedelta(days=29), row_ok.next_charge_at)
db.refresh(u_ok)
check("user.is_premium nadal True", u_ok.is_premium is True, u_ok.is_premium)

# Duplikat tego samego webhooka (Stripe retry) - NIE powinien przesunac next_charge_at drugi raz.
next_charge_after_first = row_ok.next_charge_at
result2 = blik_service.BlikService._handle_charge_succeeded(event_success, db)
db.refresh(row_ok)
check("Duplikat webhooka IGNOROWANY (next_charge_at bez zmian)", row_ok.next_charge_at == next_charge_after_first, (row_ok.next_charge_at, next_charge_after_first))
db.close()


print()
print("=" * 70)
print("7. Webhook porazki obciazenia - natychmiastowa utrata Pro")
print("=" * 70)
db = TestSession()
u_fail = User(firebase_uid="user_fail", email="fail@example.com", is_premium=True, premium_until=now + timedelta(days=30))
db.add(u_fail)
db.commit()
row_fail = Subscription(
    user_id="user_fail", provider="blik", blik_payment_method_id="pm_fail",
    status="active", blik_charge_in_progress=True,
)
db.add(row_fail)
db.commit()

event_fail = {"data": {"object": {
    "id": "pi_fail_1",
    "metadata": {"blik_charge": "true", "subscription_row_id": str(row_fail.id)},
}}}
result = blik_service.BlikService._handle_charge_failed(event_fail, db)
check("_handle_charge_failed zwraca success (obsluzone poprawnie)", result.get("success") is True, result)
db.refresh(row_fail)
check("status='past_due' po porazce", row_fail.status == "past_due", row_fail.status)
db.refresh(u_fail)
check("user.is_premium natychmiast False", u_fail.is_premium is False, u_fail.is_premium)
check("premium_until wyczyszczone", u_fail.premium_until is None, u_fail.premium_until)
db.close()


print()
print("=" * 70)
print("8. Cofniecie mandatu (mandate.updated -> inactive) - degradacja niezalezna od naszego API")
print("=" * 70)
db = TestSession()
u_revoked = User(firebase_uid="user_revoked", email="rev@example.com", is_premium=True)
db.add(u_revoked)
db.commit()
row_revoked = Subscription(
    user_id="user_revoked", provider="blik", blik_payment_method_id="pm_revoked", status="active",
)
db.add(row_revoked)
db.commit()

event_mandate = {"data": {"object": {"status": "inactive", "payment_method": "pm_revoked", "id": "mandate_fake"}}}
result = blik_service.BlikService._handle_mandate_revoked(event_mandate, db)
check("_handle_mandate_revoked zwraca success", result.get("success") is True, result)
db.refresh(row_revoked)
check("status='canceled' po cofnieciu mandatu", row_revoked.status == "canceled", row_revoked.status)
db.refresh(u_revoked)
check("user.is_premium=False po cofnieciu mandatu", u_revoked.is_premium is False, u_revoked.is_premium)

# mandate.updated z INNYM statusem (np. "active") NIE powinno nic zmienic.
row_active2 = Subscription(user_id="user_stays", provider="blik", blik_payment_method_id="pm_stays", status="active")
db.add(row_active2)
db.commit()
event_mandate_active = {"data": {"object": {"status": "active", "payment_method": "pm_stays", "id": "mandate_fake2"}}}
blik_service.BlikService._handle_mandate_revoked(event_mandate_active, db)
db.refresh(row_active2)
check("mandate.updated ze statusem INNYM niz 'inactive' -> brak zmian", row_active2.status == "active", row_active2.status)
db.close()


print()
print("=" * 70)
print("9. mark_canceled - NIE woła Stripe, tylko flaguje wiersz")
print("=" * 70)
db = TestSession()
row_cancel = Subscription(
    user_id="user_cancel_me", provider="blik", blik_payment_method_id="pm_cm",
    status="active", current_period_end=now + timedelta(days=10),
)
db.add(row_cancel)
db.commit()
result = blik_service.BlikService.mark_canceled(db, row_cancel)
check("mark_canceled zwraca success", result.get("success") is True, result)
db.refresh(row_cancel)
check("cancel_at_period_end=True", row_cancel.cancel_at_period_end is True, row_cancel.cancel_at_period_end)
check("status pozostaje 'active' (dostep do konca okresu, nie natychmiast)", row_cancel.status == "active", row_cancel.status)
db.close()


print()
print("=" * 70)
print("WYNIK:", "0 bledow - wszystkie testy przeszly" if not FAILED else f"{len(FAILED)} bledow")
print("=" * 70)
if FAILED:
    for name, detail in FAILED:
        print(f"  - {name} ({detail})")
    sys.exit(1)
