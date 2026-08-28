"""
EXAM PDF GENERATOR — Eduvia AI
Generuje profesjonalne sprawdziany PDF z GPT-4o
Na tym samym poziomie co generator notatek.
"""

import io, re, json, os, tempfile, datetime, time, random
import concurrent.futures as _cf
import matplotlib
matplotlib.use('Agg')
import matplotlib as _mpl
_mpl.rcParams['font.family'] = 'DejaVu Sans'
_mpl.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Flowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from pypdf import PdfWriter, PdfReader
from .level_config import (
    describe_level, get_quadratic_difficulty_anchor, is_quadratic_equation_topic,
    get_sequence_difficulty_anchor, is_sequence_topic,
    get_trig_difficulty_anchor, is_trigonometry_topic,
    get_linear_function_difficulty_anchor, is_linear_function_topic,
    get_quadratic_function_difficulty_anchor, is_quadratic_function_topic,
    get_exponential_function_difficulty_anchor, is_exponential_function_topic,
)
from .math_verify import (
    verify_and_fix_math_question, match_final_answer_index,
    shuffle_options_preserving_correct, log_unverifiable_diagnostic,
    log_no_option_matches_diagnostic, log_final_answer_mismatch_diagnostic,
    is_too_similar_diversity_tag, build_safe_linear_param_quadratic,
    pick_safe_param_values,
)
from .openai_exam import sanitize_latex_json_backslashes, _parallel_batch_sizes
from .difficulty import DifficultyAnalyzer

# ETAP 2 Universal Difficulty Engine: patrz identyczny komentarz w
# openai_exam.py - jedna, wspoldzielona instancja, bez stanu miedzy wywolaniami.
_difficulty_analyzer = DifficultyAnalyzer()

# ============================================================
# CZCIONKI
# ============================================================
def _register_fonts():
    FONT_PATHS = [
        {  # Linux
            'n': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            'b': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            'i': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
        },
        {  # Windows
            'n': 'C:/Windows/Fonts/arial.ttf',
            'b': 'C:/Windows/Fonts/arialbd.ttf',
            'i': 'C:/Windows/Fonts/ariali.ttf',
        },
        {  # Mac
            'n': '/System/Library/Fonts/Helvetica.ttc',
            'b': '/System/Library/Fonts/Helvetica.ttc',
            'i': '/System/Library/Fonts/Helvetica.ttc',
        },
    ]
    for paths in FONT_PATHS:
        if os.path.exists(paths['n']):
            try:
                pdfmetrics.registerFont(TTFont('ExFN', paths['n']))
                pdfmetrics.registerFont(TTFont('ExFB', paths['b']))
                pdfmetrics.registerFont(TTFont('ExFI', paths['i']))
                return 'ExFN', 'ExFB', 'ExFI'
            except: pass
    return 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'

FN, FB, FI = _register_fonts()

def _canvas_pl(c, tekst: str, x: float, y: float, width_pt: float,
               fontsize=9, color='#1E1B4B', bold=False, align='left', bg=None):
    """Rysuje tekst z polskimi znakami na canvas — przezroczyste tło."""
    from reportlab.lib.utils import ImageReader
    from PIL import Image as _PIL
    DPI = 150
    W_IN = max(0.5, width_pt / 72)
    H_IN = max(0.25, fontsize / 72.0 * 2.0)
    col = color.lstrip('#')
    rgb = tuple(int(col[i:i+2], 16)/255 for i in (0, 2, 4))
    ha = 'center' if align == 'center' else ('right' if align == 'right' else 'left')
    xa = 0.5 if align == 'center' else (0.98 if align == 'right' else 0.01)
    fig = plt.figure(figsize=(W_IN, H_IN), dpi=DPI)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor((0, 0, 0, 0)); ax.axis('off')
    ax.text(xa, 0.5, tekst, fontsize=fontsize,
            fontweight='bold' if bold else 'normal',
            color=rgb, ha=ha, va='center', transform=ax.transAxes)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, transparent=True, edgecolor='none')
    plt.close(fig); buf.seek(0)
    pil = _PIL.open(buf).convert('RGBA')
    pw, ph = pil.size
    h_pt = ph / DPI * 72
    out = io.BytesIO(); pil.save(out, 'PNG'); out.seek(0)
    img_r = ImageReader(out)
    if align == 'center':
        x = x - width_pt / 2
    elif align == 'right':
        x = x - width_pt
    c.drawImage(img_r, x, y - h_pt * 0.65, width=width_pt, height=h_pt, mask='auto')

# ============================================================
# KOLORY — jasny motyw dla sprawdzianu (do druku!)
# ============================================================
C_BG       = colors.HexColor('#FFFFFF')   # białe tło
C_SURFACE  = colors.HexColor('#F8F9FF')   # bardzo jasny niebieskofiolet
C_SURFACE2 = colors.HexColor('#EEF0FF')   # trochę ciemniejszy
C_ACCENT   = colors.HexColor('#4F46E5')   # indygo - nagłówki
C_ACCENT2  = colors.HexColor('#7C3AED')   # fiolet
C_GREEN    = colors.HexColor('#059669')   # zielony - klucz odpowiedzi
C_RED      = colors.HexColor('#DC2626')   # czerwony - ostrzeżenia
C_TEXT     = colors.HexColor('#1E1B4B')   # ciemny tekst
C_MUTED    = colors.HexColor('#6B7280')   # szary
C_BORDER   = colors.HexColor('#C7D2FE')   # jasny border indygo
C_GOLD     = colors.HexColor('#D97706')   # złoty - punkty
C_LINEBG   = colors.HexColor('#F0F0F0')   # linia do odpowiedzi

PW, PH = A4

# ============================================================
# PROMPT
# ============================================================
EXAM_PROMPT = """Jestes doswiadczonym nauczycielem z 15-letnim stazem.
Tworzysz PROFESJONALNY SPRAWDZIAN.

PARAMETRY:
- POZIOM UCZNIA: {klasa}
- SZCZEGOLOWY OPIS POZIOMU: {poziom_opis}
- TEMAT: {temat}
- TRUDNOSC: {trudnosc}
- LICZBA PYTAN: {liczba_pytan}

POZIOM = {klasa}. KONKRETNIE:

[podstawowka]: ulamki liczbowe, procenty, prosta geometria, rownania liniowe
[liceum]: ulamki algebraiczne p(x)/q(x), funkcje wymierne, nierownosci wymierne,
          dziedziny funkcji wymiernych, uklady rownan z ulamkami
          ZAKAZ: prostego dodawania ulamkow liczbowych — to material podstawowki
[matura]: poziom CKE rozszerzony, funkcje wymierne z parametrem, dowody
[studia]: rozklad na ulamki proste, calki wymierne, szeregi

TRUDNOSC = {trudnosc} w ramach {klasa}:
[latwa]:   podstawowka=dodawanie ulamkow | liceum=prosta funkcja wymierna
[srednia]: podstawowka=dzialania mieszane | liceum=nierownosc wymierna 2-krokowa
[trudna]:  podstawowka=zadania wieloetapowe | liceum=nierownosci z parametrem, badanie funkcji

NAKAZ: KAZDE zadanie musi byc na poziomie {klasa} i trudnosci {trudnosc}
ZAKAZ: dla liceum/matura/studia — prostego dodawania ulamkow liczbowych
{difficulty_anchor_blok}
WERYFIKACJA OBLICZEN - KRYTYCZNE (bledny klucz odpowiedzi to powazny blad,
tak samo powazny jak zbyt latwe zadanie):
Dla KAZDEGO zadania z obliczeniami (rownania, nierownosci, delta/wyroznik,
pierwiastki, prawdopodobienstwo, pochodne, calki itp.) MUSISZ, ZANIM
zapiszesz finalna odpowiedz:
1. Rozwiaz zadanie NAPRAWDE, krok po kroku (nie tylko w polu
   "odpowiedz_modelowa" - to samo rozumowanie musi faktycznie doprowadzic
   Cie do wyniku, ktory potem zapisujesz).
2. PODSTAW otrzymany wynik z powrotem do pierwotnego rownania/warunku i
   sprawdz, czy sie zgadza (np. dla zadania z parametrem: podstaw
   znaleziona wartosc parametru do rownania i sprawdz, czy faktycznie ma
   ono zadane wlasciwosci - dwa pierwiastki, jeden pierwiastek,
   pierwiastki ujemne, itd. - a nie tylko "wyglada podobnie").
3. Dla zadan zamknietych (Czesc A): upewnij sie, ze DOKLADNIE JEDNA z 4
   opcji odpowiada Twojemu sprawdzonemu wynikowi. Jesli zaden dystraktor
   nie pasuje do prawidlowego wyniku - POPRAW dystraktory, NIE zostawiaj
   klucza "odpowiedz" wskazujacego na bledna opcje.
4. Jesli po podstawieniu wynik SIE NIE ZGADZA - przelicz zadanie jeszcze
   raz od nowa. NIE zgaduj i NIE zostawiaj niesprawdzonej odpowiedzi ani
   niesprawdzonego "odpowiedz_modelowa".

KOLEJNOSC TWORZENIA OPCJI (Czesc A) - zeby nie powtorzyc powyzszego bledu:
NAJPIERW rozwiaz zadanie i zapisz sobie prawdziwy wynik, DOPIERO POTEM
wymysl 3 bledne dystraktory wokol niego. NIGDY nie rob tego odwrotnie
(najpierw 4 "prawdopodobnie wygladajace" opcje, potem zgadywanie ktora
pasuje) - to najczestsza przyczyna sytuacji, w ktorej PRAWDZIWA
odpowiedz nie znajduje sie wsrod opcji wcale. Jesli rownanie z
parametrem ma parametr jako WSPOLCZYNNIK PRZY x^2 (np. $ax^2+...=0$) -
to trudniejszy przypadek: pamietaj o zalozeniu wspolczynnik != 0
(inaczej rownanie przestaje byc kwadratowe) w obliczeniach delty I w
opcjach.

POLE "final_answer" (Czesc A) - NOWE, OBOWIAZKOWE: oprocz "odpowiedz" i
"wyjasnienie", KAZDE zadanie zamkniete MUSI miec pole "final_answer" -
skopiuj do niego DOKLADNIE (znak w znak, razem z $...$, BEZ prefiksu
"a) ") tekst TEJ JEDNEJ opcji z "opcje", ktora jest Twoja sprawdzona,
poprawna odpowiedzia. NIE parafrazuj, NIE skracaj. System automatycznie
sprawdza to pole i ODRZUCA zadanie, jesli "final_answer" nie jest
identyczny z zadna opcja - wiec musi dokladnie pasowac.

POLE "diversity_tag" (Czesc A) - NOWE, OBOWIAZKOWE (pomaga systemowi
pilnowac roznorodnosci w sprawdzianie): dla KAZDEGO zadania zamknietego
podaj obiekt z 4 KROTKIMI (kilka slow, NIE zdaniami) polami opisujacymi
WLASNYMI slowami typ rozumowania w TYM zadaniu:
  "skill" - glowna umiejetnosc/wzor uzyty (np. "wzor na delte", "wzory Viete'a", "twierdzenie sinusow")
  "concept" - kluczowe pojecie/wariant (np. "parametr jako wspolczynnik liniowy", "parametr jako wyraz wolny")
  "task_type" - co dokladnie trzeba zrobic (np. "wyznacz parametr z warunku na delte", "oblicz wartosc wyrazenia")
  "reasoning" - krotki opis krokow (np. "oblicz delte, rozwiaz nierownosc, zapisz przedzial")
KRYTYCZNE: jesli generujesz WIELE zadan tego samego tematu, CELOWO
ROZNICUJ te 4 pola miedzy zadaniami - to jest sygnal dla systemu, ktory
pilnuje, zeby sprawdzian nie skladal sie z wielu zadan o tym samym
schemacie (tylko z innymi liczbami/literami). Jesli dwa zadania maja
NAPRAWDE ten sam typ rozumowania - ich tagi tez powinny to szczerze
odzwierciedlac.

GRAMATYKA - KRYTYCZNE (czesty blad): gdy odpowiedzia jest ZBIOR/
PRZEDZIAL/NIEROWNOSC (nie jedna liczba), pytanie o parametr MUSI byc w
LICZBIE MNOGIEJ: "Dla jakich wartości parametru {{x}}..." - NIGDY "Dla
jakiej wartości parametru {{x}}..." (liczba pojedyncza jest gramatycznie
bledna, bo sugeruje jedna wartosc, a szukamy calego zbioru). Ta sama
zasada dotyczy KAZDEGO tematu z parametrem, nie tylko rownan
kwadratowych.
POPRAWNIE: "Dla jakich wartości parametru m równanie ... ma dwa różne pierwiastki?"
BLEDNIE: "Dla jakiej wartości parametru m równanie ... ma dwa różne pierwiastki?"

WZORY MATEMATYCZNE:
KRYTYCZNE: backslash podwojny w JSON: \\frac, \\sqrt, \\cdot, \\times
KRYTYCZNE: KAZDY wzor w dolarach: $wzor$
ZAKAZ: \\left, \\right, \\displaystyle, \\limits, \\newline
POPRAWNE: "$\\frac{{a}}{{b}}$", "$x^2 + y^2$", "$\\sqrt{{4}}$"

POLE "wyjasnienie" - WIELOKROKOWE OBLICZENIA (KRYTYCZNE, czesty blad):
Wielokrokowe wyjasnienie (np. delta -> warunek -> wzory Viete'a) pisz
jako JEDNO, CIAGLE zdanie zwyklej prozy, w ktorym TYLKO pojedyncze
wzory sa opakowane w $...$ (kazdy z osobna). NIGDY nie uzywaj \\newline
ani \\\\ do lamania linii wewnatrz "wyjasnienie" - psuje to renderowanie
(zlamane dolary, dublowanie tekstu w PDF). NIGDY nie opakowuj calego
zdania w jeden $...$.

WLASNE INSTRUKCJE NAUCZYCIELA (jesli podane — OBOWIAZKOWE):
{wlasne_instrukcje_blok}

ZASADY:
- Pytania konkretne i obliczeniowe
- Kazde pytanie z jasna liczba punktow
- Dystraktory realistyczne
- Zadania otwarte ze schematem oceniania
- Trudnosc rosnaca w obrebie sekcji
- Po polsku, konkretne liczby

=== STRUKTURA JSON ===
{{
  "tytul": "Sprawdzian: [temat] (max 60 znakow)",
  "przedmiot": "Matematyka / Fizyka / Chemia itp.",
  "klasa": "{klasa}",
  "czas": 45,
  "punkty_lacznie": 30,
  "instrukcja": "Przeczytaj kazde zadanie uwaznie. Odpowiedzi pisz czytelnie. Przy zadaniach obliczeniowych pokazuj sposob rozwiazania.",

  "sekcje": [
    {{
      "nazwa": "Czesc A — Zadania zamkniete",
      "typ": "zamkniete",
      "instrukcja_sekcji": "Zaznacz poprawna odpowiedz (a, b, c lub d). Za kazde poprawne: 1 pkt.",
      "pytania": [
        {{
          "nr": 1,
          "tresc": "Tresc pytania z konkretnymi danymi. Moze zawierac $wzory$.",
          "opcje": ["a) ...", "b) ...", "c) ...", "d) ..."],
          "odpowiedz": "b",
          "final_answer": "...(doslowna kopia tresci opcji b, BEZ prefiksu 'b) ')",
          "punkty": 1,
          "wyjasnienie": "Krotkie wyjasnienie dlaczego b jest poprawne.",
          "diversity_tag": {{
            "skill": "wzor na delte", "concept": "parametr jako wyraz wolny",
            "task_type": "wyznacz parametr z warunku na delte",
            "reasoning": "oblicz delte, rozwiaz nierownosc, zapisz przedzial"
          }}
        }}
      ]
    }},
    {{
      "nazwa": "Czesc B — Zadania obliczeniowe",
      "typ": "otwarte",
      "instrukcja_sekcji": "Rozwiaz zadania pokazujac pelny sposob obliczen. Podaj jednostki.",
      "pytania": [
        {{
          "nr": 6,
          "tresc": "Tresc zadania na poziomie {klasa}, trudnosc {trudnosc} — NIE kopiuj tego przykladu!",
          "punkty": 4,
          "miejsce_na_odpowiedz": 6,
          "schemat_oceniania": [
            "1 pkt — znalezienie wspolnego mianownika (20)",
            "1 pkt — poprawne rozszerzenie ulamkow",
            "1 pkt — poprawne dodanie licznikow",
            "1 pkt — skrocenie wyniku do postaci nieskracalnej"
          ],
          "odpowiedz_modelowa": "Pelne rozwiazanie krok po kroku z wynikiem."
        }}
      ]
    }}
  ]
}}

=== WYMAGANIA ILOSCI ===
- DOKLADNIE {liczba_pytan} pytan lacznie (NIE wiecej, NIE mniej)
- rozdziel proporcjonalnie: okolo 60% zamknietych, 40% otwartych
- PRIORYTET: liczba pytan {liczba_pytan} jest WAZNIEJSZA niz zakresy sekcji
- punkty lacznie: 25-35 pkt
- trudnosc rosnaca w obrebie kazdej sekcji
- final_answer (zadania zamkniete) = doslowna kopia tresci poprawnej opcji, BEZ prefiksu "a) " (patrz wyzej)
- diversity_tag (zadania zamkniete) = 4 krotkie pola opisujace typ rozumowania (patrz wyzej) - ROZNE dla roznych zadan
- PO POLSKU, konkretne liczby w zadaniach, nie ogolniki"""

