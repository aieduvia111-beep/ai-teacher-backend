"""BLIK RECURRING - druga metoda platnosci obok karty (Android/Web/Stripe),
wrzesien 2026. Audyt UX ("dlaczego ludzie nie chca placic") wykazal, ze
checkout przyjmowal WYLACZNIE karte, mimo ze docelowa grupa (uczniowie
liceum) czesto nie ma wlasnej karty, a MA dostep do BLIK-a (przez wlasna
lub rodzica aplikacje bankowa) - dominujacej metody platnosci wsrod
mlodych w Polsce.

KLUCZOWA ROZNICA wzgledem karty: BLIK recurring NIE MA odpowiednika
Stripe Subscription. Karta -> Stripe sam prowadzi caly cykl zycia
(trial, pierwsze obciazenie, odnowienia, retry). BLIK -> MY jestesmy
tym "robotem": raz dziennie (patrz scheduler w app/api/notifications.py,
job 'blik_charge_sweep') sprawdzamy komu nalezy sie dzis obciazenie i
recznie zlecamy PaymentIntent. Pelny plan (w tym "jak dokladnie
pobierane sa pieniadze") - patrz plan zapisany podczas implementacji tej
funkcji, sekcja 0.

DWIE SCIEZKI (mirror architektury Apple IAP - patrz apple_iap_service.py):
1. create_setup_session() - Checkout Session w mode="setup" (NIE
   "subscription"!) - user zatwierdza mandat BLIK w banku, BEZ zadnej
   platnosci w tym momencie. Wywolane z POST /api/v1/payments/create-checkout
   (payment_method="blik").
2. Webhooki (_handle_setup_completed/_handle_charge_succeeded/
   _handle_charge_failed/_handle_mandate_revoked) - zrodlo prawdy dla
   stanu w czasie, wpiete w StripeService.handle_webhook (jeden wspolny
   endpoint webhooka dla karty i BLIK-a).

charge_due_subscription() - wywolywane WYLACZNIE przez codzienny
scheduler, NIGDY synchronicznie z requestu HTTP usera - to jest to
miejsce, gdzie faktycznie "pobieramy pieniadze"."""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import stripe
from sqlalchemy.orm import Session

from ..config import settings
from ..models import User, Subscription
from .stripe_service import _update_firebase_plan, get_trial_days

# Ile dni odnawia sie okres BLIK po udanym obciazeniu - identyczne z
# miesiecznym cyklem karty (Stripe Price ma interval="month", tutaj
# przyblizamy stalymi 30 dniami, bo nie ma obiektu Subscription, ktory
# liczylby to za nas kalendarzowo).
_RENEWAL_PERIOD_DAYS = 30

# Jesli blik_charge_in_progress zostanie "zawieszone" (proces padl po
# ustawieniu blokady, przed rozstrzygnieciem przez webhook) - po tylu
# godzinach scheduler moze bezpiecznie zdjac blokade i sprobowac ponownie
# nastepnego dnia, zamiast trwale utracic userowi mozliwosc odnowienia.
_STUCK_LOCK_HOURS = 1


def _resolve_price_amount() -> tuple:
    """Kwota i waluta brane z TEGO SAMEGO Stripe Price co karta
    (settings.STRIPE_PRICE_ID) - nie hardkodowac grosza drugi raz, zeby
    nie rozjechalo sie cicho przy zmianie ceny w Dashboardzie."""
    price = stripe.Price.retrieve(settings.STRIPE_PRICE_ID)
    return price.unit_amount, price.currency


