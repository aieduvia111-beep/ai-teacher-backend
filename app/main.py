from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict
import os

# Ścieżka do folderu static
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from .config import settings
from .database import engine, Base
from .openai_vision import (
    analyze_image_with_gpt4_vision,
    vision_analyze_homework,
    vision_analyze_diagram,
    solve_homework_vision
)
from .openai_exam import (
    generate_exam_from_image,
    generate_notes_from_image,
    generate_notes_from_topic,
    generate_quiz_from_image,
    generate_quiz_from_topic
)

# Tables will be created on startup


app = FastAPI(title="AI Teacher API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══ ROUTERY ══
try:
    from .api.chat import router as chat_router
    app.include_router(chat_router)
    print("✅ chat OK")
except Exception as e:
    print(f"❌ chat: {e}")

try:
    from .api.auth import router as auth_router
    app.include_router(auth_router)
    print("✅ auth OK")
except Exception as e:
    print(f"❌ auth: {e}")

try:
    from .api.lessons import router as lessons_router
    app.include_router(lessons_router)
    print("✅ lessons OK")
except Exception as e:
    print(f"❌ lessons: {e}")

try:
    from .api.payments import router as payments_router
    app.include_router(payments_router)
    print("✅ payments OK")
except Exception as e:
    print(f"❌ payments: {e}")

try:
    from .api.notes_api import router as notes_router
    app.include_router(notes_router)
    print("✅ notes OK")
except Exception as e:
    print(f"❌ notes: {e}")

try:
    from .api.exam_api import router as exam_router
    app.include_router(exam_router)
    print("✅ exam_api OK")
except Exception as e:
    print(f"❌ exam_api: {e}")

try:
    from .api.vision import router as vision_router
    app.include_router(vision_router)
    print("✅ vision OK")
except Exception as e:
    print(f"❌ vision: {e}")

try:
    from .api.voice import router as voice_router
    app.include_router(voice_router)
    print("✅ voice OK")
except Exception as e:
    print(f"❌ voice: {e}")

try:
    from .api.users import router as users_router
    app.include_router(users_router)
    print("✅ users OK")
except Exception as e:
    print(f"❌ users: {e}")

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    print("✅ static OK")
except Exception as e:
    print(f"⚠️ static: {e}")


# ══ STRONY HTML ══
@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "AI Teacher API is running! 🚀",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "chat": "/chat",
            "quiz": "/quiz",
            "dashboard": "/static/dashboard_FINAL.html",
            "voice": "/static/voice_conversation.html",
        }
    }

@app.get("/chat")
@app.head("/chat")
async def page_chat():
    return FileResponse(os.path.join(BASE_DIR, "static", "chat.html"))

@app.get("/quiz")
@app.head("/quiz")
async def page_quiz():
    return FileResponse(os.path.join(BASE_DIR, "static", "quiz_app.html"))

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "openai_key_preview": settings.OPENAI_API_KEY[:20] + "..." if settings.OPENAI_API_KEY else "MISSING",
        "database": "connected"
    }


# ══ MODELE ══
class VisionRequest(BaseModel):
    image: str
    subject: Optional[str] = "matematyka"
    mode: Optional[str] = "solve"
    prompt: Optional[str] = "Co widzisz na tym obrazie?"

class VisionResponse(BaseModel):
    success: bool
    analysis: str
    error: Optional[str] = None

class ExamRequest(BaseModel):
    image: str
    difficulty: str = "medium"
    num_questions: int = 10
    include_open_questions: bool = True

class ExamResponse(BaseModel):
    success: bool
    exam: Optional[Dict] = None
    error: Optional[str] = None

class NotesRequest(BaseModel):
    image: str
    style: str = "academic"

class NotesResponse(BaseModel):
    success: bool
    notes: Optional[str] = None
    style: Optional[str] = None
    error: Optional[str] = None

class NotesTopicRequest(BaseModel):
    topic: str
    level: str = "liceum"
    subject: str = "matematyka"
    style: str = "academic"
    details: str = ""

class NotesTopicResponse(BaseModel):
    success: bool
    notes: Optional[str] = None
    topic: Optional[str] = None
    level: Optional[str] = None
    subject: Optional[str] = None
    style: Optional[str] = None
    error: Optional[str] = None

class QuizRequest(BaseModel):
    image: str
    num_questions: int = 5
    difficulty: str = "medium"

class QuizTopicRequest(BaseModel):
    topic: str
    subject: str = "matematyka"
    level: str = "liceum"
    num_questions: int = 5
    difficulty: str = "medium"
    wlasne_instrukcje: str = ""

