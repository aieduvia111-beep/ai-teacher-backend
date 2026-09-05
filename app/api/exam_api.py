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
from ..job_store import create_job, set_done, set_error, get_job, pop_job, cleanup_old_jobs
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
    """Uzywane TYLKO gdy PDF faktycznie NIE powstal (np. 0 zaakceptowanych
    zadan) - zero pliku w odpowiedzi, user dostaje jasny komunikat i moze
    sprobowac ponownie. Dla przypadku "PDF powstal, ale z mniejsza niz
    zamowiona liczba zadan" patrz _shortfall_headers ponizej - TEN
    przypadek TERAZ oddaje PDF, nie ten JSON (patrz komentarz nizej)."""
    return {
        "success": False,
        "status": "incomplete_generation",
        "message": shortfall_info["message"],
        "requested_count": shortfall_info["requested_count"],
        "accepted_count": shortfall_info["accepted_count"],
    }


def _shortfall_headers(shortfall_info: dict) -> dict:
    """NOWE (user, 29.08.2026 - po 3. z rzedu real-tescie trudnej
    trygonometrii, ostatni raz 13/15 po PELNYCH 3 minutach oczekiwania):
    "bez jaj nie mozemy tak zrobic ze czekac 5 minut kurwa na sprawdzian
    musimy miec inne rozwiazanie". Podnoszenie budzetu czasowego bez
    konca to slepy zaulek (identyczny wzorzec co przy matematyce/LaTeX-ie
    wczesniej w tej samej sesji - patrz Warstwa 2.5/1.5) - PRAWDZIWY
    problem byl gdzie indziej: _shortfall_response WYZEJ przez caly czas
    WYRZUCAL caly, juz zbudowany i w pelni zweryfikowany PDF (generate_exam
    buduje PDF normalnie NAWET przy niedoborze - patrz jego docstring),
    zmuszajac usera do czekania od zera po raz drugi za KAZDYM razem, gdy
    zabraklo choc 1 z zamowionych zadan - user placil pelnym czasem
    oczekiwania i dostawal NIC.

    Naprawiono: gdy PDF/ZIP FAKTYCZNIE powstal (patrz wywolania nizej),
    oddajemy go userowi OD RAZU (dostaje 13 z 15 poprawnych, zweryfikowanych
    zadan NATYCHMIAST, zamiast czekac druga probe od zera) - ale
    NIEUCCIWIE-CICHO tego nie robimy: te naglowki niosa dokladna informacje
    o niedoborze, a frontend (exam_generator.html) czyta je i pokazuje
    WYRAZNE ostrzezenie (nie chowa faktu niedoboru) zamiast udawac pelny
    sukces. To jest to samo, uczciwe rozroznienie co pierwotny projekt
    _shortfall_response mial na celu ("nie oddawaj po cichu niepelnego PDF
    jako cichy sukces") - tylko ZREALIZOWANE tak, zeby user NIE TRACIL
    juz wykonanej, poprawnej pracy AI z powodu 1-2 brakujacych zadan.
    Naglowki HTTP musza byc ASCII - polskie znaki w komunikacie kodujemy
    percent-encoding (urllib.parse.quote), frontend dekoduje decodeURIComponent."""
    from urllib.parse import quote
    return {
        "X-Shortfall": "1",
        "X-Requested-Count": str(shortfall_info["requested_count"]),
        "X-Accepted-Count": str(shortfall_info["accepted_count"]),
        "X-Shortfall-Message": quote(shortfall_info["message"]),
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
        model="gpt-4o-mini",
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
            # NAPRAWIONE (patrz _shortfall_headers - "bez jaj czekac 5 minut"):
            # PDF/ZIP jest budowany normalnie NAWET przy niedoborze - jesli
            # OBA pliki faktycznie istnieja, oddajemy ZIP z jawnymi
            # naglowkami niedoboru zamiast wyrzucac cala, poprawna prace.
            # _shortfall_response (bez pliku) zostaje TYLKO dla przypadku,
            # gdy plik(i) naprawde nie powstaly.
            if filename_a and os.path.exists(filename_a) and filename_b and os.path.exists(filename_b):
                zip_path = tempfile.mktemp(suffix=".zip")
                with zipfile.ZipFile(zip_path, "w") as zf:
                    zf.write(filename_a, arcname="wariant_A.pdf")
                    zf.write(filename_b, arcname="wariant_B.pdf")
                headers = {"Content-Disposition": "attachment; filename=sprawdzian_AB.zip"}
                worse_shortfall = shortfall_a or shortfall_b
                if worse_shortfall:
                    headers.update(_shortfall_headers(worse_shortfall))
                return FileResponse(path=zip_path, media_type="application/zip", filename="sprawdzian_AB.zip", headers=headers)
            if shortfall_a or shortfall_b:
                return _shortfall_response(shortfall_a or shortfall_b)
            return {"success": False, "error": "Nie udalo sie wygenerowac PDF"}

        filename, shortfall = await loop.run_in_executor(
            _executor, _generate_blocking,
            pelny_temat, req.klasa, req.trudnosc, req.liczba_pytan, settings.OPENAI_API_KEY, req.wariant, req.wlasne_instrukcje
        )
        # NAPRAWIONE (patrz _shortfall_headers powyzej): jesli PDF FAKTYCZNIE
        # powstal (generate_exam buduje go normalnie nawet przy niedoborze),
        # oddajemy go OD RAZU z jawnymi naglowkami niedoboru - user nie traci
        # juz wykonanej, poprawnej pracy AI z powodu 1-2 brakujacych zadan.
        if filename and os.path.exists(filename):
            headers = {"Content-Disposition": "attachment; filename=sprawdzian.pdf"}
            if shortfall:
                headers.update(_shortfall_headers(shortfall))
            return FileResponse(
                path=filename,
                media_type="application/pdf",
                filename=filename.encode('ascii', 'ignore').decode('ascii'),
                headers=headers,
            )
        if shortfall:
            return _shortfall_response(shortfall)
        return {"success": False, "error": "Nie udalo sie wygenerowac PDF"}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# NOWE (05.09.2026, user: "nie moze byc tak ze zamawiasz 5 pytan a dostajesz
# 1 - profesjonalne aplikacje tak nie robia"): endpoint /generate powyzej
# trzyma JEDNO polaczenie HTTP otwarte przez caly czas generowania - a
# kazde polaczenie HTTP ma jakis limit czasu (przegladarka, ewentualny
# proxy). Wczesniejszy fix ograniczyl czasowo mechanizm "ostatecznego
# ratunku" zeby zmiescic sie w tym limicie - kosztem czasem niepelnego
# kompletu pytan, co user uznal za nieakceptowalne.
#
# Prawdziwe rozwiazanie: rozdzielic "poprosic o wygenerowanie" od "czekac
# na wynik". /generate/start odpala generowanie W TLE (bez zadnego
# sztucznego sufitu czasowego innego niz sam, dlugi proces generowania) i
# OD RAZU zwraca job_id. Przegladarka co pare sekund pyta /generate/status
# - dzieki temu NIC nie "timeoutuje" w trakcie oczekiwania, bo nie ma
# jednego dlugiego polaczenia - jest tylko seria krotkich, natychmiastowych
# zapytan o postep. Gdy status=="done", przegladarka pobiera plik z
# /generate/result. Stary /generate (wyzej) zostaje nietkniety (na wypadek
# bezposrednich wywolan API z pominieciem frontendu) - nowe endpointy sa
# tym, czego uzywa teraz exam_generator.html.
# ══════════════════════════════════════════════════════════════════════

async def _run_exam_job(job_id, pelny_temat, klasa, trudnosc, liczba_pytan, wariant, wlasne_instrukcje):
    try:
        loop = asyncio.get_event_loop()
        if wariant == "AB":
            (filename_a, shortfall_a), (filename_b, shortfall_b) = await asyncio.gather(
                loop.run_in_executor(
                    _executor, _generate_blocking,
                    pelny_temat, klasa, trudnosc, liczba_pytan, settings.OPENAI_API_KEY, "A", wlasne_instrukcje
                ),
                loop.run_in_executor(
                    _executor, _generate_blocking,
                    pelny_temat, klasa, trudnosc, liczba_pytan, settings.OPENAI_API_KEY, "B", wlasne_instrukcje
                ),
            )
            if filename_a and os.path.exists(filename_a) and filename_b and os.path.exists(filename_b):
                zip_path = tempfile.mktemp(suffix=".zip")
                with zipfile.ZipFile(zip_path, "w") as zf:
                    zf.write(filename_a, arcname="wariant_A.pdf")
                    zf.write(filename_b, arcname="wariant_B.pdf")
                set_done(job_id, {"kind": "zip", "path": zip_path, "shortfall": shortfall_a or shortfall_b})
                return
            if shortfall_a or shortfall_b:
                set_done(job_id, {"kind": "shortfall_only", "shortfall": shortfall_a or shortfall_b})
                return
            set_error(job_id, "Nie udalo sie wygenerowac PDF")
            return

        filename, shortfall = await loop.run_in_executor(
            _executor, _generate_blocking,
            pelny_temat, klasa, trudnosc, liczba_pytan, settings.OPENAI_API_KEY, wariant, wlasne_instrukcje
        )
        if filename and os.path.exists(filename):
            set_done(job_id, {"kind": "pdf", "path": filename, "shortfall": shortfall})
            return
        if shortfall:
            set_done(job_id, {"kind": "shortfall_only", "shortfall": shortfall})
            return
        set_error(job_id, "Nie udalo sie wygenerowac PDF")
    except Exception as e:
        import traceback
        traceback.print_exc()
        set_error(job_id, str(e))


@router.post("/generate/start")
async def generate_exam_start(req: ExamRequest, user: User = Depends(require_feature_limit("exam"))):
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
        cleanup_old_jobs()
        job_id = create_job()
        asyncio.create_task(_run_exam_job(
            job_id, pelny_temat, req.klasa, req.trudnosc, req.liczba_pytan, req.wariant, req.wlasne_instrukcje
        ))
        return {"success": True, "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@router.get("/generate/status/{job_id}")
async def generate_exam_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Nieznane zadanie generowania (mogło wygasnąć)")
    if job["status"] == "pending":
        return {"status": "pending"}
    if job["status"] == "error":
        return {"status": "error", "error": job["error"]}
    # status == "done" - jesli wynik to WYLACZNIE niedobor bez zadnego pliku
    # (patrz _run_exam_job), oddajemy to od razu tutaj (bez pliku do pobrania),
    # zamiast zmuszac frontend do wywolania /result po nic.
    result = job["result"]
    if result.get("kind") == "shortfall_only":
        pop_job(job_id)
        return _shortfall_response(result["shortfall"])
    return {"status": "done"}


@router.get("/generate/result/{job_id}")
async def generate_exam_result(job_id: str):
    job = pop_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Nieznane zadanie generowania (mogło wygasnąć)")
    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=job["error"])
    if job["status"] != "done":
        raise HTTPException(status_code=425, detail="Wynik jeszcze niegotowy")
    result = job["result"]
    if result.get("kind") == "shortfall_only":
        return _shortfall_response(result["shortfall"])
    is_zip = result["kind"] == "zip"
    fname = "sprawdzian_AB.zip" if is_zip else "sprawdzian.pdf"
    headers = {"Content-Disposition": f"attachment; filename={fname}"}
    if result.get("shortfall"):
        headers.update(_shortfall_headers(result["shortfall"]))
    return FileResponse(
        path=result["path"],
        media_type="application/zip" if is_zip else "application/pdf",
        filename=fname,
        headers=headers,
    )
