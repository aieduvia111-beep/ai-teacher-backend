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

def _txt_png(tekst, w_pt, fontsize=9, color='#1A1A2E', bg='#FFFFFF',
             bold=False, align='left'):
    """Renderuje tekst jako PNG przez matplotlib - gwarantuje polskie znaki."""
    import io as _io_tp; from PIL import Image as _PIL_tp
    w_in = max(0.3, w_pt / 72.0)
    # Szacuj wysokosc
    chars_per_line = max(15, int(w_in * 72 / (fontsize * 0.58)))
    words = str(tekst).split()
    lines = []; line = ''
    for word in words:
        test = (line + ' ' + word).strip()
        if len(test) > chars_per_line and line:
            lines.append(line); line = word
        else:
            line = test
    if line: lines.append(line)
    n = max(1, len(lines))
    h_in = max(0.25, n * fontsize / 72.0 * 1.8 + 0.08)
    fw = 'bold' if bold else 'normal'
    ha = 'center' if align == 'center' else 'left'
    x0 = 0.5 if align == 'center' else 0.01
    fig = plt.figure(figsize=(w_in, h_in), dpi=180)
    fig.patch.set_facecolor(bg)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(bg); ax.axis('off')
    ax.text(x0, 0.97, '\n'.join(lines), fontsize=fontsize,
            fontweight=fw, color=color, ha=ha, va='top',
            transform=ax.transAxes, linespacing=1.45)
    buf = _io_tp.BytesIO()
    plt.savefig(buf, format='png', dpi=180, facecolor=bg,
                edgecolor='none', bbox_inches='tight', pad_inches=0.02)
    plt.close(fig); buf.seek(0)
    return _PIL_tp.open(buf).convert('RGB')

def _txt_rl(tekst, w_pt, fontsize=9, color='#1A1A2E', bg='#FFFFFF',
            bold=False, align='left'):
    """Zwraca RLImage z tekstem - polskie znaki zawsze działają."""
    from PIL import Image as _PIL_rl; import io as _io_rl
    img = _txt_png(tekst, w_pt, fontsize, color, bg, bold, align)
    buf = _io_rl.BytesIO(); img.save(buf, 'PNG'); buf.seek(0)
    w_in_px, h_in_px = img.size
    h_pt = h_in_px / 180.0 * 72.0
    return RLImage(buf, width=w_pt, height=h_pt)

# ── POLSKIE ZNAKI W MATPLOTLIB ──────────────────────────────
import matplotlib as _mpl
_mpl.rcParams['font.family'] = 'DejaVu Sans'
_mpl.rcParams['axes.unicode_minus'] = False
# ─────────────────────────────────────────────────────────────

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
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
    # Auto-install na Render/Ubuntu
    try:
        import subprocess
        subprocess.run(['apt-get','install','-y','fonts-dejavu-core'],
                       capture_output=True, timeout=30)
        p = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        if os.path.exists(p):
            pdfmetrics.registerFont(TTFont('DJ',   p))
            pdfmetrics.registerFont(TTFont('DJ-B', p.replace('Sans.','Sans-Bold.')))
            pdfmetrics.registerFont(TTFont('DJ-I', p.replace('Sans.','Sans-Oblique.')))
            pdfmetrics.registerFont(TTFont('DJ-M', p.replace('Sans.','SansMono.')))
            pdfmetrics.registerFont(TTFont('DJ-MB',p.replace('Sans.','SansMono-Bold.')))
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

