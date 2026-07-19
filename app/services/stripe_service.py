import firebase_admin
from firebase_admin import credentials, firestore
import os

# Firebase Admin init
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH', 'firebase-service-account.json'))
        firebase_admin.initialize_app(cred)
    _fdb = firestore.client()
except Exception as _fe:
    print(f"Firebase Admin nie zaladowany: {_fe}")
    _fdb = None

def _update_firebase_plan(user_id: str, is_pro: bool):
    """Aktualizuje plan w Firebase Firestore"""
    if not _fdb:
        print("Brak Firebase Admin - pomijam aktualizacje Firebase")
        return
    try:
        _fdb.collection('users').document(user_id).set({
            'plan': 'pro' if is_pro else 'free',
            'premium_until': None if not is_pro else None
        }, merge=True)
        print(f"Firebase zaktualizowany: user {user_id} -> {'PRO' if is_pro else 'FREE'}")
    except Exception as e:
        print(f"Blad aktualizacji Firebase: {e}")

"""
Stripe SERVICE - Obsluga platnosci
NAPRAWIONA WERSJA - dodana brakujaca synchronizacja Firebase
"""

import stripe
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Dict, Optional

from ..config import settings
from ..models import User, Subscription

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Serwis do obslugi platnosci Stripe"""

    @staticmethod
    def create_checkout_session(user_id: str, email: str, db: Session, affiliate_code: str = "") -> Dict:
        try:
            print(f"Tworze checkout session dla user {user_id} ({email})")

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

            checkout_kwargs = {}
            checkout_metadata = {"user_id": user_id}
            if affiliate_code:
                code_clean = affiliate_code.upper().strip()
                if _fdb:
                    try:
                        aff_doc = _fdb.collection('affiliates').document(code_clean).get()
                        if aff_doc.exists and aff_doc.to_dict().get('active'):
                            checkout_kwargs["discounts"] = [{"coupon": "AFFILIATE10"}]
                            checkout_metadata["affiliate_code"] = code_clean
                            print(f"Kod polecajacy {code_clean} zwalidowany, rabat zastosowany")
                        else:
                            print(f"Kod polecajacy {code_clean} nieprawidlowy lub nieaktywny")
                    except Exception as _e:
                        print(f"Blad walidacji kodu polecajacego: {_e}")

            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
                mode="subscription",
                                success_url=f"{settings.FRONTEND_URL}/dashboard_FINAL.html?payment=success",
                cancel_url=f"{settings.FRONTEND_URL}/pricing.html?payment=cancelled",
                metadata=checkout_metadata,
                **checkout_kwargs
            )

            return {"success": True, "checkout_url": checkout_session.url, "session_id": checkout_session.id}

        except stripe.error.StripeError as e:
            print(f"Blad Stripe: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            print(f"Blad: {e}")
            return {"success": False, "error": str(e)}


    @staticmethod
    def handle_webhook(payload: bytes, sig_header: str, db: Session) -> Dict:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
            print(f"Webhook otrzymany: {event['type']}")

            if event['type'] == 'checkout.session.completed':
                return StripeService._handle_checkout_completed(event, db)
            elif event['type'] == 'customer.subscription.updated':
                return StripeService._handle_subscription_updated(event, db)
            elif event['type'] == 'customer.subscription.deleted':
                return StripeService._handle_subscription_deleted(event, db)
            elif event['type'] == 'invoice.payment_failed':
                return StripeService._handle_payment_failed(event, db)

            return {"success": True, "message": f"Event {event['type']} received"}

        except ValueError as e:
            print(f"Invalid payload: {e}")
            return {"success": False, "error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            print(f"Invalid signature: {e}")
            return {"success": False, "error": "Invalid signature"}


    @staticmethod
    def _handle_checkout_completed(event: Dict, db: Session) -> Dict:
        """Obsluguje zakonczenie checkout - nowa subskrypcja"""
        session = event['data']['object']
        user_id = session['metadata']['user_id']

        subscription_id = session['subscription']
        subscription = stripe.Subscription.retrieve(subscription_id)

        user = db.query(User).filter(User.firebase_uid == user_id).first()
        if user:
            user.is_premium = True
            user.premium_until = datetime.fromtimestamp(subscription.current_period_end)
            db.commit()
            _update_firebase_plan(user_id, True)  # <- JUZ BYLO OK
            print(f"User {user_id} ustawiony jako PREMIUM do {user.premium_until}")

        db_subscription = Subscription(
            user_id=user_id,
            stripe_subscription_id=subscription.id,
            stripe_customer_id=subscription.customer,
            stripe_price_id=subscription['items']['data'][0]['price']['id'],
            status=subscription.status,
            current_period_start=datetime.fromtimestamp(subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(subscription.current_period_end)
        )
        db.add(db_subscription)
        db.commit()

        affiliate_code = session.get('metadata', {}).get('affiliate_code')
        if affiliate_code and _fdb:
            try:
                amount = 26.10
                commission = round(amount * 0.30, 2)
                aff_ref = _fdb.collection('affiliates').document(affiliate_code)
                aff_doc = aff_ref.get()
                if aff_doc.exists:
                    data = aff_doc.to_dict()
                    aff_ref.update({
                        "sales": data.get("sales", 0) + 1,
                        "earnings": round(data.get("earnings", 0) + commission, 2)
                    })
                    _fdb.collection('affiliate_sales').add({
                        "code": affiliate_code,
                        "amount": amount,
                        "commission": commission,
                        "buyer_uid": user_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    print(f"Prowizja {commission} zl naliczona dla kodu {affiliate_code}")
            except Exception as _e:
                print(f"Blad naliczania prowizji: {_e}")

        return {"success": True, "message": "Subscription created"}


    @staticmethod
    def _handle_subscription_updated(event: Dict, db: Session) -> Dict:
        """Obsluguje aktualizacje subskrypcji"""
        subscription = event['data']['object']
        stripe_sub_id = subscription['id']

        db_sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if db_sub:
            db_sub.status = subscription['status']
            db_sub.current_period_end = datetime.fromtimestamp(subscription['current_period_end'])
            db_sub.cancel_at_period_end = subscription.get('cancel_at_period_end', False)

            user = db.query(User).filter(User.id == db_sub.user_id).first()
            new_premium_status = None
            if user:
                if subscription['status'] in ('active', 'trialing'):
                    user.is_premium = True
                    user.premium_until = db_sub.current_period_end
                    new_premium_status = True
                else:
                    # status = past_due, unpaid, canceled, incomplete_expired itp.
                    # (dokladnie to sie dzieje gdy platnosc przy odnowieniu sie nie powiedzie)
                    user.is_premium = False
                    user.premium_until = None
                    new_premium_status = False

            # Kolejnosc ma znaczenie: najpierw zapisujemy do SQL (zrodlo prawdy),
            # dopiero PO udanym commit synchronizujemy Firebase. Gdyby robic to
            # w odwrotnej kolejnosci, a zapis do SQL by sie nie powiodl - Firebase
            # i SQL moglyby pokazywac sprzeczne dane.
            db.commit()
            if user and new_premium_status is not None:
                _update_firebase_plan(user.firebase_uid, new_premium_status)
            print(f"Subskrypcja zaktualizowana -> status: {subscription['status']}")

        return {"success": True, "message": "Subscription updated"}


    @staticmethod
    def _handle_subscription_deleted(event: Dict, db: Session) -> Dict:
        """Obsluguje anulowanie/wygasniecie subskrypcji"""
        subscription = event['data']['object']
        stripe_sub_id = subscription['id']

        db_sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if db_sub:
            db_sub.status = 'canceled'
            db_sub.canceled_at = datetime.utcnow()

            user = db.query(User).filter(User.id == db_sub.user_id).first()
            if user:
                user.is_premium = False
                user.premium_until = None

            # ===== NAPRAWA (GLOWNA PRZYCZYNA ZGLOSZONEGO PROBLEMU) =====
            # Wczesniej ten fragment w ogole nie aktualizowal Firebase - SQL
            # poprawnie ustawial is_premium=False, ale Firebase (skad apka
            # rzeczywiscie sprawdza dostep) nigdy sie o tym nie dowiadywal.
            # Dodatkowo: najpierw zapisujemy do SQL, dopiero PO commit
            # synchronizujemy Firebase (bezpieczniejsza kolejnosc).
            db.commit()
            if user:
                _update_firebase_plan(user.firebase_uid, False)
            print(f"User {db_sub.user_id} wrocil do FREE (subskrypcja usunieta)")

        return {"success": True, "message": "Subscription canceled"}


    @staticmethod
    def _handle_payment_failed(event: Dict, db: Session) -> Dict:
        """
        NOWA FUNKCJA - obsluguje nieudana platnosc (np. odrzucona karta przy odnowieniu).
        Stripe NIE zawsze od razu usuwa subskrypcje po nieudanej platnosci - czasem
        probuje ponowic obciazenie przez kilka dni (status 'past_due'). Zamiast czekac
        az Stripe finalnie skasuje subskrypcje, od razu odbieramy dostep premium
        w momencie pierwszej nieudanej platnosci - bezpieczniej dla Ciebie finansowo.
        """
        invoice = event['data']['object']
        stripe_sub_id = invoice.get('subscription')

        if not stripe_sub_id:
            return {"success": True, "message": "Brak subscription_id w fakturze"}

        db_sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if db_sub:
            user = db.query(User).filter(User.id == db_sub.user_id).first()
            if user:
                user.is_premium = False
                user.premium_until = None
                db.commit()
                _update_firebase_plan(user.firebase_uid, False)
                print(f"User {db_sub.user_id} odebrany dostep premium (nieudana platnosc)")

        return {"success": True, "message": "Payment failed handled"}


    @staticmethod
    def cancel_subscription(user_id: int, db: Session) -> Dict:
        """Anuluje subskrypcje uzytkownika (na koniec okresu rozliczeniowego)"""
        try:
            subscription = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.status.in_(['active', 'trialing'])
            ).first()

            if not subscription:
                return {"success": False, "error": "Nie znaleziono aktywnej subskrypcji"}

            stripe.Subscription.modify(subscription.stripe_subscription_id, cancel_at_period_end=True)

            subscription.cancel_at_period_end = True
            db.commit()

            return {
                "success": True,
                "message": "Subskrypcja zostanie anulowana po zakonczeniu okresu rozliczeniowego",
                "ends_at": subscription.current_period_end.isoformat()
            }

        except Exception as e:
            print(f"Blad anulowania: {e}")
            return {"success": False, "error": str(e)}
