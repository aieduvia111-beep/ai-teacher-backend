from ..error_logger import log_error
"""QUIZ API - generowanie quizu z obrazka, tematu lub pliku PDF/DOCX"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from ..config import settings
from ..openai_exam import (
    generate_quiz_from_image, generate_quiz_from_topic,
    sanitize_latex_json_backslashes, fix_latex_in_quiz,
)
from ..firebase_auth import require_feature_limit
from ..models import User
import os, base64, json
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/v1/quiz", tags=["quiz"])
_executor = ThreadPoolExecutor(max_workers=4)


def _shortfall_response(quiz: dict, requested_count: int):
    """ETAP 2, Punkt 2 (pierwotna wersja): quiz["_shortfall_warning"] byl
    dotad MARTWYM polem - ustawiany przez backend, ale nigdy nie czytany
    tutaj ani przez frontend, wiec user dostawal cichy success:true z
    mniejsza liczba pytan niz zamowil, bez zadnej informacji dlaczego.

    NAPRAWIONE PONOWNIE (user, 29.08.2026 - identyczny problem i naprawa
    co w exam_api.py _shortfall_headers, patrz tam pelne uzasadnienie:
    "bez jaj czekac 5 minut na sprawdzian musimy miec inne rozwiazanie"):
    pierwotna wersja wracala success:false + "quiz" w ciele, ALE frontend
    (quiz_app.html) na status=='incomplete_generation' po prostu rzucal
    blad i NIGDY nie uzywal dolaczonego "quiz" - user placil pelnym
    czasem oczekiwania i dostawal PUSTY ekran bledu, mimo ze quiz z
    mniejsza (ale w pelni zweryfikowana) liczba pytan JUZ ISTNIAL w tej
    samej odpowiedzi. Teraz: jesli jest CHOC JEDNO zaakceptowane pytanie,
    zwracamy success:true (user dostaje quiz OD RAZU, nie czeka od zera
    drugi raz) + osobne pole "shortfall_message" (frontend pokazuje
    JAWNE, ale nieblokujace ostrzezenie - NIE chowa faktu niedoboru,
    tylko nie wyrzuca juz wykonanej pracy). Zwraca None, jesli wszystko
    w porzadku (pelna liczba pytan) - BEZ zmian wzgledem wczesniej."""
    # "B2" (30.08.2026): _difficulty_downgrade_notice moze byc obecne
    # NAWET gdy _shortfall_warning juz nie ma (B2 w pelni domknal luke) -
    # user i tak powinien wiedziec, ze CZESC pytan jest latwiejsza niz
    # zamowiona, wiec oba komunikaty (jesli oba istnieja) laczymy w JEDEN,
    # zamiast pokazywac tylko jeden z nich.
    shortfall_warning = quiz.get("_shortfall_warning")
    downgrade_notice = quiz.get("_difficulty_downgrade_notice")
    warning = " ".join(m for m in (shortfall_warning, downgrade_notice) if m) or None
    if not warning:
        return None
    accepted = len(quiz.get("questions", []))
    if accepted > 0:
        return {"success": True, "quiz": quiz, "shortfall_message": warning}
    return {
        "success": False,
        "status": "incomplete_generation",
        "message": warning,
        "requested_count": requested_count,
        "accepted_count": accepted,
        "quiz": quiz,
    }

class QuizImageRequest(BaseModel):
    image: str
    num_questions: int = 10
    difficulty: str = "medium"
    wlasne_instrukcje: str = ""

class QuizTopicRequest(BaseModel):
    topic: str
    subject: str = "matematyka"
    level: str = "liceum"
    num_questions: int = 10
    difficulty: str = "medium"
    wlasne_instrukcje: str = ""

class QuizFileRequest(BaseModel):
    document: str              # base64
    document_type: str = ""
    document_name: str = ""
    num_questions: int = 10
    difficulty: str = "medium"
    subject: str = "ogolny"
    level: str = "liceum"
    wlasne_instrukcje: str = ""

def _build_instrukcje_blok(wlasne: str) -> str:
    """Buduje blok wlasnych instrukcji do prompta - tylko ASCII."""
    if not wlasne or not wlasne.strip():
        return ""
    return (
        "\n=== WLASNE INSTRUKCJE (NAJWYZSZY PRIORYTET) ===\n"
        "Uczen podal nastepujace instrukcje. MUSISZ je bezwzglednie uwzglednic:\n"
        f"{wlasne.strip()}\n"
        "Dostosuj CALY quiz do powyzszych wskazowek.\n"
    )

def _extract_text(doc_base64: str, doc_type: str, doc_name: str) -> str:
    data = base64.b64decode(doc_base64)
    ext = (doc_name or "").lower().split(".")[-1]

    if ext == "pdf" or "pdf" in (doc_type or ""):
        try:
            import pypdf, io
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join(p.extract_text() or "" for p in reader.pages[:20])[:8000]
        except Exception:
            pass
        try:
            import pdfplumber, io
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages[:20])[:8000]
        except Exception:
            pass

    if ext in ("docx", "doc") or "word" in (doc_type or ""):
        try:
            import docx, io
            doc = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:8000]
        except Exception:
            pass

    return ""

@router.post("/generate")
async def quiz_from_image(req: QuizImageRequest, user: User = Depends(require_feature_limit("quiz"))):
    try:
        result = await generate_quiz_from_image(req.image, req.num_questions, req.difficulty)
        if not result["success"]:
            return {"success": False, "error": result.get("error")}
        # Jezeli sa wlasne instrukcje - dodaj je do tytulu zeby zaznaczyc ze zostaly uwzglednione
        # Obrazki sa analizowane przez Vision - instrukcje przekazujemy przez temat
        quiz = result["quiz"]
        if req.wlasne_instrukcje and req.wlasne_instrukcje.strip():
            # Wstrzyknij instrukcje jako dodatkowy kontekst do tytulu (Vision nie przyjmuje prompta)
            quiz["_instrukcje"] = req.wlasne_instrukcje.strip()
        shortfall = _shortfall_response(quiz, req.num_questions)
        if shortfall:
            return shortfall
        return {"success": True, "quiz": quiz}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/generate-topic")
async def quiz_from_topic(req: QuizTopicRequest, user: User = Depends(require_feature_limit("quiz"))):
    try:
        wlasne = (req.wlasne_instrukcje or "").strip()
        print(f"[Quiz-Topic] temat='{req.topic}' wlasne='{wlasne[:60] if wlasne else 'BRAK'}'")
        # NAPRAWIONE: ten endpoint wolal wczesniej wlasna, zduplikowana
        # funkcje (_generate_topic_with_instrukcje), ktora NIGDY nie
        # wywolywala describe_level() - "Poziom: {level}" trafial do prompta
        # jako surowy string (np. "liceum_2") bez ZADNEGO zakresu materialu
        # z SUBJECT_SCOPE ani klauzuli trudnosci. To byl realny powod, dla
        # ktorego produkcyjny Quiz mogl wygenerowac cos w stylu "oblicz
        # 24-32" dla liceum_2 - cala praca w level_config.py (SUBJECT_SCOPE,
        # klauzula "nie upraszczaj") nigdy tu nie docierala. generate_quiz_from_topic
        # w openai_exam.py juz to wszystko ma (plus priorytet tematu nad
        # poziomem, plus lepsza sanityzacja JSON) - wiec wolamy ja tutaj
        # zamiast utrzymywac dwie rozjezdzajace sie implementacje.
        result = await generate_quiz_from_topic(
            topic=req.topic, subject=req.subject, level=req.level,
            num_questions=req.num_questions, difficulty=req.difficulty,
            wlasne_instrukcje=wlasne
        )
        if result["success"]:
            quiz = result["quiz"]
            shortfall = _shortfall_response(quiz, req.num_questions)
            if shortfall:
                return shortfall
            return {"success": True, "quiz": quiz}
        return {"success": False, "error": result.get("error")}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/generate-file")
async def quiz_from_file(req: QuizFileRequest, user: User = Depends(require_feature_limit("quiz"))):
    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            _executor, _extract_text, req.document, req.document_type, req.document_name
        )

        if not text.strip():
            return {"success": False, "error": "Nie udalo sie odczytac tekstu z pliku. Sprawdz czy plik nie jest zaszyfrowany lub pusty."}

        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        diff_map = {"easy": "latwy", "medium": "sredni", "hard": "trudny"}
        diff_pl = diff_map.get(req.difficulty, "sredni")
        instrukcje_blok = _build_instrukcje_blok(req.wlasne_instrukcje)

        prompt = f"""Na podstawie ponizszego tekstu wygeneruj quiz z {req.num_questions} pytaniami wielokrotnego wyboru (poziom: {diff_pl}).
{instrukcje_blok}
Tekst:
{text[:5000]}

Odpowiedz TYLKO w formacie JSON (bez markdown):
{{
  "title": "Tytul quizu",
  "questions": [
    {{
      "question": "Tresc pytania?",
      "options": ["A", "B", "C", "D"],
      "correct": 2,
      "explanation": "Krotkie wyjasnienie dlaczego ta odpowiedz jest poprawna"
    }}
  ]
}}
WAZNE: correct to INDEX (0-3) poprawnej odpowiedzi w tablicy options. Urozmaicaj indeksy - NIE dawaj zawsze correct=0!"""

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.7
        )

        raw = resp.choices[0].message.content.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()
        s = raw.find('{'); e = raw.rfind('}')
        raw = sanitize_latex_json_backslashes(raw[s:e+1])
        quiz_data = json.loads(raw)
        quiz_data = fix_latex_in_quiz(quiz_data)

        print(f"[Quiz-File] '{req.document_name}' -> {len(quiz_data.get('questions',[]))} pytan")
        return {"success": True, "quiz": quiz_data}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
