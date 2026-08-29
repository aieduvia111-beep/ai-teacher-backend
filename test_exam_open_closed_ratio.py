# -*- coding: utf-8 -*-
"""User zglosil real przypadek: "dlaczego na sprawdzianie sa tylko a,b,c
[tylko Czesc A]... 10 zadan ma byc matematycznie... backend liczy
procentowe... jak wybrales 15 zadan to masz dostac iles tam procent
zamknietych i iles tam procent otwartych... na tym sprawdzianie co
wygenerowalo bylo TYLKO czesc A".

Zbadano: KAZDA runda dogenerowania w _fill_missing_exam_questions
(WSZYSTKIE galezie - safe-archetypy z dzisiejszej pracy I fallback
wolnej generacji) dodawala WYLACZNIE zadania ZAMKNIETE - sekcja
"otwarte" z odpowiedzi AI byla po cichu odrzucana, nawet jesli AI ja
wygenerowalo (brak jakiegokolwiek mechanizmu dogenerowania OTWARTYCH -
patrz TODO.md, ten brak byl juz wczesniej znany i CELOWO odlozony jako
"kosmetyczny"). Przy WYSOKIM rejection rate dla zadan otwartych +
NIEZAWODNYM (dzieki dzisiejszym archetypom) dopelnianiu zamknietych,
`missing` bylo ZAWSZE dopelniane zamknietymi az caly sprawdzian
stawal sie 100% Czescia A - dokladnie zgloszony przypadek.

Naprawiono: cel proporcji (60% zamkniete / 40% otwarte, patrz
EXAM_PROMPT) liczony RAZ na poczatku _fill_missing_exam_questions -
kazda runda dogenerowania smie dodac TYLKO tyle zamknietych, ile
brakuje do TEGO celu, nie do calego `missing`. Gdy cel zamknietych jest
juz osiagniety ale `missing` > 0 (bo brakuje otwartych) - petla KONCZY
SIE (uczciwy, PROPORCJONALNY niedobor) zamiast dalej dopelniac
zamkniete ponad cel.

Ten plik testuje TO WPROST - mockuje generacje tak, zeby symulowac
WYSOKI rejection rate otwartych (0% sukcesu) i NISKI zamknietych (100%
sukcesu, dokladnie scenariusz zgloszony przez usera) - bez zadnego
prawdziwego wywolania AI."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


from app.exam_pdf_generator import ExamGenerator

gen = ExamGenerator(openai_api_key="fake-key-not-used-in-this-test")


def _make_closed(n, start_nr=1):
    return [
        {"nr": start_nr + i, "tresc": f"P{start_nr + i}", "opcje": ["a) 1", "b) 2", "c) 3", "d) 4"],
         "odpowiedz": "a", "final_answer": "1", "punkty": 1}
        for i in range(n)
    ]


print("=" * 70)
print("Real scenariusz zgloszony przez usera: otwarte ZAWSZE odrzucane,")
print("zamkniete ZAWSZE przechodza - regen NIE moze przekroczyc celu 60%")
print("=" * 70)
# Startowy stan: 4 zamkniete + 2 otwarte = 6 z 10 zamowionych (typowa
# sytuacja po pierwszej, wolnej partii z pewnymi odrzuceniami).
data = {
    "tytul": "Test",
    "sekcje": [
        {"typ": "zamkniete", "pytania": _make_closed(4)},
        {"typ": "otwarte", "pytania": [
            {"nr": 5, "tresc": "Z1", "punkty": 4, "odpowiedz_modelowa": "x", "final_answer": "1"},
            {"nr": 6, "tresc": "Z2", "punkty": 4, "odpowiedz_modelowa": "x", "final_answer": "2"},
        ]},
    ],
}
# Mock: KAZDE wywolanie "wolnej generacji" zwraca SAME zamkniete zadania
# (symuluje real przypadek - free-gen dla otwartych regularnie zawodzi,
# a nawet gdyby AI wygenerowalo otwarte, i tak sa odrzucane przez
# _verify_and_fix_exam_math po drodze - efekt koncowy identyczny: regen
# dostarcza TYLKO uzywalne zamkniete).
call_count = {"n": 0}


def _mock_raw_parallel(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block=""):
    call_count["n"] += 1
    return {"sekcje": [{"typ": "zamkniete", "pytania": _make_closed(n, start_nr=100 + call_count["n"] * 10)}]}


gen._get_exam_data_raw_parallel = _mock_raw_parallel

result = gen._fill_missing_exam_questions(
    data, temat="Matematyka: przykladowy temat", klasa="liceum_2",
    trudnosc="srednia", liczba_pytan=10, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=None,
)

final_closed = sum(len(s["pytania"]) for s in result["sekcje"] if s["typ"] == "zamkniete")
final_open = sum(len(s["pytania"]) for s in result["sekcje"] if s["typ"] == "otwarte")
final_total = final_closed + final_open

check("Zamkniete NIE przekraczaja celu proporcji (60% z 10 = 6)", final_closed <= 6, final_closed)
check("Otwarte NIE zostaly ZERO-owane (zostaja oryginalne 2, nie usuwane)", final_open == 2, final_open)
check("Sprawdzian NIE stal sie 100% zamkniety (real zgloszony problem)",
      not (final_closed == final_total and final_open == 0), (final_closed, final_open))
check("Finalny total < 10 (uczciwy niedobor - system NIE potrafi dogenerowac otwartych)",
      final_total < 10, final_total)
check("_shortfall_warning obecne (user widzi uczciwy komunikat, nie cichy niedobor)",
      "_shortfall_warning" in result, result.get("_shortfall_warning"))

print()
print("=" * 70)
print("Regresja: gdy BRAKUJE tylko zamknietych (typowy, czesty przypadek) -")
print("dopelnianie dziala NORMALNIE do pelnej liczby_pytan")
print("=" * 70)
call_count2 = {"n": 0}


def _mock_raw_parallel2(temat, klasa, trudnosc, n, wlasne_instrukcje, przedmiot, avoid_block=""):
    call_count2["n"] += 1
    return {"sekcje": [{"typ": "zamkniete", "pytania": _make_closed(n, start_nr=200 + call_count2["n"] * 10)}]}


gen._get_exam_data_raw_parallel = _mock_raw_parallel2
# Startowy stan: 3 zamkniete + 4 otwarte = 7 z 10 (cel zamknietych to 6,
# WCIAZ ponizej celu - 3 brakujace zamkniete powinny sie dopelnic normalnie).
data2 = {
    "tytul": "Test",
    "sekcje": [
        {"typ": "zamkniete", "pytania": _make_closed(3)},
        {"typ": "otwarte", "pytania": [
            {"nr": 4 + i, "tresc": f"Z{i}", "punkty": 4, "odpowiedz_modelowa": "x", "final_answer": str(i)}
            for i in range(4)
        ]},
    ],
}
result2 = gen._fill_missing_exam_questions(
    data2, temat="Matematyka: inny temat", klasa="liceum_2",
    trudnosc="srednia", liczba_pytan=10, wlasne_instrukcje=None, przedmiot="Matematyka",
    max_rounds=10, t_start=None,
)
final_total2 = sum(len(s["pytania"]) for s in result2["sekcje"])
check("Typowy niedobor TYLKO w zamknietych -> nadal dopelnia do pelnej liczby (10)",
      final_total2 == 10, final_total2)
check("Brak _shortfall_warning (pelny sukces, jak przed ta naprawa)",
      "_shortfall_warning" not in result2, result2.get("_shortfall_warning"))

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