def _canvas_draw_text(c, tekst, x, y, width_pt, fontsize=10, color='#1A1A2E',
                      bg=None, bold=False, align='left'):
    """Rysuje tekst jako PNG (matplotlib) na canvas ReportLab — gwarantuje polskie znaki."""
    import io as _iocd
    from PIL import Image as _PILcd
    DPI = 220
    W_IN = max(0.5, width_pt / 72.0)
    H_IN = max(0.25, fontsize / 72.0 * 2.8)
    fw = 'bold' if bold else 'normal'
    ha = 'center' if align == 'center' else 'left'
    x0 = 0.5 if align == 'center' else 0.01
    bg_c = bg if bg else '#FFFFFF00'
    use_alpha = bg is None
    fig = plt.figure(figsize=(W_IN, H_IN), dpi=DPI)
    if use_alpha:
        fig.patch.set_alpha(0)
    else:
        fig.patch.set_facecolor(bg)
    ax = fig.add_axes([0, 0, 1, 1])
    if use_alpha:
        ax.patch.set_alpha(0)
    else:
        ax.set_facecolor(bg)
    ax.axis('off')
    ax.text(x0, 0.5, str(tekst), fontsize=fontsize, fontweight=fw,
            color=color, ha=ha, va='center', transform=ax.transAxes)
    buf = _iocd.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI,
                facecolor='none' if use_alpha else bg,
                edgecolor='none', bbox_inches='tight', pad_inches=0.01)
    plt.close(fig)
    buf.seek(0)
    img = _PILcd.open(buf).convert('RGBA')
    iw, ih = img.size
    h_pt = (ih / DPI) * 72
    w_pt = (iw / DPI) * 72
    buf2 = _iocd.BytesIO()
    img.save(buf2, 'PNG')
    buf2.seek(0)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(buf2), x, y - h_pt * 0.75, width=w_pt, height=h_pt,
                mask='auto')

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

    # Biale tlo
    c.setFillColor(colors.HexColor('#FFFFFF'))
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Bardzo subtelny glow gorny lewy
    for i in range(5):
        alpha = max(0.0, 0.04 - i*0.007)
        try: c.setFillColorRGB(*hex2rgb(ACC_PURPLE), alpha=alpha)
        except: pass
        c.circle(0, h, 100 + i*35, fill=1, stroke=0)

    # HEADER
    c.setFillColor(colors.HexColor('#FAFAFA'))
    c.rect(0, h-34, w, 34, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor('#E8E8F0')); c.setLineWidth(0.5)
    c.line(0, h-34, w, h-34)
    # 3-kolorowa linia akcentowa na samej gorze
    c.setFillColor(colors.HexColor(ACC_PURPLE)); c.rect(0, h-2, w*0.45, 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_CYAN));   c.rect(w*0.45, h-2, w*0.30, 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_GOLD));   c.rect(w*0.75, h-2, w*0.25, 2, fill=1, stroke=0)
    # Logo
    c.setFont(FB, 8.5); c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.drawString(14, h-22, "EDUVIA")
    c.setFont(FN, 7); c.setFillColor(colors.HexColor(TXT_MUTED))
    c.drawString(60, h-22, "AI PREMIUM NOTES")
    # Numer strony
    c.setFont(FN, 7.5); c.setFillColor(colors.HexColor(TXT_MUTED))
    c.drawRightString(w-14, h-22, "str. " + str(doc.page))

    # FOOTER
    c.setFillColor(colors.HexColor('#FAFAFA'))
    c.rect(0, 0, w, 22, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor('#E8E8F0')); c.setLineWidth(0.5)
    c.line(0, 22, w, 22)
    # Linia kolor na dole
    c.setFillColor(colors.HexColor(ACC_PURPLE)); c.rect(0, 0, w, 1.5, fill=1, stroke=0)
    c.setFont(FN, 6.5); c.setFillColor(colors.HexColor(TXT_MUTED))
    c.drawCentredString(w/2, 7, "Eduvia AI  |  eduvia.pl")

    c.restoreState()

