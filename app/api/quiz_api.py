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
    """Generuje quiz z tematu. Zawsze generuje pytania A-D, potem przeksztalca per typ."""
    from openai import AsyncOpenAI
    import random
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    diff_map = {"easy": "latwy", "medium": "sredni", "hard": "trudny"}
    diff_pl = diff_map.get(difficulty, "sredni")
    instrukcje_blok = _build_instrukcje_blok(wlasne_instrukcje)

    level_map = {
        "podstawowka": "klasy 4-8, proste pojecia",
        "liceum": "liceum, sredni poziom, podstawa programowa",
        "technikum": "technikum, sredni poziom",
        "studia": "poziom akademicki, zaawansowane pojecia"
    }
    level_desc = level_map.get(level, level_map["liceum"])

    # Dla open — osobny prompt
    if quiz_type == "open":
        prompt = f"""Jestes nauczycielem. Wygeneruj {num_questions} pytan opisowych otwartych.
Temat: {topic}, Przedmiot: {subject}, Poziom: {level_desc}, Trudnosc: {diff_pl}.
{instrukcje_blok}
Kazde pytanie zaczyna sie od: Wyjasni / Opisz / Porownaj / Omow / Na czym polega.
Format JSON:
{{"title":"Quiz: {topic}","questions":[
  {{"question":"Wyjasni na czym polega fotosynteza.","correct_answer":"Fotosynteza to proces...","explanation":"Kluczowe: swiatlo, CO2, woda"}},
  {{"question":"Opisz role chlorofilu w fotosyntezie.","correct_answer":"Chlorofil...","explanation":"..."}}
]}}
Odpowiedz TYLKO czystym JSON bez markdown."""

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Jestes generatorem quizow. Odpowiadasz WYLACZNIE czystym JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        quiz_data = json.loads(resp.choices[0].message.content)
        # Dodaj type=open do kazdego pytania
        for q in quiz_data.get("questions", []):
            q["type"] = "open"
            q["options"] = []
            q["correct"] = -1
            if not q.get("correct_answer"):
                q["correct_answer"] = q.get("explanation", "")
        return {"success": True, "quiz": quiz_data}

    # Dla pozostalych typow — generuj pytania A-D, potem przeksztalc
    # Dla mixed — generuj wiecej zeby miec materiał do podzielenia
    n = num_questions if quiz_type != "mixed" else num_questions + 2

    prompt = f"""Jestes nauczycielem. Wygeneruj {n} pytan jednokrotnego wyboru z 4 opcjami.
Temat: {topic}, Przedmiot: {subject}, Poziom: {level_desc}, Trudnosc: {diff_pl}.
{instrukcje_blok}
WAZNE: Urozmaicaj poprawna odpowiedz — nie zawsze opcja A (indeks 0)!
Format JSON:
{{"title":"Quiz: {topic}","questions":[
  {{"question":"Pytanie?","options":["opcja A","opcja B","opcja C","opcja D"],"correct":2,"explanation":"Wyjasnienie dlaczego C jest poprawne"}}
]}}
Odpowiedz TYLKO czystym JSON bez markdown."""

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000, temperature=0.7
    )
    raw = resp.choices[0].message.content.strip().replace('```json','').replace('```','').strip()
    s = raw.find('{'); e = raw.rfind('}')
    quiz_data = json.loads(raw[s:e+1])
    questions = quiz_data.get("questions", [])

    # POST-PROCESSING per typ
    if quiz_type == "single_choice":
        for q in questions:
            q["type"] = "single"
            if not isinstance(q.get("correct"), int):
                q["correct"] = 0

    elif quiz_type == "true_false":
        new_qs = []
        for i, q in enumerate(questions[:num_questions]):
            correct_idx = q.get("correct", 0)
            options = q.get("options", [])
            correct_ans = options[correct_idx] if correct_idx < len(options) else ""
            wrong_opts = [o for j,o in enumerate(options) if j != correct_idx]
            wrong_ans = wrong_opts[0] if wrong_opts else ""
            explanation = q.get("explanation", "")
            is_true = (i % 2 == 0)
            if is_true and correct_ans:
                # Twierdzenie prawdziwe — używamy poprawnej odpowiedzi
                statement = f"{correct_ans} jest poprawną odpowiedzią w kontekście tematu {topic}."
                # Lepiej: używamy explanation żeby zbudować twierdzenie
                if explanation:
                    # Bierz pierwsze zdanie z explanation
                    first_sentence = explanation.split('.')[0].strip()
                    if len(first_sentence) > 10:
                        statement = first_sentence + "."
                correct_val = 0
            elif not is_true and wrong_ans:
                # Twierdzenie fałszywe — używamy błędnej odpowiedzi w kontekście
                statement = f"{wrong_ans} jest głównym produktem/elementem procesu związanego z tematem {topic}."
                if explanation:
                    # Neguj pierwsze zdanie
                    first_sentence = explanation.split('.')[0].strip()
                    if len(first_sentence) > 10:
                        statement = f"{wrong_ans}: {first_sentence.lower()}."
                correct_val = 1
            else:
                statement = correct_ans + "." if correct_ans else q.get("question","")
                correct_val = 0
            new_qs.append({
                "type": "tf",
                "question": statement,
                "options": ["Prawda", "Fałsz"],
                "correct": correct_val,
                "explanation": explanation
            })
        questions = new_qs
        quiz_data["questions"] = questions

    elif quiz_type == "multi_choice":
        for q in questions:
            q["type"] = "multi"
            correct_idx = q.get("correct", 0)
            if not isinstance(correct_idx, int):
                correct_idx = 0
            # Dodaj 2 poprawne odpowiedzi — oryginalną i jedną sąsiednią
            opts = q.get("options", [])
            second = (correct_idx + 2) % len(opts) if len(opts) >= 2 else 0
            q["correct"] = sorted(list(set([correct_idx, second])))

    elif quiz_type == "mixed":
        # Podziel: single, multi, tf
        result = []
        for i, q in enumerate(questions[:num_questions]):
            mod = i % 3
            if mod == 0:
                q["type"] = "single"
                if not isinstance(q.get("correct"), int):
                    q["correct"] = 0
            elif mod == 1:
                q["type"] = "multi"
                ci = q.get("correct", 0)
                if not isinstance(ci, int): ci = 0
                opts = q.get("options", [])
                second = (ci + 2) % len(opts) if len(opts) >= 2 else 0
                q["correct"] = sorted(list(set([ci, second])))
            else:
                correct_idx = q.get("correct", 0)
                if not isinstance(correct_idx, int): correct_idx = 0
                options = q.get("options", [])
                correct_ans = options[correct_idx] if correct_idx < len(options) else ""
                explanation = q.get("explanation", "")
                wrong_opts = [o for j,o in enumerate(options) if j != correct_idx]
                wrong_ans = wrong_opts[0] if wrong_opts else ""
                is_true = (i % 2 == 0)
                if is_true and correct_ans:
                    first = explanation.split('.')[0].strip() if explanation else ""
                    statement = (first + ".") if len(first) > 10 else (correct_ans + ".")
                    cv = 0
                elif not is_true and wrong_ans:
                    first = explanation.split('.')[0].strip() if explanation else ""
                    statement = (wrong_ans + ": " + first.lower() + ".") if len(first) > 10 else (wrong_ans + ".")
                    cv = 1
                else:
                    statement = correct_ans + "."
                    cv = 0
                q["type"] = "tf"
                q["question"] = statement
                q["options"] = ["Prawda", "Fałsz"]
                q["correct"] = cv
            result.append(q)
        questions = result
        quiz_data["questions"] = questions

    print(f"[Quiz] '{topic}' typ={quiz_type} -> {len(questions)} pytan")
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
    
    prompt = "Sprawdz odpowiedzi ucznia na pytania opisowe. Dla kazdego pytania ocen odpowiedz.\n\n"
    for i, item in enumerate(questions_to_check):
        prompt += f"Pytanie {i+1}: {item.get('question','')}\n"
        prompt += f"Wzorcowa odpowiedz: {item.get('correct_answer','')}\n"
        prompt += f"Odpowiedz ucznia: {item.get('user_answer','')}\n\n"
    
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
