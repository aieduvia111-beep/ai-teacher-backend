# -*- coding: utf-8 -*-
"""Routing generowania MATEMATYKI do DeepSeek z automatycznym zapasem na OpenAI (20.09.2026, KOSZTY).

Decyzja usera: DeepSeek TYLKO do generowania pytan z matematyki (quiz + sprawdzian). Czat, zdjecia, tablica,
glos i pozostale przedmioty zostaja na OpenAI (dane uczniow, obraz, brak testow jakosci).
Dane z testu na naszych zadaniach (trudne tematy, ten sam sedzia): deepseek-flash bez myslenia 57%
przechodzacych weryfikacje w 135 s vs gpt-4o 39% / gpt-4o-mini 46% (patrz sesja 20.09.2026).

Zmienne srodowiskowe (Render):
  DEEPSEEK_API_KEY   - klucz; brak = DeepSeek wylaczony (wszystko na OpenAI, zero zmian w zachowaniu)
  MATH_PROVIDER      - "openai" wylacza DeepSeek bez zmiany kodu (domyslnie: deepseek, jesli jest klucz)
  DEEPSEEK_MODEL     - nazwa modelu (domyslnie "deepseek-flash")

Zapas na OpenAI (uczen nic nie zauwaza): blad API (brak srodkow 402, zly klucz 401, limit 429, 5xx, timeout),
pusta odpowiedz albo odpowiedz urwana przez limit tokenow -> to samo zapytanie leci na OpenAI z oryginalnymi
parametrami. Wylacznik: po _BREAKER_FAILS bledach z rzedu DeepSeek jest omijany przez _BREAKER_PAUSE s, zeby
kazde zamowienie nie czekalo na timeout."""
import os
import time
import threading

_BREAKER_FAILS = 3
_BREAKER_PAUSE = 600.0          # 10 min
_DS_TIMEOUT = 90.0              # DeepSeek nothink: ~20-25 s/wywolanie; wolniej = zapas na OpenAI
_DS_MAX_TOKENS = 8192           # limit odpowiedzi w trybie bez myslenia

_lock = threading.Lock()
_state = {"fails": 0, "paused_until": 0.0}
_stats = {"ok": 0, "fallback": 0, "last_error": ""}   # od startu procesu; tylko liczby i skrocony komunikat bledu (bez tresci pytan)


def enabled() -> bool:
    if os.environ.get("MATH_PROVIDER", "").strip().lower() == "openai":
        return False
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def is_math(subject=None, topic=None) -> bool:
    s = (subject or "").strip().lower()
    if s:
        return "matem" in s
    return (topic or "").strip().lower().startswith("matem")


def _model() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-flash").strip() or "deepseek-flash"


def _breaker_open() -> bool:
    with _lock:
        return time.time() < _state["paused_until"]


def _fail(reason: str):
    with _lock:
        _stats["fallback"] += 1
        _stats["last_error"] = reason[:160]
        _state["fails"] += 1
        if _state["fails"] >= _BREAKER_FAILS:
            _state["paused_until"] = time.time() + _BREAKER_PAUSE
            _state["fails"] = 0
            print(f"[LLMRouter] DeepSeek: {_BREAKER_FAILS} bledy z rzedu ({reason}) - pauza {_BREAKER_PAUSE:.0f}s, wszystko na OpenAI")
    print(f"[LLMRouter] DeepSeek nie zadzialal ({reason}) - zapas: OpenAI")


def _ok():
    with _lock:
        _state["fails"] = 0
        _stats["ok"] += 1


def _ds_kwargs(kw: dict) -> dict:
    d = dict(kw)
    d["model"] = _model()
    d["extra_body"] = {"thinking": {"type": "disabled"}}
    if d.get("max_tokens"):
        d["max_tokens"] = min(int(d["max_tokens"]), _DS_MAX_TOKENS)
    return d


def _usable(resp) -> bool:
    try:
        ch = resp.choices[0]
        if getattr(ch, "finish_reason", None) == "length":
            return False
        return bool((ch.message.content or "").strip())
    except Exception:
        return False


def _record(resp):
    try:
        from . import usage_tracker
        u = resp.usage
        usage_tracker.record_extra("llm_router.deepseek", _model(), int(u.prompt_tokens or 0), int(u.completion_tokens or 0))
    except Exception:
        pass


def _client(is_async: bool):
    """Nowy klient na wywolanie (tani, a async klient zwiazany z petla zdarzen nie moze byc wspoldzielony
    miedzy petlami - asyncio.run w watkach/testach)."""
    from openai import AsyncOpenAI, OpenAI
    cls = AsyncOpenAI if is_async else OpenAI
    return cls(api_key=os.environ["DEEPSEEK_API_KEY"].strip(), base_url="https://api.deepseek.com", timeout=_DS_TIMEOUT, max_retries=0)


def create_sync(openai_client, use_deepseek: bool, **kw):
    """chat.completions.create dla klienta SYNC. use_deepseek=True tylko dla matematyki."""
    if use_deepseek and enabled() and not _breaker_open():
        try:
            r = _client(False).chat.completions.create(**_ds_kwargs(kw))
            if _usable(r):
                _record(r)
                _ok()
                return r
            _record(r)
            _fail("pusta lub urwana odpowiedz")
        except Exception as e:
            _fail(f"{type(e).__name__}: {str(e)[:120]}")
    return openai_client.chat.completions.create(**kw)


async def create_async(openai_client, use_deepseek: bool, **kw):
    """chat.completions.create dla klienta ASYNC. use_deepseek=True tylko dla matematyki."""
    if use_deepseek and enabled() and not _breaker_open():
        try:
            r = await _client(True).chat.completions.create(**_ds_kwargs(kw))
            if _usable(r):
                _record(r)
                _ok()
                return r
            _record(r)
            _fail("pusta lub urwana odpowiedz")
        except Exception as e:
            _fail(f"{type(e).__name__}: {str(e)[:120]}")
    return await openai_client.chat.completions.create(**kw)


def status() -> dict:
    """Podglad dla /health/llm - czy DeepSeek jest skonfigurowany i uzywany (bez sekretow)."""
    with _lock:
        return {
            "deepseek_key_set": bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
            "math_provider_env": os.environ.get("MATH_PROVIDER", "") or "(domyslnie)",
            "deepseek_enabled": enabled(),
            "model": _model(),
            "deepseek_ok_since_start": _stats["ok"],
            "fallback_to_openai_since_start": _stats["fallback"],
            "last_error": _stats["last_error"],
            "breaker_open": time.time() < _state["paused_until"],
        }
