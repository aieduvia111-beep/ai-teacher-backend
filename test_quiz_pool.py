# -*- coding: utf-8 -*-
"""Offline: wspolna pula zweryfikowanych pytan quizu (app/quiz_pool.py)."""
import os, sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
import app.models
import app.database as dbm
import app.quiz_pool as qp
import app.openai_exam as ox

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
dbm.SessionLocal = sessionmaker(bind=eng)

CALLS = []
def make_quiz(n, tag, **extra):
    qs = [{"id": i+1, "question": f"Pytanie {tag} numer {chr(97+i)} o rownaniach {'x'*i}", "options": ["A","B","C","D"], "correct": 0, "explanation": "e"} for i in range(n)]
    q = {"title": "T", "questions": qs}; q.update(extra); return q
NEXT = {"quiz": None, "success": True}
async def fake_gen(**kw):
    CALLS.append(kw)
    if not NEXT["success"]: return {"success": False, "error": "x"}
    return {"success": True, "quiz": NEXT["quiz"]}
ox.generate_quiz_from_topic = fake_gen

def run(topic="Rownania kwadratowe", n=5, use_pool=True, wlasne="", subject="matematyka"):
    return asyncio.run(qp.generate_quiz_pooled(topic, subject, "liceum_1", n, "medium", wlasne, use_pool))

# 1) pusta pula -> AI + zapis
NEXT["quiz"] = make_quiz(5, "A")
r = run(use_pool=True)
check("pusta pula: wola AI", len(CALLS) == 1)
db = dbm.SessionLocal()
check("pytania zapisane do puli (5)", qp.pool_size(db, "matematyka", "Rownania kwadratowe", "medium", "liceum_1") == 5)
# 2) premium tez zasila pule, ale nie czyta
NEXT["quiz"] = make_quiz(5, "B"); run(use_pool=False)
NEXT["quiz"] = make_quiz(5, "C"); run(use_pool=False)
check("premium: zawsze AI (3 wywolania lacznie)", len(CALLS) == 3)
check("pula 15", qp.pool_size(db, "matematyka", "Rownania kwadratowe", "medium", "liceum_1") == 15)
# 3) free z pula >= 15 (3*5) -> bez AI
CALLS.clear()
r = run(use_pool=True)
check("free + pula>=3N: BRAK wywolan AI", len(CALLS) == 0, CALLS)
qs = r["quiz"]["questions"]
check("dokladnie N=5 pytan, ids 1..5", len(qs) == 5 and [q["id"] for q in qs] == [1,2,3,4,5], qs)
check("brak duplikatow w quizie", len({q["question"] for q in qs}) == 5)
# 4) za mala pula na wieksze N -> AI
CALLS.clear(); NEXT["quiz"] = make_quiz(10, "D")
run(n=10, use_pool=True)
check("N=10 przy puli 15 (<30): AI", len(CALLS) == 1)
# 5) wlasne instrukcje / temat ogolny -> nigdy pula, nigdy zapis
CALLS.clear(); before = qp.pool_size(db, "matematyka", "Rownania kwadratowe", "medium", "liceum_1")
NEXT["quiz"] = make_quiz(5, "E"); run(wlasne="tylko trudne", use_pool=True)
check("wlasne instrukcje: AI + brak zapisu", len(CALLS) == 1 and qp.pool_size(db, "matematyka", "Rownania kwadratowe", "medium", "liceum_1") == before)
CALLS.clear(); NEXT["quiz"] = make_quiz(5, "F"); run(topic="Matematyka", use_pool=True)
check("temat ogolny: AI + brak zapisu", len(CALLS) == 1 and qp.pool_size(db, "matematyka", "Matematyka", "medium", "liceum_1") == 0)
# 6) shortfall / obnizona trudnosc -> brak zapisu
NEXT["quiz"] = make_quiz(3, "G", _shortfall_warning="x"); run(topic="Inny temat 1", use_pool=False)
NEXT["quiz"] = make_quiz(3, "H", _difficulty_downgrade_notice="x"); run(topic="Inny temat 2", use_pool=False)
check("quiz z shortfall/downgrade nie zasila puli", qp.pool_size(db, "matematyka", "Inny temat 1", "medium", "liceum_1") == 0 and qp.pool_size(db, "matematyka", "Inny temat 2", "medium", "liceum_1") == 0)
# 7) inny przedmiot / poziom nie miesza
CALLS.clear(); NEXT["quiz"] = make_quiz(5, "I")
run(subject="fizyka", use_pool=True)
check("ten sam temat, inny przedmiot: osobna pula (AI)", len(CALLS) == 1)
# 8) blad AI -> success False, bez zapisu, bez wyjatku
CALLS.clear(); NEXT["success"] = False
r = run(topic="Cos", use_pool=False)
check("blad AI propagowany", r["success"] is False)
NEXT["success"] = True
# 9) rotacja: kolejne zamowienia free zuzywaja rozne pytania (used_count rosnie)
seen = set()
for _ in range(6):
    seen |= {q["question"] for q in run(use_pool=True)["quiz"]["questions"]}
check("rotacja: w 6 zamowieniach widac > 5 roznych pytan", len(seen) > 5, len(seen))
# 10) blad DB przy odczycie -> spada do AI
CALLS.clear(); NEXT["quiz"] = make_quiz(5, "J")
orig = qp.serve_from_pool
qp.serve_from_pool = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))
r = run(use_pool=True)
qp.serve_from_pool = orig
check("awaria puli: fallback do AI, success", r["success"] and len(CALLS) == 1)
db.close()
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
