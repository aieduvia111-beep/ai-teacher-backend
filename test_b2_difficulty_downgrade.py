# -*- coding: utf-8 -*-
"""User (30.08.2026): "czy to jest nieprofesjonalne" - dopytal, czy
dolozenie latwiejszej wersji zadania, gdy nawet "B1" (rozszerzenie
budzetu) zawiedzie, byloby nieprofesjonalne. Odpowiedz: TYLKO jesli
zrobione PO CICHU - jawnie ujawnione (patrz _difficulty_downgrade_notice
w tekscie), to standardowa, profesjonalna praktyka "graceful
degradation", nie oszustwo. User potwierdzil: "zrob".

"B2" - AWARYJNE wyjscie, WYLACZNIE gdy B1 rowniez nie dowiezie pelnej
liczby: JEDEN krok w dol trudnosci (ta sama tematyka), JEDNA proba,
zawsze WOLNA generacja (nie archetypy - "latwiejszy archetyp" nie ma
sensu, archetypy sa zwiazane z KONKRETNYM, trudnym wzorcem).

Ten plik testuje SAMA logike lokalnie - ZERO prawdziwych wywolan
OpenAI (mockowany klient/funkcje, identycznie jak
test_b1_grace_extension.py)."""
import sys, asyncio
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


# =====================================================================
# QUIZ (openai_exam.py) - _apply_b2_difficulty_downgrade
# =====================================================================
import app.openai_exam as oai


def _q(n, tag="a"):
    return [
        {"question": f"Pytanie {tag}{i}?", "options": ["1", "2", "3", "4"], "correct": 0,
         "final_answer": "1", "explanation": "test",
         "diversity_tag": {"skill": f"skill{tag}{i}", "concept": f"concept{tag}{i}", "task_type": "t", "reasoning": "r"}}
        for i in range(n)
    ]


class _MockChatCompletions:
    async def create(self, *a, **kw):
        raise RuntimeError("MOCK: zero prawdziwych wywolan API w tym tescie")


class _MockChat:
    completions = _MockChatCompletions()


class _MockClient:
    chat = _MockChat()


_real_client = oai.client
oai.client = _MockClient()

print("=" * 70)
print("QUIZ - Scenariusz: B1 zostawil niedobor 3/15, trudny -> B2 probuje")
print("'medium' i W PELNI domyka luke - jawne ujawnienie, BRAK shortfall_warning")
print("=" * 70)


async def _mock_regen_full():
    async def _fn(topic, forced, subject, level, n, difficulty, instr, avoid_block=""):
        return {"title": "T", "questions": _q(n, tag="b2_")}
    oai._raw_generate_quiz_topic_batch = _fn
    quiz_data = {"title": "T", "questions": _q(12), "_shortfall_warning": "Udalo sie wygenerowac 12 z 15..."}
    return await oai._apply_b2_difficulty_downgrade(
        quiz_data, requested_count=15, topic="Test", effective_topic_is_forced=True,
        subject="matematyka", level="liceum_2", difficulty="hard", wlasne_instrukcje="",
    )


result = asyncio.run(_mock_regen_full())
check("Finalnie PELNE 15/15 pytan", len(result.get("questions", [])) == 15, len(result.get("questions", [])))
check("_difficulty_downgrade_notice obecne (jawne ujawnienie)",
      "_difficulty_downgrade_notice" in result, result.get("_difficulty_downgrade_notice"))
check("Notice wspomina liczbe dolozonych (3) i oba poziomy (medium/hard)",
      "3" in result["_difficulty_downgrade_notice"] and "medium" in result["_difficulty_downgrade_notice"] and "hard" in result["_difficulty_downgrade_notice"],
      result["_difficulty_downgrade_notice"])
check("_shortfall_warning USUNIETE (B2 w pelni domknal luke - nie ma juz niedoboru)",
      "_shortfall_warning" not in result, result.get("_shortfall_warning"))

print()
print("=" * 70)
print("QUIZ - Scenariusz: B1 nie zostawil niedoboru (15/15) - B2 NIE robi")
print("nic (brak wywolania, brak notice)")
print("=" * 70)
call_count = {"n": 0}


async def _mock_should_not_be_called(*a, **kw):
    call_count["n"] += 1
    return {"title": "T", "questions": _q(5)}


