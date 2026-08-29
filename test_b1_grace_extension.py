# -*- coding: utf-8 -*-
"""User (29.08.2026, po alarmie kosztowym - "0.20 USD w OpenAI"): "B1" -
gdy standardowy budzet czasu/rund sie wyczerpie, ale brakuje NAPRAWDE
niewiele (<=2 zadania z zamowionych), daj do 3 dodatkowych rund zamiast
od razu poddawac sie z niedoborem - ale TWARDO ograniczone (sufit 220s
CALKOWITEGO czasu, max 3 rundy, i NIE probuj wcale jesli brakuje >2 -
"jesli 10 rund nie wystarczylo na cos wiecej niz 2 zadania, temat ma
fundamentalny problem, dalsze czekanie nie pomoze").

WASKI, WARUNKOWY wyjatek - NIE ogolne podniesienie limitu dla kazdego
requestu (to user JUZ ODRZUCIL na starcie tej sesji jako nieskuteczne).

Ten plik testuje SAMA logike lokalnie/mockowane - ZERO prawdziwych
wywolan OpenAI (user ma $0 w OpenAI w momencie pisania tego testu,
real-API testy sa WYKLUCZONE). Kontrola czasu przez podmiane
time.monotonic() na sterowalny "falszywy zegar" (bez prawdziwego
czekania), API mockowane identycznie jak w
test_exam_open_closed_ratio.py (fake_key wywoluje blad autoryzacji w
Warstwie 2.5, ktora jest zaprojektowana "fail open" - przy bledzie
wywolania zaklada TRUE/"zgadza sie", wiec pytanie przechodzi bez
prawdziwego kontaktu z siecia)."""
import sys, asyncio
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


class FakeClock:
    """Podmienia time.monotonic() w module - pozwala precyzyjnie
    kontrolowac 'uplyniety czas' bez prawdziwego czekania."""
    def __init__(self, start=0.0):
        self.t = start

    def monotonic(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


# =====================================================================
# SPRAWDZIAN (exam_pdf_generator.py) - _fill_missing_exam_questions
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


print("=" * 70)
print("SPRAWDZIAN - Scenariusz: brakuje 2/15 gdy standardowy budzet (180s)")
print("juz wyczerpany (elapsed=200s) - grace POWINIEN zadzialac i dobic")
print("=" * 70)
clock = FakeClock(start=0.0)
epg.time.monotonic = clock.monotonic
call_count = {"n": 0}


def _mock_succeeds(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block=""):
    call_count["n"] += 1
    clock.advance(5)  # symuluje czas trwania rundy (krotki, zeby nie zblizyc sie do sufitu 220s)
    return {"sekcje": [{"typ": "zamkniete", "pytania": _make_closed(n, start_nr=100 + call_count["n"] * 10)}]}


gen._get_exam_data_raw_parallel = _mock_succeeds
data = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(7)},
    {"typ": "otwarte", "pytania": _make_open(6)},
]}
# t_start w PRZESZLOSCI wzgledem zegara -> elapsed = 0 - (-200) = 200s (juz > 180s standardowego budzetu, < 220s sufitu grace)
result = gen._fill_missing_exam_questions(
    data, temat="Matematyka: temat spoza listy archetypow", klasa="liceum_2",
    trudnosc="trudna", liczba_pytan=15, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=-200.0,
)
final_total = sum(len(s["pytania"]) for s in result["sekcje"])
check("Grace zadzialal - finalnie PELNE 15/15 (mimo ze standardowy budzet byl juz wyczerpany na starcie)",
      final_total == 15, final_total)
check("Brak _shortfall_warning (grace w pelni pokryl niedobor)",
      "_shortfall_warning" not in result, result.get("_shortfall_warning"))
check("Mock wywolany dokladnie 1 raz (missing=2, jedna runda grace wystarczyla)",
      call_count["n"] == 1, call_count["n"])

print()
print("=" * 70)
print("SPRAWDZIAN - Scenariusz: brakuje 7/15 (>2) gdy standardowy budzet")
print("juz wyczerpany - grace NIE POWINIEN probowac wcale (za duzy niedobor)")
print("=" * 70)
clock2 = FakeClock(start=0.0)
epg.time.monotonic = clock2.monotonic
call_count2 = {"n": 0}


def _mock_should_not_be_called(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block=""):
    call_count2["n"] += 1
    return {"sekcje": [{"typ": "zamkniete", "pytania": _make_closed(n)}]}