class QuizResponse(BaseModel):
    success: bool
    quiz: Optional[Dict] = None
    error: Optional[str] = None


# ══ ENDPOINTY VISION ══
@app.post("/api/v1/vision/analyze", response_model=VisionResponse)
async def analyze_image(request: VisionRequest):
    try:
        result = await analyze_image_with_gpt4_vision(request.image, request.prompt)
        return VisionResponse(success=True, analysis=result)
    except Exception as e:
        return VisionResponse(success=False, analysis="", error=str(e))

@app.post("/api/v1/vision/analyze-math", response_model=VisionResponse)
async def analyze_math(request: VisionRequest):
    try:
        result = await vision_analyze_homework(request.image)
        return VisionResponse(success=True, analysis=result)
    except Exception as e:
        return VisionResponse(success=False, analysis="", error=str(e))

@app.post("/api/v1/vision/analyze-diagram", response_model=VisionResponse)
async def analyze_diagram(request: VisionRequest):
    try:
        result = await vision_analyze_diagram(request.image)
        return VisionResponse(success=True, analysis=result)
    except Exception as e:
        return VisionResponse(success=False, analysis="", error=str(e))

@app.post("/api/v1/vision/solve")
async def vision_solve(request: VisionRequest):
    try:
        # ← NAPRAWIONE: await zamiast zwykłego call
        result = await solve_homework_vision(
            image_base64=request.image,
            subject=request.subject,
            mode=request.mode,
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e), "problems": []}


# ══ ENDPOINTY EXAM ══
@app.post("/api/v1/exam/generate", response_model=ExamResponse)
async def generate_exam(request: ExamRequest):
    try:
        result = await generate_exam_from_image(
            request.image, request.difficulty,
            request.num_questions, request.include_open_questions
        )
        if result["success"]:
            return ExamResponse(success=True, exam=result["exam"])
        return ExamResponse(success=False, error=result.get("error"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══ ENDPOINTY NOTES ══
@app.post("/api/v1/notes/generate", response_model=NotesResponse)
async def generate_notes(request: NotesRequest):
    try:
        result = await generate_notes_from_image(request.image, request.style)
        if result["success"]:
            return NotesResponse(success=True, notes=result["notes"], style=result["style"])
        return NotesResponse(success=False, error=result.get("error"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/notes/generate-topic", response_model=NotesTopicResponse)
async def generate_notes_topic(request: NotesTopicRequest):
    try:
        result = await generate_notes_from_topic(
            request.topic, request.level, request.subject,
            request.style, request.details
        )
        if result["success"]:
            return NotesTopicResponse(
                success=True, notes=result["notes"], topic=result["topic"],
                level=result["level"], subject=result["subject"], style=result["style"]
            )
        return NotesTopicResponse(success=False, error=result.get("error"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══ ENDPOINTY QUIZ ══
@app.post("/api/v1/quiz/generate", response_model=QuizResponse)
async def generate_quiz(request: QuizRequest):
    try:
        result = await generate_quiz_from_image(
            request.image, request.num_questions, request.difficulty
        )
        if result["success"]:
            return QuizResponse(success=True, quiz=result["quiz"])
        return QuizResponse(success=False, error=result.get("error"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/quiz/generate-topic", response_model=QuizResponse)
async def generate_quiz_topic(request: QuizTopicRequest):
    try:
        result = await generate_quiz_from_topic(
            request.topic, request.subject, request.level,
            request.num_questions, request.difficulty,
            request.wlasne_instrukcje
        )
        if result["success"]:
            return QuizResponse(success=True, quiz=result["quiz"])
        return QuizResponse(success=False, error=result.get("error"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══ STARTUP ══
@app.on_event("startup")
async def startup():
    # Stwórz tabele przy starcie
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Tabele bazy danych OK")
    except Exception as e:
        print(f"⚠️ Baza danych: {e}")

    print("=" * 60)
    print("🚀 AI TEACHER BACKEND STARTED!")
    print(f"🔑 OpenAI: {'✅ ' + settings.OPENAI_API_KEY[:20] + '...' if settings.OPENAI_API_KEY else '❌ MISSING'}")
    print(f"📍 Docs:      http://127.0.0.1:8000/docs")
    print(f"💬 Chat:      http://127.0.0.1:8000/chat")
    print(f"🎯 Quiz:      http://127.0.0.1:8000/quiz")
    print(f"💎 Dashboard: http://127.0.0.1:8000/static/dashboard_FINAL.html")
    print(f"🎤 Voice:     http://127.0.0.1:8000/static/voice_conversation.html")
    print("=" * 60)