async def _run_no_missing():
    oai._raw_generate_quiz_topic_batch = _mock_should_not_be_called
    quiz_data = {"title": "T", "questions": _q(15)}
    return await oai._apply_b2_difficulty_downgrade(
        quiz_data, requested_count=15, topic="Test", effective_topic_is_forced=True,
        subject="matematyka", level="liceum_2", difficulty="hard", wlasne_instrukcje="",
    )


result2 = asyncio.run(_run_no_missing())
check("Brak niedoboru -> mock NIGDY nie wywolany", call_count["n"] == 0, call_count["n"])
check("Brak _difficulty_downgrade_notice (B2 nie zadzialal, bo nie musial)",
      "_difficulty_downgrade_notice" not in result2, result2.get("_difficulty_downgrade_notice"))

print()
print("=" * 70)
print("QUIZ - Scenariusz: temat juz na NAJLATWIEJSZYM poziomie ('easy') -")
print("B2 nie ma gdzie schodzic, NIE probuje wcale (mimo niedoboru)")
print("=" * 70)
call_count2 = {"n": 0}


async def _mock_should_not_fire():
    call_count2["n"] += 1
    return {"title": "T", "questions": _q(5)}


async def _run_already_easiest():
    oai._raw_generate_quiz_topic_batch = _mock_should_not_fire
    quiz_data = {"title": "T", "questions": _q(10)}
    return await oai._apply_b2_difficulty_downgrade(
        quiz_data, requested_count=15, topic="Test", effective_topic_is_forced=True,
        subject="matematyka", level="liceum_2", difficulty="easy", wlasne_instrukcje="",
    )


result3 = asyncio.run(_run_already_easiest())
check("'easy' (najlatwiejszy) -> mock NIGDY nie wywolany (brak gdzie schodzic)",
      call_count2["n"] == 0, call_count2["n"])
check("Niedobor pozostaje 10/15 (B2 sie nie uruchomil)",
      len(result3.get("questions", [])) == 10, len(result3.get("questions", [])))

print()
print("=" * 70)
print("QUIZ - Scenariusz: B2 CZESCIOWO domyka luke (zwrocono mniej niz")
print("brakowalo) - notice nadal sie pojawia, ale _shortfall_warning ZOSTAJE")
print("(nadal niedobor, mimo proby B2)")
print("=" * 70)


async def _mock_partial():
    async def _fn(topic, forced, subject, level, n, difficulty, instr, avoid_block=""):
        return {"title": "T", "questions": _q(2, tag="partial_")}  # mniej niz brakuje (5)
    oai._raw_generate_quiz_topic_batch = _fn
    quiz_data = {"title": "T", "questions": _q(10), "_shortfall_warning": "Udalo sie wygenerowac 10 z 15..."}
    return await oai._apply_b2_difficulty_downgrade(
        quiz_data, requested_count=15, topic="Test", effective_topic_is_forced=True,
        subject="matematyka", level="liceum_2", difficulty="medium", wlasne_instrukcje="",
    )


result4 = asyncio.run(_mock_partial())
check("Czesciowe domkniecie: 12/15 (10 + 2 dodane przez B2, nie pelne 15)",
      len(result4.get("questions", [])) == 12, len(result4.get("questions", [])))
check("_difficulty_downgrade_notice obecne (2 dodane, mimo ze nie domknelo calosci)",
      "_difficulty_downgrade_notice" in result4, result4.get("_difficulty_downgrade_notice"))
check("_shortfall_warning WCIAZ obecne (nadal niedobor mimo proby B2)",
      "_shortfall_warning" in result4, result4.get("_shortfall_warning"))

print()
print("=" * 70)
print("QUIZ - Regresja: mapa stopni w dol jest 'jeden krok', nie kaskada -")
print("'hard'->'medium' (NIE od razu 'easy')")
print("=" * 70)
check("_step_down_difficulty('hard') == 'medium'", oai._step_down_difficulty("hard") == "medium", oai._step_down_difficulty("hard"))
check("_step_down_difficulty('trudna') == 'srednia'", oai._step_down_difficulty("trudna") == "srednia", oai._step_down_difficulty("trudna"))
check("_step_down_difficulty('medium') == 'easy'", oai._step_down_difficulty("medium") == "easy", oai._step_down_difficulty("medium"))
check("_step_down_difficulty('easy') is None (juz najlatwiejszy)", oai._step_down_difficulty("easy") is None, oai._step_down_difficulty("easy"))
check("_step_down_difficulty('cos_nieznanego') is None (bezpieczny abstain)", oai._step_down_difficulty("cos_nieznanego") is None)

oai.client = _real_client

