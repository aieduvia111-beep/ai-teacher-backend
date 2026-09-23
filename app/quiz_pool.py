# -*- coding: utf-8 -*-
"""Wspolna pula juz zweryfikowanych pytan quizu (23.09.2026, KOSZTY).

Powod (real prod, 21-23.09.2026): ~19-27 zl/dzien API, z czego zdecydowana wiekszosc to
DARMOWI userzy (1313 kont free vs 11 platnych), a ~66% zamowionych quizow to powtorki
tych samych tematow. Kazdy taki quiz przechodzil pelna, kosztowna weryfikacje (AI + sympy
+ slepy sedzia AI-2) od zera, mimo ze identyczne pytania byly juz zweryfikowane godzine
wczesniej.

Zasada (zatwierdzona przez usera: "to zrob to"):
  * PISANIE: kazdy PELNY quiz wygenerowany "na zywo" (kazdy user) dorzuca swoje pytania do
    QuestionBankItem (feature="quiz") - one JUZ przeszly cala weryfikacje.
  * CZYTANIE: DARMOWY user dostaje quiz z puli BEZ ZADNEGO wywolania AI, ale tylko gdy pula
    dla (przedmiot, temat, trudnosc, poziom) jest na tyle duza, zeby quizy sie nie powtarzaly
    (>= 3x zamawiana liczba pytan i >= MIN_POOL). Inaczej - normalna generacja (i pula rosnie).
  * PREMIUM (w tym trial) ZAWSZE dostaje swiezy quiz z AI - to jest wartosc, za ktora placi.
  * Wlasne instrukcje usera / temat ogolny (== nazwa przedmiotu) NIGDY nie ida przez pule.
  * Kazdy blad puli jest polkniety - w najgorszym razie zachowanie identyczne jak przed zmiana.
"""
import random
import time

from sqlalchemy import func as sql_func

from .models import QuestionBankItem
from . import question_bank

FEATURE = "quiz"
POOL_MULTIPLIER = 3      # pula musi miec >= 3x zamawiana liczbe pytan zeby serwowac z niej
MIN_POOL = 15            # ...i nie mniej niz tyle (male N nie moga serwowac z 6 pytan)
MAX_POOL_PER_KEY = 200   # sufit zapisu - nie puchnij bez konca dla jednego tematu


def _norm(s) -> str:
    return (s or "").strip().lower()


def _key_filters(q, subject, topic, difficulty, level):
    return q.filter(
        QuestionBankItem.feature == FEATURE,
        sql_func.lower(sql_func.trim(QuestionBankItem.topic)) == _norm(topic),
        sql_func.lower(sql_func.trim(QuestionBankItem.subject)) == _norm(subject),
        sql_func.lower(sql_func.trim(QuestionBankItem.difficulty)) == _norm(difficulty),
        sql_func.lower(sql_func.trim(QuestionBankItem.level)) == _norm(level),
    )


def _is_poolable(topic, subject, wlasne_instrukcje) -> bool:
    if (wlasne_instrukcje or "").strip():
        return False
    if not _norm(topic) or _norm(topic) == _norm(subject):
        return False
    return True


def pool_size(db, subject, topic, difficulty, level) -> int:
    return _key_filters(db.query(sql_func.count(QuestionBankItem.id)), subject, topic, difficulty, level).scalar() or 0


def serve_from_pool(db, subject, topic, difficulty, level, n):
    """Zwraca quiz z puli (dict jak z generatora) albo None, gdy pula za mala."""
    size = pool_size(db, subject, topic, difficulty, level)
    if size < max(POOL_MULTIPLIER * n, MIN_POOL):
        return None
    rows = _key_filters(db.query(QuestionBankItem), subject, topic, difficulty, level).order_by(
        QuestionBankItem.used_count.asc(), QuestionBankItem.id.asc()
    ).limit(n * 3).all()
    seen, cand = set(), []
    for r in rows:
        if r.fingerprint in seen:
            continue
        seen.add(r.fingerprint)
        cand.append(r)
    if len(cand) < n:
        return None
    # najmniej uzywane maja pierwszenstwo, ale losujemy w obrebie puli kandydatow, zeby
    # dwa kolejne zamowienia tego samego tematu nie dawaly identycznego zestawu
    picked = random.sample(cand, n)
    for r in picked:
        r.used_count = (r.used_count or 0) + 1
    db.commit()
    random.shuffle(picked)
    questions = []
    for i, r in enumerate(picked, start=1):
        qd = dict(r.question_data)
        qd["id"] = i
        questions.append(qd)
    return {"title": f"{topic.strip()} - Quiz", "questions": questions, "_from_pool": True}


def save_to_pool(db, subject, topic, difficulty, level, quiz) -> int:
    """Dopisuje pytania PELNEGO, nieobnizonego quizu do puli. Zwraca liczbe dodanych."""
    if not isinstance(quiz, dict) or quiz.get("_from_pool"):
        return 0
    if quiz.get("_shortfall_warning") or quiz.get("_difficulty_downgrade_notice"):
        return 0  # niepelny / z obnizona trudnoscia -> nie zasilamy puli
    room = MAX_POOL_PER_KEY - pool_size(db, subject, topic, difficulty, level)
    added = 0
    for q in quiz.get("questions", []) or []:
        if added >= room:
            break
        if not isinstance(q, dict) or not q.get("question"):
            continue
        if question_bank.add_to_bank(db, FEATURE, subject, topic.strip(), difficulty, level, q):
            added += 1
    if added:
        db.commit()
    return added


async def generate_quiz_pooled(topic, subject, level, num_questions, difficulty, wlasne_instrukcje, use_pool):
    """Drop-in zamiast generate_quiz_from_topic. use_pool=True tylko dla darmowych userow."""
    from .openai_exam import generate_quiz_from_topic
    from .database import SessionLocal
    poolable = _is_poolable(topic, subject, wlasne_instrukcje)

    if use_pool and poolable:
        try:
            db = SessionLocal()
            try:
                quiz = serve_from_pool(db, subject, topic, difficulty, level, num_questions)
            finally:
                db.close()
            if quiz:
                print(f"[QuizPool] z puli: {topic}/{difficulty}/{level} n={num_questions} (0 wywolan AI)")
                return {"success": True, "quiz": quiz}
        except Exception as e:
            print(f"[QuizPool] odczyt puli nieudany (spadam do AI): {e}")

    result = await generate_quiz_from_topic(
        topic=topic, subject=subject, level=level, num_questions=num_questions,
        difficulty=difficulty, wlasne_instrukcje=wlasne_instrukcje,
    )
    if poolable and result.get("success"):
        try:
            db = SessionLocal()
            try:
                added = save_to_pool(db, subject, topic, difficulty, level, result["quiz"])
            finally:
                db.close()
            if added:
                print(f"[QuizPool] +{added} pytan do puli: {topic}/{difficulty}/{level}")
        except Exception as e:
            print(f"[QuizPool] zapis do puli nieudany (ignoruje): {e}")
    return result
