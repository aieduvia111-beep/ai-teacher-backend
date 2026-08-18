# Analiza i plan: zamiana ogólnych poziomów na konkretną klasę

Data analizy: 2026-08-18
Status: **ANALIZA / PLAN — bez implementacji**

Kontekst: dziś system operuje czterema ogólnymi kategoriami poziomu:
`podstawowka` / `liceum` (czasem `technikum`) / `matura` / `studia`. Zmiana
ma zastąpić je konkretną klasą, np. „Klasa 5 podstawówki”, „Klasa 2 liceum”.

---

## Streszczenie

To NIE jest zmiana punktowa w ankiecie quizu. Kategorie poziomu są
**zduplikowane niezależnie w co najmniej 8 plikach frontendu i 9 plikach
backendu**, każdy z własnym, ręcznie pisanym słownikiem opisów poziomu.
Nie ma jednego wspólnego komponentu UI ani jednego wspólnego miejsca w
backendzie, które trzeba by zmienić — trzeba przejść **feature po
feature**. Baza danych nie wymaga migracji strukturalnej (kolumna
`level` to `String(50)`, zmieści dowolny tekst), ale brakuje jednego
„źródła prawdy” poziomu ucznia (nie ma pola w `User`, każda funkcja
trzyma poziom osobno, w `localStorage`).

Realistyczna skala: **~17 plików do zmiany, rozsądnie robić etapami**,
zaczynając od Quizu (najprostszy backend, najwyższy ruch) jako pilotażu.
Największym pojedynczym kosztem nie jest liczba plików, tylko
przeprojektowanie treści promptów AI z 4 „koszyków” na ~10-12 konkretnych
klas bez popadania w ręczne tabele kombinacji (patrz sekcja 4 i 7).

---

## 1. Inwentaryzacja — gdzie występują stare kategorie poziomu

### 1.1 Frontend (`static/*.html`)

| Plik | Zmienna / mechanizm | Selektor poziomu w UI | Wysyła do backendu |
|---|---|---|---|
| `quiz_app.html` | `VALS.level` (domyślnie `'liceum'`) | 4 przyciski: Podstawówka / Liceum / Technikum / Studia (linia ~702) | `POST /api/v1/quiz/generate-topic` — pole `level` |
| `exam_generator.html` | `vals.klasa` (domyślnie `'liceum'`) | 4 przyciski: Podstawówka / Liceum-Tech. / Matura / Studia (linia ~667) | `POST /api/v1/exam/generate` — pole `klasa` |
| `notes_generator.html` | `level` (domyślnie `'liceum'`) | 4 przyciski: identyczne jak w exam_generator (linia ~713) | `POST /api/v1/notes/generate` — pole `klasa` |
| `lesson_planner.html` | `<select>` | `<option>`: podstawowka / liceum (selected) / matura / studia (linia ~738) | plan nauki — pole `level` |
| `whiteboard.html` | `<select id="wbLevel">` | tylko 3 opcje: liceum (selected) / matura / studia — **brak podstawówki** (linia ~646) | `/api/v1/whiteboard/explain` — pole `level` |
| `voice_conversation.html` | `selLevel` (domyślnie `'liceum'`) | przyciski z `dataset.val` (linia ~1073, ~1849) | WS/REST rozmowa głosowa — pole `level` |
| `chat.html` | inline w generowanych przyciskach | 3 przyciski przy generowaniu fiszek z czatu: podstawowka/liceum/studia (linia ~1334-1391) | przekazywane do `flashcards.html` przez URL/localStorage |
| `flashcards.html` | `level` z query param lub `localStorage['fc_level']` | brak własnego selektora — dziedziczy z chat.html | używane w treści promptu fiszek |
| `brain.html` | `klasa: 'liceum'` **zahardkodowane** | brak — generowanie automatycznego sprawdzianu z błędów, poziom nie jest wybierany przez ucznia (linia ~707) | `/api/v1/exam/generate` |
| `eduvia-final.html` | tylko tekst marketingowy (landing page) | brak funkcjonalnego selektora, tylko treści typu „Matura”, „Liceum” w opiniach | brak wysyłki |

