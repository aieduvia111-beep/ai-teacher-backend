"""WARSTWA 2.5: "slepa" weryfikacja przez DRUGIE, niezalezne AI.

KONTEKST (decyzja architektoniczna usera, sierpien 2026, po ~2 tygodniach
naprawiania kolejnych, wciaz nowych wzorcow bledow matematycznych regexem+
sympy - "Warstwa 2"): zamiast pisac nowy, waski weryfikator sympy za kazdym
razem, gdy AI wymysli nowy ksztalt zadania (co dzialo sie praktycznie
codziennie), dodajemy JEDEN uniwersalny mechanizm - drugie, niezalezne
wywolanie AI, ktore rozwiazuje zadanie OD ZERA (nie widzac odpowiedzi
pierwszego AI, zeby uniknac efektu zakotwiczenia/potwierdzania), a wynik
jest porownywany z odpowiedzia pierwszego AI. Dziala dla KAZDEGO tematu i
KAZDEGO ksztaltu pytania (zamkniete I otwarte), bez pisania nowego kodu za
kazdym razem.

KOSZT/WYDAJNOSC (jawna decyzja usera): blind-check uruchamia sie TYLKO tam,
gdzie sympy (Warstwa 2) NIE MA pewnosci (status "unverifiable") LUB dla
zadan OTWARTYCH (Czesc B Sprawdzianu), ktore w ogole nie maja pokrycia
sympy - NIE na kazdym pytaniu (pytania juz potwierdzone/poprawione przez
sympy z pelna pewnoscia NIE dostaja dodatkowego wywolania - zbedny koszt
na cos, co juz wiemy ze jest poprawne). Wywolania sa BATCHOWANE i
rownolegle (ThreadPoolExecutor w Sprawdzianie - sync klient OpenAI;
asyncio.gather w Quizie - AsyncOpenAI), zeby dodatkowe wywolania NIE
wydluzaly proporcjonalnie czasu generacji.

Ten modul zawiera WYLACZNIE czysta logike (budowanie promptu, parsowanie
odpowiedzi, porownywanie wartosci) - BEZ wlasnego klienta API, zeby Quiz
(openai_exam.py, AsyncOpenAI) i Sprawdzian (exam_pdf_generator.py, sync
OpenAI) uzywaly DOKLADNIE tej samej logiki, kazdy swoim wlasnym klientem -
to gwarantuje identyczne zachowanie w obu miejscach (wymog usera: "QUIZ
MUSI miec TEN SAM mechanizm co Sprawdzian")."""
import json
import re

import sympy as sp

from .math_verify import _option_text, _normalize_subscripts, _to_num, _parse_expr

BLIND_VERIFY_SYSTEM_PROMPT = (
    "Jestes doswiadczonym nauczycielem matematyki. Rozwiazujesz podane "
    "zadanie SAMODZIELNIE i OD ZERA - nie znasz zadnej sugerowanej "
    "odpowiedzi, nie masz do niej dostepu. Sprawdz swoje obliczenia zanim "
    "odpowiesz. Odpowiadasz WYLACZNIE czystym JSON, bez markdown/backtickow."
)

# NOWE (30.08.2026, "problem_class" - Faktografia): powyzszy prompt zaklada
# ZADANIE DO ROZWIAZANIA ("rozwiaz krok po kroku", persona "nauczyciel
# matematyki") - dobrze dopasowane do obliczen, ale semantycznie dziwne
# dla pytania FAKTOGRAFICZNEGO ("Kto napisal Pana Tadeusza?" - nie ma
# czego "rozwiazywac", jest tylko fakt do przypomnienia). WASKI wariant
# TYLKO dla problem_class=="factual" (wszystko inne, w tym brak pola -
# domyslny prompt wyzej, bez zmiany zachowania).
BLIND_VERIFY_SYSTEM_PROMPT_FACTUAL = (
    "Jestes doswiadczonym, rzetelnym nauczycielem. Podane pytanie dotyczy "
    "FAKTU/WIEDZY (nie obliczen) - odpowiadasz na podstawie swojej wiedzy, "
    "SAMODZIELNIE i OD ZERA - nie znasz zadnej sugerowanej odpowiedzi, nie "
    "masz do niej dostepu. Jesli nie jestes pewien faktu, wskaz opcje, "
    "ktora wydaje sie najbardziej prawdopodobna, ale NIE zgaduj wbrew "
    "wiedzy. Odpowiadasz WYLACZNIE czystym JSON, bez markdown/backtickow."
)


