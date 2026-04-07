"""
EXAM PDF GENERATOR — Eduvia AI
Generuje profesjonalne sprawdziany PDF z GPT-4o
Na tym samym poziomie co generator notatek.
"""

import io, re, json, os, tempfile, datetime
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
- TEMAT: {temat}
- TRUDNOSC: {trudnosc}
- LICZBA PYTAN: {liczba_pytan}

POZIOM UCZNIA - ZAKRES MATERIALU:
- podstawowka: klasy 4-8, ulamki, procenty, prosta geometria, rowrania liniowe
- liceum: funkcje, rownania kwadratowe, trygonometria, pochodne, logarytmy
- matura: pelny zakres matury, zadania jak w CKE
- studia: matematyka akademicka

TRUDNOSC ZADAN (w ramach poziomu {klasa}):
- latwa: 1 krok, proste obliczenia z danego poziomu
- srednia: 2-3 kroki, typowe zadania z danego poziomu
- trudna: wielokrokowe, najtrudniejsze z danego poziomu

PRZYKLAD POPRAWNY: liceum + trudna = trudne zadania licealne
PRZYKLAD BLEDNY: liceum + trudna = zadania z podstawowki

NAKAZ: Material dostosowany do poziomu {klasa}
NAKAZ: Trudnosc dostosowana do {trudnosc} w ramach {klasa}
ZAKAZ: Zadania z innego poziomu niz {klasa}

TRUDNOSC SZCZEGOLY:
Latwa: proste obliczenia, 1 krok
Srednia: 2-3 kroki, liczby przyjazne
Trudna: wielokrokowe, kombinacja operacji, zadania tekstowe z pulapkami

NAKAZ: KAZDE pytanie odpowiada trudnosci {trudnosc}
ZAKAZ: na trudna dawac pytania z latwa i odwrotnie

WZORY MATEMATYCZNE:
KRYTYCZNE: backslash podwojny w JSON: \\frac, \\sqrt, \\cdot, \\times
KRYTYCZNE: KAZDY wzor w dolarach: $wzor$
ZAKAZ: \\left, \\right, \\displaystyle, \\limits
POPRAWNE: "$\\frac{{a}}{{b}}$", "$x^2 + y^2$", "$\\sqrt{{4}}$"

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
          "punkty": 1,
          "wyjasnienie": "Krotkie wyjasnienie dlaczego b jest poprawne."
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
          "tresc": "Tresc zadania z KONKRETNYMI liczbami. Np: 'Oblicz $\\frac{{3}}{{4}} + \\frac{{2}}{{5}}$. Wynik zapisz w postaci nieskracalnej.'",
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
- sekcja zamknieta: 5-8 pytan po 1-2 pkt
- sekcja otwarta: 3-5 zadan po 3-6 pkt
- lacznie: okolo {liczba_pytan} pytan
- punkty lacznie: 25-35 pkt
- trudnosc rosnaca w obrebie kazdej sekcji
- PO POLSKU, konkretne liczby w zadaniach, nie ogolniki"""

def _fix_latex(tekst: str) -> str:
    """Naprawia brakujące backslashe w LaTeX — prosta zamiana stringiem."""
    if not tekst:
        return tekst
    # Lista komend które GPT gubi backslash przed
    for cmd in ['frac', 'sqrt', 'cdot', 'times', 'div', 'sum', 'int',
                'alpha', 'beta', 'gamma', 'delta', 'pi', 'theta',
                'infty', 'leq', 'geq', 'neq', 'approx', 'pm',
                'left', 'right', 'text', 'mathrm', 'overline']:
        # Zamień " rac{" -> "\frac{" (gdy brak backslasha)
        tekst = tekst.replace(' ' + cmd + '{', ' \\' + cmd + '{')
        tekst = tekst.replace('$' + cmd + '{', '$\\' + cmd + '{')
        tekst = tekst.replace('\n' + cmd + '{', '\n\\' + cmd + '{')
    return tekst


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

# ============================================================
# GŁÓWNA KLASA
# ============================================================
class ExamGenerator:
    def __init__(self, openai_api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=openai_api_key)

    def _fix_json(self, raw: str) -> str:
        """Naprawia JSON z GPT — backslashe, literalne newliny."""
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        raw = raw.strip()

        # KLUCZOWE: napraw komendy LaTeX które JSON traktuje jako escape sequence
        # \frac -> \\frac, \sqrt -> \\sqrt itd. (tylko gdy pojedynczy backslash)
        latex_cmds = ['frac', 'sqrt', 'cdot', 'times', 'div', 'sum', 'int',
                      'left', 'right', 'alpha', 'beta', 'gamma', 'delta',
                      'pi', 'theta', 'infty', 'leq', 'geq', 'neq', 'approx',
                      'pm', 'text', 'mathrm', 'overline', 'over', 'vec',
                      'hat', 'bar', 'dot', 'quad', 'qquad', 'ldots']
        for cmd in latex_cmds:
            # Zamień pojedynczy \cmd na \\cmd (unikaj podwójnego podwojenia)
            raw = re.sub(r'(?<!\\)\\' + cmd + r'\b', r'\\\\' + cmd, raw)

        # Napraw backslashe LaTeX — pozostałe
        B = chr(92)
        result, i, in_str = [], 0, False
        while i < len(raw):
            c = raw[i]
            if not in_str:
                if c == '"': in_str = True
                result.append(c); i += 1; continue
            if c == '"': in_str = False; result.append(c); i += 1; continue
            if c == B:
                nc = raw[i+1] if i+1 < len(raw) else ''
                if nc in (B, '"', 'n', 'r', 't', 'b', 'f', 'u'):
                    result.append(c); result.append(nc); i += 2
                else:
                    result.append(B); result.append(B); i += 1
            elif c == '\n': result.append('\\n'); i += 1
            elif c == '\t': result.append('\\t'); i += 1
            elif c == '\r': i += 1
            else: result.append(c); i += 1
        return ''.join(result)

    def _get_exam_data(self, temat, klasa, trudnosc, liczba_pytan) -> dict:
        prompt = EXAM_PROMPT.format(
            temat=temat, klasa=klasa,
            trudnosc=trudnosc, liczba_pytan=liczba_pytan
        )
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
            temperature=0.5, max_tokens=5500,
        )
        raw = r.choices[0].message.content.strip()
        raw = self._fix_json(raw)
        try:
            return json.loads(raw)
        except:
            try:
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                return json.loads(m.group(0)) if m else {}
            except:
                return {}

    def generate_exam(self, temat: str, klasa: str = "liceum",
                      trudnosc: str = "srednia", liczba_pytan: int = 12,
                      wariant: str = "A") -> str:
        print(f"[ExamGen] Generuję: '{temat}' | {klasa} | {trudnosc} | Wariant {wariant}")
        data = self._get_exam_data(temat, klasa, trudnosc, liczba_pytan)
        if not data:
            raise ValueError("GPT nie zwrócił poprawnych danych")
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
        return fname