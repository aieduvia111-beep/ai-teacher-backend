# -*- coding: utf-8 -*-
"""Offline (zero AI, zero DB): obnizone limity darmowego planu (22.09.2026, KOSZTY - 1313 darmowych kont
vs 11 platnych generuja wiekszosc kosztu API) - nowe wartosci, spojnosc komunikatow z liczbami, dzialanie
check_and_use_limit/get_remaining, i spojnosc z 8 kopiami LIMITS_FREE we frontendzie."""
import os, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from app.usage_limits import FREE_DAILY_LIMITS, LIMIT_MESSAGES, check_and_use_limit, get_remaining

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

EXPECTED = {"chat": 4, "quiz": 2, "notes": 1, "exam": 1, "lesson": 1, "vision": 1, "voice": 2, "flashcards": 1}
for k, v in EXPECTED.items():
    check(f"FREE_DAILY_LIMITS['{k}'] == {v}", FREE_DAILY_LIMITS.get(k) == v, FREE_DAILY_LIMITS.get(k))

for k, v in EXPECTED.items():
    msg = LIMIT_MESSAGES.get(k, "")
    check(f"komunikat '{k}' wspomina liczbe {v}", re.search(rf"\b{v}\b", msg) is not None, msg)

# ---- check_and_use_limit / get_remaining z nowymi wartosciami (bez bazy - prosty obiekt User) ----
class FakeUser:
    def __init__(self, premium=False):
        self.is_premium = premium
        self.daily_usage = None

class FakeDB:
    def commit(self): pass

u = FakeUser()
db = FakeDB()
results = [check_and_use_limit(u, db, "quiz")[0] for _ in range(3)]
check("quiz: limit 2 -> [True, True, False]", results == [True, True, False], results)
rem = get_remaining(u, "quiz")
check("get_remaining po wyczerpaniu: used=2, limit=2, remaining=0", rem == {"is_premium": False, "unlimited": False, "used": 2, "limit": 2, "remaining": 0}, rem)

u2 = FakeUser()
check("exam: limit 1 -> [True, False]", [check_and_use_limit(u2, db, "exam")[0] for _ in range(2)] == [True, False])

u3 = FakeUser(premium=True)
check("premium: bez limitu (5x True)", all(check_and_use_limit(u3, db, "quiz")[0] for _ in range(5)))
check("premium get_remaining: unlimited", get_remaining(u3, "quiz") == {"is_premium": True, "unlimited": True})

# ---- spojnosc z frontendem: 8 kopii LIMITS_FREE w static/*.html musza miec TE SAME liczby co backend ----
FRONTEND_FILES = ["chat.html", "dashboard_FINAL.html", "voice_conversation.html", "vision.html",
                   "quiz_app.html", "notes_generator.html", "lesson_planner.html", "exam_generator.html"]
for fn in FRONTEND_FILES:
    src = open(f"static/{fn}", encoding="utf-8").read()
    m = re.search(r"const LIMITS_FREE = \{(.*?)\n\};", src, re.S)
    if not m:
        check(f"{fn}: znaleziono blok LIMITS_FREE", False, "brak dopasowania")
        continue
    block = m.group(1)
    mismatches = []
    for key, val in EXPECTED.items():
        fm = re.search(rf"\b{key}:\s*(\d+)", block)
        if fm and int(fm.group(1)) != val:
            mismatches.append((key, int(fm.group(1)), val))
    check(f"{fn}: LIMITS_FREE zgodne z backendem", not mismatches, mismatches)

# ---- marketingowe strony (pricing.html, eduvia-final.html, terms.html) nie maja starych liczb ----
for fn, olds in (
    ("static/pricing.html", ["5 wiadomości dziennie", "3 quizy dziennie", "2 analizy dziennie", "2 zestawy dziennie", "2 notatki dziennie", "2 plany dziennie"]),
    ("static/eduvia-final.html", ["5 rozmow dziennie", "3 quizy dziennie", "2 analizy dziennie", "2 zestawy dziennie", "2 notatki dziennie", "2 plany dziennie"]),
    ("static/terms.html", ["Chat AI (5 wiadomości)", "Quiz AI (3 quizy)", "Notatki AI (2 notatki)", "Plan Nauki (2 plany)"]),
):
    src = open(fn, encoding="utf-8").read()
    stale = [o for o in olds if o in src]
    check(f"{fn}: brak starych liczb limitow", not stale, stale)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
