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


def build_blind_verify_prompt_closed(tresc: str, opcje: list) -> str:
    letters = "abcdefghij"
    opcje_txt = "\n".join(
        f"{letters[i]}) {_option_text(o)}" for i, o in enumerate(opcje or [])
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


def build_blind_verify_prompt_open(tresc: str) -> str:
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


def _extract_single_value(s: str):
    """'m = -3' -> -3 (sympy). 'S10 = 150' -> 150. '5/7' -> Rational(5,7).
    Bierze tekst PO ostatnim '=' (jesli jest), zeby ignorowac nazwe
    zmiennej po lewej. None jesli niesparsowalne."""
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


def values_match(claimed_a: str, claimed_b: str) -> bool:
    """Porownuje dwa 'final_answer' stringi. Dla wielo-wartosciowych
    odpowiedzi ('b = 2, c = 4') porownuje KAZDY segment osobno (po
    przecinku), w KOLEJNOSCI - musza sie zgadzac wszystkie.

    NAPRAWIONE (user: "a działa poza matematyka" - real-test na biologii
    ujawnil, ze POPRAWNA odpowiedz "Mitochondrium" byla odrzucana jako
    niezgodna z "mitochondrium" - sympy parsuje pojedyncze slowo jako
    Symbol i porownuje go case-SENSITIVE, wiec ta funkcja dzialala
    poprawnie TYLKO dla matematyki): najpierw PROSTE porownanie tekstowe
    (case/whitespace-insensitive) - jesli sie zgadza, koniec, bez
    dotykania sympy w ogole. Dopiero gdy tekst sie NIE zgadza, proba
    numeryczna/symboliczna przez sympy (tolerancyjne na format: 'm = -3'
    vs '-3', '5/7' vs '0.714...') - lapie przypadki, gdzie ten sam wynik
    matematyczny jest zapisany inaczej. Zwraca False (niezgodnosc) gdy
    NI JEDNO NI DRUGIE sie nie zgadza - caller decyduje, czy to ma
    blokowac (patrz komentarz w callerach: nieparsowalne CLAIMED = 'nie
    blokuj', wiec ten przypadek jest obslugiwany PRZED wywolaniem
    values_match, nie w niej samej)."""
    parts_a = [p.strip() for p in str(claimed_a).split(',')]
    parts_b = [p.strip() for p in str(claimed_b).split(',')]
    if len(parts_a) != len(parts_b):
        return False
    for pa, pb in zip(parts_a, parts_b):
        if _normalize_text_for_compare(pa) == _normalize_text_for_compare(pb):
            continue
        va, vb = _extract_single_value(pa), _extract_single_value(pb)
        if va is None or vb is None:
            return False
        if va == vb:
            continue
        try:
            if sp.simplify(va - vb) == 0:
                continue
        except Exception:
            pass
        return False
    return True


def safe_json_loads(raw: str):
    """Parsuje odpowiedz AI-2 jako JSON - None przy bledzie (caller
    traktuje to jako 'nie udalo sie zweryfikowac', NIE jako niezgodnosc)."""
    try:
        return json.loads(raw)
    except Exception:
        return None
