# -*- coding: utf-8 -*-
"""Offline (zero AI, zero sieci): batchowanie AI-2 (slepego sedziego) dla quizu (22.09.2026, KOSZTY -
real prod: 3621 osobnych wywolan/dzien, jedno na KAZDE pytanie zamkniete). Sprawdza: liczba wywolan
API spada (grupowanie po problem_class + chunk), wynik i KOLEJNOSC identyczne z semantyka "1 pytanie =
1 wywolanie", fail-closed per-pytanie (blad calego chunku/pojedynczego numeru -> False TYLKO dla tego
pytania, nie zaraza reszty), validation_rule nadal rozstrzyga bez AI, prompt trzyma pytania w osobnych,
kluczowanych numerem blokach (zero mieszania odpowiedzi miedzy pytaniami)."""
import os, sys, io, asyncio, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from app.blind_verify import build_blind_verify_prompt_closed_batch
import app.openai_exam as oe

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))


def q(id_, correct_letter, correct_idx, problem_class=None, validation_rule=None, final_answer=None):
    letters = "abcd"
    return {"id": id_, "question": f"Pytanie {id_}?", "options": [f"opcja {l}" for l in letters],
            "correct": correct_idx, "problem_class": problem_class,
            "validation_rule": validation_rule, "final_answer": final_answer}


class FakeClient:
    """Kazde wywolanie zwraca odpowiedz zaprogramowana w `script` (lista, kolejno per-call).
    Zapisuje wszystkie wyslane prompty do `.calls`."""
    def __init__(self, script):
        self.script = list(script); self.calls = []
        self.chat = type("C", (), {"completions": type("Cm", (), {"create": self._create})()})()
    async def _create(self, **kw):
        self.calls.append(kw)
        content = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if isinstance(content, Exception):
            raise content
        msg = type("M", (), {"content": content})()
        return type("R", (), {"choices": [type("Ch", (), {"message": msg})()]})()


