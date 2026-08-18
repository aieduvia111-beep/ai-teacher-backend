"""Centralny słownik opisów poziomu nauczania używanych w promptach AI.

Wcześniej ten sam wzorzec (słownik "poziom -> opis dla AI") był kopiowany
niezależnie w openai_exam.py (x2), app/services/lesson_planner.py,
app/api/voice.py, app/api/whiteboard.py i app/api/realtime.py. Ten moduł
jest jedynym źródłem prawdy - wszystkie te miejsca mają z niego korzystać
zamiast trzymać własne kopie.

Na razie słownik ma tylko ogólne koszyki (podstawowka/liceum/matura/studia
itp.) - to celowe, przygotowuje grunt pod przyszłe rozszerzenie na
konkretne klasy (np. "Klasa 5 podstawówki") bez zmiany API tego modułu.
"""

LEVEL_DESC = {
    "podstawowka": (
        "uczeń szkoły podstawowej (kl. 4-8) - prosty język, krótkie zdania, "
        "konkretne przykłady z codziennego życia, unikaj żargonu naukowego "
        "bez wyjaśnienia"
    ),
    "gimnazjum": (
        "uczeń gimnazjum - średni poziom szczegółowości, podstawowa "
        "terminologia z krótkim wyjaśnieniem"
    ),
    "liceum": (
        "uczeń liceum lub technikum - pełna terminologia przedmiotowa, "
        "wzory, wyjaśnianie mechanizmów i zależności, przykłady na "
        "poziomie szkoły średniej"
    ),
    "matura": (
        "uczeń przygotowujący się do matury - poziom CKE, wszystkie wzory "
        "i definicje ze słowniczka maturalnego, przykładowe zadania "
        "maturalne z pełnym rozwiązaniem, wskazówki egzaminacyjne"
    ),
    "studia": (
        "student studiów wyższych - pełna formalizacja i terminologia "
        "akademicka, wyprowadzenia wzorów krok po kroku, zaawansowane "
        "zastosowania i konteksty"
    ),
}

# Klucze historycznie używane w pojedynczych plikach, które oznaczają
# to samo co któryś z kluczy powyżej (np. whiteboard.py używał "kid"
# zamiast "podstawowka"). Trzymane tu, żeby te pliki nie musiały wiedzieć
# o swoich starych nazwach - patrzą tylko na ten moduł.
ALIASES = {
    "kid": "podstawowka",
    "dziecko": "podstawowka",
}

DEFAULT_LEVEL = "liceum"


def is_known_level(level: str) -> bool:
    """Czy `level` (lub jego alias) ma opis w LEVEL_DESC."""
    return level in LEVEL_DESC or level in ALIASES


def describe_level(level: str, fallback: str = DEFAULT_LEVEL) -> str:
    """Zwraca opis poziomu do wstrzyknięcia w prompt AI.

    Nieznany `level` -> opis poziomu `fallback` (domyślnie liceum).
    Jeśli `fallback=None`, nieznany `level` jest zwracany bez zmian
    (przydatne tam, gdzie dotychczasowy kod robił zwykły passthrough).
    """
    key = ALIASES.get(level, level)
    if key in LEVEL_DESC:
        return LEVEL_DESC[key]
    if fallback is None:
        return level
    return LEVEL_DESC.get(fallback, level)
