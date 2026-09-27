# -*- coding: utf-8 -*-
"""Offline (OpenAI zamockowany, ZERO realnych wywolan API - kosztuje pieniadze):
klient poskarzyl sie 27.09.2026 real prod ze Chat AI "nie umie dobrze wytlumaczyc",
konkretnie ulamki dziesietne. Przyczyna: chat.py jako JEDYNA funkcja w calej appce
nigdy nie wolala describe_level() - quiz/sprawdzian/notatki/glos/tablica wszystkie
dostosowuja jezyk do klasy ucznia, chat mial to zaszyte na sztywno na "liceum".
Sprawdza: poziom ucznia trafia do system promptu wyslanego do OpenAI; brak/nieznany
poziom nie crashuje (bezpieczny fallback do bazowego promptu)."""
import os, sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

import json
import app.api.chat as chat_mod
from app.api.chat import chat_message, ChatRequest

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

class FakeUser:
    def __init__(self, education_level=None, favorite_subject=None):
        self.education_level = education_level
        self.favorite_subject = favorite_subject

CAPTURED = {}
CANNED_JSON = json.dumps({
    "title": "Ulamki dziesietne", "text": "Test", "has_latex": False,
    "show_sources": False, "show_videos": False, "show_chart": False,
    "chart": None, "diagram": None, "generate_image": None, "topic_en": "decimal fractions"
})

class FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()

class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]

def fake_create(**kwargs):
    CAPTURED["messages"] = kwargs.get("messages")
    return FakeResponse(CANNED_JSON)

chat_mod.client.chat.completions.create = fake_create

# 1) uczen szkoly podstawowej pyta o ulamki dziesietne -> poziom MUSI trafic do system promptu
req = ChatRequest(text="Wytlumacz mi ulamki dziesietne")
user = FakeUser(education_level="podstawowka_5", favorite_subject="matematyka")
asyncio.run(chat_message(req, user))
system_msg = CAPTURED["messages"][0]["content"]
MARKER = "NAJWAZNIEJSZA instrukcja"  # unikalny fragment TYLKO z nowego bloku poziomu (samo "KRYTYCZNE" juz wystepuje w bazowym prompcie, wiec nie nadaje sie na marker)
check("system_prompt NIE jest juz zaszyty na sztywno na liceum", "szkół średnich" not in system_msg, system_msg[:120])
check("poziom ucznia (podstawowa) TRAFIA do system promptu", "podstaw" in system_msg.lower(), system_msg)
check("instrukcja dostosowania jezyka jest NAJWAZNIEJSZA", MARKER in system_msg, system_msg)

# 2) inny poziom (liceum) -> inny opis w promptcie (nie ten sam tekst co podstawowka)
CAPTURED.clear()
req2 = ChatRequest(text="Wytlumacz mi pochodne")
user2 = FakeUser(education_level="liceum_2", favorite_subject="matematyka")
asyncio.run(chat_message(req2, user2))
system_msg_liceum = CAPTURED["messages"][0]["content"]
check("liceum dostaje INNY opis poziomu niz podstawowka (prompt faktycznie sie rozni)", system_msg_liceum != system_msg, (system_msg_liceum[-200:], system_msg[-200:]))

# 3) brak poziomu (None) -> nie crashuje, bezpieczny fallback do bazowego promptu
CAPTURED.clear()
req3 = ChatRequest(text="Cos tam")
user3 = FakeUser(education_level=None, favorite_subject=None)
asyncio.run(chat_message(req3, user3))
check("brak poziomu -> brak crasha, dostaje bazowy prompt bez wstrzykniecia poziomu", MARKER not in CAPTURED["messages"][0]["content"])

# 4) niepoprawny/nieznany poziom (np. zly string z bazy) -> nie crashuje
CAPTURED.clear()
req4 = ChatRequest(text="Cos tam")
user4 = FakeUser(education_level="totalny_smiec_xyz", favorite_subject=None)
asyncio.run(chat_message(req4, user4))
check("nieznany poziom -> brak crasha (bezpieczny fallback)", MARKER not in CAPTURED["messages"][0]["content"])

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
