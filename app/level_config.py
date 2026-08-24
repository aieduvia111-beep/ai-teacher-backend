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
        "matematyka": (
            "równania liniowe z jedną niewiadomą (w tym z nawiasami i ułamkami), wyrażenia "
            "algebraiczne - redukcja wyrazów podobnych, mnożenie sum algebraicznych, "
            "statystyka opisowa - średnia, mediana, dominanta. PRZYKŁAD TRUDNEGO ZADANIA: "
            "'Rozwiąż równanie 3(2x-1)-5=2(x+4).' - z wymnażaniem nawiasów po obu stronach, "
            "NIE 'x+2=5'."
        ),
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
        "matematyka": (
            "układy równań (metoda podstawiania i przeciwnych współczynników), twierdzenie "
            "Pitagorasa i jego zastosowania, symetrie, bryły (pole i objętość graniastosłupów, "
            "ostrosłupów) - przygotowanie do egzaminu ósmoklasisty na poziomie realnych "
            "arkuszy CKE. PRZYKŁAD TRUDNEGO ZADANIA: 'Rozwiąż układ równań: 2x+3y=12, "
            "x-y=1, a następnie sprawdź otrzymane rozwiązanie.' - pełny układ dwóch "
            "równań, NIE 'ile to 2+2'."
        ),
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
        "matematyka": (
            "zbiory liczbowe, potęgi i pierwiastki, funkcja liniowa, logarytmy, "
            "funkcja kwadratowa - postać ogólna/kanoniczna/iloczynowa, wzory Viète'a, "
            "równania i nierówności kwadratowe, równania i nierówności kwadratowe "
            "z parametrem, zadania optymalizacyjne z parabolą, proporcjonalność odwrotna. "
            "PRZYKŁADY TRUDNYCH ZADAŃ (tak trudne mają być zadania, NIE łatwiejsze): "
            "(funkcja kwadratowa) 'Dla jakich wartości parametru m równanie x²-(m+1)x+m=0 "
            "ma dwa różne pierwiastki dodatnie?' - to NIE jest poziom 'rozwiąż x²=4'. "
            "(funkcja liniowa) 'Wyznacz równanie prostej prostopadłej do prostej "
            "y=2x-3, przechodzącej przez punkt (4,1).' - NIE 'narysuj y=2x'. "
            "(logarytmy) 'Rozwiąż równanie log₂(x+3)+log₂(x-1)=5, sprawdzając dziedzinę.' "
            "- NIE 'oblicz log 100'. (potęgi/pierwiastki) 'Uprość wyrażenie "
            "(2^(n+2)-2^n)/(2^(n+1)) dla dowolnego naturalnego n.' - NIE '2² to ile'."
        ),
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
        "matematyka": (
            "trygonometria - tożsamości trygonometryczne, wykresy funkcji trygonometrycznych, "
            "równania trygonometryczne; ciągi arytmetyczne i geometryczne - wzór ogólny, "
            "suma n wyrazów, zastosowania (np. procent składany); planimetria - twierdzenie "
            "sinusów i cosinusów, pola figur, okręgi wpisane i opisane. "
            "PRZYKŁADY TRUDNYCH ZADAŃ (KAŻDY podtemat musi być tak trudny, nie tylko "
            "planimetria): (planimetria) 'W trójkącie kąt α=60°, boki przy tym kącie mają "
            "długość 5 i 8. Oblicz pole trójkąta i długość trzeciego boku.' - wymaga "
            "twierdzenia cosinusów i wzoru na pole z sinusem, NIE prostego 'oblicz pole "
            "prostokąta'. (ciągi) 'Ciąg arytmetyczny ma a₃=11 i a₇=27. Wyznacz a₁, różnicę r "
            "oraz najmniejsze n, dla którego suma pierwszych n wyrazów przekracza 500.' - NIE "
            "'podaj kolejny wyraz ciągu 2,4,6,8'. (trygonometria) 'Rozwiąż równanie "
            "2sin²(x)-3cos(x)=0 dla x∈[0,2π), sprowadzając do równania kwadratowego "
            "względem cos(x).' - NIE 'ile wynosi sin(30°)'."
        ),
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
        "matematyka": (
            "funkcje wykładnicze - własności, wykresy, równania i nierówności wykładnicze; "
            "wprowadzenie do rachunku prawdopodobieństwa - klasyczna definicja "
            "prawdopodobieństwa, prawdopodobieństwo warunkowe; stereometria - graniastosłupy, "
            "ostrosłupy, bryły obrotowe, przekroje brył. UWAGA: NIE wybieraj ogólnej "
            "zbieżności szeregów (np. szeregi potęgowe, kryteria zbieżności) - to material "
            "studiów (analiza matematyczna), NIE liceum. "
            "PRZYKŁADY TRUDNYCH ZADAŃ (KAŻDY podtemat, nie tylko prawdopodobieństwo): "
            "(prawdopodobieństwo) 'W urnie jest 5 kul białych i 3 czarne. Losujemy bez "
            "zwracania dwie kule. Oblicz prawdopodobieństwo, że obie są tego samego koloru.' "
            "- wymaga prawdopodobieństwa warunkowego/łącznego, NIE 'rzucasz monetą, jakie "
            "prawdopodobieństwo orła'. (funkcje wykładnicze) 'Rozwiąż nierówność "
            "4^x-3·2^x-4≤0, podstawiając t=2^x.' - NIE 'oblicz 2 do potęgi 3'. "
            "(stereometria) 'Podstawą ostrosłupa prawidłowego czworokątnego jest kwadrat o "
            "boku 6, a krawędź boczna ma długość 10. Oblicz objętość i pole powierzchni "
            "całkowitej.' - NIE 'ile ścian ma sześcian'."
        ),
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
        "matematyka": (
            "powtórka całego materiału liceum; kombinatoryka i prawdopodobieństwo - "
            "permutacje, kombinacje, wariacje, schemat Bernoulliego; pochodne i całki "
            "(zakres rozszerzony) - reguła łańcuchowa, badanie przebiegu funkcji, ekstrema, "
            "całki oznaczone i pola pod wykresem; typowe zadania maturalne z pełnym zakresu. "
            "UWAGA: NIE wybieraj ogólnej zbieżności szeregów (np. szeregi potęgowe, kryteria "
            "zbieżności) - to material studiów (analiza matematyczna), NIE matury. "
            "PRZYKŁADY TRUDNYCH ZADAŃ (KAŻDY podtemat, nie tylko pochodne): "
            "(pochodne) 'Zbadaj monotoniczność i wyznacz ekstrema funkcji f(x)=x³-3x²+2 "
            "oraz naszkicuj jej wykres.' - pełne badanie funkcji z pochodną, NIE 'oblicz "
            "pochodną z x²'. (całki) 'Oblicz pole obszaru ograniczonego wykresami funkcji "
            "f(x)=x² i g(x)=2x.' - wymaga znalezienia punktów przecięcia i całki oznaczonej "
            "z różnicy funkcji, NIE 'oblicz całkę z x²'. (kombinatoryka/prawdopodobieństwo) "
            "'Z talii 52 kart losujemy 5. Oblicz prawdopodobieństwo, że wśród nich są "
            "dokładnie 2 asy.' - schemat kombinacji z prawdopodobieństwem klasycznym, NIE "
            "'ile jest asów w talii'."
        ),
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
        "matematyka": (
            "zbiory liczbowe, potęgi i pierwiastki, funkcja liniowa, funkcja kwadratowa - "
            "postać ogólna i kanoniczna, rozwiązywanie równań kwadratowych (delta). "
            "PRZYKŁADY TRUDNYCH ZADAŃ: (funkcja kwadratowa) 'Rozwiąż równanie 2x²-5x+3=0 i "
            "sprawdź znak wyróżnika przed obliczeniem pierwiastków.' - z pełnym wzorem i "
            "deltą, NIE 'rozwiąż x²=9'. (funkcja liniowa) 'Wyznacz wzór funkcji liniowej, "
            "której wykres przechodzi przez punkty (1,5) i (3,-1).' - NIE 'narysuj y=x'."
        ),
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
        "matematyka": (
            "logarytmy - własności i równania logarytmiczne, wprowadzenie do trygonometrii, "
            "elementy geometrii analitycznej (równanie prostej, odległość punktów). "
            "PRZYKŁADY TRUDNYCH ZADAŃ: (logarytmy) 'Rozwiąż równanie log₂(x+1)+log₂(x-1)=3.' "
            "- z dziedziną i własnościami logarytmów, NIE 'oblicz log 100'. (geometria "
            "analityczna) 'Oblicz odległość punktu A=(3,4) od prostej o równaniu "
            "3x-4y+5=0.' - wzór na odległość punktu od prostej, NIE 'narysuj punkt na "
            "układzie współrzędnych'. UWAGA: NIE wybieraj "
            "'równań liniowych' ani 'układów równań liniowych' jako tematu - to materiał "
            "z młodszych klas (technikum_1/podstawówka), nie z tego zakresu."
        ),
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
        "matematyka": (
            "pełna trygonometria - tożsamości i równania, ciągi arytmetyczne i "
            "geometryczne - wzór ogólny i suma n wyrazów, planimetria - twierdzenie "
            "sinusów i cosinusów. PRZYKŁADY TRUDNYCH ZADAŃ: (ciągi) 'Ciąg arytmetyczny ma "
            "a₃=7 i a₇=19. Wyznacz a₁, różnicę r oraz sumę pierwszych 20 wyrazów.' - NIE "
            "'podaj kolejny wyraz ciągu 2,4,6,8'. (trygonometria/planimetria) 'W trójkącie "
            "boki mają długość a=7, b=9, kąt między nimi γ=50°. Oblicz długość trzeciego "
            "boku oraz pole trójkąta.' - twierdzenie cosinusów + wzór na pole z sinusem, "
            "NIE 'ile wynosi sin(30°)'. UWAGA: NIE wybieraj 'macierzy' (wyznaczniki, "
            "macierz odwrotna) jako tematu - to NIE jest część tego zakresu."
        ),
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
        "matematyka": (
            "logarytmy, ciągi arytmetyczne i geometryczne (w tym suma szeregu geometrycznego "
            "zbieżnego), funkcje wykładnicze - równania i nierówności, stereometria - "
            "graniastosłupy i ostrosłupy. PRZYKŁADY TRUDNYCH ZADAŃ: (funkcje wykładnicze) "
            "'Rozwiąż nierówność 3^(2x-1) > 27.' - z zamianą na wspólną podstawę i "
            "porównaniem wykładników, NIE '3 do potęgi 2 to ile'. (logarytmy) 'Rozwiąż "
            "równanie log₃(x²-8)=2.' - z uwzględnieniem dziedziny, NIE 'oblicz log₃9'. "
            "(stereometria) 'Podstawą graniastosłupa prawidłowego czworokątnego jest kwadrat "
            "o boku 4, a wysokość bryły wynosi 10. Oblicz pole powierzchni całkowitej i "
            "objętość.' - NIE 'ile ścian ma sześcian'. UWAGA: NIE wybieraj 'całek' "
            "(rachunek różniczkowy i całkowy) ani ogólnej zbieżności szeregów potęgowych - "
            "to material studiów, NIE technikum."
        ),
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
        "matematyka": (
            "powtórka całego materiału, rachunek prawdopodobieństwa - kombinacje i schemat "
            "Bernoulliego, typowe zadania maturalne z pełnego zakresu podstawowego. "
            "PRZYKŁAD TRUDNEGO ZADANIA: 'Rzucamy 5 razy symetryczną monetą. Oblicz "
            "prawdopodobieństwo otrzymania dokładnie 3 orłów.' - schemat Bernoulliego z "
            "obliczeniem, NIE 'jakie prawdopodobieństwo orła przy jednym rzucie'."
        ),
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
        "matematyka": (
            "pełny zakres podstawowy: funkcje liniowe i kwadratowe, ciągi, trygonometria, "
            "planimetria i stereometria, elementy statystyki i prawdopodobieństwa - poziom "
            "i format typowego arkusza CKE poziom podstawowy. PRZYKŁADY TRUDNYCH ZADAŃ: "
            "(funkcje/geometria analityczna) 'Dane są punkty A=(-2,1) i B=(4,5). Wyznacz "
            "równanie prostej prostopadłej do AB, przechodzącej przez środek odcinka AB.' - "
            "typowe zadanie z arkusza CKE, NIE 'oblicz odległość dwóch punktów na osi "
            "liczbowej'. (ciągi) 'Ciąg geometryczny ma a₁=3 i q=2. Wyznacz najmniejsze n, "
            "dla którego suma pierwszych n wyrazów przekracza 300.' - NIE 'podaj następny "
            "wyraz ciągu 2,4,8'. (trygonometria/planimetria) 'W trójkącie prostokątnym "
            "przeciwprostokątna ma długość 10, a jeden z kątów ostrych 35°. Oblicz długości "
            "przyprostokątnych.' - NIE 'ile wynosi sin(30°)'. (statystyka/prawdopodobieństwo) "
            "'W klasie jest 12 dziewcząt i 8 chłopców. Losujemy 3 osoby. Oblicz "
            "prawdopodobieństwo, że wśród nich będzie dokładnie 1 chłopiec.' - NIE 'ile "
            "osób jest w klasie'."
        ),
        "polski": "wszystkie epoki literackie, rozprawka maturalna, część ustna",
        "angielski": "poziom B1, wszystkie sprawności językowe, typowy arkusz maturalny",
    },
    "matura_rozszerzona": {
        "matematyka": (
            "pełny zakres rozszerzony: pochodne i badanie przebiegu funkcji, całki oznaczone "
            "i nieoznaczone, kombinatoryka i prawdopodobieństwo, dowody geometryczne, "
            "równania i nierówności z wartością bezwzględną, ciągi rekurencyjne - poziom i "
            "format arkusza CKE poziom rozszerzony. PRZYKŁADY TRUDNYCH ZADAŃ: (dowody) "
            "'Wykaż, że dla dowolnego trójkąta ostrokątnego wpisanego w okrąg o promieniu "
            "R, pole trójkąta wyraża się wzorem P=2R²sinAsinBsinC.' - dowód na poziomie "
            "rozszerzonym, NIE 'oblicz pole trójkąta o podanych bokach'. (pochodne/całki) "
            "'Wyznacz największą i najmniejszą wartość funkcji f(x)=x³-3x na przedziale "
            "[-2,3].' - badanie funkcji z pochodną na przedziale domkniętym, NIE 'oblicz "
            "pochodną z x²'. (kombinatoryka/prawdopodobieństwo) 'Ile jest liczb "
            "czterocyfrowych o różnych cyfrach, podzielnych przez 5?' - łączenie reguły "
            "mnożenia z warunkiem podzielności, NIE 'ile jest liczb dwucyfrowych'. "
            "(wartość bezwzględna) 'Rozwiąż nierówność |2x-3|+|x+1|≤6.' - z rozbiciem na "
            "przedziały, NIE '|−5| to ile'. (ciągi rekurencyjne) 'Ciąg dany jest wzorem "
            "a₁=2, a_(n+1)=3a_n-1. Wyznacz a₅ oraz zbadaj, czy ciąg jest monotoniczny.' - "
            "NIE 'podaj a₂ dla a₁=1, a_(n+1)=a_n+1'."
        ),
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
        "matematyka": (
            "analiza matematyczna I - granice ciągów i funkcji (w tym symbole nieoznaczone), "
            "pochodne i ich zastosowania (reguła de l'Hospitala, ekstrema, wypukłość); "
            "algebra liniowa I - macierze, wyznaczniki, układy równań liniowych (eliminacja "
            "Gaussa), przestrzenie wektorowe - wprowadzenie. PRZYKŁADY TRUDNYCH ZADAŃ: "
            "(granice) 'Oblicz granicę lim(x→0) (e^x-1-x)/x², stosując regułę de "
            "l'Hospitala dwukrotnie.' - NIE 'oblicz lim(x→∞) 1/x'. (algebra liniowa) "
            "'Rozwiąż metodą eliminacji Gaussa układ trzech równań liniowych z trzema "
            "niewiadomymi i zbadaj rząd macierzy współczynników.' - NIE 'oblicz wyznacznik "
            "macierzy 2x2'."
        ),
        "informatyka": "podstawy programowania, struktury danych, logika",
    },
    "studia_2": {
        "matematyka": (
            "analiza matematyczna II - całki (w tym przez podstawienie i przez części), "
            "szeregi liczbowe i ich zbieżność; algebra liniowa II - przestrzenie wektorowe, "
            "wartości i wektory własne. To ma być WYRAŹNIE trudniejsze niż I rok - NIE "
            "sama całka z wielomianu (to material I roku), tylko np. całkowanie przez "
            "podstawienie/przez części lub badanie zbieżności szeregu. PRZYKŁADY TRUDNYCH "
            "ZADAŃ: (całki) 'Oblicz całkę ∫x·ln(x)dx metodą całkowania przez części.' - NIE "
            "'oblicz całkę z x²'. (szeregi) 'Zbadaj zbieżność szeregu Σ(n=1 do ∞) n/(2^n), "
            "stosując kryterium d'Alemberta.' - NIE 'wypisz pierwsze 3 wyrazy szeregu'. "
            "(algebra liniowa) 'Wyznacz wartości i wektory własne macierzy [[2,1],[1,2]].' "
            "- NIE 'dodaj dwie macierze 2x2'."
        ),
        "informatyka": "algorytmy i złożoność obliczeniowa, bazy danych",
    },
    "studia_3": {
        "matematyka": (
            "równania różniczkowe (zwyczajne, w tym liniowe I rzędu i o zmiennych "
            "rozdzielonych), statystyka matematyczna - estymacja, testy hipotez. "
            "PRZYKŁADY TRUDNYCH ZADAŃ: (równania różniczkowe) 'Rozwiąż równanie "
            "różniczkowe y'+2y=e^(-x) metodą czynnika całkującego.' - NIE prosta całka z "
            "wielomianu (to material I roku). (statystyka matematyczna) 'Z próby losowej "
            "n=36 o średniej x̄=52 i odchyleniu standardowym s=6, zbuduj 95% przedział "
            "ufności dla średniej populacji.' - NIE 'oblicz średnią z 5 liczb'."
        ),
        "informatyka": "inżynieria oprogramowania, sieci komputerowe",
    },
    "studia_4": {
        "matematyka": (
            "matematyka specjalistyczna zależna od kierunku - typowo: rachunek "
            "prawdopodobieństwa i procesy stochastyczne (zmienne losowe, rozkłady, wartość "
            "oczekiwana, łańcuchy Markowa), metody numeryczne (interpolacja, całkowanie "
            "numeryczne, rozwiązywanie równań nieliniowych). PRZYKŁADY TRUDNYCH ZADAŃ: "
            "(prawdopodobieństwo/procesy stochastyczne) 'Dla łańcucha Markowa o macierzy "
            "przejścia P=[[0.7,0.3],[0.4,0.6]] wyznacz rozkład stacjonarny.' - NIE 'oblicz "
            "prawdopodobieństwo orła przy rzucie monetą'. (metody numeryczne) 'Znajdź "
            "przybliżone miejsce zerowe funkcji f(x)=x³-x-2 metodą Newtona, wykonując 3 "
            "iteracje od x₀=1.5.' - NIE 'oblicz f(2) dla f(x)=x²'."
        ),
        "informatyka": "systemy rozproszone, uczenie maszynowe - podstawy",
    },
    "studia_5": {
        "matematyka": (
            "zagadnienia badawcze związane z pracą magisterską - poziom ekspercki: "
            "twierdzenia z dowodem, zaawansowana analiza funkcjonalna/topologia/algebra "
            "abstrakcyjna (w zależności od specjalizacji), zastosowanie wyników z aktualnej "
            "literatury naukowej. To NIE jest poziom standardowych ćwiczeń z I-II roku "
            "(np. prosta całka z wielomianu czy wyznacznik macierzy trójkątnej) - zadania "
            "mają wymagać samodzielnego dowodu lub analizy nietrywialnego przypadku. "
            "PRZYKŁAD: 'Udowodnij, że przestrzeń unormowana skończenie wymiarowa jest "
            "zupełna' - dowód na poziomie pracy magisterskiej, NIE 'oblicz całkę z x²'."
        ),
        "informatyka": (
            "zagadnienia badawcze związane z pracą magisterską - poziom ekspercki: "
            "analiza złożoności nietrywialnych algorytmów, zaawansowane struktury danych, "
            "zastosowanie wyników z aktualnej literatury naukowej (np. uczenie maszynowe, "
            "systemy rozproszone - zależnie od specjalizacji). To NIE jest poziom "
            "podstawowych ćwiczeń z algorytmiki I-II roku."
        ),
    },
}


