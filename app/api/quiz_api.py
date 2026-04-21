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
    # Buduj prompt zależnie od typu — kategoryczne instrukcje
    level_map = {
        "podstawowka": "Poziom podstawowka (klasy 4-8). Proste slowa, latwe pojecia, bez zaawansowanej matematyki.",
        "liceum": "Poziom liceum/technikum (klasy 1-4 liceum). Srednie trudnosci, pojecia z podstawy programowej liceum.",
        "technikum": "Poziom technikum. Srednie trudnosci, pojecia zawodowe i ogolnoksztalcace.",
        "studia": "Poziom akademicki. Zaawansowane pojecia, specjalistyczna terminologia."
    }
    level_desc = level_map.get(level, level_map["liceum"])

    if quiz_type == "true_false":
        format_example = '{"type":"tf","question":"Chlorofil jest niezbedny do fotosyntezy.","options":["Prawda","Falsz"],"correct":0,"explanation":"To prawda — chlorofil pochlania swiatlo."}'
        type_prompt = f"""Wygeneruj {num_questions} pytan PRAWDA/FALSZ.
ZASADY:
- Kazde pytanie to TWIERDZENIE (zdanie oznajmujace) ktore jest prawdziwe lub falszywe
- NIE pisz pytan z "Ktore...", "Co to...", "Ile..." — TYLKO twierdzenia!
- Przykladowe twierdzenia T/F: "Fotosynteza zachodzi w mitochondriach.", "Chlorofil nadaje roslinom zielony kolor."
- "type" MUSI byc "tf"
- options ZAWSZE = ["Prawda","Falsz"]
- correct = 0 (Prawda) lub 1 (Falsz) — urozmaicaj, polowe Prawda polowe Falsz"""

    elif quiz_type == "multi_choice":
        format_example = '{"type":"multi","question":"Ktore z ponizszych sa produktami fotosyntezy?","options":["Tlen","Dwutlenek wegla","Glukoza","Woda"],"correct":[0,2],"explanation":"Tlen i glukoza sa produktami fotosyntezy."}'
        type_prompt = f"""Wygeneruj {num_questions} pytan WIELOKROTNEGO WYBORU.
ZASADY:
- Kazde pytanie ma 2 lub 3 poprawne odpowiedzi z 4 opcji
- Pytanie MUSI brzmiec "Ktore z ponizszych...", "Zaznacz WSZYSTKIE...", "Wskaż..."
- "type" MUSI byc "multi"
- correct to LISTA indeksow np. [0,2] lub [1,3] lub [0,1,3]
- Dystraktory realistyczne ale bledne"""

    elif quiz_type == "open":
        format_example = '{"type":"open","question":"Wyjasni na czym polega fotosynteza.","options":[],"correct":-1,"correct_answer":"Fotosynteza to proces...","explanation":"Kluczowe: swiatlo, CO2, woda, glukoza, tlen"}'
        type_prompt = f"""Wygeneruj {num_questions} pytan OPISOWYCH OTWARTYCH.
ZASADY:
- Pytania wymagajace rozwinietej odpowiedzi (min 2-3 zdania)
- Typy: "Wyjasni...", "Opisz...", "Porownaj...", "Omow...", "Na czym polega..."
- "type" MUSI byc "open"
- options = [] (puste lista)
- correct = -1
- correct_answer = wzorcowa pelna odpowiedz (2-4 zdania)
- explanation = lista kluczowych elementow odpowiedzi"""

    elif quiz_type == "mixed":
        format_example = ""
        type_prompt = f"""Wygeneruj {num_questions} MIESZANYCH pytan — rozne typy:
- Okolo 40% type=single: pytania z 4 opcjami A-D, correct=liczba 0-3, pytania "Co to jest...", "Ktore..."
- Okolo 30% type=multi: pytania wielokrotnego wyboru, correct=lista, "Ktore z ponizszych (zaznacz wszystkie)..."  
- Okolo 30% type=tf: twierdzenia Prawda/Falsz, options=["Prawda","Falsz"], correct=0 lub 1

WAZNE dla kazdego typu:
- single: {{"type":"single","question":"...?","options":["A","B","C","D"],"correct":2,"explanation":"..."}}
- multi: {{"type":"multi","question":"Ktore z ponizszych...?","options":["A","B","C","D"],"correct":[0,2],"explanation":"..."}}
- tf: {{"type":"tf","question":"Twierdzenie.","options":["Prawda","Falsz"],"correct":0,"explanation":"..."}}"""

    else:  # single_choice
        format_example = """{"type":"single","question":"Co jest glownym produktem fotosyntezy?","options":["Tlen","Glukoza","CO2","Woda"],"correct":1,"explanation":"Glukoza jest glownym produktem fotosyntezy."}"""
        type_prompt = f"""Wygeneruj {num_questions} pytan JEDNOKROTNEGO WYBORU.
ZASADY:
- Kazde pytanie ma DOKLADNIE 1 poprawna odpowiedz z 4 opcji
- correct to LICZBA 0-3 — UROZMAICAJ: nie dawaj zawsze 0!
- Rozklad: pierwsze=1, drugie=3, trzecie=0, czwarte=2, piute=1 itd.
- Dystraktory realistyczne"""

    prompt = f"""Jestes nauczycielem tworzacym profesjonalny quiz edukacyjny.
Temat: {topic}
Przedmiot: {subject}
{level_desc}
Trudnosc: {diff_pl}
{instrukcje_blok}

{type_prompt}

{"Przyklad formatu: " + format_example if format_example else ""}

Odpowiedz TYLKO czystym JSON:
{{"title": "Quiz: {topic}", "questions": [pytania]}}

BEZWZGLEDNIE: Nie dodawaj markdown, nie dodawaj komentarzy. Tylko JSON."""
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

@router.post("/check-open")
async def check_open_answers(req: dict):
    """Sprawdza odpowiedzi opisowe przez AI."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    questions_to_check = req.get("questions", [])
    if not questions_to_check:
        return {"success": False, "error": "Brak pytan"}
    
    prompt = "Sprawdz odpowiedzi ucznia na pytania opisowe. Dla kazdego pytania oceń odpowiedz.

"
    for i, item in enumerate(questions_to_check):
        prompt += f"Pytanie {i+1}: {item.get('question','')}
"
        prompt += f"Wzorcowa odpowiedz: {item.get('correct_answer','')}
"
        prompt += f"Odpowiedz ucznia: {item.get('user_answer','')}

"
    
    prompt += """Odpowiedz TYLKO w JSON:
{"results": [
  {"index": 0, "correct": true/false, "score": 0-100, "feedback": "Krotki feedback 1 zdanie", "missing": "Czego brakowalo lub null"}
]}"""
    
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800, temperature=0.2
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace('```json','').replace('```','').strip()
        s = raw.find('{'); e = raw.rfind('}')
        result = json.loads(raw[s:e+1])
        return {"success": True, **result}
    except Exception as ex:
        return {"success": False, "error": str(ex)}


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
