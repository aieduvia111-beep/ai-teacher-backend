# -*- coding: utf-8 -*-
"""User (po 3. z rzedu real-tescie trudnej trygonometrii, ostatni raz
13/15 po PELNYCH 3 minutach oczekiwania): "bez jaj nie mozemy tak zrobic
ze czekac 5 minut kurwa na sprawdzian musimy miec inne rozwiazanie".

Zbadano: podnoszenie budzetu czasowego bylo slepym zaulkiem - prawdziwy
problem byl w exam_api.py/quiz_api.py _shortfall_response, ktory
WYRZUCAL caly juz zbudowany i w pelni zweryfikowany PDF/quiz przy
NAJMNIEJSZYM niedoborze (np. 13 z 15), zmuszajac usera do czekania od
zera po raz drugi za utrate calej poprawnej pracy AI.

Naprawiono (INNE rozwiazanie, nie kolejne podniesienie timeoutu):
- exam_api.py: gdy PDF/ZIP faktycznie powstal (generate_exam buduje go
  normalnie nawet przy niedoborze), oddajemy go OD RAZU z naglowkami
  X-Shortfall/X-Requested-Count/X-Accepted-Count/X-Shortfall-Message
  (percent-encoded, bo naglowki HTTP musza byc ASCII) - frontend
  pokazuje JAWNE, nieblokujace ostrzezenie zamiast chowac PDF.
- quiz_api.py: identycznie, ale JSON pozwala dolozyc pole wprost - gdy
  jest choc 1 zaakceptowane pytanie, zwracamy success:True + osobne
  pole "shortfall_message" zamiast success:False i wyrzucania quizu.

Ten plik testuje SAMA logike backendu (zero AI, zero Fast API/HTTP -
bezposrednie wywolania funkcji z gotowymi danymi)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


print("=" * 70)
print("exam_api._shortfall_headers - naglowki HTTP z informacja o niedoborze")
print("=" * 70)
from app.api.exam_api import _shortfall_headers, _shortfall_response

info = {"message": "Udało się wygenerować i zweryfikować 13 z 15 zamówionych zadań - "
                    "przekroczono limit czasu (180s), pozostałe okazały się błędne. "
                    "Spróbuj ponownie albo zmień temat/trudność.",
        "requested_count": 15, "accepted_count": 13}
headers = _shortfall_headers(info)
check("X-Shortfall == '1'", headers.get("X-Shortfall") == "1", headers)
check("X-Requested-Count == '15'", headers.get("X-Requested-Count") == "15", headers)
check("X-Accepted-Count == '13'", headers.get("X-Accepted-Count") == "13", headers)
check("X-Shortfall-Message jest ASCII (bezpieczne jako naglowek HTTP)",
      headers.get("X-Shortfall-Message", "").isascii(), headers.get("X-Shortfall-Message"))
from urllib.parse import unquote
check("X-Shortfall-Message po decode = oryginalny komunikat (polskie znaki zachowane)",
      unquote(headers.get("X-Shortfall-Message", "")) == info["message"])

print()
print("=" * 70)
print("exam_api._shortfall_response - zostaje jako fallback (0 wynikow)")
print("=" * 70)
resp = _shortfall_response(info)
check("success == False (bez pliku, PDF naprawde nie powstal)", resp["success"] is False)
check("status == 'incomplete_generation'", resp["status"] == "incomplete_generation")
check("message/requested_count/accepted_count przekazane", resp["message"] == info["message"] and resp["requested_count"] == 15 and resp["accepted_count"] == 13)

print()
print("=" * 70)
print("quiz_api._shortfall_response - dostarcza quiz gdy accepted > 0")
print("=" * 70)
from app.api.quiz_api import _shortfall_response as quiz_shortfall_response

quiz_partial = {"questions": [{"question": f"P{i}"} for i in range(8)],
                "_shortfall_warning": "Udało się wygenerować i zweryfikować 8 z 10 zamówionych pytań."}
r1 = quiz_shortfall_response(quiz_partial, 10)
check("accepted > 0 -> success:True (quiz dostarczony, nie wyrzucony)", r1 is not None and r1.get("success") is True, r1)
check("quiz dostarczony w polu 'quiz' z pelna zawartoscia (8 pytan)",
      r1 is not None and len(r1.get("quiz", {}).get("questions", [])) == 8)
check("shortfall_message obecny i zgodny z ostrzezeniem", r1 is not None and r1.get("shortfall_message") == quiz_partial["_shortfall_warning"])
check("BRAK status:'incomplete_generation' gdy accepted > 0 (to jest sukces z ostrzezeniem, nie blad)",
      r1 is not None and "status" not in r1)

quiz_empty = {"questions": [], "_shortfall_warning": "Udało się wygenerować i zweryfikować 0 z 10 zamówionych pytań."}
r2 = quiz_shortfall_response(quiz_empty, 10)
check("accepted == 0 -> stary, kontrolowany blad (nic do dostarczenia)",
      r2 is not None and r2.get("success") is False and r2.get("status") == "incomplete_generation", r2)

quiz_full = {"questions": [{"question": f"P{i}"} for i in range(10)]}
r3 = quiz_shortfall_response(quiz_full, 10)
check("brak _shortfall_warning w ogole -> None (pelny sukces, bez zmian)", r3 is None, r3)

print()
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