# ============================================================
# WALIDACJA TEMATU (dla trybu "AI samo wybiera temat" - patrz
# generate_quiz_from_topic w openai_exam.py)
# ============================================================
# Audyt 24 poziomow (temat generyczny, AI samo wybiera z SUBJECT_SCOPE)
# pokazal, ze sam opis zakresu w prompcie NIE wystarcza - dla kilku
# poziomow (glownie liceum_3/4, technikum_2/3/4, studia_2/3/5) model
# uporczywie wybieral temat spoza podanego zakresu (np. "rownania
# kwadratowe" jako "typowy" temat matematyki liceum, albo dryfowal w
# strone materialu ze studiow - szeregi, granice, macierze - dla
# technikum/liceum). To PROSTA walidacja tekstowa (substring match, BEZ
# kolejnego wywolania AI) uzywana przez generate_quiz_from_topic do
# sprawdzenia, czy wygenerowany temat faktycznie pasuje do zakresu, z
# mozliwoscia ponowienia generacji lub wymuszenia konkretnego tematu.
#
# "allowed": jesli lista niepusta, tytul+tresc pytan MUSI zawierac
# przynajmniej jeden z tych fragmentow (case-insensitive substring).
# "forbidden": jesli tytul+tresc zawiera ktorykolwiek z tych fragmentow,
# walidacja NIE przechodzi (typowe tematy z INNYCH klas/poziomow, ktore
# model wybieral zamiast podanego zakresu).
# Brak wpisu dla danej pary (poziom, przedmiot) = walidacja pomijana
# (nie blokujemy tematow, dla ktorych nie mamy jeszcze danych).
GENERIC_TOPIC_KEYWORDS = {
    "liceum_1": {"matematyka": {
        "allowed": [("funkcj", "liniow"), "funkcje liniow", ("funkcj", "kwadratow"), ("funkcj", "kwadratow"),
                    "logarytm", "potęg", "pierwiastk", "zbiór liczbow", "zbiory liczbow",
                    "proporcjonalność odwrotn", "wzory viet", "wzór viet"],
        "forbidden": ["trygonometri", "ciąg arytmetyczny", "ciąg geometryczny", "planimetri",
                      "szereg", "całka", "pochodn", "macierz", "prawdopodobieńst", "stereometri"],
    }},
    "liceum_2": {"matematyka": {
        "allowed": ["trygonometri", "ciąg arytmetyczny", "ciąg geometryczny", "planimetri",
                    "twierdzenie sinus", "twierdzenie cosinus"],
        "forbidden": [("równani", "kwadratow"), ("funkcj", "kwadratow"), "logarytm", "szereg", "całka",
                      "pochodn", "macierz", "prawdopodobieńst", "stereometri", ("funkcj", "wykładnicz")],
    }},
    "liceum_3": {"matematyka": {
        "allowed": [("funkcj", "wykładnicz"), ("funkcj", "wykładnicz"), ("równani", "wykładnicz"),
                    ("nierówno", "wykładnicz"), "prawdopodobieńst", "stereometri", "graniastosłup",
                    "ostrosłup", ("brył", "obrotow"), "przekrój bryły", "walec", "stożek", "kula"],
        "forbidden": ["szereg", "zbieżność szeregu", "szereg potęgow", "granica ciągu",
                      "granica funkcji", ("równani", "kwadratow"), "trygonometri", "macierz", "całka"],
    }},
    "liceum_4": {"matematyka": {
        "allowed": ["kombinatoryka", "permutacj", "kombinacj", "wariacj", "schemat bernoulli",
                    "pochodn", "całka oznaczon", "całka nieoznaczon", "ekstrem",
                    "badanie przebiegu funkcji", "maturaln"],
        "forbidden": ["szereg", "zbieżność szeregu", "szereg potęgow", "granica ciągu", "macierz",
                      ("równani", "kwadratow")],
    }},
    "technikum_1": {"matematyka": {
        "allowed": [("funkcj", "liniow"), ("funkcj", "kwadratow"), "zbiór liczbow", "zbiory liczbow",
                    "potęg", "pierwiastk"],
        "forbidden": ["trygonometri", "logarytm", "geometria analityczn", "macierz", "całka",
                      "szereg", ("równani", "różniczkow")],
    }},
    "technikum_2": {"matematyka": {
        "allowed": ["logarytm", "trygonometri", "geometria analityczn", ("równani", "prostej"),
                    "odległość punkt"],
        "forbidden": [("równani", "liniow"), "układ równań", ("funkcj", "kwadratow"), "macierz", "całka",
                      "szereg", "granica"],
    }},
    "technikum_3": {"matematyka": {
        "allowed": ["trygonometri", "ciąg arytmetyczny", "ciąg geometryczny", "planimetri",
                    "twierdzenie sinus", "twierdzenie cosinus"],
        "forbidden": ["macierz", "wyznacznik", "całka", "szereg", "granica ciągu",
                      "granica funkcji", ("równani", "kwadratow")],
    }},
    "technikum_4": {"matematyka": {
        "allowed": ["logarytm", ("funkcj", "wykładnicz"), ("równani", "wykładnicz"), ("nierówno", "wykładnicz"),
                    "stereometri", "graniastosłup", "ostrosłup", "ciąg arytmetyczny",
                    "ciąg geometryczny"],
        "forbidden": ["macierz", "wyznacznik", "całka", ("równani", "różniczkow"), "granica ciągu",
                      "granica funkcji"],
    }},
    "technikum_5": {"matematyka": {
        "allowed": ["rachunek prawdopodobieńst", "schemat bernoulli", "maturaln", "powtórka"],
        "forbidden": ["macierz", "całka", ("równani", "różniczkow")],
    }},
    "matura_podstawowa": {"matematyka": {
        "allowed": [("funkcj", "liniow"), ("funkcj", "kwadratow"), "ciąg", "trygonometri", "planimetri",
                    "stereometri", "statystyk", "prawdopodobieńst"],
        "forbidden": ["macierz", "całka", "pochodn", ("równani", "różniczkow"), "szereg"],
    }},
    "matura_rozszerzona": {"matematyka": {
        "allowed": ["pochodn", "całka", "kombinatoryka", "prawdopodobieńst", "dowód geometryczn",
                    "wartość bezwzględn", "ciąg rekurencyjn"],
        "forbidden": ["macierz", ("równani", "różniczkow")],
    }},
    "studia_2": {"matematyka": {
        "allowed": ["całk", "szereg", "zbieżność szeregu", "wartości własne", "wektor własn",
                    "przestrzeń wektorow"],
        "forbidden": [("równani", "różniczkow"), "statystyka matematyczn"],
    }},
    "studia_3": {"matematyka": {
        "allowed": [("równani", "różniczkow"), "statystyka matematyczn", "estymacj", "test hipotez",
                    "czynnik całkując"],
        "forbidden": ["szereg", "zbieżność szeregu"],
    }},
    "studia_5": {"matematyka": {
        "allowed": ["dowód", "udowodnij", "wykaż", "twierdzeni"],
        "forbidden": [],
    }},
}

