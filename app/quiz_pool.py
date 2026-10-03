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


# ---------------------------------------------------------------------------
# POLA "OGOLNE" (02.10.2026, user: "zrob szybkosc quizu bez utraty jakosci").
# Audyt 14 dni: 62% zywych generacji quizu to TEMAT OGOLNY (temat == nazwa
# przedmiotu, np. kafelek "Nastepny krok"/szybkie pytanie), w tym 1093 quizow
# na JEDNO pytanie (~9s kazdy) - a _is_poolable odrzuca takie zamowienia, wiec
# NIGDY nie korzystaly z puli. NIE mozna ich po prostu pobierac z puli
# "quiz": tam sa tez pytania z tematow wpisanych recznie przez userow, w tym
# niepasujacych do przedmiotu (np. angielski -> "Rownania rozniczkowe").
# Dlatego OSOBNY feature "quiz_generic" zasilany WYLACZNIE wynikami
# zywych quizow ogolnych (generate_quiz_from_topic juz waliduje temat wzgledem
# zakresu klasy - validate_generic_topic - a kazde pytanie przeszlo pelna
# weryfikacje). Pytania sa serwowane TYLKO darmowym userom (premium dalej
# zawsze dostaje swiezy quiz z AI), z tym samym kluczem (przedmiot, poziom,
# trudnosc) co zamowienie.
# ---------------------------------------------------------------------------
GENERIC_FEATURE = "quiz_generic"
GENERIC_SMALL_N = 3          # do tylu pytan: losuj z calej puli (przedmiot, poziom, trudnosc)
GENERIC_MIN_POOL = 40        # tyle pytan musi miec pula, zeby serwowac male quizy (rzadsze powtorki)
GENERIC_REFRESH_PROB = 0.12  # ulamek zamowien idacy na zywo mimo pelnej puli - zeby pula dalej rosla
MAX_GENERIC_PER_KEY = 300


def _is_generic_poolable(topic, subject, wlasne_instrukcje) -> bool:
    if (wlasne_instrukcje or "").strip():
        return False
    return bool(_norm(topic)) and _norm(topic) == _norm(subject)


def _generic_filters(q, subject, difficulty, level):
    return q.filter(
        QuestionBankItem.feature == GENERIC_FEATURE,
        sql_func.lower(sql_func.trim(QuestionBankItem.subject)) == _norm(subject),
        sql_func.lower(sql_func.trim(QuestionBankItem.difficulty)) == _norm(difficulty),
        sql_func.lower(sql_func.trim(QuestionBankItem.level)) == _norm(level),
    )


def _clean_generic_topic(title, subject) -> str:
    t = (title or "").strip()
    for suffix in (" - Quiz", " – Quiz", " - quiz"):
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
    return (t or subject or "ogolne")[:300]


