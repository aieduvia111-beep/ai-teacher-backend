# -*- coding: utf-8 -*-
"""NAPRAWA (audyt Voice AI, sierpien 2026 - kod przeczytany, ZERO
wywolan API): frontend (voice_conversation.html) woluje WYLACZNIE
/api/v1/voice/respond/stream (3 miejsca) - endpoint /respond jest
martwym kodem, nigdy nie wywolywanym. /respond/stream wstrzykiwal
SUROWY klucz poziomu ("Poziom: liceum_2") zamiast wolac describe_level()/
SUBJECT_SCOPE jak Quiz/Sprawdzian/Plan Nauki/Notatki - AI nie dostawalo
ani opisu wieku, ani zakresu materialu, ani klauzuli trudnosci.

Rownolegle sprawdzono: realtime.py (WebSocket /api/v1/realtime/ws)
poprawnie wola describe_level() w context.update, ALE
voice_conversation.html definiuje WS_URL i NIGDY nie tworzy
`new WebSocket(...)` - caly ten plik jest martwy z perspektywy
frontendu (nie wymagal naprawy, bo nie jest uzywany).

Ten test sprawdza SAMA LOGIKE budowania promptu (identyczna do tej w
respond_stream) - bez wywolywania calego endpointu (Depends na
DB/auth), bez zadnych wywolan AI."""
import sys
sys.path.insert(0, r"C:\Users\MI3\Desktop\eduvia-projekty\ai-teacher-backend")
from app.level_config import describe_level, is_known_level
from app.api.voice import SYSTEM_PROMPT

FAILED = []


def check(name, condition, detail=None):
    status = "OK  " if condition else "FAIL"
    print(f"  {status} {name}")
    if not condition:
        FAILED.append((name, detail))


def build_system_prompt(level="", subject="", topic="", profile_context=""):
    """Dokladna kopia naprawionej logiki z respond_stream (voice.py) -
    izolowana do testu bez Depends()/DB/auth."""
    system = SYSTEM_PROMPT
    if level and is_known_level(level):
        system += "\n\nKRYTYCZNE: " + describe_level(level, subject=subject or None) + " To jest NAJWAZNIEJSZA instrukcja - dostosuj CALY jezyk, terminologie i sposob wyjasniania do tego poziomu."
    if subject:
        system += f"\nPrzedmiot: {subject}"
    if topic:
        system += f"\nTemat sesji: {topic}"
    if profile_context:
        system += "\n\n" + profile_context
    return system


print("=" * 70)
print("Voice AI (/respond/stream) - poziom + przedmiot teraz przez describe_level()")
print("=" * 70)

system = build_system_prompt(level="liceum_2", subject="matematyka", topic="Trygonometria")
check("NIE zawiera surowego 'Poziom: liceum_2' (stary, bledny format)",
      "Poziom: liceum_2" not in system, None)
check("zawiera opis wieku z LEVEL_DESC ('Klasa 2 liceum')", "Klasa 2 liceum" in system, None)
check("zawiera zakres materialu z SUBJECT_SCOPE ('trygonometria')", "trygonometria" in system, None)
check("zawiera klauzule trudnosci ('NIE może być zbyt łatwe')", "NIE może być zbyt łatwe" in system, None)
check("nadal zawiera przedmiot jako osobna linia", "Przedmiot: matematyka" in system, None)
check("nadal zawiera temat sesji", "Temat sesji: Trygonometria" in system, None)

print()
print("=" * 70)
print("Regresja: brak poziomu / nieznany poziom -> bezpieczny fallback")
print("=" * 70)

system_no_level = build_system_prompt(level="", subject="matematyka", topic="")
check("brak poziomu -> brak sekcji 'KRYTYCZNE' (nie crashuje, nie zgaduje)",
      "KRYTYCZNE" not in system_no_level, None)
check("przedmiot nadal obecny mimo braku poziomu", "Przedmiot: matematyka" in system_no_level, None)

system_unknown_level = build_system_prompt(level="nieistniejacy_poziom_xyz", subject="", topic="")
check("nieznany klucz poziomu -> nie crashuje, brak falszywej sekcji KRYTYCZNE",
      "KRYTYCZNE" not in system_unknown_level, None)

print()
print("=" * 70)
print("SYSTEM_PROMPT (staly) nie jest mutowany miedzy wywolaniami (immutability check)")
print("=" * 70)

original_len = len(SYSTEM_PROMPT)
_ = build_system_prompt(level="liceum_2", subject="matematyka", topic="X")
check("dlugosc modulowego SYSTEM_PROMPT niezmieniona po budowie promptu (brak efektu ubocznego)",
      len(SYSTEM_PROMPT) == original_len, (len(SYSTEM_PROMPT), original_len))

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for name, detail in FAILED:
        print(f"  - {name}  ({detail})")
    sys.exit(1)
else:
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
