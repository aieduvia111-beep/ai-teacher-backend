"""Prosty, w-pamieci magazyn zadan w tle (background jobs) dla generowania
Quizu/Sprawdzianu (05.09.2026, user: "nie moze byc tak ze zamawiasz 5 pytan
a dostajesz 1 - profesjonalne aplikacje tak nie robia").

Kontekst: wczesniejszy fix (patrz project_exam_quiz_rescue_timeout_fix_sep2026
w pamieci) ograniczyl czasowo mechanizm "ostatecznego ratunku", zeby uniknac
timeoutu przegladarki - ale kosztem czasem niepelnego kompletu pytan. User
uznal to za nieakceptowalne. Prawdziwe rozwiazanie (jak w "profesjonalnych"
aplikacjach robiacych dlugie operacje): NIE trzymac jednego polaczenia HTTP
otwartego przez caly czas generowania (co zawsze ma jakis limit), tylko:
1. Request startuje generowanie w TLE i od razu wraca z job_id.
2. Przegladarka co kilka sekund pyta "gotowe?" (polling).
3. Backend probuje NAPRAWDE tak dlugo, jak potrzeba (z rozsadnym, dlugim
   sufitem - patrz JOB_HARD_CEILING_SECONDS), bo nic go juz nie "timeoutuje"
   w trakcie - jedyny limit to sam sufit generowania, nie polaczenie HTTP.

Bezpieczne jako zwykly dict w pamieci (nie Redis/baza) TYLKO dlatego, ze
serwer dziala jako JEDEN proces uvicorn (bez --workers N, patrz Procfile/
nixpacks.toml) - gdyby to sie kiedys zmienilo (skalowanie do wielu
workerow/instancji), ten magazyn przestalby dzialac poprawnie (status
zapytany na innym workerze nie widzialby joba stworzonego na innym) i
trzeba byloby przejsc na wspoldzielony store (np. Redis).
"""
import time
import uuid
import threading

_jobs = {}
_lock = threading.Lock()

# Jak dlugo trzymac ukonczony/bledny job w pamieci, zanim posprzatamy -
# wystarczajaco dlugo, zeby przegladarka zdazyla go odebrac nawet przy
# wolnym polaczeniu, ale nie w nieskonczonosc (unikamy powolnego wycieku
# pamieci przy duzym ruchu).
_JOB_TTL_SECONDS = 1800


def create_job() -> str:
    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {
            "status": "pending",  # pending -> done | error
            "created": time.monotonic(),
            "result": None,
            "error": None,
        }
    return job_id


def set_done(job_id: str, result) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job["status"] = "done"
            job["result"] = result


def set_error(job_id: str, error: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job["status"] = "error"
            job["error"] = error


def get_job(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job is not None else None


def pop_job(job_id: str):
    """Usuwa i zwraca job - uzywane przy pobieraniu wyniku pliku (exam),
    zeby nie trzymac w pamieci raz juz pobranego pliku/PDF-a."""
    with _lock:
        return _jobs.pop(job_id, None)


def cleanup_old_jobs() -> None:
    """Wywolywane przy okazji create_job - usuwa dawno ukonczone/porzucone
    zadania (np. user zamknal karte przed odebraniem wyniku), zeby dict nie
    rosl bez konca przy duzym ruchu."""
    now = time.monotonic()
    with _lock:
        stale = [jid for jid, j in _jobs.items() if now - j["created"] > _JOB_TTL_SECONDS]
        for jid in stale:
            _jobs.pop(jid, None)
