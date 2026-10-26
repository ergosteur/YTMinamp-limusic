#!/usr/bin/python3
"""YTMinamp Green: a classic Winamp 2.x skin, green on near-black, drawn procedurally.

Flat, modern panels: a near-black body and black titlebars and player bar, a round white play
button with a black glyph, green slider fills, and a green dot under shuffle and repeat when
they're on. Everything is drawn here from code (flat panels, anti-aliased shapes, hinted system
sans lettering, small pixel fonts for text.bmp); the About spot holds the app's own icon
(src-tauri/icons/icon.png) recoloured green.

    /usr/bin/python3 -I gen_skin.py            # build
    /usr/bin/python3 -I gen_skin.py --list     # theme names

Writes out/<theme>/*.bmp + text files, YTMinamp-Green.wsz and preview-<theme>.png beside this file.
"""

import os
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skins/genex_wacup.py, which finishes each .wsz
import genex_wacup  # noqa: E402

ICON = os.path.join(HERE, os.pardir, os.pardir, "src-tauri", "icons", "icon.png")  # the app's icon
OUT_ROOT = os.path.join(HERE, "out")
OUT = OUT_ROOT  # set per theme

SEP = (255, 0, 255)  # gen.bmp letter separators (never shown)

FONT_DIRS = ("/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.local/share/fonts"))


def find_font(*names):
    """The first of these font files found under the usual font folders."""
    for name in names:
        for root in FONT_DIRS:
            for d, subdirs, files in sorted(os.walk(root)):
                subdirs.sort()
                if name in files:
                    return os.path.join(d, name)
    raise SystemExit(f"none of these fonts is installed: {', '.join(names)}")


ADW = find_font("AdwaitaSans-Regular.ttf")  # Adwaita Sans: variable, an Inter derivative
LIBERATION = find_font("LiberationSans-Regular.ttf", "DejaVuSans.ttf")  # the previews' Arial stand-in


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexs(c):
    return "#%02X%02X%02X" % tuple(c)


# ------------------------------------------------------------------------------------------
# Themes
# ------------------------------------------------------------------------------------------
# Keys: bg (window body), bar_top/bar (titlebar gradient), bar_line (hairline under bars),
# band_y/band_top/band/band_line (the "player bar" behind the transport), panel/panel_line
# (displays: also text.bmp's and the analyzer's background), text/text2/text3 (primary,
# secondary, dim), accent/accent_hi, track (slider rails), knob (slider thumbs),
# play (round play button colours, or None for a plain glyph), seek ('line' or 'wave'),
# btn/btn_fg (pill buttons), hover (pressed highlight), fonts, playlist colours.

THEMES = {
    "green": dict(
        name="Green", wsz="YTMinamp-Green",
        title="YTMinamp", eq_title="Equalizer", pl_title="Queue", gen_title="NOW PLAYING",
        font=(ADW, "Bold"), font_bold=(ADW, "Bold"), digit_font=(ADW, "SemiBold"),
        bg="#121212", bar_top="#000000", bar="#000000", bar_line=None, bar_dim="#000000",
        band_y=84, band_top="#000000", band="#000000", band_line=None,
        panel="#1f1f1f", panel_line=None, radius=5,
        text="#ffffff", text2="#b3b3b3", text3="#535353", title_dim="#a7a7a7",
        accent="#2bd16a", accent_hi="#52e08b", track="#4d4d4d", knob="#ffffff", knob_hi="#ffffff",
        knob_r=4.5, digit_size=13, pill_fg="#000000",
        play=("#ffffff", "#000000", "#cfcfcf"), icon="#b3b3b3", icon_pressed="#ffffff",
        skip="bar", seek="line", seek_rows=(4, 2), tail=True,
        btn="#2a2a2a", btn_fg="#ffffff", btn_pressed="#3e3e3e", hover="#2a2a2a",
        toggle_on="dot",
        pl=dict(NormalBG="#121212", Normal="#B3B3B3", Current="#2BD16A", SelectedBG="#2A2A2A"),
        vis=["#52e08b", "#2bd16a", "#1c9a4c", "#0f5a2c"],
        emblem=("#12793a", "#36d873"),
    ),
}

T = {}


def setup_theme(key):
    global T, OUT
    raw = dict(THEMES[key])
    raw["key"] = key
    for k, v in list(raw.items()):
        if isinstance(v, str) and v.startswith("#") and len(v) == 7:
            raw[k] = hexc(v)
        elif isinstance(v, tuple) and v and isinstance(v[0], str) and v[0].startswith("#"):
            raw[k] = tuple(hexc(c) for c in v)
    raw["vis"] = [hexc(c) for c in raw["vis"]]
    raw.setdefault("title_fg", raw["text"])
    raw.setdefault("bar_icon", raw["text2"])
    T = raw
    OUT = os.path.join(OUT_ROOT, key)
    os.makedirs(OUT, exist_ok=True)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(stops, t):
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(n - 1, int(t * n))
    return lerp(stops[i], stops[i + 1], t * n - i)


def is_light():
    return sum(T["bg"]) > 384


# ------------------------------------------------------------------------------------------
# Canvas helpers (numpy, H x W x 3, int) and anti-aliased masks
# ------------------------------------------------------------------------------------------


def new(w, h, col=(0, 0, 0)):
    a = np.zeros((h, w, 3), dtype=np.int32)
    a[:, :] = col
    return a


def rect(a, x, y, w, h, col):
    if w > 0 and h > 0:
        a[y:y + h, x:x + w] = col


def px(a, x, y, col):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = col


def vgrad_fill(a, x, y, w, h, top, bot):
    for r in range(h):
        a[y + r, x:x + w] = lerp(top, bot, r / max(1, h - 1))


SS = 4


def mask(w, h, fn):
    im = Image.new("L", (w * SS, h * SS), 0)
    fn(ImageDraw.Draw(im), SS)
    return np.asarray(im.resize((w, h), Image.BOX), dtype=np.float32) / 255.0


def paint(a, x, y, m, col, alpha=1.0):
    h, w = m.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(a.shape[1], x + w), min(a.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    mm = (m[y0 - y:y1 - y, x0 - x:x1 - x] * alpha)[..., None]
    c = np.asarray(col, dtype=np.float32)
    if c.ndim == 3:
        c = c[y0 - y:y1 - y, x0 - x:x1 - x]
    reg = a[y0:y1, x0:x1].astype(np.float32)
    a[y0:y1, x0:x1] = np.round(reg * (1 - mm) + c * mm).astype(np.int32)


def rrect(a, x, y, w, h, r, col, alpha=1.0):
    """Anti-aliased rounded rectangle, integer box."""
    if w <= 0 or h <= 0:
        return
    r = min(r, w / 2, h / 2)
    m = mask(w, h, lambda d, S: d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=r * S, fill=255))
    paint(a, x, y, m, col, alpha)


def panel(a, x, y, w, h, r=None, col=None, line=None):
    r = T["radius"] if r is None else r
    col = T["panel"] if col is None else col
    line = T["panel_line"] if line is None else line
    if line:
        rrect(a, x - 1, y - 1, w + 2, h + 2, r + 1, line)
        # keep the inner box exactly the panel colour (text.bmp's cells sit on it)
    rrect(a, x, y, w, h, r, col)


def disc(a, cx, cy, r, col, alpha=1.0):
    """Anti-aliased disc centred at (cx, cy) in pixel-edge coordinates."""
    x0, y0 = int(np.floor(cx - r)) - 1, int(np.floor(cy - r)) - 1
    w = h = int(np.ceil(2 * r)) + 3
    m = mask(w, h, lambda d, S: d.ellipse(((cx - r - x0) * S, (cy - r - y0) * S, (cx + r - x0) * S - 1,
                                           (cy + r - y0) * S - 1), fill=255))
    paint(a, x0, y0, m, col, alpha)


def poly(a, pts, col, alpha=1.0):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = int(np.floor(min(xs))) - 1, int(np.floor(min(ys))) - 1
    w, h = int(np.ceil(max(xs))) - x0 + 2, int(np.ceil(max(ys))) - y0 + 2
    m = mask(w, h, lambda d, S: d.polygon([((p[0] - x0) * S, (p[1] - y0) * S) for p in pts], fill=255))
    paint(a, x0, y0, m, col, alpha)


def frect(a, x0, y0, x1, y1, col, r=0.0):
    """Anti-aliased (sub-pixel) rectangle from (x0, y0) to (x1, y1), optional corner radius."""
    bx, by = int(np.floor(x0)) - 1, int(np.floor(y0)) - 1
    w, h = int(np.ceil(x1)) - bx + 2, int(np.ceil(y1)) - by + 2
    m = mask(w, h, lambda d, S: d.rounded_rectangle(((x0 - bx) * S, (y0 - by) * S, (x1 - bx) * S - 1,
                                                     (y1 - by) * S - 1), radius=r * S, fill=255))
    paint(a, bx, by, m, col)


def strokes(a, x, y, w, h, fn, col, alpha=1.0):
    """Paints whatever fn(draw, S) draws (in canvas-local coordinates from (x, y))."""
    paint(a, x, y, mask(w, h, fn), col, alpha)


def save(a, name):
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, name))
    return img


# ------------------------------------------------------------------------------------------
# Lettering: the system sans (hinted, anti-aliased) and pixel fonts for text.bmp
# ------------------------------------------------------------------------------------------

