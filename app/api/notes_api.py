from ..error_logger import log_error
"""NOTES API - generowanie PDF z tematu LUB zdjecia (1 lub wiele)"""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from ..config import settings
from ..notes_pdf_generator import PremiumNotesGenerator
from ..firebase_auth import require_feature_limit
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


def _generate_blocking(temat: str, klasa: str, api_key: str, num_sections: int = 3, wlasne_instrukcje: str = "", kontekst: str = "", jezyk: str = "") -> str:
    gen = PremiumNotesGenerator(api_key)
    return gen.generate_pdf(temat, klasa, num_sections, wlasne_instrukcje, kontekst, jezyk)

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

        if all_images:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            content = []
            for img_b64 in all_images[:6]:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
            content.append({
                "type": "text",
                "text": (
                    f"Przeanalizuj te {len(all_images)} zdjecia. "
                    "Okresl jezyk, w ktorym jest napisany material na zdjeciach (np. polski, niemiecki, angielski). "
                    "Temat podaj PO POLSKU, ale jesli to cwiczenie/tekst z jezyka obcego, wpisz w kontekscie konkretne "
                    "slownictwo, zwroty i zagadnienia gramatyczne, ktore WIDAC na zdjeciu. "
                    "Odpowiedz TYLKO JSON: "
                    '{"temat": "Glowny temat max 60 znakow", '
                    '"jezyk_materialu": "polski / niemiecki / angielski / ...", '
                    '"dodatkowy_kontekst": "Co widac: zagadnienia, slownictwo, przyklady ze zdjecia, max 600 znakow"}'
                )
            })
            vision_resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                max_tokens=600, timeout=15
            )
            txt = vision_resp.choices[0].message.content.strip()
            txt = txt.replace('```json','').replace('```','').strip()
            s = txt.find('{'); e = txt.rfind('}')
            vision_data = json.loads(txt[s:e+1])
            temat = vision_data.get('temat', req.temat)
            kontekst = str(vision_data.get('dodatkowy_kontekst') or '')[:700]
            jezyk = str(vision_data.get('jezyk_materialu') or '')
            print(f"[Vision] {len(all_images)} zdj -> temat: {temat}")

        # Bez limitu czasowego - czekamy ile trzeba
        loop = asyncio.get_event_loop()
        wlasne = req.wlasne_instrukcje or ""
        filename = await loop.run_in_executor(
            _executor, _generate_blocking, temat, req.klasa, settings.OPENAI_API_KEY, req.num_sections, wlasne, kontekst, jezyk
        )

        if filename and os.path.exists(filename):
            _log_notes_metrics(temat, req.klasa, _t0, True, from_image=_img)
            return FileResponse(
                path=filename,
                media_type="application/pdf",
                filename=filename.encode('ascii', 'ignore').decode('ascii'),
                headers={"Content-Disposition": "attachment; filename=notatka.pdf"}
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