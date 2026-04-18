"""VOICE CONVERSATION API"""
from fastapi import APIRouter
from openai import OpenAI
import base64
import re
import tempfile
import os
from ..config import settings

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Jeden tryb — ogólny nauczyciel który sam wykrywa język
SYSTEM_PROMPT = """You are Eduvia AI — a smart friendly tutor for students.

LANGUAGE RULE — CRITICAL, ALWAYS FOLLOW:
- Read the student's message and detect what language it is written in
- ALWAYS reply in that EXACT same language — no exceptions
- English message → English reply
- Polish message → Polish reply
- German message → German reply
- If the student is PRACTICING English (e.g. says "where are you from?") → reply in English to help them practice. NEVER translate their English practice to Polish.

TEACHING STYLE:
- You can teach ANY subject: math, physics, chemistry, biology, history, languages, coding
- Keep answers SHORT: 2-4 sentences max (this is voice, not text)
- Be warm and natural like a real teacher, not robotic
- Use simple words and real-life examples
- End with a follow-up question to keep the conversation going
- If student shows something on camera → describe what you see and help solve it step by step

LANGUAGE CORRECTION:
- When student makes a grammar mistake, correct them naturally in your reply
- Say the correct form in your sentence, e.g. "Nice! So you WENT to school..."  
- Additionally, at the END of your response add a tag: [CORRECTION: wrong → correct]
- Example: student says "I goed to school" → reply ends with: [CORRECTION: I goed → I went]
- Only add the tag when there is a clear grammar/vocabulary mistake
- Maximum ONE correction tag per response
"""


@router.post("/transcribe")
async def transcribe_audio(data: dict):
    """Zamienia głos na tekst przez Whisper — auto wykrycie języka"""
    try:
        audio_b64 = data.get("audio", "")

        if not audio_b64:
            return {"success": False, "text": "", "error": "Brak audio"}

        audio_bytes = base64.b64decode(audio_b64)
        print(f"[TRANSCRIBE] Rozmiar audio: {len(audio_bytes)} bajtów")

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        with open(tmp_path, "rb") as f:
            # BEZ podawania języka = Whisper sam wykrywa
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
                # language=... — celowo pominięte, Whisper sam wykryje
            )

        os.unlink(tmp_path)

        text = transcription.text.strip()
        print(f"[TRANSCRIBE] Wykryto: '{text}'")

        return {"success": True, "text": text}

    except Exception as e:
        print(f"[TRANSCRIBE ERROR] {e}")
        return {"success": False, "text": "", "error": str(e)}


@router.post("/respond")
async def get_ai_response(data: dict):
    """AI odpowiada — wykrywa język automatycznie i odpowiada w tym samym"""
    try:
        text = data.get("text", "")
        history = data.get("history", [])

        if not text:
            return {"success": False, "text": "", "error": "Brak tekstu"}

        print(f"[RESPOND] Tekst ucznia: '{text}'")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        for msg in history[-8:]:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Jeśli frontend przysłał zdjęcie z kamerki — GPT-4o je widzi
        image_b64 = data.get("image")
        if image_b64:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}",
                        "detail": "high"
                    }},
                    {"type": "text", "text": text}
                ]
            })
            print("[RESPOND] Wysłano z obrazem z kamerki")
        else:
            messages.append({"role": "user", "content": text})

        # GPT-4o i TTS uruchamiamy równolegle żeby było szybciej
        import asyncio, concurrent.futures
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor()

        # Najpierw GPT (potrzebujemy tekstu żeby zrobić TTS)
        def call_gpt():
            return client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=160,
                temperature=0.7
            )

        response = await loop.run_in_executor(executor, call_gpt)
        ai_text = response.choices[0].message.content.strip()
        print(f"[RESPOND] GPT: '{ai_text[:80]}'")

        # TTS od razu po tekście
        def call_tts():
            return client.audio.speech.create(
                model="tts-1",
                voice="fable",    # fable = najcieplejszy głos, naturalny, nie brzmi jak AI
                input=ai_text,
                speed=1.1
            )

        speech = await loop.run_in_executor(executor, call_tts)
        audio_b64 = base64.b64encode(speech.content).decode("utf-8")
        print(f"[RESPOND] TTS gotowy, {len(speech.content)} bajtów")

        # Korekty językowe (format [CORRECTION: wrong → correct])
        corrections = []
        if "[CORRECTION:" in ai_text:
            matches = re.findall(r'\[CORRECTION: (.+?) → (.+?)\]', ai_text)
            for wrong, correct in matches:
                corrections.append({"wrong": wrong, "correct": correct})
            ai_text = re.sub(r'\[CORRECTION: .+? → .+?\]', '', ai_text).strip()

        return {
            "success": True,
            "text": ai_text,
            "audio": audio_b64,
            "corrections": corrections
        }

    except Exception as e:
        print(f"[RESPOND ERROR] {e}")
        return {"success": False, "text": "", "audio": None, "error": str(e)}


@router.get("/health")
async def voice_health():
    return {"status": "ok", "service": "voice"}