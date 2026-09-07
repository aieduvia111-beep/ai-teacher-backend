"""APPLE IN-APP PURCHASE - weryfikacja transakcji StoreKit 2 (wrzesien 2026,
odpowiedz na odrzucenie App Store, Guideline 2.1(b): subskrypcja w natywnej
apce iOS MUSI isc przez Apple StoreKit, nie zewnetrzny procesor platnosci
jak Stripe).

Uzywa OFICJALNEJ biblioteki Apple (app-store-server-library, PyPI) do
kryptograficznej weryfikacji podpisanych (JWS) transakcji przeciwko
certyfikatowi glownemu Apple (app/certs/AppleRootCA-G3.cer) - NIGDY nie
ufamy samemu zgloszeniu klienta "zakup sie udal" bez weryfikacji podpisu,
bo to otwieraloby drzwi do sfalszowania zakupu bez placenia (klient moglby
po prostu wywolac onNativeIAPSuccess z dowolnym tekstem).

DWIE SCIEZKI (mirror architektury Stripe - patrz stripe_service.py):
1. grant_premium_from_client_transaction() - natychmiastowe nadanie Pro
   zaraz po udanym zakupie w apce (analog StripeService.verify_session/
   webhook checkout.session.completed) - wywolane z
   POST /api/v1/payments/verify-ios-purchase.
2. handle_server_notification() - cykl zycia subskrypcji w czasie
   (odnowienie/wygasniecie/refund/nieudane odnowienie) - Apple wysyla to
   NIEZALEZNIE od klienta na webhook (App Store Server Notifications V2),
   dokladnie jak Stripe webhook - patrz POST /api/v1/payments/apple-webhook.
   TO jest zrodlo prawdy dla dlugoterminowego stanu subskrypcji (klient
   moze byc offline/apka odinstalowana, gdy subskrypcja wygasnie)."""
import os
from datetime import datetime, timezone
from typing import Optional

from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.models.NotificationTypeV2 import NotificationTypeV2
from sqlalchemy.orm import Session

from ..config import settings
from ..models import User, Subscription
from .stripe_service import _update_firebase_plan

_CERTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "certs")


def _load_root_certificates() -> list:
    """Wczytuje WSZYSTKIE pliki .cer z app/certs/ jako bajty - biblioteka
    Apple wymaga ich WPROST (nie sciaga ich sama). Zrodlo:
    https://www.apple.com/certificateauthority/ (AppleRootCA-G3.cer -
    aktualny root dla lancucha podpisow StoreKit 2, sierpien/wrzesien 2026).
    Jesli Apple kiedys zmieni/doda root - dolozyc kolejny .cer do tego
    folderu, zero zmian w kodzie."""
    certs = []
    if os.path.isdir(_CERTS_DIR):
        for fname in sorted(os.listdir(_CERTS_DIR)):
            if fname.lower().endswith(".cer"):
                with open(os.path.join(_CERTS_DIR, fname), "rb") as f:
                    certs.append(f.read())
    return certs


_verifier: Optional[SignedDataVerifier] = None


def _get_verifier() -> SignedDataVerifier:
    """Leniwie tworzy (raz, cache'owane) SignedDataVerifier - tworzenie
    parsuje certyfikaty root, wiec robimy to raz, nie przy kazdym
    zadaniu. `enable_online_checks=True` - biblioteka dodatkowo sprawdza
    liste odwolanych certyfikatow Apple online (OCSP); wymaga wychodzacego
    polaczenia z serwera do appleid.apple.com/Apple CA - jesli produkcyjne
    srodowisko go blokuje, ustaw enable_online_checks=False (mniejsze
    bezpieczenstwo - nie wykryje odwolanego certyfikatu posredniego, ale
    nadal weryfikuje podpis i lancuch)."""
    global _verifier
    if _verifier is None:
        env = Environment.SANDBOX if settings.APPLE_IAP_ENVIRONMENT.strip().lower() == "sandbox" else Environment.PRODUCTION
        # app_apple_id (numeryczne Apple ID APLIKACJI, NIE bundle_id) jest
        # WYMAGANE przez biblioteke dla environment=Production - patrz
        # APPLE_APP_ID w config.py.
        app_apple_id = int(settings.APPLE_APP_ID) if settings.APPLE_APP_ID.strip().isdigit() else None
        _verifier = SignedDataVerifier(
            root_certificates=_load_root_certificates(),
            enable_online_checks=True,
            environment=env,
            bundle_id=settings.APPLE_BUNDLE_ID,
            app_apple_id=app_apple_id,
        )
    return _verifier


def _ms_to_datetime(ms: Optional[int]) -> Optional[datetime]:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _upsert_subscription_row(db: Session, firebase_uid: str, payload) -> Subscription:
    """Wspolna logika zapisu/aktualizacji wiersza Subscription dla obu
    sciezek (klient i webhook) - `originalTransactionId` jest stabilnym
    kluczem w calej historii subskrypcji (odnowienia dostaja NOWY
    transactionId, ale TEN SAM originalTransactionId)."""
    row = db.query(Subscription).filter(
        Subscription.apple_original_transaction_id == payload.originalTransactionId
    ).first()
    is_revoked = payload.revocationDate is not None
    status = "canceled" if is_revoked else "active"
    expires = _ms_to_datetime(payload.expiresDate)
    if row:
        row.user_id = firebase_uid
        row.status = status
        row.apple_product_id = payload.productId
        row.current_period_end = expires
        row.canceled_at = _ms_to_datetime(payload.revocationDate) if is_revoked else None
    else:
        row = Subscription(
            user_id=firebase_uid,
            provider="apple",
            apple_original_transaction_id=payload.originalTransactionId,
            apple_product_id=payload.productId,
            status=status,
            current_period_start=_ms_to_datetime(payload.purchaseDate),
            current_period_end=expires,
        )
        db.add(row)
    db.commit()
    return row


