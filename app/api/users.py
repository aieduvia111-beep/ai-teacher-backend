"""USERS API - profil ucznia (ankieta onboardingowa: klasa, przedmiot, data egzaminu)."""
import re
from datetime import date, datetime
from typing import Optional

import stripe
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..firebase_auth import get_current_app_user, _ensure_firebase_app
from ..level_config import is_known_level, label_for_level
from ..models import User, Lesson, Review, Subscription, UsageStats
from ..openai_exam import generate_quiz_from_topic

router = APIRouter(prefix="/users", tags=["Users"])

# " - ", przecinek albo otwierajacy nawias - pierwszy z nich konczy
# "krotka nazwe tematu" przy skracaniu opisu SUBJECT_SCOPE do tytulu karty.
_re_topic_split = re.compile(r"\s+-\s+|,|\(")


class OnboardingRequest(BaseModel):
    education_level: str
    favorite_subject: Optional[str] = None
    exam_date: Optional[str] = None  # "YYYY-MM-DD", opcjonalne - ekran 3 mozna pominac


def _profile_dict(user: User) -> dict:
    return {
        "email": user.email,
        "is_premium": bool(user.is_premium),
        "education_level": user.education_level,
        "education_level_label": label_for_level(user.education_level) if user.education_level else None,
        "favorite_subject": user.favorite_subject,
        "exam_date": user.exam_date.date().isoformat() if user.exam_date else None,
        "onboarding_completed": bool(user.onboarding_completed),
        "suggested_topic": user.suggested_topic,
    }


async def _refresh_suggested_topic_if_stale(user: User, db: Session) -> None:
    """Karta "Nastepny krok" na Dashboardzie ma pokazywac KONKRETNY temat
    (np. "Funkcje trygonometryczne"), dopasowany do klasy+przedmiotu usera,
    i zmieniac sie raz dziennie (nie przy kazdym odswiezeniu Dashboardu).

    Bez klasy/przedmiotu nie ma czego sugerowac - karta wtedy pokazuje
    sam przedmiot (frontend). Gdy jest ten sam dzien co ostatnia sugestia,
    NIE generujemy nic nowego - zwracamy juz zapisany temat (jedno
    wywolanie AI na usera na dzien, nie na kazde zaladowanie Dashboardu).
    """
    if not user.education_level or not user.favorite_subject:
        return

    today = date.today().isoformat()
    if user.suggested_topic_date == today and user.suggested_topic:
        return

    previous_topic = user.suggested_topic
    wlasne_instrukcje = ""
    if previous_topic:
        # Uzywamy juz istniejacego kanalu "wlasne instrukcje" (najwyzszy
        # priorytet w prompcie) do wymuszenia, zeby nowy temat byl INNY
        # niz wczorajszy - bez tego losowanie/wybor AI moglby przez
        # przypadek trafic w ten sam temat dwa dni z rzedu.
        wlasne_instrukcje = (
            f"Wybrany temat NIE MOZE byc tym samym tematem co poprzednio: "
            f"'{previous_topic}'. Wybierz inny temat z podanego zakresu materialu."
        )

    try:
        result = await generate_quiz_from_topic(
            topic=user.favorite_subject,
            subject=user.favorite_subject,
            level=user.education_level,
            num_questions=1,
            difficulty="medium",
            wlasne_instrukcje=wlasne_instrukcje,
        )
    except Exception as e:
        print(f"[SuggestedTopic] blad generacji dla usera {user.id}: {e}")
        return

    if not result.get("success"):
        print(f"[SuggestedTopic] generacja nieudana dla usera {user.id}: {result.get('error')}")
        return

    title = (result["quiz"].get("title") or "").strip()
    # generate_quiz_from_topic dokleja " - Quiz" do tytulu (patrz FORMAT w
    # prompcie) - to dobre w quizie, ale zbedne na karcie Dashboardu.
    if title.lower().endswith(" - quiz"):
        title = title[: -len(" - Quiz")].strip()
    # W trybie "AI samo wybiera" model czesto kopiuje CALA fraze z
    # SUBJECT_SCOPE (np. "ciagi arytmetyczne i geometryczne - wzor
    # ogolny, suma n wyrazow, zastosowania (np. procent skladany)") -
    # dobre jako zakres dla quizu, za dlugie na maly kafelek "Nastepny
    # krok". Skracamy do pierwszego sensownego fragmentu (przed " - "
    # albo przecinkiem/nawiasem), zeby karta pokazywala krotka nazwe
    # tematu, nie cale zdanie.
    short_title = _re_topic_split.split(title, maxsplit=1)[0].strip()
    if short_title:
        title = short_title
    if not title:
        return

    user.suggested_topic = title[:255]
    user.suggested_topic_date = today
    db.commit()


@router.get("/me")
async def get_me(user: User = Depends(get_current_app_user), db: Session = Depends(get_db)):
    """Zwraca profil ucznia - w tym dane z ankiety onboardingowej, jesli juz ja wypelnil."""
    await _refresh_suggested_topic_if_stale(user, db)
    return {"success": True, "profile": _profile_dict(user)}