def _upsert_blik_subscription_row(db: Session, user_id: str, **fields) -> Subscription:
    """Wzorowane na apple_iap_service._upsert_subscription_row: najpierw
    szukamy istniejacego wiersza po stabilnym id (tu:
    blik_payment_method_id), aktualizujemy jesli istnieje, w przeciwnym
    razie wstawiamy nowy z provider="blik". CELOWO nie kopiujemy goleg
    insertu z karty (StripeService._handle_checkout_completed) - ten sam
    kod flaguje go jako zrodlo przeszlych bugow z duplikatami/sierotami."""
    payment_method_id = fields.get("blik_payment_method_id")
    row = None
    if payment_method_id:
        row = db.query(Subscription).filter(
            Subscription.provider == "blik",
            Subscription.blik_payment_method_id == payment_method_id,
        ).first()
    if row:
        for key, value in fields.items():
            setattr(row, key, value)
    else:
        row = Subscription(user_id=user_id, provider="blik", **fields)
        db.add(row)
    db.commit()
    return row


class BlikService:

    @staticmethod
    def create_setup_session(user_id: str, email: str, db: Session, affiliate_code: str = "") -> Dict:
        """Analog StripeService.create_checkout_session, ale mode="setup"
        - zero platnosci w tym kroku, tylko zapisanie mandatu BLIK do
        pozniejszego, recznego obciazania (patrz charge_due_subscription)."""
        try:
            print(f"Tworze BLIK setup session dla user {user_id} ({email})")

            user = db.query(User).filter(User.firebase_uid == user_id).first()
            if not user:
                user = User(firebase_uid=user_id, email=email, is_premium=False)
                db.add(user)
                db.commit()
                db.refresh(user)

            if user.stripe_customer_id:
                customer_id = user.stripe_customer_id
            else:
                customer = stripe.Customer.create(email=email, metadata={"user_id": user_id})
                customer_id = customer.id
                user.stripe_customer_id = customer_id
                db.commit()

            # Dlugosc triala zapisana JUZ TERAZ w metadata SetupIntentu (nie
            # dopiero w webhooku) - identyczna dyscyplina co przy promocji
            # trialowej karty: liczy sie moment kliknięcia "Subskrybuj", nie
            # moment (pozniejszy, asynchroniczny) przetworzenia webhooka,
            # ktory moglby juz wypasc po deadline promocji.
            trial_days = get_trial_days()

            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["blik"],
                mode="setup",
                setup_intent_data={
                    "metadata": {"user_id": user_id, "trial_days": str(trial_days)},
                },
                # Osobne success/cancel URL od karty ("blik_setup=..." nie
                # "payment=...") - frontend MUSI odroznic "mandat zapisany"
                # od "subskrypcja karty wystartowala", bo tu nie ma
                # session['subscription'] i nie ma jeszcze zadnej platnosci.
                success_url=f"{settings.FRONTEND_URL}/dashboard_FINAL.html?blik_setup=success&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/pricing.html?blik_setup=cancelled",
                metadata={"user_id": user_id, "affiliate_code": affiliate_code} if affiliate_code else {"user_id": user_id},
            )

            return {"success": True, "checkout_url": checkout_session.url, "session_id": checkout_session.id}

        except stripe.error.StripeError as e:
            print(f"Blad Stripe (BLIK setup): {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            print(f"Blad (BLIK setup): {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _handle_setup_completed(event: Dict, db: Session) -> Dict:
        """checkout.session.completed z mode="setup" - mandat BLIK
        zapisany. Nadajemy Pro NATYCHMIAST (jak przy karcie) - zgodnie z
        istniejaca obietnica "trial = pelny dostep od razu"; pierwsze
        realne obciazenie nastapi cicho w dniu konca triala (scheduler)."""
        session = event['data']['object']
        user_id = session['metadata']['user_id']
        setup_intent_id = session['setup_intent']

        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
        payment_method_id = setup_intent.payment_method
        trial_days = int(setup_intent.metadata.get("trial_days", get_trial_days()))

        user = db.query(User).filter(User.firebase_uid == user_id).first()
        if not user:
            print(f"BLIK setup: nie znaleziono usera {user_id}")
            return {"success": False, "error": "Nie znaleziono uzytkownika"}

        now = datetime.now(timezone.utc)
        next_charge = now + timedelta(days=trial_days)

        user.is_premium = True
        user.premium_until = next_charge
        db.commit()
        _update_firebase_plan(user_id, True)

        _upsert_blik_subscription_row(
            db, user_id,
            blik_payment_method_id=payment_method_id,
            status="trialing",
            current_period_start=now,
            current_period_end=next_charge,
            next_charge_at=next_charge,
            blik_charge_in_progress=False,
        )
        print(f"User {user_id} ustawiony jako PREMIUM (BLIK trial) do {next_charge}")

        affiliate_code = session.get('metadata', {}).get('affiliate_code')
        if affiliate_code:
            # Ta sama logika prowizji co karta - patrz
            # StripeService._handle_checkout_completed. Wydzielenie do
            # wspolnej funkcji to osobna, niezalezna poprawka - tutaj
            # celowo pominiete, zeby nie poszerzac zakresu tej zmiany.
            print(f"BLIK: kod polecajacy {affiliate_code} obecny, prowizja NIE naliczona (v1 - patrz TODO w kodzie)")

        return {"success": True, "message": "BLIK mandate saved, trial started"}

    @staticmethod
    def _handle_setup_failed(event: Dict, db: Session) -> Dict:
        """setup_intent.setup_failed - najczesciej "bank usera nie wspiera
        BLIK recurring". Nic nie bylo nadane, wiec nic nie cofamy - tylko
        log dla widocznosci."""
        setup_intent = event['data']['object']
        user_id = setup_intent.get('metadata', {}).get('user_id', '?')
        print(f"BLIK setup nieudany dla user {user_id}: {setup_intent.get('last_setup_error')}")
        return {"success": True, "message": "Setup failed logged"}

    @staticmethod
    def _find_row_by_payment_intent_metadata(event_object: Dict, db: Session) -> Optional[Subscription]:
        sub_row_id = event_object.get('metadata', {}).get('subscription_row_id')
        if not sub_row_id:
            return None
        return db.query(Subscription).filter(Subscription.id == int(sub_row_id)).first()

    @staticmethod
    def _handle_charge_succeeded(event: Dict, db: Session) -> Dict:
        """payment_intent.succeeded dla PaymentIntentow, ktore MY
        stworzylismy w charge_due_subscription (filtrowane po metadata
        blik_charge="true" w StripeService.handle_webhook przed wywolaniem
        tej funkcji)."""
        payment_intent = event['data']['object']
        row = BlikService._find_row_by_payment_intent_metadata(payment_intent, db)
        if not row:
            print(f"BLIK charge succeeded, ale nie znaleziono wiersza subskrypcji (PaymentIntent {payment_intent['id']})")
            return {"success": True, "message": "No matching subscription row"}

        # Idempotencja: jesli ten PaymentIntent juz zostal rozliczony
        # (np. duplikat dostawy webhooka), nie przesuwaj next_charge_at
        # drugi raz.
        if row.blik_last_payment_intent_id != payment_intent['id'] or not row.blik_charge_in_progress:
            print(f"BLIK charge succeeded: ignoruje powtorke webhooka dla wiersza {row.id}")
            return {"success": True, "message": "Duplicate webhook ignored"}

        now = datetime.now(timezone.utc)
        next_charge = now + timedelta(days=_RENEWAL_PERIOD_DAYS)
        row.status = "active"
        row.current_period_start = now
        row.current_period_end = next_charge
        row.next_charge_at = next_charge
        row.blik_charge_in_progress = False
        db.commit()

        user = db.query(User).filter(User.firebase_uid == row.user_id).first()
        if user:
            user.is_premium = True
            user.premium_until = next_charge
            db.commit()
            _update_firebase_plan(row.user_id, True)
        print(f"BLIK: obciazenie udane, user {row.user_id} przedluzony do {next_charge}")
        return {"success": True, "message": "BLIK charge succeeded"}

    @staticmethod
    def _handle_charge_failed(event: Dict, db: Session) -> Dict:
        """payment_intent.payment_failed dla naszych PaymentIntentow. v1:
        natychmiastowa utrata dostepu - identyczna filozofia co
        StripeService._handle_payment_failed dla karty ("bezpieczniej dla
        Ciebie finansowo" niz czekac/ponawiac)."""
        payment_intent = event['data']['object']
        row = BlikService._find_row_by_payment_intent_metadata(payment_intent, db)
        if not row:
            print(f"BLIK charge failed, ale nie znaleziono wiersza subskrypcji (PaymentIntent {payment_intent['id']})")
            return {"success": True, "message": "No matching subscription row"}

        row.status = "past_due"
        row.blik_charge_in_progress = False
        db.commit()

        user = db.query(User).filter(User.firebase_uid == row.user_id).first()
        if user:
            user.is_premium = False
            user.premium_until = None
            db.commit()
            _update_firebase_plan(row.user_id, False)
        print(f"BLIK: obciazenie nieudane, user {row.user_id} odebrany dostep premium")
        return {"success": True, "message": "BLIK charge failed handled"}

    @staticmethod
    def _handle_mandate_revoked(event: Dict, db: Session) -> Dict:
        """mandate.updated (active -> inactive) - user SAM cofnal zgode w
        swojej aplikacji bankowej, calkowicie niezaleznie od naszej apki.
        Webhook payload daje id mandatu, nie payment_method - trzeba
        rozwiazac mandate -> payment_method przez Stripe API."""
        mandate = event['data']['object']
        if mandate.get('status') != 'inactive':
            return {"success": True, "message": "Mandate update ignored (not inactive)"}

        payment_method_id = mandate.get('payment_method')
        if not payment_method_id:
            print(f"BLIK mandate.updated bez payment_method w payloadzie: {mandate.get('id')}")
            return {"success": True, "message": "No payment_method on mandate event"}

        row = db.query(Subscription).filter(
            Subscription.provider == "blik",
            Subscription.blik_payment_method_id == payment_method_id,
        ).first()
        if not row:
            print(f"BLIK mandate revoked, ale nie znaleziono wiersza dla payment_method {payment_method_id}")
            return {"success": True, "message": "No matching subscription row"}

        row.status = "canceled"
        row.canceled_at = datetime.now(timezone.utc)
        db.commit()

        user = db.query(User).filter(User.firebase_uid == row.user_id).first()
        if user:
            user.is_premium = False
            user.premium_until = None
            db.commit()
            _update_firebase_plan(row.user_id, False)
        print(f"BLIK: user {row.user_id} cofnal mandat w banku, odebrany dostep premium")
        return {"success": True, "message": "Mandate revocation handled"}

    @staticmethod
    def charge_due_subscription(db: Session, sub_row: Subscription) -> None:
        """Wywolywane WYLACZNIE przez codzienny scheduler
        (app/api/notifications.py, job 'blik_charge_sweep') - to jest
        miejsce, gdzie FAKTYCZNIE zlecamy pobranie pieniedzy. Wynik
        (sukces/porazka) przychodzi ASYNCHRONICZNIE webhookiem
        (_handle_charge_succeeded/_handle_charge_failed) - ta funkcja
        NIGDY nie zmienia status/is_premium bezposrednio (poza
        natychmiastowym wyjatkiem przy samym wywolaniu API)."""
        if sub_row.blik_charge_in_progress:
            print(f"BLIK: wiersz {sub_row.id} juz ma obciazenie w toku, pomijam")
            return

        sub_row.blik_charge_in_progress = True
        db.commit()

        try:
            amount, currency = _resolve_price_amount()
            payment_intent = stripe.PaymentIntent.create(
                customer=_customer_id_for_row(db, sub_row),
                payment_method=sub_row.blik_payment_method_id,
                amount=amount,
                currency=currency,
                off_session=True,
                confirm=True,
                automatic_payment_methods={"enabled": True},
                metadata={"blik_charge": "true", "subscription_row_id": str(sub_row.id)},
            )
            sub_row.blik_last_payment_intent_id = payment_intent.id
            db.commit()
            print(f"BLIK: PaymentIntent {payment_intent.id} utworzony dla wiersza {sub_row.id}, czekam na webhook")
        except Exception as e:
            # Synchroniczny blad przy samym wywolaniu API (np. mandat juz
            # znany jako martwy) - traktujemy jak natychmiastowa porazke,
            # zamiast czekac na webhook, ktory i tak nigdy nie nadejdzie.
            print(f"BLIK: blad przy tworzeniu PaymentIntent dla wiersza {sub_row.id}: {e}")
            sub_row.status = "past_due"
            sub_row.blik_charge_in_progress = False
            db.commit()
            user = db.query(User).filter(User.firebase_uid == sub_row.user_id).first()
            if user:
                user.is_premium = False
                user.premium_until = None
                db.commit()
                _update_firebase_plan(sub_row.user_id, False)

    @staticmethod
    def mark_canceled(db: Session, sub_row: Subscription) -> Dict:
        """Uzywane przez POST /cancel-subscription. W odroznieniu od karty
        (StripeService.cancel_subscription) NIE wolamy zadnego Stripe
        "cancel" API - nie ma obiektu Subscription do anulowania, jest
        tylko zapisana metoda platnosci. Po prostu oznaczamy wiersz, a
        scheduler (§4 planu) sam pomija wiersze z cancel_at_period_end."""
        sub_row.cancel_at_period_end = True
        db.commit()
        return {
            "success": True,
            "message": "Subskrypcja BLIK zostanie anulowana po zakonczeniu oplaconego okresu",
            "ends_at": sub_row.current_period_end.isoformat() if sub_row.current_period_end else None,
        }


def _customer_id_for_row(db: Session, sub_row: Subscription) -> str:
    """Subscription.stripe_customer_id jest nullable/nieuzywane dla BLIK
    (kolumna historycznie stripe-only) - klienta bierzemy z User."""
    user = db.query(User).filter(User.firebase_uid == sub_row.user_id).first()
    if not user or not user.stripe_customer_id:
        raise ValueError(f"Brak stripe_customer_id dla usera {sub_row.user_id}, nie mozna obciazyc BLIK")
    return user.stripe_customer_id


def charge_due_blik_subscriptions() -> None:
    """Codzienny sweep (wywolywany przez job 'blik_charge_sweep' w
    app/api/notifications.py, 03:00 Europe/Warsaw) - jedyne miejsce,
    ktore FAKTYCZNIE inicjuje pobranie pieniedzy z BLIK-a. Uzywa
    SessionLocal bezposrednio (nie FastAPI Depends(get_db)) - to nie jest
    request HTTP, tylko background job wywolywany przez APScheduler."""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Auto-zwolnienie "zawieszonej" blokady (proces padl w trakcie,
        # webhook nigdy nie nadszedl) - patrz plan, sekcja 4 punkt 3.
        stuck_cutoff = now - timedelta(hours=_STUCK_LOCK_HOURS)
        stuck = db.query(Subscription).filter(
            Subscription.provider == "blik",
            Subscription.blik_charge_in_progress == True,  # noqa: E712
            Subscription.updated_at < stuck_cutoff,
        ).all()
        for row in stuck:
            print(f"BLIK: zdejmuje zawieszona blokade dla wiersza {row.id} (proces prawdopodobnie padl)")
            row.blik_charge_in_progress = False
        if stuck:
            db.commit()

        due = db.query(Subscription).filter(
            Subscription.provider == "blik",
            Subscription.status.in_(["trialing", "active"]),
            Subscription.cancel_at_period_end == False,  # noqa: E712
            Subscription.next_charge_at <= now,
            Subscription.blik_charge_in_progress == False,  # noqa: E712
        ).all()

        print(f"BLIK sweep: {len(due)} subskrypcji do obciazenia")
        for row in due:
            try:
                BlikService.charge_due_subscription(db, row)
            except Exception as e:
                # Jeden zepsuty wiersz nie moze przerwac calego sweepu -
                # reszta userow musi zostac obciazona normalnie.
                print(f"BLIK sweep: blad przy wierszu {row.id}: {e}")
    finally:
        db.close()
