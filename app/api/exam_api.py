from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from ..config import settings
from ..exam_pdf_generator import ExamGenerator
from ..openai_vision import analyze_image_with_gpt4_vision
import os, json
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/v1/exam", tags=["exam"])
_executor = ThreadPoolExecutor(max_workers=4)

class ExamRequest(BaseModel):
    temat: Optional[str] = None
    klasa: str = "liceum"
    przedmiot: str = "Matematyka"
    trudnosc: str = "srednia"
    liczba_pytan: int = 12
    wariant: Optional[str] = "A"
    image: Optional[str] = None
    images: Optional[List[str]] = None

def _generate_blocking(pelny_temat, klasa, trudnosc, liczba_pytan, api_key, wariant):
    gen = ExamGenerator(api_key)
    return gen.generate_exam(
        temat=pelny_temat, klasa=klasa,
        trudnosc=trudnosc, liczba_pytan=liczba_pytan,
        wariant=wariant
    )

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
async def generate_exam(req: ExamRequest):
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
        filename = await loop.run_in_executor(
            _executor, _generate_blocking,
            pelny_temat, req.klasa, req.trudnosc, req.liczba_pytan, settings.OPENAI_API_KEY, req.wariant
        )

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
