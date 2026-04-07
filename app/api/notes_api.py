"""NOTES API - generowanie PDF z tematu LUB zdjecia (1 lub wiele)"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from ..config import settings
from ..notes_pdf_generator import PremiumNotesGenerator
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

def _generate_blocking(temat: str, klasa: str, api_key: str, num_sections: int = 3) -> str:
    gen = PremiumNotesGenerator(api_key)
    return gen.generate_pdf(temat, klasa, num_sections)

@router.post("/generate")
async def generate_notes_pdf(req: NotesRequest):
    try:
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        all_images = []
        if req.images:
            all_images = req.images
        elif req.image:
            all_images = [req.image]

        temat = req.temat

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
                    "Odpowiedz TYLKO JSON: "
                    '{"temat": "Glowny temat max 60 znakow", '
                    '"dodatkowy_kontekst": "Co widac, max 400 znakow"}'
                )
            })
            vision_resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                max_tokens=400, timeout=12
            )
            txt = vision_resp.choices[0].message.content.strip()
            txt = txt.replace('```json','').replace('```','').strip()
            s = txt.find('{'); e = txt.rfind('}')
            vision_data = json.loads(txt[s:e+1])
            temat = vision_data.get('temat', req.temat)
            print(f"[Vision] {len(all_images)} zdj -> temat: {temat}")

        # Bez limitu czasowego - czekamy ile trzeba
        loop = asyncio.get_event_loop()
        filename = await loop.run_in_executor(
            _executor, _generate_blocking, temat, req.klasa, settings.OPENAI_API_KEY, req.num_sections
        )

        if filename and os.path.exists(filename):
            return FileResponse(
                path=filename,
                media_type="application/pdf",
                filename=filename.encode('ascii', 'ignore').decode('ascii'),
                headers={"Content-Disposition": "attachment; filename=notatka.pdf"}
            )
        return {"success": False, "error": "Nie udalo sie wygenerowac PDF"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}