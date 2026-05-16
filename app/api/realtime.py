"""REALTIME VOICE - WebSocket proxy do OpenAI Realtime API"""
import asyncio
import json
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..config import settings

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"

SYSTEM_PROMPT = """You are Eduvia AI - a smart, warm Polish tutor for students.
Always reply in Polish. Keep answers SHORT: 2-3 sentences max.
Be warm and natural. End with a short follow-up question.
When explaining formulas or steps add: [WHITEBOARD:{"items":["punkt1","punkt2"]}]
If student makes grammar mistake add: [CORRECTION: zle -> dobrze]
"""

@router.websocket("/ws")
async def realtime_ws(ws: WebSocket):
    await ws.accept()
    print("[RT] Klient polaczony")
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }
    try:
        async with websockets.connect(
            OPENAI_REALTIME_URL,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=30,
            close_timeout=10,
            max_size=10 * 1024 * 1024
        ) as openai_ws:
            print("[RT] Polaczono z OpenAI")
            await openai_ws.send(json.dumps({
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
                        "threshold": 0.3,
                        "prefix_padding_ms": 200,
                        "silence_duration_ms": 400
                    },
                    "temperature": 0.7,
                    "max_response_output_tokens": 200
                }
            }))

            async def from_browser():
                try:
                    while True:
                        data = await ws.receive_text()
                        msg = json.loads(data)
                        if msg.get("type") == "context.update":
                            ctx = msg.get("context", {})
                            level_map = {"podstawowka":"szkola podstawowa","liceum":"liceum","matura":"matura","studia":"studia"}
                            extra = ""
                            if ctx.get("level"): extra += f"\nPOZIOM: {level_map.get(ctx['level'], ctx['level'])}"
                            if ctx.get("subject"): extra += f"\nPRZEDMIOT: {ctx['subject']}"
                            if ctx.get("topic"): extra += f"\nTEMAT: {ctx['topic']}"
                            if extra:
                                await openai_ws.send(json.dumps({"type":"session.update","session":{"instructions":SYSTEM_PROMPT+extra}}))
                            continue
                        await openai_ws.send(data)
                except WebSocketDisconnect:
                    print("[RT] Browser rozlaczony")
                except Exception as e:
                    print(f"[RT] from_browser: {e}")

            async def from_openai():
                try:
                    async for message in openai_ws:
                        try:
                            await ws.send_text(message if isinstance(message, str) else message.decode())
                        except Exception as e:
                            print(f"[RT] send: {e}")
                            break
                except Exception as e:
                    print(f"[RT] from_openai: {e}")

            await asyncio.gather(from_browser(), from_openai())

    except Exception as e:
        print(f"[RT] Blad: {e}")
        try:
            await ws.send_text(json.dumps({"type":"error","error":{"message":str(e)}}))
        except:
            pass
    finally:
        print("[RT] Sesja zakonczona")

@router.get("/health")
async def health():
    return {"status": "ok", "service": "realtime", "model": "gpt-4o-realtime-preview"}