async def run():
    # ---- 1) liczba wywolan API spada (7 pytan tej samej klasy -> ceil(7/5)=2 chunki, nie 7) ----
    cands = [q(i, "a", 0) for i in range(1, 8)]
    resp = json.dumps({str(i): {"odpowiedz": "a"} for i in range(1, 6)})  # dla chunka do 5
    client = FakeClient([json.dumps({"1": {"odpowiedz": "a"}, "2": {"odpowiedz": "a"}, "3": {"odpowiedz": "a"}, "4": {"odpowiedz": "a"}, "5": {"odpowiedz": "a"}}),
                         json.dumps({"1": {"odpowiedz": "a"}, "2": {"odpowiedz": "a"}})])
    out = await oe._blind_verify_batch_closed_quiz(cands, client=client, topic="t")
    check("7 pytan tej samej klasy -> 2 wywolania API (nie 7)", len(client.calls) == 2, len(client.calls))
    check("wszystkie 7 zaakceptowane (AI-2 zgadza sie z kazdym)", out == [True] * 7, out)

    # ---- 2) kolejnosc i przypisanie wynikow trzyma sie NUMERU, nie pozycji - jeden bledny w srodku nie zaraza reszty ----
    cands2 = [q(1, "a", 0), q(2, "b", 1), q(3, "c", 2), q(4, "d", 3)]
    # AI-2: 1=a(zgadza), 2=x(niepoprawna litera - blad TYLKO tego pytania), 3=c(zgadza), 4=a(NIE zgadza sie z "d")
    resp2 = json.dumps({"1": {"odpowiedz": "a"}, "2": {"odpowiedz": "x"}, "3": {"odpowiedz": "c"}, "4": {"odpowiedz": "a"}})
    client2 = FakeClient([resp2])
    out2 = await oe._blind_verify_batch_closed_quiz(cands2, client=client2, topic="t")
    check("pytanie 1 (zgadza sie) -> True", out2[0] is True, out2)
    check("pytanie 2 (AI-2 zwrocilo nieprawidlowa litere) -> False, NIE zaraza pozostalych", out2[1] is False, out2)
    check("pytanie 3 (zgadza sie) -> True", out2[2] is True, out2)
    check("pytanie 4 (AI-2 NIE zgadza sie z oznaczona odpowiedzia) -> False", out2[3] is False, out2)

    # ---- 3) grupowanie wg problem_class: factual i matematyczne NIE trafiaja do jednego wywolania ----
    mixed = [q(1, "a", 0, problem_class="factual"), q(2, "a", 0, problem_class="factual"),
             q(3, "a", 0, problem_class=None), q(4, "a", 0, problem_class=None)]
    client3 = FakeClient([json.dumps({"1": {"odpowiedz": "a"}, "2": {"odpowiedz": "a"}}),
                          json.dumps({"1": {"odpowiedz": "a"}, "2": {"odpowiedz": "a"}})])
    out3 = await oe._blind_verify_batch_closed_quiz(mixed, client=client3, topic="t")
    check("factual i matematyczne w OSOBNYCH wywolaniach (2 calls, nie 1)", len(client3.calls) == 2, len(client3.calls))
    check("wszystkie 4 poprawnie zweryfikowane mimo podzialu na grupy", out3 == [True, True, True, True], out3)
    system_msgs = [c["messages"][0]["content"] for c in client3.calls]
    check("jedno wywolanie uzywa promptu FAKTOGRAFICZNEGO, drugie MATEMATYCZNEGO", set(system_msgs) == {oe.BLIND_VERIFY_SYSTEM_PROMPT, oe.BLIND_VERIFY_SYSTEM_PROMPT_FACTUAL}, system_msgs)

    # ---- 4) fail-closed: caly blad wywolania -> caly chunk False (nie crash, nie True) ----
    cands4 = [q(1, "a", 0), q(2, "a", 0)]
    client4 = FakeClient([RuntimeError("timeout")])
    out4 = await oe._blind_verify_batch_closed_quiz(cands4, client=client4, topic="t")
    check("blad calego wywolania API -> caly chunk False (fail-closed)", out4 == [False, False], out4)

    # ---- 5) niepoprawny JSON (nie dict) -> caly chunk False ----
    client5 = FakeClient(['"nie jest to obiekt JSON"'])
    out5 = await oe._blind_verify_batch_closed_quiz([q(1, "a", 0)], client=client5, topic="t")
    check("odpowiedz AI-2 nie jest obiektem JSON -> False (fail-closed)", out5 == [False], out5)

    # ---- 6) brakujacy numer w odpowiedzi (AI-2 pominelo jedno pytanie) -> TYLKO to pytanie False ----
    client6 = FakeClient([json.dumps({"1": {"odpowiedz": "a"}})])  # brak "2"
    out6 = await oe._blind_verify_batch_closed_quiz([q(1, "a", 0), q(2, "a", 0)], client=client6, topic="t")
    check("brakujacy numer w odpowiedzi AI-2 -> TYLKO to jedno pytanie False", out6 == [True, False], out6)

    # ---- 7) validation_rule nadal rozstrzyga BEZ zadnego wywolania AI ----
    vr_ok = {"variables": {"a": 2, "b": 3}, "expression": "a+b", "expected": 5}
    cands7 = [q(1, "a", 0, validation_rule=vr_ok, final_answer="5")]
    client7 = FakeClient(["SENTINEL_SHOULD_NOT_BE_CALLED"])
    out7 = await oe._blind_verify_batch_closed_quiz(cands7, client=client7, topic="t")
    check("validation_rule poprawny -> True, ZERO wywolan AI", out7 == [True] and len(client7.calls) == 0, (out7, len(client7.calls)))

    # ---- 8) mieszanka: czesc rozstrzygnieta przez validation_rule, reszta przez AI-2 (jedno wywolanie tylko na reszte) ----
    cands8 = [q(1, "a", 0, validation_rule=vr_ok, final_answer="5"), q(2, "b", 1), q(3, "c", 2)]
    client8 = FakeClient([json.dumps({"1": {"odpowiedz": "b"}, "2": {"odpowiedz": "c"}})])
    out8 = await oe._blind_verify_batch_closed_quiz(cands8, client=client8, topic="t")
    check("mieszanka: 1 wywolanie AI tylko dla 2 nierozstrzygnietych (nie 3)", len(client8.calls) == 1, len(client8.calls))
    sent_prompt = client8.calls[0]["messages"][1]["content"]
    check("prompt wyslany do AI zawiera TYLKO 2 nierozstrzygniete pytania (nie 3, nie to z validation_rule)", "Pytanie 2?" in sent_prompt and "Pytanie 3?" in sent_prompt and "Pytanie 1?" not in sent_prompt, sent_prompt[:200])
    check("wszystkie 3 poprawnie zweryfikowane (1 przez kod, 2-3 przez AI-2)", out8 == [True, True, True], out8)

    # ---- 9) pusta lista -> pusta lista, zero wywolan ----
    out9 = await oe._blind_verify_batch_closed_quiz([], client=FakeClient([]), topic="t")
    check("pusta lista kandydatow -> pusta lista", out9 == [])

    # ---- 10) brak klienta (client=None) -> fail-closed False dla wszystkich nierozstrzygnietych ----
    out10 = await oe._blind_verify_batch_closed_quiz([q(1, "a", 0), q(2, "a", 0)], client=None, topic="t")
    check("client=None -> fail-closed False dla wszystkich (bez validation_rule)", out10 == [False, False], out10)

asyncio.run(run())

# ---- prompt wsadowy: struktura, brak mieszania, klucze-numery ----
p = build_blind_verify_prompt_closed_batch([("Ile to 2+2?", ["3", "4", "5", "6"]), ("Stolica Polski?", ["Krakow", "Warszawa", "Lodz", "Poznan"])])
check("prompt wsadowy zawiera OBA pytania z numerami", "Zadanie 1:" in p and "Zadanie 2:" in p, p[:200])
check("prompt wsadowy prosi o JSON kluczowany numerami '1' i '2'", '"1"' in p and '"2"' in p, p[-300:])
p_fact = build_blind_verify_prompt_closed_batch([("Kto napisal Pana Tadeusza?", ["Slowacki", "Mickiewicz"])], problem_class="factual")
check("wariant factual uzywa ramy faktograficznej (bez 'krok po kroku')", "faktow/wiedzy" in p_fact and "krok po kroku" not in p_fact, p_fact[:200])

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
