from ..error_logger import log_error
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

ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY","").strip()
USE_ELEVEN = False
eleven_client = None
if ELEVEN_KEY and len(ELEVEN_KEY) > 20:
    try:
        from elevenlabs.client import ElevenLabs as EL
        from elevenlabs import VoiceSettings
        eleven_client = EL(api_key=ELEVEN_KEY)
        USE_ELEVEN = True
        print(f"[TTS] ElevenLabs OK (voice: onwK4e9ZLuTAKqWW03F9)")
    except Exception as ee:
        print(f"[TTS] ElevenLabs error: {ee}")
else:
    print("[TTS] Brak klucza ElevenLabs - OpenAI TTS")
try:
    from groq import Groq
    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    GROQ_AVAILABLE = True
    print("[VOICE] Groq STT aktywny")
except Exception as e:
    groq_client = None
    GROQ_AVAILABLE = False
    print(f"[VOICE] Groq fallback OpenAI: {e}")

SYSTEM_PROMPT = """Jesteś Eduvia — charyzmatyczny, ciepły AI korepetytor. Mówisz naturalnie jak najlepszy nauczyciel prywatny. Jeśli znasz imię ucznia — zawsze zwracaj się do niego po imieniu. Jeśli znasz jego postępy — odwołuj się do nich naturalnie. ADAPTUJ poziom języka automatycznie. Gdy uczeń prosi "jak dla 6-latka" lub "prościej" — natychmiast mów bardzo prostym językiem przez całą resztę rozmowy.

STYL MÓWIENIA:
- Zawsze 2-3 zdania + angażujące pytanie na końcu
- Zaczynaj energetycznie: "To naprawdę ciekawe!", "Słuchaj, to fascynująca sprawa!", "No właśnie — tu jest haczyk!"
- Gdy uczeń dobrze odpowiada: "Dokładnie! Właśnie o to chodzi!", "Świetnie to uchwyciłeś!"
- Gdy błąd: "Prawie! Tu jest mały haczyk..."

ZAWSZE gdy wyjaśniasz — ta kolejność:
1. Energetyczny wstęp (1-2 zdania)
2. TABLICA z profesjonalną notatką
3. Pytanie które angażuje

TABLICA — profesjonalna notatka (min 4-5 punktów, PEŁNE zdania). Gdy są przykłady a) b) c) — WSZYSTKIE w jednym punkcie tablicy, nie osobno:
Wzory matematyczne ZAWSZE w $$...$$ np. $$x^2+5x+6=0$$ nie x^2+5x+6=0!
[TABLICA: punkt1 | punkt2 | punkt3 | punkt4 | punkt5]

PRZYKŁAD idealnej odpowiedzi na "co to są grzyby":
Grzyby to naprawdę fascynująca sprawa — to zupełnie osobne królestwo organizmów, ani rośliny ani zwierzęta! [TABLICA: Grzyby = odrębne królestwo organizmów eukariotycznych — nie rośliny, nie zwierzęta | Budowa: kapelusz + trzon + rozległa grzybnia pod ziemią | Odżywianie: saprofity — rozkładają martwą materię organiczną i pobierają składniki | Przykłady: borowik szlachetny, pieczarka, rydz, muchomor | Znaczenie: produkują antybiotyki np. penicylina i odgrywają kluczową rolę w ekosystemie] [EMOCJA: excited] Powiedz mi, co Cię najbardziej zaskakuje w grzybach?

EMOCJE (zawsze dodaj):
[EMOCJA: excited] — ciekawy temat, entuzjazm
[EMOCJA: happy] — uczeń dobrze odpowiada
[EMOCJA: thinking] — trudne pojęcie, wyjaśniasz
[EMOCJA: serious] — poprawiasz błąd
[EMOCJA: neutral] — normalnie

BŁĘDY: [CORRECTION: złe -> dobre]
Odpowiadaj w języku ucznia."""

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
        # Prosta analiza pewnosci ucznia na podstawie tekstu
        confidence = "neutral"
        low_conf = ["nie wiem","hmm","chyba","moze","nie jestem pewny","nie pamietam","zapomnialem"]
        high_conf = ["tak","dokladnie","wiem","rozumiem","jasne","oczywiscie","tak jest"]
        text_lower = text.lower()
        if any(w in text_lower for w in low_conf): confidence = "unsure"
        elif any(w in text_lower for w in high_conf): confidence = "confident"
        print(f"[STT] confidence={confidence}")
        return {"success": True, "text": text, "confidence": confidence}
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
            "podstawowka": "Mow jak do dziecka 12 lat. Przyklad: zamiast 'fotosynteza to konwersja energii' powiedz 'rosliny jedzą slonce'. Uzyj slow: super, fajne, wiesz co. Max 2 krotkie zdania.",
            "liceum": "Uzyj terminologii: chlorofil, ATP, CO2, glukoza, chloroplasty. Wyjasniaj mechanizmy. 2-3 zdania.",
            "matura": "matura - schematy maturalne",
            "studia": "studia - pelna formalizacja"
        }
        system = SYSTEM_PROMPT
        if level and level in level_map:
            system = system + "\n\nKRYTYCZNE: " + level_map[level] + " To jest NAJWAZNIEJSZA instrukcja - dostosuj CALY jezyk, terminologie i sposob wyjasniania do tego poziomu."
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
                return openai_client.chat.completions.create(model="gpt-4o",messages=messages,max_tokens=380,temperature=0.75)
            if GROQ_AVAILABLE:
                return groq_client.chat.completions.create(model="llama-3.3-70b-versatile",messages=messages,max_tokens=380,temperature=0.75)
            return openai_client.chat.completions.create(model="gpt-4o",messages=messages,max_tokens=380,temperature=0.75)
        response = await loop.run_in_executor(executor, call_llm)
        ai_text = response.choices[0].message.content.strip()
        voice_text = ai_text
        board_text = ai_text
        print(f"[GPT] '{ai_text[:80]}'")
        clean_text = re.sub(r'[CORRECTION:[^]]*]', '', ai_text).strip()
        clean_text = re.sub(r'[TABLICA:[^]]*]', '', clean_text).strip()
        def call_tts():
            if USE_ELEVEN and eleven_client:
                try:
                    is_excited=any(x in clean_text.lower() for x in ["super","swietnie","brawo","dokladnie","wlasnie","niesamowite"])
                    audio=eleven_client.text_to_speech.convert(
                        text=clean_text,
                        voice_id="Xb7hH8MSUJpSbSDYk0k2",
                        model_id="eleven_turbo_v2_5",
                        voice_settings=VoiceSettings(stability=0.62 if is_excited else 0.75,similarity_boost=0.9,style=0.65 if is_excited else 0.35,speed=1.05)
                    )
                    result=b"".join(audio) if hasattr(audio,'__iter__') else audio
                    print(f"[TTS] ElevenLabs OK ({len(clean_text)} znakow)")
                    return result
                except Exception as e:
                    print(f"[TTS] ElevenLabs failed: {e}")
            speech=openai_client.audio.speech.create(model="tts-1",voice="nova",input=clean_text,speed=1.1)
            return speech.content
        speech = await loop.run_in_executor(executor, call_tts)
        audio_bytes = speech
        print("[TTS] nova OK")
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

