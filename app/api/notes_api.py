from ..error_logger import log_error
"""NOTES API - generowanie PDF z tematu LUB zdjecia (1 lub wiele)"""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from ..config import settings
from ..notes_pdf_generator import PremiumNotesGenerator
from ..firebase_auth import require_feature_limit, get_current_app_user
from ..models import User
import os, json
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/v1/notes-pdf", tags=["notes-pdf"])
_executor = ThreadPoolExecutor(max_workers=4)

class NotesRequest(BaseModel):
    temat: str
    klasa: str = "liceum"
    num_sections: int = 3
    pages: Optional[int] = None
    image: Optional[str] = None
    images: Optional[List[str]] = None
    wlasne_instrukcje: Optional[str] = None

class NotesReportRequest(BaseModel):
    key: str
    comment: Optional[str] = None


@router.post("/report")
async def report_notes_error(req: NotesReportRequest, user: User = Depends(get_current_app_user)):
    """Uczen zglasza blad w notatce -> notatka znika z pamieci (patrz app/notes_cache.py)."""
    from .. import notes_cache
    try:
        res = notes_cache.report_note(user.firebase_uid, req.key, req.comment or "")
        return {"success": bool(res.get("ok")), "removed": bool(res.get("removed"))}
    except Exception as e:
        print(f"[NotesReport] blad: {e}")
        return {"success": False}

def _log_notes_metrics(temat: str, klasa: str, t0: float, ok: bool, reason: str = None, from_image: bool = False):
    """Statystyki notatek (19.09.2026): Quiz i Sprawdzian mialy tabele
    generation_request_log, notatki NIE mialy nic - nie dalo sie ustalic,
    ile notatek sie nie udalo ani ile trwaly. Zapis NIGDY nie blokuje ani
    nie psuje odpowiedzi (wszystko w try/except)."""
    try:
        import time as _t
        from ..metrics import GenerationMetrics, persist_generation_metrics
        m = GenerationMetrics(requested_count=1)
        m.accepted_count = 1 if ok else 0
        m.total_time = _t.monotonic() - t0
        if not ok:
            m.record_rejection(reason or "notes_failed")
        persist_generation_metrics(m, feature="notes", temat=(temat or "")[:300],
                                   trudnosc="zdjecie" if from_image else "tekst", poziom=klasa)
    except Exception as _e:
        print(f"[NotesMetrics] pominieto zapis statystyk: {_e}")


def _generate_blocking(temat: str, klasa: str, api_key: str, num_sections: int = 3, wlasne_instrukcje: str = "", kontekst: str = "", jezyk: str = "", przedmiot: str = "", czy_obliczenia=None, images=None, verified_quiz_future=None, cached_data=None, store_mode=None, is_pro=False) -> str:
    gen = PremiumNotesGenerator(api_key)
    gen.is_pro = bool(is_pro)  # znacznik PRO w naglowkach PDF (Premium)
    filename = gen.generate_pdf(temat, klasa, num_sections, wlasne_instrukcje, kontekst, jezyk, przedmiot, czy_obliczenia, images, verified_quiz_future, cached_data)
    # Zwykly temat tekstowy: zapisz kompletna, sprawdzona tresc do pamieci (nastepny uczen dostanie ja od reki)
    if store_mode is not None and cached_data is None:
        from ..notes_cache import should_store, store
        if should_store(getattr(gen, "last_data", None), store_mode):
            store(temat, klasa, num_sections, gen.last_data)
    return filename

