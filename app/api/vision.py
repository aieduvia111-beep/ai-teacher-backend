from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
import base64, os, json
import openai

router = APIRouter(prefix="/vision", tags=["Vision"])

class SolveRequest(BaseModel):
    image: str
    subject: str = "matematyka"
    mode: str = "solve"
    show_steps: bool = True
    generate_similar: bool = True
    show_explanation: bool = True

@router.post("/solve")
async def solve_problem(req: SolveRequest):
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = f"Jestes nauczycielem. Przedmiot: {req.subject}. Rozwiaz WSZYSTKIE zadania ze zdjecia krok po kroku po polsku. Odpowiedz TYLKO w JSON: {{\"success\":true,\"problems\":[{{\"question\":\"tresc\",\"solution\":{{\"steps\":[\"krok1\",\"krok2\"],\"final_answer\":\"odpowiedz\",\"explanation\":\"wyjasnienie\"}}}}]}}"
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role":"user","content":[{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{req.image}","detail":"high"}},{"type":"text","text":prompt}]}],
            max_tokens=2000,
            response_format={"type":"json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"success":False,"error":str(e),"problems":[]}

@router.post("/analyze")
async def analyze(file: UploadFile = File(...), prompt: str = None):
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Wymagany obraz")
    try:
        image_base64 = base64.b64encode(await file.read()).decode('utf-8')
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role":"user","content":[{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{image_base64}"}},{"type":"text","text":prompt or "Opisz zdjecie po polsku."}]}],
            max_tokens=1000
        )
        return {"success":True,"analysis":response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
