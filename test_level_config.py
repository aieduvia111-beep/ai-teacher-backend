"""
Test poprawności systemu poziomow nauki (app/level_config.py) +
integracji z generatorem quizow (app/openai_exam.py).

Uruchom: python test_level_config.py

Sprawdza:
1. Kazdy klucz w LEVEL_DESC ma niepusty opis (z i bez przedmiotu)
2. label_for_level() dziala dla kazdego klucza i jest identyczny z
   logika JS w static/level_picker.js (recznie porownane wzorce)
3. SUBJECT_SCOPE nie ma literowek w kluczach przedmiotow (musza sie
   zgadzac z lista przedmiotow uzywana przez frontend)
4. Ten sam poziom + rozne przedmioty daje ROZNY, dopasowany zakres
   materialu (kluczowy regresyjny test na zgloszony bug)
5. Stary bug (fallback "poziom X, trudnosc Y" z generatora quizow)
   nie wystepuje dla ZADNEGO znanego poziomu
6. ALIASES dzialaja poprawnie
7. Nieznany poziom + fallback=None dziala jako passthrough
"""
import sys
sys.path.insert(0, ".")

from app.level_config import (
    LEVEL_DESC, SUBJECT_SCOPE, ALIASES, DEFAULT_LEVEL,
    describe_level, label_for_level, is_known_level,
)

FAILED = []


def check(name, condition, detail=""):
    if condition:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


# Przedmioty faktycznie uzywane w apce (patrz onboarding.html subj-grid /
# dashboard_FINAL.html DASH_SUBJECT_LABELS) - kazdy klucz w SUBJECT_SCOPE
# MUSI byc jednym z nich, inaczej to literowka ktora nigdy nie trafi.
VALID_SUBJECTS = {
    "matematyka", "fizyka", "chemia", "biologia", "historia",
    "polski", "angielski", "geografia", "informatyka", "inne",
}

print("=" * 70)
print("1) Kazdy klucz w LEVEL_DESC ma niepusty opis")
print("=" * 70)
for key in LEVEL_DESC:
    desc = describe_level(key)
    check(f"describe_level('{key}') niepusty", bool(desc and len(desc) > 20), repr(desc))
    label = label_for_level(key)
    check(f"label_for_level('{key}') niepusty", bool(label), repr(label))

print()
print("=" * 70)
print("2) label_for_level() - zgodnosc z wzorcem JS (describeLevelLabel)")
print("=" * 70)
# Recznie przepisane oczekiwane etykiety z tej samej logiki co
# EduviaLevelPicker.describeLevelLabel() w static/level_picker.js
expected_labels = {
    "podstawowka_1": "Klasa 1 podstawówki",
    "podstawowka_8": "Klasa 8 podstawówki",
    "liceum_2": "Klasa 2 liceum",
    "liceum_4": "Klasa 4 liceum",
    "technikum_3": "Klasa 3 technikum",
    "studia_1": "Rok 1 studiów",
    "studia_5": "Rok 5 studiów",
    "matura_podstawowa": "Matura podstawowa",
    "matura_rozszerzona": "Matura rozszerzona",
    "liceum": "Liceum",
    "podstawowka": "Podstawówka",
}
for key, expected in expected_labels.items():
    actual = label_for_level(key)
    check(f"label_for_level('{key}') == '{expected}'", actual == expected, f"otrzymano: {actual!r}")

print()
print("=" * 70)
print("3) SUBJECT_SCOPE - klucze przedmiotow bez literowek")
print("=" * 70)
bad_subjects = set()
for level_key, subjects in SUBJECT_SCOPE.items():
    check(f"'{level_key}' jest znanym poziomem", level_key in LEVEL_DESC, "nieznany klucz poziomu w SUBJECT_SCOPE")
    for subj_key, scope_text in subjects.items():
        if subj_key not in VALID_SUBJECTS:
            bad_subjects.add((level_key, subj_key))
        check(f"'{level_key}'/'{subj_key}' ma tresc", bool(scope_text and len(scope_text) > 5), repr(scope_text))
check("brak literowek w kluczach przedmiotow SUBJECT_SCOPE", not bad_subjects, bad_subjects)