**Ważne odkrycie:** nie ma wspólnego komponentu selektora poziomu ani
wspólnego pliku JS z listą poziomów. Każda strona ma własny,
skopiowany HTML przycisków i własną nazwę zmiennej (`level` w jednych
miejscach, `klasa` w innych) — czysto kosmetyczna niespójność, ale
oznacza, że nowy picker trzeba wpiąć osobno w każdą z ~8 stron.

**Brak jednego „profilu ucznia”:** poziom nie jest zapisywany przy
koncie — jest trzymany lokalnie per-funkcja i przekazywany między
funkcjami tylko doraźnie przez `localStorage` (`auto_notes_level`,
`auto_exam_level`, `fc_level` — ustawiane w `quiz_app.html:1285,1291`
i odczytywane w `notes_generator.html:1265`, `exam_generator.html:1244`,
`flashcards.html:273`). Uczeń dziś może mieć w quizie „Liceum”, a w
notatkach nadal domyślne „Liceum” bez związku z kontem.

### 1.2 Backend (`app/**/*.py`)

| Plik / funkcja | Mechanizm poziomu | Sposób wpływu na prompt |
|---|---|---|
| `app/api/quiz_api.py` → `_generate_topic_with_instrukcje()` | brak słownika — `level` wklejany 1:1 do promptu (`f"Poziom: {level}"`, linia 71) | **trywialne** — działa z dowolnym stringiem już dziś |
| `app/openai_exam.py` → `generate_quiz_from_topic()` | `combo_map` — słownik kluczowany krotką `(level, difficulty)` z ręcznie napisanym opisem klas (linie 578-591); osobny `level_map` (571-574) i trzeci opis w system prompcie (660-663) | funkcja używana dziś tylko przez stary endpoint w `app/main.py:363` (legacy) — do zweryfikowania czy w ogóle jest osiągalna z aktualnego frontendu |
| `app/exam_pdf_generator.py` | opisy `[podstawowka]/[liceum]/[matura]/[studia]` wpisane inline w f-string promptu (linie 124-134), osobno dla trudności w ramach poziomu | **największy koszt treściowy** — to jest właściwy generator sprawdzianów używany przez `exam_api.py` i `brain.html` |
| `app/api/exam_api.py` | przekazuje `klasa` 1:1 do `exam_pdf_generator` | bez zmian logiki, tylko routing parametru |
| `app/notes_pdf_generator.py` | **`SIZE_CONFIG`** — słownik kluczowany liczbą sekcji notatki (2-5), a NIE parametrem `klasa`! Ton/styl tekstu („POZIOM: DZIECKO”, „POZIOM: LICEUM”, „POZIOM: STUDIA”, „POZIOM: EKSPERT”) zależy dziś od długości notatki, a rzeczywisty wybrany poziom trafia tylko jako placeholder `{klasa}` w treści i na okładce PDF (linie 1053-1057, 935) | **istniejąca niespójność do naprawienia przy okazji** — trzeba rozdzielić „długość notatki” od „poziom ucznia”, inaczej zmiana kategorii poziomu nic nie da w praktyce (styl i tak sterowany liczbą stron) |
| `app/api/notes_api.py` | przekazuje `klasa` 1:1 do generatora | routing only |
| `app/api/lessons.py` | częściowy inline opis (tylko liceum/matura, linia 45-46), reszta przekazywana wprost do promptu planu nauki | umiarkowane |
| `app/services/lesson_planner.py` | własny `level_map` (linie 49-53) | duplikat wzorca z innych plików |
| `app/api/voice.py` | własny `level_map` dla tonu rozmowy głosowej (linie 165-169) + osobny prosty pass-through (`ctx.append(f"Poziom: {level}")`, linia 326) | dwa niezależne miejsca w jednym pliku |
| `app/api/whiteboard.py` | własny `LEVEL_DESC` (linie 23-27), **bez klucza `podstawowka`** — spójne z brakiem tej opcji w UI | duplikat wzorca |
| `app/api/realtime.py` | własny `level_map` (linia 64) | duplikat wzorca |
| `app/api/youtube_notes.py` | pass-through `klasa`, prawdopodobnie reużywa `notes_pdf_generator` | niska złożoność |
| `app/api/multiplayer.py` | import z nieistniejącego modułu `app.services.openai_quiz` (linia 89) — **martwy/zepsuty kod**, poziom zahardkodowany na `'liceum'` (linia 92) | poza głównym zakresem tej zmiany, ale warto zgłosić osobno jako dług techniczny |

