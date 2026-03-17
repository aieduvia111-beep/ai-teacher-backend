from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from ..services.lesson_planner import LessonPlannerAI
from ..services.spaced_repetition import SpacedRepetitionEngine

router = APIRouter(prefix="/api/v1/lessons", tags=["lessons"])


# =============================================================================
# ðŸ“‹ REQUEST MODELS
# =============================================================================

class CreateLessonPlanRequest(BaseModel):
    topic: str
    subject: str
    level: str
    total_days: Optional[int] = 7
    minutes_per_day: Optional[int] = 30
    user_id: Optional[int] = 1
    additional_info: Optional[str] = ""

class CompleteDayRequest(BaseModel):
    lesson_id: int
    user_id: int
    day: int

class CompleteReviewRequest(BaseModel):
    review_id: int
    user_id: int
    quality: int  # 0-5


# =============================================================================
# ðŸ“‹ RESPONSE MODELS
# =============================================================================

class LessonPlanResponse(BaseModel):
    success: bool
    lesson_id: Optional[int] = None
    plan: Optional[dict] = None
    error: Optional[str] = None

class ReviewStatsResponse(BaseModel):
    success: bool
    stats: Optional[dict] = None
    error: Optional[str] = None


# =============================================================================
# ðŸŽ“ LESSON PLANNER ENDPOINTS
# =============================================================================

@router.post("/create-plan")
def create_lesson_plan(
    request: CreateLessonPlanRequest, 
    db: Session = Depends(get_db)
):
    """
    ðŸ§  StwÃ³rz plan nauki z pomocÄ… AI
    
    Body:
    {
        "topic": "Fotosynteza",
        "subject": "Biologia",
        "level": "liceum",
        "total_days": 7,
        "minutes_per_day": 30,
        "user_id": 1,
        "additional_info": "PotrzebujÄ™ duÅ¼o przykÅ‚adÃ³w"
    }
    
    Response:
    {
        "success": true,
        "lesson_id": 1,
        "plan": { ... kompletny plan ... }
    }
    """
    try:
        print(f"[DEBUG] create-plan payload: topic={request.topic!r} subject={request.subject!r} level={request.level!r} total_days={request.total_days!r} minutes_per_day={request.minutes_per_day!r} user_id={request.user_id!r}")
        print(f"ðŸ“š TworzÄ™ plan: {request.topic}")
        
        # SYNCHRONICZNE WYWOÅANIE - bez async/await!
        # Sanityzacja — zabezpieczenie przed None/NaN z frontendu
        safe_days = max(1, int(request.total_days or 7))
        safe_min = max(5, min(300, int(request.minutes_per_day or 30)))
        safe_uid = int(request.user_id or 1)

        result = LessonPlannerAI.create_lesson_plan(
            topic=request.topic,
            subject=request.subject,
            level=request.level,
            total_days=safe_days,
            minutes_per_day=safe_min,
            user_id=safe_uid,
            db=db,
            additional_info=request.additional_info or ""
        )
        
        # ZwrÃ³Ä‡ tylko JSON-serializable dane
        if result.get("success"):
            return {
                "success": True,
                "lesson_id": result.get("lesson_id"),
                "plan": result.get("plan"),
                "message": "âœ… Plan nauki zostaÅ‚ wygenerowany!"
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Nieznany bÅ‚Ä…d"),
                "plan": result.get("plan")  # Fallback plan jeÅ›li jest
            }
            
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d w create_lesson_plan endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "error": f"BÅ‚Ä…d serwera: {str(e)}"
        }