def serve_generic_from_pool(db, subject, difficulty, level, n):
    """Quiz z puli "ogolnej" albo None (pula za mala / pech odswiezenia).
    Male quizy (n <= GENERIC_SMALL_N): losowane z calej puli (przedmiot,
    poziom, trudnosc), najmniej uzywane maja pierwszenstwo. Wieksze: tylko
    z JEDNEGO tematu (spojny quiz) majacego >= max(3n, MIN_POOL) pytan."""
    if random.random() < GENERIC_REFRESH_PROB:
        return None
    base = _generic_filters(db.query(QuestionBankItem), subject, difficulty, level)
    if n <= GENERIC_SMALL_N:
        total = _generic_filters(db.query(sql_func.count(QuestionBankItem.id)), subject, difficulty, level).scalar() or 0
        if total < GENERIC_MIN_POOL:
            return None
        rows = base.order_by(QuestionBankItem.used_count.asc(), QuestionBankItem.id.asc()).limit(max(n * 8, 60)).all()
        seen, cand = set(), []
        for r in rows:
            if r.fingerprint in seen:
                continue
            seen.add(r.fingerprint)
            cand.append(r)
        if len(cand) < n:
            return None
        # losowo TYLKO w obrebie najmniej uzywanej warstwy (used_count), dopiero
        # gdy jej zabraknie - kolejna warstwa; dzieki temu powtorka pytania
        # pojawia sie dopiero po przejsciu CALEJ puli, nie wczesniej.
        picked = []
        by_tier = {}
        for r in cand:
            by_tier.setdefault(r.used_count or 0, []).append(r)
        for tier in sorted(by_tier):
            pool_t = by_tier[tier]
            take = min(n - len(picked), len(pool_t))
            picked.extend(random.sample(pool_t, take))
            if len(picked) >= n:
                break
        title_topic = picked[0].topic
    else:
        need = max(POOL_MULTIPLIER * n, MIN_POOL)
        topic_counts = _generic_filters(
            db.query(QuestionBankItem.topic, sql_func.count(QuestionBankItem.id)), subject, difficulty, level
        ).group_by(QuestionBankItem.topic).all()
        big = [t for t, c in topic_counts if c >= need]
        if not big:
            return None
        title_topic = random.choice(big)
        rows = base.filter(QuestionBankItem.topic == title_topic).order_by(
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
    return {"title": f"{title_topic} - Quiz", "questions": questions, "_from_pool": True}


def save_generic_to_pool(db, subject, difficulty, level, quiz) -> int:
    """Dopisuje pytania PELNEGO, nieobnizonego quizu OGOLNEGO do puli
    "quiz_generic" (temat = oczyszczony tytul quizu wybrany przez generator)."""
    if not isinstance(quiz, dict) or quiz.get("_from_pool"):
        return 0
    if quiz.get("_shortfall_warning") or quiz.get("_difficulty_downgrade_notice"):
        return 0
    total = _generic_filters(db.query(sql_func.count(QuestionBankItem.id)), subject, difficulty, level).scalar() or 0
    room = MAX_GENERIC_PER_KEY - total
    topic = _clean_generic_topic(quiz.get("title"), subject)
    added = 0
    for q in quiz.get("questions", []) or []:
        if added >= room:
            break
        if not isinstance(q, dict) or not q.get("question"):
            continue
        if question_bank.add_to_bank(db, GENERIC_FEATURE, subject, topic, difficulty, level, q):
            added += 1
    if added:
        db.commit()
    return added


async def generate_quiz_pooled(topic, subject, level, num_questions, difficulty, wlasne_instrukcje, use_pool):
    """Drop-in zamiast generate_quiz_from_topic. use_pool=True tylko dla darmowych userow."""
    from .openai_exam import generate_quiz_from_topic
    from .database import SessionLocal
    poolable = _is_poolable(topic, subject, wlasne_instrukcje)
    generic_poolable = _is_generic_poolable(topic, subject, wlasne_instrukcje)

    if use_pool and generic_poolable:
        try:
            db = SessionLocal()
            try:
                quiz = serve_generic_from_pool(db, subject, difficulty, level, num_questions)
            finally:
                db.close()
            if quiz:
                print(f"[QuizPool] z puli OGOLNEJ: {subject}/{difficulty}/{level} n={num_questions} (0 wywolan AI)")
                return {"success": True, "quiz": quiz}
        except Exception as e:
            print(f"[QuizPool] odczyt puli ogolnej nieudany (spadam do AI): {e}")

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
    elif generic_poolable and result.get("success"):
        try:
            db = SessionLocal()
            try:
                added = save_generic_to_pool(db, subject, difficulty, level, result["quiz"])
            finally:
                db.close()
            if added:
                print(f"[QuizPool] +{added} pytan do puli OGOLNEJ: {subject}/{difficulty}/{level}")
        except Exception as e:
            print(f"[QuizPool] zapis do puli ogolnej nieudany (ignoruje): {e}")
    return result
