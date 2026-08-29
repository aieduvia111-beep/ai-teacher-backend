# -*- coding: utf-8 -*-
"""User (29.08.2026, alarm kosztowy w OpenAI - "0.20 USD... jakim
cudem?"): konta premium nie maja ZADNEGO limitu czestotliwosci - nic nie
chronilo przed podwojnym kliknieciem "Generuj" (albo bledem UI), gdzie
DRUGIE zadanie startuje zanim pierwsze sie skonczylo, dublujac PELNY
koszt AI. Dodano prosty, w pamieci procesu bezpiecznik w
require_feature_limit (firebase_auth.py): TYLKO jedno aktywne zadanie
generowania na (user, feature) naraz dla "quiz"/"exam" (najbardziej
kosztowne funkcje) - drugie, jednoczesne zadanie dostaje 429 zamiast po
cichu dublowac koszt.

Ten plik testuje SAMA logike lokalnie - ZERO prawdziwych wywolan
OpenAI/Firebase/bazy danych. FastAPI yield-dependency jest generatorem -
testujemy przez BEZPOSREDNIE sterowanie generatorem (next()/throw()),
dokladnie tak jak robi to sam FastAPI wewnetrznie (setup przed yield,
cleanup w finally PO yield - uruchamiany przy normalnym zakonczeniu ORAZ
przy wyjatku w endpoincie)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


import app.firebase_auth as fa
from fastapi import HTTPException


class FakeUser:
    def __init__(self, id):
        self.id = id


# Bezpiecznik: pomijamy PRAWDZIWY dzienny limit (i baze danych) - testujemy
# WYLACZNIE mechanizm konkurencji, ktory jest niezalezny od tej logiki.
fa.check_and_use_limit = lambda user, db, feature: (True, 999)

print("=" * 70)
print("Scenariusz: DRUGIE, jednoczesne zadanie TEGO SAMEGO usera dla")
print("'exam' (chroniona funkcja) -> natychmiastowy blad 429, NIE cichy")
print("start (symulacja podwojnego kliknieciu 'Generuj')")
print("=" * 70)
dep = fa.require_feature_limit("exam")
user1 = FakeUser(id=42)

gen1 = dep(user=user1, db=None)
yielded1 = next(gen1)
check("Pierwsze zadanie startuje normalnie (yield zwraca usera)", yielded1 is user1)

gen2 = dep(user=user1, db=None)
try:
    next(gen2)
    check("Drugie, jednoczesne zadanie TEGO SAMEGO usera -> HTTPException(429)", False, "nie rzucilo wyjatku")
except HTTPException as e:
    check("Drugie, jednoczesne zadanie TEGO SAMEGO usera -> HTTPException(429)", e.status_code == 429, e.status_code)

# Zakoncz pierwsze zadanie (symuluje normalne zakonczenie endpointu - FastAPI
# wznawia generator PO yield, uruchamiajac blok finally).
try:
    next(gen1)
except StopIteration:
    pass

gen3 = dep(user=user1, db=None)
yielded3 = next(gen3)
check("PO zakonczeniu pierwszego zadania - trzecie zadanie TEGO SAMEGO usera znow dziala (blokada zwolniona)",
      yielded3 is user1)
try:
    next(gen3)
except StopIteration:
    pass

print()
print("=" * 70)
print("Scenariusz: blad/wyjatek W TRAKCIE endpointu (np. timeout AI) -")
print("blokada MUSI sie zwolnic (finally), inaczej user zostaje trwale")
print("zablokowany az do restartu serwera")
print("=" * 70)
gen4 = dep(user=user1, db=None)
next(gen4)
try:
    gen4.throw(RuntimeError("symulowany blad AI w trakcie generowania"))
except RuntimeError:
    pass  # oczekiwane - throw() propaguje wyjatek z powrotem, ale finally JUZ sie wykonal

gen5 = dep(user=user1, db=None)
try:
    yielded5 = next(gen5)
    check("PO wyjatku w poprzednim zadaniu - blokada zwolniona, kolejne zadanie dziala",
          yielded5 is user1)
    try:
        next(gen5)
    except StopIteration:
        pass
except HTTPException:
    check("PO wyjatku w poprzednim zadaniu - blokada zwolniona, kolejne zadanie dziala", False, "wciaz zablokowane")

print()
print("=" * 70)
print("Scenariusz: DWAJ ROZNI userzy moga generowac 'exam' JEDNOCZESNIE")
print("(blokada jest per-user, nie globalna)")
print("=" * 70)
user_a = FakeUser(id=100)
user_b = FakeUser(id=200)
gen_a = dep(user=user_a, db=None)
gen_b = dep(user=user_b, db=None)
try:
    ya = next(gen_a)
    yb = next(gen_b)
    check("Dwaj rozni userzy - OBAJ dostaja dostep jednoczesnie (blokada per-user)",
          ya is user_a and yb is user_b)
except HTTPException as e:
    check("Dwaj rozni userzy - OBAJ dostaja dostep jednoczesnie (blokada per-user)", False, str(e))
for g in (gen_a, gen_b):
    try:
        next(g)
    except StopIteration:
        pass

print()
print("=" * 70)
print("Scenariusz: funkcja NIECHRONIONA (np. 'chat') - BRAK blokady")
print("konkurencji, tylko normalny dzienny limit (jak wczesniej)")
print("=" * 70)
dep_chat = fa.require_feature_limit("chat")
user_c = FakeUser(id=300)
gen_c1 = dep_chat(user=user_c, db=None)
gen_c2 = dep_chat(user=user_c, db=None)
try:
    yc1 = next(gen_c1)
    yc2 = next(gen_c2)
    check("'chat' (niechronione) - DWA jednoczesne zadania TEGO SAMEGO usera OBA przechodza",
          yc1 is user_c and yc2 is user_c)
except HTTPException as e:
    check("'chat' (niechronione) - DWA jednoczesne zadania TEGO SAMEGO usera OBA przechodza", False, str(e))
for g in (gen_c1, gen_c2):
    try:
        next(g)
    except StopIteration:
        pass

print()
print("=" * 70)
print("Regresja: dzienny limit WCIAZ dziala (429 gdy check_and_use_limit")
print("zwroci False) - nowy mechanizm nie zastapil starego, dziala OBOK")
print("=" * 70)
fa.check_and_use_limit = lambda user, db, feature: (False, 0)
dep2 = fa.require_feature_limit("exam")
user_d = FakeUser(id=400)
try:
    gen_d = dep2(user=user_d, db=None)
    next(gen_d)
    check("Wyczerpany dzienny limit -> nadal HTTPException(429)", False, "nie rzucilo wyjatku")
except HTTPException as e:
    check("Wyczerpany dzienny limit -> nadal HTTPException(429)", e.status_code == 429, e.status_code)

print()
print("=" * 70)
print("Scenariusz: RATE LIMIT (nie wspolbieznosc - kazde zadanie konczy sie")
print("PRZED nastepnym) - max _RATE_LIMIT_MAX_PER_WINDOW zadan w oknie,")
print("kolejne dostaje 429 (chroni konta premium bez dziennego limitu przed")
print("nieograniczonym powtarzaniem SEKWENCYJNYM, ktorego blokada")
print("wspolbieznosci NIE lapie)")
print("=" * 70)
fa.check_and_use_limit = lambda user, db, feature: (True, 999)


class FakeClock:
    def __init__(self, start=0.0):
        self.t = start

    def monotonic(self):
        return self.t

    def advance(self, s):
        self.t += s


rl_clock = FakeClock(start=0.0)
fa.time.monotonic = rl_clock.monotonic
fa._rate_limit_history.clear()
dep_rl = fa.require_feature_limit("exam")
user_rl = FakeUser(id=500)

ok_count = 0
for i in range(fa._RATE_LIMIT_MAX_PER_WINDOW):
    g = dep_rl(user=user_rl, db=None)
    next(g)
    ok_count += 1
    try:
        next(g)
    except StopIteration:
        pass
    rl_clock.advance(1.0)  # sekwencyjne, NIE jednoczesne zadania
check(f"Pierwsze {fa._RATE_LIMIT_MAX_PER_WINDOW} sekwencyjnych zadan w oknie - wszystkie przechodza",
      ok_count == fa._RATE_LIMIT_MAX_PER_WINDOW, ok_count)

g_over = dep_rl(user=user_rl, db=None)
try:
    next(g_over)
    check(f"Zadanie nr {fa._RATE_LIMIT_MAX_PER_WINDOW + 1} w tym samym oknie -> HTTPException(429)", False, "nie rzucilo")
except HTTPException as e:
    check(f"Zadanie nr {fa._RATE_LIMIT_MAX_PER_WINDOW + 1} w tym samym oknie -> HTTPException(429)",
          e.status_code == 429, e.status_code)

print()
print("=" * 70)
print("Scenariusz: PO uplynieciu okna (_RATE_LIMIT_WINDOW_SECONDS) limit")
print("sie odswieza - user NIE jest zablokowany na zawsze")
print("=" * 70)
rl_clock.advance(fa._RATE_LIMIT_WINDOW_SECONDS + 1)
g_after_window = dep_rl(user=user_rl, db=None)
try:
    y = next(g_after_window)
    check("Po uplynieciu okna - kolejne zadanie znow dziala", y is user_rl)
    try:
        next(g_after_window)
    except StopIteration:
        pass
except HTTPException as e:
    check("Po uplynieciu okna - kolejne zadanie znow dziala", False, str(e))

print()
print("=" * 70)
print("Scenariusz: rate limit jest PER (user, feature) - inny user LUB inna")
print("funkcja ma WLASNE, niezalezne okno")
print("=" * 70)
fa._rate_limit_history.clear()
rl_clock.t = 0.0
user_other = FakeUser(id=600)
# Wyczerpujemy limit dla user_rl na "exam"
for i in range(fa._RATE_LIMIT_MAX_PER_WINDOW):
    g = dep_rl(user=user_rl, db=None)
    next(g)
    try:
        next(g)
    except StopIteration:
        pass
try:
    g_other_user = dep_rl(user=user_other, db=None)
    y = next(g_other_user)
    check("Inny user (rozne id) - WLASNE okno, nie zablokowany limitem user_rl", y is user_other)
    try:
        next(g_other_user)
    except StopIteration:
        pass
except HTTPException as e:
    check("Inny user (rozne id) - WLASNE okno, nie zablokowany limitem user_rl", False, str(e))

try:
    g_other_feature = fa.require_feature_limit("quiz")(user=user_rl, db=None)
    y = next(g_other_feature)
    check("Ta sama osoba, INNA funkcja ('quiz' zamiast 'exam') - WLASNE okno",
          y is user_rl)
    try:
        next(g_other_feature)
    except StopIteration:
        pass
except HTTPException as e:
    check("Ta sama osoba, INNA funkcja ('quiz' zamiast 'exam') - WLASNE okno", False, str(e))

fa.time.monotonic = __import__("time").monotonic  # przywroc prawdziwy zegar
fa._rate_limit_history.clear()

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