print()
print("=" * 70)
print("WYNIK CZESCI QUIZ:", "0 bledow" if not FAILED else f"{len(FAILED)} bledow")
print("=" * 70)

# =====================================================================
# SPRAWDZIAN (exam_pdf_generator.py) - _apply_b2_difficulty_downgrade
# =====================================================================
import app.exam_pdf_generator as epg

gen = epg.ExamGenerator(openai_api_key="fake-key-not-used-in-this-test")


def _make_closed(n, start_nr=1):
    return [
        {"nr": start_nr + i, "tresc": f"P{start_nr + i}", "opcje": ["a) 1", "b) 2", "c) 3", "d) 4"],
         "odpowiedz": "a", "final_answer": "1", "punkty": 1}
        for i in range(n)
    ]


def _make_open(n, start_nr=100):
    return [
        {"nr": start_nr + i, "tresc": f"Z{start_nr + i}", "punkty": 4, "odpowiedz_modelowa": "x", "final_answer": str(i)}
        for i in range(n)
    ]


print()
print("=" * 70)
print("SPRAWDZIAN - Scenariusz: B1 zostawil niedobor 2/15 (7 zamkniete,")
print("6 otwarte = 13), target_closed=9 wiec headroom=2 - B2 probuje")
print("'srednia' zamiast 'trudna' i W PELNI domyka luke")
print("=" * 70)
gen._get_exam_data_raw_parallel = lambda temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block="", only_open=False: {
    "sekcje": [{"typ": "otwarte" if only_open else "zamkniete", "pytania": (_make_open(n, start_nr=900) if only_open else _make_closed(n, start_nr=900))}]
}
data = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(7)},
    {"typ": "otwarte", "pytania": _make_open(6)},
], "_shortfall_warning": "Udalo sie wygenerowac 13 z 15..."}
result_e1 = gen._apply_b2_difficulty_downgrade(data, temat="Test", klasa="liceum_2", trudnosc="trudna", liczba_pytan=15, wlasne_instrukcje=None, przedmiot="Matematyka")
final_total_e1 = sum(len(s["pytania"]) for s in result_e1["sekcje"])
check("Finalnie PELNE 15/15 zadan", final_total_e1 == 15, final_total_e1)
check("_difficulty_downgrade_notice obecne", "_difficulty_downgrade_notice" in result_e1, result_e1.get("_difficulty_downgrade_notice"))
check("_shortfall_warning USUNIETE (B2 w pelni domknal luke)",
      "_shortfall_warning" not in result_e1, result_e1.get("_shortfall_warning"))
check("punkty_lacznie przeliczone poprawnie (9x1pkt zamkniete [7+2 z B2] + 6x4pkt otwarte = 33)",
      result_e1.get("punkty_lacznie") == 33, result_e1.get("punkty_lacznie"))

print()
print("=" * 70)
print("SPRAWDZIAN - Scenariusz: brak niedoboru (15/15) - B2 nie robi nic")
print("=" * 70)
call_count_e = {"n": 0}
gen._get_exam_data_raw_parallel = lambda *a, **kw: (call_count_e.__setitem__("n", call_count_e["n"] + 1), {"sekcje": []})[1]
data2 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(9)},
    {"typ": "otwarte", "pytania": _make_open(6)},
]}
result_e2 = gen._apply_b2_difficulty_downgrade(data2, temat="Test", klasa="liceum_2", trudnosc="trudna", liczba_pytan=15, wlasne_instrukcje=None, przedmiot="Matematyka")
check("Brak niedoboru -> mock NIGDY nie wywolany", call_count_e["n"] == 0, call_count_e["n"])

print()
print("=" * 70)
print("SPRAWDZIAN - Scenariusz: 'latwa' (najlatwiejszy poziom) - B2 nie ma")
print("gdzie schodzic, nie probuje wcale")
print("=" * 70)
call_count_e2 = {"n": 0}
gen._get_exam_data_raw_parallel = lambda *a, **kw: (call_count_e2.__setitem__("n", call_count_e2["n"] + 1), {})[1]
data3 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(5)},
    {"typ": "otwarte", "pytania": _make_open(3)},
]}
result_e3 = gen._apply_b2_difficulty_downgrade(data3, temat="Test", klasa="liceum_2", trudnosc="latwa", liczba_pytan=15, wlasne_instrukcje=None, przedmiot="Matematyka")
check("'latwa' -> mock NIGDY nie wywolany", call_count_e2["n"] == 0, call_count_e2["n"])

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
