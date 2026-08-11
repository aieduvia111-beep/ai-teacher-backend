"""
💳 PAYMENTS API - Endpointy płatności Stripe
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..services.stripe_service import StripeService
from ..models import User, Subscription
from ..services.stripe_service import _update_firebase_plan
from ..firebase_auth import get_verified_firebase_user
import stripe

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateCheckoutRequest(BaseModel):
    """Request do stworzenia checkout session"""
    user_id: str
    email: str
    affiliate_code: str = ""

class CheckoutResponse(BaseModel):
    """Response z checkout URL"""
    success: bool
    checkout_url: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None

# =============================================================================
# ENDPOINTY
# =============================================================================

class VerifySessionRequest(BaseModel):
    session_id: str

@router.post("/verify-session")
def verify_session(request: VerifySessionRequest):
    """
    Weryfikuje platnosc Stripe PO STRONIE SERWERA (bezpiecznie) i dopiero
    po potwierdzeniu ustawia plan=pro w Firestore.
    """
    try:
        session = stripe.checkout.Session.retrieve(request.session_id)
        if session.payment_status != "paid":
            return {"success": False, "error": "Platnosc nie zostala potwierdzona"}
        firebase_uid = session.metadata.get("user_id")
        if not firebase_uid:
            return {"success": False, "error": "Brak identyfikatora uzytkownika w sesji"}
        _update_firebase_plan(firebase_uid, True)
        return {"success": True, "plan": "pro"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/create-checkout")
def create_checkout(
    request: CreateCheckoutRequest,
    db: Session = Depends(get_db),
    firebase_user: dict = Depends(get_verified_firebase_user),
):
    """
    💳 Tworzy Stripe Checkout Session

    Wymaga naglowka: Authorization: Bearer <firebase_id_token>
    user_id/email brane sa z zweryfikowanego tokenu, nie z body requestu
    (zapobiega tworzeniu sesji platnosci w imieniu cudzego konta).

    Returns:
    {
        "success": true,
        "checkout_url": "https://checkout.stripe.com/...",
        "session_id": "cs_..."
    }
    """
    try:
        verified_uid = firebase_user["uid"]
        verified_email = firebase_user.get("email") or request.email
        print(f"💳 Request checkout dla user {verified_uid}")

        result = StripeService.create_checkout_session(
            user_id=verified_uid,
            email=verified_email,
            db=db,
            affiliate_code=request.affiliate_code
        )
        
        return result
        
    except Exception as e:
        print(f"❌ Błąd w create_checkout: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db)
):
    """
    🔔 Webhook endpoint dla Stripe
    
    Stripe wysyła tutaj powiadomienia o płatnościach
    
    WAŻNE: Ten endpoint NIE wymaga autoryzacji!
    Weryfikacja odbywa się przez Stripe signature
    """
    try:
        # Pobierz raw body (potrzebne do weryfikacji signature)
        payload = await request.body()
        
        print(f"🔔 Webhook otrzymany (signature: {stripe_signature[:20]}...)")
        
        # Obsłuż webhook
        result = StripeService.handle_webhook(
            payload=payload,
            sig_header=stripe_signature,
            db=db
        )
        
        return result
        
    except Exception as e:
        print(f"❌ Błąd webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel-subscription")
def cancel_subscription(
    db: Session = Depends(get_db),
    firebase_user: dict = Depends(get_verified_firebase_user),
):
    """
    ❌ Anuluje subskrypcję zalogowanego użytkownika

    Wymaga naglowka: Authorization: Bearer <firebase_id_token>
    Zawsze anuluje subskrypcje wlasciciela tokenu - nie da sie juz
    podac cudzego user_id w body.

    Subskrypcja zostanie anulowana na koniec okresu rozliczeniowego
    """
    try:
        result = StripeService.cancel_subscription(
            user_id=firebase_user["uid"],
            db=db
        )
        
        return result
        
    except Exception as e:
        print(f"❌ Błąd anulowania: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/subscription")
def get_subscription(
    db: Session = Depends(get_db),
    firebase_user: dict = Depends(get_verified_firebase_user),
):
    """
    📊 Pobiera informacje o subskrypcji zalogowanego użytkownika

    Wymaga naglowka: Authorization: Bearer <firebase_id_token>
    Zwraca zawsze dane wlasciciela tokenu - nie da sie juz podejrzec
    subskrypcji innego uzytkownika przez podanie jego ID w URL.

    Returns:
    {
        "success": true,
        "is_premium": true,
        "premium_until": "2026-03-15T...",
        "subscription": { ... }
    }
    """
    try:
        user_id = firebase_user["uid"]
        # Pobierz usera
        user = db.query(User).filter(User.firebase_uid == user_id).first()

        if not user:
            return {
                "success": False,
                "error": "User nie znaleziony"
            }

        # Pobierz aktywną subskrypcję
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(['active', 'trialing'])
        ).first()
        
        result = {
            "success": True,
            "is_premium": user.is_premium,
            "premium_until": user.premium_until.isoformat() if user.premium_until else None,
        }
        
        if subscription:
            result["subscription"] = {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end.isoformat(),
                "cancel_at_period_end": subscription.cancel_at_period_end
            }
        else:
            result["subscription"] = None
        
        return result
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return {
            "success": False,
            "error": str(e)
        }