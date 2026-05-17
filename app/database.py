from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# 🗄️ Utwórz silnik bazy danych
is_sqlite = "sqlite" in settings.DATABASE_URL

try:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False} if is_sqlite else {},
        pool_pre_ping=True,
        pool_recycle=300,
        pool_timeout=10,
        pool_size=3,
        max_overflow=5,
    )
    print("✅ Baza danych OK")
except Exception as e:
    print(f"⚠️ Baza danych niedostepna: {e}")
    engine = None

# 📦 Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 🏗️ Base dla modeli
Base = declarative_base()

# 🔌 Dependency dla FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Import models to create tables
from . import models  # noqa
