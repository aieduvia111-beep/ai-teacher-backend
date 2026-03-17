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
    user_id = Column(Integer, index=True)
    
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
    hashed_password = Column(String(255), nullable=True)  # Użyjemy w Dniu 7
    
    # Stripe
    stripe_customer_id = Column(String(255), unique=True, nullable=True)
    
    # Premium status
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime(timezone=True), nullable=True)
    
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
    user_id = Column(Integer, index=True, nullable=False)
    
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
    
    def __repr__(self):
        return f"<UsageStats User {self.user_id}: Plans={self.lesson_plans_created}, Messages={self.ai_messages_sent}, PDFs={self.pdfs_generated}>"