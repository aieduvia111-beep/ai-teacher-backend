"""
💳 PAYMENTS API - Endpointy płatności Stripe
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..services.stripe_service import StripeService
from ..services.apple_iap_service import AppleIAPService
from ..models import User, Subscription
from ..services.stripe_service import _update_firebase_plan, get_promo_status
from ..firebase_auth import get_verified_firebase_user
import stripe

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.get("/trial-info")
async def trial_info():
    """PROMOCJA (07.09.2026, patrz stala PROMO_DEADLINE w stripe_service.py) -
    publiczny (bez autoryzacji - to tylko tekst marketingowy, nie dane usera)
    endpoint zwracajacy AKTUALNA dlugosc darmowego triala (Android/Web) i
    status promocji, zeby frontend (pricing.html, trial_promo_modal.js,
    limit_modal.js) mogl pokazac DOKLADNIE ta sama liczbe dni i to samo
    odliczanie czasu, ktore faktycznie dostanie user po kliknieciu
    Subskrybuj (get_trial_days() jest wolane W TYM SAMYM momencie tam)."""
    return get_promo_status()


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

    NOWE (wrzesien 2026, App Store IAP): subskrypcje Apple (provider="apple")
    NIE MOGA byc anulowane przez nasz backend - Apple celowo NIE udostepnia
    takiej mozliwosci w App Store Server API (w odroznieniu od Stripe).
    User musi anulowac przez Ustawienia iOS (Apple ID -> Subskrypcje) albo
    natywny przycisk "Zarzadzaj subskrypcja" w apce (AppStore.
    showManageSubscriptions() po stronie Swift) - zwracamy jasny komunikat
    zamiast probowac (i failowac) wolac Stripe API dla subskrypcji, ktora
    nigdy tam nie istniala.
    """
    try:
        apple_sub = db.query(Subscription).filter(
            Subscription.user_id == firebase_user["uid"],
            Subscription.provider == "apple",
            Subscription.status.in_(["active"]),
        ).first()
        if apple_sub:
            return {
                "success": False,
                "error": "apple_managed",
                "message": "Ta subskrypcja zostala kupiona przez App Store i musi byc anulowana przez Ustawienia iOS (Apple ID -> Subskrypcje) albo przycisk 'Zarzadzaj subskrypcja' w aplikacji.",
            }

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
                "provider": subscription.provider,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
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


# =============================================================================
# APPLE IN-APP PURCHASE (wrzesien 2026, App Store Guideline 2.1(b))
# =============================================================================

class VerifyIOSPurchaseRequest(BaseModel):
    transaction_id: str  # w rzeczywistosci CALY podpisany JWS (Transaction.jwsRepresentation), nie sama liczba - patrz IAPManager.swift


@router.post("/verify-ios-purchase")
def verify_ios_purchase(
    request: VerifyIOSPurchaseRequest,
    db: Session = Depends(get_db),
    firebase_user: dict = Depends(get_verified_firebase_user),
):
    """
    🍎 Weryfikuje zakup StoreKit 2 zaraz po jego zakonczeniu w apce iOS i
    nadaje Pro - natywny odpowiednik /verify-session (Stripe).

    Wymaga naglowka: Authorization: Bearer <firebase_id_token>. `transaction_id`
    w body to w rzeczywistosci CALY podpisany JWS zwrocony przez StoreKit
    (Transaction.jwsRepresentation) - weryfikowany kryptograficznie po
    stronie serwera (app/services/apple_iap_service.py) PRZED nadaniem Pro,
    nigdy nie ufamy samemu zgloszeniu klienta.
    """
    try:
        result = AppleIAPService.grant_premium_from_client_transaction(
            signed_transaction=request.transaction_id,
            firebase_uid=firebase_user["uid"],
            db=db,
        )
        return result
    except Exception as e:
        print(f"❌ Błąd weryfikacji zakupu iOS: {e}")
        return {"success": False, "error": str(e)}


@router.post("/apple-webhook")
async def apple_webhook(request: Request, db: Session = Depends(get_db)):
    """
    🔔 Webhook endpoint dla Apple App Store Server Notifications V2 -
    natywny odpowiednik /webhook (Stripe). Apple wysyla tu zdarzenia
    cyklu zycia subskrypcji (odnowienie/wygasniecie/refund/nieudane
    odnowienie) NIEZALEZNIE od tego, czy user ma otwarta apke - to
    JEDYNE wiarygodne zrodlo prawdy dla dlugoterminowego stanu.

    WAZNE: ten endpoint NIE wymaga naglowka Authorization (Apple nie
    wysyla tokenu Firebase) - autentycznosc jest weryfikowana przez
    podpis kryptograficzny (JWS) samego payloadu, dokladnie jak Stripe
    signature dla /webhook.

    KONFIGURACJA: App Store Connect -> Twoja apka -> App Information ->
    App Store Server Notifications -> ustaw Production/Sandbox URL na
    https://<twoj-backend>/api/v1/payments/apple-webhook
    """
    try:
        body = await request.json()
        signed_payload = body.get("signedPayload")
        if not signed_payload:
            raise HTTPException(status_code=400, detail="Brak signedPayload")
        result = AppleIAPService.handle_server_notification(signed_payload, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Błąd webhook Apple: {e}")
        raise HTTPException(status_code=400, detail=str(e))