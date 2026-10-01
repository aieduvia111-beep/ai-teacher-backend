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
wywolanie AI (_generate_flashcards_fast ponizej), bez retry/weryfikacji.

ZMIERZONE (01.10.2026, lokalny test REALNYM wywolaniem OpenAI, user
zaakceptowal koszt): jedno wywolanie na 10 kart z odpowiedziami 2-3-zdaniowymi
trwalo 8.9-11.4s - WOLNIEJ niz user oczekiwal, bo czas generacji LLM skaluje
sie z liczba tokenow WYJscia, a 10 wieloziedaniowych odpowiedzi w jednym
wywolaniu to sporo tokenow do wygenerowania zanim cokolwiek wraca (brak
streamingu). Dwie zmiany ponizej to bezposrednia odpowiedz na to pomiary:
(1) odpowiedzi skrocone do 1 zdania (mniej tokenow = krocej), (2) generacja
podzielona na 2 ROWNOLEGLE wywolania po polowie kart kazde (asyncio.gather) -
czas calosci ograniczony przez WOLNIEJSZE z dwoch, nie suma obu, wiec w
przyblizeniu ~polowa poprzedniego czasu."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import asyncio
import json
from ..config import settings
from ..firebase_auth import require_feature_limit
from ..models import User
from ..level_config import is_known_level, describe_level

router = APIRouter(prefix="/api/v1/flashcards", tags=["flashcards"])

# NAPRAWIONE (01.10.2026, realny test: 4 rownolegle wywolania BEZ przypisanego
# "kata" dawaly masowe duplikaty - np. "jakie byly przyczyny II wojny" wyszlo
# 3x niemal identycznie, bo kazde wywolanie dzialalo w izolacji, nie widzac co
# generuja pozostale, i kazde niezaleznie "skakalo" do tych samych,
# najbardziej oczywistych pytan o dany temat). Przypisanie KAZDEJ partii
# INNEGO, wymuszonego kata tematu eliminuje nakladanie sie Z KONSTRUKCJI,
# bez potrzeby komunikacji miedzy wywolaniami (co zniszczyloby rownoleglosc/
# szybkosc) - efekt uboczny: fiszki maja teraz tez sensowna, pedagogiczna
# strukture (fakty -> przyczyny -> wydarzenia -> skutki) zamiast przypadkowej.
## NAPRAWIONE #2 (01.10.2026, realny test z tematem matematycznym): JEDEN
# uniwersalny zestaw katow ("przyczyny/skutki") dzialal dobrze dla historii,
# ale dla matematyki/fizyki wymuszal sztuczny podzial, ktory i tak zbiegal
# do tych samych podstawowych definicji w kilku partiach (3x niemal
# identyczne "czym sa wzory Viete'a"). Katy sa wiec teraz DOPASOWANE DO
# TYPU PRZEDMIOTU - STEM dostaje podzial pasujacy do matematyki/fizyki
# (definicje/wzory/przyklady/bledy), przedmioty narracyjne (historia,
# biologia, geografia) zostaja przy fakty/przyczyny/wydarzenia/skutki,
# jezyki dostaja wlasny (slownictwo/gramatyka/uzycie/bledy).
_ANGLES_STEM = [
    "podstawowe definicje i pojęcia",
    "wzory, zasady lub twierdzenia",
    "przykłady zastosowań i obliczeń krok po kroku",
    "typowe błędy i pułapki uczniów przy tym temacie",
]
_ANGLES_NARRATIVE = [
    "podstawowe fakty, definicje i daty",
    "przyczyny, okoliczności i kontekst",
    "kluczowe wydarzenia, osoby lub etapy",
    "skutki, znaczenie i wnioski",
]
_ANGLES_LANGUAGE = [
    "kluczowe słownictwo i pojęcia",
    "zasady gramatyczne lub reguły językowe",
    "przykłady użycia w zdaniu lub kontekście",
    "częste błędy i wyjątki od reguł",
]
_ANGLES_DEFAULT = [
    "podstawowe fakty i definicje",
    "szczegóły, mechanizmy i zależności",
    "przykłady i zastosowania",
    "podsumowanie i najważniejsze wnioski",
]
_SUBJECT_ANGLE_SETS = {
    "matematyka": _ANGLES_STEM, "fizyka": _ANGLES_STEM, "chemia": _ANGLES_STEM, "informatyka": _ANGLES_STEM,
    "historia": _ANGLES_NARRATIVE, "biologia": _ANGLES_NARRATIVE, "geografia": _ANGLES_NARRATIVE,
    "polski": _ANGLES_LANGUAGE, "angielski": _ANGLES_LANGUAGE,
}


def _angles_for_subject(subject: str) -> list:
    return _SUBJECT_ANGLE_SETS.get((subject or "").strip().lower(), _ANGLES_DEFAULT)


