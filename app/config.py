import os
from dotenv import load_dotenv

# Załaduj .env
load_dotenv()

class Settings:
    """Ustawienia aplikacji"""
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    
    # Stripe
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # Apple In-App Purchase (wrzesien 2026, App Store Guideline 2.1(b) -
    # subskrypcja iOS MUSI isc przez StoreKit, nie Stripe). Klucz API
    # App Store Connect: Users and Access -> Integrations -> App Store
    # Connect API -> wygeneruj klucz z rola "App Manager" (wystarcza do
    # weryfikacji transakcji - NIE potrzeba pelnych uprawnien admina).
    # APPLE_IAP_PRIVATE_KEY to CALA zawartosc pobranego pliku .p8
    # (zaczyna sie od "-----BEGIN PRIVATE KEY-----"), wklejona wprost
    # jako zmienna srodowiskowa (ten sam wzorzec co FIREBASE_SERVICE_ACCOUNT_JSON).
    APPLE_BUNDLE_ID: str = os.getenv("APPLE_BUNDLE_ID", "com.eduvia.ios")
    # Numeryczne Apple ID APLIKACJI (NIE bundle_id!) - App Store Connect ->
    # Twoja apka -> App Information -> General Information -> "Apple ID"
    # (cyfry, np. "1234567890"). Wymagane przez biblioteke Apple dla
    # environment=Production (uzywane do weryfikacji online/OCSP).
    APPLE_APP_ID: str = os.getenv("APPLE_APP_ID", "")
    APPLE_IAP_KEY_ID: str = os.getenv("APPLE_IAP_KEY_ID", "")
    APPLE_IAP_ISSUER_ID: str = os.getenv("APPLE_IAP_ISSUER_ID", "")
    APPLE_IAP_PRIVATE_KEY: str = os.getenv("APPLE_IAP_PRIVATE_KEY", "")
    APPLE_IAP_ENVIRONMENT: str = os.getenv("APPLE_IAP_ENVIRONMENT", "Production")  # "Production" albo "Sandbox"

    # Database
    # NAPRAWIONE (31.08.2026): fallback byl WCZESNIEJ prawdziwym connection
    # stringiem do produkcyjnej/stagingowej bazy Supabase Z HASLEM WPROST W
    # KODZIE - i to repo jest PUBLICZNE na GitHubie, wiec haslo bylo jawnie
    # widoczne w historii commitow. Fallback teraz wskazuje na nieszkodliwy
    # lokalny sqlite - jesli SUPABASE_URL/DATABASE_URL nie sa ustawione (np.
    # brak .env), apka po prostu uzyje lokalnej bazy zamiast po cichu proowac
    # laczyc sie z prawdziwa baza produkcyjna zaszytym w kodzie haslem.
    DATABASE_URL: str = os.getenv("SUPABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./ai_teacher.db"))
    
    # App
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://eduvia-backend-2.onrender.com/static")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True") == "True"
    
    # Limity FREE vs PREMIUM
    FREE_PLANS_PER_MONTH: int = 10
    FREE_MESSAGES_PER_DAY: int = 50
    FREE_PDF_PER_DAY: int = 3

settings = Settings()

# Sprawdzenie przy starcie
if not settings.OPENAI_API_KEY:
    print("⚠️ BRAK OPENAI_API_KEY!")
    
if not settings.STRIPE_SECRET_KEY:
    print("⚠️ BRAK STRIPE_SECRET_KEY!")

if not settings.STRIPE_PRICE_ID:
    print("⚠️ BRAK STRIPE_PRICE_ID!")

print(f"✅ Config załadowany (env: {settings.ENVIRONMENT}, debug: {settings.DEBUG})")
print(f"💳 Stripe Price ID: {settings.STRIPE_PRICE_ID[:20]}..." if settings.STRIPE_PRICE_ID else "❌ BRAK PRICE ID")
