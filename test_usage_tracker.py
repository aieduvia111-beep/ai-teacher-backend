# -*- coding: utf-8 -*-
"""Offline (zero AI, zero sieci): usage_tracker liczy tokeny z response.usage
na etykiete 'modul.funkcja', dziala dla sync/async/watkow/strumieni, nie zmienia
zwracanej odpowiedzi i zapisuje sumy do tabeli api_usage_daily."""
import os, sys, io, asyncio, threading, types
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from openai.resources.chat.completions import Completions, AsyncCompletions
FAKE = types.SimpleNamespace(
    model="gpt-4o-mini-2024-07-18",
    usage=types.SimpleNamespace(prompt_tokens=1000, completion_tokens=200,
                                prompt_tokens_details=types.SimpleNamespace(cached_tokens=400)),
    choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))],
)
STREAM = object()   # odpowiedz strumieniowa: brak .usage

def fake_sync(self, *a, **k):
    return STREAM if k.get("stream") else FAKE
async def fake_async(self, *a, **k):
    return STREAM if k.get("stream") else FAKE
Completions.create = fake_sync            # podmiana PRZED install() -> zadne wywolanie nie idzie do sieci
AsyncCompletions.create = fake_async

import app.usage_tracker as ut
ut.install()
ut.install()                              # idempotentne

from openai import OpenAI, AsyncOpenAI
c, ac = OpenAI(api_key="x"), AsyncOpenAI(api_key="x")
FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, detail))

# etykieta = modul app.* wolajacy; symulujemy wywolanie z modulu app.notes_pdf_generator
mod = types.ModuleType("app.notes_pdf_generator"); mod.__dict__["c"] = c; mod.__dict__["ac"] = ac
exec("def generate_pdf():\n    return c.chat.completions.create(model='gpt-4o-mini', messages=[])\n"
     "async def agen():\n    return await ac.chat.completions.create(model='gpt-4o-mini', messages=[])\n"
     "def gstream():\n    return c.chat.completions.create(model='gpt-4o-mini', messages=[], stream=True)\n", mod.__dict__)
sys.modules["app.notes_pdf_generator"] = mod

r1 = mod.generate_pdf()
r2 = asyncio.run(mod.agen())
res = []
t = threading.Thread(target=lambda: res.append(mod.generate_pdf())); t.start(); t.join()
r4 = mod.gstream()
check("odpowiedz sync nie zmieniona", r1 is FAKE)
check("odpowiedz async nie zmieniona", r2 is FAKE)
check("odpowiedz z watku nie zmieniona", res and res[0] is FAKE)
check("odpowiedz strumieniowa nie zmieniona", r4 is STREAM)

snap = dict(ut._counters)
keys = [k for k in snap if k[1].startswith("notes_pdf_generator.")]
by_label = {k[1]: snap[k] for k in keys}
print("  liczniki:", by_label)
check("sync+watek: 2 wywolania generate_pdf, 2000/400 tokenow, 800 cached",
      by_label.get("notes_pdf_generator.generate_pdf") == [2, 2000, 400, 800, 0], by_label)
check("async: etykieta agen, 1 wywolanie", by_label.get("notes_pdf_generator.agen") == [1, 1000, 200, 400, 0], by_label)
check("stream: policzone jako stream_call, tokeny 0", by_label.get("notes_pdf_generator.gstream") == [1, 0, 0, 0, 1], by_label)

# zapis do bazy + skumulowanie przy kolejnym flush
from app.database import SessionLocal, engine, Base
from app.models import ApiUsageDaily
Base.metadata.create_all(bind=engine)   # w aplikacji robi to startup PRZED install()
ut._flush()
db = SessionLocal()
rows = db.query(ApiUsageDaily).filter(ApiUsageDaily.label.like("notes_pdf_generator.%")).all()
check("zapis do bazy: 3 etykiety", len(rows) == 3, [(r.label, r.calls) for r in rows])
mod.generate_pdf(); ut._flush()
db.expire_all()
r = db.query(ApiUsageDaily).filter_by(label="notes_pdf_generator.generate_pdf").first()
check("kolejny flush DODAJE do istniejacego wiersza (3 wywolania, 3000 tokenow)", r and r.calls == 3 and r.prompt_tokens == 3000, r and (r.calls, r.prompt_tokens))
for x in db.query(ApiUsageDaily).filter(ApiUsageDaily.label.like("notes_pdf_generator.%")).all(): db.delete(x)
db.commit(); db.close()
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
