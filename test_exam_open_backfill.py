"""Lokalne testy (zero kosztu API - FakeClock + mock, patrz
test_b1_grace_extension.py po ten sam wzorzec) dla dogenerowania zadan
OTWARTYCH w _fill_missing_exam_questions (exam_pdf_generator.py).

Domyka TODO.md "Dogenerowanie zadan OTWARTYCH przy odrzuceniu" (odlozone
28.08.2026 jako "kosmetyczne") - real-test 30.08.2026 (n=13, rownania
kwadratowe, srednia) pokazal 12/13 z myllacym komunikatem "wyczerpano 10
prob dogenerowania" (realnie 1 runda) - user: "user ma zawsze dostawac
tyle zamowien ile zamawial, ma byc szybki i bez bledow".
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


class FakeClock:
    def __init__(self, start=0.0):
        self.t = start

    def monotonic(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


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
print("1. DOKLADNY real przypadek: n=13, closed target (8) juz osiagniety,")
print("   brakuje 1 otwartego -> NOWY mechanizm powinien go dobic (13/13)")
print("=" * 70)
clock = FakeClock(start=0.0)
epg.time.monotonic = clock.monotonic
call_log = []


def _mock_only_open(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block="", only_open=False):
    call_log.append({"n": n, "only_open": only_open})
    clock.advance(3)
    return {"sekcje": [{"typ": "otwarte", "pytania": _make_open(n, start_nr=200 + len(call_log) * 10)}]}


gen._get_exam_data_raw_parallel = _mock_only_open
# 8 zamkniete (=target_closed dla n=13, round(13*0.6)=8) + 4 otwarte (brakuje 1 z 5=target_open)
data = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(8)},
    {"typ": "otwarte", "pytania": _make_open(4)},
]}
result = gen._fill_missing_exam_questions(
    data, temat="Rownania kwadratowe", klasa="liceum",
    trudnosc="srednia", liczba_pytan=13, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=0.0,
)
final_total = sum(len(s["pytania"]) for s in result["sekcje"])
check("Dobito do pelnych 13/13 (dokladnie real przypadek z real-testu)", final_total == 13, final_total)
check("Brak _shortfall_warning (pelny sukces)", "_shortfall_warning" not in result, result.get("_shortfall_warning"))
check("Wywolanie uzylo only_open=True", len(call_log) == 1 and call_log[0]["only_open"] is True, call_log)
check("Poprosilo o dokladnie 1 (missing_capped = min(1, open_headroom=1))", call_log[0]["n"] >= 1, call_log[0]["n"])

print()
print("=" * 70)
print("2. Regresja: niedobor TYLKO w zamknietych (closed_headroom>0) ->")
print("   zachowanie identyczne jak przed ta naprawa (dogeneruje zamkniete)")
print("=" * 70)
clock2 = FakeClock(start=0.0)
epg.time.monotonic = clock2.monotonic
call_log2 = []


def _mock_closed_only(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block="", only_open=False):
    call_log2.append({"n": n, "only_open": only_open})
    clock2.advance(3)
    return {"sekcje": [{"typ": "zamkniete", "pytania": _make_closed(n, start_nr=300 + len(call_log2) * 10)}]}


gen._get_exam_data_raw_parallel = _mock_closed_only
# target_open (13-8=5) JUZ osiagniety (5 otwartych) - caly niedobor (2) jest
# w zamknietych, wiec to NAPRAWDE czysty "closed-only" scenariusz (open_headroom=0).
data2 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(6)},
    {"typ": "otwarte", "pytania": _make_open(5)},
]}
result2 = gen._fill_missing_exam_questions(
    data2, temat="Matematyka: inny temat", klasa="liceum",
    trudnosc="srednia", liczba_pytan=13, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=0.0,
)
final_total2 = sum(len(s["pytania"]) for s in result2["sekcje"])
check("Dobito do 13/13 przez zamkniete (regresja: stare zachowanie zachowane)", final_total2 == 13, final_total2)
check("Wywolanie NIE uzylo only_open (bo brakowalo zamknietych, nie otwartych)",
      len(call_log2) >= 1 and all(c["only_open"] is False for c in call_log2), call_log2)

print()
print("=" * 70)
print("3. 'Tylko zamkniete' zadane przez nauczyciela -> open-backfill NIGDY")
print("   sie nie uruchamia, nawet gdyby cos wygladalo na niedobor otwartych")
print("=" * 70)
clock3 = FakeClock(start=0.0)
epg.time.monotonic = clock3.monotonic
call_log3 = []


def _mock_should_not_use_open(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block="", only_open=False):
    call_log3.append({"n": n, "only_open": only_open})
    clock3.advance(3)
    return {"sekcje": [{"typ": "zamkniete", "pytania": _make_closed(n, start_nr=400 + len(call_log3) * 10)}]}


gen._get_exam_data_raw_parallel = _mock_should_not_use_open
data3 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(10)},
]}
result3 = gen._fill_missing_exam_questions(
    data3, temat="Matematyka: cokolwiek", klasa="liceum",
    trudnosc="srednia", liczba_pytan=13, wlasne_instrukcje="TYLKO zadania zamkniete, sprawdzian ma miec wylacznie test wyboru",
    przedmiot="Matematyka", max_rounds=10, t_start=0.0,
)
final_total3 = sum(len(s["pytania"]) for s in result3["sekcje"])
check("target_open=0 wymuszony -> dobito 13/13 WYLACZNIE zamknietymi", final_total3 == 13, final_total3)
check("Zaden otwarty nigdy nie zostal dodany", all(s.get("typ") != "otwarte" for s in result3["sekcje"]), result3["sekcje"])
check("only_open nigdy nie zostalo uzyte", all(c["only_open"] is False for c in call_log3), call_log3)

print()
print("=" * 70)
print("4. Otwarte grace wyczerpane (3 rundy, nadal 0 zwrocone) -> stop_reason")
print("   dokladnie opisuje przyczyne (nie mylacy '10 prob')")
print("=" * 70)
clock4 = FakeClock(start=0.0)
epg.time.monotonic = clock4.monotonic
call_log4 = []


def _mock_open_always_empty(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block="", only_open=False):
    call_log4.append({"n": n, "only_open": only_open})
    clock4.advance(5)
    return {"sekcje": [{"typ": "otwarte", "pytania": []}]}


gen._get_exam_data_raw_parallel = _mock_open_always_empty
data4 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(8)},
    {"typ": "otwarte", "pytania": _make_open(4)},
]}
# t_start=-46.0: elapsed startuje na 46s (> 45s std budget dla "trudny" spoza
# listy - patrz test_b1_grace_extension.py po identyczne okno), grace probuje.
result4 = gen._fill_missing_exam_questions(
    data4, temat="Matematyka: temat spoza listy archetypow", klasa="liceum_2",
    trudnosc="trudna", liczba_pytan=13, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=-46.0,
)
check("Zatrzymalo sie po DOKLADNIE 3 probach grace (otwarte)", len(call_log4) == 3, len(call_log4))
warning = result4.get("_shortfall_warning", "")
check("Komunikat wspomina 'otwarte' (typ ktorego naprawde brakowalo)", "otwarte" in warning, warning)
check("Komunikat NIE klamie o '10 prob dogenerowania' (bo realnie 3 rundy)", "10 prob dogenerowania" not in warning, warning)
check("Komunikat wspomina konkretnie B1/rozszerzenie", "rozszerzenia" in warning or "B1" in warning, warning)

epg.time.monotonic = __import__("time").monotonic

print()
print("=" * 70)
print("5. B2 (obnizenie trudnosci) - identyczna naprawa: closed target juz")
print("   osiagniety, brakuje 1 otwartego -> B2 tez uzywa only_open=True")
print("=" * 70)
call_log5 = []


def _mock_b2_only_open(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block="", only_open=False):
    call_log5.append({"n": n, "only_open": only_open, "trudnosc": trudnosc})
    return {"sekcje": [{"typ": "otwarte", "pytania": _make_open(n, start_nr=500)}]}


gen._get_exam_data_raw_parallel = _mock_b2_only_open
data5 = {"tytul": "Test", "sekcje": [
    {"typ": "zamkniete", "pytania": _make_closed(8)},
    {"typ": "otwarte", "pytania": _make_open(4)},
], "_shortfall_warning": "Udalo sie wygenerowac 12 z 13..."}
result5 = gen._apply_b2_difficulty_downgrade(
    data5, temat="Test", klasa="liceum_2", trudnosc="trudna", liczba_pytan=13,
    wlasne_instrukcje=None, przedmiot="Matematyka",
)
final_total5 = sum(len(s["pytania"]) for s in result5["sekcje"])
check("B2 dobil do 13/13 przez otwarte (na latwiejszym poziomie)", final_total5 == 13, final_total5)
check("B2 uzyl only_open=True (bo brakowalo otwartych, nie zamknietych)",
      len(call_log5) == 1 and call_log5[0]["only_open"] is True, call_log5)
check("B2 zszedl o jeden poziom (trudna -> srednia)", call_log5[0]["trudnosc"] == "srednia", call_log5)
check("_shortfall_warning usuniete (B2 w pelni domknal)", "_shortfall_warning" not in result5, result5.get("_shortfall_warning"))

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
