# -*- coding: utf-8 -*-
"""Offline (zero AI): limiter gpt-4o - limit na zamowienie, dzienny budzet, liczenie wydatku, brak
nieosłoniętych eskalacji w kodzie, generatory pomocnicze na mini, zachowanie sprawdzianu w rundach ratunkowych."""
import os, sys, io, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
from app.models import ApiUsageDaily
import app.usage_tracker as ut

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

for k in ("GPT4O_MAX_PER_ORDER", "GPT4O_DAILY_BUDGET_USD"): os.environ.pop(k, None)

# ---- limit na zamowienie ----
real_spend = ut.gpt4o_spend_today
ut.gpt4o_spend_today = lambda: 0.0
b = ut.OrderStrongBudget()
check("domyslnie 2 eskalacje na zamowienie: T, T, F", [b.use(), b.use(), b.use()] == [True, True, False])
os.environ["GPT4O_MAX_PER_ORDER"] = "1"
b = ut.OrderStrongBudget()
check("GPT4O_MAX_PER_ORDER=1: T, F", [b.use(), b.use()] == [True, False])
os.environ["GPT4O_MAX_PER_ORDER"] = "0"
check("GPT4O_MAX_PER_ORDER=0: gpt-4o wylaczone calkiem", ut.OrderStrongBudget().use() is False)
os.environ.pop("GPT4O_MAX_PER_ORDER")

# ---- dzienny budzet ----
ut.gpt4o_spend_today = lambda: 5.0
check("wydatek $5 > budzet $1.2: zaden nowy order nie dostaje gpt-4o", ut.OrderStrongBudget().use() is False and ut.strong_model_allowed() is False)
ut.gpt4o_spend_today = lambda: 0.5
check("wydatek $0.5 < budzet: wolno", ut.strong_model_allowed() is True)
os.environ["GPT4O_DAILY_BUDGET_USD"] = "0"
ut.gpt4o_spend_today = lambda: 99.0
check("GPT4O_DAILY_BUDGET_USD=0: brak limitu dziennego", ut.strong_model_allowed() is True)
os.environ["GPT4O_DAILY_BUDGET_USD"] = "0.4"
ut.gpt4o_spend_today = lambda: 0.5
check("wlasny budzet $0.4 < wydatek $0.5: blokada", ut.strong_model_allowed() is False)
os.environ.pop("GPT4O_DAILY_BUDGET_USD")

# ---- liczenie wydatku (baza + pamiec) ----
ut.gpt4o_spend_today = real_spend
eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
S = sessionmaker(bind=eng)
import app.database as dbm
dbm.SessionLocal = S
today = date.today().isoformat()
s = S()
s.add(ApiUsageDaily(day=today, label="x", model="gpt-4o-2024-08-06", calls=3, prompt_tokens=1_000_000, completion_tokens=100_000, cached_tokens=0, stream_calls=0))
s.add(ApiUsageDaily(day=today, label="x", model="gpt-4o-mini-2024-07-18", calls=9, prompt_tokens=9_000_000, completion_tokens=900_000, cached_tokens=0, stream_calls=0))
s.add(ApiUsageDaily(day="2000-01-01", label="x", model="gpt-4o-2024-08-06", calls=1, prompt_tokens=9_000_000, completion_tokens=0, cached_tokens=0, stream_calls=0))
s.commit(); s.close()
ut._counters.clear(); ut._counters[(today, "y", "gpt-4o-2024-08-06")] = [1, 200_000, 20_000, 0, 0]
ut._STRONG_CACHE["t"] = 0
v = ut.gpt4o_spend_today()
expected = (1_000_000 * 2.5 + 100_000 * 10) / 1e6 + (200_000 * 2.5 + 20_000 * 10) / 1e6
check(f"wydatek = baza (dzis, tylko gpt-4o, bez mini i starych dni) + pamiec = ${expected:.3f}", abs(v - expected) < 1e-6, v)
ut._counters.clear()

# ---- kod: brak nieosłoniętych eskalacji, generatory pomocnicze na mini ----
src_q = open("app/openai_exam.py", encoding="utf-8").read()
src_e = open("app/exam_pdf_generator.py", encoding="utf-8").read()
check("zadna eskalacja do gpt-4o nie omija limitera (quiz + sprawdzian)", '"gpt-4o" if escalate else None' not in src_q + src_e)
check("4 punkty eskalacji uzywaja _sb.use()", (src_q + src_e).count('escalate and _sb.use()') == 4, (src_q + src_e).count('escalate and _sb.use()'))
bad = []
cur = None
for l in src_q.split("\n"):
    m = re.match(r"\s*(?:async )?def (\w+)\(", l)
    if m: cur = m.group(1)
    if 'model="gpt-4o",' in l and cur and cur.startswith("_raw_generate_safe_"): bad.append(cur)
check("10 generatorow pomocniczych _raw_generate_safe_* dziala na gpt-4o-mini", not bad, bad)

# ---- zachowanie sprawdzianu w rundach ratunkowych (AI zablokowane, czas przyspieszony) ----
from openai.resources.chat.completions import Completions, AsyncCompletions
def _boom(self, *a, **k): raise RuntimeError("AI zablokowane")
async def _aboom(self, *a, **k): raise RuntimeError("AI zablokowane")
Completions.create = _boom; AsyncCompletions.create = _aboom
import app.exam_pdf_generator as eg

ut.gpt4o_spend_today = lambda: 0.0        # budzet nie jest problemem - testujemy limit NA ZAMOWIENIE
MODELS = []
def fake_raw_parallel(self, temat, klasa, trudnosc, total_n, wlasne_instrukcje=None, przedmiot=None, avoid_block="", only_open=False, force_model=None):
    MODELS.append(force_model)
    return {"sekcje": [{"nazwa": "A", "typ": "zamkniete", "pytania": []}, {"nazwa": "B", "typ": "otwarte", "pytania": []}]}   # poprawna struktura, zero pytan -> petla rund ratunkowych trwa
eg.ExamGenerator._get_exam_data_raw_parallel = fake_raw_parallel
eg._max_generation_seconds_exam = lambda *a, **k: 0.0
eg._GRACE_MAX_MISSING_EXAM = 99
clock = {"t": 0.0}
real_monotonic = time.monotonic
def fake_monotonic():
    clock["t"] += 1.0                       # tikajacy zegar; standardowy budzet = 0 s -> od razu rundy 'grace' z eskalacja
    return clock["t"]
time.monotonic = fake_monotonic
try:
    g = eg.ExamGenerator("sk-test")
    g._get_exam_data("Historia: Kongres wiedeński", "liceum_2", "srednia", 10)
finally:
    time.monotonic = real_monotonic
strong = sum(1 for m in MODELS if m == "gpt-4o")
check(f"sprawdzian: rundy ratunkowe wystapily (wywolan AI: {len(MODELS)})", len(MODELS) >= 3, MODELS)
check(f"sprawdzian: gpt-4o uzyty NAJWYZEJ 2 razy na zamowienie (uzyto {strong})", strong <= 2, MODELS)
ut.gpt4o_spend_today = lambda: 9.0        # budzet wyczerpany
MODELS.clear(); clock["t"] = 0.0
time.monotonic = fake_monotonic
try:
    eg.ExamGenerator("sk-test")._get_exam_data("Historia: Kongres wiedeński", "liceum_2", "srednia", 10)
finally:
    time.monotonic = real_monotonic
check("sprawdzian: przy wyczerpanym budzecie dziennym gpt-4o NIE jest uzyty wcale", "gpt-4o" not in MODELS and len(MODELS) >= 3, MODELS)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
