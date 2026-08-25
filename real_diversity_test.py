# -*- coding: utf-8 -*-
"""Universal Diversity Engine - Krok 4: real end-to-end test (n=20,
rownania kwadratowe, medium - ten sam scenariusz uzywany caly dzien,
wiec bezposrednie porownanie przed/po). Mierzy: N==N, czas, ORAZ
roznorodnosc schematow w finalnym quizie (grupowanie po polu "concept"
diversity_tag, plus niezalezna kontrola przez skeleton tresci pytania -
ta sama metoda co real_generation_audit.py wczesniej dzisiaj)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import asyncio
import time
import collections
import re as re_mod
from app.openai_exam import generate_quiz_from_topic


def _skeleton_only(text):
    t = (text or "").lower()
    t = re_mod.sub(r'-?\d+(?:[.,]\d+)?', '#', t)
    t = re_mod.sub(r'\$[^$]*\$', '§', t)
    t = re_mod.sub(r'[^a-ząćęłńóśźż#§]+', ' ', t)
    return ' '.join(t.split())


async def main():
    t0 = time.time()
    result = await generate_quiz_from_topic(
        topic="Rownania kwadratowe", subject="matematyka", level="liceum_3",
        num_questions=20, difficulty="medium",
    )
    elapsed = time.time() - t0
    if not result["success"]:
        print("ERROR:", result.get("error"))
        return

    qs = result["quiz"]["questions"]
    print("=" * 70)
    print(f"WYNIK: {len(qs)}/20 pytan w {elapsed:.1f}s")
    print("=" * 70)

    concept_counts = collections.Counter()
    skeleton_counts = collections.Counter()
    for q in qs:
        tag = q.get("diversity_tag")
        concept = tag.get("concept") if isinstance(tag, dict) else "(brak tagu)"
        concept_counts[concept] += 1
        skeleton_counts[_skeleton_only(q.get("question", ""))] += 1

    print("\nRozklad wg pola 'concept' (diversity_tag) w FINALNYM quizie:")
    for concept, count in concept_counts.most_common():
        print(f"  {count}x  {concept}")

    print("\nRozklad wg szkieletu tresci pytania (niezalezna kontrola, ta sama metoda co real_generation_audit.py):")
    same_schema_groups = {k: c for k, c in skeleton_counts.items() if c > 1}
    for skel, count in skeleton_counts.most_common():
        marker = " <-- POWTORZONY SCHEMAT" if count > 1 else ""
        print(f"  {count}x  {skel[:80]}{marker}")

    print(f"\nMax powtorzen jednego 'concept': {concept_counts.most_common(1)[0][1] if concept_counts else 0}")
    print(f"Liczba grup powtorzonego szkieletu tresci: {len(same_schema_groups)}")
    print(f"Pytania bez diversity_tag: {concept_counts.get('(brak tagu)', 0)}")


if __name__ == "__main__":
    asyncio.run(main())