# Fallback, gdy nawet po kilku probach AI nie wybiera tematu z zakresu -
# wtedy zamiast dalej pozwalac AI "wybierac samemu", wymuszamy JEDEN
# konkretny, sprawdzony temat (to samo, co user wpisujacy konkretny
# temat recznie - ta sciezka dziala niezawodnie, bo "temat ma najwyzszy
# priorytet" jest respektowane przez model duzo silniej niz "wybierz
# cokolwiek z listy").
FORCED_FALLBACK_TOPICS = {
    "liceum_1": {"matematyka": "Funkcja kwadratowa - równania i nierówności z parametrem"},
    "liceum_2": {"matematyka": "Trygonometria - tożsamości i równania trygonometryczne"},
    # liceum_3/4 i studia_5: LISTA kilku tematow, nie jeden - Sugerowany
    # Quiz na Dashboardzie ma sie zmieniac codziennie, wiec jeden staly
    # fallback zniszczylby ta rotacje dla tych poziomow (AI prawie nigdy
    # nie trafia tu samo w zakres, wiec fallback jest w praktyce GLOWNA
    # sciezka, nie tylko siatka bezpieczenstwa - patrz audyt w komentarzu
    # przy generate_quiz_from_topic).
    "liceum_3": {"matematyka": [
        "Prawdopodobieństwo klasyczne i warunkowe",
        "Funkcja wykładnicza - równania i nierówności z parametrem",
        "Stereometria - graniastosłupy i ostrosłupy, obliczanie objętości",
        "Bryły obrotowe - walec, stożek i kula w zadaniach maturalnych",
    ]},
    "liceum_4": {"matematyka": [
        "Kombinatoryka i rachunek prawdopodobieństwa - zadania maturalne",
        "Pochodne - badanie przebiegu funkcji i ekstrema",
        "Całka oznaczona - obliczanie pól figur",
        "Permutacje, kombinacje i wariacje - kombinatoryka maturalna",
    ]},
    "technikum_1": {"matematyka": "Funkcja kwadratowa - wprowadzenie"},
    "technikum_2": {"matematyka": "Logarytmy - równania logarytmiczne"},
    "technikum_3": {"matematyka": "Ciągi arytmetyczne i geometryczne"},
    "technikum_4": {"matematyka": "Funkcje wykładnicze - równania i nierówności"},
    "technikum_5": {"matematyka": "Rachunek prawdopodobieństwa - schemat Bernoulliego"},
    "matura_podstawowa": {"matematyka": "Funkcja kwadratowa i trygonometria - zadania typu CKE"},
    "matura_rozszerzona": {"matematyka": "Pochodne i badanie przebiegu funkcji"},
    "studia_2": {"matematyka": "Szeregi liczbowe - badanie zbieżności"},
    "studia_3": {"matematyka": "Równania różniczkowe zwyczajne pierwszego rzędu"},
    "studia_5": {"matematyka": [
        "Dowód twierdzenia z analizy funkcjonalnej - przestrzenie unormowane",
        "Dowód twierdzenia o zwartości w przestrzeniach metrycznych",
        "Wykaż zbieżność ciągu funkcyjnego - twierdzenie o zbieżności jednostajnej",
        "Dowód twierdzenia z topologii ogólnej - zwartość i spójność",
    ]},
}


