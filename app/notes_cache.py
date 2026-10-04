"""Pamiec gotowych notatek popularnych tematow (03.10.2026, user: "jak zrobic aby byly szybsze
bez kitu"). Notatka z matematyki trwala ~50 s i kosztowala kilka wywolan AI - a wielu uczniow
prosi o ten sam temat ("Rownania kwadratowe", "Fotosynteza"). Dla zwyklych zapytan o temat
(bez zdjec, bez wlasnych instrukcji, bez dodatkowego kontekstu) zapisujemy gotowa tresc notatki
i oddajemy ja od reki - zostaje tylko zlozenie PDF (~6 s), zero kosztu API.

Zapisujemy WYLACZNIE kompletne notatki (tryb obliczeniowy: ze zweryfikowanym quizem), a zmiana
promptow/weryfikacji uniewaznia wszystko przez podbicie NOTES_CACHE_VERSION. Kazde odczytanie
i zapis sa w try/except - blad pamieci nigdy nie psuje generowania."""
import hashlib
import json
import re
from datetime import datetime, timezone

# Podbij, gdy zmieniasz prompty/weryfikacje notatek - stare wpisy przestana pasowac.
NOTES_CACHE_VERSION = "v2"  # v2: kontrola faktow w notatkach opisowych


def _norm(temat: str) -> str:
    t = (temat or "").strip().lower()
    t = re.sub(r"[\s]+", " ", t)
    return t.strip(" .,!?;:-")


def cache_key(temat: str, klasa: str, num_sections: int) -> str:
    raw = f"{NOTES_CACHE_VERSION}|{_norm(temat)}|{(klasa or '').strip().lower()}|{int(num_sections)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def is_eligible(temat: str, images, wlasne_instrukcje: str, kontekst: str) -> bool:
    """Tylko zwykly temat tekstowy - zdjecia, wlasne instrukcje i kontekst daja notatke
    unikalna dla tego ucznia, wiec nie moze isc do wspolnej pamieci."""
    if images:
        return False
    if (wlasne_instrukcje or "").strip() or (kontekst or "").strip():
        return False
    t = _norm(temat)
    return 3 <= len(t) <= 120


def get_cached(temat: str, klasa: str, num_sections: int):
    """Zwraca slownik tresci notatki albo None."""
    try:
        from .database import SessionLocal
        from .models import NotesCache
        db = SessionLocal()
        try:
            row = db.query(NotesCache).filter(NotesCache.cache_key == cache_key(temat, klasa, num_sections)).first()
            if row is None:
                return None
            data = json.loads(row.data)
            if not isinstance(data, dict) or not (data.get("sekcje") or data.get("kluczowe_pojecia")):
                return None
            row.hits = (row.hits or 0) + 1
            row.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return data
        finally:
            db.close()
    except Exception as e:
        print(f"[NotesCache] odczyt pominiety: {e}")
        return None


def should_store(data: dict, mode: str) -> bool:
    if not isinstance(data, dict) or not (data.get("sekcje") or data.get("kluczowe_pojecia")):
        return False
    if mode != "opisowy" and not data.get("quiz"):
        return False  # notatka obliczeniowa bez zweryfikowanego quizu jest niekompletna
    return True


def store(temat: str, klasa: str, num_sections: int, data: dict) -> None:
    try:
        from .database import SessionLocal
        from .models import NotesCache
        db = SessionLocal()
        try:
            key = cache_key(temat, klasa, num_sections)
            if db.query(NotesCache).filter(NotesCache.cache_key == key).first() is not None:
                return
            db.add(NotesCache(
                cache_key=key, temat=_norm(temat)[:200], klasa=(klasa or "")[:40],
                num_sections=int(num_sections), data=json.dumps(data, ensure_ascii=False),
                hits=0, created_at=datetime.now(timezone.utc), last_used_at=datetime.now(timezone.utc),
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[NotesCache] zapis pominiety: {e}")


def report_note(user_uid: str, key: str, comment: str = "") -> dict:
    """Zgloszenie bledu: zapisuje zgloszenie (1 na uzytkownika i notatke, max 20 dziennie na
    uzytkownika) i USUWA notatke z pamieci. Zwraca {"ok": bool, "removed": bool}."""
    from datetime import timedelta
    from .database import SessionLocal
    from .models import NotesCache, NotesReport
    if not user_uid or not re.fullmatch(r"[0-9a-f]{40}", key or ""):
        return {"ok": False, "removed": False}
    db = SessionLocal()
    try:
        day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        if db.query(NotesReport).filter(NotesReport.user_id == user_uid, NotesReport.created_at >= day_ago).count() >= 20:
            return {"ok": False, "removed": False}
        row = db.query(NotesCache).filter(NotesCache.cache_key == key).first()
        temat = row.temat if row is not None else None
        if db.query(NotesReport).filter(NotesReport.user_id == user_uid, NotesReport.cache_key == key).first() is None:
            db.add(NotesReport(user_id=user_uid, cache_key=key, temat=temat,
                               comment=((comment or "").strip()[:500] or None)))
        removed = False
        if row is not None:
            db.delete(row)
            removed = True
        db.commit()
        print(f"[NotesReport] zgloszono notatke '{temat}' (usunieta z pamieci: {removed})")
        return {"ok": True, "removed": removed}
    finally:
        db.close()
