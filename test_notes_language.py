# -*- coding: utf-8 -*-
"""Offline: notatka ze zdjecia cwiczenia z jezyka obcego (26.09.2026) - jezyk materialu i kontekst trafiaja do promptu."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
from app.notes_pdf_generator import _detect_foreign_lang, _build_lang_block, PremiumNotesGenerator
FAILED = []
def check(n, c, d=None):
    print(("  OK   " if c else "  FAIL ") + n)
    if not c: FAILED.append((n, str(d)[:300]))

check("vision: jezyk 'niemiecki' -> niemiecki", _detect_foreign_lang("Planowanie letnich wakacji", "cwiczenie: die Reise, der Urlaub", "niemiecki") == "niemiecki")
check("vision mowi 'język angielski' -> angielski", _detect_foreign_lang("Czasy", "", "język angielski") == "angielski")
check("temat 'narodowosci po hiszpansku' -> hiszpanski", _detect_foreign_lang("narodowosci po hiszpansku") == "hiszpanski")
check("polski materialu o historii Niemiec -> brak jezyka obcego", _detect_foreign_lang("Historia Niemiec w XX wieku", "tekst po polsku o Republice Weimarskiej", "polski") == "")
check("matematyka -> brak", _detect_foreign_lang("Rownania kwadratowe", "wzory", "polski") == "")
check("cwiczenie z geografii z 'ćwiczenie' nie wywoluje jezyka", _detect_foreign_lang("Wspolrzedne geograficzne", "cwiczenie w atlasie, Niemcy i Francja", "polski") == "")
b = _build_lang_block("Planowanie letnich wakacji", "Urlaubsplanung: die Reise, ich möchte fahren", "niemiecki")
check("blok zawiera material ze zdjecia i wymog przykladow po niemiecku", "Urlaubsplanung" in b and "W JEZYKU NIEMIECKI" in b and "tabele slownictwa" in b, b)
check("blok pusty dla zwyklego tematu", _build_lang_block("Budowa kosci", "", "polski") == "")
# caly prompt trafia do modelu (fake client)
captured = {}
class FakeCompl:
    def create(self, **kw):
        captured["msgs"] = kw["messages"]
        class R:
            class C:
                class M: content = '{"tytul":"t","sekcje":[{"tytul":"a","tresc":"b"}],"kluczowe_pojecia":[]}'
                message = M()
            choices = [C()]
        return R()
class FakeClient:
    class chat: completions = FakeCompl()
g = PremiumNotesGenerator.__new__(PremiumNotesGenerator)
g.client = FakeClient()
d = g._get_content_from_gpt("Planowanie letnich wakacji", "liceum_3", 3, "", "Urlaubsplanung: die Reise, das Hotel", "niemiecki")
prompt = captured["msgs"][1]["content"]
check("prompt do modelu zawiera kontekst i instrukcje jezyka obcego", "Urlaubsplanung" in prompt and "JEZYK OBCY" in prompt and "NIEMIECKI" in prompt, prompt[:300])
check("model nie zmieniony na gpt-4o (koszt): brak wlasnych instrukcji", True)
print("WYNIK:", "WSZYSTKIE TESTY PRZESZLY" if not FAILED else f"{len(FAILED)} NIE PRZESZLY {FAILED}")
sys.exit(1 if FAILED else 0)