# ============================================================
# OKŁADKA — PREMIUM REDESIGN
# ============================================================
def draw_cover(c, tytul, podtytul, klasa):
    w, h = PW, PH

    # TLO: glebokie granatowe
    c.setFillColor(colors.HexColor('#06060F'))
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Fioletowy glow - centrum
    for i in range(20):
        alpha = max(0.0, 0.22 - i*0.011)
        try: c.setFillColorRGB(*hex2rgb(ACC_PURPLE), alpha=alpha)
        except: pass
        c.circle(w*0.5, h*0.5, 60 + i*28, fill=1, stroke=0)

    # Zielony glow - prawy rog
    for i in range(12):
        alpha = max(0.0, 0.14 - i*0.011)
        try: c.setFillColorRGB(*hex2rgb(ACC_CYAN), alpha=alpha)
        except: pass
        c.circle(w*0.92, h*0.18, 40 + i*20, fill=1, stroke=0)

    # Zloty glow - lewy dol
    for i in range(10):
        alpha = max(0.0, 0.10 - i*0.009)
        try: c.setFillColorRGB(*hex2rgb(ACC_GOLD), alpha=alpha)
        except: pass
        c.circle(w*0.08, h*0.82, 35 + i*16, fill=1, stroke=0)

    # Siatka - bardzo subtelna
    try: c.setStrokeColorRGB(*hex2rgb(ACC_PURPLE), alpha=0.06)
    except: c.setStrokeColor(colors.HexColor('#1A1A3A'))
    c.setLineWidth(0.3)
    for x in range(0, int(w)+1, 36): c.line(x, 0, x, h)
    for y in range(0, int(h)+1, 36): c.line(0, y, w, y)

    # GORNY PASEK brand
    c.setFillColor(colors.HexColor('#0A0A1E'))
    c.rect(0, h-50, w, 50, fill=1, stroke=0)
    # Kolorowe paski
    c.setFillColor(colors.HexColor(ACC_PURPLE)); c.rect(0, h-50, w*0.5, 2.5, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_CYAN));   c.rect(w*0.5, h-50, w*0.3, 2.5, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_GOLD));   c.rect(w*0.8, h-50, w*0.2, 2.5, fill=1, stroke=0)
    # Nazwa
    c.setFont(FB, 11); c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.drawString(16, h-33, "EDUVIA")
    c.setFont(FN, 8); c.setFillColor(colors.HexColor('#666699'))
    c.drawString(70, h-33, "AI PREMIUM NOTES")
    # Poziom badge - prawy
    c.setFillColor(colors.HexColor('#151530'))
    c.roundRect(w-120, h-46, 106, 22, 11, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor(ACC_PURPLE)); c.setLineWidth(1)
    c.roundRect(w-120, h-46, 106, 22, 11, fill=0, stroke=1)
    c.setFont(FB, 7.5); c.setFillColor(colors.HexColor(ACC_PURPLE))
    c.drawCentredString(w-67, h-37, "POZIOM: " + klasa.upper())

    # DIVIDER
    c.setStrokeColor(colors.HexColor(ACC_PURPLE)); c.setLineWidth(1.5)
    c.line(40, h*0.63, w-40, h*0.63)
    c.setStrokeColor(colors.HexColor(ACC_CYAN)); c.setLineWidth(0.8)
    c.line(40, h*0.63-5, w*0.6, h*0.63-5)

    # TYTUL - duzy bialy przez matplotlib
    words = tytul.split()
    if len(tytul) > 22 and len(words) > 2:
        mid = len(words)//2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        _canvas_draw_text(c, line1, 40, h*0.555, w-80, fontsize=40, color='white', bold=True, align='center')
        _canvas_draw_text(c, line2, 40, h*0.475, w-80, fontsize=40, color='white', bold=True, align='center')
        ty = h*0.40
    else:
        _canvas_draw_text(c, tytul, 40, h*0.52, w-80, fontsize=40, color='white', bold=True, align='center')
        ty = h*0.44

    # PODTYTUL
    _canvas_draw_text(c, podtytul, 40, ty - 4, w-80, fontsize=13, color=ACC_CYAN, align='center')

    # DATA
    c.setFont(FN, 9); c.setFillColor(colors.HexColor('#555577'))
    c.drawCentredString(w/2, ty - 28, datetime.now().strftime('%d.%m.%Y'))

    # DOLNY PASEK
    c.setFillColor(colors.HexColor(ACC_PURPLE)); c.rect(0, 0, w, 9, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_CYAN));   c.rect(w*0.38, 0, w*0.24, 9, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(ACC_GOLD));   c.rect(w*0.78, 0, w*0.22, 9, fill=1, stroke=0)

    c.showPage()

# ============================================================
# NOWE FLOWABLES — PREMIUM REDESIGN
# ============================================================

# ────────────────────────────────────────────────────────
# UI elementy — Table+Paragraph (polskie znaki 100%)
# ────────────────────────────────────────────────────────
def make_label(text, accent=None, width=515):
    acc = accent or ACC_PURPLE
    s = ParagraphStyle('lbl', fontName=FB, fontSize=8,
                       textColor=colors.white, leading=12)
    t = Table([[Paragraph(text, s)]], colWidths=[width])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor(acc)),
        ('TOPPADDING',    (0,0),(-1,-1), 6),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('LEFTPADDING',   (0,0),(-1,-1), 10),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
        ('LINEABOVE',     (0,0),(-1, 0), 0.8, colors.HexColor('#E0E0EE')),
    ]))
    return t

def make_section_header(number, text, accent=None, width=515):
    acc = accent or ACC_PURPLE
    sn = ParagraphStyle('shn', fontName=FB, fontSize=10,
                        textColor=colors.white, alignment=1, leading=14)
    st2 = ParagraphStyle('sht', fontName=FB, fontSize=12,
                         textColor=colors.HexColor('#1A1A2E'), leading=16)
    t = Table([[Paragraph('%02d'%number, sn), Paragraph(text, st2)]],
              colWidths=[36, width-36])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,-1),  colors.HexColor(acc)),
        ('BACKGROUND',    (1,0),(-1,-1), colors.HexColor('#F5F4FF')),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 12),
        ('BOTTOMPADDING', (0,0),(-1,-1), 12),
        ('LEFTPADDING',   (0,0),(0,-1),  4),
        ('LEFTPADDING',   (1,0),(-1,-1), 14),
        ('RIGHTPADDING',  (0,0),(-1,-1), 10),
    ]))
    return t

