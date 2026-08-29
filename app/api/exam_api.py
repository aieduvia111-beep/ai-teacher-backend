from ..error_logger import log_error
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from ..config import settings
from ..exam_pdf_generator import ExamGenerator
from ..openai_vision import analyze_image_with_gpt4_vision
from ..firebase_auth import require_feature_limit
from ..models import User
import os, json, zipfile, tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/v1/exam", tags=["exam"])
_executor = ThreadPoolExecutor(max_workers=4)

class ExamRequest(BaseModel):
    temat: Optional[str] = None
    klasa: str = "liceum"
    przedmiot: str = "Matematyka"
    trudnosc: str = "srednia"
    # NAPRAWIONE: suwak we frontendzie mial max=30, ale realny test (n=30,
    # rownania kwadratowe z parametrem, srednia) pokazal, ze budzet
    # czasowy generowania (60s) bywa przekraczany (~70s tresci + PDF),
    # zostawiajac coraz cieńszy margines do timeoutu frontendu (120s).
    # Frontend juz ma max=20 (patrz exam_generator.html), ten limit tutaj
    # to autorytatywne wymuszenie po stronie serwera - zeby bezposrednie
    # wywolanie API (z pominieciem frontendu) nie mogło obejsc ograniczenia.
    liczba_pytan: int = Field(default=12, ge=1, le=20)
    wariant: Optional[str] = "A"
    wlasne_instrukcje: Optional[str] = None
    image: Optional[str] = None
    images: Optional[List[str]] = None

def _generate_blocking(pelny_temat, klasa, trudnosc, liczba_pytan, api_key, wariant, wlasne_instrukcje=None):
    """Zwraca (fname, shortfall_info) - patrz ExamGenerator.generate_exam."""
    gen = ExamGenerator(api_key)
    return gen.generate_exam(
        temat=pelny_temat, klasa=klasa,
        trudnosc=trudnosc, liczba_pytan=liczba_pytan,
        wariant=wariant, wlasne_instrukcje=wlasne_instrukcje
    )


def _shortfall_response(shortfall_info: dict):
    """ETAP 2, Punkt 2: identyczny mechanizm co quiz_api._shortfall_response -
    zamiast po cichu oddac niepelny PDF jako sukces, zwracamy kontrolowany
    stan incomplete_generation. Zero PDF w odpowiedzi - user dostaje jasny
    komunikat i moze sprobowac ponownie (patrz Punkt 3, frontend)."""
    return {
        "success": False,
        "status": "incomplete_generation",
        "message": shortfall_info["message"],
        "requested_count": shortfall_info["requested_count"],
        "accepted_count": shortfall_info["accepted_count"],
    }

