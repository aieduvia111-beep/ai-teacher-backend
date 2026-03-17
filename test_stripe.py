import stripe
import os
from dotenv import load_dotenv

# Załaduj .env
load_dotenv()

# Ustaw klucz API
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
price_id = os.getenv("STRIPE_PRICE_ID")

print("🧪 TEST POŁĄCZENIA ZE STRIPE")
print("=" * 60)
print(f"🔑 Secret Key: {stripe.api_key[:20]}..." if stripe.api_key else "❌ BRAK KLUCZA!")
print(f"📦 Price ID: {price_id}")
print()

try:
    # Pobierz dane o cenie
    price = stripe.Price.retrieve(price_id)
    
    # Pobierz dane o produkcie
    product = stripe.Product.retrieve(price.product)
    
    print("✅ POŁĄCZENIE DZIAŁA!")
    print()
    print(f"💎 Produkt: {product.name}")
    print(f"📝 Opis: {product.description[:60] if product.description else 'Brak opisu'}...")
    print(f"💰 Cena: {price.unit_amount / 100} {price.currency.upper()}")
    print(f"🔄 Okres: {price.recurring['interval']}")
    print(f"🎯 Price ID: {price.id}")
    print()
    print("🎉 WSZYSTKO GOTOWE DO INTEGRACJI!")
    
except stripe.error.AuthenticationError:
    print("❌ BŁĄD AUTORYZACJI!")
    print("Sprawdź czy STRIPE_SECRET_KEY jest poprawny w .env")
    
except stripe.error.InvalidRequestError as e:
    print("❌ BŁĄD: Price ID nie istnieje!")
    print(f"Szczegóły: {e}")
    print("Sprawdź czy STRIPE_PRICE_ID jest poprawny w .env")
    
except Exception as e:
    print(f"❌ NIEZNANY BŁĄD: {e}")

print("=" * 60)