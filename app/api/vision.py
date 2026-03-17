from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import base64
from ..services.openai_vision import analyze_image, analyze_math_problem, check_homework


router = APIRouter(prefix="/vision", tags=["Vision"])


@router.post("/analyze")
async def analyze_uploaded_image(
    file: UploadFile = File(...),
    prompt: str = None
):
    """
    📸 Upload zdjęcia i analiza przez GPT-4 Vision
    
    Przykład użycia:
    - Upload zdjęcia zadania
    - AI analizuje i wyjaśnia
    """
    
    # Sprawdź typ pliku
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="Plik musi być obrazem (JPG, PNG, etc.)"
        )
    
    try:
        # Przeczytaj plik
        image_data = await file.read()
        
        # Konwertuj na base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Analizuj przez OpenAI Vision
        result = analyze_image(image_base64, prompt)
        
        if result["success"]:
            return JSONResponse({
                "success": True,
                "filename": file.filename,
                "analysis": result["analysis"],
                "tokens_used": result["tokens_used"]
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Błąd AI: {result['error']}"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd przetwarzania: {str(e)}"
        )


@router.post("/analyze-math")
async def analyze_math(file: UploadFile = File(...)):
    """📐 Specjalnie dla zadań matematycznych"""
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Wymagany obraz")
    
    image_data = await file.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    result = analyze_math_problem(image_base64)
    
    if result["success"]:
        return {"success": True, "analysis": result["analysis"]}
    else:
        raise HTTPException(status_code=500, detail=result["error"])


@router.post("/check-homework")
async def check_hw(file: UploadFile = File(...)):
    """✅ Sprawdź pracę domową - znajdź błędy"""
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Wymagany obraz")
    
    image_data = await file.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    result = check_homework(image_base64)
    
    if result["success"]:
        return {"success": True, "analysis": result["analysis"]}
    else:
        raise HTTPException(status_code=500, detail=result["error"])