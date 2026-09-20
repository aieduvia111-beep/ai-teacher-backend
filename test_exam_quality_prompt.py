# -*- coding: utf-8 -*-
"""Offline (zero AI): jakosc sprawdzianow z przedmiotow NIEobliczeniowych (skarga 20.09.2026: polski 'za latwy i
niedoprecyzowany') - blok trudnosci/precyzji w prompcie tylko dla nieobliczeniowych, poprawne polecenie Czesci B,
skala ocen bez nakladajacych sie progow."""
import os, sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)
os.environ["MATH_PROVIDER"] = "openai"      # zero ruchu do DeepSeek w tescie

import app.exam_pdf_generator as eg

FAILED = []
def check(name, cond, detail=None):
    print(("  OK   " if cond else "  FAIL ") + name)
    if not cond: FAILED.append((name, str(detail)[:300]))

# ---- rozpoznanie tematu obliczeniowego ----
f = eg._exam_topic_needs_calculations
check("Matematyka: Funkcja kwadratowa -> obliczeniowy", f("Matematyka: Funkcja kwadratowa", "Matematyka") is True)
check("Fizyka: Ruch -> obliczeniowy (przedmiot fizyka)", f("Fizyka: Ruch jednostajny", "Fizyka") is True)
check("Polski: Czesci mowy -> NIEobliczeniowy", f("Język polski: Części mowy odmienne", "Język polski") is False)
check("Historia: PRL -> NIEobliczeniowy", f("Historia: PRL", "Historia") is False)
check("Geografia: Strefy czasowe (oblicz) -> obliczeniowy", f("Geografia: obliczanie czasu", "Geografia") is True)

# ---- prompt: przechwycenie tresci wysylanej do modelu ----
class Cap:
    prompts = []
def fake_create(**kw):
    Cap.prompts.append(" ".join(m["content"] for m in kw["messages"] if isinstance(m.get("content"), str)))
    msg = type("M", (), {"content": json.dumps({"sekcje": [{"nazwa": "Część B — Zadania obliczeniowe", "typ": "otwarte", "instrukcja_sekcji": "Rozwiąż zadania, pokazując pełny sposób obliczeń. Podaj jednostki.", "pytania": [{"nr": 1, "tresc": "x", "punkty": 1}]}]})})()
    ch = type("C", (), {"message": msg, "finish_reason": "stop"})()
    u = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1})()
    return type("R", (), {"choices": [ch], "usage": u, "model": "x"})()
g = eg.ExamGenerator("sk-test")
g.client.chat.completions.create = fake_create

g._get_exam_data_raw("Język polski: Części mowy", "podstawowka_6", "trudna", 10, None, "Język polski")
p_pl = Cap.prompts[-1]
check("polski: prompt zawiera blok JAKOSC I PRECYZJA", "JAKOSC I PRECYZJA" in p_pl and 'POZIOM TRUDNOSCI "trudna"' in p_pl and "podstawowka_6" in p_pl, p_pl[-300:])
check("polski: prompt wymaga podania przypadku/liczby w pytaniach o odmiane", "MUSI podawac przypadek" in p_pl)
check("polski: prompt zakazuje polecen typu 'Opisz zasady' bez zakresu", "ZAKAZ polecen ogolnych" in p_pl)
check("polski: prompt zakazuje powtarzania tej samej umiejetnosci", "INNA umiejetnosc" in p_pl)

g._get_exam_data_raw("Matematyka: Ułamki", "podstawowka_6", "srednia", 10, None, "Matematyka")
p_m = Cap.prompts[-1]
check("matematyka: prompt NIE dostaje bloku dla nieobliczeniowych", "JAKOSC I PRECYZJA" not in p_m)

g._get_exam_data_raw("Historia: PRL", "liceum_2", "trudna", 5, None, "Historia", only_open=True)
check("historia (tylko otwarte): blok jakosci tez dolaczony", "JAKOSC I PRECYZJA" in Cap.prompts[-1])

# ---- polecenie Czesci B ----
d = {"sekcje": [{"nazwa": "Część B — Zadania obliczeniowe", "typ": "otwarte", "instrukcja_sekcji": "Rozwiąż zadania, pokazując pełny sposób obliczeń. Podaj jednostki.", "pytania": []}]}
out = eg._fix_open_section_instruction(json.loads(json.dumps(d)), "Język polski: Części mowy", "Język polski")
sec = out["sekcje"][0]
check("polski: Czesc B bez 'obliczen' i 'jednostek'", "oblicze" not in sec["instrukcja_sekcji"].lower() and "jednostk" not in sec["instrukcja_sekcji"].lower() and "obliczeniowe" not in sec["nazwa"], sec)
out = eg._fix_open_section_instruction(json.loads(json.dumps(d)), "Matematyka: Ciągi", "Matematyka")
check("matematyka: polecenie Czesci B bez zmian", out["sekcje"][0]["instrukcja_sekcji"].startswith("Rozwiąż zadania"), out)

# ---- skala ocen: bez nakladania i bez luk ----
import math
def scale(m):
    lo = [math.ceil(m * x - 1e-9) for x in (0.92, 0.80, 0.65, 0.50, 0.30)]
    return [(lo[0], m), (lo[1], lo[0]-1), (lo[2], lo[1]-1), (lo[3], lo[2]-1), (lo[4], lo[3]-1), (0, lo[4]-1)]
ok = True; why = None
for m in range(10, 81):
    sc = scale(m)
    for i in range(len(sc) - 1):
        if sc[i][0] != sc[i+1][1] + 1 or sc[i][0] > sc[i][1]: ok = False; why = (m, sc)
check("skala ocen: zakresy przylegaja bez wspolnych punktow i bez luk dla 10-80 pkt", ok, why)
src = open("app/exam_pdf_generator.py", encoding="utf-8").read()
check("kod PDF uzywa nowych progow (ceil) zamiast int()*0.91", "_lo6 - 1" in src and "max_pkt*0.91" not in src)

print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