def build_blind_verify_prompt_closed(tresc: str, opcje: list, problem_class: str = None) -> str:
    letters = "abcdefghij"
    opcje_txt = "\n".join(
        f"{letters[i]}) {_option_text(o)}" for i, o in enumerate(opcje or [])
    )
    if problem_class == "factual":
        return (
            f"Ponizsze pytanie dotyczy faktu/wiedzy (NIE obliczen) - "
            f"odpowiedz na podstawie swojej wiedzy, calkowicie niezaleznie. "
            f"Wskaz, KTORA z podanych opcji jest poprawna.\n\n"
            f"Pytanie: {tresc}\n\nOpcje:\n{opcje_txt}\n\n"
            f'Odpowiedz WYLACZNIE w formacie JSON: '
            f'{{"uzasadnienie": "krotkie uzasadnienie", '
            f'"odpowiedz": "a"}} (pole "odpowiedz" = DOKLADNIE jedna litera '
            f'spomiedzy podanych opcji, ta ktora jest poprawna).'
        )
    return (
        f"Rozwiaz ponizsze zadanie krok po kroku, calkowicie niezaleznie. "
        f"Na koniec wskaz, KTORA z podanych opcji jest matematycznie "
        f"poprawna.\n\nZadanie: {tresc}\n\nOpcje:\n{opcje_txt}\n\n"
        f'Odpowiedz WYLACZNIE w formacie JSON: '
        f'{{"rozwiazanie": "krotkie rozwiazanie krok po kroku", '
        f'"odpowiedz": "a"}} (pole "odpowiedz" = DOKLADNIE jedna litera '
        f'spomiedzy podanych opcji, ta ktora jest poprawna).'
    )


# NOWE (22.09.2026, KOSZTY - real prod: 3621 wywolan AI-2/dzien, jedno na
# KAZDE pytanie osobno): zamiast N osobnych wywolan (N pytan = N requestow),
# JEDNO wywolanie weryfikuje do _BLIND_VERIFY_BATCH_SIZE pytan naraz -
# ta sama persona/system prompt (wywolujacy grupuje kandydatow wg
# problem_class PRZED wywolaniem tej funkcji, wiec jeden batch nigdy nie
# miesza faktografii z obliczeniami), ten sam wymog "SAMODZIELNIE i OD
# ZERA" na kazde pytanie z osobna. Klucz bezpieczenstwa: kazde pytanie w
# batchu jest kluczowane WLASNYM NUMEREM w JSON (nie pozycja w liscie),
# a caller (patrz openai_exam.py _blind_verify_chunk_closed_quiz) odrzuca
# (fail-closed, tak jak dotychczas dla pojedynczego pytania) KAZDE pytanie
# z osobna, ktorego numeru brakuje w odpowiedzi albo ktorego "odpowiedz"
# sie nie parsuje - blad/niekompletnosc DLA JEDNEGO pytania w batchu nigdy
# nie "pozycza" cudzej odpowiedzi ani nie zaleza od kolejnosci.
def build_blind_verify_prompt_closed_batch(items: list, problem_class: str = None) -> str:
    """`items` = lista (tresc, opcje) krotek. Zwraca JEDEN prompt dla calego batcha."""
    letters = "abcdefghij"
    blocks = []
    for i, (tresc, opcje) in enumerate(items, start=1):
        opcje_txt = "\n".join(
            f"{letters[j]}) {_option_text(o)}" for j, o in enumerate(opcje or [])
        )
        blocks.append(f"Zadanie {i}: {tresc}\n\nOpcje:\n{opcje_txt}")
    joined = "\n\n---\n\n".join(blocks)
    detail_key = "uzasadnienie" if problem_class == "factual" else "rozwiazanie"
    example = ", ".join(
        f'"{i}": {{"{detail_key}": "...", "odpowiedz": "a"}}' for i in range(1, len(items) + 1)
    )
    if problem_class == "factual":
        lead = (
            "Ponizsze pytania dotycza faktow/wiedzy (NIE obliczen) - dla KAZDEGO z nich "
            "odpowiedz na podstawie swojej wiedzy, calkowicie niezaleznie i SAMODZIELNIE "
            "(nie znasz zadnej sugerowanej odpowiedzi, nie masz do niej dostepu)."
        )
    else:
        lead = (
            "Rozwiaz KAZDE z ponizszych zadan krok po kroku, calkowicie niezaleznie i "
            "SAMODZIELNIE (traktuj kazde zadanie osobno - odpowiedz jednego NIE wplywa na inne)."
        )
    return (
        f"{lead} Dla kazdego wskaz, KTORA z podanych opcji jest poprawna.\n\n{joined}\n\n"
        f"Odpowiedz WYLACZNIE w formacie JSON, PODAJ WSZYSTKIE {len(items)} zadania, "
        f'kluczami sa numery zadan jako stringi (dokladnie jak ponizej): {{{example}}} '
        f'(pole "odpowiedz" w KAZDYM zadaniu = DOKLADNIE jedna litera spomiedzy '
        f'podanych opcji TEGO zadania).'
    )