_MATH_INDICATOR_RE = re.compile(r'[\d\\=+\-*/^<>_{}]')


def _strip_mistaken_dollar_pairs(t: str) -> str:
    """Usuwa POJEDYNCZE "sieroce" dolary bez prawdziwego partnera (skanuje
    znak po znaku, nie sekwencyjnym parowaniem) - patrz identyczny fix (z
    pelnym uzasadnieniem) w openai_exam.py."""
    out = []
    i, n = 0, len(t)
    while i < n:
        if t[i] != '$':
            out.append(t[i])
            i += 1
            continue
        j = t.find('$', i + 1)
        if j == -1:
            out.append(t[i])
            i += 1
            continue
        content = t[i + 1:j]
        if _MATH_INDICATOR_RE.search(content):
            out.append(t[i:j + 1])
            i = j + 1
        else:
            i += 1
    return ''.join(out)


def _fix_latex(tekst: str) -> str:
    """Naprawia brakujące backslashe w LaTeX — prosta zamiana stringiem."""
    if not tekst:
        return tekst
    # Usun \newline / \\ - model czasem wstawia je jako separator krokow w
    # wielokrokowych wyjasnieniach (Viete itp.), co psuje parzystosc dolarow
    # i renderowanie (patrz identyczny fix w openai_exam.py fix_latex_in_quiz).
    tekst = tekst.replace('\\newline', ' ').replace('\\\\', ' ')
    # Zwin ciagi 2+ dolarow do pojedynczego, usun "sieroce" nie-matematyczne
    # pary $...$ (patrz _strip_mistaken_dollar_pairs), po czym zwin jeszcze
    # raz na wypadek nowej przyleglosci po usunieciu.
    tekst = re.sub(r'\${2,}', '$', tekst)
    tekst = _strip_mistaken_dollar_pairs(tekst)
    tekst = re.sub(r'\${2,}', '$', tekst)
    # Lista komend które GPT gubi backslash przed
    for cmd in ['frac', 'sqrt', 'cdot', 'times', 'div', 'sum', 'int',
                'alpha', 'beta', 'gamma', 'delta', 'pi', 'theta',
                'infty', 'leq', 'geq', 'neq', 'approx', 'pm',
                'land', 'lor', 'lnot', 'forall', 'exists', 'in', 'notin',
                'cup', 'cap', 'subset', 'supset', 'emptyset',
                'left', 'right', 'text', 'mathrm', 'overline']:
        # Zamień " rac{" -> "\frac{" (gdy brak backslasha)
        tekst = tekst.replace(' ' + cmd + '{', ' \\' + cmd + '{')
        tekst = tekst.replace('$' + cmd + '{', '$\\' + cmd + '{')
        tekst = tekst.replace('\n' + cmd + '{', '\n\\' + cmd + '{')
    return tekst


def _merge_exam_data_chunks(chunks: list) -> dict:
    """Laczy wyniki kilku ROWNOLEGLYCH wywolan _get_exam_data_raw w
    jeden dokument (patrz _get_exam_data_raw_parallel) - laczy pytania
    PER TYP sekcji (zamkniete/otwarte osobno, nie mieszane), metadane
    (tytul/przedmiot/klasa/czas/...) biora sie z pierwszego niepustego
    wyniku. Numeracja "nr" jest i tak przeliczana pozniej (patrz
    _fill_missing_exam_questions), wiec tutaj nie ma znaczenia."""
    chunks = [c for c in chunks if c and c.get("sekcje")]
    if not chunks:
        return {}
    if len(chunks) == 1:
        return chunks[0]
    merged = dict(chunks[0])
    sekcje_by_typ = {}
    order = []
    for chunk in chunks:
        for sekcja in chunk.get("sekcje", []):
            typ = sekcja.get("typ")
            if typ not in sekcje_by_typ:
                sekcje_by_typ[typ] = dict(sekcja)
                sekcje_by_typ[typ]["pytania"] = list(sekcja.get("pytania", []))
                order.append(typ)
            else:
                sekcje_by_typ[typ]["pytania"].extend(sekcja.get("pytania", []))
    merged["sekcje"] = [sekcje_by_typ[t] for t in order]
    return merged


def _fix_latex_in_exam_data(data: dict) -> dict:
    """Stosuje _fix_latex() (w tym usuwanie \\newline/\\\\) do WSZYSTKICH pol
    tekstowych sprawdzianu - jeden punkt normalizacji zaraz po sparsowaniu
    JSON, zanim dane traf ia do KTOREGOKOLWIEK z rendererow PDF. Potrzebne,
    bo np. wyjasnienie w sekcji "zamkniete" jest renderowane bezposrednio
    przez _render_math_png (linia w tabeli klucza odpowiedzi), z pominieciem
    _math_line - jedynego innego miejsca, ktore wczesniej wywolywalo
    _fix_latex."""
    for sekcja in data.get("sekcje", []):
        for pyt in sekcja.get("pytania", []):
            for key in ("tresc", "wyjasnienie", "final_answer", "odpowiedz_modelowa"):
                if pyt.get(key):
                    pyt[key] = _fix_latex(str(pyt[key]))
            if isinstance(pyt.get("opcje"), list):
                pyt["opcje"] = [_fix_latex(str(o)) for o in pyt["opcje"]]
            if isinstance(pyt.get("schemat_oceniania"), list):
                pyt["schemat_oceniania"] = [_fix_latex(str(o)) for o in pyt["schemat_oceniania"]]
    return data


def _render_math_png(tekst: str, width_pt: float, fontsize: float = 11,
                     color: str = '#1E1B4B', bg: str = '#FFFFFF') -> bytes | None:
    """Renderuje tekst (z LaTeX) jako przezroczyste PNG przez matplotlib."""
    from PIL import Image as _PIL
    DPI = 150
    W_IN = max(0.5, width_pt / 72)
    # Zawijanie tekstu
    cpl = max(20, int(W_IN * 72 / (fontsize * 0.58)))
    linie, bufor, in_m = [], "", False
    for ch in tekst:
        if ch == "$": in_m = not in_m
        bufor += ch
        if ch == " " and not in_m and len(bufor) > cpl:
            linie.append(bufor.rstrip()); bufor = ""
    if bufor.strip(): linie.append(bufor.strip())
    if not linie: linie = [tekst]
    n = len(linie)
    H_IN = max(0.3, n * fontsize / 72.0 * 1.9 + 0.08)
    full = "\n".join(linie)
    try:
        fig = plt.figure(figsize=(W_IN, H_IN), dpi=DPI)
        fig.patch.set_alpha(0)
        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
        ax.set_facecolor((0, 0, 0, 0)); ax.axis("off")
        ax.text(0.008, 0.97, full, fontsize=fontsize, color=color,
                ha="left", va="top", transform=ax.transAxes, linespacing=1.5)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=DPI, transparent=True, edgecolor="none")
        plt.close(fig); buf.seek(0)
        rgba = _PIL.open(buf).convert("RGBA")
        out = io.BytesIO(); rgba.save(out, "PNG"); out.seek(0)
        return out.read()
    except:
        try: plt.close(fig)
        except: pass
        return None

