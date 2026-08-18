"""Centralny słownik opisów poziomu nauczania używanych w promptach AI.

Wcześniej ten sam wzorzec (słownik "poziom -> opis dla AI") był kopiowany
niezależnie w openai_exam.py (x2), app/services/lesson_planner.py,
app/api/voice.py, app/api/whiteboard.py i app/api/realtime.py. Ten moduł
jest jedynym źródłem prawdy - wszystkie te miejsca mają z niego korzystać
zamiast trzymać własne kopie.

## Klucze

Słownik ma dwa poziomy szczegółowości:

1. Koszyki ogólne - "podstawowka", "liceum", "technikum", "matura",
   "studia", "gimnazjum" (bez numeru klasy). To jest wsteczna
   kompatybilność: dzisiejszy frontend (quiz_app.html, exam_generator.html
   itd.) wysyła właśnie takie wartości i ma tak działać bez zmian, dopóki
   nie zostanie zaktualizowany o wybór konkretnej klasy. Opis takiego
   koszyka to celowo "środek zakresu" danego etapu, nie uśrednienie
   tekstowe skrajności - łatwiej AI dostać jedną konkretną kotwicę
   trudności niż wskazówkę "gdzieś pomiędzy bardzo łatwym a bardzo
   trudnym".

2. Konkretne klasy - klucz w formacie `{etap}_{numer}`, np. "podstawowka_5",
   "liceum_2", "technikum_4", "studia_3", oraz "matura_podstawowa" /
   "matura_rozszerzona" (dla matury numer zastępuje poziom egzaminu, bo
   matura nie ma "klas"). Ten format jest tu ustalony jako kontrakt na
   przyszłość - żaden dzisiejszy caller jeszcze go nie używa, ale kiedy
   frontend dostanie wybór konkretnej klasy (patrz docs/plan-konkretne-klasy.md),
   ma wysyłać dokładnie takie klucze i nic w tym module nie będzie trzeba
   zmieniać.

Wszystkie funkcje w tym module (`describe_level`, `is_known_level`) działają
identycznie dla obu poziomów szczegółowości - nie trzeba w miejscach
wywołania wiedzieć, czy dostały koszyk ogólny czy konkretną klasę.
"""

