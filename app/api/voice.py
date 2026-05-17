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

SYSTEM_PROMPT = """Jestes Eduvia AI - madry i ciepły nauczyciel głosowy.

JEZYK: Zawsze odpowiadaj w jezyku ucznia. Polski -> polski, angielski -> angielski.

MATEMATYKA PO POLSKU:
- Mow po polsku: "a do kwadratu" nie "a squared"
- "pierwiastek z" nie "square root"
- "razy" nie "times", "przez" nie "divided by"
- "rowna sie" nie "equals"
- Wzory czytaj naturalnie: "a kwadrat plus b kwadrat rowna sie c kwadrat"

GŁOS: Krotko - max 3 zdania. Naturalnie jak prawdziwy nauczyciel. Zakoncz pytaniem.

TABLICA - pisz TYLKO gdy naprawde pomaga:
Kiedy pisac na tablicy:
- Uczen nie rozumie czegos -> napisz prostsze wytłumaczenie krok po kroku
- Uczen popełnił bład -> napisz co bylo zle i jak jest dobrze
- Wzor lub definicja -> napisz wzor w LaTeX i przykład
- Kluczowe pojecia -> wypisz je z krótkim opisem
- Uczen pyta "jak to działa" -> napisz kroki

Format tablicy: [TABLICA: punkt1 | punkt2 | punkt3]
Zasady:
- Pisz jak nauczyciel na tablicy - konkretnie i sensownie
- Wzory w LaTeX: $$a^2+b^2=c^2$$
- Definicje: "Fotosynteza: zamiana swiatla w energie"
- Kroki numerowane: "1. Zbierz dane | 2. Podstaw wzor | 3. Oblicz"
- Przyklady: "Przyklad: a=3, b=4, wiec c=5"
- Max 5 punktow, kazdy max 12 slow
- ZAWSZE pisz po polsku

BLEDY UCZNIA:
- Gdy uczen sie myli -> popraw naturalnie w odpowiedzi
- Dodaj: [CORRECTION: blad -> poprawnie]

PAMIETAJ: Jestes jak najlepszy nauczyciel - cierpliwy, mądry, tłumaczysz prosto.

ZACHOWANIE JAK CZLOWIEK:
- Uzyj naturalnych zwrotow: "Swietnie!", "Prawie!", "Dobry kierunek!", "Hmm, nie do konca..."
- Gdy uczen odpowiada dobrze -> pochwal konkretnie: "Dokladnie tak! Widzę że rozumiesz"
- Gdy uczen sie myli -> nie mow "zle" - mow "Prawie! Chodzi o to ze..."
- Po wytlumaczeniu ZAWSZE zapytaj: "Co z tego zapamiętales?" lub "Powiedz mi własnymi słowami co to znaczy"
- Bądź ciepły i motywujący - uczniowie lepiej sie uczą gdy czują wsparcie

LUDZKIE DZWIĘKI w odpowiedzi głosowej:
- Czasem zacznij od: "Hmm...", "No dobra...", "Chwileczke...", "O, dobre pytanie!"
- Nigdy nie zaczynaj od "Jako AI..." lub "Oczywiscie..."
- Mow naturalnie jak człowiek, nie jak robot

ZADANIA DLA UCZNIA:
- Gdy temat wymaga cwiczenia (matematyka, jezyki, fizyka) -> daj krotkie zadanie
- Gdy to teoria lub ciekawostka -> nie dawaj zadania, tylko zapytaj czy rozumie
- Np. "Spróbuj sam obliczyc..." lub "Jak myslisz, dlaczego..."
- Gdy uczen wyśle zdjecie -> sprawdź czy rozwiązanie jest poprawne
- Jesli bledne -> powiedz co jest nie tak i daj wskazówkę
- Jesli poprawne -> pochwal i daj trudniejsze zadanie
- Przykłady z życia: zakupy, sport, gotowanie, gry - cokolwiek co jest bliskie uczniowi"""

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
        # ROWNOLEGLE: LLaMA dla glosu + GPT-4o dla tablicy
        def call_voice_llm():
            # LLaMA - szybki, krotka odpowiedz glosowa
            voice_messages = messages[:-1] + [{"role":"user","content": text + "\nOdpowiedz krotko - max 2-3 zdania. NIE dodawaj [TABLICA:]."}]
            if GROQ_AVAILABLE:
                return groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=voice_messages,
                    max_tokens=120,
                    temperature=0.7
                )
            return openai_client.chat.completions.create(
                model="gpt-4o-mini", messages=voice_messages, max_tokens=120, temperature=0.7
            )

        def call_board_llm():
            # GPT-4o - lepsza jakosc dla tablicy
            board_messages = messages[:-1] + [{"role":"user","content": text + "\nOdpowiedz TYLKO tagiem [TABLICA:] jesli wytlumaczyc cos waznego. Format: [TABLICA: punkt1 | punkt2 | Wzor: $$wzor$$]. Jesli nie trzeba tablicy - odpowiedz pustym stringiem."}]
            return openai_client.chat.completions.create(
                model="gpt-4o", messages=board_messages, max_tokens=400, temperature=0.3
            )

        # Uruchom rownolegle
        voice_resp, board_resp = await asyncio.gather(
            loop.run_in_executor(executor, call_voice_llm),
            loop.run_in_executor(executor, call_board_llm)
        )
        voice_text = voice_resp.choices[0].message.content.strip()
        board_text = board_resp.choices[0].message.content.strip()
        # Połącz - glos z LLaMA + tablica z GPT-4o
        ai_text = voice_text
        if '[TABLICA:' in board_text:
            ai_text = voice_text + ' ' + board_text
        print(f"[GPT] '{ai_text[:80]}'")
        clean_text = re.sub(r'[CORRECTION:[^]]*]', '', ai_text).strip()
        clean_text = re.sub(r'[TABLICA:[^]]*]', '', clean_text).strip()
        def call_tts():
            speech = openai_client.audio.speech.create(model="tts-1", voice="onyx", input=clean_text, speed=1.1)
            return speech.content
            speech = openai_client.audio.speech.create(model="tts-1", voice="onyx", input=clean_text, speed=1.05)
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
