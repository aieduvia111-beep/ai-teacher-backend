import sys, subprocess

def _ensure(pkg, import_name=None):
    import_name = import_name or pkg
    try:
        __import__(import_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

_ensure("reportlab")
_ensure("pypdf")
_ensure("matplotlib")
_ensure("Pillow", "PIL")

import os, io, re, json, math
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
# ── POLSKIE ZNAKI W MATPLOTLIB ──────────────────────────────
import matplotlib as _mpl
_mpl.rcParams['font.family'] = 'DejaVu Sans'
_mpl.rcParams['axes.unicode_minus'] = False
# ─────────────────────────────────────────────────────────────

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
from reportlab.platypus.flowables import Flowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas as canvas_module
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfWriter, PdfReader

# ============================================================
# CZCIONKI
# ============================================================
FONT_PATHS = [
    {
        'n': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'b': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        'i': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
        'm': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
        'mb':'/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
    },
    {
        'n': 'C:/Windows/Fonts/arial.ttf',
        'b': 'C:/Windows/Fonts/arialbd.ttf',
        'i': 'C:/Windows/Fonts/ariali.ttf',
        'm': 'C:/Windows/Fonts/cour.ttf',
        'mb':'C:/Windows/Fonts/courbd.ttf',
    },
]

def _reg_fonts():
    for paths in FONT_PATHS:
        if os.path.exists(paths['n']):
            try:
                pdfmetrics.registerFont(TTFont('DJ',  paths['n']))
                pdfmetrics.registerFont(TTFont('DJ-B',paths['b']))
                pdfmetrics.registerFont(TTFont('DJ-I',paths['i']))
                pdfmetrics.registerFont(TTFont('DJ-M',paths['m']))
                pdfmetrics.registerFont(TTFont('DJ-MB',paths['mb']))
                return True
            except: pass
    return False

_OK = _reg_fonts()
FN = 'DJ'    if _OK else 'Helvetica'
FB = 'DJ-B'  if _OK else 'Helvetica-Bold'
FI = 'DJ-I'  if _OK else 'Helvetica-Oblique'
FM = 'DJ-M'  if _OK else 'Courier'
FMB= 'DJ-MB' if _OK else 'Courier-Bold'

# ============================================================
# NOWA PALETA KOLORÓW — Premium Dark
# ============================================================
# Tła
BG_PAGE     = '#FFFFFF'   # Bardzo ciemne tło strony
BG_CARD     = '#F8F7FF'   # Karta/sekcja
BG_CARD2    = '#F0EEFF'   # Alternatywna karta
BG_CODE     = '#F0FFF8'   # Tło kodu/przykładu
BG_ACCENT   = '#F0EEFF'   # Tło z akcentem fioletowym
BG_GREEN    = '#F0FFF8'   # Tło z akcentem zielonym
BG_GOLD     = '#FFFBF0'   # Tło z akcentem złotym
BG_RED      = '#FFF5F5'   # Tło z akcentem czerwonym
BG_BLUE     = '#EBF5FF'   # Tło z akcentem niebieskim

# Akcenty
ACC_PURPLE  = '#6C5CE7'   # Główny fiolet
ACC_CYAN    = '#00B894'   # Zielony/turkus
ACC_GOLD    = '#D4A017'   # Złoty
ACC_ORANGE  = '#E05A00'   # Pomarańczowy
ACC_BLUE    = '#0984E3'   # Niebieski
ACC_PINK    = '#D63085'   # Różowy
ACC_RED     = '#C0392B'   # Czerwony

# Tekst
TXT_MAIN    = '#1A1A2E'   # Główny tekst
TXT_SUB     = '#2D3436'   # Podrzędny tekst
TXT_MUTED   = '#636E72'   # Wyciszony tekst
TXT_WHITE   = '#1A1A2E'

# ReportLab kolory
C_BG   = colors.HexColor(BG_PAGE)
C_ACC  = colors.HexColor(ACC_PURPLE)
C_GR   = colors.HexColor(ACC_CYAN)
C_TXT  = colors.HexColor(TXT_MAIN)
C_MUT  = colors.HexColor(TXT_MUTED)
C_W    = colors.white
C_YEL  = colors.HexColor(ACC_GOLD)
C_RED  = colors.HexColor(ACC_RED)
C_ORG  = colors.HexColor(ACC_ORANGE)
C_BLU  = colors.HexColor(ACC_BLUE)

PW, PH = A4

# Paleta gradientów sekcji
SECTION_ACCENTS = [ACC_PURPLE, ACC_CYAN, ACC_GOLD, ACC_ORANGE, ACC_BLUE, ACC_PINK]
SECTION_BG      = [BG_ACCENT,  BG_GREEN, BG_GOLD,  BG_RED,    BG_BLUE,  '#FFF0FA']

# ============================================================
# HELPER
# ============================================================
def st(t):
    return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16)/255 for i in (0, 2, 4))

def _sanitize_latex(f: str) -> str:
    import re; B = chr(92)
    for cmd in ['bigg|','Bigg|','big|','Big|']:
        f = f.replace(B+cmd, '|')
    for cmd in ['biggl','biggr','Biggl','Biggr','bigg','Bigg','bigl','bigr','Bigl','Bigr','big','Big']:
        f = f.replace(B+cmd, '')
    for src, dst in [('\\left(','('),('\\left[','['),('\\left{','{'),('\\left|','|'),
                     ('\\right)',')'),('\\right]',']'),('\\right}','}'),('\\right|','|'),
                     ('\\left.',''),('\\right.','')]:
        f = f.replace(src, dst)
    f = f.replace(B+'left','').replace(B+'right','')
    f = f.replace(B+',', ' ').replace(B+';',' ').replace(B+':',' ')
    f = f.replace(B+'!', '').replace(B+'quad','  ').replace(B+'qquad','   ')
    for cmd in ['displaystyle','textstyle','scriptstyle','scriptscriptstyle','limits','nolimits']:
        f = f.replace(B+cmd, '')
    for cmd in ['text','mathrm','mathbf','mathit','mathbb','mathcal','mathscr','boldsymbol','operatorname','ensuremath','mbox','hbox']:
        f = re.sub(re.escape(B+cmd)+r'\{([^}]*)\}', r'\1', f)
    for cmd in ['hspace','vspace','label','tag','phantom','vphantom','hphantom']:
        f = re.sub(re.escape(B+cmd)+r'\{[^}]*\}', '', f)
    f = re.sub(re.escape(B+'textcolor')+r'\{[^}]*\}\{([^}]*)\}', r'\1', f)
    f = re.sub(re.escape(B+'begin')+r'\{[^}]*\}', '', f)
    f = re.sub(re.escape(B+'end')+r'\{[^}]*\}', '', f)
    f = f.replace('&', ' ').replace(B+B, ' ')
    for cmd in ['overrightarrow','overleftarrow','widehat','widetilde','overline','underline']:
        f = re.sub(re.escape(B+cmd)+r'\{([^}]*)\}', r'\1', f)
    f = f.replace('$$', '$')
    f = re.sub(r'  +', ' ', f)
    return f.strip()

# ============================================================
# RENDEROWANIE WZORÓW
# ============================================================
def render_formula_png(formula: str, width_pt: float = 475) -> bytes | None:
    if not formula or not formula.strip():
        return None
    f = formula.strip()
    if not f.startswith('$'):
        f = '$' + f + '$'
    f = _sanitize_latex(f)
    if '$' not in f:
        f = '$' + f + '$'
    w_inch = max(1.0, width_pt / 72.0)
    from PIL import Image as _PILf; import io as _iof
    try:
        fig = plt.figure(figsize=(w_inch, 1.2), dpi=200)
        fig.patch.set_facecolor(BG_ACCENT)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor(BG_ACCENT); ax.axis('off')
        ax.text(0.5, 0.5, f, fontsize=22, ha='center', va='center',
               color=TXT_MAIN, transform=ax.transAxes)
        buf = _iof.BytesIO()
        plt.savefig(buf, format='png', dpi=200, bbox_inches='tight',
                   facecolor=BG_ACCENT, edgecolor='none', pad_inches=0.12)
        plt.close(fig); buf.seek(0)
        rgb = _PILf.open(buf).convert('RGB')
        out = _iof.BytesIO(); rgb.save(out, 'PNG'); out.seek(0)
        return out.read()
    except:
        try: plt.close(fig)
        except: pass
        return None