def make_timeline_item(rok, opis, width=515):
    sr = ParagraphStyle('tlr', fontName=FB, fontSize=10,
                        textColor=colors.HexColor(ACC_PURPLE), leading=14)
    so = ParagraphStyle('tlo', fontName=FN, fontSize=9,
                        textColor=colors.HexColor('#2D3436'), leading=14)
    t = Table([[Paragraph(str(rok), sr), Paragraph(opis, so)]],
              colWidths=[65, width-65])
    t.setStyle(TableStyle([
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
        ('RIGHTPADDING',  (0,0),(-1,-1), 6),
        ('LINEBEFORE',    (0,0),(0,-1),  3, colors.HexColor(ACC_PURPLE)),
    ]))
    return t

def make_mindmap_item(poziom, tekst, width=515):
    indent = poziom * 28
    avail  = width - indent
    if poziom == 0:
        s = ParagraphStyle('mm0', fontName=FB, fontSize=10,
                            textColor=colors.white, leading=14)
        t = Table([[Paragraph(tekst, s)]], colWidths=[avail])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor(ACC_PURPLE)),
            ('TOPPADDING',    (0,0),(-1,-1), 8),('BOTTOMPADDING',(0,0),(-1,-1), 8),
            ('LEFTPADDING',   (0,0),(-1,-1), 14),('RIGHTPADDING', (0,0),(-1,-1), 14),
        ]))
    elif poziom == 1:
        s = ParagraphStyle('mm1', fontName=FB, fontSize=9,
                            textColor=colors.HexColor('#1A1A2E'), leading=13)
        t = Table([[Paragraph('▸  '+tekst, s)]], colWidths=[avail])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor('#F2F0FF')),
            ('TOPPADDING',    (0,0),(-1,-1), 6),('BOTTOMPADDING',(0,0),(-1,-1), 6),
            ('LEFTPADDING',   (0,0),(-1,-1), 14),
            ('BOX',           (0,0),(-1,-1), 1, colors.HexColor(ACC_PURPLE)),
        ]))
    else:
        s = ParagraphStyle('mm2', fontName=FN, fontSize=8.5,
                            textColor=colors.HexColor('#2D3436'), leading=13)
        t = Table([[Paragraph('•  '+tekst, s)]], colWidths=[avail])
        t.setStyle(TableStyle([
            ('TOPPADDING',    (0,0),(-1,-1), 4),('BOTTOMPADDING',(0,0),(-1,-1), 4),
            ('LEFTPADDING',   (0,0),(-1,-1), 14),
        ]))
    if indent > 0:
        outer = Table([['', t]], colWidths=[indent, avail])
        outer.setStyle(TableStyle([
            ('TOPPADDING',    (0,0),(-1,-1), 0),('BOTTOMPADDING',(0,0),(-1,-1), 0),
            ('LEFTPADDING',   (0,0),(-1,-1), 0),('RIGHTPADDING', (0,0),(-1,-1), 0),
        ]))
        return outer
    return t


class SectionHeader(Flowable):
    def __init__(self, number, text, accent=None, width=515):
        super().__init__()
        self.number = number; self.text = text
        self.accent = accent or ACC_PURPLE
        self.width = width; self.height = 44

    def draw(self):
        c = self.canv; W = self.width; H = self.height
        acc = self.accent

        # Tlo - bardzo jasny odcien akcentu
        c.setFillColor(colors.HexColor('#F5F4FF'))
        try:
            r,g,b = hex2rgb(acc)
            c.setFillColorRGB(r, g, b, alpha=0.06)
        except:
            pass
        c.roundRect(0, 0, W, H, 7, fill=1, stroke=0)

        # Lewy gruby pasek koloru
        c.setFillColor(colors.HexColor(acc))
        c.roundRect(0, 0, 5, H, 3, fill=1, stroke=0)

        # Kolo z numerem
        cx, cy = 27, H//2

        c.setFillColor(colors.HexColor(acc))
        c.circle(cx, cy, 13, fill=1, stroke=0)
        c.setFont(FB, 9)
        c.setFillColor(colors.white)
        c.drawCentredString(cx, cy-3, "%02d" % self.number)

        # Tytul
        _canvas_draw_text(c, self.text[:65], 50, cy + 4, W - 60,
                          fontsize=12, color='#1A1A2E', bold=True)

        # Linia po prawej
        try:
            r,g,b = hex2rgb(acc)
            c.setStrokeColorRGB(r, g, b, alpha=0.25)
        except:
            c.setStrokeColor(colors.HexColor('#DFE6E9'))
        c.setLineWidth(1)
        est_tw = len(self.text[:65]) * 7
        if 52 + est_tw + 12 < W - 10:
            c.line(52 + est_tw + 12, cy, W - 10, cy)



