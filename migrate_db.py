from app.database import Base, engine
from app.models import User, Subscription, UsageStats, Lesson

print("🗄️ Tworzę tabele w bazie danych...")
print("=" * 60)

try:
    # Utwórz wszystkie tabele
    Base.metadata.create_all(bind=engine)
    
    print("✅ Tabele utworzone pomyślnie!")
    print()
    
    # Sprawdź jakie tabele są w bazie
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print(f"📊 Znaleziono {len(tables)} tabel:")
    for table in tables:
        print(f"  ✓ {table}")
    
    print()
    print("🎉 Baza danych gotowa!")
    
except Exception as e:
    print(f"❌ Błąd: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)