def _keyword_hit(combined: str, item) -> bool:
    """Jeden wpis w allowed/forbidden: string = pojedynczy substring,
    tuple/list = WSZYSTKIE czesci musza wystapic (gdziekolwiek w tekscie,
    niekoniecznie obok siebie) - uzywane zamiast jednej zlaczonej frazy,
    bo polska odmiana (funkcja/funkcje/funkcji, rownanie/rownania) psuje
    dopasowanie zlaczonej frazy z literalna spacja w srodku."""
    if isinstance(item, (list, tuple)):
        return all(part in combined for part in item)
    return item in combined


def validate_generic_topic(quiz_data: dict, level: str, subject: str) -> bool:
    """Sprawdza (prostym substring-matchem, bez kolejnego wywolania AI),
    czy temat wygenerowany przez AI w trybie "samo wybiera" faktycznie
    miesci sie w zakresie tej klasy. True = OK albo brak danych do
    walidacji (nie blokujemy). False = wykryto temat spoza zakresu."""
    key = ALIASES.get(level, level)
    spec = GENERIC_TOPIC_KEYWORDS.get(key, {}).get(subject.strip().lower())
    if not spec:
        return True
    title = (quiz_data.get("title") or "").lower()
    questions_text = " ".join(
        q.get("question", "") for q in quiz_data.get("questions", []) if isinstance(q, dict)
    ).lower()
    combined = f"{title} {questions_text}"
    forbidden = spec.get("forbidden", [])
    if any(_keyword_hit(combined, f) for f in forbidden):
        return False
    allowed = spec.get("allowed", [])
    if allowed and not any(_keyword_hit(combined, a) for a in allowed):
        return False
    return True


