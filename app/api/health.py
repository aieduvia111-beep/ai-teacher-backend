from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/")
def health_check():
    return {
        "status": "healthy",
        "message": "AI Teacher Backend is running!"
    }
@router.get("/chat")
def health_chat():
    try:
        from ..config import settings
        return {"status": "ok", "service": "chat", "llm": settings.GROQ_MODEL}
    except Exception as e:
        return {"status": "error", "service": "chat", "error": str(e)}

@router.get("/voice")  
def health_voice():
    try:
        from ..config import settings
        return {"status": "ok", "service": "voice", "stt": "groq", "tts": "openai"}
    except Exception as e:
        return {"status": "error", "service": "voice", "error": str(e)}

@router.get("/quiz")
def health_quiz():
    try:
        from ..config import settings
        return {"status": "ok", "service": "quiz"}
    except Exception as e:
        return {"status": "error", "service": "quiz", "error": str(e)}

@router.get("/notes")
def health_notes():
    try:
        from ..config import settings
        return {"status": "ok", "service": "notes"}
    except Exception as e:
        return {"status": "error", "service": "notes", "error": str(e)}

@router.get("/exam")
def health_exam():
    try:
        from ..config import settings
        return {"status": "ok", "service": "exam"}
    except Exception as e:
        return {"status": "error", "service": "exam", "error": str(e)}

@router.get("/lessons")
def health_lessons():
    try:
        from ..config import settings
        return {"status": "ok", "service": "lessons"}
    except Exception as e:
        return {"status": "error", "service": "lessons", "error": str(e)}
