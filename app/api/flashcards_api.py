from ..error_logger import log_error
"""FLASHCARDS API - dedykowany, BEZPIECZNY endpoint dla Fiszek.

NAPRAWIONE (audyt limitow, sierpien 2026 - user zglosil: "klikam byle
jaka funkcje i wszedzie limit wyczerpany, a nie uzywalem wcale"):
Fiszki wczesniej wolaly WPROST /api/v1/quiz/generate-topic - dzieliły
wiec (po cichu, bez wiedzy usera) TA SAMA serwerowa pule co Quiz
(require_feature_limit("quiz")), mimo ze klient (checkLimit/showLimitPopup)
udawal, ze to OSOBNY licznik "flashcards" (i to jeszcze NIEZGODNY miedzy
plikami - 1 w jednym, 3 w drugim). Efekt: wygenerowanie Fiszek zjadalo
realny slot Quizu (i odwrotnie) bez zadnego ostrzezenia, dajac dokladnie
ten losowy, mylacy wzorzec "limit wyczerpany" na funkcji, ktorej user
"nie uzywal".

Fiszki dostaja teraz WLASNY, prawdziwy, serwerowy limit
(require_feature_limit("flashcards") - patrz usage_limits.py), calkowicie
niezalezny od Quizu.

ZMIENIONE (01.10.2026, user: "nie moze sie 5 sekund generowac"): wczesniej
Fiszki reuzywaly CALY ciezki pipeline Quizu (generate_quiz_from_topic w
openai_exam.py - buforowane batche, archetypy "safe parameter generation",
weryfikacja sympy, Diversity Engine, petle dogenerowania) - ten sam
mechanizm zaprojektowany pod OCENIANE pytania quizowe/egzaminacyjne,
gdzie bledna odpowiedz ma realna cene (zly wynik testu). Fiszki to
niskostawkowa pomoc do samodzielnej nauki - uczen SAM ocenia czy umial
odpowiedz, nic nie jest "oceniane" - nie potrzebuja tego samego rygoru
weryfikacji, a placily za niego czasem generowania. Teraz: JEDNO proste
wywolanie AI (_generate_flashcards_fast ponizej), bez retry/weryfikacji -
wyraznie szybciej, kosztem (akceptowalnym dla fiszek) braku formalnej
weryfikacji poprawnosci kazdej karty."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import json
from ..config import settings
from ..firebase_auth import require_feature_limit
from ..models import User
from ..level_config import is_known_level, describe_level

router = APIRouter(prefix="/api/v1/flashcards", tags=["flashcards"])


async def _generate_flashcards_fast(topic: str, subject: str, level: str, num_cards: int, wlasne_instrukcje: str = "") -> list:
    """Szybka, lekka generacja fiszek - jedno wywolanie gpt-4o-mini, zero
    petli weryfikacyjnych (patrz uzasadnienie w docstringu modulu wyzej).
    Zwraca liste dictow {"question":..., "explanation":...} - DOKLADNIE
    ksztalt, jakiego oczekuje static/flashcards.html (patrz
    `d.quiz.questions.map(q=>({f:q.question,b:q.explanation}))`)."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    level_line = describe_level(level, subject=subject) if is_known_level(level) else f"Poziom ucznia: {level}."
    extra = f"\nDodatkowe instrukcje: {wlasne_instrukcje}" if wlasne_instrukcje.strip() else ""

    prompt = f"""Stworz {num_cards} fiszek edukacyjnych do nauki na temat: "{topic}" (przedmiot: {subject}).
{level_line}{extra}

Kazda fiszka: KROTKIE pytanie/pojecie (przod) + ZWIEZLA, konkretna odpowiedz/definicja (tyl, max 2-3 zdania).
Fiszki maja pokrywac ROZNE aspekty tematu - nie powtarzaj tego samego pytania innymi slowami.

Zwroc WYLACZNIE JSON w formacie:
{{"questions": [{{"question": "...", "explanation": "..."}}]}}"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2500,
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return (data.get("questions") or [])[:num_cards]


class FlashcardsRequest(BaseModel):
    topic: str
    subject: str = "matematyka"
    level: str = "liceum"
    num_questions: int = 10
    difficulty: str = "medium"
    wlasne_instrukcje: str = ""


@router.post("/generate")
async def flashcards_generate(req: FlashcardsRequest, user: User = Depends(require_feature_limit("flashcards"))):
    try:
        wlasne = (req.wlasne_instrukcje or "").strip()
        questions = await _generate_flashcards_fast(
            topic=req.topic, subject=req.subject, level=req.level,
            num_cards=req.num_questions, wlasne_instrukcje=wlasne,
        )
        if not questions:
            return {"success": False, "error": "Nie udało się wygenerować fiszek, spróbuj ponownie."}
        return {"success": True, "quiz": {"questions": questions}}
    except Exception as e:
        log_error("Flashcards", str(e))
        return {"success": False, "error": str(e)}
