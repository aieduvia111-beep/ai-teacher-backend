import os
from dotenv import load_dotenv

# Załaduj .env
load_dotenv()

class Settings:
    """Ustawienia aplikacji"""
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Stripe
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ai_teacher.db")
    
    # App
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
