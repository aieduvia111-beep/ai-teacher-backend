from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..openai_vision import (
    analyze_image_with_gpt4_vision,
    vision_analyze_homework,
    vision_analyze_diagram,
    solve_homework_vision
)

router = APIRouter(prefix="/api/v1/vision", tags=["Vision"])

class VisionRequest(BaseModel):
    image: str
    subject: Optional[str] = "matematyka"
    mode: Optional[str] = "solve"
    prompt: Optional[str] = None

@router.post("/analyze")
async def analyze(request: VisionRequest):
    try:
        result = await analyze_image_with_gpt4_vision(request.image, request.prompt)
        return {"success": True, "analysis": result}
    except Exception as e:
        return {"success": False, "analysis": "", "error": str(e)}

@router.post("/analyze-math")
async def analyze_math(request: VisionRequest):
    try:
        result = await vision_analyze_homework(request.image)
        return {"success": True, "analysis": result}
    except Exception as e:
        return {"success": False, "analysis": "", "error": str(e)}

@router.post("/analyze-diagram")
async def analyze_diagram(request: VisionRequest):
    try:
        result = await vision_analyze_diagram(request.image)
        return {"success": True, "analysis": result}
    except Exception as e:
        return {"success": False, "analysis": "", "error": str(e)}

@router.post("/solve")
async def solve(request: VisionRequest):
    try:
        result = await solve_homework_vision(
            image_base64=request.image,
            subject=request.subject,
            mode=request.mode,
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e), "problems": []}
