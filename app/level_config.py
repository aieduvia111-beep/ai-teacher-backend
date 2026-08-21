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
   matura nie ma "klas").

## Opis wieku/zlozonosci vs zakres przedmiotowy

WAZNE (naprawione po zgloszeniu): LEVEL_DESC opisuje TYLKO wiek i
zlozonosc jezykowa/poznawcza danej klasy - jest wiec identyczny
niezaleznie od przedmiotu. Wczesniej te opisy mialy na sztywno wpisany
zakres MATEMATYKI (np. "funkcja kwadratowa, trygonometria") - co bylo
mylace/bezuzyteczne, gdy przedmiotem byla Historia czy Biologia (AI
dostawal wskazowki matematyczne przy generowaniu quizu z historii).

Zakres materialu per przedmiot jest teraz w osobnym slowniku
SUBJECT_SCOPE, ktory `describe_level(level, subject=...)` doklada do
opisu TYLKO gdy wywolujacy poda `subject` i mamy dla niego wpis. Bez
`subject` (stare wywolania) funkcja dziala jak wczesniej - zwraca sam
opis wieku/zlozonosci, bez zadnego zakresu przedmiotowego (lepiej nic
niz zle dopasowany).
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
        "obrazków - unikaj jakiejkolwiek terminologii naukowej."
    ),
    "podstawowka_2": (
        "Klasa 2 szkoły podstawowej (7-8 lat, edukacja wczesnoszkolna). "
        "Proste zdania, przykłady z życia dziecka (zabawki, jedzenie, "
        "zwierzęta)."
    ),
    "podstawowka_3": (
        "Klasa 3 szkoły podstawowej (8-9 lat, ostatnia klasa edukacji "
        "wczesnoszkolnej). Proste zdania, obrazowe porównania."
    ),
    "podstawowka_4": (
        "Klasa 4 szkoły podstawowej (9-10 lat, początek nauczania "
        "przedmiotowego - matematyka, przyroda i historia jako osobne "
        "przedmioty). Proste, konkretne wyjaśnienia z przykładami "
        "liczbowymi."
    ),
    "podstawowka_5": (
        "Klasa 5 szkoły podstawowej (10-11 lat). Jasny język z "
        "przykładami z życia codziennego, terminologia wprowadzana "
        "stopniowo z krótkim wyjaśnieniem."
    ),
    "podstawowka_6": (
        "Klasa 6 szkoły podstawowej (11-12 lat). Terminologia wprowadzana "
        "stopniowo, z wyjaśnieniem każdego nowego pojęcia."
    ),
    "podstawowka_7": (
        "Klasa 7 szkoły podstawowej (12-13 lat, początek nauczania fizyki "
        "i chemii jako osobnych przedmiotów). Pełniejsza terminologia "
        "przedmiotowa, ale wciąż z wyjaśnieniami."
    ),
    "podstawowka_8": (
        "Klasa 8 szkoły podstawowej (13-14 lat, rok egzaminu "
        "ósmoklasisty). Precyzyjny język przedmiotowy, nastawiony na "
        "powtórkę i utrwalenie całego materiału klas 4-8 pod kątem "
        "egzaminu."
    ),

    # ============================================================
    # LICEUM (4-letnie) - klasy 1-4
    # ============================================================
    "liceum_1": (
        "Klasa 1 liceum (15-16 lat, pierwszy rok liceum 4-letniego). "
        "Pełna terminologia przedmiotowa z wyjaśnieniem, przykłady krok "
        "po kroku, powtórka i pogłębienie materiału ze szkoły "
        "podstawowej."
    ),
    "liceum_2": (
        "Klasa 2 liceum (16-17 lat). Pełna terminologia, wzory z "
        "wyprowadzeniem."
    ),
    "liceum_3": (
        "Klasa 3 liceum (17-18 lat). Zaawansowana terminologia, nacisk na "
        "zastosowania i powiązania między działami."
    ),
    "liceum_4": (
        "Klasa 4 liceum (18-19 lat, ostatni rok, przygotowanie "
        "maturalne). Poziom maturalny, pełne wzory i przykłady zadań "
        "egzaminacyjnych, powtórka całego materiału liceum."
    ),

    # ============================================================
    # TECHNIKUM (5-letnie) - klasy 1-5
    # ============================================================
    "technikum_1": (
        "Klasa 1 technikum (15-16 lat, pierwszy rok technikum "
        "5-letniego). Pełna terminologia z wyjaśnieniem, jak w liceum, "
        "ale z naciskiem na zastosowania praktyczne."
    ),
    "technikum_2": (
        "Klasa 2 technikum (16-17 lat). Nacisk na przykłady "
        "zawodowo-praktyczne."
    ),
    "technikum_3": (
        "Klasa 3 technikum (17-18 lat). Tempo materiału wolniejsze niż w "
        "liceum (5 lat zamiast 4), pełna terminologia z zastosowaniami "
        "zawodowymi."
    ),
    "technikum_4": (
        "Klasa 4 technikum (18-19 lat). Zaawansowana terminologia, "
        "zastosowania techniczne."
    ),
    "technikum_5": (
        "Klasa 5 technikum (19-20 lat, ostatni rok, przygotowanie "
        "maturalne i do egzaminu zawodowego). Poziom maturalny, powtórka "
        "całego materiału."
    ),

    # ============================================================
    # MATURA - poziom egzaminu zamiast numeru klasy
    # ============================================================
    "matura_podstawowa": (
        "Matura na poziomie podstawowym (obowiązkowa dla wszystkich "
        "maturzystów, z matematyki/polskiego/języka obcego). Zadania "
        "zamknięte i krótkie otwarte, materiał ograniczony do podstawy "
        "programowej poziomu podstawowego, dozwolona karta wzorów CKE. "
        "Podawaj wzory i definicje słownikowo, przykłady zadań typowe dla "
        "arkusza podstawowego."
    ),
    "matura_rozszerzona": (
        "Matura na poziomie rozszerzonym (dodatkowa, dla kandydatów na "
        "kierunki ścisłe/techniczne/humanistyczne - dowolny przedmiot). "
        "Zadania wieloetapowe, dowody, złożone zastosowania, pełny zakres "
        "wzorów z karty CKE. Podawaj rozwiązania z pełną argumentacją i "
        "typowe sposoby podejścia do trudnych zadań maturalnych."
    ),

    # ============================================================
    # STUDIA - rok 1-5 (licencjat/inżynierskie + magisterskie)
    # ============================================================
    "studia_1": (
        "Rok 1 studiów (studia licencjackie/inżynierskie, podstawy). "
        "Terminologia akademicka wprowadzana z wyjaśnieniem."
    ),
    "studia_2": (
        "Rok 2 studiów. Pełna terminologia akademicka, wyprowadzenia "
        "wzorów krok po kroku."
    ),
    "studia_3": (
        "Rok 3 studiów (zwykle ostatni rok licencjatu/studiów "
        "inżynierskich). Zaawansowana terminologia specjalistyczna, "
        "przygotowanie do pracy dyplomowej."
    ),
    "studia_4": (
        "Rok 4 studiów (pierwszy rok studiów magisterskich, jeśli "
        "kontynuacja). Zaawansowana terminologia, pogłębione ujęcie "
        "tematów, wybór specjalizacji."
    ),
    "studia_5": (
        "Rok 5 studiów (ostatni rok studiów magisterskich). Poziom "
        "ekspercki - pełna formalizacja, powiązania z aktualnymi "
        "badaniami naukowymi, praca magisterska."
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


# ============================================================
# ZAKRES MATERIAŁU PER PRZEDMIOT (opcjonalny dodatek do opisu)
# ============================================================
# Slownik {klucz_poziomu: {przedmiot: krotki_opis_zakresu}}. Brak wpisu
# dla danej pary (poziom, przedmiot) oznacza "przedmiot jeszcze nie
# istnieje samodzielnie na tym etapie" (np. fizyka przed klasa 7) albo
# po prostu "nie mamy jeszcze tego opisu" - w obu przypadkach
# describe_level() po cichu pomija dopisek zamiast zgadywac.
#
# Klucze przedmiotow odpowiadaja wartosciom wysylanym przez frontend
# (patrz DASH_SUBJECT_LABELS w dashboard_FINAL.html / subj-grid w
# onboarding.html): matematyka, fizyka, chemia, biologia, historia,
# polski, angielski, geografia, informatyka.
SUBJECT_SCOPE = {
    # ---------- SZKOŁA PODSTAWOWA ----------
    "podstawowka_1": {
        "matematyka": "liczenie do 20-30, dodawanie i odejmowanie w tym zakresie",
        "polski": "nauka czytania i pisania, proste zdania, rozpoznawanie liter",
        "angielski": "podstawowe słówka (kolory, zwierzęta, liczby), proste zwroty powitalne",
        "informatyka": "podstawy obsługi komputera/tabletu, gry edukacyjne, bezpieczeństwo w sieci",
    },
    "podstawowka_2": {
        "matematyka": "liczenie do 100, dodawanie i odejmowanie pisemne, wprowadzenie mnożenia",
        "polski": "czytanie ze zrozumieniem krótkich tekstów, pisanie prostych zdań",
        "angielski": "słownictwo tematyczne (rodzina, jedzenie, szkoła), proste pytania i odpowiedzi",
        "informatyka": "rysowanie w prostych programach, pierwsze algorytmy (np. Scratch Jr)",
    },
    "podstawowka_3": {
        "matematyka": "tabliczka mnożenia i dzielenia do 100, liczby do 1000, jednostki miary",
        "polski": "dłuższe teksty, elementy gramatyki (rzeczownik, czasownik), pisanie opowiadań",
        "angielski": "proste opisy (mój dzień, mój dom), czasowniki w czasie teraźniejszym",
        "informatyka": "podstawy programowania blokowego (Scratch), logiczne myślenie",
    },
    "podstawowka_4": {
        "matematyka": "ułamki zwykłe (wprowadzenie), liczby wielocyfrowe, podstawy geometrii (punkty, odcinki, kąty)",
        "polski": "pierwsze lektury szkolne, części mowy, rozprawka - wprowadzenie",
        "angielski": "czasy teraźniejsze, słownictwo rozszerzone, proste dialogi",
        "informatyka": "algorytmy w Scratch, podstawy edytora tekstu i grafiki",
        "historia": "wprowadzenie do historii - legendy, symbole narodowe, historia najbliższej okolicy",
    },
    "podstawowka_5": {
        "matematyka": "ułamki dziesiętne, działania na ułamkach, pola i obwody figur",
        "polski": "lektury (np. mitologia, baśnie), części zdania, opis i opowiadanie",
        "angielski": "czasy przeszłe - wprowadzenie, słownictwo tematyczne rozszerzone",
        "biologia": "budowa i funkcje roślin, klasyfikacja organizmów, komórka - wprowadzenie",
        "geografia": "mapa i jej elementy, kontynenty i oceany, Polska - położenie",
        "historia": "starożytność - Egipt, Grecja, Rzym, początki Polski",
        "informatyka": "algorytmika, edytory tekstu i prezentacji",
    },
    "podstawowka_6": {
        "matematyka": "liczby całkowite (ujemne), procenty - wprowadzenie, pola i obwody złożonych figur",
        "polski": "lektury (np. \"W pustyni i w puszczy\"), odmiana przez przypadki, rozprawka",
        "angielski": "czasy przeszłe - utrwalenie, konstrukcje gramatyczne złożone",
        "biologia": "układy narządów zwierząt, ekosystemy, przystosowania organizmów",
        "geografia": "Europa, klimat i strefy klimatyczne, ludność świata",
        "historia": "średniowiecze - Polska Piastów i Jagiellonów",
        "informatyka": "arkusze kalkulacyjne - podstawy, bezpieczeństwo w sieci",
    },
    "podstawowka_7": {
        "matematyka": "równania liniowe z jedną niewiadomą, wyrażenia algebraiczne, statystyka opisowa",
        "polski": "lektury (np. \"Kamienie na szaniec\"), style wypowiedzi, mowa zależna",
        "angielski": "strona bierna - wprowadzenie, słownictwo maturalne - podstawy",
        "fizyka": "wprowadzenie - ruch, siła, energia, proste zjawiska fizyczne",
        "chemia": "budowa atomu, pierwiastki i związki chemiczne, proste reakcje",
        "biologia": "genetyka - podstawy, budowa człowieka - układ nerwowy i hormonalny",
        "geografia": "Azja, Afryka, Ameryki - środowisko przyrodnicze i gospodarka",
        "historia": "nowożytność - odkrycia geograficzne, reformacja, I i II Rzeczpospolita",
        "informatyka": "podstawy programowania tekstowego, bazy danych - wprowadzenie",
    },
    "podstawowka_8": {
        "matematyka": "układy równań, twierdzenie Pitagorasa, symetrie, bryły - przygotowanie do egzaminu ósmoklasisty",
        "polski": "lektury maturalne - wprowadzenie, rozprawka egzaminacyjna, streszczenie",
        "angielski": "przygotowanie do egzaminu ósmoklasisty - wszystkie sprawności językowe",
        "fizyka": "elektryczność, optyka, przygotowanie do egzaminu ósmoklasisty",
        "chemia": "kwasy, zasady, sole, przygotowanie do egzaminu ósmoklasisty",
        "biologia": "genetyka, ewolucja, ekologia - przygotowanie do egzaminu ósmoklasisty",
        "geografia": "Polska - gospodarka i regiony, przygotowanie do egzaminu ósmoklasisty",
        "historia": "XIX i XX wiek, historia najnowsza, przygotowanie do egzaminu ósmoklasisty",
        "informatyka": "algorytmy, podstawy programowania w Pythonie",
    },

    # ---------- LICEUM ----------
    "liceum_1": {
        # Zweryfikowane wzgledem aktualnej (od 2025) podstawy programowej
        # (zpe.gov.pl, sekcja "Warunki i sposob realizacji"): logarytmy +
        # pojecie funkcji/funkcje liniowe maja byc zrealizowane w I polroczu
        # klasy 1, funkcja kwadratowa do konca klasy 1 - wczesniej mialem to
        # bledne w klasach 2-3 (za pozno wzgledem oficjalnego rozkladu).
        "matematyka": "zbiory liczbowe, potęgi i pierwiastki, funkcja liniowa, logarytmy, funkcja kwadratowa, proporcjonalność odwrotna",
        "polski": "starożytność i średniowiecze (Biblia, Iliada, pieśni)",
        "angielski": "poziom B1, gramatyka rozszerzona, słownictwo tematyczne maturalne",
        "fizyka": "kinematyka i dynamika - poziom podstawowy",
        "chemia": "chemia ogólna i nieorganiczna, budowa atomu, układ okresowy",
        "biologia": "chemia życia, budowa i funkcje komórki",
        "geografia": "geografia fizyczna świata, klimat, hydrologia",
        "historia": "starożytność i średniowiecze - cywilizacje, chrześcijaństwo",
        "informatyka": "algorytmy i podstawy programowania (Python), systemy liczbowe",
    },
    "liceum_2": {
        "matematyka": "trygonometria, ciągi arytmetyczne i geometryczne, planimetria",
        "polski": "renesans, barok, oświecenie (Kochanowski, \"Pan Tadeusz\" - wprowadzenie)",
        "angielski": "poziom B1/B2, strona bierna, mowa zależna",
        "fizyka": "praca, energia, moc, termodynamika",
        "chemia": "stechiometria, reakcje redoks, roztwory",
        "biologia": "genetyka klasyczna, fizjologia roślin i zwierząt",
        "geografia": "geografia społeczno-ekonomiczna, ludność i urbanizacja",
        "historia": "nowożytność - odkrycia geograficzne, reformacja, oświecenie",
        "informatyka": "bazy danych, struktury danych, algorytmy zaawansowane",
    },
    "liceum_3": {
        "matematyka": "funkcje wykładnicze, wprowadzenie do rachunku prawdopodobieństwa, stereometria",
        "polski": "romantyzm i pozytywizm (Mickiewicz, Słowacki, \"Lalka\")",
        "angielski": "poziom B2, słownictwo abstrakcyjne, przygotowanie do matury ustnej",
        "fizyka": "elektrostatyka, prąd elektryczny, magnetyzm",
        "chemia": "chemia organiczna - węglowodory i ich pochodne",
        "biologia": "ewolucja, ekologia, biotechnologia",
        "geografia": "geografia Polski - gospodarka i regiony",
        "historia": "XIX wiek - powstania narodowe, zabory, industrializacja",
        "informatyka": "sieci komputerowe, bezpieczeństwo danych, projektowanie aplikacji",
    },
    "liceum_4": {
        "matematyka": "powtórka całego materiału, kombinatoryka i prawdopodobieństwo, pochodne i całki (zakres rozszerzony), typowe zadania maturalne",
        "polski": "Młoda Polska i współczesność (Wyspiański, literatura XX/XXI w.), powtórka maturalna",
        "angielski": "przygotowanie maturalne - pisanie rozprawek, matura ustna",
        "fizyka": "fizyka jądrowa i atomowa, fale, powtórka maturalna",
        "chemia": "chemia organiczna zaawansowana, powtórka maturalna",
        "biologia": "fizjologia człowieka zaawansowana, powtórka maturalna",
        "geografia": "geografia globalna - problemy współczesnego świata, powtórka maturalna",
        "historia": "XX wiek - wojny światowe, PRL, III RP, powtórka maturalna",
        "informatyka": "projekt maturalny, zaawansowane algorytmy, powtórka",
    },

    # ---------- TECHNIKUM (jak liceum, przesunięte tempo + nacisk zawodowy) ----------
    "technikum_1": {
        # Technikum ma wlasna podstawe programowa (5 lat, wolniejsze tempo
        # niz liceum) - nie mam dla niej tak dokladnego oficjalnego zrodla
        # jak dla liceum, ale dostosowuje ten sam kierunek korekty (funkcja
        # kwadratowa i logarytmy przesuniete wczesniej wzgledem mojej
        # pierwotnej, zbyt pozniej wersji).
        "matematyka": "zbiory liczbowe, potęgi i pierwiastki, funkcja liniowa, funkcja kwadratowa - wprowadzenie",
        "polski": "starożytność i średniowiecze - wprowadzenie",
        "angielski": "poziom A2/B1, słownictwo ogólne i zawodowe - podstawy",
        "fizyka": "kinematyka - podstawy, zastosowania praktyczne",
        "chemia": "chemia ogólna - podstawy, zastosowania w zawodzie",
        "biologia": "budowa i funkcje komórki - wprowadzenie",
        "geografia": "geografia fizyczna świata - podstawy",
        "historia": "starożytność i średniowiecze - zarys",
        "informatyka": "podstawy programowania i obsługi komputera w zawodzie",
    },
    "technikum_2": {
        "matematyka": "logarytmy, wprowadzenie do trygonometrii, elementy geometrii analitycznej",
        "polski": "renesans i oświecenie - zarys",
        "angielski": "poziom B1, słownictwo zawodowe rozszerzone",
        "fizyka": "dynamika, praca i energia - zastosowania techniczne",
        "chemia": "reakcje chemiczne w kontekście zawodowym",
        "biologia": "fizjologia - podstawy",
        "geografia": "geografia społeczno-ekonomiczna - podstawy",
        "historia": "nowożytność - zarys",
        "informatyka": "bazy danych - podstawy, programowanie strukturalne",
    },
    "technikum_3": {
        "matematyka": "pełna trygonometria, ciągi arytmetyczne i geometryczne, planimetria",
        "polski": "romantyzm i pozytywizm - zarys",
        "angielski": "poziom B1/B2, korespondencja zawodowa",
        "fizyka": "termodynamika, elektryczność - zastosowania techniczne",
        "chemia": "chemia organiczna - podstawy zawodowe",
        "biologia": "genetyka - podstawy",
        "geografia": "geografia Polski - regiony gospodarcze",
        "historia": "XIX wiek - zarys",
        "informatyka": "sieci komputerowe - podstawy",
    },
    "technikum_4": {
        "matematyka": "logarytmy, ciągi arytmetyczne i geometryczne, funkcje wykładnicze, stereometria",
        "polski": "Młoda Polska - zarys, przygotowanie do matury",
        "angielski": "poziom B2, przygotowanie maturalne",
        "fizyka": "elektromagnetyzm - zastosowania techniczne",
        "chemia": "chemia stosowana w zawodzie",
        "biologia": "ekologia - podstawy",
        "geografia": "geografia globalna - zarys",
        "historia": "XX wiek do 1945 - zarys",
        "informatyka": "projektowanie systemów, bezpieczeństwo danych",
    },
    "technikum_5": {
        "matematyka": "powtórka całego materiału, rachunek prawdopodobieństwa, typowe zadania maturalne",
        "polski": "literatura współczesna, powtórka maturalna",
        "angielski": "przygotowanie maturalne i do egzaminu zawodowego",
        "fizyka": "powtórka maturalna",
        "chemia": "powtórka maturalna i zawodowa",
        "biologia": "powtórka maturalna",
        "geografia": "powtórka maturalna",
        "historia": "powtórka maturalna - XX i XXI wiek",
        "informatyka": "projekt dyplomowy, powtórka do egzaminu zawodowego",
    },

    # ---------- MATURA ----------
    "matura_podstawowa": {
        "matematyka": "pełny zakres podstawowy: funkcje, geometria, statystyka, typowe zadania z arkusza CKE",
        "polski": "wszystkie epoki literackie, rozprawka maturalna, część ustna",
        "angielski": "poziom B1, wszystkie sprawności językowe, typowy arkusz maturalny",
    },
    "matura_rozszerzona": {
        "matematyka": "pełny zakres rozszerzony: pochodne, całki, kombinatoryka, dowody geometryczne",
        "polski": "pogłębiona interpretacja, kontekst historycznoliteracki, wypracowanie na poziomie rozszerzonym",
        "angielski": "poziom B2/C1, tłumaczenia, rozprawka na poziomie rozszerzonym",
        "fizyka": "pełny zakres maturalny - mechanika, elektromagnetyzm, fizyka współczesna",
        "chemia": "pełny zakres maturalny - chemia nieorganiczna i organiczna, obliczenia stechiometryczne",
        "biologia": "pełny zakres maturalny - genetyka, ewolucja, fizjologia, ekologia",
        "geografia": "pełny zakres maturalny - geografia fizyczna i społeczno-ekonomiczna świata i Polski",
        "historia": "pełny zakres maturalny - źródła historyczne, analiza i argumentacja",
        "informatyka": "pełny zakres maturalny - algorytmika, programowanie, bazy danych",
    },

    # ---------- STUDIA (ogólnie, bez podziału na kierunek) ----------
    "studia_1": {
        "matematyka": "analiza matematyczna I (granice, pochodne), algebra liniowa I (macierze, wektory)",
        "informatyka": "podstawy programowania, struktury danych, logika",
    },
    "studia_2": {
        "matematyka": "analiza matematyczna II (całki, szeregi), algebra liniowa II",
        "informatyka": "algorytmy i złożoność obliczeniowa, bazy danych",
    },
    "studia_3": {
        "matematyka": "równania różniczkowe, statystyka matematyczna",
        "informatyka": "inżynieria oprogramowania, sieci komputerowe",
    },
    "studia_4": {
        "matematyka": "matematyka specjalistyczna zależna od kierunku",
        "informatyka": "systemy rozproszone, uczenie maszynowe - podstawy",
    },
    "studia_5": {
        "matematyka": "zagadnienia badawcze związane z pracą magisterską",
        "informatyka": "zagadnienia badawcze związane z pracą magisterską",
    },
}


def is_known_level(level: str) -> bool:
    """Czy `level` (lub jego alias) ma opis w LEVEL_DESC."""
    return level in LEVEL_DESC or level in ALIASES


def describe_level(level: str, fallback: str = DEFAULT_LEVEL, subject: str = None) -> str:
    """Zwraca opis poziomu do wstrzyknięcia w prompt AI.

    Działa identycznie dla koszyków ogólnych ("liceum") i konkretnych
    klas ("liceum_2") - to jeden i ten sam słownik, więc caller nie musi
    wiedzieć, jak dokładny poziom dostał.

    Nieznany `level` -> opis poziomu `fallback` (domyślnie liceum).
    Jeśli `fallback=None`, nieznany `level` jest zwracany bez zmian
    (przydatne tam, gdzie dotychczasowy kod robił zwykły passthrough).

    Jeśli podano `subject` i mamy dla tej pary (poziom, przedmiot) wpis w
    SUBJECT_SCOPE, dokładamy do opisu konkretny zakres materiału z tego
    przedmiotu. Bez `subject`, albo gdy nie mamy takiego wpisu, zwracamy
    sam opis wieku/złożoności - celowo bez zgadywania zakresu.
    """
    key = ALIASES.get(level, level)
    if key in LEVEL_DESC:
        base = LEVEL_DESC[key]
    elif fallback is None:
        return level
    else:
        key = fallback
        base = LEVEL_DESC.get(fallback, level)

    if subject:
        scope = SUBJECT_SCOPE.get(key, {}).get(subject)
        if scope:
            return f"{base} Zakres materiału z przedmiotu ({subject}): {scope}."
    return base


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
