"""
💳 STRIPE SERVICE - Obsługa płatności
Dzień 6: Integracja Stripe Payments
"""

import stripe
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Dict, Optional

from ..config import settings
from ..models import User, Subscription

# Inicjalizacja Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Serwis do obsługi płatności Stripe"""
    
    @staticmethod
    def create_checkout_session(
        user_id: int,
        email: str,
        db: Session
    ) -> Dict:
        """
        Tworzy sesję checkout Stripe
        
        Args:
            user_id: ID użytkownika
            email: Email użytkownika
            db: Database session
            
        Returns:
            Dict z URL do checkout
        """
        try:
            print(f"💳 Tworzę checkout session dla user {user_id} ({email})")
            
            # Sprawdź czy user ma już Stripe Customer ID
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                # Stwórz nowego usera jeśli nie istnieje
                user = User(
                    id=user_id,
                    email=email,
                    is_premium=False
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            
            # Stwórz lub pobierz Stripe Customer
            if user.stripe_customer_id:
                customer_id = user.stripe_customer_id
                print(f"✅ Użytkownik ma już Stripe Customer: {customer_id}")
            else:
                # Stwórz nowego customera w Stripe
                customer = stripe.Customer.create(
                    email=email,
                    metadata={"user_id": user_id}
                )
                customer_id = customer.id
                
                # Zapisz w bazie
                user.stripe_customer_id = customer_id
                db.commit()
                
                print(f"✅ Stworzono nowego Stripe Customer: {customer_id}")
            
            # Stwórz Checkout Session
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": settings.STRIPE_PRICE_ID,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url="http://localhost:8000/static/success.html?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="http://localhost:8000/static/cancel.html",
                metadata={
                    "user_id": user_id
                }
            )
            
            print(f"✅ Checkout session utworzona: {checkout_session.id}")
            
            return {
                "success": True,
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id
            }
            
        except stripe.error.StripeError as e:
            print(f"❌ Błąd Stripe: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            print(f"❌ Błąd: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    @staticmethod
    def handle_webhook(
        payload: bytes,
        sig_header: str,
        db: Session
    ) -> Dict:
        """
        Obsługuje webhooks ze Stripe
        
        Args:
            payload: Raw request body
            sig_header: Stripe signature header
            db: Database session
            
        Returns:
            Dict z rezultatem
        """
        try:
            # Weryfikuj webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            
            print(f"🔔 Webhook otrzymany: {event['type']}")
            
            # Obsłuż różne typy eventów
            if event['type'] == 'checkout.session.completed':
                return StripeService._handle_checkout_completed(event, db)
                
            elif event['type'] == 'customer.subscription.updated':
                return StripeService._handle_subscription_updated(event, db)
                
            elif event['type'] == 'customer.subscription.deleted':
                return StripeService._handle_subscription_deleted(event, db)
            
            return {"success": True, "message": f"Event {event['type']} received"}
            
        except ValueError as e:
            print(f"❌ Invalid payload: {e}")
            return {"success": False, "error": "Invalid payload"}
            
        except stripe.error.SignatureVerificationError as e:
            print(f"❌ Invalid signature: {e}")
            return {"success": False, "error": "Invalid signature"}
    
    
    @staticmethod
    def _handle_checkout_completed(event: Dict, db: Session) -> Dict:
        """Obsługuje zakończenie checkout - nowa subskrypcja"""
        
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        
        print(f"✅ Checkout completed dla user {user_id}")
        
        # Pobierz szczegóły subskrypcji
        subscription_id = session['subscription']
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Zaktualizuj usera
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_premium = True
            user.premium_until = datetime.fromtimestamp(subscription.current_period_end)
            db.commit()
            
            print(f"✅ User {user_id} ustawiony jako PREMIUM do {user.premium_until}")
        
        # Zapisz subskrypcję
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
        
        print(f"✅ Subskrypcja zapisana w bazie")
        
        return {"success": True, "message": "Subscription created"}
    
    
    @staticmethod
    def _handle_subscription_updated(event: Dict, db: Session) -> Dict:
        """Obsługuje aktualizację subskrypcji"""
        
        subscription = event['data']['object']
        stripe_sub_id = subscription['id']
        
        print(f"🔄 Aktualizacja subskrypcji {stripe_sub_id}")
        
        # Znajdź subskrypcję w bazie
        db_sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()
        
        if db_sub:
            # Zaktualizuj status
            db_sub.status = subscription['status']
            db_sub.current_period_end = datetime.fromtimestamp(subscription['current_period_end'])
            db_sub.cancel_at_period_end = subscription.get('cancel_at_period_end', False)
            
            # Zaktualizuj usera
            user = db.query(User).filter(User.id == db_sub.user_id).first()
            if user:
                if subscription['status'] == 'active':
                    user.is_premium = True
                    user.premium_until = db_sub.current_period_end
                else:
                    user.is_premium = False
                    user.premium_until = None
            
            db.commit()
            print(f"✅ Subskrypcja zaktualizowana")
        
        return {"success": True, "message": "Subscription updated"}
    
    
    @staticmethod
    def _handle_subscription_deleted(event: Dict, db: Session) -> Dict:
        """Obsługuje anulowanie subskrypcji"""
        
        subscription = event['data']['object']
        stripe_sub_id = subscription['id']
        
        print(f"❌ Anulowanie subskrypcji {stripe_sub_id}")
        
        # Znajdź subskrypcję
        db_sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()
        
        if db_sub:
            db_sub.status = 'canceled'
            db_sub.canceled_at = datetime.utcnow()
            
            # Zaktualizuj usera
            user = db.query(User).filter(User.id == db_sub.user_id).first()
            if user:
                user.is_premium = False
                user.premium_until = None
            
            db.commit()
            print(f"✅ User {db_sub.user_id} wrócił do FREE")
        
        return {"success": True, "message": "Subscription canceled"}
    
    
    @staticmethod
    def cancel_subscription(
        user_id: int,
        db: Session
    ) -> Dict:
        """Anuluje subskrypcję użytkownika"""
        
        try:
            # Znajdź aktywną subskrypcję
            subscription = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.status == 'active'
            ).first()
            
            if not subscription:
                return {
                    "success": False,
                    "error": "Nie znaleziono aktywnej subskrypcji"
                }
            
            # Anuluj w Stripe (na końcu okresu)
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Zaktualizuj w bazie
            subscription.cancel_at_period_end = True
            db.commit()
            
            print(f"✅ Subskrypcja zostanie anulowana po końcu okresu")
            
            return {
                "success": True,
                "message": "Subskrypcja zostanie anulowana po zakończeniu okresu rozliczeniowego",
                "ends_at": subscription.current_period_end.isoformat()
            }
            
        except Exception as e:
            print(f"❌ Błąd anulowania: {e}")
            return {
                "success": False,
                "error": str(e)
            }
