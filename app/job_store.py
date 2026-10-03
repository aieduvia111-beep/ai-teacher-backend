"""Magazyn zadan w tle (background jobs) dla generowania Quizu/Sprawdzianu.

Historia: 05.09.2026 (user: "nie moze byc tak ze zamawiasz 5 pytan a dostajesz 1")
generowanie przeniesiono z jednego dlugiego requestu HTTP na job + polling:
1. Request startuje generowanie w TLE i od razu wraca z job_id.
2. Przegladarka co kilka sekund pyta "gotowe?" (polling).

PRZEBUDOWANE 03.10.2026 (user: "Nieznane zadanie generowania" po wpisaniu tematu):
dotad joby zyly TYLKO w pamieci procesu, wiec KAZDY restart/deploy Rendera w trakcie
generowania kasowal zadanie i /status zwracal 404. Teraz:
- job (status, parametry, wynik) jest w tabeli `generation_jobs` (przezywa restart),
- parametry startu sa zapisane, wiec gdy proces zginie w trakcie, pierwsze zapytanie
  /status na NOWYM procesie widzi "pending, ale nikt tego nie liczy" (sierota) i
  WZNAWIA generowanie od nowa (get_or_resume) - uczen nie zauwaza restartu,
- jesli baza jest chwilowo niedostepna, wracamy do starego trybu w pamieci (brak
  odpornosci na restart, ale nic sie nie psuje).

Wznawianie dziala dla jobow z zarejestrowanym "resumerem" (register_resumer) i
zapisanymi parametrami - quiz z tematu i sprawdzian. Quiz ze zdjecia nie zapisuje
parametrow (wielkie base64), wiec sierota jest tam usuwana -> 404 -> frontend sam
robi jeden ponowny start.
"""
import asyncio
import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

_lock = threading.Lock()

# Zadania liczone W TYM procesie (id -> True). Job "pending" w bazie, ktorego tu nie ma,
# to sierota po restarcie (lub po innym procesie).
_running = set()

# Fallback w pamieci, gdy baza nie dziala.
_mem = {}

# Jak dlugo trzymac job w bazie, zanim posprzatamy.
_JOB_TTL_SECONDS = 1800
# Ile razy wolno wznowic ten sam job (ochrona przed petla restartow/bledow).
MAX_RESUMES = 2

_RESUMERS = {}


def register_resumer(kind: str, fn) -> None:
    """fn(job_id, **params) -> coroutine; wywolywane przy wznowieniu sieroty."""
    _RESUMERS[kind] = fn


def _db():
    from .database import SessionLocal
    return SessionLocal()


def _row_to_dict(row) -> dict:
    def _loads(s):
        if s is None:
            return None
        try:
            return json.loads(s)
        except (TypeError, ValueError):
            return None
    return {
        "status": row.status,
        "kind": row.kind,
        "params": _loads(row.params),
        "result": _loads(row.result),
        "error": row.error,
        "user_id": row.user_id,
        "attempts": row.attempts or 0,
    }


