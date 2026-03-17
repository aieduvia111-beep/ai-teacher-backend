import os
from dotenv import load_dotenv

# Załaduj .env
load_dotenv()

print("🧪 TEST ZAŁADOWANIA .env")
print("=" * 60)

# Sprawdź każdy klucz
keys_to_check = [
    "OPENAI_API_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_PRICE_ID",
    "DATABASE_URL",
    "ENVIRONMENT"
]

for key in keys_to_check:
    value = os.getenv(key, "")
    
    if value:
        # Pokaż tylko pierwsze 20 znaków (bezpieczeństwo)
        preview = value[:20] + "..." if len(value) > 20 else value
        print(f"✅ {key}: {preview}")
    else:
        print(f"❌ {key}: BRAK!")

print("=" * 60)