def _render_formula_png(formula: str, width_pt: float = 400) -> bytes | None:
    """Renderuje samodzielny wzór matematyczny — wyśrodkowany."""
    from PIL import Image as _PIL
    f = formula.strip()
    if not f.startswith('$'): f = '$' + f + '$'
    f_inner = f[1:-1]
    f_inner = _sanitize_mathtext(f_inner)
    f = '$' + f_inner + '$'
    W_IN = max(1.0, width_pt / 72)
    try:
        fig = plt.figure(figsize=(W_IN, 0.75), dpi=180)
        fig.patch.set_facecolor('#FFFFFF')
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor('#FFFFFF'); ax.axis('off')
        ax.text(0.5, 0.5, f, fontsize=22, ha='center', va='center',
                color='#1E1B4B', transform=ax.transAxes)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=180, bbox_inches='tight',
                    facecolor='#FFFFFF', edgecolor='none', pad_inches=0.08)
        plt.close(fig); buf.seek(0)
        from PIL import Image as PIL2
        rgb = PIL2.open(buf).convert('RGB')
        out = io.BytesIO(); rgb.save(out, 'PNG'); out.seek(0)
        return out.read()
    except:
        try: plt.close(fig)
        except: pass
        return None

def _png_to_rl(png: bytes, width_pt: float):
    """Konwertuje PNG bytes na ReportLab Image z przezroczystością."""
    from reportlab.platypus import Image as RLImage
    from PIL import Image as PIL
    pil = PIL.open(io.BytesIO(png))
    pw, ph = pil.size
    scale = width_pt / (pw / 150 * 72)
    h_pt = (ph / 150 * 72) * scale
    img = RLImage(io.BytesIO(png), width=width_pt, height=h_pt)
    img._mask = 'auto'
    return img

def _math_line(tekst: str, width_pt: float, fontsize=11,
               color='#1E1B4B', bg='#FFFFFF', styl=None):
    """Zawsze renderuje przez matplotlib PNG — polskie znaki 100%."""
    from reportlab.platypus import Image as RLImage
    tekst = _fix_latex(str(tekst))
    png = _render_math_png(str(tekst), width_pt, fontsize, color, bg)
    if png:
        return _png_to_rl(png, width_pt)
    # fallback
    if styl: return Paragraph(str(tekst), styl)
    return Paragraph(str(tekst), _styles()['body'])

# ============================================================
# STYLE
# ============================================================
def _styles():
    return {
        'title': ParagraphStyle('ExTitle', fontName=FB, fontSize=22,
            textColor=C_ACCENT, leading=28, alignment=1, spaceAfter=4),
        'subtitle': ParagraphStyle('ExSub', fontName=FN, fontSize=11,
            textColor=C_MUTED, leading=15, alignment=1, spaceAfter=2),
        'section': ParagraphStyle('ExSec', fontName=FB, fontSize=12,
            textColor=C_ACCENT, leading=16, spaceBefore=4),
        'body': ParagraphStyle('ExBody', fontName=FN, fontSize=10.5,
            textColor=C_TEXT, leading=15),
        'bold': ParagraphStyle('ExBold', fontName=FB, fontSize=10.5,
            textColor=C_TEXT, leading=15),
        'small': ParagraphStyle('ExSmall', fontName=FN, fontSize=8.5,
            textColor=C_MUTED, leading=12),
        'answer': ParagraphStyle('ExAns', fontName=FB, fontSize=10,
            textColor=C_GREEN, leading=14),
        'schema': ParagraphStyle('ExSchema', fontName=FI, fontSize=9.5,
            textColor=C_MUTED, leading=13, leftIndent=12),
        'points': ParagraphStyle('ExPts', fontName=FB, fontSize=9,
            textColor=C_GOLD, leading=12, alignment=2),
        'instruk': ParagraphStyle('ExInstr', fontName=FI, fontSize=9.5,
            textColor=C_ACCENT2, leading=13),
    }

# ============================================================
# FLOWABLES
# ============================================================
class HRule(Flowable):
    """Pozioma linia."""
    def __init__(self, width, color=C_BORDER, thickness=1):
        super().__init__()
        self.width = width; self.color = color; self.thickness = thickness
        self.height = thickness + 4
    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 2, self.width, 2)

class AnswerLines(Flowable):
    """Linie na odpowiedź do zadań otwartych."""
    def __init__(self, width, lines=4):
        super().__init__()
        self.width = width; self.lines = lines
        self.height = lines * 22 + 6
    def draw(self):
        self.canv.setStrokeColor(C_LINEBG)
        self.canv.setLineWidth(0.8)
        for i in range(self.lines):
            y = self.height - 20 - i * 22
            self.canv.line(0, y, self.width, y)

class QuestionBox(Flowable):
    """Ramka pytania zamkniętego z numerem."""
    def __init__(self, nr, punkty, width):
        super().__init__()
        self.nr = nr; self.punkty = punkty
        self.width = width; self.height = 28
    def draw(self):
        c = self.canv
        # Lewy akcent
        c.setFillColor(C_ACCENT)
        c.rect(0, 0, 4, self.height, fill=1, stroke=0)
        # Tło
        c.setFillColor(C_SURFACE)
        c.rect(4, 0, self.width - 4, self.height, fill=1, stroke=0)
        # Nr pytania
        c.setFillColor(C_ACCENT)
        c.setFont(FB, 11)
        c.drawString(12, 9, f"{self.nr}.")
        # Punkty (prawy róg)
        c.setFillColor(C_GOLD)
        c.setFont(FB, 9)
        pts_txt = f"{self.punkty} pkt"
        c.drawRightString(self.width - 8, 9, pts_txt)

class OpenQuestionHeader(Flowable):
    """Nagłówek zadania otwartego."""
    def __init__(self, nr, punkty, width):
        super().__init__()
        self.nr = nr; self.punkty = punkty
        self.width = width; self.height = 32
    def draw(self):
        c = self.canv
        c.setFillColor(C_ACCENT2)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        _canvas_pl(c, f"Zadanie {self.nr}", 12, 10, self.width / 2,
                   fontsize=12, color='#FFFFFF', bold=True, bg='#7C3AED')
        _canvas_pl(c, f"{self.punkty} punktow", self.width - 12, 10, self.width / 2,
                   fontsize=10, color='#FFFFFF', align='right', bg='#7C3AED')

class SectionHeader(Flowable):
    """Nagłówek sekcji sprawdzianu."""
    def __init__(self, nazwa, instrukcja, width):
        super().__init__()
        self.nazwa = nazwa; self.instrukcja = instrukcja
        self.width = width; self.height = 46
    def draw(self):
        c = self.canv
        c.setFillColor(C_SURFACE2)
        c.roundRect(0, 0, self.width, self.height, 8, fill=1, stroke=0)
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(1.5)
        c.roundRect(0, 0, self.width, self.height, 8, fill=0, stroke=1)
        _canvas_pl(c, self.nazwa, 14, 28, self.width - 28,
                   fontsize=12, color='#4F46E5', bold=True)
        _canvas_pl(c, self.instrukcja[:90], 14, 12, self.width - 28,
                   fontsize=9, color='#6B7280')

