from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/")
def health_check():
    return {"status": "healthy", "message": "Eduvia Backend is running!"}

@router.get("/voice")
def health_voice():
    return {"status": "ok", "service": "voice", "stt": "groq", "tts": "openai"}

@router.get("/chat")
def health_chat():
    return {"status": "ok", "service": "chat"}

@router.get("/quiz")
def health_quiz():
    return {"status": "ok", "service": "quiz"}

@router.get("/notes")
def health_notes():
    return {"status": "ok", "service": "notes"}

@router.get("/exam")
def health_exam():
    return {"status": "ok", "service": "exam"}

@router.get("/lessons")
def health_lessons():
    return {"status": "ok", "service": "lessons"}