@router.get("/my-plans/{user_id}")
def get_my_plans(user_id: int, db: Session = Depends(get_db)):
    """
    ðŸ“š Pobierz wszystkie plany uÅ¼ytkownika
    
    Returns:
    [
        {
            "id": 1,
            "title": "Fotosynteza - Plan Nauki",
            "subject": "Biologia",
            "current_day": 3,
            "total_days": 7,
            "is_completed": false
        }
    ]
    """
    try:
        lessons = LessonPlannerAI.get_user_lessons(db, user_id)
        
        return {
            "success": True,
            "lessons": [
                {
                    "id": lesson.id,
                    "title": lesson.title,
                    "subject": lesson.subject,
                    "level": lesson.level,
                    "current_day": lesson.current_day,
                    "total_days": lesson.total_days,
                    "minutes_per_day": lesson.minutes_per_day,
                    "is_completed": lesson.is_completed,
                    "created_at": lesson.created_at.isoformat() if lesson.created_at else None
                }
                for lesson in lessons
            ]
        }
        
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d w get_my_plans: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan/{lesson_id}/{user_id}")
def get_lesson_plan(lesson_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    ðŸ“– Pobierz szczegÃ³Å‚y planu nauki
    
    Returns: Kompletny plan z wszystkimi dniami i krokami
    """
    try:
        lesson = LessonPlannerAI.get_lesson_by_id(db, lesson_id, user_id)
        
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")
        
        return {
            "success": True,
            "lesson": {
                "id": lesson.id,
                "title": lesson.title,
                "subject": lesson.subject,
                "level": lesson.level,
                "current_day": lesson.current_day,
                "total_days": lesson.total_days,
                "content": lesson.content,
                "is_completed": lesson.is_completed,
                "created_at": lesson.created_at.isoformat() if lesson.created_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d w get_lesson_plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complete-day")
def complete_day(request: CompleteDayRequest, db: Session = Depends(get_db)):
    """
    âœ… Oznacz dzieÅ„ jako ukoÅ„czony
    
    Body:
    {
        "lesson_id": 1,
        "user_id": 1,
        "day": 1
    }
    """
    try:
        result = LessonPlannerAI.complete_day(
            db=db,
            lesson_id=request.lesson_id,
            user_id=request.user_id,
            day=request.day
        )
        
        return result
        
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d w complete_day: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ðŸ”„ SPACED REPETITION ENDPOINTS
# =============================================================================

@router.get("/reviews/due/{user_id}")
def get_due_reviews(user_id: int, db: Session = Depends(get_db)):
    """
    ðŸ“… Pobierz dzisiejsze powtÃ³rki
    
    Returns: Lista powtÃ³rek do zrobienia
    """
    try:
        reviews = SpacedRepetitionEngine.get_due_reviews(db, user_id)
        
        return {
            "success": True,
            "reviews": [
                {
                    "id": review.id,
                    "topic": review.topic,
                    "scheduled_for": review.scheduled_for.isoformat() if review.scheduled_for else None,
                    "interval_days": review.interval_days,
                    "review_count": review.review_count
                }
                for review in reviews
            ]
        }
        
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d w get_due_reviews: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reviews/complete")
def complete_review(request: CompleteReviewRequest, db: Session = Depends(get_db)):
    """
    âœ… UkoÅ„cz powtÃ³rkÄ™
    
    Body:
    {
        "review_id": 1,
        "user_id": 1,
        "quality": 4
    }
    
    quality: 0-5
    - 5: perfect recall (idealnie pamiÄ™tam)
    - 4: correct after hesitation (po chwili przypominam sobie)
    - 3: correct with difficulty (z trudem)
    - 2: incorrect but remembered (Åºle ale coÅ› pamiÄ™tam)
    - 1: incorrect (Åºle)
    - 0: complete blackout (kompletnie nie pamiÄ™tam)
    """
    try:
        review = SpacedRepetitionEngine.complete_review(
            db=db,
            review_id=request.review_id,
            quality=request.quality
        )
        
        return {
            "success": True,
            "review": {
                "id": review.id,
                "quality": review.quality,
                "next_review": review.next_review.isoformat() if review.next_review else None,
                "interval_days": review.interval_days,
                "easiness_factor": review.easiness_factor
            }
        }
        
    except ValueError as e:
        print(f"âŒ ValueError w complete_review: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d w complete_review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reviews/stats/{user_id}")
def get_review_stats(user_id: int, db: Session = Depends(get_db)):
    """
    ðŸ“Š Statystyki powtÃ³rek uÅ¼ytkownika
    
    Returns:
    {
        "due_today": 5,
        "due_tomorrow": 3,
        "completed_this_week": 12,
        "total_reviews": 45
    }
    """
    try:
        stats = SpacedRepetitionEngine.get_review_stats(db, user_id)
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        print(f"âŒ BÅ‚Ä…d w get_review_stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))