**Kluczowe odkrycie:** wzorzec „słownik poziom → opis dla AI” jest
**skopiowany niezależnie co najmniej 5 razy** (`openai_exam.py` ×2,
`lesson_planner.py`, `voice.py`, `whiteboard.py`, `realtime.py`), za
każdym razem z lekko innym tekstem. To jest największe ryzyko tej
zmiany: bez centralizacji, przejście na klasy oznacza przepisanie 5+
osobnych, niespójnych słowników zamiast jednego.

---

## 2. Zmiana promptów AI — feature po feature

Zasada ogólna, którą rekomendujemy (patrz też sekcja 7): **nie** budować
sztywnej tabeli kombinacji `klasa × trudność × przedmiot` (jak dziś robi
`combo_map` w `openai_exam.py`) — przy 10-12 klasach i 3 poziomach
trudności to 30-36 ręcznie pisanych opisów *na każdą funkcję*. GPT-4o
zna polską podstawę programową wystarczająco dobrze, by dostać krótką,
jednoznaczną instrukcję w stylu:

> „Poziom ucznia: klasa 5 szkoły podstawowej. Dostosuj trudność,
> słownictwo i zakres materiału ściśle do tej klasy w polskiej podstawie
> programowej. Nie wykraczaj poza materiał tej klasy.”

zamiast dzisiejszych ręcznie wypisanych list tematów per koszyk.

| Funkcja | Dziś (przykład) | Po zmianie |
|---|---|---|
| Quiz (`quiz_api.py`) | `f"Poziom: {level}"` gdzie `level='liceum'` | `f"Poziom: {level}"` gdzie `level='Klasa 2 liceum'` — **zero zmian w kodzie**, wystarczy że frontend wyśle pełną nazwę klasy |
| Sprawdziany (`exam_pdf_generator.py`) | blok `[podstawowka]/[liceum]/[matura]/[studia]` z ręcznie wypisanym zakresem materiału per koszyk × trudność | zastąpić jedną instrukcją opartą o nazwę klasy + trudność (bez oddzielnej tabeli na każdą klasę); ewentualnie zostawić 2-3 „kotwice programowe” (np. „klasa 8 = przygotowanie do egzaminu ósmoklasisty”, „ostatnia klasa liceum = poziom maturalny”) jako podpowiedzi kontekstowe, nie pełne tabele |
| Notatki (`notes_pdf_generator.py`) | styl zależny od liczby stron (`SIZE_CONFIG`), `{klasa}` tylko jako etykieta | **najpierw naprawić rozdzielenie**: długość notatki (liczba sekcji) ma sterować tylko długością, a osobny parametr `klasa` ma sterować stylem/słownictwem; dopiero potem podłączyć konkretną klasę |
| Plan nauki (`lesson_planner.py`, `lessons.py`) | `level_map` z ogólnym opisem grupy wiekowej | jedna instrukcja z nazwą klasy, jak wyżej |
| Voice AI (`voice.py`) | `level_map` z instrukcją tonu wypowiedzi („mów jak do dziecka 12 lat” dla `podstawowka`) | instrukcja tonu oparta o konkretną klasę (np. „klasa 1 podstawówki” vs „klasa 8” to bardzo różny ton, dziś oba wpadają w jeden koszyk) — to jedna z funkcji, która **najbardziej zyska** na granularności |
| Tablica AI (`whiteboard.py`) | `LEVEL_DESC` bez opcji podstawówki w ogóle | dodać pełen zakres klas (dziś whiteboard arbitralnie nie obsługuje podstawówki — do potwierdzenia czy to celowe czy przeoczenie) |
| Rozmowa czasu rzeczywistego (`realtime.py`) | kolejna kopia `level_map` | scentralizować razem z resztą |
| Fiszki (`chat.html` → `flashcards.html`) | 3 twarde przyciski (podstawowka/liceum/studia) | rozszerzyć do pełnej listy klas lub uprościć do wyboru etapu (patrz sekcja 7) |