def build_blind_verify_prompt_open(tresc: str, problem_class: str = None) -> str:
    if problem_class == "factual":
        return (
            f"Ponizsze pytanie dotyczy faktu/wiedzy (NIE obliczen) - "
            f"odpowiedz na podstawie swojej wiedzy, calkowicie niezaleznie.\n\n"
            f"Pytanie: {tresc}\n\n"
            f'Odpowiedz WYLACZNIE w formacie JSON: '
            f'{{"uzasadnienie": "krotkie uzasadnienie", '
            f'"final_answer": "..."}} (pole "final_answer" = SAMA '
            f'poprawna odpowiedz, bez opisu, np. "Adam Mickiewicz" albo "1795").'
        )
    return (
        f"Rozwiaz ponizsze zadanie krok po kroku, calkowicie niezaleznie.\n\n"
        f"Zadanie: {tresc}\n\n"
        f'Odpowiedz WYLACZNIE w formacie JSON: '
        f'{{"rozwiazanie": "krotkie rozwiazanie krok po kroku", '
        f'"final_answer": "..."}} (pole "final_answer" = SAMA koncowa '
        f'wartosc liczbowa/wyrazenie bez jednostek i bez opisu, np. "175" '
        f'albo "5/7" albo "m = -3" - jesli zadanie ma wiecej niz jedna '
        f'szukana wartosc, podaj obie oddzielone przecinkiem, np. "b = 2, c = 4").'
    )


def parse_blind_verify_letter(raw_json: dict):
    """Zwraca litere (a/b/c/d...) albo None (nie udalo sie sparsowac -
    caller MUSI traktowac None jako 'nie blokuj', nie jako niezgodnosc -
    patrz komentarz w callerach obu plikow)."""
    if not isinstance(raw_json, dict):
        return None
    letter = str(raw_json.get("odpowiedz", "")).strip().lower()
    letter = re.sub(r'[^a-z]', '', letter)
    return letter if len(letter) == 1 else None


def parse_blind_verify_final_answer(raw_json: dict):
    """Zwraca surowy string final_answer albo None."""
    if not isinstance(raw_json, dict):
        return None
    val = raw_json.get("final_answer")
    if val is None:
        return None
    val = str(val).strip()
    return val if val else None


