# -*- coding: utf-8 -*-
"""Pomiar zuzycia tokenow OpenAI na funkcje i model (19.09.2026, user:
"jak mozemy ograniczyc koszty API bezpiecznie" - dotad NIE BYLO danych,
co ile kosztuje: baza zapisywala tylko liczbe pytan, nie tokeny).

Jak dziala: instaluje sie RAZ przy starcie (install()), owija
openai...chat.completions.create (sync i async) - po kazdym wywolaniu
czyta response.usage (prompt/completion/cached tokens) i dolicza do
licznika w PAMIECI, klucz = (dzien, etykieta, model). Etykieta =
modul.funkcja w app/, ktora wywolala AI (np. "openai_exam._blind_verify_one_closed_quiz",
"notes_pdf_generator.generate_pdf") - dziala tez w watkach/executorach,
bo czyta stos wywolan, nie kontekst. Co ~60 s watek w tle zapisuje sumy
do tabeli api_usage_daily.

Bezpieczenstwo: kazdy krok w try/except - blad pomiaru NIGDY nie zmienia
wyniku ani nie opozniaje wywolania AI (zapis do bazy poza sciezka
wywolania). Zapisywane sa WYLACZNIE liczby (zero tresci rozmow/pytan/PII).

Ograniczenia (celowo): odpowiedzi strumieniowane (stream=True) nie maja
usage bez zmiany parametrow zapytania (co mogloby zepsuc klientow) -
liczymy tylko liczbe wywolan ("stream_calls"), tokeny=0. Whisper/TTS/
realtime (WebSocket) nie przechodza przez chat.completions - poza pomiarem
(patrz panel OpenAI)."""
import sys
import threading
import time
import atexit
from datetime import date

_lock = threading.Lock()
_counters = {}          # (day, label, model) -> [calls, prompt, completion, cached, stream_calls]
_installed = False
_FLUSH_SECONDS = 60


def _caller_label() -> str:
    """Pierwsza ramka stosu z modulu app.* (poza tym plikiem) -> 'modul.funkcja'."""
    try:
        f = sys._getframe(2)
        while f is not None:
            mod = f.f_globals.get("__name__", "")
            if mod.startswith("app.") and mod != __name__:
                return f"{mod[4:]}.{f.f_code.co_name}"
            f = f.f_back
    except Exception:
        pass
    return "nieznane"


def _estimate_stream(messages, max_tokens):
    """Strumien nie ma usage (a dodanie stream_options moglo by zepsuc klientow,
    ktorzy czytaja chunk.choices[0]) - SZACUJEMY: ~3.3 znaku/token wejscia
    (polski) i polowa max_tokens na wyjscie. Model dostaje sufiks '~szac'."""
    try:
        chars = sum(len(str(m.get("content", ""))) for m in (messages or []) if isinstance(m, dict))
    except Exception:
        chars = 0
    return int(chars / 3.3), int((max_tokens or 300) * 0.5)


def _record(label: str, resp, model_hint: str, is_stream: bool, messages=None, max_tokens=None):
    try:
        model = getattr(resp, "model", None) or model_hint or "?"
        u = getattr(resp, "usage", None)
        pt = int(getattr(u, "prompt_tokens", 0) or 0)
        ct = int(getattr(u, "completion_tokens", 0) or 0)
        if is_stream and u is None:
            pt, ct = _estimate_stream(messages, max_tokens)
            model = f"{model_hint or '?'}~szac"
        details = getattr(u, "prompt_tokens_details", None)
        cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
        key = (date.today().isoformat(), label[:120], str(model)[:60])
        with _lock:
            c = _counters.setdefault(key, [0, 0, 0, 0, 0])
            c[0] += 1
            c[1] += pt
            c[2] += ct
            c[3] += cached
            if is_stream or u is None:
                c[4] += 1
    except Exception:
        pass


def _flush():
    with _lock:
        if not _counters:
            return
        snapshot = dict(_counters)
        _counters.clear()
    try:
        from .database import SessionLocal
        from .models import ApiUsageDaily
        db = SessionLocal()
        try:
            for (day, label, model), (calls, pt, ct, cached, streams) in snapshot.items():
                row = db.query(ApiUsageDaily).filter_by(day=day, label=label, model=model).first()
                if row:
                    row.calls += calls
                    row.prompt_tokens += pt
                    row.completion_tokens += ct
                    row.cached_tokens += cached
                    row.stream_calls += streams
                else:
                    db.add(ApiUsageDaily(day=day, label=label, model=model, calls=calls, prompt_tokens=pt,
                                         completion_tokens=ct, cached_tokens=cached, stream_calls=streams))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        # zapis nieudany (np. baza chwilowo niedostepna) - oddaj sumy do licznika, nie gub danych
        try:
            with _lock:
                for k, v in snapshot.items():
                    c = _counters.setdefault(k, [0, 0, 0, 0, 0])
                    for i in range(5):
                        c[i] += v[i]
        except Exception:
            pass
        print(f"[UsageTracker] zapis pominiety: {e}")


