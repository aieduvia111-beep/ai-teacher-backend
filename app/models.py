from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


# =============================================================================
# LESSON & REVIEW MODELS (DZIEŃ 5)
# =============================================================================

class Lesson(Base):
    """Plan nauki stworzony przez AI"""
    __tablename__ = "lessons"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), index=True)
    
    # Basic info
    title = Column(String(200), nullable=False)
    subject = Column(String(100), nullable=False)
    level = Column(String(50), nullable=False)
    
    # Time planning
    total_days = Column(Integer, nullable=False)
    minutes_per_day = Column(Integer, nullable=False)
    
    # Content (cały plan w JSON)
    content = Column(JSON, nullable=False)
    
    # Progress
    is_completed = Column(Boolean, default=False)
    completion_date = Column(DateTime, nullable=True)
    current_day = Column(Integer, default=1)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reviews = relationship("Review", back_populates="lesson")


class Review(Base):
    """Spaced Repetition - powtórki"""
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    user_id = Column(Integer, index=True)
    
    # Topic
    topic = Column(String(200), nullable=False)
    
    # Scheduling
    scheduled_for = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # SM-2 Algorithm
    easiness_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    review_count = Column(Integer, default=0)
    next_review = Column(DateTime, nullable=True)
    
    # User response (0-5)
    quality = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lesson = relationship("Lesson", back_populates="reviews")


# =============================================================================
# USER & PAYMENT MODELS (DZIEŃ 6)
# =============================================================================

class User(Base):
    """Model użytkownika z obsługą płatności"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    firebase_uid = Column(String(255), unique=True, index=True, nullable=True)

    # Stripe
    stripe_customer_id = Column(String(255), unique=True, nullable=True)
    
    # Premium status
    is_premium = Column(Boolean, default=False)
    daily_usage = Column(Text, default='{}')
    voice_seconds_today = Column(Integer, default=0)
    voice_usage_date = Column(String(10), nullable=True)
    premium_until = Column(DateTime(timezone=True), nullable=True)
    fcm_token = Column(String(255), nullable=True)
    last_notification_sent = Column(DateTime(timezone=True), nullable=True)

    # Profil ucznia (ankieta onboardingowa)
    # education_level - klucz z app/level_config.py, np. "liceum_2", "matura_rozszerzona"
    education_level = Column(String(30), nullable=True)
    favorite_subject = Column(String(50), nullable=True)
    exam_date = Column(DateTime(timezone=True), nullable=True)
    onboarding_completed = Column(Boolean, default=False)

    # Sugerowany Quiz na Dashboardzie ("Nastepny krok") - konkretny temat
    # (nie tylko nazwa przedmiotu), zmieniany raz dziennie. Wzorowane na
    # voice_usage_date (String YYYY-MM-DD zamiast DateTime, bo porownujemy
    # tylko z date.today().isoformat(), nie potrzebujemy czasu/strefy).
    suggested_topic = Column(String(255), nullable=True)
    suggested_topic_date = Column(String(10), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<User {self.id}: {self.email} (Premium: {self.is_premium})>"


class Subscription(Base):
    """Subskrypcja Stripe"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    # NAPRAWIONE (user 04.09.2026, real-blad: proba anulowania subskrypcji
    # rzucila surowy blad SQL "invalid input syntax for type integer" na
    # produkcyjnej (Postgres/Supabase) bazie) - user_id tutaj byl blednie
    # Integer, mimo ze w calej reszcie aplikacji (np. Lesson.user_id wyzej)
    # user_id to Firebase UID - alfanumeryczny STRING (np.
    # "yXsgnTJdl1OLsFmvLte2zWLBQcR2"), nigdy liczba. Na SQLite (lokalnie)
    # dzialalo to przypadkiem (luzne typowanie), na Postgresie (produkcja)
    # kazde zapytanie/insert z prawdziwym Firebase UID w tej kolumnie
    # konczylo sie twardym bledem typu - stad KAZDA proba anulowania
    # subskrypcji musiala sie wywalac, a insert w _handle_checkout_completed
    # prawdopodobnie tez cicho zawodzil (bez wplywu na is_premium, ktore
    # jest ustawiane WCZESNIEJ, osobnym commitem, na innej tabeli).
    user_id = Column(String(128), index=True, nullable=False)
    
    # Stripe IDs
    stripe_subscription_id = Column(String(255), unique=True, nullable=False)
    stripe_customer_id = Column(String(255), nullable=False)
    stripe_price_id = Column(String(255), nullable=False)
    
    # Status
    status = Column(String(50))  # active, canceled, past_due, etc.
    cancel_at_period_end = Column(Boolean, default=False)
    
    # Daty
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Subscription {self.id}: User {self.user_id} - {self.status}>"


class GenerationRequestLog(Base):
    """Instrumentacja obserwacyjna (29.08.2026, user: "zrob to teraz,
    zanim kolejne dni ruchu bezpowrotnie znikna" - dane o KAZDYM
    wywolaniu generowania Quizu/Sprawdzianu leciaty dotad WYLACZNIE do
    konsoli (print, patrz GenerationMetrics.log w metrics.py) - znikaly
    przy kazdym restarcie serwera, wiec nie dalo sie retrospektywnie
    ustalic, jakie tematy/trudnosci userzy FAKTYCZNIE zamawiaja
    najczesciej. Jeden wiersz na kazde wywolanie - surowe dane do
    PRZYSZLEJ analizy Pareto (za 1-2 tygodnie ruchu), zeby kolejne
    archetypy Safe Parameter Generation (patrz math_verify.py) byly
    wybierane na podstawie faktow, nie tylko programu nauczania jak
    dzisiejsze (trygonometria/ciagi). CELOWO oddzielone od usage_stats
    (ktora liczy TYLKO dzienne limity dla planu darmowego) - to jest
    czysto obserwacyjne, nigdy nie uzywane do egzekwowania czegokolwiek."""
    __tablename__ = "generation_request_log"

    id = Column(Integer, primary_key=True, index=True)
    feature = Column(String(20), nullable=False)  # "quiz" albo "exam"
    temat = Column(String(300), nullable=True)
    trudnosc = Column(String(30), nullable=True)
    poziom = Column(String(30), nullable=True)
    requested_count = Column(Integer, default=0)
    accepted_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    total_time = Column(Float, default=0.0)
    rejection_reasons = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UsageStats(Base):
    """Statystyki użycia (FREE limity)"""
    __tablename__ = "usage_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    
    # Data statystyk
    date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Liczniki dzienne
    lesson_plans_created = Column(Integer, default=0)
    ai_messages_sent = Column(Integer, default=0)
    pdfs_generated = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    