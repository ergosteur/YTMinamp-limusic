#!/usr/bin/python3
"""YTMinamp Material Music: a classic Winamp 2.x skin in the Material design style of 2015.

A light #fafafa body with white cards and soft shadows, deep orange app bars, an orange floating
action button for play, grey transport icons with a grey ripple when pressed, Material switches,
checkboxes and tabs, and thin sliders with an orange fill and dot thumb. Everything is drawn here
from code (anti-aliased shapes, hand-made pixel fonts, Noto Sans for titles and digits); the About
spot holds the app's own icon (src-tauri/icons/icon.png), recoloured deep orange to amber with a
lighter fold.

    /usr/bin/python3 -I gen_skin.py            # build
    /usr/bin/python3 -I gen_skin.py --list     # theme names

Writes the sheets to out/<theme>/, zips them flat into YTMinamp-Material-Music.wsz beside this
script and draws preview-<theme>.png (every window assembled from the sprites the way the app
does, 2x).
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


SANS = find_font("NotoSans[wght].ttf")   # Noto Sans, variable weight 400-700

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SEP = (255, 0, 255)          # gen.bmp letter separators (never shown)

T = None                     # the theme being built
OUT = None

# ------------------------------------------------------------------------------------------
# Colour and canvas helpers
# ------------------------------------------------------------------------------------------


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(cols, t):
    """Colour along evenly spaced stops, t in 0..1."""
    t = max(0.0, min(1.0, t))
    n = len(cols) - 1
    i = min(n - 1, int(t * n))
    return lerp(cols[i], cols[i + 1], t * n - i)


def hexc(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def new(w, h, col=BLACK):
    a = np.zeros((h, w, 3), dtype=np.int32)
    a[:, :] = col
    return a


def rect(a, x, y, w, h, col):
    if w > 0 and h > 0:
        a[max(0, y):y + h, max(0, x):x + w] = col


def px(a, x, y, col):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = col


def vfill(a, x, y, w, h, stops):
    for r in range(h):
        rect(a, x, y + r, w, 1, ramp(stops, r / max(1, h - 1)))


def save(a, name):
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, name))
    return img


def grid(a, rows, x, y, col, half=None):
    """Pixel art: '#' full colour, '+' half blended into what's there (or `half` colour)."""
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "#":
                px(a, x + c, y + r, col)
            elif ch == "+" and 0 <= y + r < a.shape[0] and 0 <= x + c < a.shape[1]:
                px(a, x + c, y + r, half if half else lerp(tuple(a[y + r, x + c]), col, 0.5))


# Anti-aliased shapes: coverage masks drawn supersampled and boxed down.
SS = 6


def mask(w, h, fn):
    im = Image.new("L", (w * SS, h * SS), 0)
    fn(ImageDraw.Draw(im), SS)
    return np.asarray(im.resize((w, h), Image.BOX), dtype=np.float32) / 255.0


def rr_mask(w, h, r, x=0.0, y=0.0, mw=None, mh=None):
    mw = w - x if mw is None else mw
    mh = h - y if mh is None else mh
    r = max(0.0, min(r, mw / 2, mh / 2))
    return mask(w, h, lambda d, S: d.rounded_rectangle(
        (round(x * S), round(y * S), round((x + mw) * S) - 1, round((y + mh) * S) - 1), radius=round(r * S), fill=255))


def ellipse_mask(w, h, x, y, ew, eh):
    return mask(w, h, lambda d, S: d.ellipse((round(x * S), round(y * S), round((x + ew) * S) - 1,
                                              round((y + eh) * S) - 1), fill=255))


def poly_mask(w, h, pts):
    return mask(w, h, lambda d, S: d.polygon([(round(px_ * S), round(py_ * S)) for px_, py_ in pts], fill=255))


def pie_mask(w, h, cx, cy, r, a0, a1):
    return mask(w, h, lambda d, S: d.pieslice((round((cx - r) * S), round((cy - r) * S), round((cx + r) * S) - 1,
                                               round((cy + r) * S) - 1), a0, a1, fill=255))


