"""QUIZ API - generowanie quizu z obrazka, tematu lub pliku PDF/DOCX"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from ..config import settings
from ..openai_exam import generate_quiz_from_image, generate_quiz_from_topic
import os, base64, json
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/v1/quiz", tags=["quiz"])
_executor = ThreadPoolExecutor(max_workers=4)

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
    quiz_type: str = "mixed"  # single_choice | multi_choice | true_false | open | mixed

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

async def _generate_topic_with_instrukcje(topic, subject, level, num_questions, difficulty, wlasne_instrukcje, quiz_type="mixed"):
    """Generuje quiz z tematu z wlasnymi instrukcjami bezposrednio przez OpenAI."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    diff_map = {"easy": "latwy", "medium": "sredni", "hard": "trudny"}
    diff_pl = diff_map.get(difficulty, "sredni")
    instrukcje_blok = _build_instrukcje_blok(wlasne_instrukcje)
    type_map = {
        "single_choice": "TYLKO pytania jednokrotnego wyboru. type=single, correct to liczba 0-3.",
        "multi_choice": "TYLKO pytania wielokrotnego wyboru (2-3 poprawne). type=multi, correct to LISTA np. [0,2].",
        "true_false": "TYLKO pytania Prawda/Falsz. Opcje=[Prawda,Falsz]. type=tf, correct=0 lub 1.",
        "open": "TYLKO pytania opisowe. Brak opcji. type=open, correct=-1, correct_answer=pelna odpowiedz.",
        "mixed": f"Wygeneruj MIESZANE typy: polowa type=single (correct=liczba), cwiartka type=multi (correct=lista), cwiartka type=tf.",
    }
    type_instr = type_map.get(quiz_type, type_map["mixed"])
    prompt = f"""Wygeneruj quiz z {num_questions} pytaniami.\nTemat: {topic}\nPrzedmiot: {subject}\nPoziom: {level}\nTrudnosc: {diff_pl}\nTYP PYTAN: {type_instr}\n{instrukcje_blok}\n\nOdpowiedz TYLKO w JSON (bez markdown):\n{{"title":"Tytul","questions":[\n{{"type":"single","question":"?","options":["A","B","C","D"],"correct":2,"explanation":"..."}},\n{{"type":"multi","question":"Ktore?","options":["A","B","C","D"],"correct":[0,2],"explanation":"..."}},\n{{"type":"tf","question":"Prawda?","options":["Prawda","Falsz"],"correct":0,"explanation":"..."}},\n{{"type":"open","question":"Wyjasni?","options":[],"correct":-1,"correct_answer":"Odpowiedz","explanation":"..."}}\n]}}\nWAZNE: Dla single correct=liczba, dla multi correct=lista, dla tf correct=0/1. Urozmaicaj!"""
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5000, temperature=0.7
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.replace('```json', '').replace('```', '').strip()
    s = raw.find('{'); e = raw.rfind('}')
    quiz_data = json.loads(raw[s:e+1])
    print(f"[Quiz-Topic+Instr] '{topic}' -> {len(quiz_data.get('questions',[]))} pytan")
    return {"success": True, "quiz": quiz_data}

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
async def quiz_from_image(req: QuizImageRequest):
    try:
        result = await generate_quiz_from_image(req.image, req.num_questions, req.difficulty)
        if not result["success"]:
            return {"success": False, "error": result.get("error")}
        # Jezeli sa wlasne instrukcje - dodaj je do tytulu zeby zaznaczyc ze zostaly uwzglednione
        # Obrazki sa analizowane przez Vision - instrukcje przekazujemy przez temat
        if req.wlasne_instrukcje and req.wlasne_instrukcje.strip():
            quiz = result["quiz"]
            # Wstrzyknij instrukcje jako dodatkowy kontekst do tytulu (Vision nie przyjmuje prompta)
            quiz["_instrukcje"] = req.wlasne_instrukcje.strip()
        return {"success": True, "quiz": result["quiz"]}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/generate-topic")
async def quiz_from_topic(req: QuizTopicRequest):
    try:
        wlasne = (req.wlasne_instrukcje or "").strip()
        print(f"[Quiz-Topic] temat='{req.topic}' wlasne='{wlasne[:60] if wlasne else 'BRAK'}'")
        qt = getattr(req, 'quiz_type', 'mixed') or 'mixed'
        result = await _generate_topic_with_instrukcje(
            req.topic, req.subject, req.level,
            req.num_questions, req.difficulty, wlasne, qt
        )
        if result["success"]:
            return {"success": True, "quiz": result["quiz"]}
        return {"success": False, "error": result.get("error")}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/generate-file")
async def quiz_from_file(req: QuizFileRequest):
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
        quiz_data = json.loads(raw[s:e+1])

        print(f"[Quiz-File] '{req.document_name}' -> {len(quiz_data.get('questions',[]))} pytan")
        return {"success": True, "quiz": quiz_data}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