def _flusher():
    while True:
        time.sleep(_FLUSH_SECONDS)
        try:
            _flush()
        except Exception:
            pass


def record_extra(label: str, model: str, prompt: int = 0, completion: int = 0, cached: int = 0):
    """Reczne dolozenie zuzycia spoza chat.completions (realtime, TTS).
    Zapisuje WYLACZNIE liczby. Nigdy nie rzuca wyjatku."""
    try:
        key = (date.today().isoformat(), str(label)[:120], str(model)[:60])
        with _lock:
            c = _counters.setdefault(key, [0, 0, 0, 0, 0])
            c[0] += 1
            c[1] += int(prompt or 0)
            c[2] += int(completion or 0)
            c[3] += int(cached or 0)
    except Exception:
        pass


def record_realtime_message(raw, label: str = "api.realtime.session"):
    """Wywolywane dla KAZDEJ wiadomosci z OpenAI Realtime (WebSocket). Reaguje
    tylko na 'response.done' i czyta z niego response.usage - rozbite na tekst i
    audio (ceny sa rozne: audio ~8x drozsze). Modele w tabeli:
    'realtime-text' i 'realtime-audio' (prompt=wejscie, completion=wyjscie)."""
    try:
        if not isinstance(raw, str) or '"response.done"' not in raw:
            return
        import json
        obj = json.loads(raw)
        if obj.get("type") != "response.done":
            return
        u = (obj.get("response") or {}).get("usage") or {}
        ind, outd = u.get("input_token_details") or {}, u.get("output_token_details") or {}
        record_extra(label, "realtime-text", ind.get("text_tokens", 0), outd.get("text_tokens", 0),
                     (ind.get("cached_tokens_details") or {}).get("text_tokens", 0) if isinstance(ind.get("cached_tokens_details"), dict) else 0)
        record_extra(label, "realtime-audio", ind.get("audio_tokens", 0), outd.get("audio_tokens", 0),
                     (ind.get("cached_tokens_details") or {}).get("audio_tokens", 0) if isinstance(ind.get("cached_tokens_details"), dict) else 0)
    except Exception:
        pass


def _install_speech():
    """Owija openai audio.speech.create (TTS): liczy ZNAKI wejscia (rozliczenie tts-1 jest za znaki)."""
    try:
        from openai.resources.audio.speech import Speech
        orig = Speech.create

        def wrapper(self, *args, **kwargs):
            label = _caller_label()
            resp = orig(self, *args, **kwargs)
            try:
                record_extra(label, str(kwargs.get("model") or "tts"), prompt=len(str(kwargs.get("input") or "")))
            except Exception:
                pass
            return resp
        Speech.create = wrapper
    except Exception as e:
        print(f"[UsageTracker] TTS nie owiniete: {e}")


def install():
    """Idempotentne. Owija Completions.create i AsyncCompletions.create."""
    global _installed
    if _installed:
        return
    try:
        from openai.resources.chat.completions import Completions, AsyncCompletions
        orig_sync = Completions.create
        orig_async = AsyncCompletions.create

        def sync_wrapper(self, *args, **kwargs):
            label = _caller_label()
            resp = orig_sync(self, *args, **kwargs)
            try:
                _record(label, resp, kwargs.get("model"), bool(kwargs.get("stream")), kwargs.get("messages"), kwargs.get("max_tokens"))
            except Exception:
                pass
            return resp

        def async_wrapper(self, *args, **kwargs):
            label = _caller_label()
            coro = orig_async(self, *args, **kwargs)
            model_hint, is_stream = kwargs.get("model"), bool(kwargs.get("stream"))
            msgs, max_tok = kwargs.get("messages"), kwargs.get("max_tokens")

            async def _run():
                resp = await coro
                try:
                    _record(label, resp, model_hint, is_stream, msgs, max_tok)
                except Exception:
                    pass
                return resp
            return _run()

        _install_speech()
        Completions.create = sync_wrapper
        AsyncCompletions.create = async_wrapper
        threading.Thread(target=_flusher, daemon=True, name="usage-flusher").start()
        atexit.register(_flush)
        _installed = True
        print("[UsageTracker] pomiar zuzycia tokenow wlaczony")
    except Exception as e:
        print(f"[UsageTracker] nie zainstalowano (aplikacja dziala normalnie): {e}")