gen._get_exam_data_raw_parallel = _mock_should_not_be_called
data2 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(5)},
    {"typ": "otwarte", "pytania": _make_open(3)},
]}
result2 = gen._fill_missing_exam_questions(
    data2, temat="Matematyka: temat spoza listy archetypow", klasa="liceum_2",
    trudnosc="trudna", liczba_pytan=15, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=-200.0,
)
final_total2 = sum(len(s["pytania"]) for s in result2["sekcje"])
check("Grace NIE probowal (missing=7>2) - mock NIGDY nie wywolany",
      call_count2["n"] == 0, call_count2["n"])
check("Niedobor pozostaje 8/15 (5+3, bez zadnej proby grace)",
      final_total2 == 8, final_total2)
check("_shortfall_warning obecne, BEZ wzmianki o dodatkowych probach rozszerzenia (grace nie bylo)",
      "_shortfall_warning" in result2 and "dodatkowych prob rozszerzenia" not in result2["_shortfall_warning"],
      result2.get("_shortfall_warning"))

print()
print("=" * 70)
print("SPRAWDZIAN - Scenariusz: brakuje 2/15, ale sufit 220s JUZ przekroczony")
print("(elapsed=225s) - grace NIE POWINIEN probowac (poza absolutnym sufitem)")
print("=" * 70)
clock3 = FakeClock(start=0.0)
epg.time.monotonic = clock3.monotonic
call_count3 = {"n": 0}
gen._get_exam_data_raw_parallel = lambda *a, **kw: (call_count3.__setitem__("n", call_count3["n"] + 1), {"sekcje": [{"typ": "zamkniete", "pytania": _make_closed(2)}]})[1]
data3 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(7)},
    {"typ": "otwarte", "pytania": _make_open(6)},
]}
result3 = gen._fill_missing_exam_questions(
    data3, temat="Matematyka: temat spoza listy archetypow", klasa="liceum_2",
    trudnosc="trudna", liczba_pytan=15, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=-225.0,
)
check("Sufit 220s juz przekroczony na starcie -> mock NIGDY nie wywolany",
      call_count3["n"] == 0, call_count3["n"])

print()
print("=" * 70)
print("SPRAWDZIAN - Scenariusz: brakuje 2/15, grace probuje ale temat NIGDY")
print("nie dostarcza uzywalnych zadan - zatrzymuje sie po dokladnie 3 rundach")
print("grace (nie w nieskonczonosc), z uczciwym komunikatem wspominajacym probe")
print("=" * 70)
clock4 = FakeClock(start=0.0)
epg.time.monotonic = clock4.monotonic
call_count4 = {"n": 0}


def _mock_always_empty(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block=""):
    call_count4["n"] += 1
    clock4.advance(5)
    return {"sekcje": [{"typ": "zamkniete", "pytania": []}]}  # nigdy nic uzywalnego


gen._get_exam_data_raw_parallel = _mock_always_empty
data4 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(7)},
    {"typ": "otwarte", "pytania": _make_open(6)},
]}
result4 = gen._fill_missing_exam_questions(
    data4, temat="Matematyka: temat spoza listy archetypow", klasa="liceum_2",
    trudnosc="trudna", liczba_pytan=15, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=-200.0,
)
check("Zatrzymalo sie po DOKLADNIE 3 probach grace (nie w nieskonczonosc)",
      call_count4["n"] == 3, call_count4["n"])
check("_shortfall_warning wspomina '3 dodatkowych prob rozszerzenia' (transparentnosc)",
      "_shortfall_warning" in result4 and "3 dodatkowych prob rozszerzenia" in result4["_shortfall_warning"],
      result4.get("_shortfall_warning"))

epg.time.monotonic = __import__("time").monotonic  # przywroc prawdziwy zegar

print()
print("=" * 70)
print("WYNIK CZESCI SPRAWDZIAN:", "0 bledow" if not FAILED else f"{len(FAILED)} bledow")
print("=" * 70)

# =====================================================================
# QUIZ (openai_exam.py) - _verify_and_fill_quiz_math
# =====================================================================
import app.openai_exam as oai


