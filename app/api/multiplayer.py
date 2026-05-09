from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import json
import random
import string
import asyncio

router = APIRouter()

def gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

rooms: Dict[str, dict] = {}

class Room:
    def __init__(self, code, host_id, topic, num_q):
        self.code = code
        self.host_id = host_id
        self.topic = topic
        self.num_q = num_q
        self.players = {}  # uid -> {name, score, ws}
        self.questions = []
        self.current_q = -1
        self.state = 'waiting'  # waiting, playing, finished
        self.answers_this_round = {}

    async def broadcast(self, msg):
        dead = []
        for uid, p in self.players.items():
            try:
                await p['ws'].send_text(json.dumps(msg))
            except:
                dead.append(uid)
        for uid in dead:
            del self.players[uid]

    def get_state(self):
        return {
            'code': self.code,
            'state': self.state,
            'players': [{
                'uid': uid,
                'name': p['name'],
                'score': p['score'],
                'isHost': uid == self.host_id
            } for uid, p in self.players.items()],
            'currentQ': self.current_q,
            'totalQ': len(self.questions),
            'question': self.questions[self.current_q] if self.current_q >= 0 and self.current_q < len(self.questions) else None
        }

active_rooms: Dict[str, Room] = {}

@router.post('/api/multiplayer/create')
async def create_room(data: dict):
    code = gen_code()
    while code in active_rooms:
        code = gen_code()
    room = Room(code, data['uid'], data.get('topic', ''), data.get('num_q', 10))
    active_rooms[code] = room
    return {'code': code}

@router.post('/api/multiplayer/check/{code}')
async def check_room(code: str):
    if code not in active_rooms:
        return {'exists': False}
    room = active_rooms[code]
    return {'exists': True, 'state': room.state, 'players': len(room.players)}

@router.websocket('/ws/multiplayer/{code}/{uid}/{name}')
async def multiplayer_ws(ws: WebSocket, code: str, uid: str, name: str):
    await ws.accept()
    if code not in active_rooms:
        await ws.send_text(json.dumps({'type': 'error', 'msg': 'Pokój nie istnieje'}))
        await ws.close()
        return

    room = active_rooms[code]
    room.players[uid] = {'name': name, 'score': 0, 'ws': ws, 'answered': False}

    await room.broadcast({'type': 'player_joined', **room.get_state()})

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg['type'] == 'start' and uid == room.host_id:
                from app.services.openai_quiz import generate_quiz_from_topic
                room.state = 'generating'
                await room.broadcast({'type': 'generating'})
                result = await generate_quiz_from_topic(room.topic, 'liceum', room.num_q, 'medium')
                room.questions = result['quiz']['questions']
                room.current_q = 0
                room.state = 'playing'
                room.answers_this_round = {}
                await room.broadcast({'type': 'question', **room.get_state()})

            elif msg['type'] == 'answer':
                if uid not in room.answers_this_round:
                    room.answers_this_round[uid] = msg['answer']
                    q = room.questions[room.current_q]
                    correct = msg['answer'] == q['correct']
                    speed_bonus = max(0, 10 - len(room.answers_this_round))
                    if correct:
                        room.players[uid]['score'] += 10 + speed_bonus
                    await ws.send_text(json.dumps({'type': 'answer_result', 'correct': correct, 'score': room.players[uid]['score']}))

                    # Wszyscy odpowiedzieli
                    if len(room.answers_this_round) >= len(room.players):
                        await asyncio.sleep(2)
                        room.current_q += 1
                        room.answers_this_round = {}
                        if room.current_q >= len(room.questions):
                            room.state = 'finished'
                            await room.broadcast({'type': 'finished', **room.get_state()})
                        else:
                            await room.broadcast({'type': 'question', **room.get_state()})

    except WebSocketDisconnect:
        del room.players[uid]
        if not room.players:
            del active_rooms[code]
        else:
            await room.broadcast({'type': 'player_left', **room.get_state()})