**Rekomendacja architektoniczna:** stworzyć jeden wspólny moduł
backendowy, np. `app/services/education_levels.py`, z:
- kanoniczną listą klas (jedno źródło prawdy, patrz sekcja 7),
- jedną funkcją `describe_level(level: str) -> str` zwracającą tekst do
  promptu,

i podmienić w nim wszystkie 5+ zduplikowanych słowników. To jedyny
sposób, by zmiana nie musiała być zrobiona 5 razy z ryzykiem rozjazdu.

---

## 3. Baza danych (`app/models.py`)

- `Lesson.level = Column(String(50), nullable=False)` — **wystarczy**,
  string typu `"Klasa 5 podstawówki"` mieści się bez problemu w 50
  znakach. **Migracja strukturalna nie jest potrzebna.**
- Pozostałe funkcje (quiz, sprawdziany, notatki, tablica, voice) **w
  ogóle nie zapisują poziomu do bazy** — to parametr request/response,
  ulotny. Zmiana nie dotyka tam żadnych tabel.
- `User` **nie ma pola poziomu** (`app/models.py:80-108` — same pola
  premium/Stripe/notyfikacje, brak `education_level`). To osobna,
  opcjonalna decyzja produktowa (patrz sekcja 7, pkt „Profil ucznia”):
  czy przy okazji tej zmiany dodać `User.default_level` jako wygodę
  (”ustaw raz, używaj wszędzie”), czy zostawić model status quo
  (poziom wybierany za każdym razem lokalnie per funkcja). Jeśli tak —
  to jest jedyne miejsce wymagające prawdziwej migracji Alembic/SQL.

---

## 4. Skala zmiany i harmonogram etapowy

### Zestawienie

| Obszar | Liczba plików | Złożoność |
|---|---|---|
| Frontend — selektory poziomu | 8 (`quiz_app`, `exam_generator`, `notes_generator`, `lesson_planner`, `whiteboard`, `voice_conversation`, `chat`, `flashcards`) | średnia — nowy UI (patrz pkt 6) + wpięcie w 8 miejsc |
| Backend — logika promptów | 9 (`quiz_api`, `openai_exam`, `exam_pdf_generator`, `exam_api`, `notes_pdf_generator`, `notes_api`, `lessons`, `lesson_planner` (service), `voice`, `whiteboard`, `realtime`, `youtube_notes`) *(11 faktycznie, patrz sekcja 1.2)* | wysoka — 5+ zduplikowanych słowników do scentralizowania, `exam_pdf_generator` i `notes_pdf_generator` wymagają przepisania treści promptu |
| Baza danych | 0 wymagane / 1 opcjonalne (`User.default_level`) | niska (chyba że dojdzie profil ucznia) |
| **Razem** | **~17 plików** | — |

### Szacunek czasu (dla osoby znającej ten kod)

- Zaprojektowanie kanonicznej listy klas + jeden wspólny komponent UI
  (picker) + jeden wspólny moduł backendowy `education_levels.py`:
  **0.5–1 dzień**
- Etap 1 — pilotaż na Quizie (najprostszy backend, najwyższy ruch —
  dobry kandydat, by sprawdzić UX nowego pickera na żywym ruchu przed
  rozszerzeniem na resztę): **0.5–1 dzień**
- Etap 2 — Sprawdziany + Notatki (największy koszt treściowy promptów,
  plus naprawa rozjazdu `SIZE_CONFIG` vs `klasa` w notatkach): **1.5–2 dni**
- Etap 3 — Plan nauki, Voice AI, Tablica AI, Realtime: **1–1.5 dnia**
  (głównie podmiana na wspólny moduł, mniej nowej treści)