def call_tts(text: str, emotion: str = "neutral"):
    if not text or len(text.strip()) < 2:
        text = "Rozumiem."
    if USE_ELEVEN and eleven_client:
        try:
            settings_map = {
                "excited":  {"stability":0.55,"style":0.85,"speed":1.08},
                "happy":    {"stability":0.65,"style":0.70,"speed":1.05},
                "thinking": {"stability":0.80,"style":0.25,"speed":0.98},
                "serious":  {"stability":0.75,"style":0.15,"speed":1.02},
                "neutral":  {"stability":0.72,"style":0.40,"speed":1.05},
            }
            cfg = settings_map.get(emotion, settings_map["neutral"])
            audio = eleven_client.text_to_speech.convert(
                text=text,
                voice_id="Xb7hH8MSUJpSbSDYk0k2",
                model_id="eleven_turbo_v2_5",
                voice_settings=VoiceSettings(
                    stability=cfg["stability"],
                    similarity_boost=0.92,
                    style=cfg["style"],
                    speed=cfg["speed"]
                )
            )
            print(f"[TTS] ElevenLabs | emotion={emotion} | len={len(text)}")
            return b"".join(audio) if hasattr(audio,"__iter__") else audio
        except Exception as e:
            print(f"[TTS] ElevenLabs error: {e}")
    speed = 1.08 if emotion in ["excited","happy"] else 1.05
    speech = openai_client.audio.speech.create(model="tts-1",voice="nova",input=text[:500],speed=speed)
    return speech.content


