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

@router.get("/voice")
def health_voice():
    errors = []
    try:
        from ..config import settings
        if not settings.GROQ_API_KEY: errors.append("Brak GROQ_API_KEY")
        if not settings.OPENAI_API_KEY: errors.append("Brak OPENAI_API_KEY")
    except Exception as e:
        errors.append(f"Config error: {str(e)}")
    return {"status": "ok" if not errors else "error", "service": "voice", "errors": errors}

@router.get("/chat")
def health_chat():
    errors = []
    try:
        from ..config import settings
        if not settings.GROQ_API_KEY: errors.append("Brak GROQ_API_KEY")
    except Exception as e:
        errors.append(f"Config error: {str(e)}")
    return {"status": "ok" if not errors else "error", "service": "chat", "errors": errors}

@router.get("/quiz")
def health_quiz():
    errors = []
    try:
        from ..config import settings
        if not settings.OPENAI_API_KEY: errors.append("Brak OPENAI_API_KEY")
    except Exception as e:
        errors.append(f"Config error: {str(e)}")
    return {"status": "ok" if not errors else "error", "service": "quiz", "errors": errors}

@router.get("/notes")
def health_notes():
    errors = []
    try:
        from ..config import settings
        if not settings.OPENAI_API_KEY: errors.append("Brak OPENAI_API_KEY")
    except Exception as e:
        errors.append(f"Config error: {str(e)}")
    return {"status": "ok" if not errors else "error", "service": "notes", "errors": errors}

@router.get("/exam")
def health_exam():
    errors = []
    try:
        from ..config import settings
        if not settings.OPENAI_API_KEY: errors.append("Brak OPENAI_API_KEY")
    except Exception as e:
        errors.append(f"Config error: {str(e)}")
    return {"status": "ok" if not errors else "error", "service": "exam", "errors": errors}

@router.get("/lessons")
def health_lessons():
    errors = []
    try:
        from ..config import settings
        if not settings.OPENAI_API_KEY: errors.append("Brak OPENAI_API_KEY")
    except Exception as e:
        errors.append(f"Config error: {str(e)}")
    return {"status": "ok" if not errors else "error", "service": "lessons", "errors": errors}
