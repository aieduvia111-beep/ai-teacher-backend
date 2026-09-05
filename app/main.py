from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict
import os
import sentry_sdk

sentry_sdk.init(
    dsn="https://1c0ce09af391ac4be873092870db6091@o4511484097003520.ingest.de.sentry.io/4511836255420496",
    send_default_pii=True,
    traces_sample_rate=0.2,
)

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
)

# Tables will be created on startup


app = FastAPI(title="AI Teacher API", version="1.0.0")
from app.limit_middleware import usage_limit_middleware
app.middleware("http")(usage_limit_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|https://eduvia-backend-2\.onrender\.com|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?",
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
except Exception as e:
    print(f"notes_api error: {e}")
try:
    from .api.youtube_notes import router as youtube_router
    app.include_router(youtube_router)
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
    from .api.quiz_api import router as quiz_router
    app.include_router(quiz_router)
    print("✅ quiz_api OK")
except Exception as e:
    print(f"❌ quiz_api: {e}")

try:
    from .api.flashcards_api import router as flashcards_router
    app.include_router(flashcards_router)
    print("✅ flashcards_api OK")
except Exception as e:
    print(f"❌ flashcards_api: {e}")

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
    from .api.realtime import router as realtime_router
    app.include_router(realtime_router)
    print("✅ realtime OK")
except Exception as e:
    print(f"❌ realtime: {e}")

try:
    from .api.users import router as users_router
    app.include_router(users_router)
    print("✅ users OK")
except Exception as e:
    print(f"❌ users: {e}")

try:
    from .api.brain import router as brain_router
    app.include_router(brain_router)
    print("✅ brain OK")
except Exception as e:
    print(f"❌ brain: {e}")
try:
    from .api.notifications import router as notifications_router
    app.include_router(notifications_router)
    print("✅ notifications OK")
except Exception as e:
    print(f"❌ notifications: {e}")

try:
    app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")), name="static")
    print("✅ static OK")
except Exception as e:
    print(f"⚠️ static: {e}")


# ══ STRONY HTML ══
@app.get("/manifest.json", include_in_schema=False)
async def manifest():
    from fastapi.responses import FileResponse
    return FileResponse("static/manifest.json")

@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/eduvia-final.html")

@app.get("/chat")
@app.head("/chat")
async def page_chat():
    return FileResponse(os.path.join(BASE_DIR, "static", "chat.html"))

@app.get("/quiz")
@app.head("/quiz")
async def page_quiz():
    return FileResponse(os.path.join(BASE_DIR, "static", "quiz_app.html"))

try:
    from .api.affiliates import router as affiliates_router
    app.include_router(affiliates_router)
except Exception as e:
    print(f"affiliates error: {e}")
try:
    from .api.health import router as health_router
    app.include_router(health_router)
except Exception as e:
    print(f"health router error: {e}")
try:
    from .api.admin import router as admin_router
    app.include_router(admin_router)
except Exception as e:
    print(f"admin router error: {e}")

@app.get("/health")
async def health():
    db_status = "disconnected"
    try:
        from sqlalchemy import text
        from .database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:100]}"

    return {
        "status": "healthy",
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "database": db_status
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
# NAPRAWIONE (01.09.2026, audyt kosztow API - user zglosil nagly skok
# kosztow OpenAI): usuniety stad duplikat /api/v1/exam/generate - ten
# konkretny byl juz w praktyce martwy (exam_router z app/api/exam_api.py,
# podlaczony WCZESNIEJ w tym pliku, zawsze wygrywal wyscig routingu na
# ten sam sciezke+metode), ale zostawiony tu byl myacy i ukrywal
# prawdziwy problem opisany nizej. Ten sam wzorzec co Quiz (patrz
# komentarz historyczny przy sekcji Quiz ponizej).
# ══ ENDPOINTY NOTES ══
# NAPRAWIONE (01.09.2026, KRYTYCZNE - realny, aktywny wyciek kosztow):
# oba te endpointy (/api/v1/notes/generate, /api/v1/notes/generate-topic)
# NIE kolidowaly z niczym (notes_router z app/api/notes_api.py zyje pod
# INNA sciezka, /api/v1/notes-pdf/...) - byly wiec naprawde zywe,
# osiagalne, i (1) BEZ jakiejkolwiek autoryzacji (brak Depends na
# zweryfikowanego usera), (2) BEZ limit_middleware (nie ma ich w
# PROTECTED_PREFIXES) - czyli KAZDY, kto zna adres (repo jest publiczne
# na GitHub), mogl je spamowac bez ograniczen, kazde wywolanie to
# platne zapytanie do gpt-4o (notatki z obrazka to wywolanie Vision,
# jeszcze drozsze). Zaden plik frontendu nigdzie ich nie wywoluje
# (sprawdzone grepem) - byly czystym, niepotrzebnym ryzykiem. Usuniete
# w calosci, tak jak analogiczny duplikat Quiz zostal usuniety wczesniej
# (patrz komentarz historyczny ponizej).


# ══ ENDPOINTY QUIZ ══
# ETAP 2, Punkt 2: usuniete stad duplikaty /api/v1/quiz/generate i
# /generate-topic - ZAWSZE wygrywaly wyscig routingu z app/api/quiz_api.py
# (ten plik nigdy nie byl podlaczony przez app.include_router - martwy kod
# od poczatku), wiec caly ruch Quiz szedl przez ta prostsza, starsza
# implementacje: bez Depends(require_feature_limit), bez response_model
# pozwalajacego na dodatkowe pola (status/requested_count/accepted_count
# potrzebne dla incomplete_generation). Teraz jedynym zrodlem prawdy jest
# quiz_api.router (patrz include_router nizej) - identyczna logika
# generowania (ta sama funkcja generate_quiz_from_topic), ale z pelna
# obsluga limitow i shortfallu.


# ══ STARTUP ══
@app.on_event("startup")
async def startup():
    # Stwórz tabele przy starcie
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Tabele bazy danych OK")
    except Exception as e:
        print(f"⚠️ Baza danych: {e}")

    # create_all() tworzy tylko BRAKUJACE TABELE, nie dokłada nowych
    # kolumn do już istniejącej tabeli (SQLAlchemy tego nie robi) - stąd
    # recznie dodajemy nowe, opcjonalne kolumny (jesli jeszcze ich nie ma)
    # zamiast wymagac od kogokolwiek reczengo kasowania/migrowania bazy
    # przy kazdym takim dodaniu. Idempotentne - bezpieczne przy kazdym
    # restarcie.
    try:
        from sqlalchemy import inspect as _sa_inspect, text as _sa_text
        _insp = _sa_inspect(engine)
        if "users" in _insp.get_table_names():
            _existing_cols = {c["name"] for c in _insp.get_columns("users")}
            # NAPRAWIONE (31.08.2026): przed pierwszym prawdziwym deployem tych
            # kolumn na produkcje odkrylismy ze origin/main byl 125 commitow
            # w tyle - realna tabela users na Supabase moze nie miec ZADNEJ
            # z kolumn dodanych do modelu User od dawna (nie tylko dwoch
            # ponizej). Lista rozszerzona o WSZYSTKIE nullable/opcjonalne
            # kolumny z models.py, zeby migracja byla kompletna niezaleznie
            # od tego ktora dokladnie brakuje - bez tego apka wywalalaby sie
            # na pierwszym zapytaniu dotykajacym brakujacej kolumny.
            _new_cols = {
                "username": "VARCHAR(100)",
                "hashed_password": "VARCHAR(255)",
                "firebase_uid": "VARCHAR(255)",
                "stripe_customer_id": "VARCHAR(255)",
                "is_premium": "BOOLEAN",
                "daily_usage": "TEXT",
                "voice_seconds_today": "INTEGER",
                "voice_usage_date": "VARCHAR(10)",
                "premium_until": "TIMESTAMP",
                "fcm_token": "VARCHAR(255)",
                "last_notification_sent": "TIMESTAMP",
                "education_level": "VARCHAR(30)",
                "favorite_subject": "VARCHAR(50)",
                "exam_date": "TIMESTAMP",
                "onboarding_completed": "BOOLEAN",
                "suggested_topic": "VARCHAR(255)",
                "suggested_topic_date": "VARCHAR(10)",
                "last_login": "TIMESTAMP",
            }
            with engine.connect() as _conn:
                for _col, _sqltype in _new_cols.items():
                    if _col not in _existing_cols:
                        _conn.execute(_sa_text(f"ALTER TABLE users ADD COLUMN {_col} {_sqltype}"))
                        _conn.commit()
                        print(f"✅ Dodano kolumne users.{_col}")
    except Exception as e:
        print(f"⚠️ Migracja kolumn users: {e}")

    # NAPRAWIONE (user 04.09.2026, real-blad: proba anulowania subskrypcji
    # rzucila surowy blad SQL Postgresa "invalid input syntax for type
    # integer" przy zapytaniu o subscriptions.user_id): kolumna byla
    # blednie utworzona jako Integer (patrz models.py Subscription), mimo
    # ze user_id to zawsze Firebase UID - alfanumeryczny string (np.
    # "yXsgnTJdl1OLsFmvLte2zWLBQcR2"). Na SQLite dzialalo to przypadkiem
    # (luzne typowanie), na Postgresie/Supabase (produkcja) kazde
    # zapytanie/insert z prawdziwym UID w tej kolumnie konczylo sie
    # twardym bledem typu. ALTER COLUMN TYPE ... USING to skladnia
    # WYLACZNIE Postgresa (SQLite nie wspiera ALTER COLUMN w ten sposob),
    # stad jawny warunek - na SQLite nic nie robimy (i tak "dzialalo").
    # Idempotentne: sprawdzamy PRAWDZIWY typ kolumny w bazie przed zmiana,
    # bezpieczne przy kazdym restarcie.
    try:
        from sqlalchemy import inspect as _sa_inspect2, text as _sa_text2
        if "sqlite" not in settings.DATABASE_URL:
            _insp2 = _sa_inspect2(engine)
            if "subscriptions" in _insp2.get_table_names():
                _sub_cols = {c["name"]: str(c["type"]).upper() for c in _insp2.get_columns("subscriptions")}
                _uid_type = _sub_cols.get("user_id", "")
                if _uid_type and "CHAR" not in _uid_type and "TEXT" not in _uid_type:
                    with engine.connect() as _conn2:
                        _conn2.execute(_sa_text2(
                            "ALTER TABLE subscriptions ALTER COLUMN user_id TYPE VARCHAR(128) USING user_id::VARCHAR"
                        ))
                        _conn2.commit()
                        print("✅ Naprawiono typ subscriptions.user_id (Integer -> VARCHAR)")
    except Exception as e:
        print(f"⚠️ Migracja typu subscriptions.user_id: {e}")

    print("=" * 60)
    print("🚀 AI TEACHER BACKEND STARTED!")
    print(f"🔑 OpenAI: {'✅ ' + settings.OPENAI_API_KEY[:20] + '...' if settings.OPENAI_API_KEY else '❌ MISSING'}")
    print(f"📍 Docs:      http://127.0.0.1:8000/docs")
    print(f"💬 Chat:      http://127.0.0.1:8000/chat")
    print(f"🎯 Quiz:      http://127.0.0.1:8000/quiz")
    print(f"💎 Dashboard: http://127.0.0.1:8000/static/dashboard_FINAL.html")
    print(f"🎤 Voice:     http://127.0.0.1:8000/static/voice_conversation.html")
    print("=" * 60)

try:
    from .api.whiteboard import router as whiteboard_router
    app.include_router(whiteboard_router)
    print("✅ whiteboard OK")
except Exception as e:
    print(f"❌ whiteboard: {e}")

try:
    from .api.multiplayer import router as multiplayer_router
    app.include_router(multiplayer_router)
    print("✅ multiplayer OK")
except Exception as e:
    print(f"❌ multiplayer: {e}")
