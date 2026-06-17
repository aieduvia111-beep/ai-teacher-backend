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

from groq import Groq
import os

@router.post("/quiz")
async def quiz_from_pdf(req: PDFRequest):
    """Szybki quiz z PDF przez Groq LLaMA"""
    try:
        # 1. Wyciagnij tekst
        data = base64.b64decode(req.pdf_base64)
        doc = fitz.open(stream=data, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) > 8000:
                break
        doc.close()
        text = text[:8000]
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF nie zawiera tekstu")
        
        # 2. Generuj quiz przez Groq (szybki)
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY",""))
        prompt = f"""Wygeneruj 5 pytan quizowych na podstawie tego tekstu. 
Zwroc TYLKO JSON w tym formacie:
{{"questions":[{{"id":1,"question":"...","options":["A","B","C","D"],"correct":0,"explanation":"..."}}]}}

Tekst:
{text[:6000]}"""
        
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            max_tokens=2000,
            temperature=0.3
        )
        
        import json, re as _re
        raw = resp.choices[0].message.content
        match = _re.search(r'\{.*\}', raw, _re.DOTALL)
        if not match:
            raise HTTPException(status_code=500, detail="Błąd parsowania odpowiedzi AI")
        
        quiz_data = json.loads(match.group())
        # Napraw LaTeX w pytaniach
        from app.openai_exam import fix_latex_in_quiz
        questions = fix_latex_in_quiz(quiz_data["questions"])
        return {"success": True, "quiz": {"title": "Quiz z PDF", "questions": questions}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quiz-text")
async def quiz_from_text(req: PDFRequest):
    """Quiz z tekstu PDF przez GPT-4o"""
    try:
        data = base64.b64decode(req.pdf_base64)
        doc = fitz.open(stream=data, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) > 8000: break
        doc.close()
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF nie zawiera tekstu")
        from app.openai_exam import generate_quiz_from_text
        result = await generate_quiz_from_text(text[:7000])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