@router.post("/respond/stream")
async def respond_stream(data: dict):
    text = data.get("text","").strip()
    history = data.get("history", [])
    level = data.get("level", "")
    subject = data.get("subject", "")
    topic = data.get("topic", "")
    profile_context = data.get("profile_context", "").strip()
    if not text:
        return {"error":"brak tekstu"}
    system = SYSTEM_PROMPT
    ctx = []
    if level: ctx.append(f"Poziom: {level}")
    if subject: ctx.append(f"Przedmiot: {subject}")
    if topic: ctx.append(f"Temat: {topic}")
    if ctx: system += "\n\n" + ". ".join(ctx) + "."
    if profile_context: system += "\n\n" + profile_context
    messages = [{"role":"system","content":system}]
    for msg in history[-12:]:
        if isinstance(msg,dict) and msg.get("role") in ("user","assistant"):
            messages.append(msg)
    image_b64 = data.get("image")
    if image_b64:
        messages.append({"role":"user","content":[
            {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{image_b64}","detail":"high"}},
            {"type":"text","text":text}
        ]})
    else:
        messages.append({"role":"user","content":text})
    loop = asyncio.get_event_loop()
    ex = concurrent.futures.ThreadPoolExecutor()
    def call_llm():
        try:
            if GROQ_AVAILABLE:
                return groq_client.chat.completions.create(model="llama-3.3-70b-versatile",messages=messages,max_tokens=380,temperature=0.76)
        except Exception as ge:
            print(f"[GROQ] fallback: {ge}")
        return openai_client.chat.completions.create(model="gpt-4o",messages=messages,max_tokens=380,temperature=0.76)
    import time as _t; _t1=_t.time(); resp = await loop.run_in_executor(ex,call_llm); print(f"[LLM] {_t.time()-_t1:.2f}s")
    ai_text = resp.choices[0].message.content.strip()
    tablica = None
    emocja = "neutral"
    tm = _re2.search(r'\[TABLICA: ([^\]]+)\]',ai_text)
    if tm: tablica = tm.group(1).strip()
    em = _re2.search(r'\[EMOCJA: ([^\]]+)\]',ai_text)
    if em: emocja = em.group(1).strip().lower()
    clean = _re2.sub(r'\[TABLICA:[^\]]*\]|\[EMOCJA:[^\]]*\]|\[CORRECTION:[^\]]*\]','',ai_text).strip()
    corrections = []
    for m in _re2.finditer(r'\[CORRECTION: ([^-]+) -> ([^\]]+)\]',ai_text):
        corrections.append({"wrong":m.group(1).strip(),"correct":m.group(2).strip()})
    sentences = [s.strip() for s in _re2.split(r'(?<=[.!?])\s+',clean) if s.strip()]
    if not sentences: sentences=[clean]
    import asyncio as _aio
    async def make_audio(idx2, s2):
        if len(s2)<3: return None
        try:
            def tts_t(sx=s2,em=emocja):
                spd=1.08 if em in ["excited","happy"] else 1.05
                return openai_client.audio.speech.create(model="tts-1",voice="nova",input=sx[:500],speed=spd).content
            aud = await loop.run_in_executor(ex,tts_t)
            print(f"[TTS] OK {idx2}: {s2[:25]}")
            return base64.b64encode(aud).decode()
        except Exception as e:
            print(f"[TTS] ERR: {e}")
            return None
    audios = await _aio.gather(*[make_audio(i,s) for i,s in enumerate(sentences)])
    async def generate():
        yield _js.dumps({"type":"meta","text":ai_text,"tablica":tablica,"emocja":emocja,"corrections":corrections})+"\n"
        for i,a in enumerate(audios):
            if a: yield _js.dumps({"type":"audio","index":i,"audio":a})+"\n"
    return _SR(generate(),media_type="application/x-ndjson")

