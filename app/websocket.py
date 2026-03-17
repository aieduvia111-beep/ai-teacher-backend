from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from typing import Dict


class ConnectionManager:
    """Zarządza połączeniami WebSocket"""
    
    def __init__(self):
        # Słownik: user_id → WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Połącz nowego klienta"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"✅ Client {client_id} connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, client_id: str):
        """Rozłącz klienta"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"❌ Client {client_id} disconnected. Total: {len(self.active_connections)}")
    
    async def send_message(self, message: str, client_id: str):
        """Wyślij wiadomość do konkretnego klienta"""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)


# Globalny manager
manager = ConnectionManager()


async def handle_voice_websocket(websocket: WebSocket, client_id: str = "anonymous"):
    """
    Obsługuje WebSocket dla Live Bot (voice mode)
    
    Flow:
    1. Client łączy się
    2. Client wysyła audio chunks
    3. Backend wysyła do OpenAI
    4. OpenAI odpowiada (audio)
    5. Backend wysyła z powrotem do client
    """
    
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Odbierz wiadomość od klienta
            data = await websocket.receive_text()
            
            # Parse JSON
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "audio":
                    # Audio chunk od usera
                    audio_data = message.get("data")
                    
                    # TODO: Wyślij do OpenAI Realtime API
                    # Na razie - echo test
                    response = {
                        "type": "audio_response",
                        "text": "Testowa odpowiedź - OpenAI będzie jutro!",
                        "data": audio_data  # Echo
                    }
                    
                    await manager.send_message(json.dumps(response), client_id)
                
                elif msg_type == "text":
                    # Tekstowa wiadomość (fallback)
                    text = message.get("data")
                    
                    response = {
                        "type": "text_response",
                        "text": f"Otrzymałem: {text}"
                    }
                    
                    await manager.send_message(json.dumps(response), client_id)
                
                else:
                    # Nieznany typ
                    await manager.send_message(
                        json.dumps({"type": "error", "message": "Unknown message type"}),
                        client_id
                    )
            
            except json.JSONDecodeError:
                # Nieprawidłowy JSON
                await manager.send_message(
                    json.dumps({"type": "error", "message": "Invalid JSON"}),
                    client_id
                )
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        print(f"Client {client_id} disconnected")
    
    except Exception as e:
        print(f"Error in WebSocket: {e}")
        manager.disconnect(client_id)