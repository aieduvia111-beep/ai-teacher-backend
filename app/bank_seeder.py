# -*- coding: utf-8 -*-
"""Proces W TLE, ktory zapelnia magazyn pytan (app/question_bank.py) -
generuje i weryfikuje pytania dla konkretnego (topic, subject, level,
difficulty) BEZ presji czasu zywej generacji (60-210s w
openai_exam.py/_verify_and_fill_quiz_math) - tu nikt nie czeka, wiec
mozna spokojnie zebrac duzo prob.

WAZNE (koszt): kazda runda to prawdziwe, PLATNE wywolania OpenAI
(generacja + "slepy" blind-check AI-2 dla nierozpoznanych wzorcow) -
DOKLADNIE tak samo jak zywa generacja. To NIE jest test/symulacja.
Uruchamiaj tylko po jawnej zgodzie usera (patrz feedback_ask_before_
paid_tests w pamieci) - ten modul tylko DEFINIUJE mechanizm, nie
uruchamia sie sam."""
from .openai_exam import _raw_generate_quiz_topic_batch, _verify_and_fix_quiz_math, client
from .database import SessionLocal
from . import question_bank


async def seed_bank_for_topic(topic: str, subject: str, level: str, difficulty: str,
                               target_pool_size: int = 30, feature: str = "quiz",
                               batch_size: int = 15, max_rounds: int = 10) -> dict:
    """Zbiera zweryfikowane pytania dla JEDNEJ kombinacji (topic/subject/
    level/difficulty), az magazyn dla niej osiagnie `target_pool_size`
    ALBO wyczerpie `max_rounds` prob (bezpiecznik kosztu - nie
    nieskonczona petla nawet jesli temat jest bardzo trudny i malo prob
    przechodzi weryfikacje). Kazda runda uzywa DOKLADNIE tej samej
    trzywarstwowej weryfikacji co zywa generacja (_verify_and_fix_quiz_math
    z prawdziwym `client` - Warstwa 2.5 blind-check TEZ dziala), wiec
    kazde zaakceptowane pytanie jest rownie pewne jak swiezo
    wygenerowane i zaakceptowane w zywym quizie. Zwraca podsumowanie
    (ile dodano, jaka jest pula na koniec) - do logowania/raportowania,
    NIE rzuca wyjatku przy pojedynczej nieudanej rundzie (probuje dalej,
    do max_rounds)."""
    db = SessionLocal()
    try:
        current = question_bank.bank_pool_size(db, feature, topic, difficulty, level)
        print(f"[BankSeeder] {topic}/{difficulty}/{level}: obecna pula={current}, cel={target_pool_size}")
        added_total = 0
        for round_i in range(1, max_rounds + 1):
            current = question_bank.bank_pool_size(db, feature, topic, difficulty, level)
            if current >= target_pool_size:
                print(f"[BankSeeder] {topic}/{difficulty}/{level}: cel osiagniety ({current}/{target_pool_size}), koncze")
                break
            try:
                raw = await _raw_generate_quiz_topic_batch(topic, True, subject, level, batch_size, difficulty, "")
                verified = await _verify_and_fix_quiz_math(raw, difficulty=difficulty, level=level, client=client)
            except Exception as e:
                print(f"[BankSeeder] runda {round_i}/{max_rounds} nieudana ({e}), probuje dalej")
                continue
            questions = verified.get("questions", [])
            print(f"[BankSeeder] runda {round_i}/{max_rounds}: {len(questions)}/{batch_size} zweryfikowanych kandydatow")
            round_added = 0
            for q in questions:
                if question_bank.add_to_bank(db, feature=feature, subject=subject, topic=topic, difficulty=difficulty, level=level, question_data=q):
                    round_added += 1
            db.commit()
            added_total += round_added
        final = question_bank.bank_pool_size(db, feature, topic, difficulty, level)
        summary = {"topic": topic, "subject": subject, "level": level, "difficulty": difficulty,
                   "added": added_total, "pool_size": final, "target": target_pool_size}
        print(f"[BankSeeder] ZAKONCZONO {topic}/{difficulty}/{level}: dodano {added_total}, pula={final}/{target_pool_size}")
        return summary
    finally:
        db.close()


async def seed_bank_multi(specs: list, target_pool_size: int = 30) -> list:
    """`specs`: lista (topic, subject, level, difficulty). SEKWENCYJNIE
    (jeden temat na raz, nie rownolegle miedzy tematami) - unika skoku
    kosztow/rate-limitow naraz; kazdy temat WEWNETRZNIE juz rownolegli
    wywolania AI przez istniejacy _parallel_batch_sizes."""
    results = []
    for topic, subject, level, difficulty in specs:
        results.append(await seed_bank_for_topic(topic, subject, level, difficulty, target_pool_size=target_pool_size))
    return results