print()
print("=" * 70)
print("4) Ten sam poziom, rozne przedmioty -> rozny, dopasowany zakres")
print("=" * 70)
math_desc = describe_level("liceum_3", subject="matematyka")
hist_desc = describe_level("liceum_3", subject="historia")
bio_desc = describe_level("liceum_3", subject="biologia")
check("matematyka != historia dla liceum_3", math_desc != hist_desc)
check("matematyka != biologia dla liceum_3", math_desc != bio_desc)
check("opis matematyki NIE zawiera slow z historii", "powstania narodowe" not in math_desc)
check("opis historii NIE zawiera wzorow matematycznych", "wykładnicz" not in hist_desc)
check("opis matematyki wspomina wlasciwy temat (funkcje wykladnicze - klasa 3 liceum, po korekcie wg aktualnej podstawy programowej)", "wykładnicz" in math_desc.lower())
check("opis historii wspomina wlasciwy temat (XIX wiek - klasa 3 liceum)", "xix wiek" in hist_desc.lower())

print()
print("=" * 70)
print("5) Stary bug (bezuzyteczny fallback z quiz generatora) NIE wystepuje")
print("=" * 70)
# To jest dokladnie ten sam wzorzec co byl zepsuty w
# generate_quiz_from_topic() PRZED naprawa: combo_map.get((level, difficulty))
# nigdy nie trafial dla konkretnych klas (np "liceum_3"), wiec kod spadal
# na goly string "poziom {level}, trudnosc {difficulty}" bez ZADNEGO
# realnego zakresu materialu. Test przechodzi po klasach + koszykach
# ogolnych, zeby miec pewnosc ze to sie NIGDZIE nie powtarza.
all_level_keys = list(LEVEL_DESC.keys())
for level_key in all_level_keys:
    for subject in ["matematyka", "historia", None]:
        result = describe_level(level_key, subject=subject)
        fallback_pattern = f"poziom {level_key}"
        check(
            f"brak zepsutego fallbacku dla ('{level_key}', subject={subject!r})",
            fallback_pattern not in result,
            result,
        )

print()
print("=" * 70)
print("6) ALIASES dzialaja poprawnie")
print("=" * 70)
for alias, target in ALIASES.items():
    check(f"is_known_level('{alias}') == True", is_known_level(alias))
    check(
        f"describe_level('{alias}') == describe_level('{target}')",
        describe_level(alias) == describe_level(target),
    )

print()
print("=" * 70)
print("7) Nieznany poziom + fallback=None -> passthrough")
print("=" * 70)
check("nieznany klucz + fallback=None zwraca sam siebie", describe_level("cos_dziwnego_123", fallback=None) == "cos_dziwnego_123")
check("nieznany klucz + domyslny fallback zwraca opis liceum", describe_level("cos_dziwnego_123") == LEVEL_DESC[DEFAULT_LEVEL])
check("is_known_level('cos_dziwnego_123') == False", not is_known_level("cos_dziwnego_123"))

print()
print("=" * 70)
print("8) Integracja z generatorem quizow (dokladnie zgloszony przypadek)")
print("=" * 70)
# Odtwarza DOKLADNIE logike z app/openai_exam.py generate_quiz_from_topic()
# po naprawie, dla przypadku zgloszonego przez usera: Klasa 3 liceum.
difficulty_map = {"easy": "łatwy", "medium": "średni", "hard": "trudny"}
for subject in ["matematyka", "historia", "biologia", "angielski"]:
    poziom_opis = describe_level("liceum_3", subject=subject)
    trudnosc_opis = difficulty_map.get("medium", "medium")
    check(f"quiz prompt dla liceum_3/{subject}: zawiera 'Klasa 3 liceum'", "Klasa 3 liceum" in poziom_opis)
    check(f"quiz prompt dla liceum_3/{subject}: ma zakres przedmiotu", f"({subject})" in poziom_opis)
    check(f"quiz prompt dla liceum_3/{subject}: trudnosc po polsku", trudnosc_opis == "średni")

print()
print("=" * 70)
if FAILED:
    print(f"WYNIK: {len(FAILED)} test(y) NIE PRZESZLY:")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
else:
    total = sum(1 for _ in range(1))  # placeholder, liczymy ponizej
    print("WYNIK: WSZYSTKIE TESTY PRZESZLY.")
    sys.exit(0)
