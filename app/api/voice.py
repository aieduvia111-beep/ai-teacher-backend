"""VOICE CONVERSATION API - Groq STT + GPT-4o + ElevenLabs TTS"""
from fastapi import APIRouter
from openai import OpenAI
import base64
import re
import tempfile
import os
import asyncio
import concurrent.futures
import httpx
from ..config import settings

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

try:
    from groq import Groq
    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    GROQ_AVAILABLE = True
    print("[VOICE] Groq STT aktywny")
except Exception as e:
    groq_client = None
    GROQ_AVAILABLE = False
    print(f"[VOICE] Groq fallback OpenAI: {e}")

SYSTEM_PROMPT = """Jestes Eduvia AI - elitarny korepetytor. Mow krotko i naturalnie.

ZASADA 1 - GLOS: 3-5 zdan. Naturalnie jak czlowiek. Nie jak encyklopedia.
Tłumacz krok po kroku, daj przyklad z zycia, sprawdz czy rozumie.
Gdy uczen nie rozumie: uproscij, zmien metode, uzyj analogii.

ZASADA 2 - JEZYK: Odpowiadaj w jezyku ucznia. Polski->polski.

ZASADA 3 - TABLICA:
Dodaj [TABLICA: ...] po KAZDYM wyjasnieniu, definicji, wzorze, zadaniu.
NIE dodawaj tylko przy: "czesc", "jak sie masz", "dziekuje", "do widzenia".
W kazdej innej sytuacji MUSISZ dodac tablice.

Format: [TABLICA: punkt1 | punkt2 | punkt3 | punkt4 | punkt5]

TABLICA musi byc jak profesjonalne notatki z korepetycji:
- Pelne zdania z sensem
- Wzory matematyczne: $$wzor$$
- Przyklady liczbowe
- Kluczowe definicje
- Czeste bledy

PRZYKLAD dobrej tablicy dla fotosyntezy gdy uczen nie rozumie:
[TABLICA: Fotosynteza = proces zamiany swiatla w energie | Potrzebuje: swiatlo sloneczne + woda + CO2 | Produkty: tlen ($$O_2$$) + glukoza (cukier) | Zachodzi w: chloroplastach (zielone czesci lisci) | Przyklad: jak ogrod sobie ros­nie bez podlewania - bierze wode z powietrza]

PRZYKLAD tablicy dla Pitagorasa:
[TABLICA: Twierdzenie Pitagorasa: $$a^2 + b^2 = c^2$$ | a i b = przyprostokatne (krotsze boki) | c = przeciwprostokatna (najdluzszy bok, naprzeciwko kata prostego) | Przyklad: $$3^2 + 4^2 = 9 + 16 = 25 = 5^2$$ wiec c=5 | Zastosowanie: obliczanie odleglosci, wysokosci budynkow]

PRZYKLAD tablicy dla zadania:
[TABLICA: Zadanie: oblicz c gdy a=3, b=4 | Krok 1: $$c^2 = a^2 + b^2 = 9 + 16 = 25$$ | Krok 2: $$c = \sqrt{25} = 5$$ | Odpowiedz: c = 5 | Sprawdzenie: $$3^2+4^2=5^2$$ ✓]

BLEDY: [CORRECTION: zle -> dobrze]
Wzory TYLKO: $$wzor$$ - nigdy nie uzywaj \( \) lub \[ \]"""

@router.post("/transcribe")
async def transcribe_audio(data: dict):
    try:
        audio_b64 = data.get("audio", "")
        if not audio_b64:
            return {"success": False, "text": "", "error": "Brak audio"}
        audio_bytes = base64.b64decode(audio_b64)
        print(f"[STT] {len(audio_bytes)} bajtow")
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        try:
            if GROQ_AVAILABLE:
                with open(tmp_path, "rb") as f:
                    result = groq_client.audio.transcriptions.create(
                        model="whisper-large-v3-turbo",
                        file=f,
                        response_format="text"
                    )
                text = result.strip() if isinstance(result, str) else result.text.strip()
                print(f"[STT] Groq: '{text}'")
            else:
                with open(tmp_path, "rb") as f:
                    result = openai_client.audio.transcriptions.create(model="whisper-1", file=f)
                text = result.text.strip()
                print(f"[STT] OpenAI: '{text}'")
        finally:
            os.unlink(tmp_path)
        return {"success": True, "text": text}
    except Exception as e:
        print(f"[STT ERROR] {e}")
        return {"success": False, "text": "", "error": str(e)}