def get_forced_fallback_topic(level: str, subject: str) -> str:
    """Konkretny temat do wymuszenia, gdy AI nie potrafi trafic w zakres
    samo (patrz FORCED_FALLBACK_TOPICS). Wartosc moze byc pojedynczym
    stringiem (jeden staly temat) albo lista - wtedy losujemy jeden z
    nich, zeby powtarzane wywolania (np. codzienny Sugerowany Quiz na
    Dashboardzie) nie utknely na jednym, zawsze tym samym temacie.
    None = brak zdefiniowanego fallbacku dla tej pary (poziom, przedmiot)."""
    import random
    key = ALIASES.get(level, level)
    topic = FORCED_FALLBACK_TOPICS.get(key, {}).get(subject.strip().lower())
    if isinstance(topic, (list, tuple)):
        return random.choice(topic) if topic else None
    return topic


# ============================================================
# SKALA TRUDNOSCI 1-10 DLA ROWNAN KWADRATOWYCH (matematyka)
# ============================================================
# Pierwszy, scelowany krok w strone pelnego systemu trudnosci (patrz
# TODO z podsumowania sesji - pelna wersja ChatGPT: skala 1-10 +
# kryteria per-temat + wielowarstwowa walidacja, dla WSZYSTKICH
# tematow). Zaczynamy TYLKO od rownan kwadratowych, bo to jedyny
# temat z pelna infrastruktura weryfikacji (math_verify.py +
# final_answer) - kazdy nowy przyklad ponizej jest od razu chroniony
# istniejacym mechanizmem. Inne tematy nadal dostaja tylko pojedyncze
# slowo latwy/sredni/trudny, jak dotychczas - to swiadome, gated
# rozszerzenie, nie zmiana globalnego zachowania.
QUADRATIC_DIFFICULTY_TIERS = {
    "1-2": {
        "kryterium": (
            "Bezposredni rozklad na czynniki, calkowite wspolczynniki, "
            "oczywisty wzor skroconego mnozenia - BEZ liczenia delty."
        ),
        "przyklad": "x² - 5x + 6 = 0",
    },
    "3-4": {
        "kryterium": (
            "Standardowy wzor na delte, wieksze lub niecalkowite "
            "wspolczynniki, brak latwego rozkladu na czynniki."
        ),
        "przyklad": "2x² - 7x + 3 = 0",
    },
    "5-6": {
        "kryterium": (
            "Jeden parametr, prosty warunek na delte - bezposrednie "
            "podstawienie do wzoru na delte i rozwiazanie nierownosci "
            "LINIOWEJ wzgledem parametru."
        ),
        "przyklad": "Dla jakich wartości parametru m równanie x²+(m-3)x+m=0 ma dwa różne pierwiastki?",
    },
    "7-8": {
        "kryterium": (
            "Parametr + warunek ZLOZONY - znak pierwiastkow przez wzory "
            "Viete'a, ALBO parametr jako wspolczynnik wiodacy (wymaga "
            "dodatkowego zalozenia wspolczynnik != 0)."
        ),
        "przyklad": "Dla jakich wartości parametru a równanie ax²-(2a+3)x+a+2=0 ma dwa różne pierwiastki dodatnie?",
    },
    "9-10": {
        "kryterium": (
            "Wymaga analizy KILKU przypadkow jednoczesnie (np. osobno "
            "przypadek degeneracji do rownania liniowego), dowodu, ALBO "
            "polaczenia z zadaniem geometrycznym/optymalizacyjnym."
        ),
        "przyklad": "Dla jakich wartości parametru k równanie kx²-(k+2)x+2=0 ma dokładnie jedno rozwiązanie rzeczywiste? (rozważ osobno k=0 i k≠0)",
    },
}

