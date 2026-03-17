from datetime import datetime, timedelta
from typing import Dict
from sqlalchemy.orm import Session
from ..models import Review


class SpacedRepetitionEngine:
    """
    🧠 Spaced Repetition System (SM-2 Algorithm)
    
    Algorytm SuperMemo 2 - optymalnie planuje powtórki
    """
    
    @staticmethod
    def calculate_next_review(
        quality: int,
        current_easiness: float = 2.5,
        current_interval: int = 1,
        review_count: int = 0
    ) -> Dict:
        """Oblicza następną powtórkę według SM-2"""
        
        if quality < 0 or quality > 5:
            quality = max(0, min(5, quality))
        
        # Oblicz nowy Easiness Factor
        new_easiness = current_easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_easiness = max(1.3, new_easiness)
        
        # Oblicz nowy interwał
        if quality < 3:
            new_interval = 1
            new_review_count = 0
        else:
            new_review_count = review_count + 1
            
            if new_review_count == 1:
                new_interval = 1
            elif new_review_count == 2:
                new_interval = 6
            else:
                new_interval = round(current_interval * new_easiness)
        
        next_review_date = datetime.utcnow() + timedelta(days=new_interval)
        
        return {
            "next_interval": new_interval,
            "next_easiness": round(new_easiness, 2),
            "next_review_date": next_review_date,
            "review_count": new_review_count
        }
    
    
    @staticmethod
    def create_review(
        db: Session,
        lesson_id: int,
        user_id: int,
        topic: str,
        scheduled_for: datetime = None
    ) -> Review:
        """Tworzy nową powtórkę"""
        
        if scheduled_for is None:
            scheduled_for = datetime.utcnow() + timedelta(days=1)
        
        review = Review(
            lesson_id=lesson_id,
            user_id=user_id,
            topic=topic,
            scheduled_for=scheduled_for,
            easiness_factor=2.5,
            interval_days=1,
            review_count=0
        )
        
        db.add(review)
        db.commit()
        db.refresh(review)
        
        return review
    
    
    @staticmethod
    def complete_review(db: Session, review_id: int, quality: int) -> Review:
        """Oznacz powtórkę jako ukończoną"""
        
        review = db.query(Review).filter(Review.id == review_id).first()
        
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        review.completed_at = datetime.utcnow()
        review.quality = quality
        
        next_review = SpacedRepetitionEngine.calculate_next_review(
            quality=quality,
            current_easiness=review.easiness_factor,
            current_interval=review.interval_days,
            review_count=review.review_count
        )
        
        review.easiness_factor = next_review["next_easiness"]
        review.interval_days = next_review["next_interval"]
        review.review_count = next_review["review_count"]
        review.next_review = next_review["next_review_date"]
        
        db.commit()
        db.refresh(review)
        
        if quality >= 3:
            SpacedRepetitionEngine.create_review(
                db=db,
                lesson_id=review.lesson_id,
                user_id=review.user_id,
                topic=review.topic,
                scheduled_for=next_review["next_review_date"]
            )
        
        return review
    
    
    @staticmethod
    def get_due_reviews(db: Session, user_id: int) -> list:
        """Pobierz powtórki do zrobienia dzisiaj"""
        
        reviews = db.query(Review).filter(
            Review.user_id == user_id,
            Review.completed_at == None,
            Review.scheduled_for <= datetime.utcnow()
        ).order_by(Review.scheduled_for).all()
        
        return reviews
    
    
    @staticmethod
    def get_review_stats(db: Session, user_id: int) -> Dict:
        """Statystyki powtórek"""
        
        due_today = db.query(Review).filter(
            Review.user_id == user_id,
            Review.completed_at == None,
            Review.scheduled_for <= datetime.utcnow()
        ).count()
        
        tomorrow = datetime.utcnow() + timedelta(days=1)
        due_tomorrow = db.query(Review).filter(
            Review.user_id == user_id,
            Review.completed_at == None,
            Review.scheduled_for >= datetime.utcnow(),
            Review.scheduled_for < tomorrow
        ).count()
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        completed_this_week = db.query(Review).filter(
            Review.user_id == user_id,
            Review.completed_at >= week_ago
        ).count()
        
        return {
            "due_today": due_today,
            "due_tomorrow": due_tomorrow,
            "completed_this_week": completed_this_week,
            "total_reviews": db.query(Review).filter(
                Review.user_id == user_id,
                Review.completed_at != None
            ).count()
        }