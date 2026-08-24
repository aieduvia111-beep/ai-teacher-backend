# -*- coding: utf-8 -*-
"""NAPRAWA (znaleziony problem czasowy dla duzych partii, sierpien
2026): jedno sekwencyjne wywolanie AI generujace ~26 pytan naraz
trwalo 35-45s samo w sobie, zjadajac caly globalny budzet 30s zanim
petla dogenerowania zdazyla zadzialac choc raz (realny test: 12/20
trygonometria w 65s, 18/20 rownania kwadratowe w 47s). Naprawiono:
_raw_generate_quiz_topic_batch dzieli wieksze partie na kilka
mniejszych, ROWNOLEGLYCH wywolan (ta sama laczna liczba pytan/kosztu,
krotszy czas zegarowy = czas najwolniejszego wywolania, nie suma).

Przy WDRAZANIU znaleziono NOWY problem: rownolegle wywolania bez
zadnej wskazowki roznorodnosci daly 17/34 duplikatow w realnym tescie
(obie partie "zgodnie" wybraly te same "typowe" przyklady) - naprawiono
przez _chunk_diversity_hint (rozlaczne pule liter parametrow/zakresy
stalych per-partia), zweryfikowane realnym retestem: 0 duplikatow."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.openai_exam import _parallel_batch_sizes, _chunk_diversity_hint, _CHUNK_LETTER_POOLS

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("_parallel_batch_sizes")
print("=" * 70)

check("total=4 (<=target_chunk) -> [4], bez podzialu", _parallel_batch_sizes(4) == [4], _parallel_batch_sizes(4))
check("total=13 (=target_chunk) -> [13], bez podzialu", _parallel_batch_sizes(13) == [13], _parallel_batch_sizes(13))
check("total=1 -> [1], bez podzialu", _parallel_batch_sizes(1) == [1], _parallel_batch_sizes(1))

r26 = _parallel_batch_sizes(26)
check("total=26 -> 2 rownolegle czesci", len(r26) == 2, r26)
check("total=26 -> suma czesci = 26 (nic nie ginie)", sum(r26) == 26, r26)

r40 = _parallel_batch_sizes(40)
check("total=40 -> capped na max_chunks=3", len(r40) == 3, r40)
check("total=40 -> suma czesci = 40 (nic nie ginie)", sum(r40) == 40, r40)

r100 = _parallel_batch_sizes(100)
check("total=100 -> nadal capped na 3 (nie eksploduje liczba requestow)", len(r100) == 3, r100)
check("total=100 -> suma czesci = 100 (nic nie ginie)", sum(r100) == 100, r100)

for n in range(1, 61):
    parts = _parallel_batch_sizes(n)
    if sum(parts) != n:
        FAILED.append((f"suma czesci != total dla n={n}", parts))
    if len(parts) > 3:
        FAILED.append((f"za duzo rownoleglych czesci dla n={n}", parts))
print("  OK   suma czesci == total dla wszystkich n=1..60, max 3 czesci (brak FAILED wpisow powyzej = OK)")

print()
print("=" * 70)
print("_chunk_diversity_hint")
print("=" * 70)

check("n_chunks<=1 -> pusty string (brak zmiany zachowania dla pojedynczego wywolania)",
      _chunk_diversity_hint(0, 1) == "", _chunk_diversity_hint(0, 1))

hints = [_chunk_diversity_hint(i, 3) for i in range(3)]
check("3 rownolegle czesci -> 3 NIEPUSTE, ROZNE wskazowki", all(hints) and len(set(hints)) == 3, hints)
check(f"liczba pul liter >= max_chunks (3)", len(_CHUNK_LETTER_POOLS) >= 3, _CHUNK_LETTER_POOLS)

for i, h in enumerate(hints):
    pool = _CHUNK_LETTER_POOLS[i % len(_CHUNK_LETTER_POOLS)]
    check(f"czesc {i}: wskazowka zawiera WLASNA pule liter", pool in h, h)

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