- Etap 4 — Fiszki/chat (mniejszy, ale osobny wzorzec przycisków) +
  porządki (martwy import w `multiplayer.py`, `brain.html` zahardkodowane
  `liceum`): **0.5 dnia**
- Testy manualne każdego etapu na żywym API (jakość promptów AI trzeba
  ocenić jakościowo, nie tylko testem jednostkowym): rozłożone w etapach
  powyżej, ale realnie doliczyć **~1 dzień** review treści generowanych
  przez AI dla kilku przykładowych klas skrajnych (kl. 1 SP, kl. 8 SP,
  matura, studia).

**Łącznie: ~5–7 dni roboczych**, jeśli robione etapami z realną walidacją
jakości promptów (a nie tylko zmianą kodu). Da się to bezpiecznie
wdrażać etapami — każdy etap jest niezależny funkcjonalnie (quiz nie
zależy od tablicy AI), więc nie trzeba jednego wielkiego PR-a.

---

## 5. Wibracje (haptic feedback) w ankiecie

**Dobra wiadomość: infrastruktura już istnieje.** W `static/animations.js:41-57`
jest gotowa funkcja `window._haptic(type)`:

```js
window._haptic=function(type){
  if(window.Capacitor&&window.Capacitor.Plugins&&window.Capacitor.Plugins.Haptics){
    var H=window.Capacitor.Plugins.Haptics;
    if(type==='ok')H.impact({style:'light'});
    else if(type==='err')H.notification({type:'error'});
    else H.impact({style:'medium'});
    return;
  }
  if(navigator.vibrate){
    if(type==='ok')navigator.vibrate(30);
    else if(type==='err')navigator.vibrate([50,30,50]);
    else navigator.vibrate(50);
  }
};
```

- `@capacitor/haptics ^8.0.2` jest już zależnością w `package.json`.
- `quiz_app.html` już ją wywołuje, ale **tylko przy odpowiedzi na
  pytanie w quizie** (`window._haptic('ok'/'err')`, linie 1218-1220),
  **nie na ekranie ustawień/ankiety** (funkcja `sel(this,'level')`,
  `quiz_app.html:1050`, nic dziś nie wibruje).

### Co trzeba zrobić
Dodać `window._haptic('ok')` (lub nowy typ np. `'tap'` →
`navigator.vibrate(50)` / `H.impact({style:'light'})`, zgodnie z prośbą
o `50ms`) wewnątrz funkcji `sel()` w `quiz_app.html` oraz analogicznych
funkcji (`setLevel()` w `notes_generator.html`/`exam_generator.html`,
obsługi przycisków w `voice_conversation.html`, `<select onchange>` w
`lesson_planner.html`/`whiteboard.html`). To **bardzo mała zmiana** —
jedna linijka na funkcję, bo mechanizm już istnieje i jest przetestowany
w produkcji na innym ekranie tej samej apki.

### Weryfikacja per platforma (zbadane, nie zakładane)

| Platforma | Ścieżka wykonania | Zadziała? |
|---|---|---|
| Android — natywna apka (Capacitor, `android/`) | `Capacitor.Plugins.Haptics` (natywny plugin, prawdziwy silnik wibracji) | **Tak** |
| Android — TWA (`eduvia-twa`) / Chrome | brak `window.Capacitor` → fallback na `navigator.vibrate()`, wspierane przez Chrome/Chromium | **Tak** (stąd komentarz w kodzie „działa w TWA przez Web Vibration API”) |
| iOS Safari (przeglądarka, nie apka) | brak `window.Capacitor`, `navigator.vibrate` **nie istnieje w WebKit/Safari** — WebKit świadomie nie implementuje Vibration API | **Nie** — cicho nic się nie dzieje (brak błędu, po prostu `if(navigator.vibrate)` jest fałszywe) |
| iOS — natywna apka (`eduvia-ios`) | Sprawdzone: to **czysty natywny wrapper Swift + WKWebView** (`WebView.swift`, `ViewController.swift`), **BEZ Capacitor** — `window.Capacitor` tam nie istnieje, więc apka iOS dziedziczy dokładnie te same ograniczenia co Safari | **Nie**, dopóki nie dodamy natywnego mostu |

