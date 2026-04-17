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

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateCheckoutRequest(BaseModel):
    """Request do stworzenia checkout session"""
    user_id: str
    email: str

class CheckoutResponse(BaseModel):
    """Response z checkout URL"""
    success: bool
    checkout_url: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None

class CancelSubscriptionRequest(BaseModel):
    """Request do anulowania subskrypcji"""
    user_id: str


# =============================================================================
# ENDPOINTY
# =============================================================================

@router.post("/create-checkout")
def create_checkout(
    request: CreateCheckoutRequest,
    db: Session = Depends(get_db)
):
    """
    💳 Tworzy Stripe Checkout Session
    
    Example:
    POST /api/v1/payments/create-checkout
    {
        "user_id": "test_uid",
        "email": "user@example.com"
    }
    
    Returns:
    {
        "success": true,
        "checkout_url": "https://checkout.stripe.com/...",
        "session_id": "cs_..."
    }
    """
    try:
        print(f"💳 Request checkout dla user {request.user_id}")
        
        result = StripeService.create_checkout_session(
            user_id=request.user_id,
            email=request.email,
            db=db
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
    request: CancelSubscriptionRequest,
    db: Session = Depends(get_db)
):
    """
    ❌ Anuluje subskrypcję użytkownika
    
    Example:
    POST /api/v1/payments/cancel-subscription
    {
        "user_id": 1
    }
    
    Subskrypcja zostanie anulowana na koniec okresu rozliczeniowego
    """
    try:
        result = StripeService.cancel_subscription(
            user_id=request.user_id,
            db=db
        )
        
        return result
        
    except Exception as e:
        print(f"❌ Błąd anulowania: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/subscription/{user_id}")
def get_subscription(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    📊 Pobiera informacje o subskrypcji użytkownika
    
    Example:
    GET /api/v1/payments/subscription/1
    
    Returns:
    {
        "success": true,
        "is_premium": true,
        "premium_until": "2026-03-15T...",
        "subscription": { ... }
    }
    """
    try:
        # Pobierz usera
        user = db.query(User).filter(User.id == user_id).first()
        
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