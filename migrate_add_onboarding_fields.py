"""
Migracja: dodaje pola profilu ucznia (ankieta onboardingowa) do tabeli `users`.

Idempotentna - bezpieczna do wielokrotnego uruchomienia: sprawdza jakie
kolumny juz istnieja w tabeli `users` i dodaje TYLKO te, ktorych brakuje
wzgledem aktualnego modelu w app/models.py (ALTER TABLE ADD COLUMN) -
nie tylko 4 nowe pola onboardingu, ale KAZDA kolumne modelu User, ktorej
nie ma jeszcze w bazie. Dziala zarowno na SQLite (lokalny dev, patrz
.env) jak i na Postgresie (produkcja) - typ kolumny jest generowany z
definicji w app/models.py przez dialekt aktualnie skonfigurowanego
silnika.

Uzycie (lokalnie, z DATABASE_URL wskazujacym na sqlite - patrz .env):
    python migrate_add_onboarding_fields.py

WAZNE: ten skrypt laczy sie z baza danych wskazana przez DATABASE_URL
(app/config.py). Przed uruchomieniem sprawdz, na jaka baze wskazuje
aktualny .env - domyslnie (bez .env) byla to produkcyjna baza Supabase,
dlatego ten projekt ma teraz lokalny .env z DATABASE_URL=sqlite.
"""
from sqlalchemy import inspect, text
from app.database import engine
from app.models import User


def main():
    if engine is None:
        print("❌ Brak polaczenia z baza danych (silnik nie zostal utworzony).")
        return

    print(f"🗄️ Baza danych: {engine.url}")
    inspector = inspect(engine)

    if "users" not in inspector.get_table_names():
        print("ℹ️  Tabela 'users' jeszcze nie istnieje - tworze wszystkie tabele od zera.")
        User.metadata.create_all(bind=engine)
        print("✅ Tabele utworzone (nowe pola sa juz w niej od razu).")
        return

    existing = {col["name"] for col in inspector.get_columns("users")}
    dialect = engine.dialect

    with engine.begin() as conn:
        for column in User.__table__.columns:
            if column.name in existing:
                print(f"✓  users.{column.name} juz istnieje - pomijam")
                continue

            col_type = column.type.compile(dialect=dialect)
            ddl = f"ALTER TABLE users ADD COLUMN {column.name} {col_type}"
            print(f"➕ {ddl}")
            conn.execute(text(ddl))

    print("🎉 Migracja zakonczona.")


if __name__ == "__main__":
    main()