class _MockChatCompletions:
    """Bezpiecznik: gwarantuje ZERO prawdziwych polaczen sieciowych,
    niezaleznie od tego, ktora sciezka kodu probuje wywolac AI (np.
    Warstwa 2.5 blind-verify uzywa GLOBALNEGO oai.client, nie parametru -
    w przeciwienstwie do ExamGenerator, gdzie fake_key wystarczal).
    Rzuca natychmiast (bez opoznienia), identycznie jak realny blad sieci -
    Warstwa 2.5 jest zaprojektowana 'fail open' (przy bledzie zaklada
    TRUE/'zgadza sie'), wiec pytania i tak przechodza."""
    async def create(self, *a, **kw):
        raise RuntimeError("MOCK: zero prawdziwych wywolan API w tym tescie")


class _MockChat:
    completions = _MockChatCompletions()


class _MockOpenAIClient:
    chat = _MockChat()


# NAPRAWIONE (dwie nieudane proby wczesniej w tym samym pliku): tokenizer
# Diversity Engine (diversity_tag_tokens, math_verify.py) uzywa
# _DIVERSITY_NON_WORD_RE = r'[^a-ząćęłńóśźż]+' - USUWA WSZYSTKIE CYFRY
# jako "nie-slowo" PRZED porownaniem Jaccarda. Zarowno numerowane
# sufiksy DOKLEJONE do slowa ("liniowe_r1" -> po strip cyfr zostaje
# "liniowe", IDENTYCZNE z oryginalem) JAK I calkowicie unikalne slowa z
# CYFRA w srodku ("umiejetnosctestowa24") kolapsuja do tego samego
# tokenu bez cyfr - obie pierwsze proby dawaly FALSZYWE odrzucenia
# Diversity Engine (mimo zera prawdziwych wywolan sieciowych). Jedyny
# bezpieczny sposob: PULA naprawde roznych (bez wspolnego rdzenia) slow
# ZLOZONYCH WYLACZNIE Z LITER, wybieranych przez offset (CALY inny wpis
# puli), nigdy przez dopisanie cyfry/sufiksu do tego samego slowa.
_DIVERSE_TOPICS = [
    ("rownania", "izolacja", "rozwiaz"),
    ("funkcje", "wierzcholek", "wyznacz"),
    ("trygonometria", "tozsamosc", "oblicz"),
    ("ciagi", "rekurencja", "wypisz"),
    ("geometria", "pole", "policz"),
    ("logarytmy", "podstawa", "uprosc"),
    ("prawdopodobienstwo", "zdarzenie", "oszacuj"),
    ("stereometria", "objetosc", "zmierz"),
    ("pochodne", "lancuch", "zroznicz"),
    ("statystyka", "srednia", "usrednij"),
    ("wektory", "iloczyn", "pomnoz"),
    ("macierze", "wyznacznik", "przeksztalc"),
    ("zespolone", "modul", "zapisz"),
    ("kombinatoryka", "permutacja", "przelicz"),
    ("nierownosci", "modul", "porownaj"),
]  # 15 wpisow, KAZDY o calkowicie innym rdzeniu slownym (zero wspoldzielonych liter-tokenow)


def _make_quiz_questions(n, offset=0):
    """`offset` wybiera CALY INNY wpis puli (nie dokleja nic do tego
    samego slowa) - partie z roznych rund MUSZA uzywac roznych offsetow,
    zeby nie kolidowaly ze soba (patrz komentarz wyzej)."""
    result = []
    for i in range(n):
        skill, concept, task = _DIVERSE_TOPICS[(offset + i) % len(_DIVERSE_TOPICS)]
        result.append({
            "question": f"Pytanie o {skill} numer {offset + i}?",
            "options": ["1", "2", "3", "4"],
            "correct": 0, "final_answer": "1", "explanation": "test",
            "diversity_tag": {"skill": skill, "concept": concept, "task_type": task, "reasoning": "brak"},
        })
    return result


_real_oai_client = oai.client
oai.client = _MockOpenAIClient()


print()
print("=" * 70)
print("QUIZ - Scenariusz: brakuje 2/15 gdy standardowy budzet (180s) juz")
print("wyczerpany (elapsed=200s) - grace POWINIEN zadzialac i dobic")
print("=" * 70)
qclock = FakeClock(start=0.0)
oai.time.monotonic = qclock.monotonic
qcall_count = {"n": 0}


async def _mock_regen_succeeds(n, avoid_block=""):
    qcall_count["n"] += 1
    qclock.advance(5)
    # offset=13: partia startowa (ponizej) uzywa indeksow puli 0-12 -
    # ta partia MUSI wziac calkowicie INNE wpisy (13, 14), zeby nie
    # kolidowac (patrz komentarz nad _DIVERSE_TOPICS).
    return {"title": "Test", "questions": _make_quiz_questions(n, offset=13)}


