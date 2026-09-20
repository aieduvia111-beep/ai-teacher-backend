# -*- coding: utf-8 -*-
"""Offline (zero AI, zero sieci): routing matematyki do DeepSeek z zapasem na OpenAI - kiedy DeepSeek,
kiedy OpenAI, zapas przy bledach (402/401/429/timeout/pusta/urwana odpowiedz), wylacznik po serii bledow,
parametry wysylane do DeepSeek i NIEZMIENIONE parametry zapasu."""
import os, sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

import app.llm_router as lr

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))


class Msg:  # minimalna odpowiedz
    def __init__(self, content, finish="stop", model="x"):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})(), "finish_reason": finish})()]
        self.usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 5})()
        self.model = model


class FakeClient:
    """Udaje OpenAI/DeepSeek (sync i async). behavior: lista wynikow kolejnych wywolan (Msg albo wyjatek)."""
    def __init__(self, behavior, is_async=False):
        self.calls, self.behavior, self._i = [], list(behavior), 0
        create = self._acreate if is_async else self._create
        self.chat = type("Chat", (), {"completions": type("Comp", (), {"create": staticmethod(create)})()})()
    def _next(self, kw):
        self.calls.append(kw)
        b = self.behavior[min(self._i, len(self.behavior) - 1)]; self._i += 1
        if isinstance(b, Exception): raise b
        return b
    def _create(self, **kw): return self._next(kw)
    async def _acreate(self, **kw): return self._next(kw)


def reset():
    lr._state.update({"fails": 0, "paused_until": 0.0})
    for k in ("DEEPSEEK_API_KEY", "MATH_PROVIDER", "DEEPSEEK_MODEL"): os.environ.pop(k, None)

DS = {"c": None}
lr._client = lambda is_async: DS["c"]
lr._record = lambda resp: None

KW = dict(model="gpt-4o-mini", messages=[{"role": "user", "content": "json"}], temperature=0.5, max_tokens=12000, response_format={"type": "json_object"})

# ---- is_math ----
check("is_math: przedmiot Matematyka", lr.is_math("Matematyka", "x") is True)
check("is_math: przedmiot pusty, temat 'Matematyka: Ciagi'", lr.is_math(None, "Matematyka: Ciągi") is True)
check("is_math: Historia -> nie", lr.is_math("Historia", "Matematyka w historii") is False)
check("is_math: brak danych -> nie", lr.is_math(None, None) is False)

# ---- bez klucza: zero zmian ----
reset(); DS["c"] = FakeClient([Msg("ds")]); oa = FakeClient([Msg("oa")])
r = lr.create_sync(oa, True, **KW)
check("brak DEEPSEEK_API_KEY: wszystko na OpenAI, DeepSeek nietkniety", r.choices[0].message.content == "oa" and not DS["c"].calls)

# ---- klucz + matematyka: DeepSeek ----
reset(); os.environ["DEEPSEEK_API_KEY"] = "sk-test"
DS["c"] = FakeClient([Msg("ds")]); oa = FakeClient([Msg("oa")])
r = lr.create_sync(oa, True, **KW)
kw = DS["c"].calls[0] if DS["c"].calls else {}
check("matematyka + klucz: odpowiada DeepSeek, OpenAI nietkniety", r.choices[0].message.content == "ds" and not oa.calls)
check("DeepSeek dostaje model deepseek-flash, thinking wylaczone, max_tokens<=8192, reszta parametrow bez zmian",
      kw.get("model") == "deepseek-flash" and kw.get("extra_body") == {"thinking": {"type": "disabled"}} and kw.get("max_tokens") == 8192
      and kw.get("temperature") == 0.5 and kw.get("response_format") == {"type": "json_object"}, kw)
check("oryginalne KW nie zostaly zmodyfikowane (zapas dostaje gpt-4o-mini i max_tokens=12000)", KW["model"] == "gpt-4o-mini" and KW["max_tokens"] == 12000 and "extra_body" not in KW)

# ---- nie-matematyka i przelacznik ----
reset(); os.environ["DEEPSEEK_API_KEY"] = "sk-test"; DS["c"] = FakeClient([Msg("ds")]); oa = FakeClient([Msg("oa")])
r = lr.create_sync(oa, False, **KW)
check("nie-matematyka: OpenAI mimo klucza", r.choices[0].message.content == "oa" and not DS["c"].calls)
os.environ["MATH_PROVIDER"] = "openai"; oa = FakeClient([Msg("oa")])
r = lr.create_sync(oa, True, **KW)
check("MATH_PROVIDER=openai wylacza DeepSeek", r.choices[0].message.content == "oa" and not DS["c"].calls)