@router.post("/onboarding")
def save_onboarding(
    req: OnboardingRequest,
    user: User = Depends(get_current_app_user),
    db: Session = Depends(get_db),
):
    """Zapisuje odpowiedzi z ankiety onboardingowej przy koncie usera."""
    if not is_known_level(req.education_level):
        return {"success": False, "error": f"Nieznany poziom: {req.education_level}"}

    user.education_level = req.education_level
    if req.favorite_subject:
        user.favorite_subject = req.favorite_subject.strip()[:50]
    if req.exam_date:
        try:
            user.exam_date = datetime.fromisoformat(req.exam_date)
        except ValueError:
            return {"success": False, "error": "Nieprawidlowy format daty (oczekiwano YYYY-MM-DD)."}
    user.onboarding_completed = True

    db.commit()
    db.refresh(user)
    return {"success": True, "profile": _profile_dict(user)}


@router.delete("/me")
def delete_account(
    user: User = Depends(get_current_app_user),
    db: Session = Depends(get_db),
):
    """USUWA konto uzytkownika NA STALE - wymog Apple App Store (Guideline
    5.1.1(v): kazda apka z rejestracja MUSI oferowac samoobslugowe
    USUNIECIE konta, nie tylko wylogowanie/deaktywacje). Wrzesien 2026,
    odpowiedz na odrzucenie App Store Review.

    Kolejnosc krokow (celowa - kazdy nastepny krok zaklada, ze poprzedni
    juz sie odbyl):
    1. Anuluj NATYCHMIAST (nie "na koniec okresu") KAZDA aktywna/trialujaca/
       zalegajaca subskrypcje Stripe tego uzytkownika - usuniete konto NIE
       MOZE nadal byc obciazane.
    2. Usun powiazane rekordy SQL: Review (przez lesson_id, bo Review nie
       ma bezposredniego firebase_uid), Lesson, Subscription, UsageStats.
    3. Usun dokument Firestore users/{uid} (profil/plan uzywany przez
       reszte apki).
    4. Usun konto Firebase Auth - KONCOWY krok przed skasowaniem wiersza
       SQL, bo to on uniewaznia token/sesje uzytkownika natychmiast.
    5. Usun wiersz User z SQL.

    Kazdy krok jest best-effort i logowany osobno (nie jeden wielki
    try/except) - czesciowa awaria JEDNEGO zewnetrznego systemu (np.
    Firestore chwilowo niedostepne) nie powinna zostawic uzytkownika: (a)
    dalej platnego w Stripe, (b) z kontem, ktore wyglada na usuniete, ale
    nadal moze sie zalogowac. `errors` w odpowiedzi pozwala to zdiagnozowac,
    ale user zawsze dostaje success=True - z jego punktu widzenia proces
    usuwania zostal zainicjowany i najwazniejszy krok (dostep/logowanie)
    jest zawsze wykonywany."""
    firebase_uid = user.firebase_uid
    email = user.email
    errors = []

    # 1. Stripe - NATYCHMIASTOWE anulowanie (nie modify+cancel_at_period_end,
    # jak przy zwyklym "Anuluj subskrypcje" - tu chcemy zero dalszych obciazen).
    if user.stripe_customer_id:
        try:
            subs = stripe.Subscription.list(customer=user.stripe_customer_id, status="all", limit=100)
            for s in subs.data:
                if s.status in ("active", "trialing", "past_due", "unpaid"):
                    stripe.Subscription.delete(s.id)
        except Exception as e:
            errors.append(f"stripe: {e}")

    # 2. Powiazane rekordy SQL.
    try:
        if firebase_uid:
            lesson_ids = [row[0] for row in db.query(Lesson.id).filter(Lesson.user_id == firebase_uid).all()]
            if lesson_ids:
                db.query(Review).filter(Review.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)
            db.query(Lesson).filter(Lesson.user_id == firebase_uid).delete(synchronize_session=False)
            db.query(Subscription).filter(Subscription.user_id == firebase_uid).delete(synchronize_session=False)
        db.query(UsageStats).filter(UsageStats.user_id == user.id).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"sql_powiazane: {e}")

    # 3. Firestore.
    try:
        if firebase_uid:
            from ..services.stripe_service import _fdb
            if _fdb:
                _fdb.collection("users").document(firebase_uid).delete()
    except Exception as e:
        errors.append(f"firestore: {e}")

    # 4. Firebase Auth - koncowy krok przed usunieciem wiersza SQL.
    try:
        if firebase_uid:
            _ensure_firebase_app()
            from firebase_admin import auth as _fb_admin_auth
            _fb_admin_auth.delete_user(firebase_uid)
    except Exception as e:
        errors.append(f"firebase_auth: {e}")

    # 5. Wiersz User w SQL.
    try:
        db.delete(user)
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"sql_user: {e}")

    print(f"[DeleteAccount] Konto usuniete: {email} ({firebase_uid}). Bledy: {errors or 'brak'}")
    return {"success": True, "errors": errors}