_QUADRATIC_DIFFICULTY_WORD_TO_TIER = {
    "easy": "1-2", "latwy": "1-2", "łatwy": "1-2", "latwa": "1-2", "łatwa": "1-2",
    "medium": "5-6", "sredni": "5-6", "średni": "5-6", "srednia": "5-6", "średnia": "5-6",
    "hard": "7-8", "trudny": "7-8", "trudna": "7-8",
}


def get_quadratic_difficulty_anchor(difficulty_word: str):
    """Zwraca tekst kryterium+przykladu (skala 1-10) dla podanego slowa
    trudnosci (easy/medium/hard - Quiz; latwy/sredni/trudny lub
    latwa/srednia/trudna - Sprawdzian). None jesli slowo nierozpoznane
    (wtedy caller ma spasc na stare, generyczne zachowanie)."""
    tier = _QUADRATIC_DIFFICULTY_WORD_TO_TIER.get((difficulty_word or "").strip().lower())
    if not tier:
        return None
    data = QUADRATIC_DIFFICULTY_TIERS[tier]
    return (
        f"POZIOM TRUDNOSCI {tier}/10 (skala dla rownan kwadratowych): {data['kryterium']} "
        f"Przyklad zadania na tym poziomie: '{data['przyklad']}'. "
        f"Wygeneruj zadanie o TAKIM WLASNIE poziomie trudnosci - nie latwiejsze, nie trudniejsze."
    )


def is_quadratic_equation_topic(topic: str) -> bool:
    """Proste wykrycie, czy temat dotyczy rownan kwadratowych - uzywane
    do "gated injection" skali 1-10 (dziala TYLKO dla tego tematu, inne
    tematy sa niedotkniete - nie zmieniamy globalnego zachowania)."""
    t = (topic or "").lower()
    return ("równani" in t or "rownani" in t) and "kwadratow" in t


# ETAP 6: analogiczna "gated injection" skala trudnosci dla ciagow
# arytmetycznych/geometrycznych - patrz QUADRATIC_DIFFICULTY_TIERS wyzej
# po uzasadnienie wzorca. Skala tu to 1-5 (nie 1-10), bo tyle rozpoznawalnych
# pasm daje dzis detect_sequence_intent/classify_sequence_difficulty w
# math_verify.py - kazde pasmo nadal odpowiada WIELU roznym wzorcom zadan
# (np. pasmo "4-5" obejmuje uklad-2-wyrazow, wyraz+suma, ORAZ szukanie n z
# sumy), zeby "hard" nie oznaczalo w praktyce jednego powtarzalnego typu
# zadania (wyraznie wymagane przez usera).
SEQUENCE_DIFFICULTY_TIERS = {
    "1": {
        "kryterium": (
            "Podstawienie n do wzoru na n-ty wyraz (a1 i r/q dane wprost) - "
            "JEDNO dzialanie, bez ukladu rownan."
        ),
        "przyklad": "Ciąg arytmetyczny ma a1=3, r=5. Oblicz dziesiąty wyraz tego ciągu.",
    },
    "2-3": {
        "kryterium": (
            "Wyznaczenie sumy n poczatkowych wyrazow (dane a1 i r/q), ALBO "
            "wyznaczenie liczby wyrazow n z warunku na ostatni wyraz, ALBO "
            "wyznaczenie a1 z danej sumy i r/q - jeden konkretny warunek, "
            "BEZ ukladu 2 rownan."
        ),
        "przyklad": "Ciąg arytmetyczny ma a1=2, r=3. Oblicz sumę pierwszych 10 wyrazów tego ciągu.",
    },
    "4-5": {
        "kryterium": (
            "Uklad DWOCH warunkow jednoczesnie, prowadzacy do ukladu 2 rownan "
            "na a1 i r/q: dwa rozne wyrazy ciagu, ALBO jeden wyraz + suma, "
            "ALBO wyznaczenie n z rownania (suma pierwszych n wyrazow rowna "
            "danej liczbie). Uzyj ROZNORODNYCH wzorcow z tej listy, nie "
            "zawsze tego samego."
        ),
        "przyklad": (
            "Rozne przyklady na tym poziomie: 'W ciągu arytmetycznym a3=10, "
            "a7=22. Wyznacz pierwszy wyraz i różnicę.' LUB 'W ciągu "
            "arytmetycznym a2=7. Suma pierwszych 4 wyrazów wynosi 26. "
            "Wyznacz pierwszy wyraz i różnicę.' LUB 'Ciąg arytmetyczny ma "
            "a1=3, r=2. Suma pierwszych n wyrazów wynosi 120. Wyznacz n.'"
        ),
    },
}

_SEQUENCE_DIFFICULTY_WORD_TO_TIER = {
    "easy": "1", "latwy": "1", "łatwy": "1", "latwa": "1", "łatwa": "1",
    "medium": "2-3", "sredni": "2-3", "średni": "2-3", "srednia": "2-3", "średnia": "2-3",
    "hard": "4-5", "trudny": "4-5", "trudna": "4-5",
}


def get_sequence_difficulty_anchor(difficulty_word: str):
    """Zwraca tekst kryterium+przykladow (skala 1-5) dla podanego slowa
    trudnosci, analogicznie do get_quadratic_difficulty_anchor. None jesli
    slowo nierozpoznane (wtedy caller ma spasc na stare, generyczne
    zachowanie)."""
    tier = _SEQUENCE_DIFFICULTY_WORD_TO_TIER.get((difficulty_word or "").strip().lower())
    if not tier:
        return None
    data = SEQUENCE_DIFFICULTY_TIERS[tier]
    return (
        f"POZIOM TRUDNOSCI {tier}/5 (skala dla ciagow arytmetycznych/geometrycznych): {data['kryterium']} "
        f"Przyklady zadan na tym poziomie: {data['przyklad']}. "
        f"Wygeneruj zadanie o TAKIM WLASNIE poziomie trudnosci - nie latwiejsze, nie trudniejsze."
    )


def is_sequence_topic(topic: str) -> bool:
    """Proste wykrycie, czy temat dotyczy ciagow arytmetycznych/geometrycznych -
    uzywane do "gated injection" skali 1-5 (dziala TYLKO dla tego tematu)."""
    t = (topic or "").lower()
    has_ciag = "ciąg" in t or "ciag" in t
    return has_ciag and ("arytmetyczn" in t or "geometryczn" in t)