async def _extract_topic_from_images(images: list) -> str:
    """Używa vision żeby wyciągnąć temat ze zdjęć."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    content = []
    for img_b64 in images[:6]:
        b64 = img_b64.split("base64,")[1] if "base64," in img_b64 else img_b64
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
    content.append({
        "type": "text",
        "text": (
            "Przeanalizuj zdjecia i odpowiedz TYLKO w JSON: "
            '{"temat": "Glowny temat do sprawdzianu max 60 znakow", '
            '"przedmiot": "Matematyka/Fizyka/Chemia/Historia/Biologia itp."}'
        )
    })
    resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=200, temperature=0.3
    )
    txt = resp.choices[0].message.content.strip()
    txt = txt.replace('```json', '').replace('```', '').strip()
    s = txt.find('{'); e = txt.rfind('}')
    return json.loads(txt[s:e+1])

@router.post("/generate")
async def generate_exam(req: ExamRequest, user: User = Depends(require_feature_limit("exam"))):
    try:
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        all_images = req.images or ([req.image] if req.image else [])
        temat = req.temat
        przedmiot = req.przedmiot

        if all_images:
            vision_data = await _extract_topic_from_images(all_images)
            temat = vision_data.get('temat', temat)
            przedmiot = vision_data.get('przedmiot', przedmiot)
            print(f"[Vision->Exam] {len(all_images)} zdj -> {przedmiot}: {temat}")

        if not temat:
            raise HTTPException(status_code=422, detail="Podaj temat lub wyslij zdjecie")

        pelny_temat = f"{przedmiot}: {temat}"
        loop = asyncio.get_event_loop()

        # Wariant "AB" generuje OBA warianty w JEDNYM wywolaniu endpointu (wiec
        # i jednym zuzyciu dziennego limitu "exam" - Depends(require_feature_limit)
        # powyzej liczy sie raz na cale zadanie, niezaleznie od tego ile PDF-ow
        # wewnatrz wygenerujemy). Wczesniej klient robil TO DWA oddzielne zadania
        # (wariant A, potem wariant B) - kazde osobno zuzywalo limit 1/dzien, wiec
        # przy darmowym koncie drugie zadanie (wariant B) zawsze dostawalo odmowe
        # i cala funkcja "Wariant A+B" byla realnie zepsuta dla darmowych userow.
        if req.wariant == "AB":
            # NAPRAWIONE: Warianty A i B byly generowane SEKWENCYJNIE (najpierw
            # cale A, potem cale B) mimo ze sa CALKOWICIE niezalezne od siebie
            # (osobne wywolania ExamGenerator, osobne pliki, brak wspoldzielonego
            # stanu miedzy nimi - kazde generate_exam tworzy wlasne
            # seen_fingerprints/used_safe_letters/itd. lokalnie). Realny test
            # (n=20, rownania kwadratowe z parametrem, srednia - najciezszy
            # przypadek) pokazal 114.9s dla sekwencyjnego A+B, zaledwie 5.1s
            # marginesu do ONCZESNIE OBOWIAZUJACEGO timeoutu frontendu
            # (120s wtedy - patrz NOWSZY komentarz w exam_generator.html:
            # timeout frontendu podniesiony do 180s 29.08.2026, razem z
            # backendowym budzetem dla "trudny" 60s->120s) -
            # niebezpiecznie ciasno. Uruchamiamy je teraz ROWNOLEGLE
            # (asyncio.gather) - _executor ma max_workers=4, wystarczajaco na
            # dwa jednoczesne zadania - calkowity czas to czas WOLNIEJSZEGO z
            # dwoch, nie suma, wiec spodziewany spadek z ~115s do ~50-55s.
            (filename_a, shortfall_a), (filename_b, shortfall_b) = await asyncio.gather(
                loop.run_in_executor(
                    _executor, _generate_blocking,
                    pelny_temat, req.klasa, req.trudnosc, req.liczba_pytan, settings.OPENAI_API_KEY, "A", req.wlasne_instrukcje
                ),
                loop.run_in_executor(
                    _executor, _generate_blocking,
                    pelny_temat, req.klasa, req.trudnosc, req.liczba_pytan, settings.OPENAI_API_KEY, "B", req.wlasne_instrukcje
                ),
            )
            if shortfall_a or shortfall_b:
                # Jesli KTORYKOLWIEK wariant ma niepelna liczbe zadan - nie
                # oddawaj po cichu ZIP-a z niekompletnym PDF-em w srodku.
                return _shortfall_response(shortfall_a or shortfall_b)
            if not (filename_a and os.path.exists(filename_a) and filename_b and os.path.exists(filename_b)):
                return {"success": False, "error": "Nie udalo sie wygenerowac PDF"}
            zip_path = tempfile.mktemp(suffix=".zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(filename_a, arcname="wariant_A.pdf")
                zf.write(filename_b, arcname="wariant_B.pdf")
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename="sprawdzian_AB.zip",
                headers={"Content-Disposition": "attachment; filename=sprawdzian_AB.zip"}
            )

        filename, shortfall = await loop.run_in_executor(
            _executor, _generate_blocking,
            pelny_temat, req.klasa, req.trudnosc, req.liczba_pytan, settings.OPENAI_API_KEY, req.wariant, req.wlasne_instrukcje
        )
        if shortfall:
            return _shortfall_response(shortfall)

        if filename and os.path.exists(filename):
            return FileResponse(
                path=filename,
                media_type="application/pdf",
                filename=filename.encode('ascii', 'ignore').decode('ascii'),
                headers={"Content-Disposition": "attachment; filename=sprawdzian.pdf"}
            )
        return {"success": False, "error": "Nie udalo sie wygenerowac PDF"}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
