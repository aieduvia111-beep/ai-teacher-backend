from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from ..config import settings
from ..notes_pdf_generator import PremiumNotesGenerator
from concurrent.futures import ThreadPoolExecutor
import asyncio, re, os

router = APIRouter(prefix="/api/v1/youtube", tags=["youtube"])
_executor = ThreadPoolExecutor(max_workers=2)

class YoutubeRequest(BaseModel):
    url: str
    klasa: str = "liceum"
    num_sections: int = 3

def extract_video_id(url: str) -> str:
    m = re.search(r'(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', url)
    if m: return m.group(1)
    raise ValueError("Nieprawidlowy link YouTube")

def _generate_blocking(temat: str, transkrypcja: str, klasa: str, api_key: str, num_sections: int) -> str:
    gen = PremiumNotesGenerator(api_key)
    instrukcje = f"Notatka ma byc oparta na tej transkrypcji z YouTube:\n\n{transkrypcja[:6000]}"
    return gen.generate_pdf(temat, klasa, num_sections, instrukcje)

@router.post("/notes")
async def youtube_notes(req: YoutubeRequest):
    try:
        video_id = extract_video_id(req.url)
        
        # Pobierz transkrypcje
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['pl'])
        except:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            except:
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        full_text = ' '.join([t['text'] for t in transcript])[:6000]
        temat = f"Notatka z YouTube: {req.url}"
        
        loop = asyncio.get_event_loop()
        pdf_path = await loop.run_in_executor(
            _executor, _generate_blocking,
            temat, full_text, req.klasa, settings.OPENAI_API_KEY, req.num_sections
        )
        
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=notatka-youtube.pdf"}
        )
        
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Blad: {str(e)}"}