# NAPRAWIONE (wrzesien 2026, user: "wszystkie tematy maja dzialac" - audyt
# blind-verify na fizyce wykazal 6/6 zadan OTWARTYCH falszywie odrzuconych,
# WSZYSTKIE faktycznie poprawne): AI-1 dostaje w tresci zadania "podaj
# jednostki" (typowe dla fizyki/chemii) -> final_answer="150 J", ale
# promptem AI-2 jest jawnie proszone o wartosc "BEZ jednostek" ->
# final_answer="150". Przed ta naprawa _extract_single_value("150 J")
# nie parsowalo sie jako czysta liczba (_to_num rzuca wyjatek na literze),
# wiec spadalo do _parse_expr, ktore (przez implicit_multiplication)
# CICHO sparsowalo to jako "150*J" (J jako WOLNY SYMBOL, nie jednostka) -
# 150*J nigdy nie rowna sie liczbie 150, wiec KAZDA odpowiedz z jednostka
# byla oznaczana jako niezgodna z AI-2, niezaleznie od poprawnosci. Ten
# regex lapie WYLACZNIE ksztalt "liczba + spacja + jednostka" (np. "150 J",
# "9.81 m/s^2", "60 km/h") - jesli po odcieciu sufiksu reszta parsuje sie
# jako CZYSTA liczba, uzywamy jej. Nie dotyka innych przypadkow (np.
# "m = -3", "x^2+1") - te nadal spadaja do _parse_expr jak dotychczas.
_UNIT_SUFFIX_RE = re.compile(
    r'^([\-+]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?)\s+'
    r'[a-zA-Z°%Ω][a-zA-Z0-9°%Ω²³/^.\-⋅·\s]*$'
)


def _extract_single_value(s: str):
    """'m = -3' -> -3 (sympy). 'S10 = 150' -> 150. '5/7' -> Rational(5,7).
    '150 J' -> 150 (patrz _UNIT_SUFFIX_RE - jednostka odcieta, jesli
    reszta jest czysta liczba). Bierze tekst PO ostatnim '=' (jesli jest),
    zeby ignorowac nazwe zmiennej po lewej. None jesli niesparsowalne."""
    s = _normalize_subscripts(str(s)).strip()
    if '=' in s:
        s = s.rsplit('=', 1)[-1]
    s = s.strip()
    if not s:
        return None
    try:
        return _to_num(s)
    except Exception:
        pass
    m = _UNIT_SUFFIX_RE.match(s)
    if m:
        try:
            return _to_num(m.group(1))
        except Exception:
            pass
    try:
        return _parse_expr(s)
    except Exception:
        return None


def _normalize_text_for_compare(s: str) -> str:
    """Normalizuje tekst do porownania NIE-liczbowego (case/whitespace/
    interpunkcja-koncowa-insensitive) - patrz komentarz w values_match."""
    s = str(s).strip().lower()
    s = re.sub(r'\s+', ' ', s)
    return s.strip('.,;:!?()[]{}')


def _part_equal(pa: str, pb: str) -> bool:
    """Porownanie JEDNEJ wartosci (bez przecinkow-separatorow) - dokladnie
    dotychczasowa logika, plus (19.09.2026) tolerancja dla faktografii:
    gdy w zadnej z wartosci nie ma cyfr ani '=', a wszystkie slowa
    krotszej odpowiedzi wystepuja w dluzszej (co najmniej 4 znaki) -
    "Adam Mickiewicz" == "Mickiewicz". Cale slowa (nie podciagi), wiec
    "chlor" != "chlorek sodu"."""
    if _normalize_text_for_compare(pa) == _normalize_text_for_compare(pb):
        return True
    na, nb = _normalize_text_for_compare(pa), _normalize_text_for_compare(pb)
    if not re.search(r'[\d=]', na + nb):
        ta, tb = set(na.split()), set(nb.split())
        short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
        if short and short <= long_ and sum(len(w) for w in short) >= 4:
            return True
    va, vb = _extract_single_value(pa), _extract_single_value(pb)
    if va is None or vb is None:
        return False
    if va == vb:
        return True
    try:
        return sp.simplify(va - vb) == 0
    except Exception:
        return False


