# -*- coding: utf-8 -*-
"""NAPRAWA (decyzja usera po pelnej, udokumentowanej analizie - NIE
ciche/globalne podniesienie limitu): rownania kwadratowe z parametrem
na poziomie MEDIUM maja potwierdzony realnymi testami wysoki i
uporczywy wskaznik odrzucen (sympy_mismatch), przez co nawet po
zwiekszonym buforze (+50%, patrz f9f82ac) i rownoleglych wywolaniach
(patrz 8eb5fb4) pojedyncza partia czasem potrzebuje jednej dodatkowej
rundy dogenerowania, ktora nie miesci sie w standardowych 30s. Dla
TEGO JEDNEGO, znanego przypadku budzet jest JAWNIE 45s - wszystko inne
zostaje przy 30s bez zmian."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.openai_exam import _max_generation_seconds

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("_max_generation_seconds - wyjatek TYLKO dla znanego przypadku")
print("=" * 70)

r = _max_generation_seconds("Rownania kwadratowe", "medium")
check("rownania kwadratowe + medium -> 45s (WYJATEK)", r == 45.0, r)

r = _max_generation_seconds("Równania kwadratowe z parametrem", "sredni")
check("polska odmiana 'sredni' + rownania kwadratowe -> 45s", r == 45.0, r)

for topic, diff in [
    ("Rownania kwadratowe", "hard"),
    ("Rownania kwadratowe", "easy"),
    ("Rownania kwadratowe", None),
    ("Trygonometria", "medium"),
    ("Ciagi arytmetyczne", "medium"),
    ("Prawdopodobienstwo", "medium"),
    (None, "medium"),
    (None, None),
]:
    r = _max_generation_seconds(topic, diff)
    check(f"topic={topic!r} difficulty={diff!r} -> 30s (bez zmian)", r == 30.0, r)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