def formula_to_rl_image(formula: str, width_pt: float = 475) -> RLImage | None:
    png = render_formula_png(formula, width_pt)
    if not png: return None
    try:
        from PIL import Image as PILImg
        img = PILImg.open(io.BytesIO(png))
        iw, ih = img.size
        scale = width_pt / (iw / 120 * 72)
        h_pt = (ih / 120 * 72) * scale
        return RLImage(io.BytesIO(png), width=width_pt, height=h_pt)
    except:
        return RLImage(io.BytesIO(png), width=width_pt, height=50)

def _render_text_png(tekst, width_pt, height_pt=28, fontsize=9, color=TXT_MAIN, bg=BG_PAGE, bold=False):
    from PIL import Image as _PILT; import io as _iot; import re as _re_rt
    DPI = 200
    W_IN = max(0.5, width_pt / 72)
    fw = "bold" if bold else "normal"
    if '$' in tekst:
        tekst = _re_rt.sub(r'\$[^$]+\$', lambda m: _sanitize_latex(m.group(0)), tekst)
    def _wrap(txt):
        cpl = max(20, int(W_IN * 72 / (fontsize * 0.60)))
        linie, bufor, in_m = [], "", False
        for ch in txt:
            if ch == "$": in_m = not in_m
            bufor += ch
            if ch == " " and not in_m and len(bufor) > cpl:
                linie.append(bufor.rstrip()); bufor = ""
        if bufor.strip(): linie.append(bufor.strip())
        return linie if linie else [txt]
    def _draw(txt, fs):
        linie = _wrap(txt)
        H_IN = max(0.32, 0.42 * len(linie) + 0.12)
        full = "\n".join(linie)
        fig = plt.figure(figsize=(W_IN, H_IN), dpi=DPI)
        fig.patch.set_facecolor(bg)
        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
        ax.set_facecolor(bg); ax.axis("off")
        ax.text(0.015, 0.96, full, fontsize=fs, fontweight=fw,
               color=color, ha="left", va="top", transform=ax.transAxes, linespacing=1.50)
        _buf = _iot.BytesIO()
        plt.savefig(_buf, format="png", dpi=DPI, facecolor=bg, edgecolor="none")
        plt.close(fig); _buf.seek(0)
        rgb = _PILT.open(_buf).convert("RGB")
        out = _iot.BytesIO(); rgb.save(out, "PNG"); out.seek(0)
        return out.read()
    try:
        return _draw(tekst, fontsize)
    except:
        try: plt.close()
        except: pass
        return None

def has_math(t): return '$' in str(t)

def smart_png(tekst, width_pt, height_pt=28, fontsize=9, color=TXT_MAIN, bg=BG_PAGE, bold=False):
    if not tekst or not str(tekst).strip(): return None
    if has_math(tekst):
        return _render_text_png(tekst, width_pt, height_pt, fontsize, color, bg, bold)
    return None

def render_mixed_line(tekst, styl, W, fontsize=10.5, color=TXT_MAIN, bg=BG_PAGE):
    if not tekst or not tekst.strip(): return Spacer(1, 2)
    stripped = tekst.strip()
    if stripped.startswith('$') and stripped.endswith('$') and stripped.count('$') == 2:
        img = formula_to_rl_image(stripped, width_pt=W*0.72)
        if img: return img
    if '$' in tekst:
        from PIL import Image as _PILml; import io as _ioml
        png = _render_text_png(tekst.strip(), W, 30, fontsize=fontsize, color=color, bg=bg)
        if png:
            pil = _PILml.open(_ioml.BytesIO(png))
            h_pt = pil.size[1] / 150 * 72
            return RLImage(_ioml.BytesIO(png), width=W, height=h_pt)
    return Paragraph(st(tekst), styl)

def smart_para(tekst, styl, width_pt=515, fontsize=10.5, color=TXT_MAIN, bg=BG_PAGE):
    if not tekst or not str(tekst).strip(): return Spacer(1, 2)
    if has_math(tekst):
        from PIL import Image as _PILmp; import io as _iomp
        png = _render_text_png(str(tekst).strip(), width_pt, 28, fontsize=fontsize, color=color, bg=bg)
        if png:
            pil = _PILmp.open(_iomp.BytesIO(png))
            h_pt = pil.size[1] / 110 * 72
            return RLImage(_iomp.BytesIO(png), width=width_pt, height=h_pt)
    return Paragraph(st(str(tekst)), styl)

# ============================================================
# TŁO STRON — PREMIUM REDESIGN
# ============================================================
def add_page_bg(c, doc):
    w, h = A4
    c.saveState()

    # Główne tło
    c.setFillColor(colors.HexColor(BG_PAGE))
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Subtelna siatka (bardzo delikatna)
    try: c.setStrokeColorRGB(*hex2rgb(ACC_PURPLE), alpha=0.04)
    except: c.setStrokeColor(colors.HexColor('#DFE6E9'))
    c.setLineWidth(0.4)
    for x in range(0, int(w)+1, 48):
        c.line(x, 0, x, h)
    for y in range(0, int(h)+1, 48):
        c.line(0, y, w, y)

    # Gradient glow w lewym górnym rogu
    for i in range(8):
        r = 160 + i * 22
        alpha = max(0.0, 0.06 - i * 0.007)
        c.setFillColorRGB(*hex2rgb(ACC_PURPLE), alpha=alpha)
        c.circle(-20, h + 20, r, fill=1, stroke=0)

    # Header bar — elegancki ciemny pas
    c.setFillColor(colors.HexColor('#FFFFFF'))
    c.rect(0, h - 38, w, 38, fill=1, stroke=0)

    # Kolorowy pasek na górze (gradientowy efekt przez 3 prostokąty)
    c.setFillColor(colors.HexColor(ACC_PURPLE)); c.rect(0, h-38, w*0.4, 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_CYAN));   c.rect(w*0.4, h-38, w*0.35, 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_GOLD));   c.rect(w*0.75, h-38, w*0.25, 2, fill=1, stroke=0)

    # Logo/marka w headerze
    c.setFont(FB, 8); c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.drawString(14, h - 24, "EDUVIA")
    c.setFont(FN, 7); c.setFillColor(colors.HexColor(TXT_MUTED))
    c.drawString(56, h - 24, "AI PREMIUM NOTES")

    # Numer strony — prawo
    c.setFont(FN, 7.5); c.setFillColor(colors.HexColor(TXT_MUTED))
    pg = str(doc.page)
    c.drawRightString(w - 14, h - 24, f"str. {pg}")

    # Footer bar
    c.setFillColor(colors.HexColor('#FFFFFF'))
    c.rect(0, 0, w, 22, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.rect(0, 0, w, 1.5, fill=1, stroke=0)
    c.setFont(FN, 6.5); c.setFillColor(colors.HexColor(TXT_MUTED))
    c.drawCentredString(w/2, 7, "Eduvia AI  ·  Ucz się mądrzej, nie ciężej  ·  eduvia.pl")

    c.restoreState()

# ============================================================
# OKŁADKA — PREMIUM REDESIGN
# ============================================================
def draw_cover(c, tytul, podtytul, klasa):
    w, h = PW, PH
    c.setFillColor(colors.HexColor('#FFFFFF'))
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Duże glowy w tle
    for i in range(16):
        alpha = max(0.0, 0.12 - i * 0.007)
        try: c.setFillColorRGB(*hex2rgb(ACC_PURPLE), alpha=alpha)
        except: c.setFillColorRGB(*hex2rgb('#E0D8FF'))
        c.circle(w * 0.5, h * 0.5, 80 + i * 28, fill=1, stroke=0)

    for i in range(10):
        alpha = max(0.0, 0.08 - i * 0.007)
        c.setFillColorRGB(*hex2rgb(ACC_CYAN), alpha=alpha)
        c.circle(w * 0.1, h * 0.2, 60 + i * 22, fill=1, stroke=0)

    for i in range(8):
        alpha = max(0.0, 0.06 - i * 0.006)
        c.setFillColorRGB(*hex2rgb(ACC_GOLD), alpha=alpha)
        c.circle(w * 0.9, h * 0.8, 50 + i * 20, fill=1, stroke=0)

    # Subtelna siatka
    c.setStrokeColorRGB(*hex2rgb(ACC_PURPLE), alpha=0.06)
    c.setLineWidth(0.3)
    for x in range(0, int(w)+1, 40): c.line(x, 0, x, h)
    for y in range(0, int(h)+1, 40): c.line(0, y, w, y)

    # Top brand bar
    c.setFillColor(colors.HexColor('#F8F7FF'))
    c.rect(0, h - 52, w, 52, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.rect(0, h - 52, w, 2.5, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_CYAN))
    c.rect(w * 0.38, h - 52, w * 0.24, 2.5, fill=1, stroke=0)

    # Brand name
    c.setFont(FB, 11); c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.drawString(16, h - 34, "EDUVIA")
    c.setFont(FN, 8); c.setFillColor(colors.HexColor(TXT_MUTED))
    c.drawString(72, h - 34, "AI PREMIUM NOTES")

    # Badge poziom
    bx, by, bw, bh2 = w/2 - 55, h - 50 - 32, 110, 22
    c.setFillColor(colors.HexColor('#F0EEFF'))
    c.roundRect(bx, by, bw, bh2, 11, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor(ACC_PURPLE)); c.setLineWidth(1)
    c.roundRect(bx, by, bw, bh2, 11, fill=0, stroke=1)
    c.setFont(FB, 8); c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.drawCentredString(w/2, by + 7, f"POZIOM: {klasa.upper()}")

    # Główny tytuł
    words = tytul.split()
    c.setFont(FB, 34)
    if len(tytul) > 24 and len(words) > 2:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        c.setFillColor(C_W)
        c.drawCentredString(w/2, h * 0.52, line1)
        c.drawCentredString(w/2, h * 0.46, line2)
        ty = h * 0.40
    else:
        c.setFillColor(C_W)
        c.drawCentredString(w/2, h * 0.49, tytul)
        ty = h * 0.43

    # Podtytuł
    c.setFont(FI, 13); c.setFillColor(colors.HexColor(ACC_CYAN))
    c.drawCentredString(w/2, ty - 4, podtytul)

    # Separator linia
    c.setStrokeColor(colors.HexColor('#DFE6E9')); c.setLineWidth(1)
    c.line(w/2 - 120, ty - 22, w/2 + 120, ty - 22)

    # Data
    c.setFont(FN, 10); c.setFillColor(colors.HexColor(TXT_MUTED))
    c.drawCentredString(w/2, ty - 38, datetime.now().strftime('%d.%m.%Y'))

    # Narożne ozdoby
    for bx2, by2 in [(28, 70), (w - 28, 70)]:
        c.setStrokeColor(colors.HexColor(ACC_PURPLE)); c.setLineWidth(1.5)
        c.setFillColor(colors.HexColor(ACC_PURPLE))
        c.circle(bx2, by2, 4, fill=1, stroke=0)
        for r in [12, 22]:
            c.setFillColorRGB(*hex2rgb(ACC_PURPLE), alpha=0.15)
            c.circle(bx2, by2, r, fill=1, stroke=0)

    # Bottom bar
    c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.rect(0, 0, w, 6, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_CYAN))
    c.rect(w * 0.38, 0, w * 0.24, 6, fill=1, stroke=0)

    c.showPage()

