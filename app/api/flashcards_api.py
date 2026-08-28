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
niezalezny od Quizu. Reuzywamy TA SAMA, juz zweryfikowana logike
generowania (generate_quiz_from_topic w openai_exam.py - Diversity Engine,
weryfikacja sympy, wszystko) - zero duplikacji, zero nowego ryzyka -
jedyna roznica to KTORY licznik limitu jest sprawdzany, co decyduje
WYLACZNIE endpoint (nie dane od klienta), wiec nie da sie tego obejsc
podajac inna nazwe feature'a w body requestu (bezpieczne z zalozenia)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ..openai_exam import generate_quiz_from_topic
from ..firebase_auth import require_feature_limit
from ..models import User

router = APIRouter(prefix="/api/v1/flashcards", tags=["flashcards"])


def _shortfall_response(quiz: dict, requested_count: int):
    """Identyczny mechanizm co quiz_api._shortfall_response - bez tego
    niepelna generacja (mniej fiszek niz zamowiono) wygladalaby cicho
    jak pelny sukces, tak jak to bylo w Quizie PRZED naprawa (patrz
    ETAP 2, Punkt 2 w quiz_api.py)."""
    warning = quiz.get("_shortfall_warning")
    if not warning:
        return None
    accepted = len(quiz.get("questions", []))
    return {
        "success": False,
        "status": "incomplete_generation",
        "message": warning,
        "requested_count": requested_count,
        "accepted_count": accepted,
        "quiz": quiz,
    }


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
        result = await generate_quiz_from_topic(
            topic=req.topic, subject=req.subject, level=req.level,
            num_questions=req.num_questions, difficulty=req.difficulty,
            wlasne_instrukcje=wlasne,
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
