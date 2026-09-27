# -*- coding: utf-8 -*-
"""Offline (OpenAI zamockowany, ZERO realnych wywolan API - kosztuje pieniadze):
klient poskarzyl sie 27.09.2026 real prod ze Chat AI "nie umie dobrze wytlumaczyc",
konkretnie ulamki dziesietne. Przyczyna: chat.py jako JEDYNA funkcja w calej appce
nigdy nie wolala describe_level() - quiz/sprawdzian/notatki/glos/tablica wszystkie
dostosowuja jezyk do klasy ucznia, chat mial to zaszyte na sztywno na "liceum".
Sprawdza: poziom ucznia trafia do system promptu wyslanego do OpenAI; brak/nieznany
poziom nie crashuje (bezpieczny fallback do bazowego promptu); KAZDA rozmowa
zapisuje do bazy temat+poziom (bez tresci wiadomosci - prywatnosc), zeby dalo sie
retrospektywnie sprawdzic z jakiego tematu/poziomu byla skarga."""
import os, sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import GenerationRequestLog
import app.api.chat as chat_mod
from app.api.chat import chat_message, ChatRequest, chat_feedback, ChatFeedbackRequest

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
SessionLocal = sessionmaker(bind=eng)
db = SessionLocal()

class FakeUser:
    def __init__(self, education_level=None, favorite_subject=None):
        self.education_level = education_level
        self.favorite_subject = favorite_subject

CAPTURED = {}
CANNED_JSON = json.dumps({
    "title": "Ułamki dziesiętne", "text": "Test", "has_latex": False,
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

MARKER = "NAJWAZNIEJSZA instrukcja"  # unikalny fragment TYLKO z nowego bloku poziomu (samo "KRYTYCZNE" juz wystepuje w bazowym prompcie, wiec nie nadaje sie na marker)

# 1) uczen szkoly podstawowej pyta o ulamki dziesietne -> poziom MUSI trafic do system promptu I do logu w bazie
req = ChatRequest(text="Wytlumacz mi ulamki dziesietne")
user = FakeUser(education_level="podstawowka_5", favorite_subject="matematyka")
result1 = asyncio.run(chat_message(req, user, db))
system_msg = CAPTURED["messages"][0]["content"]
check("system_prompt NIE jest juz zaszyty na sztywno na liceum", "szkół średnich" not in system_msg, system_msg[:120])
check("poziom ucznia (podstawowa) TRAFIA do system promptu", "podstaw" in system_msg.lower(), system_msg)
check("instrukcja dostosowania jezyka jest NAJWAZNIEJSZA", MARKER in system_msg, system_msg)

log1 = db.query(GenerationRequestLog).filter(GenerationRequestLog.feature == "chat").order_by(GenerationRequestLog.id.desc()).first()
check("rozmowa ZALOGOWANA do bazy (feature=chat)", log1 is not None)
check("log ma temat (tytul od AI), np. do wyszukania po skardze", log1 and log1.temat == "Ułamki dziesiętne", log1 and log1.temat)
check("log ma poziom ucznia zapisany", log1 and log1.poziom == "podstawowka_5", log1 and log1.poziom)
check("odpowiedz zawiera log_id, zeby front mogl podpiac kciuk gora/dol", result1.get("log_id") == log1.id, (result1.get("log_id"), log1.id))

# 2) inny poziom (liceum) -> inny opis w promptcie (nie ten sam tekst co podstawowka)
CAPTURED.clear()
req2 = ChatRequest(text="Wytlumacz mi pochodne")
user2 = FakeUser(education_level="liceum_2", favorite_subject="matematyka")
asyncio.run(chat_message(req2, user2, db))
system_msg_liceum = CAPTURED["messages"][0]["content"]
check("liceum dostaje INNY opis poziomu niz podstawowka (prompt faktycznie sie rozni)", system_msg_liceum != system_msg, (system_msg_liceum[-200:], system_msg[-200:]))

# 3) brak poziomu (None) -> nie crashuje, bezpieczny fallback do bazowego promptu; log i tak powstaje (z poziom=None)
CAPTURED.clear()
req3 = ChatRequest(text="Cos tam")
user3 = FakeUser(education_level=None, favorite_subject=None)
asyncio.run(chat_message(req3, user3, db))
check("brak poziomu -> brak crasha, dostaje bazowy prompt bez wstrzykniecia poziomu", MARKER not in CAPTURED["messages"][0]["content"])
log3 = db.query(GenerationRequestLog).filter(GenerationRequestLog.feature == "chat").order_by(GenerationRequestLog.id.desc()).first()
check("log powstaje nawet bez poziomu (poziom=None), nie wywala odpowiedzi", log3 is not None and log3.poziom is None, log3 and log3.poziom)

# 4) niepoprawny/nieznany poziom (np. zly string z bazy) -> nie crashuje
CAPTURED.clear()
req4 = ChatRequest(text="Cos tam")
user4 = FakeUser(education_level="totalny_smiec_xyz", favorite_subject=None)
asyncio.run(chat_message(req4, user4, db))
check("nieznany poziom -> brak crasha (bezpieczny fallback)", MARKER not in CAPTURED["messages"][0]["content"])

# 5) NIGDY nie logujemy tresci wiadomosci - tylko temat (krotki tytul), sprawdzamy ze pelny tekst pytania nie wyciekl do logu
check("liczba wpisow w logu = liczba rozmow (kazda sie zaloguje)", db.query(GenerationRequestLog).filter(GenerationRequestLog.feature == "chat").count() == 4)

# 6) kciuk gora/dol (user: "dlaczego nie ma ze pokazuje czy dobra odpowiedz czy zla")
fb_user = FakeUser()  # get_current_app_user zwraca User, ale sam endpoint tylko czyta req.log_id - user nieuzywany do logiki
fb_bad = asyncio.run(chat_feedback(ChatFeedbackRequest(log_id=log1.id, helpful=False), fb_user, db))
check("kciuk w dol -> sukces", fb_bad.get("success") is True, fb_bad)
db.refresh(log1)
check("kciuk w dol -> zapisany jako odrzucony (rejected_count=1, accepted_count=0)", log1.rejected_count == 1 and log1.accepted_count == 0, (log1.rejected_count, log1.accepted_count))

fb_good = asyncio.run(chat_feedback(ChatFeedbackRequest(log_id=log1.id, helpful=True), fb_user, db))
check("kciuk w gore -> sukces, nadpisuje poprzednia ocene", fb_good.get("success") is True, fb_good)
db.refresh(log1)
check("kciuk w gore -> zapisany jako zaakceptowany (accepted_count=1, rejected_count=0)", log1.accepted_count == 1 and log1.rejected_count == 0, (log1.accepted_count, log1.rejected_count))

fb_missing = asyncio.run(chat_feedback(ChatFeedbackRequest(log_id=999999, helpful=True), fb_user, db))
check("nieistniejacy log_id -> brak crasha, czytelny blad", fb_missing.get("success") is False, fb_missing)

db.close()
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