# ============================================================
# NOWE FLOWABLES — PREMIUM REDESIGN
# ============================================================
class SectionHeader(Flowable):
    """Elegancki nagłówek sekcji z numerem i kolorowym akcentem."""
    def __init__(self, number, text, accent=ACC_PURPLE, width=515):
        super().__init__()
        self.number = number; self.text = text
        self.accent = accent; self.width = width; self.height = 52

    def draw(self):
        c = self.canv; W = self.width; H = self.height
        acc = self.accent
        bg_col = '#F8F7FF'

        # Tło karty
        c.setFillColor(colors.HexColor(bg_col))
        c.roundRect(0, 0, W, H, 10, fill=1, stroke=0)

        # Lewy pasek gradientowy
        c.setFillColor(colors.HexColor(acc))
        c.roundRect(0, 0, 5, H, 2, fill=1, stroke=0)

        # Delikatna ramka
        c.setStrokeColorRGB(*hex2rgb(acc), alpha=0.25)
        c.setLineWidth(0.8)
        c.roundRect(0, 0, W, H, 10, fill=0, stroke=1)

        # Kółko z numerem
        cx, cy = 26, H // 2
        c.setFillColorRGB(*hex2rgb(acc), alpha=0.15)
        c.circle(cx, cy, 16, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor(acc)); c.setLineWidth(1.5)
        c.circle(cx, cy, 16, fill=0, stroke=1)
        c.setFillColor(colors.HexColor(acc))
        c.setFont(FB, 10); c.drawCentredString(cx, cy - 4, f"{self.number:02d}")

        # Tytuł
        c.setFillColor(C_W); c.setFont(FB, 13)
        c.drawString(50, H // 2 - 5, self.text[:60])

        # Mała linia dekoracyjna po prawej
        c.setStrokeColorRGB(*hex2rgb(acc), alpha=0.3); c.setLineWidth(1)
        txt_w = c.stringWidth(self.text[:60], FB, 13)
        c.line(54 + txt_w + 10, cy, W - 16, cy)


class ConceptCard(Flowable):
    """Karta pojęcia — nowy premium wygląd."""
    def __init__(self, pojecie, definicja, idx, width):
        super().__init__()
        self.pojecie = pojecie; self.definicja = definicja
        self.idx = idx; self.width = width
        lines = max(2, len(definicja) // 46 + 1)
        self.height = 66 + lines * 13

    def draw(self):
        c = self.canv; W = self.width; H = self.height
        ACCENTS = [ACC_PURPLE, ACC_CYAN, ACC_GOLD, ACC_ORANGE]
        BG_LIST = ['#F0EEFF','#F0FFF8','#FFFBF0','#FFF5F5','#EBF5FF','#FFF0FA']
        acc = ACCENTS[self.idx % 4]
        bg  = BG_LIST[self.idx % 4]

        # Tło karty z zaokrągleniem
        c.setFillColor(colors.HexColor(bg))
        c.roundRect(0, 2, W, H - 4, 12, fill=1, stroke=0)

        # Cienka ramka w kolorze akcentu
        c.setStrokeColorRGB(*hex2rgb(acc), alpha=0.4); c.setLineWidth(1)
        c.roundRect(0, 2, W, H - 4, 12, fill=0, stroke=1)

        # Header z pojęciem
        c.setFillColorRGB(*hex2rgb(acc), alpha=0.18)
        c.roundRect(0, H - 32, W, 30, 12, fill=1, stroke=0)
        c.rect(0, H - 22, W, 10, fill=1, stroke=0)

        # Pasek akcentu na górze karty
        c.setFillColor(colors.HexColor(acc))
        c.roundRect(0, H - 6, W, 6, 3, fill=1, stroke=0)

        # Pojęcie
        c.setFillColor(C_W); c.setFont(FB, 9.5)
        p = self.pojecie[:34] + "..." if len(self.pojecie) > 34 else self.pojecie
        c.drawString(10, H - 22, p)

        # Definicja
        import re as _re2
        defn = _re2.sub(r'\$[^$]*\$', lambda m: m.group(0).replace('$','').strip(), self.definicja)
        defn = defn.replace('\\','').replace('\\int','∫').replace('\\sum','Σ')
        defn = defn.replace('\\to','→').replace('\\rightarrow','→').replace('\\cdot','·')
        c.setFillColor(colors.HexColor(TXT_SUB)); c.setFont(FN, 8.5)
        words = defn.split(); line = ""; y = H - 36
        for word in words:
            test = (line + " " + word).strip()
            if c.stringWidth(test, FN, 8.5) < W - 18: line = test
            else:
                if y < 12: c.drawString(10, y, line + "..."); break
                c.drawString(10, y, line); y -= 12; line = word
        if line and y >= 12: c.drawString(10, y, line)


class TimelineItem(Flowable):
    def __init__(self, rok, opis, is_last, width):
        super().__init__()
        self.rok = str(rok); self.opis = opis
        self.is_last = is_last; self.width = width
        self.height = 38 + max(1, len(opis) // 58 + 1) * 13

    def draw(self):
        c = self.canv; H = self.height
        if not self.is_last:
            c.setStrokeColorRGB(*hex2rgb(ACC_PURPLE), alpha=0.3)
            c.setLineWidth(2); c.line(26, -8, 26, 0)
        # Kółko na osi czasu
        c.setFillColorRGB(*hex2rgb(ACC_PURPLE), alpha=0.2)
        c.circle(26, H - 18, 9, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(ACC_PURPLE))
        c.circle(26, H - 18, 5, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(BG_PAGE)); c.circle(26, H - 18, 2, fill=1, stroke=0)
        # Rok
        c.setFillColor(colors.HexColor(ACC_CYAN)); c.setFont(FB, 10)
        c.drawString(44, H - 22, self.rok)
        # Opis
        c.setFillColor(colors.HexColor(TXT_SUB)); c.setFont(FN, 9)
        words = self.opis.split(); line = ""; y = H - 34
        for word in words:
            test = (line + " " + word).strip()
            if c.stringWidth(test, FN, 9) < self.width - 58: line = test
            else: c.drawString(44, y, line); y -= 13; line = word
        if line: c.drawString(44, y, line)


class MindMapItem(Flowable):
    def __init__(self, poziom, tekst, width):
        super().__init__()
        self.poziom = poziom; self.tekst = tekst; self.width = width
        self.height = 30 if poziom == 0 else 24

    def draw(self):
        c = self.canv; indent = self.poziom * 28; avail = self.width - indent; H = self.height
        COLS = [ACC_PURPLE, ACC_CYAN, TXT_MUTED]
        BG_MM = ['#F0EEFF', '#F0FFF8', '#FFFFFF']
        col = COLS[min(self.poziom, 2)]
        bg  = BG_MM[min(self.poziom, 2)]
        c.setFillColor(colors.HexColor(bg))
        c.roundRect(indent, 2, avail, H - 4, 6, fill=1, stroke=0)
        if self.poziom < 2:
            c.setStrokeColorRGB(*hex2rgb(col), alpha=0.35); c.setLineWidth(0.8)
            c.roundRect(indent, 2, avail, H - 4, 6, fill=0, stroke=1)
        c.setFillColor(colors.HexColor(col))
        c.roundRect(indent, 2, 4, H - 4, 2, fill=1, stroke=0)
        fs = [11, 9.5, 8.5][min(self.poziom, 2)]
        fw = [FB, FB, FN][min(self.poziom, 2)]
        c.setFont(fw, fs); c.setFillColor(C_W if self.poziom < 2 else colors.HexColor(TXT_MUTED))
        c.drawString(indent + 12, H // 2 - fs // 3, self.tekst[:72])


# ============================================================
# PROMPT
# ============================================================
PROMPT = """Jestes doswiadczonym nauczycielem matematyki z 15-letnim stazem i autorem materialow edukacyjnych.
Tworzysz PROFESJONALNA notatke premium dla ucznia na poziomie: {klasa}
TEMAT: {temat}

Zwroc TYLKO czysty JSON (bez markdown, bez backticks, bez komentarzy).

=== WZORY MATEMATYCZNE ===
Format matplotlib mathtext. ZAWSZE otaczaj wzory $ ... $
Przyklady: "$\\frac{{a}}{{b}} + \\frac{{c}}{{d}} = \\frac{{ad+bc}}{{bd}}$"
           "$\\int_a^b f(x)\\,dx = F(b)-F(a)$"
           "$\\Delta x \\rightarrow 0$"
Wzory fizyczne MUSZA miec jednostki np. [J], [m/s], [N]

=== STYL PISANIA — ABSOLUTNY NAKAZ ===
ZAKAZ: "jest kluczowy", "jest fundamentem", "odgrywa role", "stanowi podstawe", "warto wiedziec", "nalezy pamietac"
ZAKAZ: suchych definicji bez intuicji i bez przykladu
NAKAZ: pisz jak NAUCZYCIEL ktory siedzi obok ucznia i go PROWADZI
NAKAZ: kazda sekcja = wprowadzenie + wzor + PRZYKLAD KROK PO KROKU + komentarz
NAKAZ: kazdy przyklad musi miec KONKRETNE LICZBY, ponumerowane kroki i komentarz przy kazdym kroku
NAKAZ: oznaczaj trudnosc: [P] podstawowy, [E] egzaminacyjny, [A] ambitny

=== STRUKTURA JSON ===
{{
  "tytul": "Tytul (max 45 znakow)",
  "podtytul": "Podtytul (max 75 znakow)",
  "kluczowe_pojecia": [
    {{"pojecie": "Nazwa pojecia","definicja": "Precyzyjna definicja + CO TO ZNACZY DLA UCZNIA + przyklad liczbowy."}}
  ],
  "sekcje": [
    {{
      "tytul": "Tytul sekcji (konkretny)",
      "tresc": "3-4 zdania wprowadzenia stylem nauczyciela.",
      "wzory": ["$wzor_z_pelnym_LaTeX$"],
      "przyklad": "OBOWIAZKOWY format:\\nZadanie: [tresc]\\nKrok 1: [co i dlaczego] -> [wynik]\\nKrok 2: [co i dlaczego] -> [wynik]\\nOdpowiedz: [wynik]\\nKomentarz: [co uczy]",
      "ciekawostka": "Zaskakujacy fakt LUB typowy blad. Pusty string jesli nie ma."
    }}
  ],
  "bledy_uczniow": [
    {{"blad": "Konkretny blad z przykladem liczbowym","dlaczego": "Mechanizm bledu","jak_zapamietac": "Trick lub mnemonik"}}
  ],
  "dlaczego_wazne": "2-3 zdania z konkretnymi przykladami zastosowania.",
  "tabela_porownawcza": {{"naglowki": ["K1","K2","K3"],"wiersze": [["w","w","w"]]}},
  "timeline": [{{"rok": "Rok","opis": "Co odkryto, max 85 znakow"}}],
  "schemat_myslowy": [{{"poziom": 0,"tekst": "GLOWNE POJECIE"}}],
  "quiz": [
    {{
      "pytanie": "[E] Pytanie OBLICZENIOWE z konkretnymi liczbami.",
      "opcje": ["A) wynik","B) wynik","C) wynik","D) wynik"],
      "odpowiedz": "B",
      "wyjasnienie": "Krok 1: ... Krok 2: ... Odpowiedz: B bo...",
      "poziom": "egzaminacyjny"
    }}
  ],
  "podsumowanie": "3 zdania: co umiesz, jakie wzory, gdzie zastosujesz.",
  "do_zapamietania": [
    "[P] Wzor lub fakt z przykladem",
    "[E] Warunek stosowania",
    "[E] Najczestszy blad: POKAZ blad i poprawke",
    "[A] Nieintuicyjny fakt",
    "[P] Trick na szybkie liczenie"
  ]
}}

=== WYMAGANIA ===
- kluczowe_pojecia: 4-5, KAZDE z intuicja + przykladem
- sekcje: 3-4, KAZDA z przykladem krok-po-kroku
- bledy_uczniow: DOKLADNIE 3, KAZDY z przykladem
- quiz: DOKLADNIE 4 pytania
- do_zapamietania: DOKLADNIE 5
- Caly tekst PO POLSKU
- KRYTYCZNE: Znaki nowej linii w stringach zapisuj jako \\n (escape)"""

# ============================================================
# STYLE
# ============================================================
def get_styles():
    return {
        "body": ParagraphStyle("body", fontName=FN, fontSize=10.5, leading=19,
                               textColor=colors.HexColor(TXT_SUB), spaceAfter=5),
        "section_label": ParagraphStyle("sl", fontName=FB, fontSize=8, leading=12,
                                        textColor=colors.HexColor(TXT_MUTED),
                                        spaceBefore=24, spaceAfter=12,
                                        letterSpacing=1.5),
        "summary": ParagraphStyle("summ", fontName=FN, fontSize=10.5, leading=17,
                                  textColor=colors.HexColor('#1A1A2E'), spaceAfter=5),
        "bullet_item": ParagraphStyle("bi", fontName=FN, fontSize=10, leading=15,
                                      textColor=colors.HexColor('#1A1A2E'),
                                      leftIndent=12, spaceAfter=4),
        "ciekawostka": ParagraphStyle("ciek", fontName=FI, fontSize=9.5, leading=14,
                                      textColor=colors.HexColor(ACC_GOLD),
                                      spaceAfter=4, leftIndent=10),
        "example_header": ParagraphStyle("exh", fontName=FB, fontSize=8, leading=11,
                                         textColor=colors.HexColor(ACC_CYAN),
                                         spaceAfter=3, leftIndent=14),
        "error_text": ParagraphStyle("err", fontName=FB, fontSize=10, leading=15,
                                     textColor=colors.HexColor('#ff6b6b'),
                                     leftIndent=8, spaceAfter=3),
        "hint_text": ParagraphStyle("hint", fontName=FN, fontSize=9.5, leading=14,
                                    textColor=colors.HexColor(ACC_CYAN),
                                    leftIndent=8, spaceAfter=3),
    }

# ============================================================
# SEKCJA LABEL Z OZDOBNIKIEM
# ============================================================
class SectionLabel(Flowable):
    def __init__(self, text, accent=ACC_PURPLE, width=515):
        super().__init__()
        self.text = text; self.accent = accent
        self.width = width; self.height = 20

    def draw(self):
        c = self.canv; W = self.width
        acc = self.accent
        # Linia z ikoną
        c.setStrokeColorRGB(*hex2rgb(acc), alpha=0.5); c.setLineWidth(1)
        c.line(0, 8, W, 8)
        # Tło dla tekstu
        tw = c.stringWidth(self.text, FB, 7.5) + 16
        c.setFillColor(colors.HexColor(BG_PAGE))
        c.rect(0, 2, tw, 14, fill=1, stroke=0)
        # Tekst
        c.setFillColor(colors.HexColor(acc)); c.setFont(FB, 7.5)
        c.drawString(4, 5, self.text)


# ============================================================
# GŁÓWNA KLASA
# ============================================================
def _render_concept_png(pojecie, definicja, accent_color, width_px=240, height_px=110):
    import io as _io2
    DPI = 150; W_IN = width_px / 72; H_IN = 1.95
    fig = plt.figure(figsize=(W_IN, H_IN), dpi=DPI)
    fig.patch.set_facecolor(BG_CARD)
    # Header
    ax_h = fig.add_axes([0, 0.72, 1, 0.28])
    ax_h.set_facecolor(accent_color); ax_h.axis('off')
    poj_clean = pojecie.replace('$','')[:38]
    ax_h.text(0.5, 0.5, poj_clean, fontsize=9, fontweight='bold',
              color='#1A1A2E', ha='center', va='center', transform=ax_h.transAxes, clip_on=True)
    # Body
    ax_b = fig.add_axes([0.04, 0.02, 0.92, 0.68])
    ax_b.set_facecolor(BG_CARD); ax_b.axis('off')
    # Usuń cały LaTeX $...$ z definicji - w kartach nie renderujemy wzorów
    import re as _re_def
    defn_clean = _re_def.sub(r'\$[^$]*\$', lambda m: m.group(0).replace('$','').strip(), definicja)
    defn_clean = defn_clean.replace('\\','').replace('\\frac','').replace('\\int','calka')
    defn_clean = defn_clean.replace('\\rightarrow','->').replace('\\to','->').replace('\\cdot','*')
    defn_clean = defn_clean.replace('\\infty','nieskonczonosc').replace('\\pi','pi')
    defn_clean = _re_def.sub(r'[\\{}^_]', '', defn_clean)
    defn_clean = _re_def.sub(r'  +', ' ', defn_clean).strip()
    # Utnij po pełnym zdaniu (nie w środku słowa)
    if len(defn_clean) > 200:
        # Znajdź ostatnią kropkę przed limitem
        cut = defn_clean[:210].rfind('.')
        if cut < 100:  # Za krótko - utnij po ostatnim spacji
            cut = defn_clean[:210].rfind(' ')
        defn = defn_clean[:cut+1] if cut > 0 else defn_clean[:200] + '...'
    else:
        defn = defn_clean
    _cpl = max(18, int((W_IN * 0.88) * 72 / (7.2 * 0.63)))
    _ld, _bd, _im = [], '', False
    for _ch in defn:
        if _ch == '$': _im = not _im
        _bd += _ch
        if _ch == ' ' and not _im and len(_bd) > _cpl:
            _ld.append(_bd.rstrip()); _bd = ''
    if _bd.strip(): _ld.append(_bd.strip())
    if not _ld: _ld = [defn]
    ax_b.text(0.5, 0.97, '\n'.join(_ld), fontsize=7.2, color=TXT_SUB,
              ha='center', va='top', transform=ax_b.transAxes, multialignment='center', linespacing=1.5)
    try:
        from PIL import Image as _PIL_c; import io as _io_c
        _buf_c = _io_c.BytesIO()
        plt.savefig(_buf_c, format="png", dpi=DPI, facecolor=BG_CARD, edgecolor="none")
        plt.close(fig); _buf_c.seek(0)
        _rgb_c = _PIL_c.open(_buf_c).convert("RGB")
        _out_c = _io_c.BytesIO(); _rgb_c.save(_out_c, "PNG"); _out_c.seek(0)
        return _out_c.read()
    except:
        try: plt.close(fig)
        except: pass
        return None


class PremiumNotesGenerator:

    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.styles = get_styles()

    def _fix_json_escapes(self, raw):
        import re
        raw = re.sub(r'^```json\s*', '', raw); raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw); raw = raw.strip()
        B = chr(92); CTRL = {chr(12): B+B+'f', chr(13): B+B+'r', chr(11): B+B+'v', chr(8): B+B+'b'}
        result = []; i = 0; in_string = False
        while i < len(raw):
            c = raw[i]
            if not in_string:
                if c == '"': in_string = True
                result.append(c); i += 1; continue
            if c == '"': in_string = False; result.append(c); i += 1; continue
            if c == B:
                if i+1 < len(raw):
                    nc = raw[i+1]
                    if nc == B: result.append(B); result.append(B); i += 2
                    elif nc == '"': result.append(B); result.append('"'); i += 2
                    else: result.append(B); result.append(B); i += 1
                else: result.append(B); result.append(B); i += 1
            elif c in CTRL: result.append(CTRL[c]); i += 1
            else: result.append(c); i += 1
        return ''.join(result)

    def _robust_json_parse(self, raw: str) -> dict:
        import re as _re
        raw = _re.sub(r'^```json\s*', '', raw, flags=_re.MULTILINE)
        raw = _re.sub(r'^```\s*', '', raw, flags=_re.MULTILINE)
        raw = _re.sub(r'\s*```$', '', raw, flags=_re.MULTILINE)
        raw = raw.strip()
        m = _re.search(r'\{', raw)
        if m: raw = raw[m.start():]
        depth = 0; end_idx = len(raw)
        for i, ch in enumerate(raw):
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0: end_idx = i + 1; break
        raw = raw[:end_idx]

        def _fix_strings(s):
            result = []; in_str = False; i = 0; B = chr(92)
            VALID_AFTER_BS = set('"\\u/') | set('0123456789')
            while i < len(s):
                c = s[i]
                if not in_str:
                    if c == '"': in_str = True
                    result.append(c); i += 1; continue
                if c == '"':
                    n_bs = 0; j = len(result) - 1
                    while j >= 0 and result[j] == B: n_bs += 1; j -= 1
                    if n_bs % 2 == 0: in_str = False
                    result.append(c); i += 1
                elif c == '\n': result.append(B); result.append('n'); i += 1
                elif c == '\r': i += 1
                elif c == '\t': result.append(B); result.append('t'); i += 1
                elif c == B:
                    if i+1 < len(s):
                        nc = s[i+1]
                        if nc == B or nc in VALID_AFTER_BS:
                            result.append(B); result.append(nc); i += 2
                        else: result.append(B); result.append(B); i += 1
                    else: result.append(B); result.append(B); i += 1
                else: result.append(c); i += 1
            return ''.join(result)

        def _fix_tc(s):
            return _re.sub(r',\s*([}\]])', r'\1', s)

        for attempt in [
            lambda r: json.loads(r),
            lambda r: json.loads(_fix_strings(r)),
            lambda r: json.loads(_fix_tc(_fix_strings(r))),
            lambda r: json.loads(_re.sub(r'(?<!\\)\\(?!["\\bfnrtu/])', r'\\\\', r)),
        ]:
            try: return attempt(raw)
            except: pass

        try:
            result = {}
            for field in ['tytul','podtytul','dlaczego_wazne','podsumowanie']:
                m2 = _re.search(rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, _re.DOTALL)
                if m2:
                    try: result[field] = json.loads('"' + m2.group(1) + '"')
                    except: result[field] = m2.group(1).replace('\\n', '\n')
            if result.get('tytul'):
                for k in ['kluczowe_pojecia','sekcje','bledy_uczniow','timeline','schemat_myslowy','quiz','do_zapamietania']:
                    result.setdefault(k, [])
                result.setdefault('tabela_porownawcza', {})
                return result
        except: pass
        raise ValueError(f"JSON parse failed:\n{raw[:300]}")

    def _get_content_from_gpt(self, temat: str, klasa: str) -> dict:
        prompt = PROMPT.format(temat=temat, klasa=klasa)
        r = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Jestes ekspertem edukacyjnym. Odpowiadasz TYLKO czystym JSON bez zadnych komentarzy. "
                    "Wzory TYLKO w formacie $...$. "
                    "KRYTYCZNE: Znaki nowej linii w stringach zapisuj jako \\n (escape). "
                    "Zero backticks, zero markdown, zero komentarzy."
                )},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7, max_tokens=5500,
        )
        return self._robust_json_parse(r.choices[0].message.content.strip())

    def _build_content_pages(self, data: dict) -> bytes:
        S = self.styles; W = PW - 80; story = []

        # ── POJĘCIA ──────────────────────────────────────────
        pojecia = data.get('kluczowe_pojecia', [])
        if pojecia:
            story.append(SectionLabel("KLUCZOWE POJĘCIA", ACC_PURPLE, W))
            story.append(Spacer(1, 10))
            card_w = (W - 14) / 2
            CONCEPT_COLORS = [ACC_PURPLE, ACC_CYAN, ACC_GOLD, ACC_ORANGE]
            for i in range(0, len(pojecia), 2):
                pair = pojecia[i:i+2]
                row = []
                for j, p in enumerate(pair):
                    png = _render_concept_png(p.get('pojecie',''), p.get('definicja',''),
                                              CONCEPT_COLORS[(i+j) % 4], int(card_w), 110)
                    if png:
                        from PIL import Image as PILImg
                        pil = PILImg.open(io.BytesIO(png))
                        scale = card_w / (pil.size[0] / 120 * 72)
                        h_pt = (pil.size[1] / 120 * 72) * scale
                        row.append(RLImage(io.BytesIO(png), width=card_w, height=h_pt))
                    else:
                        row.append(ConceptCard(p.get('pojecie',''), p.get('definicja',''), i+j, card_w))
                if len(row) == 1: row.append('')
                t = Table([row], colWidths=[card_w, card_w])
                t.setStyle(TableStyle([
                    ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                    ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),12),
                    ('VALIGN',(0,0),(-1,-1),'TOP')
                ]))
                story.append(t)

        # ── SEKCJE ───────────────────────────────────────────
        for i, s in enumerate(data.get('sekcje', [])):
            acc = SECTION_ACCENTS[i % len(SECTION_ACCENTS)]
            story.append(Spacer(1, 22))
            story.append(SectionHeader(i + 1, s.get('tytul',''), accent=acc, width=W))
            story.append(Spacer(1, 16))

            # Treść
            if s.get('tresc'):
                for linia in s['tresc'].replace('\\n', '\n').split('\n'):
                    if not linia.strip(): continue
                    # Zawsze przez _render_text_png dla spójności fontu
                    from PIL import Image as _PILtr; import io as _iotr
                    _png_tr = _render_text_png(linia.strip(), W, 28,
                                               fontsize=10.5, color=TXT_SUB, bg=BG_PAGE)
                    if _png_tr:
                        _pil_tr = _PILtr.open(_iotr.BytesIO(_png_tr))
                        story.append(RLImage(_iotr.BytesIO(_png_tr), width=W,
                                             height=_pil_tr.size[1]/150*72))
                    else:
                        story.append(Paragraph(st(linia.strip()), S['body']))
                story.append(Spacer(1, 10))

            # Wzory — każdy w osobnym "boksie"
            for wzor in s.get('wzory', []):
                if wzor and wzor.strip() and len(wzor.strip()) > 3:
                    story.append(Spacer(1, 8))
                    img = formula_to_rl_image(wzor.strip(), width_pt=W * 0.78)
                    if img:
                        # Owiń w tabelę z tłem
                        t_f = Table([[img]], colWidths=[W])
                        t_f.setStyle(TableStyle([
                            ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(BG_ACCENT)),
                            ('TOPPADDING',(0,0),(-1,-1), 10),
                            ('BOTTOMPADDING',(0,0),(-1,-1), 10),
                            ('LEFTPADDING',(0,0),(-1,-1), 20),
                            ('ALIGN',(0,0),(-1,-1),'CENTER'),
                            ('LINEBEFORE',(0,0),(0,-1), 3, colors.HexColor(acc)),
                        ]))
                        story.append(t_f)
                    else:
                        story.append(Paragraph(f"  {st(wzor)}", ParagraphStyle("wzf",
                            fontName=FM, fontSize=10, textColor=colors.HexColor(ACC_CYAN), spaceAfter=4)))
                    story.append(Spacer(1, 6))

            # Przykład — nowy premium styl
            przyklad = s.get('przyklad', '')
            if przyklad and przyklad.strip():
                story.append(Spacer(1, 8))
                linie = przyklad.strip().replace('\\n', '\n').split('\n')
                rows = []
                # Header przykładu
                rows.append([Paragraph(
                    "  > PRZYKLAD",
                    ParagraphStyle("przH", fontName=FB, fontSize=8, leading=12,
                                   textColor=colors.HexColor(ACC_CYAN), leftIndent=8)
                )])
                for linia in linie:
                    if not linia.strip(): continue
                    tekst = "   " + linia.strip()
                    # ZAWSZE przez _render_text_png - jednakowy font
                    from PIL import Image as _PILl; import io as _iol
                    png_l = _render_text_png(tekst, W-4, 26, fontsize=10,
                                             color='#1A4A32', bg=BG_GREEN)
                    if png_l:
                        _pl = _PILl.open(_iol.BytesIO(png_l)).size[1]
                        rows.append([RLImage(_iol.BytesIO(png_l), width=W-4, height=_pl/150*72)])
                    else:
                        rows.append([Paragraph(
                            f"   {st(linia.strip())}",
                            ParagraphStyle("prz", fontName=FM, fontSize=10, leading=16,
                                           textColor=colors.HexColor('#c8f0d8'), leftIndent=14)
                        )])
                t_prz = Table(rows, colWidths=[W])
                t_prz.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(BG_GREEN)),
                    ('LINEBEFORE',(0,0),(0,-1), 3, colors.HexColor(ACC_CYAN)),
                    ('TOPPADDING',(0,0),(-1,-1), 6),('BOTTOMPADDING',(0,0),(-1,-1), 8),
                    ('LEFTPADDING',(0,0),(-1,-1), 0),('RIGHTPADDING',(0,0),(-1,-1), 10),
                ]))
                story.append(t_prz)
                story.append(Spacer(1, 6))

            # Ciekawostka
            ciek = s.get('ciekawostka', '')
            if ciek and ciek.strip():
                story.append(Spacer(1, 4))
                from PIL import Image as _PILck; import io as _iock
                _png_ck = _render_text_png("  * " + ciek, W, 28, fontsize=10,
                                           color=ACC_GOLD, bg=BG_GOLD)
                if _png_ck:
                    _pil_ck = _PILck.open(_iock.BytesIO(_png_ck))
                    ciek_para = RLImage(_iock.BytesIO(_png_ck), width=W,
                                        height=_pil_ck.size[1]/150*72)
                else:
                    ciek_para = Paragraph(st("  * " + ciek), S['ciekawostka'])
                t_c = Table([[ciek_para]], colWidths=[W])
                t_c.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(BG_GOLD)),
                    ('LINEBEFORE',(0,0),(0,-1), 3, colors.HexColor(ACC_GOLD)),
                    ('TOPPADDING',(0,0),(-1,-1), 6),('BOTTOMPADDING',(0,0),(-1,-1), 6),
                    ('LEFTPADDING',(0,0),(-1,-1), 4),('RIGHTPADDING',(0,0),(-1,-1), 10),
                ]))
                story.append(t_c)

        # ── DLACZEGO WAŻNE ───────────────────────────────────
        dlaczego = data.get('dlaczego_wazne', '')
        if dlaczego and dlaczego.strip():
            story.append(Spacer(1, 20))
            story.append(SectionLabel("DLACZEGO MUSISZ TO UMIEĆ?", ACC_BLUE, W))
            story.append(Spacer(1, 8))
            from PIL import Image as _PILdl; import io as _iodl
            _png_dl = _render_text_png("  " + dlaczego, W-4, 28, fontsize=10.5,
                                       color='#0A3060', bg=BG_BLUE)
            if _png_dl:
                _pil_dl = _PILdl.open(_iodl.BytesIO(_png_dl))
                p_dl = RLImage(_iodl.BytesIO(_png_dl), width=W-4,
                               height=_pil_dl.size[1]/150*72)
            else:
                p_dl = Paragraph(st("  " + dlaczego), S['body'])
            t_dl = Table([[p_dl]], colWidths=[W])
            t_dl.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(BG_BLUE)),
                ('LINEBEFORE',(0,0),(0,-1), 4, colors.HexColor(ACC_BLUE)),
                ('TOPPADDING',(0,0),(-1,-1), 10),('BOTTOMPADDING',(0,0),(-1,-1), 10),
                ('LEFTPADDING',(0,0),(-1,-1), 4),('RIGHTPADDING',(0,0),(-1,-1), 12),
            ]))
            story.append(t_dl)

        # ── BŁĘDY UCZNIÓW ────────────────────────────────────
        bledy = data.get('bledy_uczniow', [])
        if bledy:
            story.append(Spacer(1, 20))
            story.append(SectionLabel("BŁĘDY KTÓRE ROBI 7/10 UCZNIÓW", ACC_RED, W))
            story.append(Spacer(1, 8))
            for idx_b, bl in enumerate(bledy):
                rows_b = []
                from PIL import Image as _PILbl; import io as _iobl

                def _bl_png(tekst, col):
                    png = _render_text_png(tekst, W-4, 28, fontsize=10,
                                          color=col, bg=BG_RED)
                    if png:
                        pil = _PILbl.open(_iobl.BytesIO(png))
                        return RLImage(_iobl.BytesIO(png), width=W-4,
                                       height=pil.size[1]/150*72)
                    return Paragraph(st(tekst), ParagraphStyle("fb", fontName=FN,
                        fontSize=10, textColor=colors.HexColor(col)))

                blad_txt = f"  X  BLAD #{idx_b+1}: {bl.get('blad','')}"
                rows_b.append([_bl_png(blad_txt, '#ff6b6b')])
                if bl.get('dlaczego'):
                    rows_b.append([_bl_png("  Dlaczego: " + bl['dlaczego'], '#ffaa88')])
                if bl.get('jak_zapamietac'):
                    rows_b.append([_bl_png("  Trick: " + bl['jak_zapamietac'], ACC_CYAN)])
                t_b = Table(rows_b, colWidths=[W])
                t_b.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(BG_RED)),
                    ('LINEBEFORE',(0,0),(0,-1), 4, colors.HexColor(ACC_RED)),
                    ('TOPPADDING',(0,0),(-1,-1), 4),('BOTTOMPADDING',(0,0),(-1,-1), 4),
                    ('LEFTPADDING',(0,0),(-1,-1), 4),('RIGHTPADDING',(0,0),(-1,-1), 12),
                ]))
                story.append(t_b)
                story.append(Spacer(1, 8))

        # ── TABELA PORÓWNAWCZA ───────────────────────────────
        tab = data.get('tabela_porownawcza', {})
        if tab and tab.get('wiersze'):
            story.append(Spacer(1, 20))
            story.append(SectionLabel("TABELA PORÓWNAWCZA", ACC_PURPLE, W))
            story.append(Spacer(1, 8))
            nagl = tab.get('naglowki', []); wiersze = tab.get('wiersze', [])
            if nagl and wiersze:
                col_w = W / len(nagl)
                def _l2u(s):
                    import re as _r2; s = str(s).strip()
                    s = _r2.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', r'\1/\2', s)
                    for src, dst in [('\\int','∫'),('\\infty','∞'),('\\pi','π'),
                                     ('\\alpha','α'),('\\beta','β'),('\\gamma','γ'),
                                     ('\\Delta','Δ'),('\\delta','δ'),('\\sigma','σ'),
                                     ('\\leq','≤'),('\\geq','≥'),('\\neq','≠'),
                                     ('\\rightarrow','→'),('\\to','→'),('\\cdot','·')]:
                        s = s.replace(src, dst)
                    s = _r2.sub(r'[\\{}_^]','',s).replace('$','').strip()
                    return s
                def _cell(val):
                    s = str(val).strip()
                    # Zawsze renderuj tak samo - tekst przez PNG z identycznym fontem
                    if '$' in s or '\\' in s:
                        # Wzór - renderuj przez matplotlib z IDENTYCZNYM rozmiarem
                        png = _render_text_png(s, col_w - 8, 28, fontsize=11,
                                               color=TXT_MAIN, bg=BG_CARD2)
                        if png:
                            from PIL import Image as _PILc; import io as _ioc
                            _pc = _PILc.open(_ioc.BytesIO(png))
                            return RLImage(_ioc.BytesIO(png), width=col_w-8,
                                          height=_pc.size[1]/150*72)
                    # Zwykły tekst - Paragraph z identycznym fontem
                    return Paragraph(st(_l2u(s)), ParagraphStyle("tc", fontName=FN,
                        fontSize=10, textColor=colors.HexColor('#1A1A2E'), alignment=1))
                safe_w = [[_cell(c) for c in row] for row in wiersze]
                nagl_cells = [Paragraph(st(_l2u(n)), ParagraphStyle("th", fontName=FB,
                    fontSize=10, textColor=C_W, alignment=1)) for n in nagl]
                t = Table([nagl_cells] + safe_w, colWidths=[col_w]*len(nagl), repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,0), colors.HexColor(ACC_PURPLE)),
                    ('TEXTCOLOR',(0,0),(-1,0), C_W),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),
                     [colors.HexColor('#F8F7FF'), colors.HexColor('#F0EEFF')]),
                    ('TEXTCOLOR',(0,1),(-1,-1), colors.HexColor(TXT_MAIN)),
                    ('FONTNAME',(0,1),(-1,-1), FN),('FONTSIZE',(0,1),(-1,-1), 10),
                    ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                    ('GRID',(0,0),(-1,-1), 0.5, colors.HexColor('#DFE6E9')),
                    ('LINEBELOW',(0,0),(-1,0), 2, colors.HexColor(ACC_PURPLE)),
                    ('TOPPADDING',(0,0),(-1,-1), 12),('BOTTOMPADDING',(0,0),(-1,-1), 12),
                    ('LEFTPADDING',(0,0),(-1,-1), 8),('RIGHTPADDING',(0,0),(-1,-1), 8),
                    ('ROWHEIGHT',(0,1),(-1,-1), 44),
                ]))
                story.append(t)

        # ── OŚ CZASU ─────────────────────────────────────────
        tl = data.get('timeline', [])
        if tl:
            import re as _re
            def _rok_sort(item):
                m = _re.search(r'(\d{3,4})', str(item.get('rok','')))
                val = int(m.group(1)) if m else 9999
                return -val if 'p.n.e' in str(item.get('rok','')) else val
            tl = sorted(tl, key=_rok_sort)
            story.append(Spacer(1, 20))
            story.append(SectionLabel("OŚ CZASU", ACC_CYAN, W))
            story.append(Spacer(1, 10))
            for i, item in enumerate(tl):
                story.append(TimelineItem(item.get('rok',''), item.get('opis',''),
                                          (i == len(tl)-1), W))
                story.append(Spacer(1, 4))

        # ── SCHEMAT MYŚLOWY ──────────────────────────────────
        sch = data.get('schemat_myslowy', [])
        if sch:
            story.append(Spacer(1, 20))
            story.append(SectionLabel("MAPA MYŚLOWA", ACC_PURPLE, W))
            story.append(Spacer(1, 10))
            for item in sch:
                tekst_sch = item.get('tekst', '')
                poziom_sch = item.get('poziom', 0)
                if '$' in tekst_sch:
                    png_sch = _render_text_png(tekst_sch, W - poziom_sch*28 - 20, 24,
                                               fontsize=9.5,
                                               color=[ACC_PURPLE, ACC_CYAN, TXT_MUTED][min(poziom_sch,2)],
                                               bg=[BG_ACCENT, BG_GREEN, BG_PAGE][min(poziom_sch,2)])
                    if png_sch:
                        from PIL import Image as _PILsch; import io as _iosch
                        _psch = _PILsch.open(_iosch.BytesIO(png_sch))
                        story.append(RLImage(_iosch.BytesIO(png_sch),
                                             width=W-poziom_sch*28-20,
                                             height=_psch.size[1]/130*72))
                    else:
                        story.append(MindMapItem(poziom_sch, tekst_sch, W))
                else:
                    story.append(MindMapItem(poziom_sch, tekst_sch, W))
                story.append(Spacer(1, 4))

        # ── QUIZ ─────────────────────────────────────────────
        quiz = data.get('quiz', [])
        if quiz:
            story.append(PageBreak())
            story.append(SectionLabel("QUIZ SPRAWDZAJĄCY", ACC_RED, W))
            story.append(Spacer(1, 12))

            def _qpng(tekst, w, h, fs, col, bg, bold=False):
                png = smart_png(tekst, w, h, fontsize=fs, color=col, bg=bg, bold=bold)
                if not png: return None
                import io as _ioQZ; from PIL import Image as _PILQZ
                im = _PILQZ.open(_ioQZ.BytesIO(png))
                return RLImage(_ioQZ.BytesIO(png), width=w, height=im.size[1]/110*72)

            for i, q in enumerate(quiz):
                pytanie = q.get('pytanie', '')
                opcje = q.get('opcje', [])
                odp = q.get('odpowiedz', 'A')
                wyjasn = q.get('wyjasnienie', '')
                bg_quiz = '#F8F7FF' if i % 2 == 0 else '#FFFFFF'

                # Pytanie
                from PIL import Image as _PILpyt; import io as _iopyt
                _png_pyt = _render_text_png(f"Pytanie {i+1}: {pytanie}", W-4, 30,
                                            fontsize=12, color=TXT_WHITE, bg=bg_quiz, bold=True)
                if _png_pyt:
                    _pil_pyt = _PILpyt.open(_iopyt.BytesIO(_png_pyt))
                    story.append(RLImage(_iopyt.BytesIO(_png_pyt), width=W-4,
                                        height=_pil_pyt.size[1]/150*72))
                else:
                    story.append(Paragraph(st(f'Pytanie {i+1}: {pytanie}'),
                        ParagraphStyle("pytp", fontName=FB, fontSize=12,
                                       textColor=colors.HexColor(TXT_WHITE))))

                # Opcje
                for op in opcje:
                    ltr = op[0] if op else '?'
                    is_correct = (ltr == odp)
                    col = ACC_CYAN if is_correct else TXT_MUTED
                    bg_op = '#F0FFF8' if is_correct else bg_quiz
                    # ZAWSZE przez _render_text_png - jednakowy rozmiar czcionki
                    from PIL import Image as _PILop; import io as _ioop
                    _png_op = _render_text_png(f'  {op}', W-8, 28, fontsize=11,
                                               color=col, bg=bg_op)
                    if _png_op:
                        _pil_op = _PILop.open(_ioop.BytesIO(_png_op))
                        _h_op = _pil_op.size[1] / 150 * 72
                        op_elem = RLImage(_ioop.BytesIO(_png_op), width=W-8, height=_h_op)
                    else:
                        op_elem = Paragraph(st(f'  {op}'),
                            ParagraphStyle("opp", fontName=FN, fontSize=11,
                                           textColor=colors.HexColor(col)))
                    border_col = ACC_CYAN if is_correct else '#DFE6E9'
                    t_op = Table([[op_elem]], colWidths=[W])
                    t_op.setStyle(TableStyle([
                        ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(bg_op)),
                        ('TOPPADDING',(0,0),(-1,-1), 3),('BOTTOMPADDING',(0,0),(-1,-1), 3),
                        ('LEFTPADDING',(0,0),(-1,-1), 2),('RIGHTPADDING',(0,0),(-1,-1), 4),
                        ('LINEBEFORE',(0,0),(0,-1), 3, colors.HexColor(border_col)),
                    ]))
                    t_op.setStyle(TableStyle([
                        ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(bg_op)),
                        ('TOPPADDING',(0,0),(-1,-1), 3),('BOTTOMPADDING',(0,0),(-1,-1), 3),
                        ('LEFTPADDING',(0,0),(-1,-1), 2),('RIGHTPADDING',(0,0),(-1,-1), 4),
                        ('LINEBEFORE',(0,0),(0,-1), 3, colors.HexColor(border_col)),
                    ]))
                    story.append(t_op)
                    story.append(Spacer(1, 2))

                # Wyjaśnienie
                wyjasn_clean = wyjasn.replace('\\n', ' | ').replace('\n', ' | ')
                from PIL import Image as _PILwj; import io as _iowj
                _png_wj = _render_text_png("  Wyjaśnienie: " + wyjasn_clean, W-4, 26,
                                           fontsize=9.5, color=ACC_GOLD, bg=BG_GOLD)
                if _png_wj:
                    _pil_wj = _PILwj.open(_iowj.BytesIO(_png_wj))
                    story.append(RLImage(_iowj.BytesIO(_png_wj), width=W-4,
                                        height=_pil_wj.size[1]/150*72))
                else:
                    story.append(Paragraph(st(f'  Wyjaśnienie: {wyjasn_clean}'),
                        ParagraphStyle("wjp", fontName=FI, fontSize=9.5,
                                       textColor=colors.HexColor(ACC_GOLD))))
                story.append(Spacer(1, 24))

        # ── PODSUMOWANIE ─────────────────────────────────────
        story.append(Spacer(1, 20))
        story.append(SectionLabel("PODSUMOWANIE", ACC_CYAN, W))
        story.append(Spacer(1, 10))
        if data.get('podsumowanie'):
            podsum = data['podsumowanie'].replace('\\n', '\n')
            rows_ps = []
            for linia in podsum.split('. '):
                linia = linia.strip()
                if not linia: continue
                if not linia.endswith('.'): linia += '.'
                from PIL import Image as _PILps2; import io as _iops2
                _png_ps = _render_text_png(linia, W-32, 28, fontsize=10.5,
                                           color=TXT_MAIN, bg='#F0EEFF')
                if _png_ps:
                    _pil_ps = _PILps2.open(_iops2.BytesIO(_png_ps))
                    rows_ps.append([RLImage(_iops2.BytesIO(_png_ps), width=W-32,
                                            height=_pil_ps.size[1]/150*72)])
                else:
                    rows_ps.append([Paragraph(st(linia), S['summary'])])
            t = Table(rows_ps, colWidths=[W])
            t.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1), colors.HexColor('#F0EEFF')),
                ('LEFTPADDING',(0,0),(-1,-1), 20),('RIGHTPADDING',(0,0),(-1,-1), 20),
                ('TOPPADDING',(0,0),(-1,-1), 8),('BOTTOMPADDING',(0,0),(-1,-1), 8),
                ('LINEBELOW',(0,-1),(-1,-1), 3, colors.HexColor(ACC_CYAN)),
                ('LINEBEFORE',(0,0),(0,-1), 4, colors.HexColor(ACC_CYAN)),
            ]))
            story.append(t)

        # ── DO ZAPAMIĘTANIA ──────────────────────────────────
        dz = data.get('do_zapamietania', [])
        if dz:
            story.append(Spacer(1, 20))
            story.append(SectionLabel("DO ZAPAMIĘTANIA", ACC_GOLD, W))
            story.append(Spacer(1, 10))
            BULLETS = ["(1)","(2)","(3)","(4)","(5)"]
            COLORS_DZ = [ACC_PURPLE, ACC_CYAN, ACC_RED, ACC_GOLD, ACC_BLUE]
            for j, f in enumerate(dz):
                col_dz = COLORS_DZ[j % 5]
                tekst = f"{BULLETS[j%5]}  {f}"
                from PIL import Image as _PILdz2; import io as _iodz2
                _png_dz = _render_text_png(tekst, W-4, 28, fontsize=10.5,
                                           color=col_dz, bg=BG_CARD)
                if _png_dz:
                    _pil_dz = _PILdz2.open(_iodz2.BytesIO(_png_dz))
                    para_dz = RLImage(_iodz2.BytesIO(_png_dz), width=W-4,
                                      height=_pil_dz.size[1]/150*72)
                else:
                    para_dz = Paragraph(st(tekst), S['bullet_item'])
                t_dz = Table([[para_dz]], colWidths=[W])
                t_dz.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(BG_CARD)),
                    ('LINEBEFORE',(0,0),(0,-1), 3, colors.HexColor(col_dz)),
                    ('TOPPADDING',(0,0),(-1,-1), 5),('BOTTOMPADDING',(0,0),(-1,-1), 5),
                    ('LEFTPADDING',(0,0),(-1,-1), 4),('RIGHTPADDING',(0,0),(-1,-1), 10),
                ]))
                story.append(t_dz)
                story.append(Spacer(1, 8))

        # Build PDF
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=44, rightMargin=44,
                                topMargin=55, bottomMargin=35)
        doc.build(story, onFirstPage=add_page_bg, onLaterPages=add_page_bg)
        return buf.getvalue()

    def generate_pdf(self, temat: str, klasa: str = "liceum") -> str:
        print(f"[Eduvia] Generuje: '{temat}' | {klasa}")
        data = self._get_content_from_gpt(temat, klasa)
        print(f"[Eduvia] GPT: '{data.get('tytul','?')}'")

        cover_buf = io.BytesIO()
        c = canvas_module.Canvas(cover_buf, pagesize=A4)
        draw_cover(c, data.get('tytul', temat), data.get('podtytul','Notatka edukacyjna'), klasa)
        c.save(); cover_buf.seek(0)

        content_bytes = self._build_content_pages(data)

        writer = PdfWriter()
        for reader in [PdfReader(cover_buf), PdfReader(io.BytesIO(content_bytes))]:
            for page in reader.pages:
                writer.add_page(page)

        safe = re.sub(r'[^\w\s-]', '', temat)[:40].strip().replace(' ', '_')
        filename = f"Notatka_{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        with open(filename, 'wb') as f:
            writer.write(f)
        print(f"[Eduvia] Gotowe: {filename}")
        return filename