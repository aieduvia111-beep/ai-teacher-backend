# -*- coding: utf-8 -*-
"""Magazyn gotowych, juz zweryfikowanych pytan - backup dla zywej
generacji AI (patrz pelne uzasadnienie w QuestionBankItem, app/models.py).

Architektura (user 18.09.2026): "AI probuje generowac ZAWSZE (swiezosc,
roznorodnosc) - ALE jesli po X probach/sekundach NIE udaje sie osiagnac
N=N, system SIEGA do gotowej, JUZ zweryfikowanej bazy pytan jako backup".
Zywa generacja (openai_exam.py) zostaje jedynym GLOWNYM zrodlem - ten
modul jest WYLACZNIE czytany/zasilany jako uzupelnienie, nigdy odwrotnie.

Dwa kierunki uzycia:
  - CZYTANIE (get_bank_questions): wolane z _verify_and_fill_quiz_math
    (openai_exam.py) PO wyczerpaniu standardowych+grace+rescue rund, tuz
    PRZED twardym niepowodzeniem - patrz tam.
  - PISANIE (add_to_bank): wolane z app/bank_seeder.py (proces w tle,
    generuje+weryfikuje BEZ presji czasu, zeby zapelnic magazyn dla
    najczesciej zamawianych tematow) ORAZ opcjonalnie z samej zywej
    generacji, jesli chcemy dokladac do magazynu kazde pytanie, ktore i
    tak przeszlo pelna weryfikacje "za darmo" przy okazji normalnego
    zamowienia (nie wlaczone domyslnie - patrz bank_seeder.py)."""
import hashlib
import re

from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from .models import QuestionBankItem

_NUMBER_RE = re.compile(r'-?\d+(?:[.,]\d+)?')
_NON_WORD_RE = re.compile(r'[^a-ząćęłńóśźż#]+')


def compute_fingerprint(question_text: str) -> str:
    """Stabilny string-fingerprint (do kolumny `fingerprint`/dedup przy
    czytaniu) - UPROSZCZONA wersja _question_fingerprint z openai_exam.py
    (tam zwracany jest kortet kluczy do porownan w pamieci w obrebie
    jednego requestu; tu potrzebny jeden stabilny string do zapisu w
    bazie) - ten sam pomysl (normalizacja liczb do placeholdera, zeby
    "ta sama tresc z innymi liczbami" NIE liczyla sie jako identyczna),
    ale zredukowany do jednej wartosci przez hash."""
    t = (question_text or "").lower()
    skeleton = _NUMBER_RE.sub('#', t)
    skeleton = _NON_WORD_RE.sub(' ', skeleton)
    skeleton = ' '.join(skeleton.split())
    return hashlib.sha256(skeleton.encode("utf-8")).hexdigest()[:32]


def add_to_bank(db: Session, feature: str, subject: str, topic: str, difficulty: str, level: str, question_data: dict) -> bool:
    """Dodaje JEDNO juz-zweryfikowane pytanie do magazynu. Pomija (zwraca
    False) ciche duplikaty - to samo pytanie (fingerprint) dla tego
    samego (feature, topic, difficulty, level) juz w magazynie - zeby
    seeder odpalony wielokrotnie nie zapchal magazynu kopiami. NIE
    commituje sam (caller decyduje o transakcji/batchu - patrz
    bank_seeder.py, ktory dodaje wiele naraz i commituje raz)."""
    text = question_data.get("question", "") if isinstance(question_data, dict) else ""
    fp = compute_fingerprint(text)
    exists = db.query(QuestionBankItem.id).filter(
        QuestionBankItem.feature == feature,
        QuestionBankItem.topic == topic,
        QuestionBankItem.difficulty == difficulty,
        QuestionBankItem.level == level,
        QuestionBankItem.fingerprint == fp,
    ).first()
    if exists:
        return False
    db.add(QuestionBankItem(
        feature=feature, subject=subject, topic=topic, difficulty=difficulty, level=level,
        question_data=question_data, fingerprint=fp, used_count=0,
    ))
    return True


def get_bank_questions(db: Session, feature: str, topic: str, difficulty: str, level: str, limit: int, exclude_fingerprints=None) -> list:
    """Zwraca do `limit` pytan z magazynu dla (feature, topic, difficulty,
    level) - dopasowanie case-insensitive/trim (zywa generacja i seeder
    moga miec drobne roznice w wielkosci liter/spacjach). Preferuje
    NAJMNIEJ uzywane pozycje (used_count ASC), zeby przy malej puli nie
    serwowac WCIAZ tego samego jednego pytania. Pomija fingerprinty juz
    obecne w biezacej partii zywej generacji (exclude_fingerprints, patrz
    seen_fingerprints w _verify_and_fill_quiz_math) - unika duplikatu AI+
    magazyn w tym samym quizie. ZWIEKSZA used_count zwroconych pozycji i
    COMMITUJE (to jedyna operacja pisania w sciezce odczytu - celowo
    natychmiastowa, zeby rownolegle zapytania nie zobaczyly tej samej
    "najmniej uzywanej" pozycji i nie zdublowaly jej w dwoch roznych
    quizach na raz)."""
    if not topic or limit <= 0:
        return []
    q = db.query(QuestionBankItem).filter(
        QuestionBankItem.feature == feature,
        sql_func.lower(sql_func.trim(QuestionBankItem.topic)) == topic.strip().lower(),
    )
    if difficulty:
        q = q.filter(sql_func.lower(sql_func.trim(QuestionBankItem.difficulty)) == difficulty.strip().lower())
    if level:
        q = q.filter(sql_func.lower(sql_func.trim(QuestionBankItem.level)) == level.strip().lower())
    rows = q.order_by(QuestionBankItem.used_count.asc(), QuestionBankItem.id.asc()).limit(limit * 3).all()
    exclude = exclude_fingerprints or set()
    picked = []
    for row in rows:
        if row.fingerprint in exclude:
            continue
        picked.append(row)
        if len(picked) >= limit:
            break
    for row in picked:
        row.used_count = (row.used_count or 0) + 1
    if picked:
        db.commit()
    return [row.question_data for row in picked]


def bank_pool_size(db: Session, feature: str, topic: str, difficulty: str, level: str) -> int:
    """Ile pytan jest aktualnie w magazynie dla danej kombinacji -
    uzywane przez bank_seeder.py, zeby wiedziec czy/ile jeszcze
    dogenerowac (cel puli), oraz do monitoringu/raportowania."""
    q = db.query(sql_func.count(QuestionBankItem.id)).filter(
        QuestionBankItem.feature == feature,
        sql_func.lower(sql_func.trim(QuestionBankItem.topic)) == (topic or "").strip().lower(),
    )
    if difficulty:
        q = q.filter(sql_func.lower(sql_func.trim(QuestionBankItem.difficulty)) == difficulty.strip().lower())
    if level:
        q = q.filter(sql_func.lower(sql_func.trim(QuestionBankItem.level)) == level.strip().lower())
    return q.scalar() or 0