**Wniosek:** żądanie „`navigator.vibrate(50)` dla Androida, iOS Safari
nie wspiera” — potwierdzone w 100%, i dotyczy też natywnej apki iOS (nie
tylko przeglądarki), bo `eduvia-ios` nie ma Capacitora ani żadnego mostu
haptycznego.

### Opcjonalny dodatek dla iOS (poza minimalnym zakresem)
`ViewController.swift:259` ma już wzorzec `WKScriptMessageHandler`
obsługujący komunikaty z JS (`message.name == "print"`,
`"signInWithApple"`). Można by tym samym wzorcem dodać
`message.name == "vibrate"` wywołujący
`UIImpactFeedbackGenerator`/`UINotificationFeedbackGenerator`, a w
`_haptic()` dodać trzecią gałąź (`window.webkit?.messageHandlers?.vibrate`)
przed fallbackiem na `navigator.vibrate`. To realna, ale osobna praca
(Swift + Xcode build) — do decyzji, czy wchodzi w zakres tej zmiany, czy
zostaje jako oddzielne zadanie techniczne.

---

## 6. Design ankiety — motyw kosmiczny

**Motyw kosmiczny już istnieje w aplikacji** — nie trzeba go wymyślać od
zera, tylko rozszerzyć na ekran ankiety/ustawień:

- Paleta już zdefiniowana jako zmienne CSS w `quiz_app.html:20`:
  `--accent:#7c6aff` (fiolet), `--accent2:#a78bfa` (jaśniejszy fiolet),
  plus `--green` do akcentów sukcesu.
- Gotowa klasa `.bg-star` + animacja `@keyframes twinkle`
  (`quiz_app.html:108-109`) — małe białe kropki, które migają
  (`opacity .15→.5`) w losowych odstępach czasu.
- Dziś gwiazdki są użyte **tylko w nagłówku strony** — kilka
  ręcznie wstawionych `<div class="bg-star" style="top:..;right:..">`
  (`quiz_app.html:680-687`), nie na całej stronie.

### Propozycja rozszerzenia na ankietę poziomu/klasy
- **Tło całej karty ankiety**: rozciągnąć `.bg-star` na cały kontener
  `#pageSetup` (dziś jest tylko w pasku nagłówka) — 15-20 kropek o
  różnych rozmiarach (2-4px) i losowych `animation-delay`, żeby migały
  asynchronicznie. Można to zrobić w JS przy renderze strony (pętla
  generująca `div`-y) zamiast ręcznie wypisywać każdą gwiazdkę w HTML —
  łatwiej wielokrotnie użyć na kilku stronach.
- **Karty poziomu jako „planety/orbity”**: zamiast płaskich
  przycisków, każda opcja klasy jako karta z delikatną poświatą
  (`box-shadow: 0 0 20px rgba(124,106,255,.25)`) w spoczynku, która
  rozjaśnia się przy `:hover`/`.active` — spójne z istniejącym stylem
  `.sel-btn.active{background:rgba(124,106,255,.12);border-color:rgba(124,106,255,.4)}`
  (`quiz_app.html:136`).
- **Dwuetapowy wybór (Etap → Klasa)** zamiast 10-12 przycisków na raz:
  najpierw duże karty etapu („Podstawówka” / „Liceum / Technikum” /
  „Studia”) z ikoną i gradientowym obramowaniem, po kliknięciu — rozwija
  się (`slide-down`, spójnie z istniejącymi `transitions.js`) rząd
  mniejszych „kapsuł” z numerami klas (1-8 lub 1-4), jak stacja
  przystankowa na trasie orbitalnej. To ogranicza liczbę widocznych na
  raz elementów i pasuje do motywu „podróży przez etapy nauki”.
- **Mikroanimacja przy wyborze**: krótkie „rozbłyśnięcie” wybranej
  kapsuły (scale 1→1.08→1, 200ms) połączone z hapticiem z sekcji 5 —
  spójne odczucie dotyku i wizualnego potwierdzenia jednocześnie.