class AppleIAPService:

    @staticmethod
    def grant_premium_from_client_transaction(signed_transaction: str, firebase_uid: str, db: Session) -> dict:
        """Weryfikuje podpisana (JWS) transakcje zwrocona przez StoreKit 2
        PO UDANYM zakupie w apce (Transaction.jwsRepresentation, patrz
        IAPManager.swift) i, jesli poprawna i nieodwolana, nadaje Pro
        NATYCHMIAST - analog StripeService/verify_session dla Stripe.
        Prawdziwym, dlugoterminowym zrodlem prawdy o stanie subskrypcji
        pozostaje handle_server_notification() (webhook) - ta funkcja
        istnieje TYLKO po to, zeby user nie czekal na webhook (moze
        przyjsc z opoznieniem), zeby dostep odblokowal sie od razu."""
        try:
            payload = _get_verifier().verify_and_decode_signed_transaction(signed_transaction)
        except Exception as e:
            return {"success": False, "error": f"Nieprawidlowa lub niezweryfikowana transakcja: {e}"}

        if payload.bundleId != settings.APPLE_BUNDLE_ID:
            return {"success": False, "error": "Transakcja dla innej aplikacji (bundle_id mismatch)"}
        if payload.revocationDate is not None:
            return {"success": False, "error": "Ta transakcja zostala zwrocona (refund) - Pro NIE zostanie nadane"}

        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            return {"success": False, "error": "Nie znaleziono uzytkownika"}

        user.is_premium = True
        db.commit()
        _update_firebase_plan(firebase_uid, True)
        row = _upsert_subscription_row(db, firebase_uid, payload)

        return {
            "success": True,
            "plan": "pro",
            "product_id": payload.productId,
            "expires_at": row.current_period_end.isoformat() if row.current_period_end else None,
        }

    @staticmethod
    def handle_server_notification(signed_payload: str, db: Session) -> dict:
        """Odbiera i przetwarza App Store Server Notifications V2 (Apple
        wysyla to NIEZALEZNIE od klienta - jedyne wiarygodne zrodlo dla
        odnowien/wygasniec/refundow, ktore moga sie zdarzyc gdy user nie
        ma otwartej apki). Analog StripeService.handle_webhook.

        KONFIGURACJA (App Store Connect -> [Twoja apka] -> App Information
        -> App Store Server Notifications): ustaw Production/Sandbox URL na
        https://<twoj-backend>/api/v1/payments/apple-webhook - Apple
        zaczyna wtedy wysylac zdarzenia automatycznie."""
        try:
            notification = _get_verifier().verify_and_decode_notification(signed_payload)
        except Exception as e:
            return {"success": False, "error": f"Nieprawidlowe powiadomienie: {e}"}

        notif_type = notification.notificationType
        data = notification.data
        if data is None or not data.signedTransactionInfo:
            # Powiadomienia typu np. TEST/CONSUMPTION_REQUEST moga nie
            # miec danych transakcji - bezpieczny no-op, nie blad.
            return {"success": True, "handled": False, "reason": "brak signedTransactionInfo"}

        try:
            payload = _get_verifier().verify_and_decode_signed_transaction(data.signedTransactionInfo)
        except Exception as e:
            return {"success": False, "error": f"Nieprawidlowa transakcja w powiadomieniu: {e}"}

        # originalTransactionId jest stabilny - jesli mamy juz wiersz (z
        # grant_premium_from_client_transaction), wiemy do KTOREGO firebase_uid
        # nalezy. Jesli to PIERWSZE zdarzenie, jakie widzimy dla tej
        # transakcji (webhook wyprzedzil klienta), NIE znamy jeszcze
        # firebase_uid - w takim przypadku zapisujemy sam stan subskrypcji
        # bez przypisania do usera; grant_premium_from_client_transaction
        # (wywolane zaraz po tym przez klienta) dowiaze user_id.
        existing = db.query(Subscription).filter(
            Subscription.apple_original_transaction_id == payload.originalTransactionId
        ).first()
        firebase_uid = existing.user_id if existing else None

        row = _upsert_subscription_row(db, firebase_uid or "", payload)

        if firebase_uid:
            user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            if user:
                should_be_premium = notif_type not in (
                    NotificationTypeV2.EXPIRED, NotificationTypeV2.REFUND,
                    NotificationTypeV2.REVOKE, NotificationTypeV2.GRACE_PERIOD_EXPIRED,
                )
                if user.is_premium != should_be_premium:
                    user.is_premium = should_be_premium
                    db.commit()
                    _update_firebase_plan(firebase_uid, should_be_premium)

        return {"success": True, "handled": True, "notification_type": str(notif_type), "original_transaction_id": payload.originalTransactionId}
