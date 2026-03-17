from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# 🗄️ Utwórz silnik bazy danych
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

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