def create_job(kind: str = None, params: dict = None, user_id: int = None) -> str:
    job_id = uuid.uuid4().hex
    with _lock:
        _running.add(job_id)
    try:
        from .models import GenerationJob
        db = _db()
        try:
            db.add(GenerationJob(
                job_id=job_id, kind=kind, status="pending",
                params=json.dumps(params) if params is not None else None,
                user_id=user_id, attempts=0,
                created_at=datetime.now(timezone.utc),
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[JobStore] baza niedostepna, job w pamieci: {e}")
        with _lock:
            _mem[job_id] = {"status": "pending", "kind": kind, "params": params, "result": None,
                            "error": None, "user_id": user_id, "attempts": 0, "created": time.monotonic()}
    return job_id


def _update(job_id: str, **fields) -> None:
    with _lock:
        if job_id in _mem:
            _mem[job_id].update(fields)
            return
    try:
        from .models import GenerationJob
        db = _db()
        try:
            row = db.query(GenerationJob).filter(GenerationJob.job_id == job_id).first()
            if row is None:
                return
            for k, v in fields.items():
                if k in ("result", "params") and v is not None:
                    v = json.dumps(v)
                setattr(row, k, v)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[JobStore] update {job_id} nieudany: {e}")


def set_done(job_id: str, result) -> None:
    _update(job_id, status="done", result=result)
    with _lock:
        _running.discard(job_id)


def set_error(job_id: str, error: str) -> None:
    _update(job_id, status="error", error=error)
    with _lock:
        _running.discard(job_id)


def get_job(job_id: str):
    with _lock:
        if job_id in _mem:
            return dict(_mem[job_id])
    try:
        from .models import GenerationJob
        db = _db()
        try:
            row = db.query(GenerationJob).filter(GenerationJob.job_id == job_id).first()
            return _row_to_dict(row) if row is not None else None
        finally:
            db.close()
    except Exception as e:
        print(f"[JobStore] get {job_id} nieudany: {e}")
        return None


def pop_job(job_id: str):
    """Usuwa i zwraca job (wynik odbierany raz)."""
    job = get_job(job_id)
    if job is None:
        return None
    with _lock:
        _mem.pop(job_id, None)
        _running.discard(job_id)
    try:
        from .models import GenerationJob
        db = _db()
        try:
            db.query(GenerationJob).filter(GenerationJob.job_id == job_id).delete()
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[JobStore] pop {job_id} nieudany: {e}")
    return job


def cleanup_old_jobs() -> None:
    cutoff_mono = time.monotonic() - _JOB_TTL_SECONDS
    with _lock:
        for jid in [j for j, v in _mem.items() if v.get("created", 0) < cutoff_mono]:
            _mem.pop(jid, None)
    try:
        from .models import GenerationJob
        db = _db()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=_JOB_TTL_SECONDS)
            db.query(GenerationJob).filter(GenerationJob.created_at < cutoff).delete()
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[JobStore] cleanup nieudany: {e}")


def _claim(job_id: str) -> bool:
    """Atomowo oznacza job jako liczony w tym procesie. False = juz ktos go wznowil."""
    with _lock:
        if job_id in _running:
            return False
        _running.add(job_id)
        return True


def _launch(job_id: str, job: dict) -> bool:
    fn = _RESUMERS.get(job.get("kind"))
    params = job.get("params")
    if fn is None or params is None:
        return False
    if not _claim(job_id):
        return True  # inne zapytanie juz wznowilo - po prostu dalej "pending"
    _update(job_id, attempts=(job.get("attempts") or 0) + 1)
    print(f"[JobStore] wznawiam job {job_id} ({job.get('kind')}), proba {(job.get('attempts') or 0) + 1}")
    asyncio.get_running_loop().create_task(fn(job_id, **params))
    return True


def get_or_resume(job_id: str):
    """Jak get_job, ale gdy job jest sierota po restarcie (pending, a ten proces go nie liczy)
    - wznawia generowanie. Zwraca None, gdy zadania nie da sie odzyskac (-> 404)."""
    job = get_job(job_id)
    if job is None:
        return None
    if job["status"] != "pending":
        return job
    with _lock:
        alive = job_id in _running
    if alive:
        return job
    if (job.get("attempts") or 0) >= MAX_RESUMES:
        set_error(job_id, "Generowanie zostalo przerwane przez restart serwera. Sprobuj ponownie.")
        return get_job(job_id)
    if _launch(job_id, job):
        return get_job(job_id)
    pop_job(job_id)  # sierota bez parametrow (np. quiz ze zdjecia) - nie do odzyskania
    return None


def restart_job(job_id: str):
    """Wymusza ponowne wygenerowanie (np. gotowy plik zniknal z dysku po deployu)."""
    job = get_job(job_id)
    if job is None:
        return None
    if (job.get("attempts") or 0) >= MAX_RESUMES:
        return job
    with _lock:
        _running.discard(job_id)
    _update(job_id, status="pending", result=None, error=None)
    job["status"] = "pending"
    if _launch(job_id, job):
        return get_job(job_id)
    return job