# ============================================================
# OKŁADKA SPRAWDZIANU
# ============================================================
def _draw_exam_cover(c, data: dict, wariant: str = "A"):
    w, h = PW, PH
    # Białe tło
    c.setFillColor(C_BG)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Górny pasek akcent
    c.setFillColor(C_ACCENT)
    c.rect(0, h - 6, w, 6, fill=1, stroke=0)

    # Boczny akcent
    c.setFillColor(C_SURFACE2)
    c.rect(0, 0, 8, h, fill=1, stroke=0)
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, 4, h, fill=1, stroke=0)

    # Logo / badge
    c.setFillColor(C_SURFACE2)
    c.roundRect(w/2 - 80, h - 80, 160, 34, 17, fill=1, stroke=0)
    c.setFillColor(C_ACCENT)
    c.setFont(FB, 10)
    c.drawCentredString(w/2, h - 58, "✦  EDUVIA AI  ✦")

    # Wariant
    c.setFillColor(C_ACCENT)
    c.circle(w - 55, h - 55, 28, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(FB, 20)
    c.drawCentredString(w - 55, h - 48, wariant)

    # Tytuł
    tytul = data.get('tytul', 'Sprawdzian')
    if len(tytul) > 35:
        words = tytul.split()
        line1 = " ".join(words[:len(words)//2])
        line2 = " ".join(words[len(words)//2:])
        _canvas_pl(c, line1, w/2, h - 145, w - 80, fontsize=20, color='#4F46E5', bold=True, align='center')
        _canvas_pl(c, line2, w/2, h - 168, w - 80, fontsize=20, color='#4F46E5', bold=True, align='center')
        y_after = h - 190
    else:
        _canvas_pl(c, tytul, w/2, h - 155, w - 80, fontsize=20, color='#4F46E5', bold=True, align='center')
        y_after = h - 180

    # Przedmiot / klasa
    info = f"{data.get('przedmiot','')}"
    if data.get('klasa'): info += f"  |  {data.get('klasa','')}"
    _canvas_pl(c, info, w/2, y_after, w - 80, fontsize=11, color='#6B7280', align='center')

    # Linia
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(1)
    c.line(40, y_after - 20, w - 40, y_after - 20)

    # Info box — czas, punkty, data
    box_y = y_after - 90
    box_items = [
        ("⏱", f"{data.get('czas', 45)} minut", "Czas"),
        ("📊", f"{data.get('punkty_lacznie', 30)} pkt", "Punkty"),
        ("📅", datetime.date.today().strftime("%d.%m.%Y"), "Data"),
    ]
    box_w = 120
    box_x_start = w/2 - (len(box_items) * box_w + (len(box_items)-1)*10) / 2
    for i, (icon, val, label) in enumerate(box_items):
        bx = box_x_start + i * (box_w + 10)
        c.setFillColor(C_SURFACE2)
        c.roundRect(bx, box_y, box_w, 56, 10, fill=1, stroke=0)
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(1)
        c.roundRect(bx, box_y, box_w, 56, 10, fill=0, stroke=1)
        c.setFillColor(C_ACCENT)
        c.setFont(FN, 16)
        c.drawCentredString(bx + box_w/2, box_y + 34, icon)
        c.setFillColor(C_TEXT)
        c.setFont(FB, 13)
        c.drawCentredString(bx + box_w/2, box_y + 18, val)
        c.setFillColor(C_MUTED)
        c.setFont(FN, 8)
        c.drawCentredString(bx + box_w/2, box_y + 5, label)

    # Pole: Imię i nazwisko / Klasa
    field_y = box_y - 70
    # Imię i nazwisko
    c.setFillColor(C_SURFACE)
    c.roundRect(40, field_y, w - 80, 42, 8, fill=1, stroke=0)
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(1)
    c.roundRect(40, field_y, w - 80, 42, 8, fill=0, stroke=1)
    c.setFillColor(C_MUTED)
    c.setFont(FN, 8)
    _canvas_pl(c, "IMIĘ I NAZWISKO", 52, field_y + 30, w - 104,
               fontsize=8, color='#6B7280')
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.5)
    c.line(52, field_y + 18, w - 52, field_y + 18)

    # Klasa / Nr
    field_y2 = field_y - 52
    col_w = (w - 80 - 12) / 2
    for i, label in enumerate(["KLASA", "NR W DZIENNIKU"]):
        bx = 40 + i * (col_w + 12)
        c.setFillColor(C_SURFACE)
        c.roundRect(bx, field_y2, col_w, 42, 8, fill=1, stroke=0)
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(1)
        c.roundRect(bx, field_y2, col_w, 42, 8, fill=0, stroke=1)
        c.setFillColor(C_MUTED)
        c.setFont(FN, 8)
        c.drawString(bx + 12, field_y2 + 30, label)

    # Skala ocen
    scale_y = field_y2 - 70
    c.setFillColor(C_SURFACE2)
    c.roundRect(40, scale_y, w - 80, 54, 8, fill=1, stroke=0)
    c.setStrokeColor(C_BORDER)
    c.roundRect(40, scale_y, w - 80, 54, 8, fill=0, stroke=1)
    c.setFillColor(C_MUTED); c.setFont(FN, 8)
    _canvas_pl(c, "SKALA OCEN", 52, scale_y + 42, 120, fontsize=8, color='#6B7280')
    max_pkt = data.get('punkty_lacznie', 30)
    oceny = [
        (f"{int(max_pkt*0.92)}–{max_pkt}", "6", C_ACCENT),
        (f"{int(max_pkt*0.80)}–{int(max_pkt*0.91)}", "5", C_GREEN),
        (f"{int(max_pkt*0.65)}–{int(max_pkt*0.79)}", "4", colors.HexColor('#0891B2')),
        (f"{int(max_pkt*0.50)}–{int(max_pkt*0.64)}", "3", C_GOLD),
        (f"{int(max_pkt*0.30)}–{int(max_pkt*0.49)}", "2", C_RED),
        (f"0–{int(max_pkt*0.29)}", "1", C_MUTED),
    ]
        
    col_w2 = (w - 80) / len(oceny)
    for i, (zakres, ocena, kolor) in enumerate(oceny):
        bx = 40 + i * col_w2
        c.setFillColor(kolor)
        c.setFont(FB, 14)
        c.drawCentredString(bx + col_w2/2, scale_y + 20, ocena)
        c.setFillColor(C_MUTED)
        c.setFont(FN, 7)
        c.drawCentredString(bx + col_w2/2, scale_y + 8, zakres)

    # Instrukcja ogólna
    instr = data.get('instrukcja', '')
    if instr:
        instr_y = scale_y - 60
        c.setFillColor(colors.HexColor('#FFF7ED'))
        c.roundRect(40, instr_y, w - 80, 48, 8, fill=1, stroke=0)
        c.setStrokeColor(C_GOLD)
        c.setLineWidth(1)
        c.roundRect(40, instr_y, w - 80, 48, 8, fill=0, stroke=1)
        c.setFillColor(C_GOLD); c.setFont(FB, 9)
        c.drawString(52, instr_y + 35, "INSTRUKCJA:")
        words = instr.split()
        line, lines = "", []
        for word in words:
            if len(line + " " + word) > 90: lines.append(line); line = word
            else: line = (line + " " + word).strip()
        if line: lines.append(line)
        for j, l in enumerate(lines[:2]):
            _canvas_pl(c, l, 52, instr_y + 22 - j * 13, w - 104,
                       fontsize=8.5, color='#1E1B4B')

    # Stopka
    c.setFillColor(C_MUTED)
    c.setFont(FN, 7)
    _canvas_pl(c, "Wygenerowano przez Eduvia AI • Nie kopiowac • Chronione prawem autorskim",
               w/2, 18, w - 80, fontsize=7, color='#6B7280', align='center')

# ============================================================
# STRONA KLUCZA ODPOWIEDZI
# ============================================================
def _draw_answer_key_page(story, data, S, W):
    story.append(PageBreak())

    # Nagłówek klucza
    png = _render_math_png("KLUCZ ODPOWIEDZI — TYLKO DLA NAUCZYCIELA",
                            W, fontsize=14, color='#FFFFFF', bg='#4F46E5')
    if png:
        story.append(_png_to_rl(png, W))
    else:
        story.append(Paragraph("KLUCZ ODPOWIEDZI", S['section']))

    story.append(Spacer(1, 10))

    for sekcja in data.get('sekcje', []):
        story.append(Spacer(1, 8))
        story.append(_math_line(sekcja.get('nazwa', ''), W, fontsize=12,
                                color='#4F46E5', bg='#FFFFFF', styl=S['section']))
        story.append(Spacer(1, 6))

        if sekcja.get('typ') == 'zamkniete':
            for idx, p in enumerate(sekcja.get('pytania', [])):
                bg_hex = '#F8F9FF' if idx % 2 == 0 else '#FFFFFF'
                bg_col = colors.HexColor(bg_hex)

                # Zbuduj wiersz jako PNG — cały wiersz naraz
                linia = f"  {p.get('nr','?')}.   [{p.get('odpowiedz','?').upper()}]   {p.get('punkty',1)} pkt   —   {p.get('wyjasnienie','')}"
                png = _render_math_png(linia, W, fontsize=9.5,
                                       color='#1E1B4B', bg=bg_hex)
                if png:
                    from PIL import Image as _PILk
                    pil = _PILk.open(io.BytesIO(png))
                    pw2, ph2 = pil.size
                    scale2 = W / (pw2 / 130 * 72)
                    h_pt2 = (ph2 / 130 * 72) * scale2
                    from reportlab.platypus import Image as RLImage2
                    img_el = RLImage2(io.BytesIO(png), width=W, height=h_pt2)
                    # Opakuj w tabelę z tłem
                    t_row = Table([[img_el]], colWidths=[W])
                    t_row.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,-1), bg_col),
                        ('TOPPADDING', (0,0), (-1,-1), 2),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                        ('LEFTPADDING', (0,0), (-1,-1), 0),
                        ('RIGHTPADDING', (0,0), (-1,-1), 0),
                        ('LINEBELOW', (0,0), (-1,-1), 0.3, C_BORDER),
                    ]))
                    story.append(t_row)
                else:
                    # Fallback plaintext
                    plain = f"{p.get('nr','?')}.  [{p.get('odpowiedz','?').upper()}]  {p.get('punkty',1)} pkt  —  {p.get('wyjasnienie','')}"
                    story.append(Paragraph(plain, ParagraphStyle('kfb', fontName=FN, fontSize=9, textColor=C_TEXT, leading=14)))

        else:
            # Zadania otwarte — schemat oceniania
            for p in sekcja.get('pytania', []):
                story.append(Spacer(1, 8))
                nr_txt = f"Zadanie {p.get('nr','?')} ({p.get('punkty','?')} pkt)"
                story.append(_math_line(nr_txt, W, fontsize=10.5,
                                        color='#1E1B4B', bg='#FFFFFF', styl=S['bold']))
                odp = p.get('odpowiedz_modelowa', '')
                if odp:
                    el = _math_line("Odpowiedź: " + odp, W, fontsize=9.5,
                                   color='#059669', bg='#F0FDF4', styl=S['answer'])
                    story.append(el)
                    story.append(Spacer(1, 4))
                schema = p.get('schemat_oceniania', [])
                if schema:
                    story.append(_math_line("Schemat oceniania:", W, fontsize=8.5,
                                            color='#6B7280', bg='#FFFFFF', styl=S['small']))
                    for krok in schema:
                        el = _math_line("• " + krok, W, fontsize=9,
                                       color='#6B7280', bg='#FFFFFF', styl=S['schema'])
                        story.append(el)
                story.append(HRule(W, C_BORDER))

# ============================================================
# BUDOWANIE STRON SPRAWDZIANU
# ============================================================
def _add_page_bg(c, doc):
    w, h = A4
    c.saveState()
    c.setFillColor(C_BG)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    # Boczny pasek
    c.setFillColor(C_SURFACE2)
    c.rect(0, 0, 8, h, fill=1, stroke=0)
    c.setFillColor(C_ACCENT)
    c.rect(0, 0, 4, h, fill=1, stroke=0)
    # Górna linia
    c.setFillColor(C_SURFACE2)
    c.rect(0, h-30, w, 30, fill=1, stroke=0)
    c.setFillColor(C_ACCENT)
    c.rect(0, h-4, w, 4, fill=1, stroke=0)
    # Nagłówek strony
    c.setFont(FN, 8); c.setFillColor(C_MUTED)
    _canvas_pl(c, "Eduvia AI — Sprawdzian", 20, h - 20, 200, fontsize=8, color='#6B7280')
    c.setFont(FN, 8); c.setFillColor(C_MUTED)
    _canvas_pl(c, f"Strona {doc.page}", w - 220, h - 20, 200, fontsize=8, color='#6B7280', align='right')
    # Dolna linia
    c.setStrokeColor(C_BORDER); c.setLineWidth(0.5)
    c.line(20, 20, w - 20, 20)
    _canvas_pl(c, "Wygenerowano przez Eduvia AI", w/2, 8, 300, fontsize=7, color='#6B7280', align='center')
    c.restoreState()

def _build_exam_pages(data: dict) -> bytes:
    S = _styles()
    W = PW - 80
    story = []

    for sekcja in data.get('sekcje', []):
        story.append(Spacer(1, 10))
        story.append(SectionHeader(
            sekcja.get('nazwa', ''),
            sekcja.get('instrukcja_sekcji', ''),
            W
        ))
        story.append(Spacer(1, 12))

        for p in sekcja.get('pytania', []):
            nr = p.get('nr', '?')
            pkt = p.get('punkty', 1)
            tresc = p.get('tresc', '')

            if sekcja.get('typ') == 'zamkniete':
                # Nagłówek pytania
                story.append(QuestionBox(nr, pkt, W))
                story.append(Spacer(1, 4))
                # Treść
                el = _math_line(tresc, W - 40, fontsize=10.5,
                               color='#1E1B4B', bg='#FFFFFF', styl=S['body'])
                # Wcięcie
                t = Table([[el]], colWidths=[W])
                t.setStyle(TableStyle([
                    ('LEFTPADDING',(0,0),(-1,-1), 24),
                    ('RIGHTPADDING',(0,0),(-1,-1), 10),
                    ('TOPPADDING',(0,0),(-1,-1), 2),
                    ('BOTTOMPADDING',(0,0),(-1,-1), 6),
                ]))
                story.append(t)

                # Opcje A-D
                opcje = p.get('opcje', [])
                opcje_items = []
                for op in opcje:
                    el_op = _math_line(op, W/2 - 30, fontsize=10,
                                      color='#1E1B4B', bg='#FFFFFF', styl=S['body'])
                    opcje_items.append(el_op)

                # 2 opcje w wierszu
                rows_op = []
                for i in range(0, len(opcje_items), 2):
                    row = opcje_items[i:i+2]
                    if len(row) == 1: row.append(Spacer(1,1))
                    rows_op.append(row)

                if rows_op:
                    t_op = Table(rows_op, colWidths=[W/2, W/2])
                    t_op.setStyle(TableStyle([
                        ('LEFTPADDING',(0,0),(-1,-1), 24),
                        ('TOPPADDING',(0,0),(-1,-1), 3),
                        ('BOTTOMPADDING',(0,0),(-1,-1), 3),
                    ]))
                    story.append(t_op)
                story.append(Spacer(1, 8))

            else:
                # Zadanie otwarte
                story.append(OpenQuestionHeader(nr, pkt, W))
                story.append(Spacer(1, 6))
                el = _math_line(tresc, W, fontsize=10.5,
                               color='#1E1B4B', bg='#FFFFFF', styl=S['body'])
                story.append(el)
                story.append(Spacer(1, 8))
                # Linie na odpowiedź
                lines = p.get('miejsce_na_odpowiedz', 4)
                story.append(AnswerLines(W, lines=lines))
                story.append(Spacer(1, 12))

    # Klucz odpowiedzi
    _draw_answer_key_page(story, data, S, W)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=40, rightMargin=40,
                            topMargin=50, bottomMargin=30)
    doc.build(story, onFirstPage=_add_page_bg, onLaterPages=_add_page_bg)
    return buf.getvalue()

# ETAP 3: adaptacyjny oversampling - identyczne uzasadnienie i mechanizm
# co w openai_exam.py _buffered_count (patrz komentarz tam).
_HARD_DIFFICULTY_WORDS = {"trudny", "trudna"}

# PORT z Quizu (audyt Sprawdzian V1, sierpien 2026 - user zglosil 13
# zamowionych, 8 dostarczonych): rownania kwadratowe z golym parametrem
# na "medium" maja potwierdzony (w Quizie) wyzszy niz przecietny
# rejection rate (sympy_mismatch - normalna zmiennosc trafnosci AI dla
# tego konkretnego podwzorca) - ten sam +50% bufor co w openai_exam.py.
_MEDIUM_DIFFICULTY_WORDS = {"srednia", "sredni", "średnia", "średni"}


