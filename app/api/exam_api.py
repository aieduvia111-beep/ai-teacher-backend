from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from ..config import settings
from ..exam_pdf_generator import ExamGenerator
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/v1/exam", tags=["exam"])
_executor = ThreadPoolExecutor(max_workers=4)

class ExamRequest(BaseModel):
    temat: str
    klasa: str = "liceum"
    przedmiot: str = "Matematyka"
    trudnosc: str = "srednia"
    liczba_pytan: int = 12
    wariant: Optional[str] = "A"

def _generate_blocking(pelny_temat, klasa, trudnosc, liczba_pytan, api_key):
    gen = ExamGenerator(api_key)
    return gen.generate_exam(
        temat=pelny_temat, klasa=klasa,
        trudnosc=trudnosc, liczba_pytan=liczba_pytan
    )

@router.post("/generate")
async def generate_exam(req: ExamRequest):
    try:
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        pelny_temat = f"{req.przedmiot}: {req.temat}"

        # Bez limitu czasowego - czekamy ile trzeba
        loop = asyncio.get_event_loop()
        filename = await loop.run_in_executor(
            _executor, _generate_blocking,
            pelny_temat, req.klasa, req.trudnosc, req.liczba_pytan, settings.OPENAI_API_KEY
        )

        if filename and os.path.exists(filename):
            return FileResponse(
                path=filename,
                media_type="application/pdf",
                filename=filename.encode('ascii', 'ignore').decode('ascii'),
                headers={"Content-Disposition": "attachment; filename=sprawdzian.pdf"}
            )
        return {"success": False, "error": "Nie udalo sie wygenerowac PDF"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}