@router.post("/generate")
async def generate_notes_pdf(req: NotesRequest, user: User = Depends(require_feature_limit("notes"))):
    import time as _time
    _t0 = _time.monotonic()
    _img = bool(req.images or req.image)
    try:
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        all_images = []
        if req.images:
            all_images = req.images
        elif req.image:
            all_images = [req.image]

        temat = req.temat
        kontekst = ""
        jezyk = ""
        przedmiot = ""
        czy_obliczenia = None

        if all_images:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            content = []
            for img_b64 in all_images[:6]:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
            # ZMIENIONE (03.10.2026, user: notatka ze zdjec geografii miala wymyslone
            # wzory i przyklady): wczesniej ten krok oddawal generatorowi tylko
            # ~600 znakow streszczenia - reszte (i wzory) generator dopowiadal sam.
            # Teraz: wierne odczytanie TRESCI zdjec (do 2500 znakow) + przedmiot +
            # czy na zdjeciach sa obliczenia - to decyduje o trybie notatki.
            content.append({
                "type": "text",
                "text": (
                    f"Przeanalizuj te {len(all_images)} zdjecia (strony materialu szkolnego). "
                    "Odpowiedz TYLKO JSON w formacie: "
                    '{"temat": "Glowny temat PO POLSKU, max 60 znakow", '
                    '"przedmiot": "jedno z: matematyka, fizyka, chemia, biologia, geografia, historia, polski, angielski, informatyka, inny", '
                    '"jezyk_materialu": "polski / niemiecki / angielski / ...", '
                    '"czy_obliczenia": true lub false, '
                    '"dodatkowy_kontekst": "WIERNE streszczenie TRESCI widocznej na zdjeciach, max 2500 znakow"}. '
                    "ZASADY: 'czy_obliczenia' = true TYLKO jesli na zdjeciach WIDAC wzory, obliczenia lub zadania liczbowe do rozwiazania, "
                    "w przeciwnym razie false. W 'dodatkowy_kontekst' przepisz/streszczaj dokladnie to, co JEST na zdjeciach: naglowki, "
                    "definicje, kluczowe fakty, nazwy, daty, dane liczbowe; wzory TYLKO jesli sa widoczne (doslownie). "
                    "NIE dodawaj niczego, czego nie widac na zdjeciach. Dla jezyka obcego wpisz konkretne slownictwo, zwroty i "
                    "zagadnienia gramatyczne, ktore WIDAC."
                )
            })
            # gpt-4o (nie mini) TYLKO do czytania zdjec (03.10.2026, user zaakceptowal
            # ~+0.05 zl/notatke): mini blednie przepisywal nazwy ("Drawsko" -> "Drowo"),
            # a notatka ma sluzyc do nauki. Generowanie samej notatki zostaje na mini.
            vision_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                max_tokens=1500, timeout=40
            )
            txt = vision_resp.choices[0].message.content.strip()
            txt = txt.replace('```json','').replace('```','').strip()
            s = txt.find('{'); e = txt.rfind('}')
            vision_data = json.loads(txt[s:e+1])
            temat = vision_data.get('temat', req.temat)
            kontekst = str(vision_data.get('dodatkowy_kontekst') or '')[:2500]
            jezyk = str(vision_data.get('jezyk_materialu') or '')
            przedmiot = str(vision_data.get('przedmiot') or '').strip().lower()
            _co = vision_data.get('czy_obliczenia')
            czy_obliczenia = (_co is True) or (isinstance(_co, str) and _co.strip().lower() == 'true')
            print(f"[Vision] {len(all_images)} zdj -> temat: {temat} | przedmiot: {przedmiot} | obliczenia: {czy_obliczenia}")

        # Bez limitu czasowego - czekamy ile trzeba
        loop = asyncio.get_event_loop()
        wlasne = req.wlasne_instrukcje or ""
        # Quiz w notatkach obliczeniowych ze zweryfikowanego potoku quizu (03.10.2026) - liczony
        # ROWNOLEGLE w tej petli zdarzen, a watek generatora tylko czeka na wynik.
        from ..notes_pdf_generator import _notes_mode, build_verified_quiz, SIZE_CONFIG
        from .. import notes_cache
        # Pamiec popularnych tematow: zwykly temat tekstowy (bez zdjec/instrukcji/kontekstu)
        cache_ok = notes_cache.is_eligible(temat, all_images, wlasne, kontekst)
        cached_data = notes_cache.get_cached(temat, req.klasa, req.num_sections) if cache_ok else None
        store_mode = None
        quiz_future = None
        if cached_data is None:
            try:
                _mode = _notes_mode(temat, kontekst, przedmiot, czy_obliczenia, wlasne)
                store_mode = _mode if cache_ok else None
                if _mode != "opisowy":
                    _n = SIZE_CONFIG.get(req.num_sections, SIZE_CONFIG[3]).get('n_quiz', 4)
                    quiz_future = asyncio.run_coroutine_threadsafe(
                        build_verified_quiz(temat, req.klasa, przedmiot, _n), loop)
            except Exception as _e:
                print(f"[Notes] nie udalo sie uruchomic zweryfikowanego quizu: {_e}")
        filename = await loop.run_in_executor(
            _executor, _generate_blocking, temat, req.klasa, settings.OPENAI_API_KEY, req.num_sections, wlasne, kontekst, jezyk, przedmiot, czy_obliczenia, (all_images[:6] if all_images else None), quiz_future, cached_data, store_mode, bool(getattr(user, 'is_premium', False))
        )

        if filename and os.path.exists(filename):
            _log_notes_metrics(temat, req.klasa, _t0, True, from_image=_img)
            _hdrs = {"Content-Disposition": "attachment; filename=notatka.pdf"}
            if cache_ok:
                # klucz notatki - frontend uzywa go do przycisku "Zglos blad w notatce"
                _hdrs["X-Notes-Key"] = notes_cache.cache_key(temat, req.klasa, req.num_sections)
            return FileResponse(
                path=filename,
                media_type="application/pdf",
                filename=filename.encode('ascii', 'ignore').decode('ascii'),
                headers=_hdrs
            )
        _log_notes_metrics(temat, req.klasa, _t0, False, "no_pdf", from_image=_img)
        return {"success": False, "error": "Nie udalo sie wygenerowac PDF"}

    except Exception as e:
        import traceback
        print(f"NOTES ERROR: {traceback.format_exc()}")
        import traceback
        traceback.print_exc()
        _log_notes_metrics(req.temat, req.klasa, _t0, False, "exception", from_image=_img)
        return {"success": False, "error": str(e)}