# ETAP 7: analogiczna "gated injection" skala trudnosci dla trygonometrii -
# patrz QUADRATIC_DIFFICULTY_TIERS/SEQUENCE_DIFFICULTY_TIERS wyzej po
# uzasadnienie wzorca. Skala 1-5 (jak ciagi) - tyle pasm rozpoznaje dzis
# classify_trig_difficulty w math_verify.py. Bezposredni powod Etapu 7:
# "sin(30°)" bylo generowane jako "medium" mimo ze to wartosc z pamieci -
# pasmo "1" jednoznacznie to lapie. "4-5" celowo obejmuje 2 rozne wzorce
# (rownanie z/bez parametru ORAZ dowod tozsamosci), zeby "hard" nie bylo
# jednym powtarzalnym typem zadania (ta sama zasada co przy ciagach).
TRIG_DIFFICULTY_TIERS = {
    "1": {
        "kryterium": (
            "Wartosc funkcji trygonometrycznej dla kata specjalnego "
            "(0°,30°,45°,60°,90°,...) - wartosc z pamieci, BEZ obliczen."
        ),
        "przyklad": "Ile wynosi sin(30°)?",
    },
    "2-3": {
        "kryterium": (
            "Trojkat prostokatny (SOH-CAH-TOA) - jedna niewiadoma z danych "
            "pozostalych bokow/katow, ALBO prosta tozsamosc (Pitagorasa) w "
            "bezposrednim zastosowaniu, ALBO zamiana stopnie<->radiany, "
            "ALBO twierdzenie sinusow/cosinusow w trojkacie dowolnym."
        ),
        "przyklad": (
            "W trójkącie prostokątnym przeciwprostokątna ma długość 10, a "
            "jeden z kątów ostrych 35°. Oblicz długości przyprostokątnych."
        ),
    },
    "4-5": {
        "kryterium": (
            "Rownanie trygonometryczne wymagajace przeksztalcenia (np. "
            "sprowadzenia do rownania kwadratowego wzgledem sin/cos), Z "
            "PARAMETREM albo BEZ, ALBO dowod tozsamosci trygonometrycznej. "
            "Uzyj ROZNORODNYCH wzorcow z tej listy, nie zawsze tego samego."
        ),
        "przyklad": (
            "Rozne przyklady na tym poziomie: 'Rozwiąż równanie "
            "2sin²(x)-3cos(x)=0 dla x∈[0,2π), sprowadzając do równania "
            "kwadratowego względem cos(x).' LUB 'Dla jakich wartości "
            "parametru a równanie sin(x)=a ma rozwiązanie w [0,2π)?' LUB "
            "'Udowodnij tożsamość (1-cos(2x))/sin(2x) = tan(x).'"
        ),
    },
}

_TRIG_DIFFICULTY_WORD_TO_TIER = {
    "easy": "1", "latwy": "1", "łatwy": "1", "latwa": "1", "łatwa": "1",
    "medium": "2-3", "sredni": "2-3", "średni": "2-3", "srednia": "2-3", "średnia": "2-3",
    "hard": "4-5", "trudny": "4-5", "trudna": "4-5",
}


def get_trig_difficulty_anchor(difficulty_word: str):
    """Zwraca tekst kryterium+przykladow (skala 1-5) dla podanego slowa
    trudnosci, analogicznie do get_sequence_difficulty_anchor. None jesli
    slowo nierozpoznane (wtedy caller ma spasc na stare, generyczne
    zachowanie)."""
    tier = _TRIG_DIFFICULTY_WORD_TO_TIER.get((difficulty_word or "").strip().lower())
    if not tier:
        return None
    data = TRIG_DIFFICULTY_TIERS[tier]
    return (
        f"POZIOM TRUDNOSCI {tier}/5 (skala dla trygonometrii): {data['kryterium']} "
        f"Przyklady zadan na tym poziomie: {data['przyklad']}. "
        f"Wygeneruj zadanie o TAKIM WLASNIE poziomie trudnosci - nie latwiejsze, nie trudniejsze."
    )


def is_trigonometry_topic(topic: str) -> bool:
    """Proste wykrycie, czy temat dotyczy trygonometrii - uzywane do
    "gated injection" skali 1-5 (dziala TYLKO dla tego tematu)."""
    t = (topic or "").lower()
    return "trygonometri" in t


# ETAP 8: analogiczna "gated injection" skala trudnosci dla funkcji
# (liniowej, kwadratowej JAKO FUNKCJI - nie rownania, wykladniczej
# podstawowej) - patrz TRIG_DIFFICULTY_TIERS wyzej po uzasadnienie
# wzorca. Skala 1-5, 3 pasma - jak ciagi/trygonometria.
LINEAR_FUNCTION_DIFFICULTY_TIERS = {
    "1": {
        "kryterium": (
            "Podstawienie konkretnej liczby do f(x)=ax+b (a,b dane "
            "wprost) - JEDNO dzialanie."
        ),
        "przyklad": "Dla funkcji f(x)=2x+3, oblicz f(4).",
    },
    "2-3": {
        "kryterium": (
            "Wyznaczenie rownania prostej przez 2 punkty, ALBO prostej "
            "rownoleglej/prostopadlej przez dany punkt, ALBO "
            "monotonicznosc/miejsce zerowe z danego wzoru."
        ),
        "przyklad": "Wyznacz równanie prostej prostopadłej do y=2x-3, przechodzącej przez punkt (4,1).",
    },
    "4-5": {
        "kryterium": (
            "Parametr (dla jakich m funkcja jest rosnaca/malejaca, "
            "przechodzi przez dany punkt), ALBO uklad dwoch prostych z "
            "warunkiem. Uzyj ROZNORODNYCH wzorcow, nie zawsze tego samego."
        ),
        "przyklad": "Dla jakich wartości m funkcja f(x)=(m-2)x+3 jest malejąca?",
    },
}
_LINEAR_FUNCTION_DIFFICULTY_WORD_TO_TIER = {
    "easy": "1", "latwy": "1", "łatwy": "1", "latwa": "1", "łatwa": "1",
    "medium": "2-3", "sredni": "2-3", "średni": "2-3", "srednia": "2-3", "średnia": "2-3",
    "hard": "4-5", "trudny": "4-5", "trudna": "4-5",
}


def get_linear_function_difficulty_anchor(difficulty_word: str):
    """Zwraca tekst kryterium+przykladow (skala 1-5) dla funkcji
    liniowej, analogicznie do get_trig_difficulty_anchor."""
    tier = _LINEAR_FUNCTION_DIFFICULTY_WORD_TO_TIER.get((difficulty_word or "").strip().lower())
    if not tier:
        return None
    data = LINEAR_FUNCTION_DIFFICULTY_TIERS[tier]
    return (
        f"POZIOM TRUDNOSCI {tier}/5 (skala dla funkcji liniowej): {data['kryterium']} "
        f"Przyklad zadania na tym poziomie: '{data['przyklad']}'. "
        f"Wygeneruj zadanie o TAKIM WLASNIE poziomie trudnosci - nie latwiejsze, nie trudniejsze."
    )


