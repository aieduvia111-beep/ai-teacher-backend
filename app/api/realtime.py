"""REALTIME VOICE — WebSocket proxy do OpenAI Realtime API"""
import asyncio
import json
import base64
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..config import settings

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"

SYSTEM_PROMPT = """You are Eduvia AI — a smart, warm tutor for students.

LANGUAGE RULE — CRITICAL:
- Detect the language the student speaks and ALWAYS reply in that same language
- If student speaks Polish → reply in Polish
- If student speaks English or is PRACTICING English → reply in English only

TEACHING STYLE:
- Keep answers SHORT: 2-4 sentences max (this is voice)
- Be warm and natural like a real teacher, not robotic
- Use simple words and real-life examples
- End with a short follow-up question to keep conversation going
- If student shows something on camera → describe and help solve it step by step

WHITEBOARD:
- When you explain something that needs steps, formulas or key points → add at the END of your response a JSON block like this:
  [WHITEBOARD:{"items":["Wzór: a² + b² = c²","Krok 1: podstaw wartości","Krok 2: oblicz"]}]
- Only add WHITEBOARD block when it genuinely helps (formulas, steps, key vocabulary)
- Keep whiteboard items SHORT — max 6 words each, max 5 items
- Do NOT add whiteboard for simple conversational answers

CORRECTIONS:
- When student makes a grammar mistake, correct naturally in your reply
- At the END of response add: [CORRECTION: wrong → correct]
- Max one correction per response
"""


@router.websocket("/ws")
async def realtime_ws(ws: WebSocket):
    """
    WebSocket proxy:
    Browser <──WS──> FastAPI <──WS──> OpenAI Realtime
    """
    await ws.accept()
    print("[REALTIME] Klient połączony")

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(OPENAI_REALTIME_URL, additional_headers=headers) as openai_ws:
            print("[REALTIME] Połączono z OpenAI Realtime")

            # Skonfiguruj sesję OpenAI
            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": SYSTEM_PROMPT,
                    "voice": "nova",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 600
                    },
                    "temperature": 0.7,
                    "max_response_output_tokens": 300
                }
            }
            await openai_ws.send(json.dumps(session_config))

            async def browser_to_openai():
                """Przekazuje wiadomości od przeglądarki do OpenAI"""
                try:
                    while True:
                        data = await ws.receive_text()
                        msg = json.loads(data)

                        # Obsługa aktualizacji kontekstu (poziom, przedmiot, temat)
                        if msg.get("type") == "context.update":
                            ctx = msg.get("context", {})
                            level = ctx.get("level", "")
                            subject = ctx.get("subject", "")
                            topic = ctx.get("topic", "")

                            extra = ""
                            if level:
                                level_map = {
                                    "podstawowka": "szkoła podstawowa — bardzo proste słowa, krótkie zdania",
                                    "liceum": "liceum/technikum — pełna terminologia",
                                    "matura": "poziom maturalny — zadania maturalne i schematy",
                                    "studia": "studia — pełna formalizacja, dowody"
                                }
                                extra += f"\nSTUDENT LEVEL: {level_map.get(level, level)}"
                            if subject:
                                extra += f"\nFOCUS SUBJECT: {subject}"
                            if topic:
                                extra += f"\nSESSION TOPIC: {topic} — start the conversation about this topic."

                            if extra:
                                update = {
                                    "type": "session.update",
                                    "session": {
                                        "instructions": SYSTEM_PROMPT + extra
                                    }
                                }
                                await openai_ws.send(json.dumps(update))
                            continue

                        # Wszystko inne (audio, text) przekaż dalej
                        await openai_ws.send(data)

                except WebSocketDisconnect:
                    print("[REALTIME] Przeglądarka rozłączona")
                except Exception as e:
                    print(f"[REALTIME] browser_to_openai error: {e}")

            async def openai_to_browser():
                """Przekazuje odpowiedzi OpenAI do przeglądarki"""
                try:
                    async for message in openai_ws:
                        try:
                            msg = json.loads(message)
                            msg_type = msg.get("type", "")

                            # Parsuj WHITEBOARD i CORRECTION z delta tekstów
                            if msg_type == "response.text.delta":
                                delta = msg.get("delta", "")
                                # Wykryj whiteboard w strumieniu
                                if "[WHITEBOARD:" in delta:
                                    await ws.send_text(json.dumps({
                                        "type": "whiteboard.update",
                                        "raw": delta
                                    }))
                                    continue

                            # Przekaż do przeglądarki
                            await ws.send_text(message)

                        except Exception as e:
                            print(f"[REALTIME] parse error: {e}")
                            await ws.send_text(message)

                except Exception as e:
                    print(f"[REALTIME] openai_to_browser error: {e}")

            # Uruchom obie pętle równolegle
            await asyncio.gather(
                browser_to_openai(),
                openai_to_browser()
            )

    except WebSocketDisconnect:
        print("[REALTIME] Klient rozłączył się przed połączeniem z OpenAI")
    except Exception as e:
        print(f"[REALTIME] Błąd: {e}")
        try:
            await ws.send_text(json.dumps({
                "type": "error",
                "error": {"message": str(e)}
            }))
        except:
            pass
    finally:
        print("[REALTIME] Sesja zakończona")


@router.get("/health")
async def realtime_health():
    return {"status": "ok", "service": "realtime", "model": "gpt-4o-realtime-preview"}