# ---- zapas przy bledach ----
for label, err in (("brak srodkow 402", RuntimeError("Error code: 402 - Insufficient Balance")), ("zly klucz 401", RuntimeError("401")),
                   ("limit 429", RuntimeError("429")), ("timeout", TimeoutError("timeout")),
                   ("pusta odpowiedz", Msg("")), ("urwana (length)", Msg("{", finish="length"))):
    reset(); os.environ["DEEPSEEK_API_KEY"] = "sk-test"; DS["c"] = FakeClient([err]); oa = FakeClient([Msg("oa")])
    r = lr.create_sync(oa, True, **KW)
    check(f"zapas na OpenAI przy: {label}", r.choices[0].message.content == "oa" and len(oa.calls) == 1 and oa.calls[0]["model"] == "gpt-4o-mini", (r.choices[0].message.content, oa.calls))

# ---- wylacznik po serii bledow ----
reset(); os.environ["DEEPSEEK_API_KEY"] = "sk-test"; DS["c"] = FakeClient([RuntimeError("402")]); oa = FakeClient([Msg("oa")])
for _ in range(3): lr.create_sync(oa, True, **KW)
n_ds = len(DS["c"].calls)
lr.create_sync(oa, True, **KW)
check("po 3 bledach z rzedu DeepSeek jest omijany (4. wywolanie nie dotyka DeepSeek)", n_ds == 3 and len(DS["c"].calls) == 3 and len(oa.calls) == 4, (n_ds, len(DS["c"].calls), len(oa.calls)))
lr._state["paused_until"] = 0.0
DS["c"] = FakeClient([Msg("ds")])
r = lr.create_sync(oa, True, **KW)
check("po uplywie pauzy DeepSeek wraca", r.choices[0].message.content == "ds")

# ---- sukces zeruje licznik bledow ----
reset(); os.environ["DEEPSEEK_API_KEY"] = "sk-test"; DS["c"] = FakeClient([RuntimeError("x"), RuntimeError("x"), Msg("ds"), RuntimeError("x"), RuntimeError("x"), Msg("ds")]); oa = FakeClient([Msg("oa")])
outs = [lr.create_sync(oa, True, **KW).choices[0].message.content for _ in range(6)]
check("sukces zeruje serie bledow (wylacznik sie nie wlacza przy 2+2 bledach)", len(DS["c"].calls) == 6 and outs == ["oa", "oa", "ds", "oa", "oa", "ds"], (outs, len(DS["c"].calls)))

# ---- async ----
async def run_async():
    reset(); os.environ["DEEPSEEK_API_KEY"] = "sk-test"
    DS["c"] = FakeClient([Msg("ds")], is_async=True); oa = FakeClient([Msg("oa")], is_async=True)
    r1 = await lr.create_async(oa, True, **KW)
    DS["c"] = FakeClient([RuntimeError("402")], is_async=True); oa = FakeClient([Msg("oa")], is_async=True)
    r2 = await lr.create_async(oa, True, **KW)
    DS["c"] = FakeClient([Msg("ds")], is_async=True); oa2 = FakeClient([Msg("oa")], is_async=True)
    r3 = await lr.create_async(oa2, False, **KW)
    return r1.choices[0].message.content, r2.choices[0].message.content, r3.choices[0].message.content
a = asyncio.run(run_async())
check("async: matematyka -> DeepSeek; blad -> OpenAI; nie-matematyka -> OpenAI", a == ("ds", "oa", "oa"), a)

# ---- podpiecie w kodzie ----
src_q = open("app/openai_exam.py", encoding="utf-8").read()
src_e = open("app/exam_pdf_generator.py", encoding="utf-8").read()
check("quiz: glowne generowanie idzie przez router z is_math(subject, topic)", "_llm_router.create_async(\n        client, _llm_router.is_math(subject, topic)," in src_q.replace("\r\n", "\n"))
check("sprawdzian: glowne generowanie idzie przez router z is_math(przedmiot, temat)", "_llm_router.is_math(przedmiot, temat)" in src_e)

reset()
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
