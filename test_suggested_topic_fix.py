# -*- coding: utf-8 -*-
"""Offline: karta 'Nastepny krok' nie pokazuje juz samej nazwy przedmiotu jako 'tematu dnia'
(real prod 27.09.2026, user: "widze temat dnia to matematyka, temat to matematyka xd")."""
import os, sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models as models
from app.models import User
import app.api.users as users_mod

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()

NEXT = {"quiz": None}
async def fake_gen(**kw):
    return {"success": True, "quiz": NEXT["quiz"]}
users_mod.generate_quiz_from_topic = fake_gen

def make_user(uid, level, subject):
    u = User(firebase_uid=uid, email=uid + "@x.pl", education_level=level, favorite_subject=subject)
    db.add(u); db.commit(); db.refresh(u)
    return u

# 1) AI zwraca sam przedmiot jako title -> ma byc podmienione na fallback (jesli istnieje)
u1 = make_user("u1", "liceum_1", "matematyka")
NEXT["quiz"] = {"title": "Matematyka - Quiz", "questions": []}
asyncio.run(users_mod._refresh_suggested_topic_if_stale(u1, db))
check("AI zwrocilo sam przedmiot -> temat NIE jest juz samym przedmiotem", (u1.suggested_topic or "").strip().lower() != "matematyka", u1.suggested_topic)
check("podmieniony na fallback (niepusty)", bool(u1.suggested_topic), u1.suggested_topic)

# 2) AI zwraca konkretny temat -> zostaje bez zmian (inna para poziom/przedmiot niz test 1,
#    zeby nie trafic w cache (poziom, przedmiot) juz ustawiony przez test 1)
u2 = make_user("u2", "liceum_2", "matematyka")
NEXT["quiz"] = {"title": "Funkcje kwadratowe - Quiz", "questions": []}
asyncio.run(users_mod._refresh_suggested_topic_if_stale(u2, db))
check("konkretny temat zostaje niezmieniony", u2.suggested_topic == "Funkcje kwadratowe", u2.suggested_topic)

# 3) Bez ulubionego przedmiotu -> nic sie nie dzieje (brak crasha)
u3 = make_user("u3", "liceum_1", None)
asyncio.run(users_mod._refresh_suggested_topic_if_stale(u3, db))
check("brak przedmiotu -> brak sugestii, brak wyjatku", u3.suggested_topic is None)

# 4) Bez fallbacku (nieznana para poziom/przedmiot): AI ciagle zwraca sam przedmiot ->
#    temat zostaje pusty (nie pokazujemy bezuzytecznego "temat=przedmiot"), ALE drugie
#    wywolanie tego samego dnia (ta sama para poziom+przedmiot) NIE odpytuje juz AI ponownie.
calls = {"n": 0}
async def counting_gen(**kw):
    calls["n"] += 1
    return {"success": True, "quiz": {"title": "Fizyka - Quiz", "questions": []}}
users_mod.generate_quiz_from_topic = counting_gen
u4 = make_user("u4", "poziom_nieznany_xyz", "fizyka")
asyncio.run(users_mod._refresh_suggested_topic_if_stale(u4, db))
check("bez fallbacku: temat NIE jest ustawiony na sam przedmiot", (u4.suggested_topic or "").strip().lower() != "fizyka", u4.suggested_topic)
u4b = make_user("u4b", "poziom_nieznany_xyz", "fizyka")
asyncio.run(users_mod._refresh_suggested_topic_if_stale(u4b, db))
check("ta sama para poziom+przedmiot, ten sam dzien -> AI wywolane tylko RAZ (cache po parze)", calls["n"] == 1, calls["n"])
users_mod.generate_quiz_from_topic = fake_gen

db.close()
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
