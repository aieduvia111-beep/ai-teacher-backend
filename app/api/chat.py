from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
from datetime import datetime
from app.config import settings
import urllib.parse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """Jesteś Learnio AI - najlepszym nauczycielem AI dla polskich uczniów szkół średnich.
Odpowiadasz po polsku, przystępnie i ciekawie.

ZAWSZE zwracaj odpowiedź jako JSON w dokładnie tym formacie (nic poza JSONem!):
{
  "title": "Krótki tytuł tematu max 5 słów np. Fotosynteza krok po kroku",
  "text": "Twoja pełna odpowiedź w Markdown",
  "has_latex": true lub false,
  "show_sources": true lub false,
  "show_videos": true lub false,
  "show_chart": false,
  "chart": null,
  "diagram": null,
  "topic_en": "temat po angielsku do YouTube i Wolfram"
}

KIEDY ustawiać flagi:
- has_latex: true gdy odpowiedź zawiera wzory matematyczne lub chemiczne w LaTeX
- show_sources: true gdy pytanie dotyczy nauki (biologia, chemia, fizyka, historia, geografia, matematyka)
- show_videos: true gdy wizualizacja pomogłaby zrozumieć (procesy, zjawiska, eksperymenty)
- show_chart: true TYLKO gdy pytasz o porównanie liczb/danych np. porównaj planety, najpopularniejsze pierwiastki
- diagram: ustaw gdy uczeń prosi o wizualizację/schemat/diagram procesu biologicznego lub chemicznego

POLE "diagram" — możliwe wartości (string):
- "photosynthesis"  → schemat fotosyntezy (CO2 + H2O → glukoza + O2)
- "cell"            → schemat komórki roślinnej lub zwierzęcej
- "dna"             → schemat struktury DNA (podwójna helisa)
- "atom"            → schemat budowy atomu
- "mitosis"         → schemat podziału komórki
- "water_cycle"     → obieg wody w przyrodzie
- "food_chain"      → łańcuch pokarmowy
- null              → brak diagramu (domyślnie)

Jeśli uczeń pyta o wizualizację/schemat/diagram i temat pasuje do listy wyżej — ustaw "diagram" na odpowiednią wartość.
Jeśli temat NIE pasuje — zostaw null.

KRYTYCZNE: Jeśli show_chart = true, pole "text" NIE może zawierać żadnego JSON ani danych wykresu!
Dane wykresu idą TYLKO do pola "chart". W "text" piszesz normalny tekst z wyjaśnieniem.

ZASADY dla pola text:
- Używaj **pogrubień** dla kluczowych pojęć
- Używaj ## dla nagłówków sekcji
- Wzory matematyczne/chemiczne ZAWSZE w LaTeX: $$wzor$$ dla bloków, $wzor$ inline
- Emoji są OK ale nie przesadzaj
- Gdy uczeń wysyła zdjęcie z zadaniami lub listę zadań - ROZWIĄŻ KAŻDE z nich osobno krok po kroku
- Gdy jest wiele zadań - numeruj je ## Zadanie 1, ## Zadanie 2 itd.
- Każde zadanie rozwiąż DOKŁADNIE i KOMPLETNIE - nie skracaj, nie pomijaj kroków
- Podaj pełne obliczenia i odpowiedź końcową dla każdego zadania

ZASADY dla title:
- Maksymalnie 5 słów
- Ciekawy jak tytuł w Knowunity
- Przykłady: Fotosynteza krok po kroku, Równania kwadratowe podstawy, Układ słoneczny planety
"""


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    text: str
    history: Optional[List[ChatMessage]] = []
    image: Optional[str] = None