async def _run_quiz_grace_succeeds():
    quiz_data = {"title": "Test", "questions": _make_quiz_questions(13)}
    return await oai._verify_and_fill_quiz_math(
        quiz_data, requested_count=15, regenerate=_mock_regen_succeeds,
        t_start=-200.0, difficulty="trudny", level="liceum_2", topic="Matematyka: temat spoza listy archetypow",
    )


qresult = asyncio.run(_run_quiz_grace_succeeds())
check("Grace zadzialal - finalnie PELNE 15/15 pytan",
      len(qresult.get("questions", [])) == 15, len(qresult.get("questions", [])))
check("Brak _shortfall_warning (grace w pelni pokryl niedobor)",
      "_shortfall_warning" not in qresult, qresult.get("_shortfall_warning"))
check("Mock wywolany dokladnie 1 raz (missing=2, jedna runda grace wystarczyla)",
      qcall_count["n"] == 1, qcall_count["n"])

print()
print("=" * 70)
print("QUIZ - Scenariusz: brakuje 6/15 (>2) gdy standardowy budzet juz")
print("wyczerpany - grace NIE POWINIEN probowac wcale")
print("=" * 70)
qclock2 = FakeClock(start=0.0)
oai.time.monotonic = qclock2.monotonic
qcall_count2 = {"n": 0}


async def _mock_regen_should_not_be_called(n, avoid_block=""):
    qcall_count2["n"] += 1
    return {"title": "Test", "questions": _make_quiz_questions(n)}


async def _run_quiz_grace_too_much_missing():
    quiz_data = {"title": "Test", "questions": _make_quiz_questions(9)}
    return await oai._verify_and_fill_quiz_math(
        quiz_data, requested_count=15, regenerate=_mock_regen_should_not_be_called,
        t_start=-200.0, difficulty="trudny", level="liceum_2", topic="Matematyka: temat spoza listy archetypow",
    )


qresult2 = asyncio.run(_run_quiz_grace_too_much_missing())
check("Grace NIE probowal (missing=6>2) - mock NIGDY nie wywolany",
      qcall_count2["n"] == 0, qcall_count2["n"])
check("Niedobor pozostaje 9/15",
      len(qresult2.get("questions", [])) == 9, len(qresult2.get("questions", [])))
check("_shortfall_warning obecne, BEZ wzmianki o dodatkowych probach (grace nie bylo)",
      "_shortfall_warning" in qresult2 and "dodatkowych prob rozszerzenia" not in qresult2["_shortfall_warning"],
      qresult2.get("_shortfall_warning"))

print()
print("=" * 70)
print("QUIZ - Scenariusz: brakuje 2/15, temat NIGDY nie dostarcza uzywalnych")
print("pytan w grace - zatrzymuje sie po dokladnie 3 rundach, uczciwy komunikat")
print("=" * 70)
qclock3 = FakeClock(start=0.0)
oai.time.monotonic = qclock3.monotonic
qcall_count3 = {"n": 0}


async def _mock_regen_always_empty(n, avoid_block=""):
    qcall_count3["n"] += 1
    qclock3.advance(5)
    return {"title": "Test", "questions": []}


async def _run_quiz_grace_exhausted():
    quiz_data = {"title": "Test", "questions": _make_quiz_questions(13)}
    return await oai._verify_and_fill_quiz_math(
        quiz_data, requested_count=15, regenerate=_mock_regen_always_empty,
        t_start=-200.0, difficulty="trudny", level="liceum_2", topic="Matematyka: temat spoza listy archetypow",
    )


qresult3 = asyncio.run(_run_quiz_grace_exhausted())
check("Zatrzymalo sie po DOKLADNIE 3 probach grace",
      qcall_count3["n"] == 3, qcall_count3["n"])
check("_shortfall_warning wspomina '3 dodatkowych prob rozszerzenia'",
      "_shortfall_warning" in qresult3 and "3 dodatkowych prob rozszerzenia" in qresult3["_shortfall_warning"],
      qresult3.get("_shortfall_warning"))

oai.time.monotonic = __import__("time").monotonic  # przywroc prawdziwy zegar
oai.client = _real_oai_client  # przywroc prawdziwego klienta

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY (SPRAWDZIAN + QUIZ) PRZESZLY.")