class ConceptCard(Flowable):
    def __init__(self, pojecie, definicja, idx, width):
        super().__init__()
        self.pojecie = pojecie; self.definicja = definicja
        self.idx = idx; self.width = width
        nlines = max(2, len(definicja)//50 + 1)
        self.height = 56 + nlines * 13

    def draw(self):
        c = self.canv; W = self.width; H = self.height
        ACCENTS = [ACC_PURPLE, ACC_CYAN, ACC_GOLD, ACC_ORANGE]
        BGS = ['#F2F0FF', '#EDFFF8', '#FFF8E8', '#FFF2F0']
        acc = ACCENTS[self.idx % 4]
        bg  = BGS[self.idx % 4]

        # Tlo karty
        c.setFillColor(colors.HexColor(bg))
        c.roundRect(0, 2, W, H-4, 10, fill=1, stroke=0)

        # Gorny pasek koloru
        c.setFillColor(colors.HexColor(acc))
        c.roundRect(0, H-24, W, 24, 10, fill=1, stroke=0)
        c.rect(0, H-18, W, 10, fill=1, stroke=0)

        # Pojecie - BIALY na kolorowym pasku
        p = self.pojecie[:36] + "..." if len(self.pojecie) > 36 else self.pojecie
        _canvas_draw_text(c, p, 10, H - 10, W - 20,
                          fontsize=9, color='white', bold=True)

        # Definicja - renderuj przez matplotlib żeby wzory LaTeX działały
        import re as _re2, io as _io2
        defn_raw = self.definicja[:220]
        # Czy zawiera LaTeX?
        if '$' in defn_raw:
            try:
                png = _render_text_png(defn_raw, W - 16, fontsize=8, color='#2D3436', bg=bg)
                if png:
                    from PIL import Image as _PIL2
                    pil = _PIL2.open(_io2.BytesIO(png))
                    iw, ih = pil.size
                    scale = (W - 16) / (iw / 200 * 72)
                    h_pt = min((ih / 200 * 72) * scale, H - 32)
                    c.drawImage(ImageReader(_io2.BytesIO(png)), 8, 4, width=W-16, height=h_pt)
                else:
                    raise Exception("no png")
            except:
                # fallback - zwykły tekst bez wzorów
                defn = _re2.sub(r'\$([^$]*)\$', lambda m: m.group(1), defn_raw)
                defn = defn.replace('\\frac{','(').replace('}{',')/(').replace('}',')')
                defn = defn.replace('\\cdot','·').replace('\\times','×').replace('\\','').replace('  ',' ')
                _canvas_draw_text(c, defn[:180], 8, H - 32, W - 16, fontsize=8, color='#2D3436', bg=bg)
        else:
            _canvas_draw_text(c, defn_raw[:180], 8, H - 32, W - 16,
                              fontsize=8, color='#2D3436', bg=bg)



class TimelineItem(Flowable):
    def __init__(self, rok, opis, is_last, width):
        super().__init__()
        self.rok = str(rok); self.opis = opis
        self.is_last = is_last; self.width = width
        self.height = 36 + max(1, len(opis)//60+1)*13

    def draw(self):
        c = self.canv; H = self.height
        # Linia pionowa
        if not self.is_last:
            try: c.setStrokeColorRGB(*hex2rgb(ACC_PURPLE), alpha=0.25)
            except: c.setStrokeColor(colors.HexColor('#DFE6E9'))
            c.setLineWidth(2); c.line(24, -6, 24, 0)
        # Kolo
        try: c.setFillColorRGB(*hex2rgb(ACC_PURPLE), alpha=0.15)
        except: c.setFillColor(colors.HexColor('#F0EEFF'))
        c.circle(24, H-16, 9, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(ACC_PURPLE))
        c.circle(24, H-16, 5, fill=1, stroke=0)
        # Rok
        _canvas_draw_text(c, self.rok, 40, H - 12, 60,
                          fontsize=10, color=ACC_PURPLE, bold=True)
        # Opis
        _canvas_draw_text(c, self.opis, 40, H - 28, self.width - 55,
                          fontsize=9, color='#2D3436')



class MindMapItem(Flowable):
    def __init__(self, poziom, tekst, width):
        super().__init__()
        self.poziom = poziom; self.tekst = tekst; self.width = width
        self.height = 36 if poziom==0 else 30 if poziom==1 else 26

    def draw(self):
        c = self.canv; indent = self.poziom*30; avail = self.width-indent; H = self.height
        if self.poziom == 0:
            c.setFillColor(colors.HexColor(ACC_PURPLE))
            c.roundRect(indent, 2, avail, H-4, 6, fill=1, stroke=0)
            _canvas_draw_text(c, self.tekst[:62], indent + 12, H - 5, avail - 24,
                              fontsize=11, color='white', bold=True)
        elif self.poziom == 1:
            c.setFillColor(colors.HexColor('#F2F0FF'))
            c.roundRect(indent, 2, avail, H-4, 5, fill=1, stroke=0)
            c.setStrokeColor(colors.HexColor(ACC_PURPLE)); c.setLineWidth(1)
            c.roundRect(indent, 2, avail, H-4, 5, fill=0, stroke=1)
            c.setFillColor(colors.HexColor(ACC_PURPLE))
            c.roundRect(indent+5, H//2-3, 5, 6, 2, fill=1, stroke=0)
            _canvas_draw_text(c, '  ' + self.tekst[:72], indent + 14, H - 5, avail - 24,
                              fontsize=9.5, color='#1A1A2E', bold=True)
        else:
            c.setFillColor(colors.HexColor(ACC_CYAN))
            c.circle(indent+8, H//2, 4, fill=1, stroke=0)
            _canvas_draw_text(c, self.tekst[:82], indent + 20, H - 4, self.width - indent - 28,
                              fontsize=9, color='#2D3436')



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
    def __init__(self, text, accent=None, width=515):
        super().__init__()
        self.text = text
        self.accent = accent or ACC_PURPLE
        self.width = width; self.height = 26

    def draw(self):
        c = self.canv; W = self.width; acc = self.accent
        c.setStrokeColor(colors.HexColor('#E0E0EE'))
        c.setLineWidth(0.8); c.line(0, 11, W, 11)
        est_w = len(self.text) * 5.5 + 20
        c.setFillColor(colors.HexColor(acc))
        c.roundRect(0, 3, est_w, 17, 4, fill=1, stroke=0)
        _canvas_draw_text(c, self.text, 5, 16, est_w - 6,
                          fontsize=7.5, color='#FFFFFF', bold=True)




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
    # Konwertuj LaTeX na czytelny tekst w kartach
    import re as _re_def
    defn_clean = _re_def.sub(r'\\\$', lambda m: m.group(1), definicja)
    defn_clean = defn_clean.replace('\\frac{', '(').replace('}{', ')/(')
    defn_clean = defn_clean.replace('\\cdot', '·').replace('\\times', '×')
    defn_clean = defn_clean.replace('\\rightarrow', '→').replace('\\to', '→')
    defn_clean = defn_clean.replace('\\int', '∫').replace('\\sum', 'Σ')
    defn_clean = defn_clean.replace('\\alpha', 'α').replace('\\beta', 'β').replace('\\gamma', 'γ')
    defn_clean = defn_clean.replace('\\delta', 'δ').replace('\\Delta', 'Δ').replace('\\pi', 'π')
    defn_clean = defn_clean.replace('\\infty', '∞').replace('\\pm', '±').replace('\\sqrt', '√')
    defn_clean = _re_def.sub(r'\\[a-zA-Z]+', '', defn_clean)
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


PROMPT = """Jestes doswiadczonym nauczycielem i autorem materialow edukacyjnych.
Tworzysz PROFESJONALNA notatke premium dla ucznia na poziomie: {klasa}
TEMAT: {temat}

{wlasne_blok}

Zwroc TYLKO czysty JSON (bez markdown, bez backticks, bez komentarzy).

=== WZORY MATEMATYCZNE ===
Format matplotlib mathtext. ZAWSZE otaczaj wzory $ ... $
Przyklady: "$\\frac{{a}}{{b}} + \\frac{{c}}{{d}} = \\frac{{{{ad+bc}}}}{{{{bd}}}}$"
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
- kluczowe_pojecia: {n_pojecia}, KAZDE z intuicja + przykladem
- sekcje: DOKLADNIE {n_sekcje}, KAZDA z przykladem krok-po-kroku
- bledy_uczniow: DOKLADNIE {n_bledy}, KAZDY z przykladem
- quiz: DOKLADNIE {n_quiz} pytania
- do_zapamietania: DOKLADNIE {n_zapamietaj}
- Caly tekst PO POLSKU
- KRYTYCZNE: Znaki nowej linii w stringach zapisuj jako \\n (escape)"""


def _build_wlasne_blok(wlasne_instrukcje: str) -> str:
    """Buduje sekcje wlasnych instrukcji do prompta."""
    if not wlasne_instrukcje or not wlasne_instrukcje.strip():
        return ""
    safe = wlasne_instrukcje.strip()
    return (
        "=== WLASNE INSTRUKCJE (NAJWYZSZY PRIORYTET) ===\n"
        "Uczen podal nastepujace instrukcje. MUSISZ je bezwzglednie uwzglednic:\n"
        f"{safe}\n"
        "Dostosuj CALA notatke do powyzszych wskazowek."
    )


# Konfig rozmiaru notatki — mapowanie num_sections -> parametry prompta
SIZE_CONFIG = {
    2: dict(n_pojecia='2',   n_sekcje=2, n_bledy=1, n_quiz=2, n_zapamietaj=3),   # Szybka
    3: dict(n_pojecia='4-5', n_sekcje=3, n_bledy=3, n_quiz=4, n_zapamietaj=5),   # Normalna (default)
    4: dict(n_pojecia='4-5', n_sekcje=4, n_bledy=3, n_quiz=4, n_zapamietaj=5),   # Dokładna
    5: dict(n_pojecia='5-6', n_sekcje=5, n_bledy=3, n_quiz=6, n_zapamietaj=6),   # Mega
}

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
        self.width = width; self.height = 24

    def draw(self):
        c = self.canv; W = self.width
        acc = self.accent
        # Linia pozioma
        try:
            r, g, b = hex2rgb(acc)
            c.setStrokeColorRGB(r, g, b, alpha=0.45)
        except:
            c.setStrokeColor(colors.HexColor(acc))
        c.setLineWidth(1); c.line(0, 10, W, 10)
        # Tło tagu
        est_w = len(self.text) * 5.5 + 18
        c.setFillColor(colors.HexColor(acc))
        c.roundRect(0, 3, est_w, 16, 4, fill=1, stroke=0)
        # Tekst przez matplotlib
        _canvas_draw_text(c, self.text, 4, 14, est_w - 4,
                          fontsize=7.5, color='#FFFFFF', bold=True)


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
    defn_clean = defn_clean.replace('\\frac{', '(').replace('}{', ')/(')
    defn_clean = defn_clean.replace('\\cdot', '·').replace('\\times', '×')
    defn_clean = defn_clean.replace('\\rightarrow', '→').replace('\\to', '→')
    defn_clean = defn_clean.replace('\\int', '∫').replace('\\sum', 'Σ')
    defn_clean = defn_clean.replace('\\alpha', 'α').replace('\\beta', 'β').replace('\\gamma', 'γ')
    defn_clean = defn_clean.replace('\\delta', 'δ').replace('\\Delta', 'Δ').replace('\\pi', 'π')
    defn_clean = defn_clean.replace('\\infty', '∞').replace('\\pm', '±').replace('\\sqrt', '√')
    defn_clean = _re_def.sub(r'\\[a-zA-Z]+', '', defn_clean)
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

    def _get_content_from_gpt(self, temat: str, klasa: str, num_sections: int = 3, wlasne_instrukcje: str = "") -> dict:
        cfg = SIZE_CONFIG.get(num_sections, SIZE_CONFIG[3])
        wlasne_blok = _build_wlasne_blok(wlasne_instrukcje)
        prompt = PROMPT.format(temat=temat, klasa=klasa, wlasne_blok=wlasne_blok, **cfg)
        max_tok = {2: 2500, 3: 4000, 4: 5000, 5: 6500}.get(num_sections, 4000)
        system_msg = (
            "Jestes ekspertem edukacyjnym. Odpowiadasz TYLKO czystym JSON bez zadnych komentarzy. "
            "Wzory TYLKO w formacie $...$. "
            "KRYTYCZNE: Znaki nowej linii w stringach zapisuj jako \\n (escape). "
            "Zero backticks, zero markdown, zero komentarzy."
        )
        if wlasne_instrukcje and wlasne_instrukcje.strip():
            system_msg += (
                " WAZNE: Uzytkownik podal wlasne instrukcje - sa one nadrzedne wobec domyslnego stylu."
                " Musisz je bezwzglednie uwzglednic w tresci notatki."
            )
        r = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7, max_tokens=max_tok,
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
                    # Wzory LaTeX - renderuj przez matplotlib
                    if '$' in s or '\\' in s:
                        png = _render_text_png(s, col_w - 8, 28, fontsize=11,
                                               color=TXT_MAIN, bg=BG_CARD2)
                        if png:
                            from PIL import Image as _PILc; import io as _ioc
                            _pc = _PILc.open(_ioc.BytesIO(png))
                            return RLImage(_ioc.BytesIO(png), width=col_w-8,
                                          height=_pc.size[1]/150*72)
                    # Zwykły tekst - zawsze Paragraph z DejaVu (polskie znaki!)
                    return Paragraph(st(_l2u(s)), ParagraphStyle("tc", fontName=FN,
                        fontSize=10, textColor=colors.HexColor('#1A1A2E'), alignment=1))
                safe_w = [[_cell(c) for c in row] for row in wiersze]
                def _nagl_cell(n, cw):
                    txt = _l2u(n)
                    return Paragraph(st(txt), ParagraphStyle("th", fontName=FB, fontSize=10, textColor=C_W, alignment=1))
                nagl_cells = [_nagl_cell(n, col_w) for n in nagl]
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
            story.append(Spacer(1, 30))
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

                # Opcje - przez matplotlib (polskie znaki)
                for op in opcje:
                    ltr = op[0] if op else '?'
                    is_correct = (ltr == odp)
                    bg_op = '#F0FFF8' if is_correct else bg_quiz
                    col_op = ACC_CYAN if is_correct else '#2D3436'
                    op_clean = _l2u(str(op))
                    from PIL import Image as _PILop; import io as _ioop
                    _png_op = _render_text_png('  ' + op_clean, W-4, 26,
                                               fontsize=11, color=col_op, bg=bg_op,
                                               bold=is_correct)
                    if _png_op:
                        _pil_op = _PILop.open(_ioop.BytesIO(_png_op))
                        t_op_img = RLImage(_ioop.BytesIO(_png_op), width=W-4,
                                           height=_pil_op.size[1]/150*72)
                        t_op = Table([[t_op_img]], colWidths=[W])
                        t_op.setStyle(TableStyle([
                            ('BACKGROUND', (0,0),(-1,-1), colors.HexColor(bg_op)),
                            ('TOPPADDING', (0,0),(-1,-1), 4),
                            ('BOTTOMPADDING',(0,0),(-1,-1), 4),
                            ('LEFTPADDING', (0,0),(-1,-1), 0),
                            ('RIGHTPADDING',(0,0),(-1,-1), 4),
                            ('LINEBEFORE',  (0,0),(0,-1), 3,
                             colors.HexColor(ACC_CYAN if is_correct else '#DFE6E9')),
                        ]))
                    else:
                        fw_op = FB if is_correct else FN
                        s_op = ParagraphStyle('op_'+ltr, fontName=fw_op, fontSize=11,
                                              textColor=colors.HexColor(col_op), leading=16)
                        t_op = Table([[Paragraph('  '+st(op_clean), s_op)]], colWidths=[W])
                        t_op.setStyle(TableStyle([
                            ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(bg_op)),
                            ('TOPPADDING',(0,0),(-1,-1), 8),('BOTTOMPADDING',(0,0),(-1,-1), 8),
                            ('LEFTPADDING',(0,0),(-1,-1), 4),('RIGHTPADDING',(0,0),(-1,-1), 8),
                            ('LINEBEFORE',(0,0),(0,-1), 3,
                             colors.HexColor(ACC_CYAN if is_correct else '#DFE6E9')),
                        ]))
                    story.append(t_op)
                    story.append(Spacer(1, 3))

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

        # ── ZAMKNIĘCIE PREMIUM ─────────────────────────────
        story.append(Spacer(1, 30))
        # Gradient banner zamykający
        from reportlab.platypus.flowables import Flowable as _Flowable
        class _ClosingBanner(_Flowable):
            def __init__(self, w):
                super().__init__(); self.width = w; self.height = 90
            def draw(self):
                c = self.canv; W = self.width; H = self.height
                # Gradient tlo
                for i in range(20):
                    alpha = max(0, 0.18 - i*0.009)
                    try: c.setFillColorRGB(*hex2rgb(ACC_PURPLE), alpha=alpha)
                    except: c.setFillColor(colors.HexColor(ACC_PURPLE))
                    c.roundRect(0, H - i*5, W, 5+i*5, 8, fill=1, stroke=0)
                # Pasek akcentowy
                c.setFillColor(colors.HexColor(ACC_PURPLE)); c.rect(0, H-4, W, 4, fill=1, stroke=0)
                c.setFillColor(colors.HexColor(ACC_CYAN)); c.rect(W*0.4, H-4, W*0.3, 4, fill=1, stroke=0)
                c.setFillColor(colors.HexColor(ACC_GOLD)); c.rect(W*0.8, H-4, W*0.2, 4, fill=1, stroke=0)
                # Tekst
                _canvas_draw_text(c, "EDUVIA AI PREMIUM NOTES", W*0.05, H - 18, W*0.9,
                                  fontsize=11, color=ACC_PURPLE, bold=True, align='center')
                _canvas_draw_text(c, "Notatka wygenerowana przez AI • eduvia.pl", W*0.05, H - 42, W*0.9,
                                  fontsize=9, color=TXT_MUTED, align='center')
                # Gwiazdki dekoracyjne
                for xi, col in [(0.15, ACC_CYAN), (0.5, ACC_GOLD), (0.85, ACC_PURPLE)]:
                    c.setFillColor(colors.HexColor(col))
                    c.circle(W*xi, H*0.22, 5, fill=1, stroke=0)
        story.append(_ClosingBanner(W))

        # Build PDF
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=44, rightMargin=44,
                                topMargin=55, bottomMargin=35)
        doc.build(story, onFirstPage=add_page_bg, onLaterPages=add_page_bg)
        return buf.getvalue()

    def generate_pdf(self, temat: str, klasa: str = "liceum", num_sections: int = 3, wlasne_instrukcje: str = "") -> str:
        print(f"[Eduvia] Generuje: '{temat}' | {klasa}")
        data = self._get_content_from_gpt(temat, klasa, num_sections, wlasne_instrukcje)
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