def is_linear_function_topic(topic: str) -> bool:
    """Proste wykrycie, czy temat dotyczy funkcji liniowej."""
    t = (topic or "").lower()
    return "funkcj" in t and "liniow" in t


QUADRATIC_FUNCTION_DIFFICULTY_TIERS = {
    "1": {
        "kryterium": (
            "Odczyt wierzcholka WPROST z postaci kanonicznej "
            "f(x)=a(x-p)^2+q (p,q dane, bez obliczen)."
        ),
        "przyklad": "f(x)=2(x-3)²+5. Podaj współrzędne wierzchołka.",
    },
    "2-3": {
        "kryterium": (
            "Sprowadzenie z postaci ogolnej do kanonicznej (wyznaczenie "
            "wierzcholka), ALBO monotonicznosc/zbior wartosci z postaci "
            "ogolnej."
        ),
        "przyklad": "f(x)=x²-4x+7. Wyznacz wierzchołek i zbiór wartości.",
    },
    "4-5": {
        "kryterium": (
            "Parametr wplywajacy na wierzcholek/zakres, ALBO zadanie "
            "optymalizacyjne wykorzystujace wierzcholek. Uzyj "
            "ROZNORODNYCH wzorcow, nie zawsze tego samego."
        ),
        "przyklad": "Dla jakich m wierzchołek paraboli f(x)=x²-2mx+1 leży powyżej osi OX?",
    },
}
_QUADRATIC_FUNCTION_DIFFICULTY_WORD_TO_TIER = {
    "easy": "1", "latwy": "1", "łatwy": "1", "latwa": "1", "łatwa": "1",
    "medium": "2-3", "sredni": "2-3", "średni": "2-3", "srednia": "2-3", "średnia": "2-3",
    "hard": "4-5", "trudny": "4-5", "trudna": "4-5",
}


def get_quadratic_function_difficulty_anchor(difficulty_word: str):
    """Zwraca tekst kryterium+przykladow dla funkcji kwadratowej JAKO
    FUNKCJI (wierzcholek/monotonicznosc/zbior wartosci - NIE rownania,
    patrz get_quadratic_difficulty_anchor dla tamtej skali)."""
    tier = _QUADRATIC_FUNCTION_DIFFICULTY_WORD_TO_TIER.get((difficulty_word or "").strip().lower())
    if not tier:
        return None
    data = QUADRATIC_FUNCTION_DIFFICULTY_TIERS[tier]
    return (
        f"POZIOM TRUDNOSCI {tier}/5 (skala dla funkcji kwadratowej - wlasciwosci, nie rownania): {data['kryterium']} "
        f"Przyklad zadania na tym poziomie: '{data['przyklad']}'. "
        f"Wygeneruj zadanie o TAKIM WLASNIE poziomie trudnosci - nie latwiejsze, nie trudniejsze."
    )


def is_quadratic_function_topic(topic: str) -> bool:
    """Proste wykrycie, czy temat dotyczy funkcji kwadratowej JAKO
    FUNKCJI - odrebne od is_quadratic_equation_topic (rownania).
    Priorytet miedzy nimi ustala KOLEJNOSC elif w openai_exam.py/
    exam_pdf_generator.py (rownania sprawdzane PIERWSZE - zachowanie
    dla tematow typu 'rownania kwadratowe' bez zmian)."""
    t = (topic or "").lower()
    return "funkcj" in t and "kwadratow" in t


EXPONENTIAL_FUNCTION_DIFFICULTY_TIERS = {
    "1": {
        "kryterium": (
            "Podstawienie calkowitej liczby do f(x)=a^x (a dane wprost) "
            "- JEDNO dzialanie, ALBO rozpoznanie wzrost/spadek z podstawy a."
        ),
        "przyklad": "f(x)=2ˣ. Oblicz f(3).",
    },
    "2-3": {
        "kryterium": (
            "Rownanie wykladnicze przy TEJ SAMEJ podstawie (porownanie "
            "wykladnikow), ALBO przesuniecie wykresu funkcji wykladniczej."
        ),
        "przyklad": "Rozwiąż równanie 2^(x+1) = 8.",
    },
    "4-5": {
        "kryterium": (
            "Rownanie wymagajace podstawienia (t=a^x) sprowadzajace do "
            "kwadratowego, ALBO nierownosc wykladnicza, ALBO parametr. "
            "Uzyj ROZNORODNYCH wzorcow, nie zawsze tego samego."
        ),
        "przyklad": "Rozwiąż nierówność 4ˣ-3·2ˣ-4≤0, podstawiając t=2ˣ.",
    },
}
_EXPONENTIAL_FUNCTION_DIFFICULTY_WORD_TO_TIER = {
    "easy": "1", "latwy": "1", "łatwy": "1", "latwa": "1", "łatwa": "1",
    "medium": "2-3", "sredni": "2-3", "średni": "2-3", "srednia": "2-3", "średnia": "2-3",
    "hard": "4-5", "trudny": "4-5", "trudna": "4-5",
}


def get_exponential_function_difficulty_anchor(difficulty_word: str):
    """Zwraca tekst kryterium+przykladow dla funkcji wykladniczej,
    analogicznie do get_linear_function_difficulty_anchor."""
    tier = _EXPONENTIAL_FUNCTION_DIFFICULTY_WORD_TO_TIER.get((difficulty_word or "").strip().lower())
    if not tier:
        return None
    data = EXPONENTIAL_FUNCTION_DIFFICULTY_TIERS[tier]
    return (
        f"POZIOM TRUDNOSCI {tier}/5 (skala dla funkcji wykladniczej): {data['kryterium']} "
        f"Przyklad zadania na tym poziomie: '{data['przyklad']}'. "
        f"Wygeneruj zadanie o TAKIM WLASNIE poziomie trudnosci - nie latwiejsze, nie trudniejsze."
    )


def is_exponential_function_topic(topic: str) -> bool:
    """Proste wykrycie, czy temat dotyczy funkcji wykladniczej."""
    t = (topic or "").lower()
    return "wykładnicz" in t or "wykladnicz" in t


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
            base = f"{base} Zakres materiału z przedmiotu ({subject}): {scope.rstrip('.')}."

    # Globalna klauzula trudnosci - dodawana zawsze, niezaleznie od
    # przedmiotu. Powod: uzytkownicy zglaszali, ze generowane
    # zadania byly za latwe wzgledem realnego poziomu danej klasy
    # (np. "rownania kwadratowe" na poziomie przedszkolaka zamiast
    # liceum). Dopisujemy to raz tutaj, bo describe_level() jest
    # jedynym wspolnym punktem wstrzykiwania opisu poziomu do Quiz,
    # Sprawdzian i Notatki - dzieki temu nie trzeba tego powtarzac w
    # kazdym miejscu generowania osobno.
    return (
        f"{base} WAŻNE: To NIE może być zbyt łatwe. Zadania muszą "
        f"odpowiadać PRAWDZIWEMU poziomowi trudności podręcznika/egzaminu "
        f"dla tej klasy, a NIE uproszczonej wersji dla młodszych uczniów. "
        f"Jeśli wahasz się między łatwiejszym a trudniejszym wariantem "
        f"zadania - wybierz trudniejszy."
    )


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