def _build_response(ai_data: dict, user_message: str) -> dict:
    topic_en = ai_data.get("topic_en", user_message)
    topic_pl = user_message
    enc_en = urllib.parse.quote(topic_en)
    enc_pl = urllib.parse.quote(topic_pl)

    sources = []
    if ai_data.get("show_sources", False):
        sources = [
            {"title": "Wikipedia (PL)", "url": f"https://pl.wikipedia.org/wiki/Special:Search?search={enc_pl}", "icon": "📖"},
            {"title": "Khan Academy", "url": f"https://www.khanacademy.org/search?page_search_query={enc_en}", "icon": "🎓"},
            {"title": "Wolfram Alpha", "url": f"https://www.wolframalpha.com/input?i={enc_en}", "icon": "🔢"}
        ]

    videos = []
    if ai_data.get("show_videos", False):
        videos = [
            {"title": f"🇵🇱 {topic_pl} — YouTube po polsku", "video_id": "none", "url": f"https://www.youtube.com/results?search_query={enc_pl}", "channel": "YouTube Polska"},
            {"title": f"🌍 {topic_en} — YouTube po angielsku", "video_id": "none", "url": f"https://www.youtube.com/results?search_query={enc_en}+explained", "channel": "YouTube English"}
        ]

    return {
        "title": ai_data.get("title", ""),
        "text": ai_data.get("text", ""),
        "has_latex": ai_data.get("has_latex", False),
        "sources": sources,
        "videos": videos,
        "chart": ai_data.get("chart") if ai_data.get("show_chart", False) else None,
        "diagram": ai_data.get("diagram", None),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/message")
async def chat_message(req: ChatRequest):
    """HTTP endpoint - przyjmuje historię rozmowy i zwraca odpowiedź AI"""
    try:
        # Buduj historię
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Dodaj historię z frontendu
        for msg in (req.history or [])[-10:]:
            messages.append({"role": msg.role, "content": msg.content})

        # Dodaj aktualną wiadomość
        if req.image:
            img_b64 = req.image.split("base64,")[1] if "base64," in req.image else req.image
            user_content = [
                {"type": "text", "text": req.text or "Przeanalizuj to zdjecie i rozwiaz zadania."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}}
            ]
        else:
            user_content = req.text

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=4000,
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        raw_response = response.choices[0].message.content

        try:
            ai_data = json.loads(raw_response)
        except json.JSONDecodeError:
            ai_data = {"title": "Odpowiedź", "text": raw_response, "has_latex": False, "show_sources": False, "show_videos": False, "show_chart": False, "chart": None, "topic_en": req.text}

        return _build_response(ai_data, req.text)

    except Exception as e:
        print(f"❌ Błąd chat HTTP: {e}")
        return {
            "title": "Błąd",
            "text": f"⚠️ Wystąpił błąd: `{str(e)}`",
            "has_latex": False, "sources": [], "videos": [], "chart": None, "error": True
        }


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket, user_id: int = 1):
    await websocket.accept()
    print(f"✅ User {user_id} połączył się z chatem")

    # Pamięć rozmowy w sesji
    conversation_history = []

    try:
        while True:
            raw = await websocket.receive_text()
            message_data = json.loads(raw)
            user_message = message_data.get("text", "").strip()
            image_data = message_data.get("image", None)

            if not user_message and not image_data:
                continue

            print(f"📨 Pytanie: {user_message[:80]}")

            # Buduj content - tekst + opcjonalne zdjecie
            if image_data:
                img_b64 = image_data.split("base64,")[1] if "base64," in image_data else image_data
                user_content = [
                    {"type": "text", "text": user_message or "Przeanalizuj to zdjecie. Rozwiaz WSZYSTKIE widoczne zadania krok po kroku. Kazde zadanie osobno z pelnym rozwiazaniem."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}}
                ]
            else:
                user_content = user_message

            # Dodaj do historii
            conversation_history.append({
                "role": "user",
                "content": user_content
            })

            # Ogranicz historię do ostatnich 10 wiadomości
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-10:]

            try:
                # Wywołaj OpenAI
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *conversation_history
                    ],
                    max_tokens=4000,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )

                raw_response = response.choices[0].message.content

                # Parsuj JSON od AI
                try:
                    ai_data = json.loads(raw_response)
                except json.JSONDecodeError:
                    ai_data = {
                        "title": "Odpowiedź",
                        "text": raw_response,
                        "has_latex": False,
                        "show_sources": False,
                        "show_videos": False,
                        "show_chart": False,
                        "chart": None,
                        "topic_en": user_message
                    }

                # Dodaj odpowiedź do historii
                conversation_history.append({
                    "role": "assistant",
                    "content": raw_response
                })

                # Buduj źródła i filmy
                topic_en = ai_data.get("topic_en", user_message)
                topic_pl = user_message
                enc_en = urllib.parse.quote(topic_en)
                enc_pl = urllib.parse.quote(topic_pl)

                sources = []
                if ai_data.get("show_sources", False):
                    sources = [
                        {
                            "title": "Wikipedia (PL)",
                            "url": f"https://pl.wikipedia.org/wiki/Special:Search?search={enc_pl}",
                            "icon": "📖"
                        },
                        {
                            "title": "Khan Academy",
                            "url": f"https://www.khanacademy.org/search?page_search_query={enc_en}",
                            "icon": "🎓"
                        },
                        {
                            "title": "Wolfram Alpha",
                            "url": f"https://www.wolframalpha.com/input?i={enc_en}",
                            "icon": "🔢"
                        }
                    ]

                videos = []
                if ai_data.get("show_videos", False):
                    videos = [
                        {
                            "title": f"🇵🇱 {topic_pl} — YouTube po polsku",
                            "video_id": "none",
                            "url": f"https://www.youtube.com/results?search_query={enc_pl}",
                            "channel": "YouTube Polska"
                        },
                        {
                            "title": f"🌍 {topic_en} — YouTube po angielsku",
                            "video_id": "none",
                            "url": f"https://www.youtube.com/results?search_query={enc_en}+explained",
                            "channel": "YouTube English"
                        }
                    ]

                # Wykres
                chart = ai_data.get("chart") if ai_data.get("show_chart", False) else None

                # Wyślij odpowiedź
                response_data = {
                    "title": ai_data.get("title", ""),
                    "text": ai_data.get("text", ""),
                    "has_latex": ai_data.get("has_latex", False),
                    "sources": sources,
                    "videos": videos,
                    "chart": chart,
                    "diagram": ai_data.get("diagram", None),
                    "timestamp": datetime.now().isoformat()
                }

                await websocket.send_json(response_data)
                print(f"✅ Odpowiedź wysłana: {ai_data.get('title', '')}")

            except Exception as e:
                import traceback
                print(f"❌ Błąd OpenAI: {type(e).__name__}: {e}")
                print(traceback.format_exc())
                await websocket.send_json({
                    "title": "Błąd",
                    "text": f"⚠️ Przepraszam, wystąpił błąd.\n\n**Możliwe przyczyny:**\n- Klucz OpenAI jest nieprawidłowy lub wygasł\n- Brak środków na koncie OpenAI\n- Problem z połączeniem\n\n**Błąd techniczny:** `{str(e)}`",
                    "has_latex": False,
                    "sources": [],
                    "videos": [],
                    "chart": None,
                    "error": True
                })

    except WebSocketDisconnect:
        print(f"👋 User {user_id} rozłączył się")
    except Exception as e:
        print(f"❌ Nieoczekiwany błąd: {e}")


@router.get("/health")
async def health_check():
    """Sprawdź czy chat działa i czy klucz OpenAI jest ustawiony"""
    key = settings.OPENAI_API_KEY
    return {
        "status": "ok",
        "service": "chat",
        "model": "gpt-4o-mini",
        "openai_configured": bool(key),
        "key_preview": (key[:8] + "...") if key else "BRAK KLUCZA!"
    }