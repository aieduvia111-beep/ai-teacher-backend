from openai import OpenAI
from typing import Dict
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..config import settings
from ..models import Lesson
from .spaced_repetition import SpacedRepetitionEngine

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class LessonPlannerAI:
    """
    ðŸ§  AI Lesson Planner - Tworzy spersonalizowane plany nauki
    
    User wpisuje: temat, poziom, deadline
    AI generuje: szczegÃ³Å‚owy plan krok-po-kroku
    """
    
    @staticmethod
    def create_lesson_plan(  # â† USUNIÄ˜TO async (bo OpenAI nie jest async)
        topic: str,
        subject: str,
        level: str,
        total_days: int,
        minutes_per_day: int,
        user_id: int,
        db: Session,
        additional_info: str = ""
    ) -> Dict:
        """
        Generuje plan nauki z pomocÄ… AI
        
        Args:
            topic: Temat (np. "Fotosynteza")
            subject: Przedmiot (np. "Biologia")
            level: Poziom (podstawowka/gimnazjum/liceum/studia)
            total_days: Ile dni nauki (np. 7)
            minutes_per_day: Ile minut dziennie (np. 30)
            user_id: ID uÅ¼ytkownika
            db: Database session
            additional_info: Dodatkowe wymagania
        
        Returns:
            Dict z planem nauki
        """
        
        level_map = {
            "podstawowka": "ucznia podstawÃ³wki (kl. 4-8)",
            "gimnazjum": "ucznia gimnazjum",
            "liceum": "ucznia liceum",
            "studia": "studenta (poziom akademicki)"
        }
        
        total_time = total_days * minutes_per_day
        days_to_gen = min(total_days, 14)
        
        prompt = f"""Stwórz PLAN NAUKI na temat: \"{topic}\"

PARAMETRY:
- Przedmiot: {subject}
- Poziom: {level_map.get(level, 'liceum')}
- Dni: {days_to_gen}
- Czas: {minutes_per_day} min/dzien
""" + (f"- Dodatkowe: {additional_info}\n" if "additional_info" else "") + f"""
FORMAT (TYLKO JSON):
{{
    "title": "Plan Nauki",
    "description": "Krotki opis",
    "total_days": {days_to_gen},
    "minutes_per_day": {minutes_per_day},
    "days": [
        {{
            "day": 1,
            "title": "Tytul dnia",
            "tasks": [
                "Zadanie 1 (15 min)",
                "Zadanie 2 (10 min)",
                "Quiz sprawdzajacy (5 min)"
            ]
        }}
    ],
    "review_schedule": [
        {{"topic": "Podstawy", "first_review": 3, "second_review": 7}}
    ]
}}

ZASADY:
1. Wygeneruj DOKLADNIE {days_to_gen} dni
2. tasks = lista stringow (NIE obiekty!)
3. Ostatni dzien = test koncowy
4. PO POLSKU, TYLKO JSON
"""

        try:
            print(f"ðŸ§  GenerujÄ™ plan nauki: {topic} ({total_days} dni, {subject})...")
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=6000,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            plan_data = json.loads(response.choices[0].message.content)
            
            # Dodaj review_topics automatycznie jeÅ›li AI zapomniaÅ‚o
            plan_data = LessonPlannerAI._add_spaced_repetition(plan_data, total_days)
            
            print(f"âœ… Plan wygenerowany: {plan_data.get('title')}")
            
            # Zapisz do bazy
            lesson = Lesson(
                user_id=user_id,
                title=plan_data.get("title"),
                subject=subject,
                level=level,
                total_days=total_days,
                minutes_per_day=minutes_per_day,
                content=plan_data,  # JSON z caÅ‚ym planem
                current_day=1,
                is_completed=False
            )
            
            db.add(lesson)
            db.commit()
            db.refresh(lesson)
            
            # StwÃ³rz harmonogram powtÃ³rek (Spaced Repetition)
            if "review_schedule" in plan_data:
                for review_item in plan_data["review_schedule"]:
                    # Pierwsza powtÃ³rka
                    first_review_date = datetime.utcnow() + timedelta(days=review_item.get("first_review", 3))
                    
                    SpacedRepetitionEngine.create_review(
                        db=db,
                        lesson_id=lesson.id,
                        user_id=user_id,
                        topic=review_item.get("topic"),
                        scheduled_for=first_review_date
                    )
            
            print(f"ðŸ’¾ Plan zapisany w bazie (ID: {lesson.id})")
            
            return {
                "success": True,
                "lesson_id": lesson.id,
                "plan": plan_data
            }
            
        except Exception as e:
            print(f"âŒ BÅ‚Ä…d: {str(e)}")
            
            # Fallback - prosty plan jeÅ›li AI zawiedzie
            fallback_plan = LessonPlannerAI._create_fallback_plan(
                topic, subject, level, total_days, minutes_per_day
            )
            
            return {
                "success": False,
                "error": str(e),
                "plan": fallback_plan  # ZwrÃ³Ä‡ prosty plan zastÄ™pczy
            }
    
    
    @staticmethod
    def _add_spaced_repetition(plan_data: Dict, total_days: int) -> Dict:
        """
        Dodaje review_topics zgodnie z algorytmem Spaced Repetition
        
        Zasada: Powtarzaj materiaÅ‚ w odstÄ™pach: 1d, 3d, 7d, 14d
        """
        if "days" not in plan_data:
            return plan_data
        
        # Harmonogram powtÃ³rek (ktÃ³re dni powtÃ³rzyÄ‡)
        review_intervals = [3, 7, 14, 21, 30]
        
        for day_data in plan_data["days"]:
            day_num = day_data.get("day", 0)
            
            # SprawdÅº czy ten dzieÅ„ powinien mieÄ‡ powtÃ³rkÄ™
            for interval in review_intervals:
                if day_num == interval and day_num <= total_days:
                    # Dodaj powtÃ³rkÄ™ z poprzednich dni
                    days_to_review = list(range(1, min(interval, day_num)))
                    
                    # Pobierz tematy z poprzednich dni
                    review_topics = []
                    for prev_day in days_to_review:
                        prev_day_data = next(
                            (d for d in plan_data["days"] if d.get("day") == prev_day),
                            None
                        )
                        if prev_day_data:
                            review_topics.append(prev_day_data.get("title", f"DzieÅ„ {prev_day}"))
                    
                    day_data["review_topics"] = review_topics[:3]  # Max 3 tematy
                    break
        
        return plan_data
    
    
    @staticmethod
    def _create_fallback_plan(
        topic: str, 
        subject: str, 
        level: str, 
        total_days: int, 
        minutes_per_day: int
    ) -> Dict:
        """
        Prosty plan zastÄ™pczy gdyby AI zawiodÅ‚o
        """
        print("âš ï¸ TworzÄ™ prosty plan zastÄ™pczy...")
        
        days = []
        for i in range(total_days):
            day_num = i + 1
            days.append({
                "day": day_num,
                "title": f"DzieÅ„ {day_num}: {topic}",
                "goal": f"Poznaj kolejny aspekt tematu: {topic}",
                "steps": [
                    {
                        "type": "reading",
                        "title": "Przeczytaj materiaÅ‚y",
                        "content": f"Przestudiuj podstawowe informacje o: {topic}",
                        "duration": int(minutes_per_day * 0.6)
                    },
                    {
                        "type": "practice",
                        "title": "Ä†wiczenia",
                        "content": "RozwiÄ…Å¼ przykÅ‚adowe zadania",
                        "duration": int(minutes_per_day * 0.4)
                    }
                ],
                "review_topics": []
            })
        
        return {
            "title": f"Plan nauki: {topic}",
            "description": f"Podstawowy plan nauki tematu {topic} ({subject})",
            "total_days": total_days,
            "minutes_per_day": minutes_per_day,
            "level": level,
            "days": days,
            "review_schedule": []
        }
    
    
    @staticmethod
    def get_user_lessons(db: Session, user_id: int) -> list:
        """Pobierz wszystkie plany uÅ¼ytkownika"""
        
        lessons = db.query(Lesson).filter(
            Lesson.user_id == user_id
        ).order_by(Lesson.created_at.desc()).all()
        
        return lessons
    
    
    @staticmethod
    def get_lesson_by_id(db: Session, lesson_id: int, user_id: int) -> Lesson:
        """Pobierz konkretny plan"""
        
        lesson = db.query(Lesson).filter(
            Lesson.id == lesson_id,
            Lesson.user_id == user_id
        ).first()
        
        return lesson
    
    
    @staticmethod
    def complete_day(db: Session, lesson_id: int, user_id: int, day: int) -> Dict:
        """Oznacz dzieÅ„ jako ukoÅ„czony"""
        
        lesson = db.query(Lesson).filter(
            Lesson.id == lesson_id,
            Lesson.user_id == user_id
        ).first()
        
        if not lesson:
            return {"success": False, "error": "Lesson not found"}
        
        # Aktualizuj current_day
        if day == lesson.current_day:
            lesson.current_day = min(day + 1, lesson.total_days)
            
            # SprawdÅº czy caÅ‚y plan ukoÅ„czony
            if lesson.current_day > lesson.total_days:
                lesson.is_completed = True
                lesson.completion_date = datetime.utcnow()
            
            db.commit()
            db.refresh(lesson)
            
            return {
                "success": True,
                "current_day": lesson.current_day,
                "is_completed": lesson.is_completed,
                "message": f"âœ… DzieÅ„ {day} ukoÅ„czony!" if not lesson.is_completed else "ðŸŽ‰ Gratulacje! UkoÅ„czyÅ‚eÅ› caÅ‚y plan!"
            }
        
        return {"success": False, "error": "Invalid day"}
    
    
    @staticmethod
    def get_next_step(db: Session, lesson_id: int, user_id: int) -> Dict:
        """Zwraca kolejny krok do wykonania"""
        
        lesson = LessonPlannerAI.get_lesson_by_id(db, lesson_id, user_id)
        
        if not lesson:
            return {"success": False, "error": "Lesson not found"}
        
        if lesson.is_completed:
            return {
                "success": True,
                "message": "ðŸŽ‰ Plan ukoÅ„czony!",
                "is_completed": True
            }
        
        # Pobierz aktualny dzieÅ„ z planu
        plan_data = lesson.content
        current_day_data = next(
            (d for d in plan_data.get("days", []) if d.get("day") == lesson.current_day),
            None
        )
        
        if current_day_data:
            return {
                "success": True,
                "day": current_day_data,
                "current_day": lesson.current_day,
                "total_days": lesson.total_days,
                "progress": (lesson.current_day / lesson.total_days) * 100
            }
        
        return {"success": False, "error": "No more steps"}