def paint(a, x, y, m, col, alpha=1.0):
    """Blends colour over a through coverage mask m placed at (x, y)."""
    h, w = m.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(a.shape[1], x + w), min(a.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    mm = (m[y0 - y:y1 - y, x0 - x:x1 - x] * alpha)[..., None]
    c = np.asarray(col, dtype=np.float32)
    reg = a[y0:y1, x0:x1].astype(np.float32)
    a[y0:y1, x0:x1] = np.round(reg * (1 - mm) + c * mm).astype(np.int32)


def rrect(a, x, y, w, h, r, col, alpha=1.0):
    paint(a, x, y, rr_mask(w, h, r), col, alpha)


def disc(a, cx, cy, d, col, alpha=1.0):
    """A circle of diameter d centred on the coordinate (cx, cy) (pixel k spans k..k+1)."""
    x0, y0 = int(np.floor(cx - d / 2)) - 1, int(np.floor(cy - d / 2)) - 1
    n = int(np.ceil(d)) + 3
    paint(a, x0, y0, ellipse_mask(n, n, cx - d / 2 - x0, cy - d / 2 - y0, d, d), col, alpha)


def poly(a, pts, col, alpha=1.0):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = int(np.floor(min(xs))) - 1, int(np.floor(min(ys))) - 1
    w, h = int(np.ceil(max(xs))) - x0 + 2, int(np.ceil(max(ys))) - y0 + 2
    paint(a, x0, y0, poly_mask(w, h, [(p[0] - x0, p[1] - y0) for p in pts]), col, alpha)


# TrueType text (Noto Sans)
_FONTS = {}


def font(size, wght=400, face=None):
    wght = max(400, min(700, wght))
    key = (size, wght)
    if key not in _FONTS:
        f = ImageFont.truetype(SANS, size)
        f.set_variation_by_axes([wght])
        _FONTS[key] = f
    return _FONTS[key]


def tt(a, s, x, y, col, size, wght=400, anchor="ls", alpha=1.0, face=None):
    h, w = a.shape[:2]
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((x, y), s, fill=255, font=font(size, wght, face), anchor=anchor)
    paint(a, 0, 0, np.asarray(im, dtype=np.float32) / 255.0, col, alpha)


# ------------------------------------------------------------------------------------------
# Pixel fonts (from Ember)
# ------------------------------------------------------------------------------------------

def G(*rows):
    return list(rows)


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
    "M": G("#...#", "##.##", "#.#.#", "#...#", "#...#"),
    "N": G("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": G(".##.", "#..#", "#..#", "#..#", ".##."),
    "P": G("###.", "#..#", "###.", "#...", "#..."),
    "Q": G(".##.", "#..#", "#..#", "#.#.", ".#.#"),
    "R": G("###.", "#..#", "###.", "#.#.", "#..#"),
    "S": G(".###", "#...", ".##.", "...#", "###."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#..#", "#..#", "#..#", "#..#", ".##."),
    "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#...#", "#...#", "#.#.#", "##.##", "#...#"),
    "X": G("#..#", "#..#", ".##.", "#..#", "#..#"),
    "Y": G("#.#", "#.#", ".#.", ".#.", ".#."),
    "Z": G("####", "...#", ".##.", "#...", "####"),
    "0": G("###", "#.#", "#.#", "#.#", "###"),
    "1": G(".#.", "##.", ".#.", ".#.", "###"),
    "2": G("###", "..#", "###", "#..", "###"),
    "3": G("###", "..#", ".##", "..#", "###"),
    "4": G("#.#", "#.#", "###", "..#", "..#"),
    "5": G("###", "#..", "###", "..#", "###"),
    "6": G("###", "#..", "###", "#.#", "###"),
    "7": G("###", "..#", ".#.", ".#.", ".#."),
    "8": G("###", "#.#", "###", "#.#", "###"),
    "9": G("###", "#.#", "###", "..#", "###"),
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
# text.bmp cells are 5 wide: the 5-wide M and W get Ember's 4-wide forms there
TEXT5 = dict(FONT5, M=G("#..#", "####", "####", "#..#", "#..#"), W=G("#..#", "#..#", "####", "####", "#..#"))

TINY = {
    "A": G(".#.", "#.#", "###", "#.#", "#.#"),
    "B": G("##.", "#.#", "##.", "#.#", "##."),
    "C": G(".##", "#..", "#..", "#..", ".##"),
    "D": G("##.", "#.#", "#.#", "#.#", "##."),
    "E": G("###", "#..", "##.", "#..", "###"),
    "F": G("###", "#..", "##.", "#..", "#.."),
    "G": G(".##", "#..", "#.#", "#.#", ".##"),
    "H": G("#.#", "#.#", "###", "#.#", "#.#"),
    "I": G("###", ".#.", ".#.", ".#.", "###"),
    "K": G("#.#", "#.#", "##.", "#.#", "#.#"),
    "L": G("#..", "#..", "#..", "#..", "###"),
    "M": G("#.#", "###", "###", "#.#", "#.#"),
    "N": G("##.", "#.#", "#.#", "#.#", "#.#"),
    "O": G(".#.", "#.#", "#.#", "#.#", ".#."),
    "P": G("##.", "#.#", "##.", "#..", "#.."),
    "Q": G(".#.", "#.#", "#.#", "##.", ".##"),
    "R": G("##.", "#.#", "##.", "#.#", "#.#"),
    "S": G(".##", "#..", ".#.", "..#", "##."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#.#", "#.#", "#.#", "#.#", "###"),
    "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#.#", "#.#", "###", "###", "#.#"),
    "X": G("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": G("#.#", "#.#", ".#.", ".#.", ".#."),
    "Z": G("###", "..#", ".#.", "#..", "###"),
    " ": G("..", "..", "..", "..", ".."),
}
for _c in "0123456789+-.":
    TINY[_c] = FONT5[_c]


def glyph_w(font_, c):
    return len(font_[c][0])


def text_w(font_, s, gap=1):
    s = [c for c in s if c in font_]
    return sum(glyph_w(font_, c) for c in s) + gap * max(0, len(s) - 1)


def draw_text(a, font_, s, x, y, col, gap=1, shadow=None):
    for c in s:
        if c not in font_:
            continue
        g = font_[c]
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    if shadow is not None:
                        px(a, x + k, y + r + 1, shadow)
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    px(a, x + k, y + r, col)
        x += len(g[0]) + gap
    return x


def text_center(a, font_, s, cx, y, col, gap=1, shadow=None):
    draw_text(a, font_, s, cx - text_w(font_, s, gap) // 2, y, col, gap, shadow)


# ------------------------------------------------------------------------------------------
# Themes
# ------------------------------------------------------------------------------------------

DEEP_ORANGE = (255, 87, 34)    # #ff5722, Material deep orange 500: the accent
DEEP_ORANGE_DK = (230, 74, 25)  # #e64a19, deep orange 700
AMBER = (255, 152, 0)          # #ff9800, Material orange 500: the emblem's fold

THEMES = {
    "material": dict(
        name="YTMinamp Material Music", wsz="YTMinamp-Material-Music.wsz",
        disp=WHITE, ink=(33, 33, 33), digit=(33, 33, 33), digit_w=400, accent=DEEP_ORANGE,
        label=(117, 117, 117), dim=(189, 189, 189),
        pl=dict(normal="#212121", current="#FF5722", normalbg="#FFFFFF", selectedbg="#FFCCBC",
                font="Noto Sans"),
        desk=(224, 224, 224),
    ),
}
THEME_KEYS = list(THEMES)


def K():
    return T["key"]


# ------------------------------------------------------------------------------------------
# Shared pieces: backgrounds, the emblem, icons
# ------------------------------------------------------------------------------------------


def emblem(a, x, y, size=16):
    """The app's icon with its red disc recoloured: deep orange 700 to 500, the upper-left half
    folded over in amber (a lighter sheet, Material's paper fold); the white mark and the bolt
    keep their own colours."""
    src = np.asarray(Image.open(ICON).convert("RGBA"), dtype=np.float64)
    rgb = src[..., :3] / 255
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    disc_px = (rgb[..., 0] == mx) & (rgb[..., 0] > 0.6) & (rgb[..., 1] < 0.45) & (sat > 0.5)
    t = np.clip((rgb[..., 0] - 0.78) / (0.97 - 0.78), 0, 1)[..., None]
    col = np.array(DEEP_ORANGE_DK, np.float64) * (1 - t) + np.array(DEEP_ORANGE, np.float64) * t
    H, W = disc_px.shape
    yy, xx = np.mgrid[0:H, 0:W]
    fold = ((xx + yy) < W)[..., None]
    col = np.where(fold, col * 0.45 + np.array(AMBER, np.float64) * 0.55, col)
    out = src.copy()
    out[..., :3] = np.where(disc_px[..., None], col, src[..., :3])
    im = Image.fromarray(np.round(out).astype(np.uint8), "RGBA").resize((size, size), Image.LANCZOS)
    lg = np.asarray(im, dtype=np.float32)
    paint(a, x, y, lg[..., 3] / 255.0, lg[..., :3])


def main_body_col(y):
    """The main window's background colour at row y (whole-window coordinates)."""
    return (250, 250, 250)


def main_body(a, x, y, w, h, y0=0):
    for r in range(h):
        rect(a, x, y + r, w, 1, main_body_col(y0 + y + r))


def card(a, x, y, w, h, fill=WHITE, r=2.0, lift=1):
    """Material card: soft shadow (heavier below) then the white face."""
    for d, al in ((3, 0.05), (2, 0.08), (1, 0.10)):
        rrect_at(a, x - d + 1, y - d + 1 + lift, w + 2 * d - 2, h + 2 * d - 2, r + d, BLACK, al)
    rrect_at(a, x, y, w, h, r, fill)


def rrect_at(a, x, y, w, h, r, col, alpha=1.0):
    if w <= 0 or h <= 0:
        return
    paint(a, x, y, rr_mask(w, h, r), col, alpha)


def display(a, x, y, w, h):
    """A display window: (x, y, w, h) is its flat interior in the display colour."""
    D = T["disp"]
    card(a, x - 1, y - 1, w + 2, h + 2)
    rect(a, x, y, w, h, D)


# ------------------------------------------------------------------------------------------
# Transport and other glyphs (anti-aliased polygons)
# ------------------------------------------------------------------------------------------


def glyph(a, kind, cx, cy, col, s=1.0, alpha=1.0):
    """Media glyphs centred on the coordinate (cx, cy)."""
    def P(*pts):
        poly(a, [(cx + u * s, cy + v * s) for u, v in pts], col, alpha)

    if kind == "play":
        P((-3, -4.5), (-3, 4.5), (4.5, 0))
    elif kind == "pause":
        P((-3.5, -4), (-1, -4), (-1, 4), (-3.5, 4))
        P((1, -4), (3.5, -4), (3.5, 4), (1, 4))
    elif kind == "stop":
        P((-3.5, -3.5), (3.5, -3.5), (3.5, 3.5), (-3.5, 3.5))
    elif kind == "previous":
        P((-4.5, -4), (-2.5, -4), (-2.5, 4), (-4.5, 4))
        P((4.5, -4), (4.5, 4), (-2.5, 0))
    elif kind == "next":
        P((2.5, -4), (4.5, -4), (4.5, 4), (2.5, 4))
        P((-4.5, -4), (-4.5, 4), (2.5, 0))
    elif kind == "eject":
        P((-4.5, 1), (4.5, 1), (0, -4))
        P((-4.5, 2.5), (4.5, 2.5), (4.5, 4.5), (-4.5, 4.5))


def mini_glyph(a, kind, x, y, col):
    """The playlist's 10x10 mini transport, as small pixel glyphs."""
    cx, cy = x + 5, y + 5
    if kind == "previous":
        rect(a, cx - 3, cy - 2, 1, 5, col)
        for r in range(5):
            n = 2 - abs(r - 2) + 1
            rect(a, cx + 2 - n + 1, cy - 2 + r, n, 1, col)
    elif kind == "play":
        for r in range(7):
            n = 3 - abs(r - 3) + 1
            rect(a, cx - 1, cy - 3 + r, n, 1, col)
    elif kind == "pause":
        rect(a, cx - 2, cy - 2, 2, 5, col)
        rect(a, cx + 1, cy - 2, 2, 5, col)
    elif kind == "stop":
        rect(a, cx - 2, cy - 2, 5, 5, col)
    elif kind == "next":
        for r in range(5):
            n = 2 - abs(r - 2) + 1
            rect(a, cx - 2, cy - 2 + r, n, 1, col)
        rect(a, cx + 2, cy - 2, 1, 5, col)
    elif kind == "eject":
        for r in range(3):
            rect(a, cx - r, cy - 3 + r, 2 * r + 1, 1, col)
        rect(a, cx - 2, cy + 1, 5, 1, col)


REPEAT_ICON = ["........#..", ".#########.", ".#......#..", ".#.........", ".#.......#.",
               ".........#.", "..#......#.", ".#########.", "..#........"]
SHUFFLE_ICON = ["#.....###", ".#.....##", "..#...#.#", ".....#...", "....#....",
                "...#.#...", "..#...#.#", ".#.....##", "#.....###"]


# ------------------------------------------------------------------------------------------
# Titlebar buttons and bars
# ------------------------------------------------------------------------------------------


def bar_glyph(a, x, y, kind, col):
    """9x9 titlebar glyphs."""
    if kind == "options":
        for r in (1, 4, 7):
            rect(a, x + 4, y + r, 1, 1, col)
            px(a, x + 4, y + r, col)
        for r in (1, 4, 7):
            rect(a, x + 4, y + r, 1, 1, col)
    elif kind == "minimize":
        rect(a, x + 2, y + 6, 5, 1, col)
    elif kind == "shade":
        rect(a, x + 2, y + 2, 5, 1, col)
        rect(a, x + 2, y + 2, 1, 5, col)
        rect(a, x + 6, y + 2, 1, 5, col)
        rect(a, x + 2, y + 6, 5, 1, col)
        rect(a, x + 2, y + 3, 5, 1, col)
    elif kind == "close":
        for i in range(5):
            px(a, x + 2 + i, y + 2 + i, col)
            px(a, x + 6 - i, y + 2 + i, col)


def bar_button(a, x, y, kind, lit, pressed, on_light=False):
    """Draws a titlebar button over the bar already painted at (x, y)."""
    ink = WHITE if not on_light else (117, 117, 117)
    if not lit and not on_light:
        ink = (245, 245, 245)
    if pressed:
        disc(a, x + 4.5, y + 4.5, 9, WHITE if not on_light else BLACK, 0.3 if not on_light else 0.12)
    bar_glyph(a, x, y, kind, ink)


def main_titlebar(lit):
    """The main window's app bar: "YTMinamp" centred, like every other window's bar."""
    a = win_bar_bg(275, 14, lit)
    bar_title(a, "YTMinamp", 137, 11, lit)
    for kind, x in (("options", 6), ("minimize", 244), ("shade", 254), ("close", 264)):
        bar_button(a, x, 3, kind, lit, False, on_light=not lit)
    return a


def win_bar_bg(w, h, lit):
    """Every window's Material app bar. Rows 0..15 are the bar; a 20px bar's last rows are the
    frame above the list."""
    a = new(w, h)
    bar_h = 16 if h == 20 else h
    rect(a, 0, 0, w, bar_h, DEEP_ORANGE if lit else (224, 224, 224))
    if h == 20:
        rect(a, 0, 16, w, 4, (250, 250, 250))
        for r, al in ((16, 0.22), (17, 0.10), (18, 0.04)):
            rect(a, 0, r, w, 1, lerp((250, 250, 250), BLACK, al))
    return a


def title_col(lit):
    return WHITE if lit else (117, 117, 117)


def bar_title(a, s, cx, baseline, lit):
    tt(a, s, cx, baseline, title_col(lit), 11, 500, anchor="ms")


# ------------------------------------------------------------------------------------------
# titlebar.bmp (344 x 87)
# ------------------------------------------------------------------------------------------

CLUTTER_SLOTS = [("O", 3, 8), ("A", 11, 7), ("I", 18, 7), ("D", 25, 8), ("V", 33, 7)]


def clutter_bar(lit_letters):
    a = new(8, 43)
    main_body(a, 0, 0, 8, 43, 22)
    rect(a, 0, 0, 8, 43, (238, 238, 238))
    for letter, y, h in CLUTTER_SLOTS:
        on = letter in lit_letters
        gy = y + (h - 5) // 2
        if on:
            rect(a, 1, y, 6, h, (255, 204, 188))
        draw_text(a, TINY, letter, 2, gy, T["accent"] if on else (158, 158, 158))
    return a


def make_titlebar():
    a = new(344, 87, T["disp"])
    lit, unlit = main_titlebar(True), main_titlebar(False)
    a[0:14, 27:302] = lit
    a[15:29, 27:302] = unlit
    a[29:43, 27:302] = lit
    a[42:56, 27:302] = unlit
    cells = {"options": ((0, 0), (0, 9), 6), "minimize": ((9, 0), (9, 9), 244), "close": ((18, 0), (18, 9), 264),
             "shade": ((0, 18), (9, 18), 254)}
    for kind, ((nx, ny), (px_, py_), bx) in cells.items():
        base = win_bar_bg(275, 14, True)
        b = base[3:12, bx:bx + 9].copy()
        n = b.copy()
        bar_button(n, 0, 0, kind, True, False)
        p = b.copy()
        bar_button(p, 0, 0, kind, True, True)
        a[ny:ny + 9, nx:nx + 9] = n
        a[py_:py_ + 9, px_:px_ + 9] = p
    off = clutter_bar("")
    on = clutter_bar("OAIDV")
    a[0:43, 304:312] = off
    a[0:43, 312:320] = off
    for (letter, y, h), sx, sy in zip(CLUTTER_SLOTS, [304, 312, 320, 328, 336], [47, 55, 62, 69, 77]):
        a[sy:sy + h, sx:sx + 8] = on[y:y + h]
    return a


# ------------------------------------------------------------------------------------------
# main.bmp (275 x 116)
# ------------------------------------------------------------------------------------------


def main_plain():
    a = new(275, 116)
    main_body(a, 0, 0, 275, 116)
    a[0:14, :] = main_titlebar(True)
    # the control card along the bottom
    card(a, 4, 85, 267, 27, r=2)
    # displays
    display(a, 21, 20, 84, 42)
    display(a, 109, 21, 159, 15)
    display(a, 109, 40, 159, 14)
    # window edge
    edge = (200, 200, 200)
    rect(a, 0, 14, 1, 102, edge)
    rect(a, 274, 14, 1, 102, edge)
    rect(a, 0, 115, 275, 1, edge)
    return a


def make_main(plain):
    a = plain.copy()
    a[22:65, 10:18] = clutter_bar("")
    # the time's colon
    for yy in (30, 35):
        disc(a, 74.0, yy + 0.0, 2.0, T["digit"])
    lab = T["label"]
    draw_text(a, TINY, "KBPS", 129, 44, lab)
    draw_text(a, TINY, "KHZ", 169, 44, lab)
    # the app's icon, in orange, in the About spot
    emblem(a, 250, 90)
    return a


# ------------------------------------------------------------------------------------------
# cbuttons.bmp (136 x 36)
# ------------------------------------------------------------------------------------------

CB = [("previous", 0, 23, 16), ("play", 23, 23, 39), ("pause", 46, 23, 62), ("stop", 69, 23, 85),
      ("next", 92, 22, 108)]


def make_cbuttons(plain):
    a = new(136, 36)
    for kind, sx, w, mx in CB:
        for pressed, sy in ((False, 0), (True, 18)):
            cell = plain[88:106, mx:mx + w].copy()
            transport_cell(cell, kind, w, 18, pressed)
            a[sy:sy + 18, sx:sx + w] = cell
    for pressed, sy in ((False, 0), (True, 16)):
        cell = plain[89:105, 136:158].copy()
        transport_cell(cell, "eject", 22, 16, pressed)
        a[sy:sy + 16, 114:136] = cell
    return a


def transport_cell(c, kind, w, h, pressed):
    cx, cy = w / 2, h / 2
    grey = (97, 97, 97)
    if kind == "play":
        # the floating action button
        for d, al in ((2.0, 0.10), (1.0, 0.16)):
            disc(c, cx, cy + d * (1.5 if pressed else 1), 16 + d, BLACK, al)
        disc(c, cx, cy, 16, DEEP_ORANGE_DK if pressed else DEEP_ORANGE)
        glyph(c, "play", cx + 0.5, cy, WHITE, 0.75)
    else:
        if pressed:
            disc(c, cx, cy, 16, BLACK, 0.12)
        glyph(c, kind, cx, cy, grey, 0.85)


# ------------------------------------------------------------------------------------------
# shufrep.bmp (92 x 85)
# ------------------------------------------------------------------------------------------


def toggle_cell(c, w, h, label, on, pressed, icon=None):
    """Material toggles: an icon or label tinted with the accent when on."""
    if pressed:
        rrect_at(c, 1, 0, w - 2, h, 3, BLACK, 0.10)
    ink = DEEP_ORANGE if on else (117, 117, 117)
    if icon is not None:
        iw, ih = len(icon[0]), len(icon)
        grid(c, icon, (w - iw) // 2, (h - ih) // 2, ink)
    else:
        tw = text_w(TINY, label)
        draw_text(c, TINY, label, (w - tw) // 2, 2, ink)
        if on:
            rect(c, (w - tw) // 2 - 1, h - 3, tw + 2, 2, DEEP_ORANGE)


def make_shufrep(plain):
    a = new(92, 85)
    for row, (on, pressed) in enumerate([(False, False), (False, True), (True, False), (True, True)]):
        y = row * 15
        c = plain[89:104, 210:238].copy()
        toggle_cell(c, 28, 15, "REPEAT", on, pressed, REPEAT_ICON)
        a[y:y + 15, 0:28] = c
        c = plain[89:104, 164:211].copy()
        toggle_cell(c, 47, 15, "SHUFFLE", on, pressed, SHUFFLE_ICON)
        a[y:y + 15, 28:75] = c
    for x, label, pressed in [(0, "EQ", False), (23, "PL", False), (46, "EQ", True), (69, "PL", True)]:
        for on, y in ((False, 61), (True, 73)):
            mx = 219 if label == "EQ" else 242
            c = plain[58:70, mx:mx + 23].copy()
            toggle_cell(c, 23, 12, label, on, pressed)
            a[y:y + 12, x:x + 23] = c
    return a


# ------------------------------------------------------------------------------------------
# monoster, playpaus, numbers, nums_ex, text
# ------------------------------------------------------------------------------------------


def make_monoster():
    a = new(56, 24, T["disp"])
    for y, on in ((0, True), (12, False)):
        col = T["accent"] if on else T["dim"]
        text_center(a, TINY, "STEREO", 14, y + 3, col)
        text_center(a, TINY, "MONO", 42, y + 3, col)
    return a


def make_playpaus():
    a = new(48, 9, T["disp"])
    acc = T["accent"]
    poly(a, [(2, 0.5), (2, 8.5), (8, 4.5)], acc)                        # playing
    rect(a, 11, 1, 2, 7, acc)                                            # paused
    rect(a, 14, 1, 2, 7, acc)
    rect(a, 20, 2, 5, 5, acc)                                            # stopped
    rect(a, 36, 0, 3, 9, T["disp"])                                      # not working
    rect(a, 40, 3, 1, 3, acc)                                            # working
    return a


def digit_cell(ch):
    c = new(9, 13, T["disp"])
    if ch == "-":
        rect(c, 2, 6, 5, 1, T["digit"])
        return c
    if ch == " ":
        return c
    size = 16
    tt(c, ch, 4.5, 12.4, T["digit"], size, T["digit_w"], anchor="ms")
    return c


def make_numbers(ex):
    a = new(108 if ex else 99, 13, T["disp"])
    for n in range(10):
        a[0:13, 9 * n:9 * n + 9] = digit_cell(str(n))
    if ex:
        a[0:13, 99:108] = digit_cell("-")
    return a


FONT_GRID = [
    list("abcdefghijklmnopqrstuvwxyz\"@") + [None, None, " "],
    list("0123456789") + ["…", ".", ":", "(", ")", "-", "'", "!", "_", "+", "\\", "/", "[", "]", "^", "&", "%",
                          ",", "=", "$", "#"],
    ["å", "ö", "ä", "?", "*"] + [None] * 26,
]


def make_text():
    a = new(155, 18, T["disp"])
    for row, chars in enumerate(FONT_GRID):
        for col, ch in enumerate(chars):
            if ch is None or ch == " ":
                continue
            key = ch if ch in TEXT5 else ch.upper()
            draw_text(a, TEXT5, key, col * 5, row * 6, T["ink"])
    return a


# ------------------------------------------------------------------------------------------
# Sliders: posbar.bmp (307 x 10), volume.bmp / balance.bmp (68 x 433)
# ------------------------------------------------------------------------------------------


def track_cols():
    """(track colour, fill colour) for the thin Material lines."""
    return (189, 189, 189), DEEP_ORANGE


def hline(a, x, y_centre, w, col, soft=True):
    """A thin horizontal line on the pixel row y_centre, with soft half rows round it (a 2px look)."""
    rect(a, x, y_centre, w, 1, col)
    if soft:
        for yy in (y_centre - 1, y_centre + 1):
            for xx in range(x, x + w):
                px(a, xx, yy, lerp(tuple(a[yy, xx]), col, 0.35))


def dot_knob(a, cx, cy, pressed, d_halo=10, d_dot=5):
    """Material slider thumb: an accent dot, grown and haloed while dragged."""
    if pressed:
        disc(a, cx, cy, d_halo, DEEP_ORANGE, 0.22)
    disc(a, cx, cy, d_dot + (2 if pressed else 0), DEEP_ORANGE)


def make_posbar(plain):
    a = new(307, 10)
    bg = plain[72:82, 16:264].copy()
    trk, _ = track_cols()
    rect(bg, 1, 4, 246, 2, trk)
    a[0:10, 0:248] = bg
    for sx, pressed in ((248, False), (278, True)):
        c = bg[:, 100:129].copy()
        dot_knob(c, 14.5, 5.0, pressed, 10, 7)
        a[0:10, sx:sx + 29] = c
    return a


def vol_frame(bg, level):
    """68x13 volume frame filled up to the thumb's centre (x 7 + level * 54)."""
    c = bg.copy()
    fill_to = 7 + round(level * 54)
    trk, fl = track_cols()
    hline(c, 2, 6, 64, trk)
    if fill_to > 2:
        hline(c, 2, 6, fill_to - 2, fl)
    return c


def vol_thumbs(a, bg, level_cut=7):
    """Thumbs 14x11 at (15, 422) normal and (0, 422) pressed; their backgrounds show the track
    filled on the left half, so they sit on the fill's end."""
    for sx, pressed in ((15, False), (0, True)):
        f = vol_frame(bg, 0.5)                   # fill to x 34: crop it round that point
        c = f[1:12, 34 - 7:34 + 7].copy()
        dot_knob(c, 7.0, 5.5, pressed, 11, 7)
        a[422:433, sx:sx + 14] = c


def make_volume(plain):
    a = new(68, 433)
    bg = plain[57:70, 107:175].copy()
    for i in range(28):
        a[i * 15:i * 15 + 13, :] = vol_frame(bg, (i + 1) / 28)
        a[i * 15 + 13:i * 15 + 15, :] = plain[70:72, 107:175]
    vol_thumbs(a, bg)
    return a


def make_balance(plain):
    a = new(68, 433)
    bg = plain[57:70, 177:215].copy()
    for i in range(28):
        c = bg.copy()
        trk, _ = track_cols()
        hline(c, 2, 6, 34, trk)
        mark = T["accent"] if i == 0 else (158, 158, 158)
        rect(c, 18, 0, 2, 2, mark)
        rect(c, 18, 11, 2, 2, mark)
        a[i * 15:i * 15 + 13, 9:47] = c
        a[i * 15:i * 15 + 13, 0:9] = plain[57:70, 168:177]
        a[i * 15:i * 15 + 13, 47:68] = plain[57:70, 215:236]
    # thumbs: on the neutral track
    clean = bg.copy()
    hline(clean, 2, 6, 34, track_cols()[0])
    for sx, pressed in ((15, False), (0, True)):
        c = clean[1:12, 5:19].copy()
        dot_knob(c, 7.0, 5.5, pressed, 11, 7)
        a[422:433, sx:sx + 14] = c
    return a


# ------------------------------------------------------------------------------------------
# eqmain.bmp (275 x 315)
# ------------------------------------------------------------------------------------------

EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]


def eq_titlebar(lit):
    a = win_bar_bg(275, 14, lit)
    bar_title(a, "Equalizer", 137, 11, lit)
    bar_button(a, 264, 3, "close", lit, False, on_light=not lit)
    return a


def eq_body_col(y):
    return (250, 250, 250)


def eq_window():
    a = new(275, 116)
    for r in range(116):
        rect(a, 0, r, 275, 1, eq_body_col(r))
    a[0:14, :] = eq_titlebar(True)
    card(a, 12, 36, 251, 74)
    # the graph: a flat outlined field (a card's shadow would show between the slider slots)
    rrect_at(a, 84, 15, 117, 23, 2, (224, 224, 224))
    rect(a, 85, 16, 115, 21, WHITE)
    # dB marks between the preamp and the bands
    lab = T["label"]
    sep = (224, 224, 224)
    rect(a, 39, 39, 1, 62, sep)
    for lbl, yy in (("+12DB", 41), ("+0DB", 66), ("-12DB", 92)):
        text_center(a, TINY, lbl, 58, yy, lab)
    for x in [21] + [78 + 18 * i for i in range(10)]:
        a[38:101, x:x + 14] = eq_slider_frame(a[38:101, x:x + 14].copy(), 14 / 27)
    lab2 = T["label"]
    text_center(a, TINY, "PREAMP", 28, 104, lab2)
    for i, lbl in enumerate(EQ_BANDS):
        text_center(a, TINY, lbl, 78 + 18 * i + 7, 104, lab2)
    edge = (200, 200, 200)
    rect(a, 0, 14, 1, 102, edge)
    rect(a, 274, 14, 1, 102, edge)
    rect(a, 0, 115, 275, 1, edge)
    return a


def eq_slider_frame(bg, v):
    """14x63 slot: a vertical track on column 6, filled from the bottom to the thumb's centre."""
    c = bg.copy()
    centre = round((1 - v) * 51 + 5.5)           # first filled row
    trk, fl = track_cols()
    for r in range(3, 60):
        col = fl if r >= centre else trk
        px(c, 6, r, col)
        for xx in (5, 7):
            px(c, xx, r, lerp(tuple(c[r, xx]), col, 0.35))
    return c


def vfill_h(a, stops):
    """Horizontal gradient across a's columns (a vertical track's rounded shading)."""
    w = a.shape[1]
    for k in range(w):
        a[:, k] = ramp(stops, k / max(1, w - 1))


def eq_toggle(c, w, h, label, on, pressed):
    # Material: a switch for ON, a checkbox for AUTO
    if pressed:
        rrect_at(c, 0, 0, w, h, 3, BLACK, 0.08)
    if label == "ON":
        tx = 2
        draw_text(c, TINY, "ON", tx, 4, (97, 97, 97))
        trk = (255, 171, 145) if on else (189, 189, 189)
        rrect_at(c, 11, 4, 13, 5, 2.5, trk)
        cx = 20.5 if on else 14.5
        disc(c, cx, 6.9, 8, BLACK, 0.18)
        disc(c, cx, 6.5, 8, DEEP_ORANGE if on else (245, 245, 245))
        if not on:
            disc(c, cx, 6.5, 8, (180, 180, 180), 0.0)
    else:
        bx, by = 2, 2
        if on:
            rrect_at(c, bx, by, 8, 8, 1.2, DEEP_ORANGE)
            grid(c, ["......", ".....#", "....#.", "#..#..", ".##...", "......"], bx + 1, by + 1, WHITE)
        else:
            rrect_at(c, bx, by, 8, 8, 1.2, (117, 117, 117))
            rect(c, bx + 1, by + 1, 6, 6, tuple(c[0, 0]) if not pressed else tuple(c[by + 4, bx + 4 - 3]))
            rrect_at(c, bx + 1, by + 1, 6, 6, 0.5, (250, 250, 250))
        draw_text(c, TINY, "AUTO", 13, 4, (97, 97, 97))


def presets_cell(c, pressed):
    if pressed:
        rrect_at(c, 0, 0, 44, 12, 2, BLACK, 0.1)
    text_center(c, TINY, "PRESETS", 22, 4, DEEP_ORANGE)


def eq_thumb(bg, pressed):
    c = bg.copy()
    dot_knob(c, 5.5, 5.5, pressed, 11, 7)
    return c


def eq_close_pressed():
    t = eq_titlebar(True)
    bar_button(t, 264, 3, "close", True, True)
    return t[3:12, 264:273]


def make_eqmain():
    a = new(275, 315, T["disp"])
    win = eq_window()
    a[0:116, :] = win
    # the window's plain background under the sliders: one slot without its track
    slot_bg = win[38:101, 21:35].copy()
    plain_slot = new(14, 63)
    for r in range(63):
        plain_slot[r, :] = WHITE
    # buttons under the window
    a[125:134, 0:9] = eq_close_pressed()
    for x, label, on, pressed in [
        (10, "ON", False, False), (36, "AUTO", False, False), (69, "ON", True, False), (95, "AUTO", True, False),
        (128, "ON", False, True), (154, "AUTO", False, True), (187, "ON", True, True), (213, "AUTO", True, True),
    ]:
        w = 26 if label == "ON" else 32
        wx = 14 if label == "ON" else 40
        c = win[18:30, wx:wx + w].copy()
        eq_toggle(c, w, 12, label, on, pressed)
        a[119:131, x:x + w] = c
    a[134:148, :] = eq_titlebar(True)
    a[149:163, :] = eq_titlebar(False)
    # slider thumbs on the plain slot background at the fill's edge
    for y, pressed in ((164, False), (176, True)):
        ref = eq_slider_frame(plain_slot, 0.5)
        # rows round the boundary (first filled row 31): thumb rows 26..36 -> centre 31.5
        cell = ref[26:37, 1:12]
        a[y:y + 11, 0:11] = eq_thumb(cell, pressed)
    for n in range(28):
        a[164 + (n // 14) * 65:164 + (n // 14) * 65 + 63, 13 + (n % 14) * 15:13 + (n % 14) * 15 + 14] = \
            eq_slider_frame(plain_slot, n / 27)
    for y, pressed in ((164, False), (176, True)):
        c = win[18:30, 217:261].copy()
        presets_cell(c, pressed)
        a[y:y + 12, 224:268] = c
    # the graph: background, preamp line, the line's colours by height
    g = new(113, 19, WHITE)
    gridc = (238, 238, 238)
    for x in range(0, 113, 14):
        rect(g, x + 1, 0, 1, 19, gridc)
    rect(g, 0, 9, 113, 1, lerp(gridc, T["label"], 0.4))
    a[294:313, 0:113] = g
    line = [(191, 54, 12), DEEP_ORANGE_DK, DEEP_ORANGE, (255, 138, 101)]
    for r in range(19):
        px(a, 115, 294 + r, ramp(line, r / 18))
    pre = (189, 189, 189)
    for x in range(113):
        px(a, x, 314, pre if x % 3 != 2 else g[0, 0])
    return a


# ------------------------------------------------------------------------------------------
# pledit.bmp (280 x 186) and gen.bmp (194 x 109)
# ------------------------------------------------------------------------------------------


def frame_col():
    return (250, 250, 250)


def edge_cols():
    """(outer edge, inner edge next to the list)"""
    return ((200, 200, 200), (224, 224, 224))


def side_tile(w, h, left, list_side=True):
    t = new(w, h, frame_col())
    outer, inner = edge_cols()
    if left:
        rect(t, 0, 0, 1, h, outer)
        if list_side:
            rect(t, w - 1, 0, 1, h, inner)
    else:
        rect(t, w - 1, 0, 1, h, outer)
        if list_side:
            rect(t, 0, 0, 1, h, inner)
    return t


def bottom_base(w, h=38):
    t = new(w, h, frame_col())
    outer, inner = edge_cols()
    rect(t, 0, 0, w, h, WHITE)
    for r, al in ((0, 0.14), (1, 0.05)):
        rect(t, 0, r, w, 1, lerp(WHITE, BLACK, al))
    rect(t, 0, h - 1, w, 1, outer)
    return t


def text_button(t, x, y, w, h, label, pressed=False):
    if pressed:
        rrect_at(t, x, y, w, h, 2, BLACK, 0.1)
    text_center(t, TINY, label, x + w // 2, y + (h - 5) // 2, DEEP_ORANGE)


def readout(t, x, y, w, h):
    """A box for text.bmp readouts (playlist times): the display colour, framed per theme."""
    rect(t, x, y, w, h, T["disp"])


def grip(t, x0, y0, n):
    col = (189, 189, 189)
    for k in range(n):
        for j in range(k + 1):
            px(t, x0 - 3 * k + 3 * j, y0 - 3 * j, col)


def make_pledit():
    a = new(280, 186, frame_col())
    outer, inner = edge_cols()
    for lit, y in ((True, 0), (False, 21)):
        t = win_bar_bg(25, 20, lit)
        a[y:y + 20, 127:152] = t
        t = win_bar_bg(25, 20, lit)
        rect(t, 0, 0, 1, 20, outer)
        rect(t, 11, 19, 14, 1, inner)
        a[y:y + 20, 0:25] = t
        t = win_bar_bg(100, 20, lit)
        bar_title(t, "Playlist", 50, 12, lit)
        rect(t, 0, 19, 100, 1, inner)
        a[y:y + 20, 26:126] = t
        t = win_bar_bg(25, 20, lit)
        rect(t, 24, 0, 1, 20, outer)
        bar_button(t, 14, 3, "close", lit, False, on_light=not lit)
        rect(t, 0, 19, 6, 1, inner)
        a[y:y + 20, 153:178] = t
        # the list's top edge across the fill tile too
        a[y + 19, 127:152] = inner
    # sides
    a[42:71, 0:12] = side_tile(12, 29, True)
    t = side_tile(20, 29, False)
    groove = (245, 245, 245)
    rect(t, 5, 0, 8, 29, groove)
    a[42:71, 31:51] = t
    for x, sel in ((52, False), (61, True)):
        c = new(8, 18, groove)
        rrect_at(c, 2, 0, 4, 18, 2, (189, 189, 189) if not sel else DEEP_ORANGE)
        a[53:71, x:x + 8] = c
    t = win_bar_bg(25, 20, True)
    rect(t, 24, 0, 1, 20, outer)
    bar_button(t, 14, 3, "close", True, True)
    a[42:51, 52:61] = t[3:12, 14:23]

    # bottom: left (buttons), right (readouts, mini transport, LIST, grip), fill
    t = bottom_base(125)
    rect(t, 0, 0, 1, 38, outer)
    for bx, lbl in ((14, "ADD"), (43, "REM"), (72, "SEL"), (101, "MISC")):
        text_button(t, bx, 8, 22, 18, lbl)
    a[72:110, 0:125] = t

    t = bottom_base(150)
    rect(t, 149, 0, 1, 38, outer)
    readout(t, 6, 9, 56, 8)
    ink = (97, 97, 97)
    for k, kind in enumerate(["previous", "play", "pause", "stop", "next", "eject"]):
        mini_glyph(t, kind, 3 + 10 * k, 22, ink)
    readout(t, 65, 22, 33, 8)
    rect(t, 84, 24, 1, 1, T["ink"])
    rect(t, 84, 27, 1, 1, T["ink"])
    text_button(t, 106, 8, 22, 18, "LIST")
    grip(t, 145, 34, 4)
    a[72:110, 126:276] = t
    t = bottom_base(25)
    a[0:38, 179:204] = t
    return a


GEN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gen_bottom(w, grip_, left_edge):
    t = new(w, 14, frame_col())
    outer, inner = edge_cols()
    rect(t, 0, 0, w, 14, (250, 250, 250))
    rect(t, 0, 0, w, 1, inner)
    rect(t, 0, 13, w, 1, outer)
    if left_edge:
        rect(t, 0, 0, 1, 14, outer)
    else:
        rect(t, w - 1, 0, 1, 14, outer)
    if grip_:
        grip(t, w - 4, 10, 3)
    return t


def make_gen():
    a = new(194, 109, frame_col())
    outer, inner = edge_cols()
    for lit, y in ((True, 0), (False, 21)):
        for px0 in (0, 26, 52, 78, 104, 130):
            t = win_bar_bg(25, 20, lit)
            rect(t, 0, 19, 25, 1, inner)
            if px0 == 0:
                rect(t, 0, 0, 1, 20, outer)
            if px0 == 130:
                rect(t, 24, 0, 1, 20, outer)
                bar_button(t, 14, 3, "close", lit, False, on_light=not lit)
            a[y:y + 20, px0:px0 + 25] = t
    a[42:56, 0:125] = gen_bottom(125, False, True)
    a[57:71, 0:125] = gen_bottom(125, True, False)
    t = gen_bottom(25, False, False)
    t[:, 24] = t[:, 23]
    a[72:86, 127:152] = t
    for x, w, h, left in ((127, 11, 29, True), (158, 11, 24, True), (139, 8, 29, False), (170, 8, 24, False)):
        a[42:42 + h, x:x + w] = side_tile(w, h, left)
    t = win_bar_bg(25, 20, True)
    bar_button(t, 14, 3, "close", True, True)
    a[42:51, 148:157] = t[3:12, 14:23]
    # letters: the bar's own rows 4..10 as each cell's background, separated by SEP
    for lit, y in ((True, 88), (False, 96)):
        bar = win_bar_bg(194, 20, lit)
        rect(a, 0, y, 194, 7, SEP)
        x = 1
        for ch in GEN_LETTERS:
            w = glyph_w(FONT5, ch) + 1
            a[y:y + 7, x:x + w] = bar[4:11, x:x + w]
            draw_text(a, FONT5, ch, x, y + 1, title_col(lit))
            x += w + 1
        assert x <= 194, x
    return a


# ------------------------------------------------------------------------------------------
# genex.bmp, text files
# ------------------------------------------------------------------------------------------


def genex_colours():
    return ([WHITE, (33, 33, 33), (250, 250, 250), DEEP_ORANGE, (33, 33, 33), (224, 224, 224),
                        (255, 204, 188), WHITE, (117, 117, 117), WHITE, (224, 224, 224), (255, 204, 188),
                        (250, 250, 250), (245, 245, 245), (189, 189, 189), (238, 238, 238), DEEP_ORANGE,
                        (250, 250, 250)])


def make_genex():
    a = new(256, 64, frame_col())
    for i, c in enumerate(genex_colours()):
        px(a, 48 + 2 * i, 0, c)
    for y, pressed in ((1, False), (16, True)):
        rect(a, 0, y, 47, 15, WHITE if not pressed else (238, 238, 238))
        rect(a, 0, y + 14, 47, 1, (224, 224, 224))
    return a


def viscolor():
    bg, dots = WHITE, (238, 238, 238)
    spec = [(191, 54, 12), DEEP_ORANGE_DK, DEEP_ORANGE, (255, 112, 67), (255, 138, 101), (255, 204, 188)]
    osc = [(191, 54, 12), DEEP_ORANGE_DK, DEEP_ORANGE, (255, 138, 101), (255, 171, 145)]
    peak = (66, 66, 66)
    out = [(bg, "background"), (dots, "dots")]
    out += [(ramp(spec, i / 15), f"spectrum {i + 1}") for i in range(16)]
    out += [(c, f"oscilloscope {i + 1}") for i, c in enumerate(osc)]
    out += [(peak, "peaks")]
    return out


def write_text_files():
    with open(os.path.join(OUT, "viscolor.txt"), "w", newline="\r\n") as f:
        for (r, g, b), note in viscolor():
            f.write(f"{r},{g},{b}, // {note}\n")
    p = T["pl"]
    with open(os.path.join(OUT, "pledit.txt"), "w", newline="\r\n") as f:
        f.write(f"[Text]\nNormal={p['normal']}\nCurrent={p['current']}\nNormalBG={p['normalbg']}\n"
                f"SelectedBG={p['selectedbg']}\nMbBG={p['normalbg']}\nMbFG={p['normal']}\nFont={p['font']}\n")
    with open(os.path.join(OUT, "readme.txt"), "w", newline="\r\n") as f:
        f.write(
            "YTMinamp Material Music - a skin in the Material design style of 2015.\n\n"
            "A classic (Winamp 2.x format) skin, drawn by a script (gen_skin.py): a light body\n"
            "with white cards and soft shadows, deep orange app bars, an orange floating play\n"
            "button, switches, checkboxes and thin orange sliders, hand-made pixel fonts and\n"
            "Noto Sans titles. The emblem is YTMinamp's own icon, in orange.\n\n"
            "License: CC0 1.0 Universal (public domain dedication).\n"
        )


# ------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------

SHEETS = {}


def build():
    plain = main_plain()
    main = make_main(plain)
    sheets = {
        "main.bmp": main,
        "titlebar.bmp": make_titlebar(),
        "cbuttons.bmp": make_cbuttons(plain),
        "shufrep.bmp": make_shufrep(plain),
        "posbar.bmp": make_posbar(plain),
        "volume.bmp": make_volume(plain),
        "balance.bmp": make_balance(plain),
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
    SHEETS.clear()
    for name, arr in sheets.items():
        SHEETS[name[:-4]] = save(arr, name)
    write_text_files()
    names = list(sheets) + ["pledit.txt", "viscolor.txt", "readme.txt"]
    with zipfile.ZipFile(os.path.join(HERE, T["wsz"]), "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(OUT, n), "rb") as fh:
                z.writestr(info, fh.read())
    # genex.bmp completed for real Winamp and WACUP: all 24 colours, readable text, and the
    # standard 112x59 button and scrollbar layout (skins/genex_wacup.py).
    genex_wacup.process(os.path.join(HERE, T["wsz"]))
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
    """text.bmp's ink as the app finds it: the commonest colour in the first two rows far from the
    space cell's."""
    a = np.asarray(SHEETS["text"])[:12, :155].reshape(-1, 3).astype(int)
    bg = np.asarray(SHEETS["text"])[0, 150].astype(int)
    far = np.abs(a - bg).sum(1) >= 96
    vals, counts = np.unique(a[far], axis=0, return_counts=True)
    return tuple(int(v) for v in vals[counts.argmax()])


def pl_font(size=11):
    return font(size, 400)


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
        sx = x0 + (46 if state["pressed"] == name else 0)
        blit(img, S["shufrep"], (sx, 73 if on else 61, 23, 12), 219 + x0, 58)
    if state["pressed"] == "close":
        blit(img, S["titlebar"], (18, 9, 9, 9), 264, 3)
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
    # the title box blanked with text.bmp's space, then the title in the playlist's TrueType font
    # in text.bmp's ink, clipped as the app clips it
    for x in range(0, 154, 5):
        blit(img, S["text"], (150, 0, min(5, 154 - x), 6), 111 + x, 24)
    layer = Image.new("RGB", (275, 116))
    layer.paste(img)
    ImageDraw.Draw(layer).text((111, 24 + 3 + 2), state["title"], fill=text_ink(), font=pl_font(11), anchor="lm")
    img.paste(layer.crop((111, 22, 265, 36)), (111, 22))
    draw_bitmap_text(img, "192", 111, 43)
    draw_bitmap_text(img, "44", 156, 43)
    cols = [c for c, _ in viscolor()]
    vis = Image.new("RGB", (76, 16))
    vp = vis.load()
    for y in range(16):
        for x in range(76):
            vp[x, y] = cols[1] if (y % 2 == 1 and x % 2 == 0) else cols[0]
    for x in range(75):
        if x % 4 == 3:
            continue
        hgt = state["bars"][x // 4] - 2
        for y in range(16 - hgt, 16):
            vp[x, y] = cols[min(17, max(2, y + 2))]
        pk = state["bars"][x // 4] + 2
        if 0 <= 16 - pk < 16:
            vp[x, 16 - pk] = cols[23]
    img.paste(vis, (24, 43))
    return img


def preview_eq(lit, state):
    sheet = SHEETS["eqmain"]
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
    sheet = SHEETS["pledit"]
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
    p = T["pl"]
    lx, lw = 12, w - 32
    d.rectangle((lx, 20, lx + lw - 1, h - 39), fill=hexc(p["normalbg"]))
    f = pl_font(11)
    for i, (txt, dur) in enumerate(rows):
        y = 23 + i * 15
        if y + 15 > h - 38:
            break
        if i == 2:
            d.rectangle((lx, y, lx + lw - 1, y + 14), fill=hexc(p["selectedbg"]))
        col = hexc(p["current"]) if i == 1 else hexc(p["normal"])
        d.text((lx + 2, y + 8), f"{i + 1}. {txt}", fill=col, font=f, anchor="lm")
        d.text((lx + lw - 3, y + 8), dur, fill=col, font=f, anchor="rm")
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
    pic = Image.linear_gradient("L").resize((w - 22, h - 34)).convert("RGB")
    arr = np.array(pic).astype(np.float32) / 255
    c0, c1 = ((255, 204, 188), (230, 74, 25))
    col = np.stack([c0[i] + (c1[i] - c0[i]) * arr[..., 0] for i in range(3)], -1)
    img.paste(Image.fromarray(col.astype(np.uint8)), (11, 20))
    return img


PREVIEW_ROWS = [("Night Drive - Copper Wire", "4:12"), ("Slow Burn - Lantern Hours", "3:47"),
                ("Kiln - Second Firing", "5:03"), ("Ash & Smoke - Afterglow", "2:58"),
                ("Ember Trio - Coal Seam", "6:21"), ("Field Notes - Warm Static", "3:33"),
                ("Tinder - Small Hours", "4:40"), ("The Forge - Bellows", "3:09"),
                ("Hearth - Long Winter", "5:51"), ("Glowworm - Low Light", "4:05"),
                ("Foundry - Pour", "3:22")]


def preview():
    bars = [12, 15, 14, 11, 13, 10, 9, 11, 8, 7, 9, 6, 5, 6, 4, 3, 4, 2, 3]
    A = dict(pressed=None, eq=True, pl=True, clutter="AV", shuffle=True, repeat=False, playing=True, stereo=True,
             pos=0.38, seek=False, volume=72, vdrag=False, balance=0, time=207, remaining=False,
             title=f"{T['name']} - drawn from scratch", bars=bars)
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
        col.paste(preview_playlist(lit, 275, 232, PREVIEW_ROWS, pressed_close=not lit, drag=not lit), (0, 232))
        col.paste(preview_gen(lit, 275, 140, "album art", pressed_close=not lit), (0, 464))
        cols.append(col)
    gap = 12
    out = Image.new("RGB", (275 * 2 + gap * 3, cols[0].height + gap * 2), T["desk"])
    out.paste(cols[0], (gap, gap))
    out.paste(cols[1], (275 + 2 * gap, gap))
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    out.save(os.path.join(HERE, f"preview-{K()}.png"))


def check_sheets():
    """Sizes and the app's own reads: gen.bmp's letter rows, text.bmp's plain space cell."""
    sizes = {"main": (275, 116), "titlebar": (344, 87), "cbuttons": (136, 36), "shufrep": (92, 85),
             "posbar": (307, 10), "volume": (68, 433), "balance": (68, 433), "monoster": (56, 24),
             "playpaus": (48, 9), "numbers": (99, 13), "nums_ex": (108, 13), "text": (155, 18),
             "pledit": (280, 186), "eqmain": (275, 315), "gen": (194, 109), "genex": (256, 64)}
    for k, s in sizes.items():
        assert SHEETS[k].size == s and SHEETS[k].mode == "RGB", (k, SHEETS[k].size)
    gen_letters()
    sp = np.asarray(SHEETS["text"].crop((150, 0, 155, 6)))
    assert (sp == np.array(T["disp"])).all(), "text.bmp's space cell must be plain display colour"
    title_box = np.asarray(SHEETS["main"].crop((111, 24, 265, 30)))
    assert (title_box == np.array(T["disp"])).all(), "the title box must be the display colour"


def run(key):
    global T, OUT
    T = dict(THEMES[key], key=key)
    OUT = os.path.join(HERE, "out", key)
    os.makedirs(OUT, exist_ok=True)
    names = build()
    check_sheets()
    preview()
    print(f"{key}: {T['wsz']} ({len(names)} files), preview-{key}.png, title ink {text_ink()}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--list" in args:
        print("\n".join(THEME_KEYS))
        sys.exit(0)
    keys = []
    for a in args:
        if a not in THEMES:
            sys.exit(f"unknown theme {a!r}; try --list")
        keys.append(a)
    for k in keys or THEME_KEYS:
        run(k)