- **Typografia i kolor tekstu** bez zmian względem reszty apki —
  używać istniejących zmiennych `--h` (nagłówki) i gradientu tekstu
  `linear-gradient(110deg,#fff,var(--accent2),var(--green))`
  (`quiz_app.html:112`) dla tytułu sekcji „Wybierz swoją klasę”.

To rozszerzenie istniejącego systemu wizualnego, nie nowy motyw —
niskie ryzyko niespójności z resztą aplikacji.

---

## 7. Otwarte pytania decyzyjne (do ustalenia przed implementacją)

1. **Dokładna lista klas** — proponowana kanoniczna lista (do
   zatwierdzenia):
   - Szkoła podstawowa: klasa 4–8 (klasy 1-3 pominięte — obecny
     `combo_map` w `openai_exam.py` też zaczyna dopiero od kl. 4-5;
     czy Eduvia w ogóle celuje w młodszych uczniów?)
   - Liceum/Technikum: klasa 1–4 (technikum 5-letnie: potencjalnie
     klasa 5 osobno albo zmapowana na „ostatnia klasa”)
   - Studia: **bez podziału na lata** (rekomendacja — programy studiów
     są zbyt zróżnicowane międzykierunkowo, żeby granularność klasa-po-klasie
     miała sens tak jak w K-12)
2. **Co z „Maturą”?** — dziś to osobna, czwarta kategoria, ale
   matura nie jest klasą, tylko egzaminem zdawanym po ostatniej klasie
   liceum/technikum. Rekomendacja: zamienić na **przełącznik „Tryb
   maturalny”** doczepiany do ostatniej klasy liceum/technikum
   (`Klasa 4 liceum` + toggle), zamiast osobnego, równoległego koszyka.
   Wymaga potwierdzenia, bo to zmiana semantyki, nie tylko nazwy.
3. **Czy dodajemy `User.default_level` (profil ucznia)?** — dziś
   poziom nie jest zapisany przy koncie, każda funkcja pyta osobno i
   synchronizuje się prowizorycznie przez `localStorage`. Przy okazji
   tej zmiany można by to naprawić właściwie (jedna migracja, jedno
   pole), ale to rozszerza zakres poza „zamianę kategorii na klasy”.
4. **Centralizacja słowników opisu poziomu** — rekomendowana (sekcja
   2), ale wymaga review i podmiany w 5+ plikach na raz, więc warto
   potwierdzić zanim zacznie się pisanie kodu.
5. **`whiteboard.html`/`whiteboard.py` nie obsługuje dziś podstawówki**
   — czy to celowe ograniczenie produktowe, czy przeoczenie do
   naprawienia przy okazji tej zmiany?
6. **Migracja istniejących danych** — istniejące rekordy `Lesson.level`
   w bazie zawierają dziś stare wartości (`"liceum"` itp.). Czy zostają
   as-is (nowe wpisy dostają nowy format, stare wyświetlają się po
   staremu), czy robimy jednorazowy backfill mapujący stare wartości na
   sensowną klasę domyślną?

---

## Podsumowanie rekomendacji do decyzji

- Zacząć od odpowiedzi na pytania w sekcji 7 (szczególnie 1 i 2 — one
  determinują kształt UI i backendu wszędzie indziej).
- Zbudować **jeden wspólny moduł list poziomów** (frontend: JS z listą
  + funkcją renderującą picker; backend: `education_levels.py` z
  `describe_level()`) **zanim** zacznie się dotykanie 17 plików — inaczej
  ryzyko powtórzenia dzisiejszego bałaganu z 5 kopiami tego samego
  słownika.
- Wdrażać etapami: Quiz → Sprawdziany/Notatki → Plan nauki/Voice/Tablica
  → Fiszki, zgodnie z harmonogramem w sekcji 4.
- Wibracje w ankiecie: gotowe do zrobienia od razu, niezależnie od
  reszty — mechanizm już istnieje, potrzeba tylko podpięcia go pod
  przyciski ankiety (Android+TWA zadziała od razu, iOS wymaga
  świadomości ograniczenia lub osobnego zadania na natywny most).
