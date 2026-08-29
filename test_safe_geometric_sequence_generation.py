# -*- coding: utf-8 -*-
"""User (29.08.2026, "robimy, bezpiecznie" - czwarte rozszerzenie tego
samego dnia, po trygonometrii/ciagach arytmetycznych/twierdzeniu
cosinusow). Port ciagow arytmetycznych na geometryczne - ale NIE
kopiuj-wklej: ciag geometryczny (a_m=a1*q^(n-1)) jest NIELINIOWY -
odwrocenie (wyznaczenie q z dwoch wyrazow) wymaga pierwiastka
$q=\\sqrt[n-m]{{a_n/a_m}}$, ktory dla UJEMNEGO q i PARZYSTEGO (n-m) ma
DWA rozwiazania rzeczywiste (q i -q, bo q^(n-m) jest wtedy dodatnie dla
obu) - z SAMYCH a_m,a_n nie da sie jednoznacznie odzyskac znaku q,
zadanie mialoby DWIE poprawne odpowiedzi. Naprawiono u ZRODLA (q zawsze
dodatnie, z malej puli {{2,3}}), nie jako pozniejsza lata - ten plik
testuje TO WPROST (rozne m,n, parzyste i nieparzyste roznice)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.math_verify import build_safe_geometric_sequence_two_terms, verify_geometric_sequence_two_terms

print("=" * 70)
print("Real przyklad (analogiczny do oficjalnego dla ciagow arytmetycznych)")
print("=" * 70)
sk = build_safe_geometric_sequence_two_terms(a1=3, q=2, m=2, n=5)
check("a1=3, q=2, m=2, n=5 -> a_2=6, a_5=48",
      sk["a_m_val"] == 6 and sk["a_n_val"] == 48, sk)
check("Poprawna odpowiedz: a_1 = 3, q = 2", sk["correct_text"] == "a_1 = 3, q = 2", sk["correct_text"])

print()
print("=" * 70)
print("Poprawnosc na 500 losowych probach (niezalezna sciezka)")
print("=" * 70)
bad = [sk for sk in (build_safe_geometric_sequence_two_terms() for _ in range(500))
       if not verify_geometric_sequence_two_terms(sk["a1"], sk["q"], sk["m"], sk["n"], sk["a_m_val"], sk["a_n_val"])]
check("500/500 poprawne", not bad, bad[:3] if bad else None)

print()
print("=" * 70)
print("Dystraktory - zero kolizji na 500 probach")
print("=" * 70)
collision = []
for _ in range(500):
    sk = build_safe_geometric_sequence_two_terms()
    all_texts = [sk["correct_text"]] + sk["distractors"]
    if sk["correct_text"] in sk["distractors"] or len(set(all_texts)) != 4:
        collision.append(sk)
check("500 prob - zero kolizji", not collision, collision[:3] if collision else None)

print()
print("=" * 70)
print("q ZAWSZE dodatnie (bezpieczenstwo przed niejednoznacznoscia znaku)")
print("=" * 70)
always_positive = all(build_safe_geometric_sequence_two_terms()["q"] > 0 for _ in range(300))
check("300 prob - q zawsze > 0 (nigdy ujemne)", always_positive)

print()
print("=" * 70)
print("Gating: _is_hard_geometric_sequence (Quiz) - TYLKO geometryczne (NIE arytmetyczne)")
print("=" * 70)
from app.openai_exam import _is_hard_geometric_sequence
check("ciagi geometryczne + trudny -> True",
      _is_hard_geometric_sequence("Matematyka: ciągi geometryczne", "trudny") is True)
check("ciagi geometryczne + srednia -> False",
      _is_hard_geometric_sequence("ciągi geometryczne", "srednia") is False)
check("ciagi ARYTMETYCZNE + trudny -> False (lustrzany warunek, inny archetyp)",
      _is_hard_geometric_sequence("ciągi arytmetyczne", "trudny") is False)
check("temat z OBOMA rodzajami -> False (bezpieczny abstain)",
      _is_hard_geometric_sequence("ciągi arytmetyczne i geometryczne", "trudny") is False)

print()
print("=" * 70)
print("Gating: _is_hard_geometric_sequence_exam (Sprawdzian) - identyczna logika")
print("=" * 70)
from app.exam_pdf_generator import _is_hard_geometric_sequence_exam
check("ciagi geometryczne + trudna -> True",
      _is_hard_geometric_sequence_exam("Matematyka: ciągi geometryczne", "trudna") is True)
check("ciagi arytmetyczne + trudna -> False",
      _is_hard_geometric_sequence_exam("ciągi arytmetyczne", "trudna") is False)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
