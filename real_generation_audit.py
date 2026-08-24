# -*- coding: utf-8 -*-
"""AUDYT REALNEJ GENERACJI (V1, obecna architektura) - wywoluje
PRAWDZIWY pipeline produkcyjny (generate_quiz_from_topic -> AI ->
Warstwa 1/2/3 -> dedup -> shuffle) dla kilku ROZNYCH przedmiotow i
tematow (nie tylko rownania kwadratowe), na poziomie Medium, i
sprawdza 7 kryteriow zadanych przez uzytkownika:

  1. N==N (dostal dokladnie tyle pytan ile zamowiono)
  2. Czy correct/final_answer sa spojne (korekta Warstwy 1 sie zgadza)
  3. Czy "correct" wskazuje na TA SAMA opcje co "final_answer" (end-to-end)
  4. Rozklad A/B/C/D w obrebie kazdego quizu
  5. Brak duplikatow (dokladnych ORAZ strukturalnie bardzo podobnych -
     ten sam szkielet slowny z innymi liczbami/parametrem - TO WLASNIE
     zgloszony problem "10 pytan tym samym schematem")
  6. Czy zgloszona trudnosc (difficulty) wyglada spojnie (manualny
     przeglad probki + dla tematow z Warstwa 3 - automatyczna zgodnosc)
  7. Czas generowania

Real API calls - kosztuje i zajmuje czas, ale to jest cel tego
zadania (test na roznych przedmiotach/tematach, nie lokalna symulacja)."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import asyncio
import time
import collections
import re as re_mod
import json

from app.openai_exam import generate_quiz_from_topic, _question_fingerprint

SCENARIOS = [
    {"label": "Matematyka / Rownania kwadratowe (kontrola)", "topic": "Rownania kwadratowe", "subject": "matematyka", "level": "liceum_3", "n": 20, "difficulty": "medium"},
    {"label": "Matematyka / Trygonometria (Etap 7)", "topic": "Trygonometria - funkcje trygonometryczne", "subject": "matematyka", "level": "liceum_2", "n": 20, "difficulty": "medium"},
    {"label": "Matematyka / Prawdopodobienstwo (waska Warstwa 2)", "topic": "Prawdopodobienstwo klasyczne", "subject": "matematyka", "level": "liceum_3", "n": 12, "difficulty": "medium"},
    {"label": "Biologia (brak Warstwy 2/3 - tylko Warstwa 1)", "topic": "Budowa komorki", "subject": "biologia", "level": "liceum_1", "n": 12, "difficulty": "medium"},
]


def _skeleton_only(text):
    """Luzniejszy szkielet niz _question_fingerprint - IGNORUJE liczby
    calkowicie (nie tylko normalizuje), zeby wykryc TEN SAM SCHEMAT z
    innymi parametrami/liczbami (zgloszony problem), nie tylko
    identyczne duplikaty."""
    t = (text or "").lower()
    t = re_mod.sub(r'-?\d+(?:[.,]\d+)?', '#', t)
    t = re_mod.sub(r'\$[^$]*\$', '§', t)  # cale wzory LaTeX -> jeden placeholder
    t = re_mod.sub(r'[^a-ząćęłńóśźż#§]+', ' ', t)
    return ' '.join(t.split())


def analyze_quiz(scenario, quiz, elapsed):
    questions = quiz.get("questions", [])
    n_req = scenario["n"]
    n_got = len(questions)

    report = {"label": scenario["label"], "requested": n_req, "got": n_got, "elapsed": elapsed}

    # 2+3: correct <-> final_answer spojnosc
    mismatches = []
    for q in questions:
        opts = q.get("options", [])
        correct = q.get("correct")
        fa = q.get("final_answer")
        if not isinstance(correct, int) or not (0 <= correct < len(opts)):
            mismatches.append((q.get("id"), "correct poza zakresem", correct))
            continue
        if fa is not None and str(opts[correct]).strip() != str(fa).strip():
            mismatches.append((q.get("id"), "correct != final_answer po przeliczeniu", (opts[correct], fa)))
    report["correct_fa_mismatches"] = mismatches

    # 4: rozklad ABCD
    dist = collections.Counter(q.get("correct") for q in questions)
    report["abcd_distribution"] = {("ABCD"[k] if isinstance(k, int) and 0 <= k < 4 else str(k)): v for k, v in dist.items()}

    # 5: duplikaty (dokladne + strukturalne "ten sam schemat")
    exact_fp = collections.Counter(_question_fingerprint(q.get("question", "")) for q in questions)
    exact_dups = sum(c - 1 for c in exact_fp.values() if c > 1)
    skeleton_only = collections.Counter(_skeleton_only(q.get("question", "")) for q in questions)
    same_schema_groups = {k: c for k, c in skeleton_only.items() if c > 1}
    report["exact_duplicates"] = exact_dups
    report["same_schema_groups"] = same_schema_groups  # >1 pytanie o TYM SAMYM szkielecie slownym

    # zapisz probke pytan do manualnego przegladu trudnosci (kryterium 6)
    report["sample_questions"] = [
        {"question": q.get("question"), "options": q.get("options"), "correct": q.get("correct"), "final_answer": q.get("final_answer")}
        for q in questions[:5]
    ]
    report["all_questions_brief"] = [q.get("question", "")[:100] for q in questions]

    return report


async def run_all():
    results = []
    for scenario in SCENARIOS:
        print("=" * 78)
        print(f"URUCHAMIAM: {scenario['label']} (n={scenario['n']}, difficulty={scenario['difficulty']})")
        print("=" * 78)
        t0 = time.time()
        try:
            result = await generate_quiz_from_topic(
                topic=scenario["topic"], subject=scenario["subject"], level=scenario["level"],
                num_questions=scenario["n"], difficulty=scenario["difficulty"],
            )
        except Exception as e:
            print(f"BLAD KRYTYCZNY (wyjatek): {e}")
            results.append({"label": scenario["label"], "error": str(e)})
            continue
        elapsed = time.time() - t0
        if not result.get("success"):
            print(f"BLAD: {result.get('error')}")
            results.append({"label": scenario["label"], "error": result.get("error")})
            continue
        quiz = result["quiz"]
        report = analyze_quiz(scenario, quiz, elapsed)
        results.append(report)
        print(f"-> {report['got']}/{report['requested']} pytan w {elapsed:.1f}s")
        print(f"-> rozklad ABCD: {report['abcd_distribution']}")
        print(f"-> duplikaty dokladne: {report['exact_duplicates']}")
        print(f"-> grupy 'ten sam schemat': {len(report['same_schema_groups'])}")
        if report["correct_fa_mismatches"]:
            print(f"-> !!! NIESPOJNOSC correct/final_answer: {report['correct_fa_mismatches']}")

    out_path = r"C:\Users\MI3\AppData\Local\Temp\claude\C--Users-MI3-Desktop-eduvia-projekty\2628af18-cf29-4d72-a412-5c124ef34312\scratchpad\real_generation_audit_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n\nWYNIKI ZAPISANE:", out_path)
    return results


if __name__ == "__main__":
    asyncio.run(run_all())