@router.post("/respond")
async def get_ai_response(data: dict):
    try:
        text = data.get("text", "")
        history = data.get("history", [])
        level = data.get("level", "")
        subject = data.get("subject", "")
        if not text:
            return {"success": False, "text": "", "error": "Brak tekstu"}
        level_map = {
            "podstawowka": "szkola podstawowa - bardzo proste slowa",
            "liceum": "liceum - pelna terminologia",
            "matura": "matura - schematy maturalne",
            "studia": "studia - pelna formalizacja"
        }
        system = SYSTEM_PROMPT
        if level and level in level_map:
            system += f"\nPOZIOM: {level_map[level]}"
        if subject:
            system += f"\nPRZEDMIOT: {subject}"
        topic = data.get("topic", "")
        if topic:
            system += f"\nTEMAT SESJI: {topic}"
        messages = [{"role": "system", "content": system}]
        for msg in history[-8:]:
            if isinstance(msg, dict) and msg.get("role") in ("user","assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})
        image_b64 = data.get("image")
        if image_b64:
            messages.append({"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"}},
                {"type": "text", "text": text}
            ]})
        else:
            messages.append({"role": "user", "content": text})
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor()
        # GPT-4o dla zdjec, Groq LLaMA dla glosu
        def call_llm():
            if image_b64:
                return openai_client.chat.completions.create(model="gpt-4o",messages=messages,max_tokens=300,temperature=0.7)
            if GROQ_AVAILABLE:
                return groq_client.chat.completions.create(model="llama-3.3-70b-versatile",messages=messages,max_tokens=250,temperature=0.7)
            return openai_client.chat.completions.create(model="gpt-4o",messages=messages,max_tokens=250,temperature=0.7)
        response = await loop.run_in_executor(executor, call_llm)
        ai_text = response.choices[0].message.content.strip()
        voice_text = ai_text
        board_text = ai_text
        print(f"[GPT] '{ai_text[:80]}'")
        clean_text = re.sub(r'[CORRECTION:[^]]*]', '', ai_text).strip()
        clean_text = re.sub(r'[TABLICA:[^]]*]', '', clean_text).strip()
        def call_tts():
            speech = openai_client.audio.speech.create(model="tts-1", voice="onyx", input=clean_text, speed=1.1)
            return speech.content
        speech = await loop.run_in_executor(executor, call_tts)
        audio_bytes = speech
        print("[TTS] onyx OK")
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        corrections = []
        if "[CORRECTION:" in ai_text:
            matches = re.findall(r'\[CORRECTION: (.+?) -> (.+?)\]', ai_text)
            for wrong, correct in matches:
                corrections.append({"wrong": wrong, "correct": correct})
            ai_text = re.sub(r'\[CORRECTION: .+? -> .+?\]', '', ai_text).strip()
        return {"success": True, "text": ai_text, "audio": audio_b64, "corrections": corrections}
    except Exception as e:
        print(f"[RESPOND ERROR] {e}")
        return {"success": False, "text": "", "audio": None, "error": str(e)}

@router.get("/health")
async def voice_health():
    return {"status": "ok", "stt": "groq" if GROQ_AVAILABLE else "openai", "tts": "elevenlabs", "llm": "gpt-4o"}

from fastapi.responses import StreamingResponse as _SR
import json as _js, re as _re2

@router.post("/respond/stream")
async def respond_stream(data: dict):
    text = data.get("text","")
    history = data.get("history",[])
    if not text:
        return {"error":"brak tekstu"}
    
    messages=[{"role":"system","content":SYSTEM_PROMPT}]
    for msg in history[-6:]:
        if isinstance(msg,dict) and msg.get("role") in ("user","assistant"):
            messages.append({"role":msg["role"],"content":msg["content"]})
    messages.append({"role":"user","content":text})
    
    loop=asyncio.get_event_loop()
    ex=concurrent.futures.ThreadPoolExecutor()
    
    def call_llm():
        try:
            if GROQ_AVAILABLE:
                return groq_client.chat.completions.create(model="llama-3.3-70b-versatile",messages=messages,max_tokens=250,temperature=0.7)
        except Exception as ge:
            print(f"[GROQ] fallback: {ge}")
        return openai_client.chat.completions.create(model="gpt-4o",messages=messages,max_tokens=250,temperature=0.7)
    resp = await loop.run_in_executor(ex, call_llm)
    ai_text = resp.choices[0].message.content.strip()
    
    tablica = None
    tm = _re2.search(r'\[TABLICA: ([^\]]+)\]', ai_text)
    if tm: tablica = tm.group(1)
    clean = _re2.sub(r'\[TABLICA:[^\]]*\]','',ai_text)
    clean = _re2.sub(r'\[CORRECTION:[^\]]*\]','',clean).strip()
    
    corrections=[]
    for m in _re2.finditer(r'\[CORRECTION: ([^-]+) -> ([^\]]+)\]',ai_text):
        corrections.append({"wrong":m.group(1).strip(),"correct":m.group(2).strip()})
    
    sentences=[s.strip() for s in _re2.split(r'(?<=[.!?])\s+',clean) if s.strip()]
    if not sentences: sentences=[clean]
    
    async def generate():
        yield _js.dumps({"type":"meta","text":ai_text,"tablica":tablica,"corrections":corrections})+"\n"
        # Hmm/aha przed odpowiedzia - naturalny dzwiek myslenia
        import random as _rand
        sounds = ["Hmm...", "No dobra.", "Aha.", "Rozumiem.", "Ok."]
        sound = _rand.choice(sounds)
        try:
            def tts_hmm():
                return openai_client.audio.speech.create(model="tts-1",voice="onyx",input=sound,speed=1.0).content
            hmm_audio = await loop.run_in_executor(ex, tts_hmm)
            yield _js.dumps({"type":"audio","index":-1,"audio":base64.b64encode(hmm_audio).decode()})+"\n"
        except: pass
        for i,s in enumerate(sentences):
            if len(s)<3: continue
            try:
                def tts(sx=s):
                    return openai_client.audio.speech.create(model="tts-1",voice="onyx",input=sx,speed=1.1).content
                audio=await loop.run_in_executor(ex,tts)
                yield _js.dumps({"type":"audio","index":i,"audio":base64.b64encode(audio).decode()})+"\n"
            except Exception as e:
                print(f"[TTS stream] {e}")
    
    return _SR(generate(), media_type="application/x-ndjson")