def _buffered_question_count(n: int, temat: str = None, trudnosc: str = None) -> int:
    """Ile zadan zamowic za pierwszym razem, zeby po odrzuceniu blednych
    (weryfikacja sympy/trudnosc) prawdopodobnie zostalo >= n bez potrzeby
    rund dogenerowania. Domyslnie +30% (min +2) - +60% dla "trudna",
    +50% dla "srednia" rownan kwadratowych z parametrem (port z Quizu)."""
    is_quadratic = temat is not None and is_quadratic_equation_topic(temat)
    trudnosc_word = (trudnosc or "").strip().lower()
    is_hard_quadratic = is_quadratic and trudnosc_word in _HARD_DIFFICULTY_WORDS
    is_medium_quadratic = is_quadratic and trudnosc_word in _MEDIUM_DIFFICULTY_WORDS
    if is_hard_quadratic:
        numerator = 6
    elif is_medium_quadratic:
        numerator = 5
    else:
        numerator = 3
    return n + max(2, -(-n * numerator // 10))  # ceil(n * numerator/10), min 2


# Minimalny rozmiar partii w rundzie dogenerowania - NIGDY nie prosimy o
# dokladnie 1 brakujace zadanie. Empirycznie partie 1-zadaniowe mialy w
# praktyce ~0% szans na przejscie weryfikacji dla tematow typu "rownania
# kwadratowe z parametrem", podczas gdy wieksza partia miala ~50%.
_MIN_FILL_BATCH_EXAM = 4

# ZMIENIONE (jawna decyzja usera, sierpien 2026 - w odroznieniu od Quizu,
# TO JEST celowe, globalne podniesienie limitu, NIE waska naprawa jednego
# podwzorca): Sprawdzian - w przeciwienstwie do Quizu - dodatkowo buduje
# PDF (okladka + strony + klucz odpowiedzi, kazda linia renderowana przez
# matplotlib) PO zakonczeniu generowania/weryfikacji tresci - realnie
# zmierzony narzut ~3s dla typowego sprawdzianu (patrz komentarz w
# generate_exam), rosnacy z liczba pytan. User zdecydowal wprost:
# jednolity budzet 60s dla WSZYSTKICH tematow/trudnosci "na wszelki
# wypadek", zamiast wczesniejszego, waskiego dwupoziomowego systemu
# (30s domyslnie / 45s TYLKO dla rownan kwadratowych z parametrem,
# medium). Ta druga gatowana wartosc byla waskim wyjatkiem po analizie
# realnych testow - TO jest inna, swiadoma decyzja: uproszczenie do
# jednego, wiekszego budzetu dla calego Sprawdzianu.
_TIMEOUT_SECONDS_EXAM = 60.0


def _is_medium_linear_param_quadratic_exam(temat: str, trudnosc: str) -> bool:
    """Warunek gatujacy 'safe parameter generation' - PORT z Quizu
    (_is_medium_linear_param_quadratic w openai_exam.py), ten sam warunek
    co _buffered_question_count/_max_generation_seconds_exam dla tego
    samego przypadku. Uzywana TYLKO w rundach dogenerowania - pierwsza
    partia zostaje wolna generacja (naturalny mix podwzorcow, dobry dla
    roznorodnosci)."""
    is_quadratic = temat is not None and is_quadratic_equation_topic(temat)
    trudnosc_word = (trudnosc or "").strip().lower()
    return is_quadratic and trudnosc_word in _MEDIUM_DIFFICULTY_WORDS


def _max_generation_seconds_exam(temat: str = None, trudnosc: str = None) -> float:
    """Zwraca globalny budzet czasu (sekundy) dla calego procesu
    generowania+weryfikacji+dogenerowania sprawdzianu (NIE liczac budowy
    PDF - patrz komentarz nad _TIMEOUT_SECONDS_EXAM). Jednolite 60s dla
    WSZYSTKICH tematow/trudnosci (jawna decyzja usera) - argumenty
    (temat/trudnosc) zostaja w sygnaturze dla zgodnosci z callerami,
    ktore nadal moga chciec przekazac te informacje w przyszlosci."""
    return _TIMEOUT_SECONDS_EXAM

_LETTER_TO_IDX = {"a": 0, "b": 1, "c": 2, "d": 3}
_IDX_TO_LETTER = {v: k for k, v in _LETTER_TO_IDX.items()}


def _question_fingerprint(text: str):
    """ETAP 3: identyczny mechanizm co openai_exam.py _question_fingerprint
    (patrz tam pelne uzasadnienie) - prosty fingerprint do wykrywania
    duplikatow/bardzo podobnych zadan w obrebie jednego requestu."""
    t = (text or "").lower()
    numbers = tuple(re.findall(r'-?\d+(?:[.,]\d+)?', t))
    skeleton = re.sub(r'-?\d+(?:[.,]\d+)?', '#', t)
    skeleton = re.sub(r'[^a-ząćęłńóśźż#]+', ' ', skeleton)
    skeleton = ' '.join(skeleton.split())
    return (skeleton, numbers)


def _verify_and_fix_exam_math(data: dict, trudnosc: str = None, seen_fingerprints: set = None, metrics=None, level: str = None, seen_diversity_tags: list = None) -> dict:
    """Trzywarstwowa weryfikacja dla zadan zamknietych - ten sam
    mechanizm co w Quizie (openai_exam._verify_and_fix_quiz_math), AI
    NIGDY nie decyduje samo, ktora opcja jest "odpowiedz":

    WARSTWA 1 (kazde zadanie zamkniete, kazdy przedmiot): "odpowiedz"
    jest ZAWSZE przeliczany na nowo z dopasowania "final_answer"
    (doslowna kopia poprawnej opcji, ktora AI ma teraz obowiazek podac)
    do "opcje" - match_final_answer_index(). Brak final_answer, brak
    dopasowania, albo dopasowanie do wiecej niz jednej opcji - zadanie
    jest odrzucane (dogenerowywane w innym miejscu potoku).

    WARSTWA 2 (tylko rozpoznane wzorce matematyczne): NIEZALEZNA
    weryfikacja sympy (math_verify.py), ktora liczy prawdziwy wynik z
    tresci zadania i porownuje z opcjami - dodatkowa siatka
    bezpieczenstwa nawet jesli final_answer AI bylo samo w sobie
    matematycznie bledne.

    WARSTWA 3 (ETAP 2 Universal Difficulty Engine, TYLKO rownania
    kwadratowe na razie): walidacja skali trudnosci - osobna od
    poprawnosci matematycznej. Uzywa DifficultyAnalyzer z domain
    modifierem math_quadratic.py, ktory wewnatrz wywoluje NIEZMIENIONY
    validate_quadratic_difficulty z math_verify.py - zachowanie
    identyczne jak przed Etapem 2 (patrz test_difficulty_engine.py).
    Szuka rownania zarowno w tresci zadania, jak i w opcjach odpowiedzi
    (obsluguje tez format "Ktore z ponizszych rownan..."). FAIL ->
    zadanie odrzucone (dogenerowywane w innym miejscu potoku, tak samo
    jak Warstwa 1/2).

    Dziala tylko na sekcjach "zamkniete" (maja 4 opcje do porownania) -
    zadania otwarte ("odpowiedz_modelowa", wolny tekst) nie sa jeszcze
    objete, bo nie maja ustalonego zbioru opcji do sprawdzenia.

    DEDUPLIKACJA (ETAP 3, opcjonalna - tylko gdy `seen_fingerprints`
    podane): identyczny mechanizm co w Quizie - patrz
    openai_exam._verify_and_fix_quiz_math. Dziala TYLKO na sekcjach
    zamknietych (ta sama, wspomniana wyzej luka co Warstwa 1/2/3).

    METRYKI (ETAP 4, opcjonalne - tylko gdy `metrics` podane): identyczny
    mechanizm co w Quizie - patrz openai_exam._verify_and_fix_quiz_math.

    KALIBRACJA POZIOMU (ETAP 5, opcjonalna - tylko gdy `level` podane -
    tutaj to wartosc `klasa` przekazana przez callera, patrz
    _get_exam_data): identyczny mechanizm co w Quizie - Warstwa 3
    przesuwa okno akceptowalnych tierow rownan kwadratowych wzgledem
    poziomu ucznia. Bez `level` - dokladnie dzisiejsze zachowanie."""
    from .metrics import _Timer
    _validation_timer = _Timer(metrics, "validation_time") if metrics else None
    if _validation_timer:
        _validation_timer.__enter__()
    for sekcja in data.get("sekcje", []):
        if sekcja.get("typ") != "zamkniete":
            continue
        kept = []
        for pyt in sekcja.get("pytania", []):
            tresc = pyt.get("tresc", "")
            opcje = pyt.get("opcje", [])

            # WARSTWA 1: wymus "odpowiedz" z "final_answer"
            try:
                fa_status, fa_idx = match_final_answer_index(pyt.get("final_answer"), opcje)
            except Exception as e:
                print(f"[MathVerify][Exam] blad wymuszania final_answer: {e}")
                fa_status, fa_idx = "no_final_answer", None
            if fa_status in ("no_match", "ambiguous", "no_final_answer"):
                print(f"[MathVerify][Exam] USUNIETO zadanie (final_answer={fa_status}): '{tresc[:60]}...'")
                log_final_answer_mismatch_diagnostic("[MathVerify][Exam]", data.get("tytul", ""), tresc, opcje, pyt.get("final_answer"), fa_status)
                if metrics:
                    metrics.record_rejection("final_answer_no_match")
                continue
            new_letter = _IDX_TO_LETTER.get(fa_idx)
            if new_letter and pyt.get("odpowiedz") != new_letter:
                pyt["odpowiedz"] = new_letter

            # WARSTWA 2: niezalezna weryfikacja sympy tam, gdzie rozpoznajemy wzorzec
            try:
                result = verify_and_fix_math_question(tresc, opcje)
            except Exception as e:
                print(f"[MathVerify][Exam] blad weryfikacji sympy: {e}")
                kept.append(pyt)
                continue
            if result["status"] == "unverifiable":
                log_unverifiable_diagnostic("[MathVerify][Exam]", data.get("tytul", ""), tresc, opcje, pyt.get("final_answer"))
                kept.append(pyt)
            elif result["status"] == "match_index":
                true_idx = result["true_index"]
                current_idx = _LETTER_TO_IDX.get(str(pyt.get("odpowiedz", "")).strip().lower())
                if current_idx != true_idx:
                    true_letter = _IDX_TO_LETTER.get(true_idx)
                    if true_letter:
                        print(f"[MathVerify][Exam] POPRAWIONO odpowiedz (sympy nie zgadza sie z final_answer): '{tresc[:60]}...' {pyt.get('odpowiedz')} -> {true_letter}")
                        pyt["odpowiedz"] = true_letter
                        if result.get("explanation"):
                            pyt["wyjasnienie"] = result["explanation"]
                kept.append(pyt)
            elif result["status"] == "no_option_matches":
                print(f"[MathVerify][Exam] USUNIETO zadanie (sympy: brak poprawnej opcji wsrod podanych): '{tresc[:60]}...'")
                log_no_option_matches_diagnostic("[MathVerify][Exam]", data.get("tytul", ""), tresc, opcje, pyt.get("final_answer"))
                if metrics:
                    metrics.record_rejection("sympy_mismatch")
            else:
                kept.append(pyt)

        # WARSTWA 3: walidacja skali trudnosci (rownania kwadratowe skala
        # 1-10, ETAP 6: ciagi arytmetyczne/geometryczne skala 1-5) -
        # topic-agnostyczne, kazdy zarejestrowany domain modifier sam
        # rozpoznaje, czy dotyczy danego pytania.
        if trudnosc:
            _difficulty_timer = _Timer(metrics, "difficulty_time") if metrics else None
            if _difficulty_timer:
                _difficulty_timer.__enter__()
            kept2 = []
            for pyt in kept:
                tresc = pyt.get("tresc", "")
                try:
                    score = _difficulty_analyzer.analyze(
                        tresc, option_texts=pyt.get("opcje", []), requested_difficulty_word=trudnosc, level=level,
                    )
                    diff_result = score.domain_detail or {"status": "not_quadratic"}
                except Exception as e:
                    print(f"[MathVerify][Exam][Difficulty] blad walidacji trudnosci: {e}")
                    kept2.append(pyt)
                    continue
                if diff_result["status"] == "fail":
                    print(
                        f"[MathVerify][Exam][Difficulty] FAIL: '{tresc[:60]}...' "
                        f"REASON={diff_result['reason']} "
                        f"REQUESTED_TIER={diff_result['requested_tier']} "
                        f"DETECTED_TIER={diff_result['detected_tier']}"
                    )
                    if metrics:
                        metrics.record_rejection("difficulty_fail")
                    continue
                kept2.append(pyt)
            kept = kept2
            if _difficulty_timer:
                _difficulty_timer.__exit__(None, None, None)

        # DEDUPLIKACJA (ETAP 3) - patrz docstring wyzej.
        if seen_fingerprints is not None:
            deduped = []
            for pyt in kept:
                fp = _question_fingerprint(pyt.get("tresc", ""))
                if fp in seen_fingerprints:
                    print(f"[MathVerify][Exam][Dedup] USUNIETO duplikat: '{pyt.get('tresc', '')[:60]}...'")
                    if metrics:
                        metrics.record_rejection("duplicate")
                    continue
                seen_fingerprints.add(fp)
                deduped.append(pyt)
            kept = deduped

        # UNIVERSAL DIVERSITY ENGINE (PORT z Quizu, audyt Sprawdzian V1,
        # sierpien 2026) - identyczny mechanizm co openai_exam.py
        # _verify_and_fix_quiz_math (patrz tam pelne uzasadnienie): wyzszy
        # poziom abstrakcji niz dedup wyzej - dedup lapie IDENTYCZNY
        # tekst, to sprawdza, czy dwa zadania maja TEN SAM SCHEMAT/TYP
        # ROZUMOWANIA (AI samo opisuje kazde zadanie 4-polowym tagiem
        # "diversity_tag" w promptcie). Zadania oznaczone prywatnym
        # kluczem "_safe_generated" (patrz Safe Parameter Generation
        # nizej) sa WYLACZONE z tej kontroli - celowo generujemy tam
        # wiele zadan tego samego podwzorca, zeby niezawodnie osiagnac
        # N==N dla najtrudniejszego przypadku.
        if seen_diversity_tags is not None:
            diverse = []
            for pyt in kept:
                if pyt.pop("_safe_generated", False):
                    diverse.append(pyt)
                    continue
                too_similar, tokens = is_too_similar_diversity_tag(pyt.get("diversity_tag"), seen_diversity_tags)
                if too_similar:
                    print(f"[MathVerify][Exam][Diversity] USUNIETO - zbyt podobny schemat do juz zaakceptowanego zadania: '{pyt.get('tresc', '')[:60]}...' tag={pyt.get('diversity_tag')}")
                    if metrics:
                        metrics.record_rejection("diversity_too_similar")
                    continue
                if tokens:
                    seen_diversity_tags.append(tokens)
                diverse.append(pyt)
            kept = diverse

        # LOSOWANIE POZYCJI POPRAWNEJ ODPOWIEDZI - PO wszystkich warstwach
        # weryfikacji (1/2/3), identycznie jak w Quizie (patrz
        # openai_exam._verify_and_fix_quiz_math). relabel_prefix=True, bo
        # "opcje" w Sprawdzianie czesto maja etykiete "a) "/"b) "
        # zapisana W SAMYM TEKSCIE (PDF nie ma frontu, ktory dorysuje
        # etykiete z pozycji) - shuffle_options_preserving_correct
        # usuwa stara i doklada nowa, zgodna z pozycja po przetasowaniu.
        for pyt in kept:
            opcje = pyt.get("opcje")
            current_idx = _LETTER_TO_IDX.get(str(pyt.get("odpowiedz", "")).strip().lower())
            if isinstance(opcje, list) and current_idx is not None:
                new_opcje, new_idx = shuffle_options_preserving_correct(opcje, current_idx, relabel_prefix=True)
                new_letter = _IDX_TO_LETTER.get(new_idx)
                if new_letter:
                    pyt["opcje"] = new_opcje
                    pyt["odpowiedz"] = new_letter

        sekcja["pytania"] = kept

    if _validation_timer:
        _validation_timer.__exit__(None, None, None)

    # Renumeracja "nr" SEKWENCYJNIE przez wszystkie sekcje (zamkniete +
    # otwarte razem) - usuniecie zadania z sekcji zamknietej nie moze
    # zostawic dziury/nakladki w numeracji dla sekcji otwartej po niej.
    nr = 1
    for sekcja in data.get("sekcje", []):
        for pyt in sekcja.get("pytania", []):
            pyt["nr"] = nr
            nr += 1
    return data


# ============================================================
# GŁÓWNA KLASA
# ============================================================
class ExamGenerator:
    def __init__(self, openai_api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=openai_api_key)

    def _fix_json(self, raw: str) -> str:
        """Naprawia JSON z GPT — backslashe, literalne newliny.

        NAPRAWIONE (audyt Sprawdzian V1, sierpien 2026): ta metoda miala
        WLASNA, zduplikowana kopie DOKLADNIE tego samego algorytmu co
        sanitize_latex_json_backslashes w openai_exam.py (Quiz) - ta sama
        dwuetapowa logika (regex per-komenda + skan znak-po-znaku), ale
        z KROTSZA, nieaktualna lista chronionych komend (brak np.
        "textbackslash", "mathbb", "underbrace" - dokladnie ta sama luka,
        ktora zostala znaleziona i naprawiona w Quizie tego samego dnia -
        patrz komentarz w openai_exam.py _LATEX_CMDS_AT_RISK). Zamiast
        utrzymywac DWIE, rozjezdzajace sie kopie tej samej logiki,
        wolamy TERAZ bezposrednio wspoldzielona, w pelni zaktualizowana
        funkcje - jedno miejsce prawdy dla obu (Quiz i Sprawdzian)."""
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        raw = raw.strip()
        # ZACHOWANE z oryginalnej wersji (NIE robi tego
        # sanitize_latex_json_backslashes - tam niepotrzebne, bo Quiz
        # uzywa response_format=json_object, ktory GWARANTUJE poprawny
        # JSON): to wywolanie AI (ponizej) NIE uzywa json_object mode,
        # wiec GPT czasem zwraca SUROWE znaki nowej linii/tabulacji
        # wewnatrz wartosci stringow - to NIEPOPRAWNY JSON (json.loads
        # odrzuca surowe znaki kontrolne w stringach). Escapujemy je
        # PRZED wspoldzielonym sanitizerem ponizej.
        result, in_str = [], False
        for c in raw:
            if c == '"':
                in_str = not in_str
                result.append(c)
            elif in_str and c == '\n':
                result.append('\\n')
            elif in_str and c == '\t':
                result.append('\\t')
            elif in_str and c == '\r':
                continue
            else:
                result.append(c)
        raw = ''.join(result)
        return sanitize_latex_json_backslashes(raw)

    def _get_exam_data_raw(self, temat, klasa, trudnosc, liczba_pytan, wlasne_instrukcje=None, przedmiot=None) -> dict:
        """Jedno 'surowe' wywolanie AI (bez weryfikacji sympy) - wydzielone
        z _get_exam_data, zeby dogenerowywanie brakujacych zadan (patrz
        _fill_missing_exam_questions) moglo to wywolywac wielokrotnie bez
        rekurencyjnego uruchamiania calego cyklu weryfikacja+uzupelnianie."""
        temat_low = temat.lower()
        przedmiot_low = (przedmiot or '').lower()

        # Wykryj typ zadań na podstawie tematu i przedmiotu
        ZAWSZE_OBLICZENIA = ['matematyka', 'fizyka', 'chemia']
        SLOWA_OBLICZENIOWE = [
            'oblicz', 'procent', 'predkosc', 'stezenie', 'masa', 'cisnienie',
            'temperatura', 'energia', 'wydajnosc', 'wzrost', 'przyrost',
            'odleglosc', 'sila', 'moc', 'napiecie', 'gestosc', 'objetosc',
            'pole', 'obwod', 'calka', 'pochodna', 'rownanie', 'logarytm',
            'ulamek', 'funkcja', 'wskaznik', 'bilans'
        ]
        SLOWA_BEZ_OBLICZEN = [
            'gramatyka', 'slownictwo', 'grammar', 'czasy', 'reading',
            'wypracowanie', 'esej', 'lektura', 'literatura', 'epoka',
            'autor', 'bohater', 'bitwa', 'data', 'wydarzenie', 'postac',
            'chronologia', 'definicja', 'pojecie', 'grzyby', 'rosliny',
            'zwierzeta', 'ekologia', 'ewolucja', 'komorka', 'tkanki',
            'fotosynteza', 'bakterie', 'wirusy', 'mitoza', 'mejoza'
        ]

        ma_obliczenia = any(s in temat_low for s in SLOWA_OBLICZENIOWE)
        bez_obliczen = any(s in temat_low for s in SLOWA_BEZ_OBLICZEN)
        zawsze = any(p in przedmiot_low for p in ZAWSZE_OBLICZENIA)

        if ma_obliczenia or (zawsze and not bez_obliczen):
            typ_instrukcja = "Ten temat wymaga zadan obliczeniowych — dodaj Czesc B z zadaniami obliczeniowymi i wzorami."
        else:
            typ_instrukcja = """WAZNE: Ten temat NIE wymaga zadan obliczeniowych matematycznych.
Czesc B powinna zawierac zadania OTWARTE OPISOWE:
- pytania na opis i wyjasnienie zjawisk
- zadania na analize i interpretacje
- pytania definicyjne i problemowe
ZAKAZ: rownania matematyczne, obliczenia liczbowe, wzory fizyczne/chemiczne w Czesci B."""

        if wlasne_instrukcje and wlasne_instrukcje.strip():
            instr = wlasne_instrukcje.strip()
            only_closed = any(x in instr.upper() for x in ['TYLKO', 'ZAMKNIETYCH', 'NIE DODAWAJ CZESCI B', 'SPRAWDZIAN MA MIEC'])
            if only_closed:
                blok = f"""KRYTYCZNE NAKAZY — BEZWZGLEDNE:
{instr}
STRUKTURA: TYLKO sekcja A (zamkniete). ZAKAZ sekcji B. ZAKAZ zadan otwartych.
LICZBA PYTAN = {liczba_pytan}. Ani wiecej, ani mniej."""
            else:
                blok = f"{typ_instrukcja}\nNAUCZYCIEL CHCE: {instr}\nMUSISZ to uwzglednic w sprawdzianie."
        else:
            blok = typ_instrukcja

        # "gated injection" skali trudnosci - rownania kwadratowe (1-10),
        # ETAP 6: ciagi arytmetyczne/geometryczne (1-5), ETAP 7: trygonometria
        # (1-5), ten sam mechanizm co w Quizie (patrz openai_exam.py). Inne
        # tematy dzialaja jak dotychczas (samo slowo trudnosci).
        difficulty_anchor_blok = ""
        if is_quadratic_equation_topic(temat):
            anchor_text = get_quadratic_difficulty_anchor(trudnosc)
            if anchor_text:
                difficulty_anchor_blok = f"\n{anchor_text}\n"
        elif is_sequence_topic(temat):
            anchor_text = get_sequence_difficulty_anchor(trudnosc)
            if anchor_text:
                difficulty_anchor_blok = f"\n{anchor_text}\n"
        elif is_trigonometry_topic(temat):
            anchor_text = get_trig_difficulty_anchor(trudnosc)
            if anchor_text:
                difficulty_anchor_blok = f"\n{anchor_text}\n"
        elif is_linear_function_topic(temat):
            anchor_text = get_linear_function_difficulty_anchor(trudnosc)
            if anchor_text:
                difficulty_anchor_blok = f"\n{anchor_text}\n"
        elif is_quadratic_function_topic(temat):
            anchor_text = get_quadratic_function_difficulty_anchor(trudnosc)
            if anchor_text:
                difficulty_anchor_blok = f"\n{anchor_text}\n"
        elif is_exponential_function_topic(temat):
            anchor_text = get_exponential_function_difficulty_anchor(trudnosc)
            if anchor_text:
                difficulty_anchor_blok = f"\n{anchor_text}\n"

        prompt = EXAM_PROMPT.format(
            temat=temat, klasa=klasa, poziom_opis=describe_level(klasa, subject=przedmiot),
            trudnosc=trudnosc, liczba_pytan=liczba_pytan,
            difficulty_anchor_blok=difficulty_anchor_blok,
            wlasne_instrukcje_blok=blok
        )
        last_error = None
        for attempt in range(2):
            try:
                r = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content":
                            "Jestes nauczycielem tworzacym sprawdziany. "
                            "Odpowiadasz TYLKO czystym JSON. Zero backticks. "
                            "KRYTYCZNE: poziom trudnosci MUSI byc scisle przestrzegany. "
                            "Znaki nowej linii w stringach jako \\n."},
                        {"role": "user", "content": prompt}
                    ],
                    # Skalujemy z liczba_pytan - stala wartosc byla
                    # ryzykowna po dodaniu bufora (_buffered_question_count
                    # moze prosic o 20+ zadan naraz), analogicznie do fixa w
                    # openai_exam.py (ucinanie odpowiedzi psulo caly JSON).
                    temperature=0.5, max_tokens=min(10000, max(5500, 600 * liczba_pytan)),
                )
                raw = r.choices[0].message.content.strip()
                raw = self._fix_json(raw)
                try:
                    data = json.loads(raw)
                except:
                    m = re.search(r'\{.*\}', raw, re.DOTALL)
                    data = json.loads(m.group(0)) if m else {}
                if data.get('sekcje'):
                    return _fix_latex_in_exam_data(data)
                last_error = ValueError("AI zwrocilo pusty sprawdzian (brak sekcji z pytaniami)")
            except Exception as e:
                last_error = e
        print(f"[ExamGen] Nie udalo sie wygenerowac po 2 probach: {last_error}")
        return {}

    def _get_exam_data_raw_parallel(self, temat, klasa, trudnosc, total_n, wlasne_instrukcje=None, przedmiot=None) -> dict:
        """Jak _get_exam_data_raw, ale dla wiekszych `total_n` dzieli
        zadanie na kilka mniejszych, ROWNOLEGLYCH wywolan AI (PORT z
        Quizu - _raw_generate_quiz_topic_batch w openai_exam.py, ta sama
        _parallel_batch_sizes). ExamGenerator jest SYNCHRONICZNY
        (self.client = OpenAI(...), nie AsyncOpenAI) - rownoleglosc idzie
        wiec przez ThreadPoolExecutor (prawdziwa rownoleglosc siecowa dla
        I/O-bound wywolan, ten sam efekt co asyncio.gather w Quizie,
        inny mechanizm dopasowany do synchronicznej architektury tej
        klasy). Dla malych `total_n` (<= target_chunk) zachowanie jest
        DOKLADNIE identyczne jak bezposrednie wywolanie
        _get_exam_data_raw (jeden request, bez zadnej zmiany)."""
        sizes = _parallel_batch_sizes(total_n)
        if len(sizes) == 1:
            return self._get_exam_data_raw(temat, klasa, trudnosc, sizes[0], wlasne_instrukcje, przedmiot)
        print(f"[MathVerify][Exam] rownolegle generowanie: {total_n} zadan podzielone na {len(sizes)} wywolan {sizes}")
        with _cf.ThreadPoolExecutor(max_workers=len(sizes)) as ex:
            futures = [
                ex.submit(self._get_exam_data_raw, temat, klasa, trudnosc, size, wlasne_instrukcje, przedmiot)
                for size in sizes
            ]
            results = [f.result() for f in futures]
        return _merge_exam_data_chunks(results)

    # SAFE PARAMETER GENERATION (PORT z Quizu, audyt Sprawdzian V1,
    # sierpien 2026) - dla JEDNEGO, potwierdzonego (w Quizie) najtrudniejszego
    # podwzorca (rownanie x^2+mx+C=0, parametr jako goly wspolczynnik
    # liniowy, medium): odwrocenie kolejnosci wzgledem reszty systemu.
    # KOD (nie AI) wybiera C jako kwadrat idealny (gwarantuje wymierna,
    # calkowita granice 2*sqrt(C)) i liczy PRAWDZIWY warunek PRZEZ
    # ISTNIEJACY build_safe_linear_param_quadratic (math_verify.py - ta
    # sama funkcja co w Quizie, zero duplikacji logiki matematycznej). AI
    # dostaje gotowy, JUZ POPRAWNY wynik - jej jedyne zadanie to jezykowe
    # sformulowanie pytania + 3 blednych dystraktorow. Warstwa 2
    # (_verify_and_fix_exam_math) NADAL robi koncowa weryfikacje jako
    # dodatkowe zabezpieczenie - ten kod NIE omija Warstwy 2.
    def _raw_generate_safe_linear_param_quadratic_batch(self, n: int, klasa: str = None, used_letters: set = None, used_constants: set = None) -> dict:
        """Generuje `n` zadan zamknietych dla podwzorca x^2+mx+C=0
        (parametr jako goly wspolczynnik liniowy) metoda 'safe parameter
        generation' - zwraca dane w KSZTALCIE sprawdzianu (sekcje/
        pytania/opcje z prefiksem litery/odpowiedz jako litera), zeby
        pasowalo bez zmian do _fill_missing_exam_questions.

        `used_letters`/`used_constants` (opcjonalne, patrz _get_exam_data)
        - jesli podane, zyja przez CALY dokument (pierwsza partia + WSZYSTKIE
        rundy dogenerowania) i sa mutowane w miejscu, zeby ZADNA litera/stala
        nie powtorzyla sie w obrebie tego samego sprawdzianu, dopoki starcza
        unikalnych wartosci w puli (10/10) - patrz pick_safe_param_values w
        math_verify.py. User zglosil realny przypadek (Pytanie 6 i 7 w
        jednym PDF, oba $x^2+_x+25=0$, rozne tylko litery) - bez tego
        mechanizmu KAZDE osobne wywolanie tej metody (np. pierwsza partia
        vs runda dogenerowania) losowalo stala NIEZALEZNIE, wiec kolizja
        MIEDZY wywolaniami byla mozliwa nawet gdy litery w OBREBIE jednego
        wywolania juz nie powtarzaly sie."""
        # Bufor +3 (identyczny wzorzec co w Quizie) - pojedyncza, rzadka
        # kolizja fingerprintu miedzy rundami nie kosztuje calej brakujacej
        # partii.
        buffered_n = n + 3
        letters_pool = list("mnpqrstkbc")
        squares_pool = [1, 4, 9, 16, 25, 36, 49, 64, 81, 100]
        if used_letters is not None and used_constants is not None:
            letters = pick_safe_param_values(letters_pool, used_letters, buffered_n)
            constants = pick_safe_param_values(squares_pool, used_constants, buffered_n)
        else:
            random.shuffle(letters_pool)
            letters = [letters_pool[i % len(letters_pool)] for i in range(buffered_n)]
            constants = [random.choice(squares_pool) for _ in range(buffered_n)]
        skeletons = [
            build_safe_linear_param_quadratic(
                param_letter=letters[i],
                c_value=constants[i],
            )
            for i in range(buffered_n)
        ]
        items_desc = "\n".join(
            f"{i + 1}. Rownanie: $x^2 + {sk['param_letter']}x + {sk['c_value']} = 0$. "
            f"POPRAWNY, JUZ OBLICZONY warunek na dwa rozne pierwiastki (NIE PRZELICZAJ, NIE ZMIENIAJ): "
            f"{sk['correct_text']}"
            for i, sk in enumerate(skeletons)
        )
        prompt = f"""Dla KAZDEGO z {len(skeletons)} ponizszych rownan kwadratowych z parametrem,
poprawny warunek na DWA ROZNE PIERWIASTKI zostal JUZ OBLICZONY (przez
niezalezny system matematyczny) - Twoje jedyne zadania to:
1. Sformulowac naturalne, poprawne pytanie po polsku o podane rownanie.
2. Wymyslic 3 SENSOWNE, ale MATEMATYCZNIE BLEDNE dystraktory (inne
   liczby/znaki, realistyczne, ale niepoprawne) - NIE kopiuj poprawnej
   wartosci do dystraktorow.
3. Napisac krotkie wyjasnienie (1-2 zdania) odwolujace sie do wzoru na
   delte.
4. Podac diversity_tag (skill/concept/task_type/reasoning, krotkie
   frazy) - dla WSZYSTKICH tych zadan concept to zawsze "parametr jako
   wspolczynnik liniowy" (to jest ten sam podwzorzec, celowo).

KRYTYCZNE: NIE PRZELICZAJ podanego warunku od nowa i NIE ZMIENIAJ go w
zadnym stopniu - jest juz zweryfikowany przez niezalezny system. Twoja
rola to TYLKO jezyk i dystraktory, nie matematyka.

{items_desc}

FORMAT (TYLKO JSON):
{{
    "sekcje": [
        {{
            "typ": "zamkniete",
            "pytania": [
                {{
                    "nr": 1,
                    "tresc": "Dla jakich wartości parametru m równanie $x^2 + mx + 16 = 0$ ma dwa różne pierwiastki?",
                    "opcje": ["a) $m < -8$ lub $m > 8$", "b) $m < -4$ lub $m > 4$", "c) $m = 8$", "d) $m < 8$"],
                    "odpowiedz": "a",
                    "final_answer": "$m < -8$ lub $m > 8$",
                    "punkty": 1,
                    "wyjasnienie": "Delta rownania to $m^2-64$, warunek $\\Delta>0$ daje $m<-8$ lub $m>8$.",
                    "diversity_tag": {{
                        "skill": "wzor na delte", "concept": "parametr jako wspolczynnik liniowy",
                        "task_type": "wyznacz parametr z warunku na delte",
                        "reasoning": "oblicz delte, rozwiaz nierownosc, zapisz przedzial"
                    }}
                }}
            ]
        }}
    ]
}}

ZASADY:
- Dokladnie {len(skeletons)} zadan, po jednym na kazde podane rownanie, w tej samej kolejnosci
- "opcje" ZAWSZE z prefiksem litery ("a) ", "b) ", "c) ", "d) ")
- "final_answer" MUSI byc DOSLOWNA kopia podanego poprawnego warunku, BEZ prefiksu litery
- "odpowiedz" = litera (a/b/c/d) poprawnej opcji (dowolna pozycja, urozmaicaj)
- Po polsku
- TYLKO JSON"""

        try:
            r = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content":
                        "Jestes nauczycielem tworzacym sprawdziany. "
                        "Odpowiadasz TYLKO czystym JSON. Zero backticks."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7, max_tokens=min(8000, max(2500, 400 + len(skeletons) * 300)),
            )
            raw = r.choices[0].message.content.strip()
            raw = self._fix_json(raw)
            try:
                data = json.loads(raw)
            except Exception:
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                data = json.loads(m.group(0)) if m else {}
        except Exception as e:
            print(f"[MathVerify][Exam] blad Safe Parameter Generation: {e}")
            return {}
        data = _fix_latex_in_exam_data(data)
        for sekcja in data.get("sekcje", []):
            for pyt in sekcja.get("pytania", []):
                pyt["_safe_generated"] = True
        return data

    def _get_exam_data(self, temat, klasa, trudnosc, liczba_pytan, wlasne_instrukcje=None, przedmiot=None) -> dict:
        # NAPRAWIONE: pierwsze wywolanie prosi o troche WIECEJ zadan niz
        # zamowiono (patrz _buffered_question_count) - empirycznie
        # wieksze partie maja wyzszy odsetek przechodzacy weryfikacje
        # sympy niz partie 1-2-zadaniowe, wiec to zmniejsza szanse na
        # koniecznosc wielu rund dogenerowania.
        # ETAP 4: GenerationMetrics tworzone tutaj (jedyne miejsce, ktore
        # zna batch_size PRZED pierwszym wywolaniem AI) - patrz identyczny
        # wzorzec w openai_exam.py _generate_quiz_topic_once.
        from .metrics import GenerationMetrics, _Timer
        t_start = time.monotonic()
        batch_size = _buffered_question_count(liczba_pytan, temat=temat, trudnosc=trudnosc)
        metrics = GenerationMetrics(requested_count=liczba_pytan, batch_size=batch_size)
        with _Timer(metrics, "generation_time"):
            # PORT z Quizu: dla wiekszych partii (batch_size > target_chunk)
            # dzielimy na rownolegle wywolania AI (ThreadPoolExecutor, bo
            # ExamGenerator.client jest SYNCHRONICZNY - w przeciwienstwie do
            # AsyncOpenAI w Quizie) - skraca czas oczekiwania proporcjonalnie.
            data = self._get_exam_data_raw_parallel(temat, klasa, trudnosc, batch_size, wlasne_instrukcje, przedmiot)
        metrics.api_request_count += 1
        metrics.generated_count += sum(len(s.get('pytania', [])) for s in data.get('sekcje', []))
        if not data.get('sekcje'):
            metrics.record_rejection("json_crash")
            metrics.total_time = time.monotonic() - t_start
            metrics.log("[GenerationMetrics][Exam]")
            return data
        # ETAP 3: seen_fingerprints zyje przez CALY proces (ta partia +
        # wszystkie rundy dogenerowania) - patrz openai_exam.py rownowazny
        # mechanizm dla Quizu.
        seen_fingerprints = set()
        seen_diversity_tags = []
        # Zyje przez CALY dokument (patrz docstring _raw_generate_safe_linear_param_quadratic_batch)
        # - zapobiega powtorzeniu tej samej litery/stalej C miedzy roznymi
        # wywolaniami metody bezpiecznej generacji w OBREBIE tego samego
        # sprawdzianu (user zglosil realny przypadek dwoch pytan z ta sama
        # stala C=25, roznymi tylko literami).
        used_safe_letters = set()
        used_safe_constants = set()
        data = _verify_and_fix_exam_math(data, trudnosc=trudnosc, seen_fingerprints=seen_fingerprints, metrics=metrics, level=klasa, seen_diversity_tags=seen_diversity_tags)
        data = self._fill_missing_exam_questions(data, temat, klasa, trudnosc, liczba_pytan, wlasne_instrukcje, przedmiot, t_start=t_start, seen_fingerprints=seen_fingerprints, metrics=metrics, seen_diversity_tags=seen_diversity_tags, used_safe_letters=used_safe_letters, used_safe_constants=used_safe_constants)
        return data

    def _fill_missing_exam_questions(self, data, temat, klasa, trudnosc, liczba_pytan, wlasne_instrukcje, przedmiot, max_rounds=10, t_start=None, seen_fingerprints=None, metrics=None, seen_diversity_tags=None, used_safe_letters=None, used_safe_constants=None):
        """STANDARD ARCHITEKTONICZNY (patrz komentarz nad SAFE PARAMETER
        GENERATION w math_verify.py): `current_total`/`missing` ponizej sa
        liczone WYLACZNIE przez len() na faktycznie zaakceptowanej liscie
        sekcji/pytan - kod, nie AI, jest zrodlem prawdy ile juz mamy i ile
        dogenerowac. Identyczny wzorzec co _verify_and_fill_quiz_math w
        openai_exam.py (Quiz).

        Gdy weryfikacja sympy usunela zadania (bledny klucz bez
        poprawki wsrod opcji), dogenerowuje ZAMKNIETE zadania na ten sam
        temat/poziom, zeby finalna liczba pytan ZAWSZE zgadzala sie z
        `liczba_pytan` zamowiona przez usera - kompletnosc i poprawnosc
        sa wazniejsze niz szybkosc. Max `max_rounds` (10) LUB `max_seconds`
        (30s, liczone od POCZATKU pierwszego buforowanego wywolania AI w
        _get_exam_data - `t_start` przekazywany stamtad, zeby limit
        obejmowal caly proces generowania, nie tylko rundy uzupelniajace)
        - bezpieczniki: user nigdy nie powinien czekac bez konca, nawet
        dla ekstremalnie uporczywego tematu (w praktyce bardzo rzadkie).

        ETAP 4: `metrics` (GenerationMetrics, patrz _get_exam_data - tworzone
        tam, bo tylko tamten caller zna batch_size PRZED pierwszym
        wywolaniem AI) jest tu koncowym punktem - loguje finalna linie JSON
        z accepted_count/total_time. Jesli caller nie poda `metrics`,
        tworzymy lokalna, jednorazowa instancje (zero zmiany zachowania)."""
        from .metrics import GenerationMetrics, _Timer
        if metrics is None:
            metrics = GenerationMetrics(requested_count=liczba_pytan)
        max_seconds = _max_generation_seconds_exam(temat, trudnosc)
        if t_start is None:
            t_start = time.monotonic()
        for round_i in range(1, max_rounds + 1):
            current_total = sum(len(s.get('pytania', [])) for s in data.get('sekcje', []))
            missing = liczba_pytan - current_total
            if missing <= 0:
                break
            elapsed = time.monotonic() - t_start
            if elapsed >= max_seconds:
                print(f"[MathVerify][Exam] przekroczono limit czasu ({elapsed:.1f}s >= {max_seconds}s) - przerywam dogenerowanie")
                break
            print(f"[MathVerify][Exam] brakuje {missing} zadan po weryfikacji (runda {round_i}/{max_rounds}, {elapsed:.1f}s) - dogenerowuje...")
            metrics.retry_count += 1
            try:
                with _Timer(metrics, "generation_time"):
                    # PORT z Quizu: dla TEGO JEDNEGO, potwierdzonego trudnego
                    # tematu/trudnosci, rundy dogenerowania uzywaja metody z
                    # gotowym, poprawnym wynikiem zamiast kolejnej proby
                    # wolnej generacji, ktora regularnie zawodzi wlasnie dla
                    # tego przypadku (stad w ogole te rundy sa potrzebne).
                    if _is_medium_linear_param_quadratic_exam(temat, trudnosc):
                        extra = self._raw_generate_safe_linear_param_quadratic_batch(max(missing, _MIN_FILL_BATCH_EXAM), klasa, used_letters=used_safe_letters, used_constants=used_safe_constants)
                    else:
                        extra = self._get_exam_data_raw_parallel(temat, klasa, trudnosc, max(missing, _MIN_FILL_BATCH_EXAM), wlasne_instrukcje, przedmiot)
                metrics.api_request_count += 1
                metrics.generated_count += sum(len(s.get('pytania', [])) for s in (extra or {}).get('sekcje', []))
            except Exception as e:
                print(f"[MathVerify][Exam] blad dogenerowania: {e}")
                metrics.record_rejection("json_crash")
                continue
            if not extra or not extra.get('sekcje'):
                metrics.record_rejection("json_crash")
                continue
            extra = _verify_and_fix_exam_math(extra, trudnosc=trudnosc, seen_fingerprints=seen_fingerprints, metrics=metrics, level=klasa, seen_diversity_tags=seen_diversity_tags)
            extra_closed = []
            for s in extra.get('sekcje', []):
                if s.get('typ') == 'zamkniete':
                    extra_closed.extend(s.get('pytania', []))
            if not extra_closed:
                continue
            target = next((s for s in data['sekcje'] if s.get('typ') == 'zamkniete'), None)
            if target is None:
                target = {
                    "nazwa": "Czesc A — Zadania zamkniete", "typ": "zamkniete",
                    "instrukcja_sekcji": "Zaznacz poprawna odpowiedz (a, b, c lub d). Za kazde poprawne: 1 pkt.",
                    "pytania": [],
                }
                data.setdefault('sekcje', []).insert(0, target)
            target['pytania'].extend(extra_closed)

        # Przytnij, jesli po dogenerowaniu wyszlo za duzo (rundy licza
        # brakujace zadania niezaleznie, wiec drobny nadmiar jest mozliwy).
        total = sum(len(s.get('pytania', [])) for s in data.get('sekcje', []))
        overflow = total - liczba_pytan
        if overflow > 0:
            for s in reversed(data.get('sekcje', [])):
                while overflow > 0 and s.get('pytania'):
                    s['pytania'].pop()
                    overflow -= 1
                if overflow <= 0:
                    break

        nr = 1
        for s in data.get('sekcje', []):
            for pyt in s.get('pytania', []):
                pyt['nr'] = nr
                nr += 1

        final_total = sum(len(s.get('pytania', [])) for s in data.get('sekcje', []))
        if final_total < liczba_pytan:
            total_elapsed = time.monotonic() - t_start
            reason = "przekroczono limit czasu (30s)" if total_elapsed >= max_seconds else f"wyczerpano {max_rounds} prob dogenerowania"
            data["_shortfall_warning"] = (
                f"Udalo sie wygenerowac i zweryfikowac {final_total} z {liczba_pytan} "
                f"zamowionych zadan - {reason}, pozostale okazaly sie bledne. "
                f"Sprobuj ponownie albo zmien temat/trudnosc."
            )
            print(f"[MathVerify][Exam] SHORTFALL: {final_total}/{liczba_pytan} po {total_elapsed:.1f}s ({reason})")

        metrics.accepted_count = final_total
        metrics.total_time = time.monotonic() - t_start
        metrics.log("[GenerationMetrics][Exam]")

        return data

    def generate_exam(self, temat: str, klasa: str = "liceum",
                      trudnosc: str = "srednia", liczba_pytan: int = 12,
                      wariant: str = "A", wlasne_instrukcje: str = None,
                      przedmiot: str = None):
        """Zwraca (fname, shortfall_info). shortfall_info jest None, jesli
        wygenerowano pelna zamowiona liczbe zadan - w przeciwnym razie dict
        {"message", "requested_count", "accepted_count"} (ETAP 2, Punkt 2 -
        patrz identyczny mechanizm w quiz_api.py _shortfall_response).
        PDF jest budowany normalnie w OBU przypadkach (data["_shortfall_warning"]
        nie blokuje generowania pliku) - to wywolujacy kod (exam_api.py)
        decyduje, czy mimo shortfallu i tak oddac PDF, czy zwrocic blad."""
        print(f"[ExamGen] Generuję: '{temat}' | {klasa} | {trudnosc} | Wariant {wariant}")
        # Wyciągnij przedmiot z tematu jeśli format "Przedmiot: Temat"
        if not przedmiot and ':' in temat:
            przedmiot = temat.split(':')[0].strip()
        data = self._get_exam_data(temat, klasa, trudnosc, liczba_pytan, wlasne_instrukcje, przedmiot)
        if not data:
            raise ValueError("GPT nie zwrócił poprawnych danych")
        shortfall_info = None
        shortfall_message = data.get("_shortfall_warning")
        if shortfall_message:
            accepted = sum(len(s.get("pytania", [])) for s in data.get("sekcje", []))
            shortfall_info = {
                "message": shortfall_message,
                "requested_count": liczba_pytan,
                "accepted_count": accepted,
            }
        data['wariant'] = wariant
        print(f"[ExamGen] Sprawdzian: '{data.get('tytul','?')}'")

        # Okładka
        cover_buf = io.BytesIO()
        from reportlab.pdfgen import canvas as rl_canvas
        c = rl_canvas.Canvas(cover_buf, pagesize=A4)
        _draw_exam_cover(c, data, wariant=wariant)
        c.save(); cover_buf.seek(0)

        # Strony z pytaniami + klucz
        pages_bytes = _build_exam_pages(data)

        # Łącz
        writer = PdfWriter()
        for r_pdf in [PdfReader(cover_buf), PdfReader(io.BytesIO(pages_bytes))]:
            for page in r_pdf.pages:
                writer.add_page(page)

        safe = re.sub(r'[^\w]', '_', temat)[:40]
        fname = f"Sprawdzian_{safe}_wariant{wariant}.pdf"
        with open(fname, 'wb') as f:
            writer.write(f)
        print(f"[ExamGen] Plik: {fname}")
        return fname, shortfall_info