LEVEL_DESC = {
    # ============================================================
    # KOSZYKI OGÓLNE (wsteczna kompatybilność - bez numeru klasy)
    # ============================================================
    "podstawowka": (
        "uczeń szkoły podstawowej, dokładna klasa nieznana (zakres: klasa "
        "1-8) - dobierz umiarkowaną trudność jak dla środka zakresu (ok. "
        "klasy 4-5): prosty język, krótkie zdania, konkretne przykłady z "
        "codziennego życia, unikaj żargonu naukowego bez wyjaśnienia"
    ),
    "gimnazjum": (
        "uczeń gimnazjum - średni poziom szczegółowości, podstawowa "
        "terminologia z krótkim wyjaśnieniem"
    ),
    "liceum": (
        "uczeń liceum, dokładna klasa nieznana (zakres: klasa 1-4) - "
        "dobierz umiarkowaną trudność jak dla środka zakresu (ok. klasy "
        "2-3): pełna terminologia przedmiotowa, wzory, wyjaśnianie "
        "mechanizmów i zależności"
    ),
    "technikum": (
        "uczeń technikum, dokładna klasa nieznana (zakres: klasa 1-5) - "
        "dobierz umiarkowaną trudność jak dla środka zakresu (ok. klasy "
        "3), analogicznie do liceum, z naciskiem na zastosowania "
        "praktyczne"
    ),
    "matura": (
        "uczeń przygotowujący się do matury, poziom (podstawowy czy "
        "rozszerzony) nieznany - dobierz zakres pośredni: wszystkie wzory "
        "i definicje z poziomu podstawowego plus najważniejsze zagadnienia "
        "z rozszerzenia, przykładowe zadania maturalne z pełnym "
        "rozwiązaniem, wskazówki egzaminacyjne"
    ),
    "studia": (
        "student studiów wyższych, dokładny rok nieznany - dobierz "
        "umiarkowaną trudność jak dla środka toku studiów (ok. 2-3 roku): "
        "pełna formalizacja i terminologia akademicka, wyprowadzenia "
        "wzorów krok po kroku, zaawansowane zastosowania i konteksty"
    ),

    # ============================================================
    # SZKOŁA PODSTAWOWA - klasy 1-8
    # ============================================================
    "podstawowka_1": (
        "Klasa 1 szkoły podstawowej (6-7 lat, edukacja wczesnoszkolna). "
        "Bardzo proste, krótkie zdania, dużo przykładów w formie zabawy i "
        "obrazków. Zakres: liczenie do 20-30, dodawanie i odejmowanie w "
        "tym zakresie, rozpoznawanie liter i prostych słów - unikaj "
        "jakiejkolwiek terminologii naukowej."
    ),
    "podstawowka_2": (
        "Klasa 2 szkoły podstawowej (7-8 lat, edukacja wczesnoszkolna). "
        "Proste zdania, przykłady z życia dziecka (zabawki, jedzenie, "
        "zwierzęta). Zakres: liczenie do 100, dodawanie i odejmowanie "
        "pisemne, wprowadzenie mnożenia w niewielkim zakresie."
    ),
    "podstawowka_3": (
        "Klasa 3 szkoły podstawowej (8-9 lat, ostatnia klasa edukacji "
        "wczesnoszkolnej). Proste zdania, obrazowe porównania. Zakres: "
        "tabliczka mnożenia i dzielenia do 100, liczby do 1000, proste "
        "zadania tekstowe, podstawowe jednostki miary."
    ),
    "podstawowka_4": (
        "Klasa 4 szkoły podstawowej (9-10 lat, początek nauczania "
        "przedmiotowego - matematyka, przyroda i historia jako osobne "
        "przedmioty). Proste, konkretne wyjaśnienia z przykładami "
        "liczbowymi. Zakres: ułamki zwykłe (wprowadzenie), liczby "
        "wielocyfrowe, podstawy geometrii (punkty, odcinki, kąty)."
    ),
    "podstawowka_5": (
        "Klasa 5 szkoły podstawowej (10-11 lat). Jasny język z "
        "przykładami z życia codziennego, terminologia wprowadzana "
        "stopniowo z krótkim wyjaśnieniem. Zakres: ułamki dziesiętne, "
        "działania na ułamkach, pola i obwody figur, proste wyrażenia "
        "algebraiczne."
    ),
    "podstawowka_6": (
        "Klasa 6 szkoły podstawowej (11-12 lat). Terminologia wprowadzana "
        "stopniowo, z wyjaśnieniem każdego nowego pojęcia. Zakres: liczby "
        "całkowite (ujemne), procenty - wprowadzenie, pola i obwody "
        "bardziej złożonych figur, proste równania."
    ),
    "podstawowka_7": (
        "Klasa 7 szkoły podstawowej (12-13 lat, początek nauczania fizyki "
        "i chemii jako osobnych przedmiotów). Pełniejsza terminologia "
        "przedmiotowa, ale wciąż z wyjaśnieniami. Zakres: równania "
        "liniowe z jedną niewiadomą, wyrażenia algebraiczne, statystyka "
        "opisowa, podstawy fizyki i chemii."
    ),
    "podstawowka_8": (
        "Klasa 8 szkoły podstawowej (13-14 lat, rok egzaminu "
        "ósmoklasisty). Precyzyjny język przedmiotowy, nastawiony na "
        "powtórkę i utrwalenie całego materiału klas 4-8 pod kątem "
        "egzaminu. Zakres: układy równań, twierdzenie Pitagorasa, "
        "symetrie, bryły, zadania typowe dla egzaminu ósmoklasisty."
    ),

    # ============================================================
    # LICEUM (4-letnie) - klasy 1-4
    # ============================================================
    "liceum_1": (
        "Klasa 1 liceum (15-16 lat, pierwszy rok liceum 4-letniego). "
        "Pełna terminologia przedmiotowa z wyjaśnieniem, przykłady krok "
        "po kroku. Zakres: funkcja liniowa, zbiory liczbowe, potęgi i "
        "pierwiastki, powtórka i pogłębienie materiału ze szkoły "
        "podstawowej."
    ),
    "liceum_2": (
        "Klasa 2 liceum (16-17 lat). Pełna terminologia, wzory z "
        "wyprowadzeniem. Zakres: funkcja kwadratowa, trygonometria, "
        "wprowadzenie do ciągów liczbowych, planimetria."
    ),
    "liceum_3": (
        "Klasa 3 liceum (17-18 lat). Zaawansowana terminologia, nacisk na "
        "zastosowania i powiązania między działami. Zakres: logarytmy, "
        "ciągi arytmetyczne i geometryczne, funkcje wykładnicze, "
        "wprowadzenie do rachunku prawdopodobieństwa, stereometria."
    ),
    "liceum_4": (
        "Klasa 4 liceum (18-19 lat, ostatni rok, przygotowanie "
        "maturalne). Poziom maturalny, pełne wzory i przykłady zadań "
        "egzaminacyjnych. Zakres: powtórka całego materiału liceum, "
        "kombinatoryka i prawdopodobieństwo, pochodne i całki (zakres "
        "rozszerzony), typowe zadania maturalne."
    ),

    # ============================================================
    # TECHNIKUM (5-letnie) - klasy 1-5
    # ============================================================
    "technikum_1": (
        "Klasa 1 technikum (15-16 lat, pierwszy rok technikum "
        "5-letniego). Pełna terminologia z wyjaśnieniem, jak w liceum, "
        "ale z naciskiem na zastosowania praktyczne. Zakres: funkcja "
        "liniowa, zbiory liczbowe, potęgi i pierwiastki."
    ),
    "technikum_2": (
        "Klasa 2 technikum (16-17 lat). Zakres: funkcja kwadratowa, "
        "wprowadzenie do trygonometrii, elementy geometrii analitycznej, "
        "z naciskiem na przykłady zawodowo-praktyczne."
    ),
    "technikum_3": (
        "Klasa 3 technikum (17-18 lat). Zakres: pełna trygonometria, "
        "wprowadzenie do ciągów liczbowych, planimetria."
    ),
    "technikum_4": (
        "Klasa 4 technikum (18-19 lat). Zakres: logarytmy, ciągi "
        "arytmetyczne i geometryczne, funkcje wykładnicze, stereometria."
    ),
    "technikum_5": (
        "Klasa 5 technikum (19-20 lat, ostatni rok, przygotowanie "
        "maturalne i do egzaminu zawodowego). Poziom maturalny. Zakres: "
        "powtórka całego materiału, rachunek prawdopodobieństwa, typowe "
        "zadania maturalne."
    ),

    # ============================================================
    # MATURA - poziom egzaminu zamiast numeru klasy
    # ============================================================
    "matura_podstawowa": (
        "Matura na poziomie podstawowym (obowiązkowa dla wszystkich "
        "maturzystów). Zadania zamknięte i krótkie otwarte, materiał "
        "ograniczony do podstawy programowej poziomu podstawowego, "
        "dozwolona karta wzorów CKE. Podawaj wzory i definicje "
        "słownikowo, przykłady zadań typowe dla arkusza podstawowego."
    ),
    "matura_rozszerzona": (
        "Matura na poziomie rozszerzonym (dodatkowa, dla kandydatów na "
        "kierunki ścisłe/techniczne). Zadania wieloetapowe, dowody, "
        "złożone zastosowania, pełny zakres wzorów z karty CKE. Podawaj "
        "rozwiązania z pełną argumentacją i typowe sposoby podejścia do "
        "trudnych zadań maturalnych."
    ),

    # ============================================================
    # STUDIA - rok 1-5 (licencjat/inżynierskie + magisterskie)
    # ============================================================
    "studia_1": (
        "Rok 1 studiów (studia licencjackie/inżynierskie, podstawy). "
        "Terminologia akademicka wprowadzana z wyjaśnieniem. Zakres: "
        "analiza matematyczna I (granice, pochodne), algebra liniowa I "
        "(macierze, wektory), podstawy przedmiotu kierunkowego."
    ),
    "studia_2": (
        "Rok 2 studiów. Pełna terminologia akademicka, wyprowadzenia "
        "wzorów krok po kroku. Zakres: analiza matematyczna II (całki, "
        "szeregi), algebra liniowa II, pierwsze przedmioty specjalistyczne "
        "kierunkowe."
    ),
    "studia_3": (
        "Rok 3 studiów (zwykle ostatni rok licencjatu/studiów "
        "inżynierskich). Zaawansowana terminologia specjalistyczna. "
        "Zakres: przedmioty kierunkowe zaawansowane, przygotowanie do "
        "pracy dyplomowej licencjackiej/inżynierskiej."
    ),
    "studia_4": (
        "Rok 4 studiów (pierwszy rok studiów magisterskich, jeśli "
        "kontynuacja). Zaawansowana terminologia, pogłębione ujęcie "
        "tematów. Zakres: przedmioty specjalistyczne pogłębione, wybór "
        "specjalizacji."
    ),
    "studia_5": (
        "Rok 5 studiów (ostatni rok studiów magisterskich). Poziom "
        "ekspercki - pełna formalizacja, powiązania z aktualnymi "
        "badaniami naukowymi. Zakres: seminaria dyplomowe, praca "
        "magisterska, przedmioty eksperckie w wybranej specjalizacji."
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

    Działa identycznie dla koszyków ogólnych ("liceum") i konkretnych
    klas ("liceum_2") - to jeden i ten sam słownik, więc caller nie musi
    wiedzieć, jak dokładny poziom dostał.

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


_STAGE_LABELS = {
    "podstawowka": "Podstawówka",
    "liceum": "Liceum",
    "technikum": "Technikum",
    "matura": "Matura",
    "studia": "Studia",
}
_MATURA_CLASS_LABELS = {"podstawowa": "Podstawowa", "rozszerzona": "Rozszerzona"}


def label_for_level(level: str) -> str:
    """Krótka, czytelna dla człowieka etykieta poziomu (np. "Klasa 2 liceum",
    "Matura rozszerzona", "Rok 3 studiów") - do wyświetlenia w UI (profil,
    Dashboard), w odróżnieniu od describe_level(), które zwraca długi opis
    do promptu AI. Odpowiednik EduviaLevelPicker.describeLevelLabel() z
    static/level_picker.js - musi dawać identyczne etykiety.
    """
    if not level:
        return ""
    key = ALIASES.get(level, level)
    for stage, stage_label in _STAGE_LABELS.items():
        if key == stage:
            return stage_label
        prefix = stage + "_"
        if key.startswith(prefix):
            cls = key[len(prefix):]
            if stage == "podstawowka":
                return f"Klasa {cls} podstawówki"
            if stage == "liceum":
                return f"Klasa {cls} liceum"
            if stage == "technikum":
                return f"Klasa {cls} technikum"
            if stage == "studia":
                return f"Rok {cls} studiów"
            if stage == "matura":
                return "Matura " + _MATURA_CLASS_LABELS.get(cls, cls).lower()
    return level
