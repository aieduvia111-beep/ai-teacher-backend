import fitz
import base64
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class PDFRequest(BaseModel):
    pdf_base64: str
    max_chars: int = 15000

@router.post("/extract")
async def extract_pdf_text(req: PDFRequest):
    try:
        data = base64.b64decode(req.pdf_base64)
        doc = fitz.open(stream=data, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) > req.max_chars:
                break
        doc.close()
        text = text[:req.max_chars]
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF nie zawiera tekstu (może być skan)")
        return {"success": True, "text": text, "chars": len(text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