def _values_match_ordered(claimed_a: str, claimed_b: str) -> bool:
    parts_a = [p.strip() for p in str(claimed_a).split(',')]
    parts_b = [p.strip() for p in str(claimed_b).split(',')]
    if len(parts_a) != len(parts_b):
        return False
    return all(_part_equal(pa, pb) for pa, pb in zip(parts_a, parts_b))


_DECIMAL_COMMA_RE = re.compile(r'(?<=\d),(?=\d)')


def values_match(claimed_a: str, claimed_b: str) -> bool:
    """Porownuje dwa 'final_answer' stringi. Dla wielo-wartosciowych
    odpowiedzi ('b = 2, c = 4') porownuje KAZDY segment osobno (po
    przecinku), w KOLEJNOSCI - musza sie zgadzac wszystkie.

    NAPRAWIONE (user: "a działa poza matematyka" - real-test na biologii
    ujawnil, ze POPRAWNA odpowiedz "Mitochondrium" byla odrzucana jako
    niezgodna z "mitochondrium"): najpierw PROSTE porownanie tekstowe
    (case/whitespace-insensitive), dopiero potem sympy (tolerancyjne na
    format: 'm = -3' vs '-3', '5/7' vs '0.714...').

    ROZSZERZONE (19.09.2026, real dane produkcyjne: od 06.09 zadania
    OTWARTE Sprawdzianu odrzucane w ~18% zamowien, glownie
    blind_ai_mismatch_open; offline potwierdzone 7 klas POPRAWNYCH
    odpowiedzi fałszywie uznawanych za niezgodne). Kazde z ponizszych
    DODAJE tylko dopasowania (dotychczasowe True zostaje True), nigdy
    nie zrownuje roznych odpowiedzi:
    1. przecinek dziesietny ("2,5" == "2.5") - wczesniej "2,5" bylo
       ciete po przecinku na "2" i "5";
    2. lista bez nazw zmiennych ("2, 3" == "3, 2") - kolejnosc
       pierwiastkow nie ma znaczenia. Przy jakimkolwiek '=' (np. "b = 2,
       c = 4") kolejnosc/przypisanie NADAL obowiazuje;
    3. faktografia - patrz _part_equal."""
    if _values_match_ordered(claimed_a, claimed_b):
        return True
    a2 = _DECIMAL_COMMA_RE.sub('.', str(claimed_a))
    b2 = _DECIMAL_COMMA_RE.sub('.', str(claimed_b))
    if (a2, b2) != (str(claimed_a), str(claimed_b)) and _values_match_ordered(a2, b2):
        return True
    for a_s, b_s in ((str(claimed_a), str(claimed_b)), (a2, b2)):
        parts_a = [p.strip() for p in a_s.split(',')]
        parts_b = [p.strip() for p in b_s.split(',')]
        all_parts = parts_a + parts_b
        no_names = not any('=' in p for p in all_parts)
        # "x = 2, x = 3": wszystkie czesci maja TE SAME zmienna po lewej
        # (to lista pierwiastkow) - kolejnosc bez znaczenia; "b = 2, c = 4"
        # (rozne zmienne) - przypisanie liczy sie, zostaje kolejnosc.
        same_var = all('=' in p for p in all_parts) and len({p.split('=')[0].strip().lower() for p in all_parts}) == 1
        if len(parts_a) == len(parts_b) > 1 and (no_names or same_var):
            remaining = list(parts_b)
            for pa in parts_a:
                idx = next((i for i, pb in enumerate(remaining) if _part_equal(pa, pb)), None)
                if idx is None:
                    break
                remaining.pop(idx)
            else:
                return True
    return False


def safe_json_loads(raw: str):
    """Parsuje odpowiedz AI-2 jako JSON - None przy bledzie (caller
    traktuje to jako 'nie udalo sie zweryfikowac', NIE jako niezgodnosc)."""
    try:
        return json.loads(raw)
    except Exception:
        return None
