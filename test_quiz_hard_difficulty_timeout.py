# -*- coding: utf-8 -*-
"""User real-test (Quiz, ciagi geometryczne, liceum_3, TRUDNY, n=6)
odtworzyl zgloszony bug 1:1: 5/6 pytan, "przekroczono limit czasu
(30s)". Log pokazal PRAWDZIWA przyczyne: samo PIERWSZE, surowe
wywolanie AI zajelo 35.3s - wiecej niz caly budzet 30s - wiec petla
dogenerowania nie dostala ani jednej szansy (retry_count=0). To NIE
byl blad dzisiejszych 3 naprawien Sprawdzianu z ciagow (verify_
geometric_power_form_ratio/max_tokens/"n$") - to zupelnie inny
mechanizm: budzet czasowy Quizu (30s) nie liczyl sie w ogole z tym,
ze "trudny" = AI odpowiada wolniej (dluzsze rozumowanie, wiecej
tokenow), niezaleznie od tematu.

User (po pokazaniu real-testu i zapytaniu o zakres naprawy) zdecydowal:
rozszerz na KAZDY temat na poziomie "trudny"/"hard" (nie tylko ciagi) -
budzet 60s (ta sama wartosc, ktora user juz zaakceptowal jako budzet
Sprawdzianu tego samego dnia) + bufor +40% zamiast domyslnych +30%.

ZWIEKSZONE (29.08.2026, patrz komentarz nad _HARD_TIMEOUT_SECONDS w
openai_exam.py): 60s bylo ustalone PRZED Warstwa 2.5 dzialala poprawnie
w kazdej rundzie dogenerowania Sprawdzianu (byla buga, po cichu
pomijana) - po naprawie tego buga kazda runda robi DWA realne wywolania
AI zamiast jednego, wiec real-test trudnej trygonometrii pokazal 80s i
nadal niepelny wynik. User potwierdzil podniesienie do 120s dla
"trudny"/"hard" (Quiz i Sprawdzian identycznie) - testy ponizej
zaktualizowane do nowej wartosci.

Testy ponizej sa JEDNOSTKOWE (zero AI)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.openai_exam import _max_generation_seconds, _buffered_count, _HARD_TIMEOUT_SECONDS

# Dokladny zgloszony przypadek: ciagi geometryczne (NIE kwadratowe), trudny
r = _max_generation_seconds(topic="Matematyka: ciągi geometryczne", difficulty="trudny")
check("ciagi geometryczne + trudny -> 120s (nie 30s jak wczesniej)", r == 120.0, r)

r2 = _buffered_count(6, topic="Matematyka: ciągi geometryczne", difficulty="trudny")
check("bufor dla ciagi+trudny: +40% (6 -> 9, nie 6->8 jak wczesniej)", r2 == 9, r2)

# Regresja: rownania kwadratowe + medium (istniejacy, waski wyjatek) - BEZ ZMIAN
r3 = _max_generation_seconds(topic="Matematyka: równania kwadratowe z parametrem", difficulty="medium")
check("Regresja: rownania kwadratowe+medium nadal 45s (niezmienione)", r3 == 45.0, r3)

# Regresja: latwy/domyslny temat - BEZ ZMIAN
r4 = _max_generation_seconds(topic="Matematyka: funkcje liniowe", difficulty="easy")
check("Regresja: temat inny + latwy -> nadal 30s", r4 == 30.0, r4)

r5 = _buffered_count(10, topic="Matematyka: funkcje liniowe", difficulty="easy")
check("Regresja: bufor dla latwy/domyslny -> nadal +30% (10 -> 13)", r5 == 13, r5)

# NOWE: dowolny inny temat + trudny -> tez 60s (generalizacja, nie tylko ciagi)
r6 = _max_generation_seconds(topic="Matematyka: trygonometria", difficulty="trudny")
check("NOWE: dowolny inny temat + trudny -> tez 120s (generalizacja)", r6 == 120.0, r6)

# Boczny efekt (POPRAWA, nie regresja): rownania kwadratowe + hard - wczesniej
# 30s (luka, nigdy nie mialo wlasnego wyjatku w _max_generation_seconds,
# mimo najwiekszego bufora +60% w _buffered_count) - teraz tez 120s.
r7 = _max_generation_seconds(topic="Matematyka: równania kwadratowe z parametrem", difficulty="trudny")
check("Efekt uboczny (poprawa): rownania kwadratowe+hard teraz tez 120s (wczesniej luka: 30s)", r7 == 120.0, r7)

print()
print("=" * 70)
print("Stale (30s) w komunikacie shortfallu Quizu - identyczny blad jak")
print("naprawiony wczesniej w Sprawdzianie")
print("=" * 70)
with open(r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend\app\openai_exam.py", encoding="utf-8") as f:
    src = f.read()
check("brak zaszytego na stale '(30s)' w komunikacie shortfallu Quizu",
      '"przekroczono limit czasu (30s)"' not in src, None)
check("komunikat shortfallu Quizu uzywa PRAWDZIWEJ wartosci max_seconds",
      'f"przekroczono limit czasu ({max_seconds' in src, None)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