_fonts = {}


def font(spec, size):
    key = (spec, size)
    if key not in _fonts:
        path, var = spec
        f = ImageFont.truetype(path, size)
        if var:
            f.set_variation_by_name(var)
        _fonts[key] = f
    return _fonts[key]


def text_width(s, f):
    return f.getlength(s)


def ttext(a, s, f, x, base, col, align="l", alpha=1.0):
    """TrueType text with its baseline on row `base`; x is the left edge or the centre."""
    if not s:
        return
    adv = f.getlength(s)
    if align == "c":
        x = x - adv / 2
    x = int(round(x))
    l, t, r, b = f.getbbox(s, anchor="ls")
    w, h = r - l + 2, b - t + 2
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((-l + 1, -t + 1), s, font=f, fill=255, anchor="ls")
    m = np.asarray(im, dtype=np.float32) / 255.0
    paint(a, x + l - 1, base + t - 1, m, col, alpha)


def label(a, s, cx, base, col, size=8):
    ttext(a, s, font(T["font_bold"], size), cx, base, col, "c")


def G(*rows):
    return list(rows)


# 5-row font for text.bmp (the readouts; the title itself is drawn by the app in TrueType).
FONT5 = {
    "A": G(".##.", "#..#", "####", "#..#", "#..#"),
    "B": G("###.", "#..#", "###.", "#..#", "###."),
    "C": G(".###", "#...", "#...", "#...", ".###"),
    "D": G("###.", "#..#", "#..#", "#..#", "###."),
    "E": G("####", "#...", "###.", "#...", "####"),
    "F": G("####", "#...", "###.", "#...", "#..."),
    "G": G(".###", "#...", "#.##", "#..#", ".###"),
    "H": G("#..#", "#..#", "####", "#..#", "#..#"),
    "I": G("###", ".#.", ".#.", ".#.", "###"),
    "J": G("...#", "...#", "...#", "#..#", ".##."),
    "K": G("#..#", "#.#.", "##..", "#.#.", "#..#"),
    "L": G("#...", "#...", "#...", "#...", "####"),
    "M": G("#..#", "####", "####", "#..#", "#..#"),
    "N": G("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": G(".##.", "#..#", "#..#", "#..#", ".##."),
    "P": G("###.", "#..#", "###.", "#...", "#..."),
    "Q": G(".##.", "#..#", "#..#", "#.#.", ".#.#"),
    "R": G("###.", "#..#", "###.", "#.#.", "#..#"),
    "S": G(".###", "#...", ".##.", "...#", "###."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#..#", "#..#", "#..#", "#..#", ".##."),
    "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#..#", "#..#", "####", "####", "#..#"),
    "X": G("#..#", "#..#", ".##.", "#..#", "#..#"),
    "Y": G("#.#", "#.#", ".#.", ".#.", ".#."),
    "Z": G("####", "...#", ".##.", "#...", "####"),
    "0": G(".#.", "#.#", "#.#", "#.#", ".#."),
    "1": G(".#.", "##.", ".#.", ".#.", "###"),
    "2": G("##.", "..#", ".#.", "#..", "###"),
    "3": G("##.", "..#", ".#.", "..#", "##."),
    "4": G("#.#", "#.#", "###", "..#", "..#"),
    "5": G("###", "#..", "##.", "..#", "##."),
    "6": G(".##", "#..", "##.", "#.#", ".#."),
    "7": G("###", "..#", ".#.", ".#.", ".#."),
    "8": G(".#.", "#.#", ".#.", "#.#", ".#."),
    "9": G(".#.", "#.#", ".##", "..#", "##."),
    '"': G("#.#", "#.#", "...", "...", "..."),
    "@": G(".##.", "#.##", "#.##", "#...", ".###"),
    "…": G(".....", ".....", ".....", ".....", "#.#.#"),
    ".": G(".", ".", ".", ".", "#"),
    ":": G(".", "#", ".", "#", "."),
    "(": G(".#", "#.", "#.", "#.", ".#"),
    ")": G("#.", ".#", ".#", ".#", "#."),
    "-": G("...", "...", "###", "...", "..."),
    "'": G("#", "#", ".", ".", "."),
    "!": G("#", "#", "#", ".", "#"),
    "_": G("....", "....", "....", "....", "####"),
    "+": G("...", ".#.", "###", ".#.", "..."),
    "\\": G("#..", "#..", ".#.", "..#", "..#"),
    "/": G("..#", "..#", ".#.", "#..", "#.."),
    "[": G("##", "#.", "#.", "#.", "##"),
    "]": G("##", ".#", ".#", ".#", "##"),
    "^": G(".#.", "#.#", "...", "...", "..."),
    "&": G(".#..", "#.#.", ".#..", "#.#.", ".#.#"),
    "%": G("#.#", "..#", ".#.", "#..", "#.#"),
    ",": G("..", "..", "..", ".#", "#."),
    "=": G("...", "###", "...", "###", "..."),
    "$": G(".###", "#.#.", ".##.", ".#.#", "###."),
    "#": G(".#.#", "####", ".#.#", "####", ".#.#"),
    "å": G(".##.", ".##.", "#..#", "####", "#..#"),
    "ö": G("#..#", ".##.", "#..#", "#..#", ".##."),
    "ä": G("#..#", ".##.", "#..#", "####", "#..#"),
    "?": G("###.", "...#", ".##.", "....", ".#.."),
    "*": G("#.#", ".#.", "###", ".#.", "#.#"),
    " ": G("...", "...", "...", "...", "..."),
}

# 3x5 font for the smallest labels.
TINY = {
    "A": G(".#.", "#.#", "###", "#.#", "#.#"),
    "B": G("##.", "#.#", "##.", "#.#", "##."),
    "D": G("##.", "#.#", "#.#", "#.#", "##."),
    "E": G("###", "#..", "##.", "#..", "###"),
    "H": G("#.#", "#.#", "###", "#.#", "#.#"),
    "I": G("###", ".#.", ".#.", ".#.", "###"),
    "K": G("#.#", "#.#", "##.", "#.#", "#.#"),
    "M": G("#.#", "###", "###", "#.#", "#.#"),
    "N": G("##.", "#.#", "#.#", "#.#", "#.#"),
    "O": G(".#.", "#.#", "#.#", "#.#", ".#."),
    "P": G("##.", "#.#", "##.", "#..", "#.."),
    "R": G("##.", "#.#", "##.", "#.#", "#.#"),
    "S": G(".##", "#..", ".#.", "..#", "##."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#.#", "#.#", "#.#", "#.#", "###"),
    "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "Z": G("###", "..#", ".#.", "#..", "###"),
    " ": G("..", "..", "..", "..", ".."),
}
for _c in "0123456789+-.":
    TINY[_c] = FONT5[_c]


def glyph_w(fnt, c):
    return len(fnt[c][0])


def ptext_w(fnt, s, gap=1):
    s = [c for c in s if c in fnt]
    return sum(glyph_w(fnt, c) for c in s) + gap * max(0, len(s) - 1)


def ptext(a, fnt, s, x, y, col, gap=1):
    for c in s:
        if c not in fnt:
            continue
        g = fnt[c]
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    px(a, x + k, y + r, col)
        x += len(g[0]) + gap
    return x


def ptext_c(a, fnt, s, cx, y, col, gap=1):
    ptext(a, fnt, s, cx - ptext_w(fnt, s, gap) // 2, y, col, gap)


# ------------------------------------------------------------------------------------------
# The emblem: the app's icon (red disc, white play mark, yellow bolt), its disc recoloured
# ------------------------------------------------------------------------------------------


def logo_rgba(size):
    """The icon at size x size with its red disc in the theme's emblem colours (dark, light),
    keeping the disc's own shading; the white mark, the bolt and its outline stay as they are."""
    a = np.asarray(Image.open(ICON).convert("RGBA"), dtype=np.float64)
    rgb = a[..., :3] / 255
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    disc_px = (rgb[..., 0] == mx) & (rgb[..., 0] > 0.6) & (rgb[..., 1] < 0.45) & (sat > 0.5)
    t = np.clip((rgb[..., 0] - 0.78) / (0.97 - 0.78), 0, 1)[..., None]
    lo, hi = (np.array(c, np.float64) for c in T["emblem"])
    out = a.copy()
    out[..., :3] = np.where(disc_px[..., None], lo * (1 - t) + hi * t, a[..., :3])
    im = Image.fromarray(np.round(out).astype(np.uint8), "RGBA").resize((size, size), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32)


def put_logo(a, x, y, size):
    rgba = logo_rgba(size)
    paint(a, x, y, rgba[..., 3] / 255.0, rgba[..., :3])


# ------------------------------------------------------------------------------------------
# Backgrounds: the bars and the main window's body column
# ------------------------------------------------------------------------------------------


def bar_rows(h, lit):
    """(h, 1, 3) column of a titlebar of height h."""
    t = new(1, h)
    if lit:
        vgrad_fill(t, 0, 0, 1, h, T["bar_top"], T["bar"])
    else:
        vgrad_fill(t, 0, 0, 1, h, lerp(T["bar_top"], T["bar_dim"], 0.7), T["bar_dim"])
    if T["bar_line"]:
        t[h - 1, 0] = T["bar_line"] if lit else lerp(T["bar_line"], T["bar_dim"], 0.4)
    return t


def bar(w, h, lit):
    return np.repeat(bar_rows(h, lit), w, axis=1)


def main_column():
    """The main window's body colour per row (horizontally uniform, so sprites can copy it)."""
    t = new(1, 116, T["bg"])
    t[0:14] = bar_rows(14, True)
    by = T["band_y"]
    vgrad_fill(t, 0, by, 1, 116 - by, T["band_top"], T["band"])
    if T["band_line"]:
        t[by, 0] = T["band_line"]
    return t


MAIN_COL = None


def body_slice(y, h, w):
    return np.repeat(MAIN_COL[y:y + h], w, axis=1).copy()


# ------------------------------------------------------------------------------------------
# Icons
# ------------------------------------------------------------------------------------------


def icon(a, kind, cx, cy, s, col):
    """Transport pictograms centred at (cx, cy) (pixel-edge coordinates); s = half height."""
    if kind == "play":
        poly(a, [(cx - s * 0.8, cy - s), (cx - s * 0.8, cy + s), (cx + s * 0.95, cy)], col)
    elif kind == "pause":
        bw = max(1.6, s * 0.62)
        frect(a, cx - s * 0.85, cy - s, cx - s * 0.85 + bw, cy + s, col, 0.4)
        frect(a, cx + s * 0.85 - bw, cy - s, cx + s * 0.85, cy + s, col, 0.4)
    elif kind == "stop":
        frect(a, cx - s * 0.9, cy - s * 0.9, cx + s * 0.9, cy + s * 0.9, col, s * 0.25)
    elif kind in ("previous", "next"):
        sg = 1 if kind == "next" else -1
        if T["skip"] == "double":
            for ox in (-s * 0.95, 0.0):
                bx = cx + sg * ox
                poly(a, [(bx, cy - s * 0.85), (bx, cy + s * 0.85), (bx + sg * s * 0.95, cy)], col)
        else:
            bx = cx - sg * s * 0.55
            poly(a, [(bx, cy - s * 0.9), (bx, cy + s * 0.9), (bx + sg * s * 1.15, cy)], col)
            ex = bx + sg * s * 1.15
            x0, x1 = (ex, ex + sg * 1.6) if sg == 1 else (ex + sg * 1.6, ex)
            frect(a, min(x0, x1), cy - s * 0.9, max(x0, x1), cy + s * 0.9, col, 0.3)
    elif kind == "eject":
        poly(a, [(cx - s, cy + s * 0.2), (cx + s, cy + s * 0.2), (cx, cy - s * 0.9)], col)
        frect(a, cx - s, cy + s * 0.5, cx + s, cy + s * 0.5 + 1.6, col, 0.3)


def shuffle_icon(a, cx, cy, col):
    def fn(d, S):
        w = 1.25 * S
        L = lambda pts: [((cx - 5.5 + x) * S, (cy - 4 + y) * S) for x, y in pts]
        d.line(L([(0, 6.5), (2.5, 6.5), (6.5, 1.5), (8.5, 1.5)]), fill=255, width=int(w))
        d.line(L([(0, 1.5), (2.5, 1.5), (6.5, 6.5), (8.5, 6.5)]), fill=255, width=int(w))
        d.polygon(L([(8.0, -0.6), (11, 1.5), (8.0, 3.6)]), fill=255)
        d.polygon(L([(8.0, 4.4), (11, 6.5), (8.0, 8.6)]), fill=255)
    x0, y0 = int(cx) - 7, int(cy) - 6
    paint(a, x0, y0, mask(14, 12, lambda d, S: fn(_Shift(d, -x0 * S, -y0 * S), S)), col)


def repeat_icon(a, cx, cy, col):
    def fn(d, S):
        w = 1.25 * S
        L = lambda pts: [((cx - 5.5 + x) * S, (cy - 4 + y) * S) for x, y in pts]
        d.line(L([(2.5, 1.5), (9, 1.5)]), fill=255, width=int(w))
        d.line(L([(8.5, 6.5), (2, 6.5)]), fill=255, width=int(w))
        d.arc(L([(-0.1, 1.5 - 0.6), (5, 6.5 + 0.6)]), 90, 270, fill=255, width=int(w))
        d.arc(L([(6, 1.5 - 0.6), (11.1, 6.5 + 0.6)]), 270, 90, fill=255, width=int(w))
        d.polygon(L([(6.5, -0.7), (9.5, 1.5), (6.5, 3.7)]), fill=255)
        d.polygon(L([(4.5, 4.3), (1.5, 6.5), (4.5, 8.7)]), fill=255)
    x0, y0 = int(cx) - 7, int(cy) - 6
    paint(a, x0, y0, mask(14, 12, lambda d, S: fn(_Shift(d, -x0 * S, -y0 * S), S)), col)


class _Shift:
    """An ImageDraw proxy that offsets every coordinate (so icons can use window coordinates)."""

    def __init__(self, d, dx, dy):
        self.d, self.dx, self.dy = d, dx, dy

    def _p(self, pts):
        if len(pts) == 4 and not isinstance(pts[0], (tuple, list)):
            return (pts[0] + self.dx, pts[1] + self.dy, pts[2] + self.dx, pts[3] + self.dy)
        return [(x + self.dx, y + self.dy) for x, y in pts]

    def line(self, pts, **k):
        self.d.line(self._p(pts), **k)

    def polygon(self, pts, **k):
        self.d.polygon(self._p(pts), **k)

    def arc(self, pts, a0, a1, **k):
        (x0, y0), (x1, y1) = self._p(pts)
        self.d.arc((x0, y0, x1, y1), a0, a1, **k)


def mini_glyph(a, x, y, kind, col):
    """9x9 titlebar button pictograms."""
    if kind == "options":
        for i in range(3):
            frect(a, x + 2, y + 2.5 + 2 * i, x + 7, y + 3.5 + 2 * i, col)
    elif kind == "minimize":
        frect(a, x + 2, y + 6, x + 7, y + 7, col)
    elif kind == "shade":
        frect(a, x + 2, y + 2, x + 7, y + 3, col)
        frect(a, x + 2, y + 5, x + 7, y + 6, col)
    elif kind == "close":
        strokes(a, x, y, 9, 9, lambda d, S: (d.line((2 * S, 2 * S, 7 * S, 7 * S), fill=255, width=int(1.2 * S)),
                                             d.line((2 * S, 7 * S, 7 * S, 2 * S), fill=255, width=int(1.2 * S))),
                col)


def mini_button(a, x, y, kind, lit=True, pressed=False):
    """A flat 9x9 titlebar button: just its glyph; pressed, a soft rounded highlight behind it."""
    if pressed:
        bg = a[y + 4, x + 4]
        rrect(a, x, y, 9, 9, 2, lerp(bg, T["title_fg"], 0.18))
    col = T["bar_icon"] if lit else lerp(T["bar_icon"], T["bar_dim"], 0.45)
    if pressed:
        col = T["title_fg"]
    mini_glyph(a, x, y, kind, col)


# ------------------------------------------------------------------------------------------
# titlebar.bmp (344 x 87)
# ------------------------------------------------------------------------------------------

CLUTTER_SLOTS = [("O", 3, 8), ("A", 11, 7), ("I", 18, 7), ("D", 25, 8), ("V", 33, 7)]


def clutter_bar(lit_letters):
    a = body_slice(22, 43, 8)
    rrect(a, 0, 0, 8, 43, 3, lerp(T["bg"], T["text"], 0.06))
    for letter, y, h in CLUTTER_SLOTS:
        on = letter in lit_letters
        if on:
            rrect(a, 1, y, 6, h, 1.5, T["accent"])
        gy = y + (h - 5) // 2
        ptext(a, TINY, letter, 2, gy, (255, 255, 255) if on else T["text3"])
    return a


def main_titlebar(lit):
    a = bar(275, 14, lit)
    f = font(T["font"], 10)
    ttext(a, T["title"], f, 137.5, 10, T["title_fg"] if lit else T["title_dim"], "c")
    mini_button(a, 6, 3, "options", lit)
    mini_button(a, 244, 3, "minimize", lit)
    mini_button(a, 254, 3, "shade", lit)
    mini_button(a, 264, 3, "close", lit)
    return a


def make_titlebar():
    a = new(344, 87, T["bg"])
    for kind, x in [("options", 0), ("minimize", 9), ("close", 18)]:
        for pressed, y in ((False, 0), (True, 9)):
            b = bar(9, 14, True)[3:12].copy()
            mini_button(b, 0, 0, kind, True, pressed)
            a[y:y + 9, x:x + 9] = b
    for pressed, x in ((False, 0), (True, 9)):
        b = bar(9, 14, True)[3:12].copy()
        mini_button(b, 0, 0, "shade", True, pressed)
        a[18:27, x:x + 9] = b
    a[0:14, 27:302] = main_titlebar(True)
    a[15:29, 27:302] = main_titlebar(False)
    a[29:43, 27:302] = main_titlebar(True)
    a[42:56, 27:302] = main_titlebar(False)
    unlit = clutter_bar("")
    lit = clutter_bar("OAIDV")
    a[0:43, 304:312] = unlit
    a[0:43, 312:320] = unlit
    for (letter, y, h), sx, sy in zip(CLUTTER_SLOTS, [304, 312, 320, 328, 336], [47, 55, 62, 69, 77]):
        a[sy:sy + h, sx:sx + 8] = lit[y:y + h]
    return a


# ------------------------------------------------------------------------------------------
# main.bmp (275 x 116)
# ------------------------------------------------------------------------------------------

SEEK_Y = 72
LOGO = (16, 250, 89)  # size, x, y: the About/emblem spot


def seek_track(a, x0, y0, w):
    """The seek rail, drawn into a (rows y0..y0+10) at columns x0..x0+w."""
    if T["seek"] == "wave":
        for i, (bx, hgt) in enumerate(wave_bars(w)):
            draw_wave_bar(a, x0 + bx, y0, hgt, T["track"], lerp(T["track"], T["bg"], 0.55))
        return
    ry, rh = T["seek_rows"]
    frect(a, x0, y0 + ry, x0 + w, y0 + ry + rh, T["track"], rh / 2)


def wave_bars(w):
    """A fixed, pseudo-random waveform: (x, height) per 2px bar on a 3px pitch."""
    rng = np.random.default_rng(4242)
    out = []
    for i, x in enumerate(range(1, w - 1, 3)):
        env = 0.52 + 0.26 * np.sin(i / 6.5) + 0.16 * np.sin(i / 2.1 + 1.3) + rng.normal(0, 0.12)
        hgt = max(1, min(7, int(round(1 + 6 * max(0.0, min(1.0, env))))))
        out.append((x, hgt))
    return out


def draw_wave_bar(a, x, y0, hgt, col, refl):
    """A waveform bar: hgt rows up from row y0+7, a 2-row paler reflection under it."""
    rect(a, x, y0 + 7 - hgt, 2, hgt, col)
    rect(a, x, y0 + 8, 2, min(2, max(1, hgt // 3)), refl)


def make_main():
    global MAIN_COL
    MAIN_COL = main_column()
    a = np.repeat(MAIN_COL, 275, axis=1).copy()
    a[0:14, :] = main_titlebar(True)
    a[22:65, 10:18] = clutter_bar("")

    # left display: indicator, time, analyzer
    panel(a, 21, 20, 84, 42)
    for yy in (29, 34):
        disc(a, 74, yy + 1, 1.1, T["text"])
    # right displays: title, then kbps/kHz/mono/stereo
    panel(a, 109, 21, 159, 15)
    panel(a, 109, 40, 159, 14)
    ptext(a, TINY, "KBPS", 129, 44, T["text2"])
    ptext(a, TINY, "KHZ", 169, 44, T["text2"])

    # seek rail
    seek_track(a, 16, SEEK_Y, 248)

    # the app's icon in the About spot
    size, lx, ly = LOGO
    put_logo(a, lx, ly, size)
    return a


# ------------------------------------------------------------------------------------------
# cbuttons.bmp (136 x 36)
# ------------------------------------------------------------------------------------------


def transport_cell(kind, w, h, y_main, pressed):
    a = body_slice(y_main, h, w)
    cx, cy = w / 2, h / 2
    if kind == "play" and T["play"]:
        face, ink, face_p = T["play"]
        r = 8.5 if not pressed else 8.0
        disc(a, cx, cy, r, face_p if pressed else face)
        icon(a, "play", cx + 0.6, cy, 3.6, ink)
        return a
    if pressed:
        disc(a, cx, cy, 8.5, T["hover"])
    col = T["icon_pressed"] if pressed else T["icon"]
    s = {"play": 5.2, "pause": 4.2, "stop": 3.9, "previous": 4.0, "next": 4.0, "eject": 4.0}[kind]
    if kind == "play" and not T["play"]:
        s = 5.6
    icon(a, kind, cx + (0.5 if kind == "play" else 0), cy, s, col)
    return a


def make_cbuttons():
    a = new(136, 36, T["band"])
    specs = [("previous", 0, 23), ("play", 23, 23), ("pause", 46, 23), ("stop", 69, 23), ("next", 92, 22)]
    for kind, x, w in specs:
        for pressed, y in ((False, 0), (True, 18)):
            a[y:y + 18, x:x + w] = transport_cell(kind, w, 18, 88, pressed)
    for pressed, y in ((False, 0), (True, 16)):
        a[y:y + 16, 114:136] = transport_cell("eject", 22, 16, 89, pressed)
    return a


# ------------------------------------------------------------------------------------------
# shufrep.bmp (92 x 85)
# ------------------------------------------------------------------------------------------


def toggle_icon_cell(kind, w, on, pressed):
    a = body_slice(89, 15, w)
    cx, cy = w / 2, 7
    if T["toggle_on"] == "dot":
        cy = 6
    if pressed:
        rrect(a, int(cx - 9), 0, 18, 15, 4, T["hover"])
    if on and T["toggle_on"] == "tint":
        bg = a[7, 1]
        rrect(a, int(cx - 9), 1, 18, 13, 4, lerp(bg, T["accent"], 0.16 if is_light() else 0.22))
    col = T["accent"] if on else (T["text"] if pressed else T["text2"])
    (shuffle_icon if kind == "shuffle" else repeat_icon)(a, cx, cy + 0.5, col)
    if on and T["toggle_on"] == "dot":
        disc(a, cx, 12.6, 1.1, T["accent"])
    return a


def pill_toggle(a, x, y, w, h, text, on, pressed, bg_slice):
    """A small pill (EQ/PL, ON/AUTO): accent when on."""
    a[y:y + h, x:x + w] = bg_slice
    if on:
        face = T["accent"]
        fg = T["pill_fg"]
        if pressed:
            face = lerp(face, (0, 0, 0), 0.18)
    else:
        face = T["btn_pressed"] if pressed else T["btn"]
        fg = T["text"] if pressed else T["text2"]
    if is_light() and not on:
        rrect(a, x, y, w, h, h / 2, T.get("panel_line_btn") or T["panel_line"] or T["track"])
        rrect(a, x + 1, y + 1, w - 2, h - 2, h / 2 - 1, face)
    else:
        rrect(a, x, y, w, h, h / 2, face)
    label(a, text, x + w / 2, y + h - 3, fg, 8)


def make_shufrep():
    a = new(92, 85, T["bg"])
    for row, (on, pressed) in enumerate([(False, False), (False, True), (True, False), (True, True)]):
        y = row * 15
        a[y:y + 15, 0:28] = toggle_icon_cell("repeat", 28, on, pressed)
        a[y:y + 15, 28:75] = toggle_icon_cell("shuffle", 47, on, pressed)
    for x, txt, pressed in [(0, "EQ", False), (23, "PL", False), (46, "EQ", True), (69, "PL", True)]:
        for on, y in ((False, 61), (True, 73)):
            cell = body_slice(58, 12, 23)
            # 22 wide, so the EQ and PL pills don't touch
            pill_toggle(cell, 0, 0, 22, 12, txt, on, pressed, cell[:, :22].copy())
            a[y:y + 12, x:x + 23] = cell
    return a


# ------------------------------------------------------------------------------------------
# monoster.bmp, playpaus.bmp, numbers.bmp, nums_ex.bmp, text.bmp
# ------------------------------------------------------------------------------------------


def make_monoster():
    a = new(56, 24, T["panel"])
    for y, on in ((0, True), (12, False)):
        col = T["text"] if on else T["text3"]
        ptext_c(a, TINY, "STEREO", 14, y + 4, col)
        ptext_c(a, TINY, "MONO", 29 + 13, y + 4, col)
    return a


def make_playpaus():
    a = new(48, 9, T["panel"])
    icon(a, "play", 4.6, 4.5, 3.4, T["accent"])
    icon(a, "pause", 9 + 4.5, 4.5, 3.2, T["text"])
    icon(a, "stop", 18 + 4.5, 4.5, 3.0, T["text"])
    disc(a, 39 + 1.5, 4.5, 1.0, T["text3"])
    return a


def make_numbers(ex):
    a = new(108 if ex else 99, 13, T["panel"])
    f = font(T["digit_font"], T["digit_size"])
    for n in range(10):
        ttext(a, str(n), f, 9 * n + 4.5, 11, T["text"], "c")
    if ex:
        frect(a, 99 + 2, 6, 99 + 7, 7.4, T["text"])
    else:
        # numbers.bmp's minus is read from (20, 6, 5, 1): keep that row of digit 2 a clean dash
        pass
    return a


FONT_GRID = [
    list("abcdefghijklmnopqrstuvwxyz\"@") + [None, None, " "],
    list("0123456789") + ["…", ".", ":", "(", ")", "-", "'", "!", "_", "+", "\\", "/", "[", "]", "^", "&", "%",
                          ",", "=", "$", "#"],
    ["å", "ö", "ä", "?", "*"] + [None] * 26,
]


def make_text():
    a = new(155, 18, T["panel"])
    for row, chars in enumerate(FONT_GRID):
        for col, ch in enumerate(chars):
            if ch is None or ch == " ":
                continue
            key = ch if ch in FONT5 else ch.upper()
            ptext(a, FONT5, key, col * 5, row * 6, T["text"])
    return a


# ------------------------------------------------------------------------------------------
# posbar.bmp (307 x 10), volume.bmp / balance.bmp (68 x 433)
# ------------------------------------------------------------------------------------------


def knob(a, cx, cy, r, selected, col=None, col_hi=None):
    col = T["knob"] if col is None else col
    col_hi = T["knob_hi"] if col_hi is None else col_hi
    if is_light() and col == (255, 255, 255):
        disc(a, cx, cy + 0.6, r + 0.4, (0, 0, 0), 0.18)
        disc(a, cx, cy, r + 0.3, (190, 190, 196))
        disc(a, cx, cy, r - 0.3, (236, 236, 240) if selected else col)
        return
    if selected:
        disc(a, cx, cy, r + 0.5, col_hi)
    else:
        disc(a, cx, cy, r, col)


def seek_thumb(selected):
    a = body_slice(SEEK_Y, 10, 29)
    if T["seek"] == "wave":
        # the playhead: a run of played (orange) bars, ending in the playhead line
        bars = wave_bars(400)[40:60]
        x = 0
        for i, (_, hgt) in enumerate(bars):
            if x + 2 > 27:
                break
            t = min(1.0, (x + 2) / 14)
            col = lerp(lerp(T["track"], T["accent"], 0.35), T["accent"], t)
            draw_wave_bar(a, x, 0, hgt, col, lerp(col, T["bg"], 0.55))
            x += 3
        rect(a, 27, 0, 2, 10, T["accent_hi"] if selected else T["accent"])
        return a
    ry, rh = T["seek_rows"]
    cx = 23.5
    rect(a, 0, ry, 29, rh, T["track"])
    for x in range(29):
        if x + 0.5 > cx:
            break
        t = max(0.0, min(1.0, x / 16))
        t = t * t * (3 - 2 * t)
        col = lerp(T["track"], T["accent"], t)
        a[ry:ry + rh, x] = col if T["tail"] else T["track"]
    # soften the rail's ends against the body above and below (kept 1px crisp rows)
    knob(a, cx, ry + rh / 2, T["knob_r"], selected, T["knob"])
    return a


def make_posbar(main):
    a = new(307, 10, T["bg"])
    a[0:10, 0:248] = main[SEEK_Y:SEEK_Y + 10, 16:264]
    a[0:10, 248:277] = seek_thumb(False)
    a[0:10, 278:307] = seek_thumb(True)
    a[0:10, 277] = MAIN_COL[SEEK_Y:SEEK_Y + 10, 0]
    return a


def h_rail(a, x0, x1, y, fill_to=None, fill_from=None):
    """A 3px rounded rail over rows y..y+2 from x0 to x1, filled in the accent up to fill_to."""
    frect(a, x0, y, x1, y + 3, T["track"], 1.5)
    if fill_to is not None:
        f0 = x0 if fill_from is None else fill_from
        if fill_to - f0 >= 1:
            frect(a, f0, y, fill_to, y + 3, T["accent"], 1.5)


def slider_thumbs(a):
    for x, sel in ((0, True), (15, False)):
        t = body_slice(58, 11, 14)
        knob(t, 7, 5.5, 4.5, sel)
        a[422:433, x:x + 14] = t


def make_volume():
    a = new(68, 433, T["bg"])
    for i in range(28):
        y = i * 15
        a[y:y + 15, 0:68] = body_slice(57, 15, 68)
        level = (i + 1) / 28
        h_rail(a[y:y + 15], 3, 65, 5, 7 + round(level * 54))
    slider_thumbs(a)
    return a


def make_balance():
    a = new(68, 433, T["bg"])
    for i in range(28):
        y = i * 15
        a[y:y + 15, 0:68] = body_slice(57, 15, 68)
        t = a[y:y + 15]
        reach = round(12 * i / 27)
        h_rail(t, 12, 44, 5)
        if reach:
            frect(t, 28 - reach, 5, 28 + reach, 8, T["accent"], 1.5)
        frect(t, 27.5, 3, 28.5, 10, T["text3"])
    slider_thumbs(a)
    return a


# ------------------------------------------------------------------------------------------
# eqmain.bmp (275 x 315)
# ------------------------------------------------------------------------------------------

EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]


def eq_titlebar(lit):
    a = bar(275, 14, lit)
    ttext(a, T["eq_title"], font(T["font"], 10), 137.5, 10, T["title_fg"] if lit else T["title_dim"], "c")
    mini_button(a, 264, 3, "close", lit)
    return a


def eq_slider_frame(a, x, y, n):
    """14x63 cell: a vertical rail, filled from the 0 dB line to the value."""
    rect(a, x, y, 14, 63, T["panel"])
    v = n / 27
    centre = (1 - v) * 51 + 6.0
    zero = 31.5
    frect(a, x + 5, y + 3, x + 8, y + 60, T["track"], 1.5)
    lo, hi = min(centre, zero), max(centre, zero)
    if hi - lo >= 0.5:
        frect(a, x + 5, y + lo, x + 8, y + hi, T["accent"], 1.0)


def make_eqmain():
    a = new(275, 315, T["bg"])
    a[0:14, :] = eq_titlebar(True)
    # graph seat and slider card
    panel(a, 85, 16, 115, 21)
    panel(a, 16, 36, 245, 68)
    rect(a, 40, 40, 1, 60, lerp(T["panel"], T["text"], 0.1))
    for lbl, yy in (("+12DB", 41), ("+0DB", 67), ("-12DB", 92)):
        ptext_c(a, TINY, lbl, 58, yy, T["text2"])
    for x in [21] + [78 + 18 * i for i in range(10)]:
        eq_slider_frame(a, x, 38, 14)
    ptext_c(a, TINY, "PREAMP", 28, 106, T["text2"])
    for i, lbl in enumerate(EQ_BANDS):
        ptext_c(a, TINY, lbl, 78 + 18 * i + 7, 106, T["text2"])

    # under the window: buttons
    b = bar(9, 14, True)[3:12].copy()
    mini_button(b, 0, 0, "close", True, pressed=True)
    a[125:134, 0:9] = b
    bg12 = np.repeat(np.array(T["bg"], dtype=np.int32)[None, None, :], 12, axis=0)
    for x, txt, on, pressed in [
        (10, "ON", False, False), (36, "AUTO", False, False), (69, "ON", True, False), (95, "AUTO", True, False),
        (128, "ON", False, True), (154, "AUTO", False, True), (187, "ON", True, True), (213, "AUTO", True, True),
    ]:
        w = 26 if txt == "ON" else 32
        cell = new(w, 12, T["bg"])
        pill_toggle(cell, 1, 0, w - 2, 12, txt, on, pressed, np.repeat(bg12, w - 2, axis=1))
        a[119:131, x:x + w] = cell
    a[134:148, :] = eq_titlebar(True)
    a[149:163, :] = eq_titlebar(False)
    for y, sel in ((164, False), (176, True)):
        t = new(11, 11, T["panel"])
        knob(t, 5.5, 5.5, 4.5, sel)
        a[y:y + 11, 0:11] = t
    for n in range(28):
        eq_slider_frame(a, 13 + (n % 14) * 15, 164 + (n // 14) * 65, n)
    for y, pressed in ((164, False), (176, True)):
        cell = new(44, 12, T["bg"])
        face = T["btn_pressed"] if pressed else T["btn"]
        if is_light():
            rrect(cell, 0, 0, 44, 12, 6, T.get("panel_line_btn") or T["panel_line"] or T["track"])
            rrect(cell, 1, 1, 42, 10, 5, face)
        else:
            rrect(cell, 0, 0, 44, 12, 6, face)
        label(cell, "PRESETS", 22, 9, T["text"] if pressed else T["btn_fg"], 8)
        a[y:y + 12, 224:268] = cell
    # graph
    rect(a, 0, 294, 113, 19, T["panel"])
    rect(a, 0, 294 + 9, 113, 1, lerp(T["panel"], T["text"], 0.12))
    for x in range(0, 113, 12):
        for y in range(0, 19, 3):
            px(a, x, 294 + y, lerp(T["panel"], T["text"], 0.07))
    for r in range(19):
        px(a, 115, 294 + r, T["accent"])
    for x in range(113):
        px(a, x, 314, T["text3"] if x % 3 != 2 else T["panel"])
    return a


# ------------------------------------------------------------------------------------------
# pledit.bmp (280 x 186) and gen.bmp (194 x 109): the 20px-titled frames
# ------------------------------------------------------------------------------------------

BAR20_BASE = 11  # title baseline in the 20px bars (caps over rows 4..10, like gen.bmp's letters)


def bottom_strip(w, h):
    """The playlist's bottom strip: the theme's player-bar colour, a hairline along its top."""
    t = new(w, h)
    vgrad_fill(t, 0, 0, w, h, T["band_top"], T["band"])
    if T["band_line"]:
        rect(t, 0, 0, w, 1, T["band_line"])
    return t


def pill_button(t, x, y, w, h, txt):
    if is_light():
        rrect(t, x, y, w, h, 4, T.get("panel_line_btn") or T["panel_line"] or T["track"])
        rrect(t, x + 1, y + 1, w - 2, h - 2, 3, T["btn"])
    else:
        rrect(t, x, y, w, h, 4, T["btn"])
    label(t, txt, x + w / 2, y + h // 2 + 3, T["btn_fg"], 8)


def readout(t, x, y, w, h):
    rrect(t, x - 1, y - 1, w + 2, h + 2, 2, T["panel"])
    rect(t, x, y, w, h, T["panel"])


def make_pledit():
    a = new(280, 186, T["bg"])
    for lit, y in ((True, 0), (False, 21)):
        a[y:y + 20, 127:152] = bar(25, 20, lit)
        a[y:y + 20, 0:25] = bar(25, 20, lit)
        t = bar(100, 20, lit)
        ttext(t, T["pl_title"], font(T["font"], 10), 50, BAR20_BASE + 1, T["title_fg"] if lit else T["title_dim"],
              "c")
        a[y:y + 20, 26:126] = t
        t = bar(25, 20, lit)
        mini_button(t, 14, 3, "close", lit)
        a[y:y + 20, 153:178] = t

    # sides: plain body, the scrollbar's lane in the right one
    a[42:71, 0:12] = T["bg"]
    a[42:71, 31:51] = T["bg"]
    b = bar(9, 20, True)[3:12].copy()
    mini_button(b, 0, 0, "close", True, pressed=True)
    a[42:51, 52:61] = b
    for x, sel in ((52, False), (61, True)):
        t = new(8, 18, T["bg"])
        frect(t, 2, 1, 6, 17, T["text2"] if sel else T["text3"], 2)
        a[53:71, x:x + 8] = t

    # bottom
    t = bottom_strip(125, 38)
    for bx, lbl in ((14, "ADD"), (43, "REM"), (72, "SEL"), (101, "MISC")):
        pill_button(t, bx, 9, 22, 16, lbl)
    a[72:110, 0:125] = t

    t = bottom_strip(150, 38)
    readout(t, 6, 9, 56, 8)
    for k, kind in enumerate(["previous", "play", "pause", "stop", "next", "eject"]):
        bx = 3 + 10 * k
        icon(t, kind, bx + 5, 22 + 5, 2.6 if kind != "play" else 3.0, T["text2"])
    readout(t, 65, 22, 33, 8)
    rect(t, 84, 24, 1, 1, T["text2"])  # the colon between minutes and seconds
    rect(t, 84, 27, 1, 1, T["text2"])
    pill_button(t, 106, 9, 22, 16, "LIST")
    for k in range(4):
        for j in range(k + 1):
            disc(t, 146.5 - 3 * k + 3 * j, 34.5 - 3 * j, 0.7, T["text3"])
    a[72:110, 126:276] = t

    a[0:38, 179:204] = bottom_strip(25, 38)
    return a


GEN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gen_letter_cells(lit):
    """Each capital as its own cell (on the bar's rows 4..10), for gen.bmp's letter rows."""
    f = font(T["font"], 9)
    col = T["title_fg"] if lit else T["title_dim"]
    rows = bar_rows(20, lit)[4:11]
    cells = []
    for c in GEN_LETTERS:
        adv = int(round(f.getlength(c)))
        w = max(3, adv)
        cell = np.repeat(rows, w, axis=1).copy()
        ttext(cell, c, f, w / 2, 7, col, "c")
        cells.append(cell)
    return cells


def make_gen():
    a = new(194, 109, T["bg"])
    for lit, y in ((True, 0), (False, 21)):
        for x0 in (0, 26, 52, 78, 104, 130):
            a[y:y + 20, x0:x0 + 25] = bar(25, 20, lit)
        t = bar(25, 20, lit)
        mini_button(t, 14, 3, "close", lit)
        a[y:y + 20, 130:155] = t

    def bottom(w, grip):
        t = new(w, 14, T["bg"])
        if grip:
            for k in range(3):
                for j in range(k + 1):
                    disc(t, w - 3.5 - 3 * k + 3 * j, 11.5 - 3 * j, 0.7, T["text3"])
        return t

    a[42:56, 0:125] = bottom(125, False)
    a[57:71, 0:125] = bottom(125, True)
    a[72:86, 127:152] = bottom(25, False)
    for x, w, h in ((127, 11, 29), (158, 11, 24), (139, 8, 29), (170, 8, 24)):
        a[42:42 + h, x:x + w] = T["bg"]
    b = bar(9, 20, True)[3:12].copy()
    mini_button(b, 0, 0, "close", True, pressed=True)
    a[42:51, 148:157] = b

    # letters: each row starts at x 1, letters in their own cells, 1px separators of x 0's colour
    for lit, y in ((True, 88), (False, 96)):
        rect(a, 0, y, 194, 7, SEP)
        x = 1
        for cell in gen_letter_cells(lit):
            w = cell.shape[1]
            a[y:y + 7, x:x + w] = cell
            x += w + 1
        assert x <= 194, x
    return a


# ------------------------------------------------------------------------------------------
# genex.bmp: Media Library colours along the top row, every other pixel from x 48
# ------------------------------------------------------------------------------------------


def genex_colours():
    pl = {k: hexc(v) for k, v in T["pl"].items()}
    light = is_light()
    return [
        pl["NormalBG"],                                     # item background
        pl["Normal"],                                       # item text
        T["bg"],                                            # window background
        T["btn_fg"],                                        # button text
        T["text"],                                          # window text
        lerp(T["bg"], T["text"], 0.15),                     # dividers, sunken borders
        pl["SelectedBG"],                                   # selection bar
        T["panel"],                                         # list header background
        T["text2"],                                         # list header text
        lerp(T["panel"], (255, 255, 255) if not light else T["text"], 0.12),  # header frame, light
        lerp(T["panel"], (0, 0, 0), 0.3),                   # header frame, dark
        T["accent"],                                        # header frame, pressed
        T["bg"],                                            # header dead area
        T["panel"],                                         # scrollbar
        T["text3"],                                         # scrollbar 2
        T["btn_pressed"],                                   # scrollbar pressed
        T["text2"],                                         # scrollbar pressed 2
        T["bg"],                                            # scrollbar dead area
    ]


def make_genex():
    a = new(256, 64, T["bg"])
    for i, c in enumerate(genex_colours()):
        px(a, 48 + 2 * i, 0, c)
    for y, pressed in ((1, False), (16, True)):
        cell = new(47, 15, T["bg"])
        rrect(cell, 0, 0, 47, 15, 4, T["btn_pressed"] if pressed else T["btn"])
        a[y:y + 15, 0:47] = cell
    return a


# ------------------------------------------------------------------------------------------
# Text files
# ------------------------------------------------------------------------------------------


def viscolor():
    p = T["panel"]
    stops = T["vis"]
    out = [(p, "background"), (lerp(p, T["text"], 0.05), "dots")]
    for i in range(16):
        out.append((ramp(stops, i / 15), f"spectrum {i + 1} (top)" if i == 0 else f"spectrum {i + 1}"))
    for i in range(5):
        out.append((ramp(stops[:3], i / 4), f"oscilloscope {i + 1}"))
    out.append((T["text"], "peaks"))
    return out


def write_text_files():
    with open(os.path.join(OUT, "viscolor.txt"), "w", newline="\r\n") as f:
        for (r, g, b), note in viscolor():
            f.write(f"{r},{g},{b}, // {note}\n")
    pl = T["pl"]
    with open(os.path.join(OUT, "pledit.txt"), "w", newline="\r\n") as f:
        f.write(f"[Text]\nNormal={pl['Normal']}\nCurrent={pl['Current']}\nNormalBG={pl['NormalBG']}\n"
                f"SelectedBG={pl['SelectedBG']}\nMbBG={pl['NormalBG']}\nMbFG={pl['Normal']}\nFont=Arial\n")
    with open(os.path.join(OUT, "readme.txt"), "w", newline="\r\n") as f:
        f.write(
            "YTMinamp Green - " + "green on near-black, drawn from scratch.\n"
            "\n"
            "A classic (Winamp 2.x format) skin: flat near-black panels, a round white play\n"
            "button, green slider fills and a green dot under shuffle and repeat when they're on.\n"
            "Every bitmap was drawn by a script (gen_skin.py) from flat shapes and system sans\n"
            "lettering; the emblem is YTMinamp's own icon, recoloured.\n\n"
            "License: CC0 1.0 Universal (public domain dedication).\n"
        )


# ------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------

SHEETS = {}


def build():
    SHEETS.clear()
    main = make_main()
    sheets = {
        "main.bmp": main,
        "titlebar.bmp": make_titlebar(),
        "cbuttons.bmp": make_cbuttons(),
        "shufrep.bmp": make_shufrep(),
        "posbar.bmp": make_posbar(main),
        "volume.bmp": make_volume(),
        "balance.bmp": make_balance(),
        "monoster.bmp": make_monoster(),
        "playpaus.bmp": make_playpaus(),
        "numbers.bmp": make_numbers(False),
        "nums_ex.bmp": make_numbers(True),
        "text.bmp": make_text(),
        "pledit.bmp": make_pledit(),
        "eqmain.bmp": make_eqmain(),
        "gen.bmp": make_gen(),
        "genex.bmp": make_genex(),
    }
    for name, arr in sheets.items():
        SHEETS[name[:-4]] = save(arr, name)
    write_text_files()
    names = list(sheets) + ["pledit.txt", "viscolor.txt", "readme.txt"]
    wsz = os.path.join(HERE, T["wsz"] + ".wsz")
    with zipfile.ZipFile(wsz, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(OUT, n), "rb") as fh:
                z.writestr(info, fh.read())
    # genex.bmp completed for real Winamp and WACUP: all 24 colours, readable text, and the
    # standard 112x59 button and scrollbar layout (skins/genex_wacup.py).
    genex_wacup.process(wsz)
    return names


# ------------------------------------------------------------------------------------------
# Preview: every window put together from the sprites the way the app does
# ------------------------------------------------------------------------------------------


def blit(dst, sheet, r, dx, dy, w=None, sx=0):
    x, y, rw, rh = r
    w = rw if w is None else w
    dst.paste(sheet.crop((x + sx, y, x + sx + w, y + rh)), (dx, dy))


def stretch(dst, sheet, r, dx, dy, dw, dh):
    x, y, w, h = r
    dst.paste(sheet.crop((x, y, x + w, y + h)).resize((dw, dh), Image.NEAREST), (dx, dy))


FONT_LOOKUP = {}
for _row, _chars in enumerate(FONT_GRID):
    for _col, _ch in enumerate(_chars):
        if _ch is not None:
            FONT_LOOKUP[_ch] = (_row, _col)


def draw_bitmap_text(dst, s, x, y):
    text = SHEETS["text"]
    for ch in s:
        row, col = FONT_LOOKUP.get(ch.lower(), FONT_LOOKUP[" "])
        blit(dst, text, (col * 5, row * 6, 5, 6), x, y)
        x += 5


def text_ink():
    """text.bmp's ink as the app takes it (marquee.js textInk): the commonest colour in the letter
    and digit rows clearly unlike the space cell's; pledit's Normal if there's none."""
    a = np.asarray(SHEETS["text"], dtype=np.int32)[0:12, 0:155]
    bg = a[0, 150]
    far = np.abs(a - bg).sum(-1) >= 96
    if not far.any():
        return hexc(T["pl"]["Normal"])
    cols, counts = np.unique(a[far].reshape(-1, 3), axis=0, return_counts=True)
    return tuple(int(v) for v in cols[counts.argmax()])


def preview_main(lit, state):
    S = SHEETS
    img = Image.new("RGB", (275, 116))
    img.paste(S["main"], (0, 0))
    blit(img, S["titlebar"], (27, 0 if lit else 15, 275, 14), 0, 0)
    cb = {"previous": (0, 23, 18), "play": (23, 23, 18), "pause": (46, 23, 18), "stop": (69, 23, 18),
          "next": (92, 22, 18)}
    pos = {"previous": (16, 88), "play": (39, 88), "pause": (62, 88), "stop": (85, 88), "next": (108, 88)}
    for k, (x, w, h) in cb.items():
        blit(img, S["cbuttons"], (x, 18 if state["pressed"] == k else 0, w, h), *pos[k])
    blit(img, S["cbuttons"], (114, 16 if state["pressed"] == "eject" else 0, 22, 16), 136, 89)
    for name, x0, on in (("eq", 0, state["eq"]), ("pl", 23, state["pl"])):
        pressed = state["pressed"] == name
        sx = x0 + (46 if pressed else 0)
        blit(img, S["shufrep"], (sx, 73 if on else 61, 23, 12), 219 + x0, 58)
    blit(img, S["titlebar"], (304, 0, 8, 43), 10, 22)
    spr = {"O": (304, 47, 8, 8, 3), "A": (312, 55, 8, 7, 11), "I": (320, 62, 8, 7, 18), "D": (328, 69, 8, 8, 25),
           "V": (336, 77, 8, 7, 33)}
    for L in state["clutter"]:
        x, y, w, h, oy = spr[L]
        blit(img, S["titlebar"], (x, y, w, h), 10, 22 + oy)
    for name, x0, w, on, dst in (("shuffle", 28, 47, state["shuffle"], 164), ("repeat", 0, 28, state["repeat"], 210)):
        row = (2 if on else 0) + (1 if state["pressed"] == name else 0)
        blit(img, S["shufrep"], (x0, row * 15, w, 15), dst, 89)
    blit(img, S["playpaus"], (0 if state["playing"] else 9, 0, 9, 9), 26, 28)
    blit(img, S["playpaus"], (39, 0, 3, 9), 24, 28)
    blit(img, S["monoster"], (29, 12 if state["stereo"] else 0, 27, 12), 212, 41)
    blit(img, S["monoster"], (0, 0 if state["stereo"] else 12, 29, 12), 239, 41)
    blit(img, S["posbar"], (0, 0, 248, 10), 16, 72)
    tl = round(state["pos"] * 219)
    blit(img, S["posbar"], (278 if state["seek"] else 248, 0, 29, 10), 16 + tl, 72)
    v = state["volume"]
    idx = max(0, round(v / 100 * 28) - 1)
    blit(img, S["volume"], (0, idx * 15, 68, 13), 107, 57)
    blit(img, S["volume"], (0 if state["vdrag"] else 15, 422, 14, 11), 107 + round(v / 100 * 54), 58)
    b = state["balance"]
    idx = int(abs(b) / 100 * 27)
    blit(img, S["balance"], (9, idx * 15, 38, 13), 177, 57)
    blit(img, S["balance"], (15, 422, 14, 11), 177 + round((b + 100) / 200 * 24), 58)
    secs = state["time"]
    m, s = secs // 60, secs % 60
    nums = S["nums_ex"]
    if state["remaining"]:
        blit(img, nums, (99, 0, 9, 13), 38, 26)
    for d, x in ((m // 10, 48), (m % 10, 60), (s // 10, 78), (s % 10, 90)):
        blit(img, nums, (9 * d, 0, 9, 13), x, 26)
    # title: text.bmp's space across the box, then the title in TrueType in pledit's Normal colour
    for x in range(0, 154, 5):
        w = min(5, 154 - x)
        blit(img, S["text"], (150, 0, w, 6), 111 + x, 24)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(LIBERATION, 11)
    tmp = img.crop((111, 22, 265, 36))
    dt = ImageDraw.Draw(tmp)
    dt.text((0, 29 - 22), state["title"], fill=text_ink(), font=f, anchor="lm")
    img.paste(tmp, (111, 22))
    draw_bitmap_text(img, "192", 111, 43)
    draw_bitmap_text(img, "44", 156, 43)
    cols = [c for c, _ in viscolor()]
    vis = Image.new("RGB", (76, 16))
    vp = vis.load()
    for y in range(16):
        for x in range(76):
            vp[x, y] = cols[1] if (y % 2 == 1 and x % 2 == 0) else cols[0]
    heights = state["bars"]
    for x in range(75):
        if x % 4 == 3:
            continue
        hgt = heights[x // 4] - 2
        for y in range(16 - hgt, 16):
            vp[x, y] = cols[min(17, max(2, y + 2))]
        pk = heights[x // 4] + 2
        if 0 <= 16 - pk < 16:
            vp[x, 16 - pk] = cols[23]
    img.paste(vis, (24, 43))
    return img


def preview_eq(lit, state):
    S = SHEETS
    sheet = S["eqmain"]
    img = Image.new("RGB", (275, 116))
    blit(img, sheet, (0, 0, 275, 116), 0, 0)
    blit(img, sheet, (0, 134 if lit else 149, 275, 14), 0, 0)
    if state["pressed"] == "close":
        blit(img, sheet, (0, 125, 9, 9), 264, 3)
    on, pressed = state["on"], state["pressed"] == "on"
    blit(img, sheet, ((187 if on else 128) if pressed else (69 if on else 10), 119, 26, 12), 14, 18)
    blit(img, sheet, ((95 if state["auto"] else 36), 119, 32, 12), 40, 18)
    blit(img, sheet, (224, 176 if state["pressed"] == "presets" else 164, 44, 12), 217, 18)

    def slider(x, value, drag):
        n = round(value / 100 * 27)
        blit(img, sheet, (13 + (n % 14) * 15, 164 + (n // 14) * 65, 14, 63), x, 38)
        ty = 38 + round((1 - value / 100) * 51)
        blit(img, sheet, (0, 176 if drag else 164, 11, 11), x + 1, ty)

    slider(21, state["preamp"], False)
    for i, v in enumerate(state["bands"]):
        slider(78 + 18 * i, v, state["drag"] == i)
    blit(img, sheet, (0, 294, 113, 19), 86, 17)
    py_ = round((100 - state["preamp"]) / 100 * 18)
    blit(img, sheet, (0, 314, 113, 1), 86, 17 + py_)
    ys = [(100 - v) / 100 * 18 for v in state["bands"]]
    last = round(ys[0])
    for x in range(0, 109):
        i = min(8, x // 12)
        t = (x - i * 12) / 12
        y = round(ys[i] + (ys[i + 1] - ys[i]) * (3 * t * t - 2 * t * t * t))
        y = max(0, min(18, y))
        top, h = min(y, last), 1 + abs(last - y)
        blit(img, sheet, (115, 294 + top, 1, h), 86 + 2 + x, 17 + top)
        last = y
    return img


def preview_playlist(lit, w, h, rows, pressed_close=False, drag=False):
    S = SHEETS
    sheet = S["pledit"]
    pl = {k: hexc(v) for k, v in T["pl"].items()}
    img = Image.new("RGB", (w, h))
    ty = 0 if lit else 21
    for x in range(25, w - 25, 25):
        blit(img, sheet, (127, ty, 25, 20), x, 0)
    blit(img, sheet, (0, ty, 25, 20), 0, 0)
    blit(img, sheet, (26, ty, 100, 20), (w - 100) // 2, 0)
    blit(img, sheet, (153, ty, 25, 20), w - 25, 0)
    for y in range(20, h - 38, 29):
        blit(img, sheet, (0, 42, 12, 29), 0, y)
        blit(img, sheet, (31, 42, 20, 29), w - 20, y)
    for x in range(125, w - 150, 25):
        blit(img, sheet, (179, 0, 25, 38), x, h - 38)
    blit(img, sheet, (0, 72, 125, 38), 0, h - 38)
    blit(img, sheet, (126, 72, 150, 38), w - 150, h - 38)
    if pressed_close:
        blit(img, sheet, (52, 42, 9, 9), w - 11, 3)
    d = ImageDraw.Draw(img)
    lx, lw = 12, w - 32
    d.rectangle((lx, 20, lx + lw - 1, h - 39), fill=pl["NormalBG"])
    f = ImageFont.truetype(LIBERATION, 10)
    for i, (txt, dur) in enumerate(rows):
        y = 23 + i * 15
        if y + 15 > h - 38:
            break
        if i == 2:
            d.rectangle((lx, y, lx + lw - 1, y + 14), fill=pl["SelectedBG"])
        col = pl["Current"] if i == 1 else pl["Normal"]
        d.text((lx + 2, y + 2), f"{i + 1}. {txt}", fill=col, font=f)
        d.text((lx + lw - 3 - d.textlength(dur, font=f), y + 2), dur, fill=col, font=f)
    blit(img, sheet, (61 if drag else 52, 53, 8, 18), w - 15, 20 + 30)
    draw_bitmap_text(img, "3:27/41:10", w - 150 + 7, h - 38 + 10)
    for dx, ch in zip([1, 7, 12, 20, 25], " 0327"):
        draw_bitmap_text(img, ch, w - 150 + 66 + dx, h - 38 + 23)
    return img


def gen_letters():
    g = SHEETS["gen"]
    pxs = g.load()
    out = {}
    for state, y in (("focused", 88), ("unfocused", 96)):
        bg = pxs[0, y]
        letters, n, x = {}, 0, 1
        while x < g.width and n < 26:
            if pxs[x, y] == bg:
                x += 1
                continue
            start = x
            while x < g.width and pxs[x, y] != bg:
                x += 1
            letters[chr(65 + n)] = (start, x - start)
            n += 1
        assert n == 26, f"gen.bmp {state} letters: found {n}"
        out[state] = letters
    return out


def preview_gen(lit, w, h, title, pressed_close=False):
    g = SHEETS["gen"]
    L = gen_letters()
    st = "focused" if lit else "unfocused"
    ty = 0 if lit else 21
    img = Image.new("RGB", (w, h), (0, 0, 0))
    piece = lambda px0: (px0, ty, 25, 20)
    for tx in range(0, w, 25):
        blit(img, g, piece(104), tx, 0)
    text_wd = sum(L[st].get(c, (0, 5))[1] for c in title.upper())
    if text_wd + 100 <= w:
        tx = (w - text_wd) // 2
        for cx in range(tx, tx + text_wd, 25):
            blit(img, g, piece(52), cx, 0, min(25, tx + text_wd - cx))
        blit(img, g, piece(26), tx - 25, 0)
        blit(img, g, piece(78), tx + text_wd, 0)
        x = tx
        for c in title.upper():
            if c in L[st]:
                lx, lw = L[st][c]
                blit(img, g, (lx, 88 if lit else 96, lw, 7), x, 4)
                x += lw
            else:
                x += 5
    blit(img, g, piece(0), 0, 0)
    blit(img, g, piece(130), w - 25, 0)
    if pressed_close:
        blit(img, g, (148, 42, 9, 9), w - 11, 3)
    right_x = w - 8
    side_bottom = h - 14 - 24
    for ty2 in range(20, side_bottom, 29):
        blit(img, g, (127, 42, 11, 29), 0, ty2)
        blit(img, g, (139, 42, 8, 29), right_x, ty2)
        stretch(img, g, (139, 42, 1, 29), right_x - 3, ty2, 3, 29)
    blit(img, g, (158, 42, 11, 24), 0, side_bottom)
    blit(img, g, (170, 42, 8, 24), right_x, side_bottom)
    stretch(img, g, (170, 42, 1, 24), right_x - 3, side_bottom, 3, 24)
    by = h - 14
    for tx in range(0, w, 25):
        blit(img, g, (127, 72, 25, 14), tx, by)
    lw_ = min(125, -(-w // 2))
    rw_ = min(125, w - lw_)
    blit(img, g, (0, 42, 125, 14), 0, by, lw_)
    blit(img, g, (0, 57, 125, 14), w - rw_, by, rw_, 125 - rw_)
    # a stand-in picture: a gradient in the theme's accents
    pw, ph = w - 22, h - 34
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    t = (xx / pw * 0.4 + yy / ph * 0.6)[..., None]
    c0, c1 = np.array(T["vis"][0], np.float32), np.array(T["vis"][3], np.float32)
    pic = c0 * (1 - t) + c1 * t
    img.paste(Image.fromarray(pic.astype(np.uint8)), (11, 20))
    return img


def preview():
    rows = [("Night Drive - Copper Wire", "4:12"), ("Slow Burn - Lantern Hours", "3:47"),
            ("Kiln - Second Firing", "5:03"), ("Ash & Smoke - Afterglow", "2:58"),
            ("Moss - Forest Floor", "6:21"), ("Field Notes - Warm Static", "3:33"),
            ("Fern - Small Hours", "4:40"), ("Canopy - Bellows", "3:09"),
            ("Hearth - Long Winter", "5:51"), ("Glowworm - Low Light", "4:05"),
            ("Ivy - Climb", "3:22")]
    bars = [12, 15, 14, 11, 13, 10, 9, 11, 8, 7, 9, 6, 5, 6, 4, 3, 4, 2, 3]
    A = dict(pressed=None, eq=True, pl=True, clutter="AV", shuffle=True, repeat=False, playing=True, stereo=True,
             pos=0.38, seek=False, volume=72, vdrag=False, balance=0, time=207, remaining=False,
             title="YTMinamp Green - drawn from scratch", bars=bars)
    B = dict(pressed="play", eq=False, pl=True, clutter="", shuffle=False, repeat=True, playing=False, stereo=False,
             pos=0.8, seek=True, volume=25, vdrag=True, balance=-60, time=95, remaining=True,
             title="Paused: Quiet Hours (Live)", bars=[3, 2, 4, 1, 2, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    EA = dict(pressed=None, on=True, auto=False, preamp=50, drag=None,
              bands=[75, 68, 56, 49, 49, 33, 30, 30, 49, 49])
    EB = dict(pressed="close", on=False, auto=True, preamp=70, drag=3,
              bands=[51, 51, 59, 65, 65, 100, 59, 51, 0, 51])
    cols = []
    for lit, st, est in ((True, A, EA), (False, B, EB)):
        h = 116 + 116 + 232 + 140
        col = Image.new("RGB", (275, h))
        col.paste(preview_main(lit, st), (0, 0))
        col.paste(preview_eq(lit, est), (0, 116))
        col.paste(preview_playlist(lit, 275, 232, rows, pressed_close=not lit, drag=not lit), (0, 232))
        col.paste(preview_gen(lit, 275, 140, T["gen_title"], pressed_close=not lit), (0, 464))
        cols.append(col)
    gap = 12
    out = Image.new("RGB", (275 * 2 + gap * 3, cols[0].height + gap * 2), (60, 60, 64) if not is_light()
                    else (150, 150, 156))
    out.paste(cols[0], (gap, gap))
    out.paste(cols[1], (275 + 2 * gap, gap))
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    out.save(os.path.join(HERE, f"preview-{T['key']}.png"))


# ------------------------------------------------------------------------------------------
# Checks
# ------------------------------------------------------------------------------------------


def check():
    S = SHEETS
    sizes = {"main": (275, 116), "titlebar": (344, 87), "cbuttons": (136, 36), "shufrep": (92, 85),
             "posbar": (307, 10), "volume": (68, 433), "balance": (68, 433), "monoster": (56, 24),
             "playpaus": (48, 9), "numbers": (99, 13), "nums_ex": (108, 13), "text": (155, 18),
             "pledit": (280, 186), "eqmain": (275, 315), "gen": (194, 109), "genex": (256, 64)}
    for k, sz in sizes.items():
        assert S[k].size == sz, (k, S[k].size, sz)
        assert S[k].mode == "RGB", k
    gen_letters()
    sp = S["text"].getpixel((150, 0))
    assert sp == tuple(T["panel"]), (sp, T["panel"])
    for x in range(150, 155):
        for y in range(6):
            assert S["text"].getpixel((x, y)) == sp
    # the title box in main.bmp is the panel colour too (where the app's TrueType title sits)
    m = np.asarray(S["main"])
    box = m[22:35, 111:265]
    assert (box == np.array(T["panel"], np.uint8)).all(), "title box not flat"
    ink = text_ink()
    assert sum(abs(ink[i] - T["panel"][i]) for i in range(3)) >= 300, ("title ink too faint", ink)


if __name__ == "__main__":
    if "--list" in sys.argv:
        print("\n".join(THEMES))
        sys.exit(0)
    keys = sys.argv[1:] or list(THEMES)
    for key in keys:
        if key not in THEMES:
            sys.exit(f"unknown theme {key!r}; one of {', '.join(THEMES)}")
        setup_theme(key)
        names = build()
        check()
        preview()
        print(f"{key}: {T['wsz']}.wsz, preview-{key}.png, out/{key}/ ({len(names)} files)")
