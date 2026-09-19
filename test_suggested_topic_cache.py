# -*- coding: utf-8 -*-
"""Offline (zero AI): temat "Nastepny krok" jest generowany raz dziennie na pare
(poziom, przedmiot), nie raz na usera; kolejny dzien = inny temat; blad
generacji nie jest cache'owany."""
import os, sys, io, asyncio, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import User
import app.api.users as users

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()

CALLS = []
TITLES = iter(["Funkcje - Quiz", "Ciagi - Quiz", "Optyka - Quiz", "Trygonometria - Quiz", "X - Quiz"])
FAIL = {"on": False}

async def fake_gen(**kw):
    CALLS.append(kw)
    if FAIL["on"]:
        return {"success": False, "error": "boom"}
    return {"success": True, "quiz": {"title": next(TITLES)}}
users.generate_quiz_from_topic = fake_gen

def mk(uid, level, subj):
    u = User(firebase_uid=uid, email=uid + "@x.pl", is_premium=False, education_level=level, favorite_subject=subj)
    db.add(u); db.commit(); return u

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, detail))

run = lambda u: asyncio.run(users._refresh_suggested_topic_if_stale(u, db))

a, b, c = mk("a", "liceum_2", "matematyka"), mk("b", "liceum_2", "matematyka"), mk("c", "liceum_2", "matematyka")
d = mk("d", "podstawowka_8", "fizyka")
for u in (a, b, c): run(u)
check("3 userow tej samej pary = 1 wywolanie AI", len(CALLS) == 1, len(CALLS))
check("wszyscy dostali ten sam temat", a.suggested_topic == b.suggested_topic == c.suggested_topic == "Funkcje", (a.suggested_topic, b.suggested_topic))
run(d)
check("inna para = osobne wywolanie", len(CALLS) == 2 and d.suggested_topic == "Ciagi", (len(CALLS), d.suggested_topic))
run(a)
check("ten sam dzien, user juz ma temat = brak wywolania", len(CALLS) == 2)

# nastepny dzien
real_date = users.date
class FakeDate(datetime.date):
    @classmethod
    def today(cls): return datetime.date.today() + datetime.timedelta(days=1)
users.date = FakeDate
run(a)
check("nowy dzien = nowe wywolanie", len(CALLS) == 3, len(CALLS))
check("nowy dzien: prompt zabrania wczorajszego tematu", "Funkcje" in CALLS[2]["wlasne_instrukcje"], CALLS[2]["wlasne_instrukcje"])
check("nowy dzien: nowy temat", a.suggested_topic == "Optyka", a.suggested_topic)
run(b)
check("drugi user tej pary w nowy dzien = z cache", len(CALLS) == 3 and b.suggested_topic == "Optyka", (len(CALLS), b.suggested_topic))

# blad nie jest cache'owany
users.date = type("D2", (datetime.date,), {"today": classmethod(lambda cls: datetime.date.today() + datetime.timedelta(days=2))})
FAIL["on"] = True
run(c)
check("blad generacji: temat niezmieniony", c.suggested_topic == "Funkcje", c.suggested_topic)
FAIL["on"] = False
run(c)
check("po bledzie kolejna proba generuje ponownie", len(CALLS) == 5 and c.suggested_topic == "Trygonometria", (len(CALLS), c.suggested_topic))
users.date = real_date
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