# NAPRAWIONE (01.10.2026, user: "sprawdz czy fiszki sa zajebiste" -> test
# pokazal 9/10 unikalnych, nie 10/10: dwa pytania o ta sama definicje w
# dwoch roznych "katach", np. "Czym jest fotosynteza?" i "Co to jest
# fotosynteza?" - kąty ograniczaja NAKLADANIE SIE TEMATOW, ale nie gwarantuja
# ze dwa rozne katy nigdy nie zjada do tego samego podstawowego pytania dla
# prostych tematow). Lekki, szybki filtr podobienstwa (nakladanie sie slow
# kluczowych, bez kolejnego wywolania AI) + JEDNO uzupelniajace wywolanie
# TYLKO gdy faktycznie znaleziono duplikaty - w normalnym przypadku (bez
# duplikatow) nie dodaje ZADNEGO czasu.
_STOPWORDS = {"co","to","jest","są","czym","jakie","jaki","jaka","jakich",
              "dla","w","z","i","na","o","do","się","jak","po","oraz","aby",
              "przy","od","za","bez","the","a","an","is","are","what"}


def _keywords(text: str) -> set:
    import re
    words = re.findall(r"[\wąćęłńóśźż]+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _is_near_duplicate(q1: str, q2: str, threshold: float = 0.6) -> bool:
    w1, w2 = _keywords(q1), _keywords(q2)
    if not w1 or not w2:
        return False
    overlap = len(w1 & w2) / min(len(w1), len(w2))
    return overlap >= threshold


def _dedupe_cards(cards: list, kept: list = None) -> list:
    """Zwraca `cards` z odfiltrowanymi fiszkami, ktorych pytanie jest
    bliskim duplikatem czegos juz w `kept` (domyslnie: samych siebie,
    kolejno)."""
    result = list(kept) if kept else []
    for c in cards:
        q = c.get("question", "")
        if q and any(_is_near_duplicate(q, k.get("question", "")) for k in result):
            continue
        result.append(c)
    return result


async def _generate_flashcards_batch(topic: str, subject: str, level_line: str, extra: str, n: int, angle: str, client) -> list:
    """Jedno wywolanie AI na `n` kart skupionych na jednym `angle` (kacie
    tematu) - patrz _generate_flashcards_fast nizej, ktora wola to
    rownolegle kilka razy, kazde z innym katem, dla szybkosci BEZ
    duplikatow."""
    prompt = f"""Stworz {n} fiszek edukacyjnych do nauki na temat: "{topic}" (przedmiot: {subject}).
{level_line}{extra}

Skup sie WYLACZNIE na tym aspekcie tematu: {angle}. Nie wychodz poza ten aspekt - inne partie fiszek (generowane osobno) pokrywaja pozostale aspekty.
Kazda fiszka: KROTKIE pytanie/pojecie (przod) + JEDNO zwiezle, konkretne zdanie odpowiedzi/definicji (tyl, max ok. 20 slow - bez rozwlekania).

Zwroc WYLACZNIE JSON w formacie:
{{"questions": [{{"question": "...", "explanation": "..."}}]}}"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return (data.get("questions") or [])[:n]


async def _generate_flashcards_fast(topic: str, subject: str, level: str, num_cards: int, wlasne_instrukcje: str = "") -> list:
    """Szybka, lekka generacja fiszek - do 4 ROWNOLEGLYCH wywolan gpt-4o-mini
    (po ~2-3 karty kazde), zero petli weryfikacyjnych (patrz uzasadnienie w
    docstringu modulu wyzej). ZMIERZONE (01.10.2026, realne wywolania
    OpenAI): 2 rownolegle wywolania (po 5 kart) = 5.8-6.7s; 4 rownolegle
    (po 2-3 karty) = 2.6-2.9s - wiecej, mniejszych wywolan rownoleglych
    jest szybsze niz mniej, wiekszych, bo czas kazdego pojedynczego
    wywolania skaluje sie z liczba generowanych tokenow, a wszystkie
    dzialaja rownolegle (calosc ogranicza NAJWOLNIEJSZE, nie suma).
    Zwraca liste dictow {"question":..., "explanation":...} - DOKLADNIE
    ksztalt, jakiego oczekuje static/flashcards.html (patrz
    `d.quiz.questions.map(q=>({f:q.question,b:q.explanation}))`)."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    level_line = describe_level(level, subject=subject) if is_known_level(level) else f"Poziom ucznia: {level}."
    extra = f"\nDodatkowe instrukcje: {wlasne_instrukcje}" if wlasne_instrukcje.strip() else ""

    num_batches = min(4, num_cards) or 1
    base = num_cards // num_batches
    remainder = num_cards - base * num_batches
    sizes = [base + (1 if i < remainder else 0) for i in range(num_batches)]
    sizes = [n for n in sizes if n > 0]
    angles = _angles_for_subject(subject)[:len(sizes)]

    results = await asyncio.gather(*[
        _generate_flashcards_batch(topic, subject, level_line, extra, n, angle, client)
        for n, angle in zip(sizes, angles)
    ])
    cards = [c for batch in results for c in batch]

    unique_cards = _dedupe_cards(cards)
    shortfall = num_cards - len(unique_cards)
    if shortfall > 0:
        existing_qs = "; ".join(c.get("question", "") for c in unique_cards if c.get("question"))
        avoid_note = f"\nUNIKAJ pytan podobnych do juz istniejacych: {existing_qs}" if existing_qs else ""
        backfill = await _generate_flashcards_batch(
            topic, subject, level_line, extra + avoid_note, shortfall,
            "dodatkowe, inne aspekty tematu niz juz wykorzystane", client,
        )
        unique_cards = _dedupe_cards(backfill, kept=unique_cards)

    return unique_cards[:num_cards]


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
