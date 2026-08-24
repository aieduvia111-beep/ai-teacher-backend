# -*- coding: utf-8 -*-
"""LOKALNA symulacja generowania 20 pytan matematycznych (rownania
kwadratowe z parametrem, poziom 'trudny' - najbardziej podatny na
odrzucenia). ZERO wywolan prawdziwego API - `regenerate` jest w pelni
mockowany i generuje syntetyczne pytania lokalnie, z celowo wbudowanym
realistycznym rozkladem bledow AI (zeby przetestowac PRAWDZIWY
mechanizm retry/fill, dedup i odrzucen), naśladujac typowe bledy
zgloszone w tej sesji: bledny final_answer (nie ma go wsrod opcji),
brak poprawnej opcji wsrod 4, oraz sporadyczne duplikaty tresci."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
import asyncio
import random
import time
import collections

from app.openai_exam import _verify_and_fill_quiz_math

random.seed(42)

_counter = {"n": 0}


def _make_question(force_duplicate_of=None, force_bad=False):
    """Tworzy jedno syntetyczne pytanie o rownaniu kwadratowym z
    parametrem. Domyslnie POPRAWNE (final_answer = prawdziwa wartosc).
    force_bad=True: final_answer wskazuje na BLEDNA (nieobecna wsrod
    opcji) odpowiedz - symuluje typowy blad AI zgloszony w tej sesji.
    force_duplicate_of: zwraca DOKLADNA kopie podanego pytania (test
    mechanizmu dedup)."""
    if force_duplicate_of is not None:
        import copy
        return copy.deepcopy(force_duplicate_of)

    _counter["n"] += 1
    n = _counter["n"]
    c_val = 5 + (n % 7)
    param_letter = "mnpqrst"[n % 7]
    true_bound = (c_val ** 2) / 4
    q = {
        "question": (
            f"Dla jakich wartości parametru {param_letter} równanie "
            f"$x^2 - {c_val}x + ({param_letter}-{n}) = 0$ ma dwa różne pierwiastki?"
        ),
        "options": [
            f"{param_letter}<{true_bound + n}",
            f"{param_letter}>{true_bound + n}",
            f"{param_letter}={true_bound + n}",
            f"{param_letter}<0",
        ],
        "correct": 99,
    }
    if force_bad:
        # AI "myli sie" i podaje final_answer, ktorej NIE MA wsrod opcji
        # (typowy realny blad zgloszony w tej sesji - odpowiedz spoza opcji)
        q["final_answer"] = f"{param_letter}>{true_bound + n + 100}"
    else:
        q["options"][0] = f"{param_letter}<{true_bound + n}"
        q["final_answer"] = f"{param_letter}<{true_bound + n}"
    return q


async def mock_regenerate(n):
    """Symuluje AI generujace `n` nowych pytan. Realistyczny rozklad:
    ~15% z bledna odpowiedzia (do odrzucenia przez Warstwe 2), reszta
    poprawna. Zero wywolan sieciowych/API - czysto lokalna funkcja."""
    await asyncio.sleep(0)  # symuluje async bez realnego opoznienia sieciowego
    out = []
    for _ in range(n):
        bad = random.random() < 0.15
        out.append(_make_question(force_bad=bad))
    return {"questions": out}


async def run_simulation(requested=20):
    # Pierwsza "partia" (symuluje pierwsze wywolanie generacji przez AI):
    # 20 pytan, z czego ~15% ma bledna final_answer, plus JEDEN swiadomy
    # duplikat (pytanie #3 powielone jako #4), zeby przetestowac dedup.
    first_batch = []
    for _ in range(requested):
        bad = random.random() < 0.15
        first_batch.append(_make_question(force_bad=bad))
    # wstrzykujemy jawny duplikat (kopia pytania #2) na pozycji ostatniej
    first_batch[-1] = _make_question(force_duplicate_of=first_batch[2])

    quiz_data = {"questions": first_batch}

    t0 = time.time()
    result = await _verify_and_fill_quiz_math(quiz_data, requested, mock_regenerate)
    elapsed = time.time() - t0

    final_questions = result.get("questions", [])
    metrics = result.get("_metrics") or {}

    dist = collections.Counter(q.get("correct") for q in final_questions)
    dist_letters = {("ABCD"[k] if isinstance(k, int) and 0 <= k < 4 else str(k)): v
                     for k, v in dist.items()}

    print("=" * 70)
    print(f"LOKALNA SYMULACJA: {requested} pytan zamowionych (rownania kwadratowe z parametrem, mock, ZERO API)")
    print("=" * 70)
    print(f"Final count:        {len(final_questions)}  (oczekiwano {requested})")
    print(f"Czas generowania:   {elapsed:.3f}s")
    print(f"Rozklad A/B/C/D:    {dist_letters}")
    print()
    print("Metryki wewnetrzne (z _verify_and_fill_quiz_math / _verify_and_fix_quiz_math):")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print()
    print(f"N==N spelnione:     {'TAK' if len(final_questions) == requested else 'NIE'}")
    return result, elapsed


if __name__ == "__main__":
    asyncio.run(run_simulation(20))
