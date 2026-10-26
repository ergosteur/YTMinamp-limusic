#!/usr/bin/python3
"""YTMinamp Classic: a classic Winamp 2.x skin in the grey 3D desktop look of the late 1990s.

The 3D control face, the classic 2px bevels, sunken white fields, push buttons that invert when
pressed, trackbars, caption buttons, and navy-to-blue gradient title bars. Every pixel is drawn
here from code, with hand-made pixel fonts; the bottom-right emblem spot holds the app's own
icon (src-tauri/icons/icon.png), downscaled.

    /usr/bin/python3 -I gen_skin.py            # build
    /usr/bin/python3 -I gen_skin.py --list     # theme names

Writes the sheets into out/<theme>/, zips them flat into YTMinamp-Classic.wsz beside this file
and draws preview-<theme>.png (every window put together from the sprites the way the app does,
2x).
"""

import os
import sys
import zipfile
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skins/genex_wacup.py, which finishes each .wsz
import genex_wacup  # noqa: E402

ICON = os.path.join(HERE, os.pardir, os.pardir, "src-tauri", "icons", "icon.png")  # the app's icon

# ------------------------------------------------------------------------------------------
# The theme: the classic late-1990s desktop scheme's system colours (one theme).
# ------------------------------------------------------------------------------------------

THEMES = {
    "classic": dict(
        face=(192, 192, 192), light=(223, 223, 223), hilight=(255, 255, 255),
        shadow=(128, 128, 128), dark=(0, 0, 0),
        cap_a=((0, 0, 128), (16, 132, 208)), cap_i=((128, 128, 128), (192, 192, 192)),
        cap_text_i=(192, 192, 192), select=(0, 0, 128),
        pl_current="#000080", pl_selected="#C0C0E0",
    ),
}

T = SimpleNamespace()          # the theme being built (set_theme)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LED = (0, 255, 0)              # the CD-player style readouts
LED_GHOST = (0, 38, 0)
LED_DIM = (0, 110, 0)
SEP = (255, 0, 255)            # gen.bmp letter separators (never shown)
OUT = ""


def set_theme(name):
    global OUT
    T.__dict__.clear()
    T.name = name
    T.__dict__.update(THEMES[name])
    # The scrollbar track: the classic look dithers white over the face; a flat blend of the two here,
    # since a 1px checker can't tile across the playlist's 29px (odd) side tiles.
    T.track = lerp(T.face, WHITE, 0.5)
    OUT = os.path.join(HERE, "out", name)
    os.makedirs(OUT, exist_ok=True)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# ------------------------------------------------------------------------------------------
# Canvas helpers (numpy, H x W x 3, int)
# ------------------------------------------------------------------------------------------


def new(w, h, col=None):
    a = np.zeros((h, w, 3), dtype=np.int32)
    a[:, :] = T.face if col is None else col
    return a


def rect(a, x, y, w, h, col):
    if w > 0 and h > 0:
        a[max(0, y):y + h, max(0, x):x + w] = col


def px(a, x, y, col):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = col


def frame(a, x, y, w, h, tl, br):
    """A 1px rectangle, the classic DrawEdge order: top/left first, bottom/right over the corners."""
    rect(a, x, y, w - 1, 1, tl)
    rect(a, x, y, 1, h - 1, tl)
    rect(a, x, y + h - 1, w, 1, br)
    rect(a, x + w - 1, y, 1, h, br)


def edge_window(a, x, y, w, h):
    """A window's raised frame: light / white outside-in at top-left, black / grey at bottom-right."""
    frame(a, x, y, w, h, T.light, T.dark)
    frame(a, x + 1, y + 1, w - 2, h - 2, T.hilight, T.shadow)


def button(a, x, y, w, h, state="up"):
    """A push button. up: raised (white outermost, as classic buttons are drawn); down: pressed, a black
    outline round a grey one; checked: latched in, sunken with the face dithered with white."""
    rect(a, x, y, w, h, T.face)
    if state == "up":
        frame(a, x, y, w, h, T.hilight, T.dark)
        frame(a, x + 1, y + 1, w - 2, h - 2, T.light, T.shadow)
    elif state == "down":
        frame(a, x, y, w, h, T.dark, T.dark)
        frame(a, x + 1, y + 1, w - 2, h - 2, T.shadow, T.shadow)
    else:  # checked
        dither(a, x + 2, y + 2, w - 4, h - 4)
        frame(a, x, y, w, h, T.dark, T.hilight)
        frame(a, x + 1, y + 1, w - 2, h - 2, T.shadow, T.light)


def dither(a, x, y, w, h):
    for r in range(h):
        for c in range(w):
            if (r + c) % 2 == 0:
                px(a, x + c, y + r, T.hilight)


def sunken(a, x, y, w, h, fill=WHITE):
    """A sunken field (edit box, list, display): (x, y, w, h) includes its 2px border."""
    rect(a, x + 2, y + 2, w - 4, h - 4, fill)
    frame(a, x, y, w, h, T.shadow, T.hilight)
    frame(a, x + 1, y + 1, w - 2, h - 2, T.dark, T.light)


def etched_h(a, x, y, w):
    rect(a, x, y, w, 1, T.shadow)
    rect(a, x, y + 1, w, 1, T.hilight)


def save(a, name):
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, name))
    return img


# ------------------------------------------------------------------------------------------
# Pixel fonts (all drawn for these skins)
# ------------------------------------------------------------------------------------------

def G(*rows):
    return list(rows)


# 4x5 font for text.bmp (kbps/kHz digits, the playlist's times).
FONT5 = {
    "A": G(".##.", "#..#", "####", "#..#", "#..#"), "B": G("###.", "#..#", "###.", "#..#", "###."),
    "C": G(".###", "#...", "#...", "#...", ".###"), "D": G("###.", "#..#", "#..#", "#..#", "###."),
    "E": G("####", "#...", "###.", "#...", "####"), "F": G("####", "#...", "###.", "#...", "#..."),
    "G": G(".###", "#...", "#.##", "#..#", ".###"), "H": G("#..#", "#..#", "####", "#..#", "#..#"),
    "I": G("###", ".#.", ".#.", ".#.", "###"), "J": G("...#", "...#", "...#", "#..#", ".##."),
    "K": G("#..#", "#.#.", "##..", "#.#.", "#..#"), "L": G("#...", "#...", "#...", "#...", "####"),
    "M": G("#..#", "####", "####", "#..#", "#..#"), "N": G("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": G(".##.", "#..#", "#..#", "#..#", ".##."), "P": G("###.", "#..#", "###.", "#...", "#..."),
    "Q": G(".##.", "#..#", "#..#", "#.#.", ".#.#"), "R": G("###.", "#..#", "###.", "#.#.", "#..#"),
    "S": G(".###", "#...", ".##.", "...#", "###."), "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#..#", "#..#", "#..#", "#..#", ".##."), "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#..#", "#..#", "####", "####", "#..#"), "X": G("#..#", "#..#", ".##.", "#..#", "#..#"),
    "Y": G("#.#", "#.#", ".#.", ".#.", ".#."), "Z": G("####", "...#", ".##.", "#...", "####"),
    "0": G(".#.", "#.#", "#.#", "#.#", ".#."), "1": G(".#", "##", ".#", ".#", ".#"),
    "2": G("##.", "..#", ".#.", "#..", "###"), "3": G("##.", "..#", ".#.", "..#", "##."),
    "4": G("#.#", "#.#", "###", "..#", "..#"), "5": G("###", "#..", "##.", "..#", "##."),
    "6": G(".##", "#..", "##.", "#.#", ".#."), "7": G("###", "..#", ".#.", ".#.", ".#."),
    "8": G(".#.", "#.#", ".#.", "#.#", ".#."), "9": G(".#.", "#.#", ".##", "..#", "##."),
    '"': G("#.#", "#.#", "...", "...", "..."), "@": G(".##.", "#.##", "#.##", "#...", ".###"),
    "…": G(".....", ".....", ".....", ".....", "#.#.#"), ".": G(".", ".", ".", ".", "#"),
    ":": G(".", "#", ".", "#", "."), "(": G(".#", "#.", "#.", "#.", ".#"), ")": G("#.", ".#", ".#", ".#", "#."),
    "-": G("...", "...", "###", "...", "..."), "'": G("#", "#", ".", ".", "."),
    "!": G("#", "#", "#", ".", "#"), "_": G("....", "....", "....", "....", "####"),
    "+": G("...", ".#.", "###", ".#.", "..."), "\\": G("#..", "#..", ".#.", "..#", "..#"),
    "/": G("..#", "..#", ".#.", "#..", "#.."), "[": G("##", "#.", "#.", "#.", "##"),
    "]": G("##", ".#", ".#", ".#", "##"), "^": G(".#.", "#.#", "...", "...", "..."),
    "&": G(".#..", "#.#.", ".#..", "#.#.", ".#.#"), "%": G("#.#", "..#", ".#.", "#..", "#.#"),
    ",": G("..", "..", "..", ".#", "#."), "=": G("...", "###", "...", "###", "..."),
    "$": G(".###", "#.#.", ".##.", ".#.#", "###."), "#": G(".#.#", "####", ".#.#", "####", ".#.#"),
    "å": G(".##.", ".##.", "#..#", "####", "#..#"), "ö": G("#..#", ".##.", "#..#", "#..#", ".##."),
    "ä": G("#..#", ".##.", "#..#", "####", "#..#"), "?": G("###.", "...#", ".##.", "....", ".#.."),
    "*": G("#.#", ".#.", "###", ".#.", "#.#"), " ": G("...", "...", "...", "...", "..."),
}

# "Small" font, 7 rows (caps 0-4, x-height 1-4, descenders 5-6), after the era's tiny UI face.
_CAPS = {
    "A": G(".#.", "#.#", "###", "#.#", "#.#"), "B": G("##.", "#.#", "##.", "#.#", "##."),
    "C": G(".##", "#..", "#..", "#..", ".##"), "D": G("##.", "#.#", "#.#", "#.#", "##."),
    "E": G("###", "#..", "##.", "#..", "###"), "F": G("###", "#..", "##.", "#..", "#.."),
    "G": G(".##", "#..", "#.#", "#.#", ".##"), "H": G("#.#", "#.#", "###", "#.#", "#.#"),
    "I": G("###", ".#.", ".#.", ".#.", "###"), "J": G("..#", "..#", "..#", "#.#", ".#."),
    "K": G("#.#", "#.#", "##.", "#.#", "#.#"), "L": G("#..", "#..", "#..", "#..", "###"),
    "M": G("#...#", "##.##", "#.#.#", "#...#", "#...#"), "N": G("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": G(".#.", "#.#", "#.#", "#.#", ".#."), "P": G("##.", "#.#", "##.", "#..", "#.."),
    "Q": G(".#.", "#.#", "#.#", "##.", ".##"), "R": G("##.", "#.#", "##.", "#.#", "#.#"),
    "S": G(".##", "#..", ".#.", "..#", "##."), "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#.#", "#.#", "#.#", "#.#", "###"), "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#...#", "#...#", "#.#.#", "##.##", "#...#"), "X": G("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": G("#.#", "#.#", ".#.", ".#.", ".#."), "Z": G("###", "..#", ".#.", "#..", "###"),
}
_LOWER = {
    "a": (1, [".##", "#.#", "#.#", ".##"]), "b": (0, ["#..", "##.", "#.#", "#.#", "##."]),
    "c": (1, [".##", "#..", "#..", ".##"]), "d": (0, ["..#", ".##", "#.#", "#.#", ".##"]),
    "e": (1, [".#.", "###", "#..", ".##"]), "f": (0, [".##", "#..", "##.", "#..", "#.."]),
    "g": (1, [".##", "#.#", "#.#", ".##", "..#", "##."]), "h": (0, ["#..", "##.", "#.#", "#.#", "#.#"]),
    "i": (0, ["#", ".", "#", "#", "#"]), "j": (0, [".#", "..", ".#", ".#", ".#", ".#", "#."]),
    "k": (0, ["#..", "#.#", "##.", "##.", "#.#"]), "l": (0, ["#", "#", "#", "#", "#"]),
    "m": (1, ["##.#.", "#.#.#", "#.#.#", "#.#.#"]), "n": (1, ["##.", "#.#", "#.#", "#.#"]),
    "o": (1, [".#.", "#.#", "#.#", ".#."]), "p": (1, ["##.", "#.#", "#.#", "##.", "#..", "#.."]),
    "q": (1, [".##", "#.#", "#.#", ".##", "..#", "..#"]), "r": (1, ["#.#", "##.", "#..", "#.."]),
    "s": (1, [".##", "#..", "..#", "##."]), "t": (0, [".#.", "###", ".#.", ".#.", "..#"]),
    "u": (1, ["#.#", "#.#", "#.#", ".##"]), "v": (1, ["#.#", "#.#", "#.#", ".#."]),
    "w": (1, ["#...#", "#.#.#", "#.#.#", ".#.#."]), "x": (1, ["#.#", ".#.", ".#.", "#.#"]),
    "y": (1, ["#.#", "#.#", "#.#", ".##", "..#", "##."]), "z": (1, ["###", "..#", "#..", "###"]),
}


def _pad(top, rows, height):
    w = len(rows[0])
    return ["." * w] * top + rows + ["." * w] * (height - top - len(rows))


SMALL = {c: _pad(0, g, 7) for c, g in _CAPS.items()}
SMALL.update({c: _pad(t, g, 7) for c, (t, g) in _LOWER.items()})
for _c in "0123456789+-.:":
    SMALL[_c] = _pad(0, FONT5[_c], 7)
SMALL[" "] = ["..."] * 7

# Bold caption font, 9 rows (caps 0-6, x-height 2-6, descenders 7-8), in the spirit of the
# bold system font on classic title bars.
_BCAPS = {
    "A": G(".###.", "##.##", "##.##", "#####", "##.##", "##.##", "##.##"),
    "B": G("####.", "##.##", "##.##", "####.", "##.##", "##.##", "####."),
    "C": G(".####", "##...", "##...", "##...", "##...", "##...", ".####"),
    "D": G("####.", "##.##", "##.##", "##.##", "##.##", "##.##", "####."),
    "E": G("#####", "##...", "##...", "####.", "##...", "##...", "#####"),
    "F": G("#####", "##...", "##...", "####.", "##...", "##...", "##..."),
    "G": G(".####", "##...", "##...", "##.##", "##.##", "##.##", ".####"),
    "H": G("##.##", "##.##", "##.##", "#####", "##.##", "##.##", "##.##"),
    "I": G("##", "##", "##", "##", "##", "##", "##"),
    "J": G("...##", "...##", "...##", "...##", "...##", "##.##", ".###."),
    "K": G("##.##", "##.##", "####.", "###..", "####.", "##.##", "##.##"),
    "L": G("##...", "##...", "##...", "##...", "##...", "##...", "#####"),
    "M": G("##...##", "###.###", "#######", "##.#.##", "##...##", "##...##", "##...##"),
    "N": G("##..##", "###.##", "######", "##.###", "##..##", "##..##", "##..##"),
    "O": G(".###.", "##.##", "##.##", "##.##", "##.##", "##.##", ".###."),
    "P": G("####.", "##.##", "##.##", "####.", "##...", "##...", "##..."),
    "Q": G(".###.", "##.##", "##.##", "##.##", "##.##", "##.#.", ".##.#"),
    "R": G("####.", "##.##", "##.##", "####.", "##.##", "##.##", "##.##"),
    "S": G(".####", "##...", "##...", ".###.", "...##", "...##", "####."),
    "T": G("######", "..##..", "..##..", "..##..", "..##..", "..##..", "..##.."),
    "U": G("##.##", "##.##", "##.##", "##.##", "##.##", "##.##", ".###."),
    "V": G("##.##", "##.##", "##.##", "##.##", ".###.", ".###.", "..#.."),
    "W": G("##...##", "##...##", "##...##", "##.#.##", "#######", "###.###", "##...##"),
    "X": G("##..##", "##..##", ".####.", "..##..", ".####.", "##..##", "##..##"),
    "Y": G("##..##", "##..##", ".####.", "..##..", "..##..", "..##..", "..##.."),
    "Z": G("######", "....##", "...##.", "..##..", ".##...", "##....", "######"),
}
_BLOWER = {
    "a": (2, [".###.", "...##", ".####", "##.##", ".####"]),
    "b": (0, ["##...", "##...", "####.", "##.##", "##.##", "##.##", "####."]),
    "c": (2, [".###", "##..", "##..", "##..", ".###"]),
    "d": (0, ["...##", "...##", ".####", "##.##", "##.##", "##.##", ".####"]),
    "e": (2, [".###.", "##.##", "#####", "##...", ".####"]),
    "f": (0, [".###", "##..", "###.", "##..", "##..", "##..", "##.."]),
    "g": (2, [".####", "##.##", "##.##", "##.##", ".####", "...##", "####."]),
    "h": (0, ["##...", "##...", "####.", "##.##", "##.##", "##.##", "##.##"]),
    "i": (0, ["##", "..", "##", "##", "##", "##", "##"]),
    "j": (0, ["..##", "....", "..##", "..##", "..##", "..##", "..##", "..##", "###."]),
    "k": (0, ["##...", "##...", "##.##", "####.", "###..", "####.", "##.##"]),
    "l": (0, ["##"] * 7),
    "m": (2, ["######.", "##.#.##", "##.#.##", "##.#.##", "##.#.##"]),
    "n": (2, ["####.", "##.##", "##.##", "##.##", "##.##"]),
    "o": (2, [".###.", "##.##", "##.##", "##.##", ".###."]),
    "p": (2, ["####.", "##.##", "##.##", "##.##", "####.", "##...", "##..."]),
    "q": (2, [".####", "##.##", "##.##", "##.##", ".####", "...##", "...##"]),
    "r": (2, ["##.##", "#####", "##...", "##...", "##..."]),
    "s": (2, [".####", "##...", ".###.", "...##", "####."]),
    "t": (0, [".##.", ".##.", "####", ".##.", ".##.", ".##.", "..##"]),
    "u": (2, ["##.##", "##.##", "##.##", "##.##", ".####"]),
    "v": (2, ["##.##", "##.##", "##.##", ".###.", "..#.."]),
    "w": (2, ["##...##", "##.#.##", "##.#.##", "#######", ".##.##."]),
    "x": (2, ["##.##", ".###.", "..#..", ".###.", "##.##"]),
    "y": (2, ["##.##", "##.##", "##.##", "##.##", ".####", "...##", "####."]),
    "z": (2, ["#####", "...##", "..##.", ".##..", "#####"]),
}
BOLD = {c: _pad(0, g, 9) for c, g in _BCAPS.items()}
BOLD.update({c: _pad(t, g, 9) for c, (t, g) in _BLOWER.items()})
BOLD[" "] = ["..."] * 9


def glyph_w(font, c):
    return len(font[c][0])


def text_w(font, s, gap=1):
    s = [c for c in s if c in font]
    return sum(glyph_w(font, c) for c in s) + gap * max(0, len(s) - 1)


def draw_text(a, font, s, x, y, col, gap=1):
    for c in s:
        if c not in font:
            continue
        g = font[c]
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    px(a, x + k, y + r, col)
        x += len(g[0]) + gap
    return x


def text_center(a, font, s, cx, y, col, gap=1):
    draw_text(a, font, s, cx - text_w(font, s, gap) // 2, y, col, gap)


# ------------------------------------------------------------------------------------------
# Title bars and their buttons
# ------------------------------------------------------------------------------------------

CAP_Y, CAP_H = 2, 11          # caption rows 2..12, under the frame's two bevel rows


def caption(a, x0, x1, lit, gradient=True):
    """Fills columns x0..x1 of rows CAP_Y.. with the caption colour (left to right gradient)."""
    c0, c1 = T.cap_a if lit else T.cap_i
    if not gradient:
        c1 = c0
    n = max(1, x1 - x0)
    for x in range(x0, x1 + 1):
        rect(a, x, CAP_Y, 1, CAP_H, lerp(c0, c1, (x - x0) / n))


def cap_text_col(lit):
    return WHITE if lit else T.cap_text_i


def cap_button(a, x, y, kind, pressed=False):
    """9x9 caption button: face-coloured, black glyph (minimise, maximise, close)."""
    button(a, x, y, 9, 9, "down" if pressed else "up")
    o = 1 if pressed else 0
    X, Y = x + 2 + o, y + 2 + o
    ink = BLACK
    if kind == "close":
        for r, row in enumerate(["#...#", "##.##", ".###.", "##.##", "#...#"]):
            for c, ch in enumerate(row):
                if ch == "#":
                    px(a, X + c, Y + r, ink)
    elif kind == "minimize":
        rect(a, X, Y + 3, 4, 2, ink)
    elif kind == "shade":        # Winamp's shade mode: the maximise box
        rect(a, X, Y, 5, 2, ink)
        rect(a, X, Y, 1, 5, ink)
        rect(a, X + 4, Y, 1, 5, ink)
        rect(a, X, Y + 4, 5, 1, ink)


def app_icon(a, x, y, pressed=False):
    """9x9 window icon (the options button): a little compact disc, drawn here."""
    o = 1 if pressed else 0
    for r in range(9):
        for c in range(9):
            d = ((c - 4) ** 2 + (r - 4) ** 2) ** 0.5
            if d > 4.4:
                continue
            if d > 3.6:
                col = (64, 64, 64)
            elif d < 1.1:
                continue                         # the hole shows the caption through
            elif d < 1.9:
                col = (150, 150, 150)
            else:
                col = (232, 232, 236)
                if (c - r) in (1, 2) and c > 4:
                    col = (150, 210, 255)        # a sheen
                elif (r - c) in (1, 2) and r > 4:
                    col = (255, 236, 150)
            px(a, x + c + o, y + r + o, col)


def win_titlebar(title, lit, buttons, icon=True):
    """275x14: the window frame's top and a caption with icon, title and buttons."""
    a = new(275, 14)
    rect(a, 0, 0, 274, 1, T.light)
    rect(a, 0, 0, 1, 14, T.light)
    rect(a, 274, 0, 1, 14, T.dark)
    rect(a, 1, 1, 272, 1, T.hilight)
    rect(a, 1, 1, 1, 13, T.hilight)
    rect(a, 273, 1, 1, 13, T.shadow)
    caption(a, 2, 272, lit)
    if icon:
        app_icon(a, 6, 3)
    draw_text(a, BOLD, title, 18 if icon else 5, 4, cap_text_col(lit))
    for kind, x in buttons:
        cap_button(a, x, 3, kind)
    return a


def main_titlebar(lit):
    return win_titlebar("YTMinamp", lit, [("minimize", 244), ("shade", 254), ("close", 264)])


def eq_titlebar(lit):
    return win_titlebar("Equalizer", lit, [("close", 264)], icon=False)


# ------------------------------------------------------------------------------------------
# titlebar.bmp (344 x 87)
# ------------------------------------------------------------------------------------------

CLUTTER_SLOTS = [("O", 3, 8), ("A", 11, 7), ("I", 18, 7), ("D", 25, 8), ("V", 33, 7)]


def clutter_bar(lit_letters):
    """8x43: a thin sunken strip of toggle cells, O A I D V; a cell that's on is latched in."""
    a = new(8, 43)
    frame(a, 0, 0, 8, 43, T.shadow, T.hilight)
    for letter, y, h in CLUTTER_SLOTS:
        on = letter in lit_letters
        o = 1 if on else 0
        if on:
            rect(a, 1, y, 6, h, T.face)
            dither(a, 2, y + 1, 5, h - 1)
            rect(a, 1, y, 6, 1, T.shadow)
            rect(a, 1, y, 1, h, T.shadow)
        draw_text(a, SMALL, letter, 3 + o - (1 if letter in "M" else 0), y + (h - 5) // 2 + o - (0 if on else 0),
                  BLACK)
    return a


def make_titlebar():
    a = new(344, 87)
    for kind, x in (("minimize", 9), ("close", 18)):
        cap_button(a, x, 0, kind)
        cap_button(a, x, 9, kind, pressed=True)
    # options: the icon on the active caption, and pressed (sunken in)
    caption_bg = T.cap_a[0]
    rect(a, 0, 0, 9, 9, caption_bg)
    app_icon(a, 0, 0)
    rect(a, 0, 9, 9, 9, caption_bg)
    frame(a, 0, 9, 9, 9, T.shadow, T.hilight)
    app_icon(a, 0, 9, pressed=True)
    cap_button(a, 0, 18, "shade")
    cap_button(a, 9, 18, "shade", pressed=True)
    a[0:14, 27:302] = main_titlebar(True)
    a[15:29, 27:302] = main_titlebar(False)
    a[29:43, 27:302] = main_titlebar(True)       # shade-mode bars: copies
    a[42:56, 27:302] = main_titlebar(False)
    unlit = clutter_bar("")
    lit = clutter_bar("OAIDV")
    a[0:43, 304:312] = unlit
    a[0:43, 312:320] = unlit
    for (letter, y, h), sx, sy in zip(CLUTTER_SLOTS, [304, 312, 320, 328, 336], [47, 55, 62, 69, 77]):
        a[sy:sy + h, sx:sx + 8] = lit[y:y + h]
    return a


# ------------------------------------------------------------------------------------------
# The emblem: the app's own icon (red disc, white play mark, yellow bolt), downscaled
# ------------------------------------------------------------------------------------------


def emblem(bg, size=16):
    """The icon at sprite size with a hard edge (alpha cut at half), as the era's icons had."""
    im = Image.open(ICON).convert("RGBA").resize((size, size), Image.LANCZOS)
    rgba = np.asarray(im).astype(np.float64)
    al = (rgba[..., 3:4] >= 128).astype(np.float64)
    out = np.array(bg, np.float64) * (1 - al) + rgba[..., :3] * al
    return np.round(out).astype(np.int32)


# ------------------------------------------------------------------------------------------
# main.bmp (275 x 116)
# ------------------------------------------------------------------------------------------

SEG = {
    "a": [(0, c) for c in range(2, 7)],
    "g": [(6, c) for c in range(2, 7)],
    "d": [(12, c) for c in range(2, 7)],
    "f": [(r, c) for r in range(1, 6) for c in (1, 2)],
    "b": [(r, c) for r in range(1, 6) for c in (6, 7)],
    "e": [(r, c) for r in range(7, 12) for c in (1, 2)],
    "c": [(r, c) for r in range(7, 12) for c in (6, 7)],
}
DIGIT_SEGS = {0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc",
              5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg"}


def seven_seg(a, x, y, lit_segs):
    rect(a, x, y, 9, 13, BLACK)
    for s, cells in SEG.items():
        for r, c in cells:
            px(a, x + c, y + r, LED if s in lit_segs else LED_GHOST)


def h_channel(a, x, y, w, open_left=False, open_right=False):
    """A trackbar's 4px sunken groove along x..x+w-1, rows y..y+3."""
    rect(a, x, y, w, 1, T.shadow)
    rect(a, x, y + 1, w, 1, T.dark)
    rect(a, x, y + 2, w, 1, T.light)
    rect(a, x, y + 3, w, 1, T.hilight)
    if not open_left:
        rect(a, x, y, 1, 3, T.shadow)
        rect(a, x + 1, y + 1, 1, 2, T.dark)
    if not open_right:
        rect(a, x + w - 1, y, 1, 4, T.hilight)
        rect(a, x + w - 2, y + 1, 1, 2, T.light)


def v_channel(a, x, y, h):
    rect(a, x, y, 1, h, T.shadow)
    rect(a, x + 1, y, 1, h, T.dark)
    rect(a, x + 2, y, 1, h, T.light)
    rect(a, x + 3, y, 1, h, T.hilight)
    rect(a, x, y, 3, 1, T.shadow)
    rect(a, x + 1, y + 1, 2, 1, T.dark)
    rect(a, x, y + h - 1, 4, 1, T.hilight)
    rect(a, x + 1, y + h - 2, 2, 1, T.light)


def make_main():
    a = new(275, 116)
    edge_window(a, 0, 0, 275, 116)
    a[0:14, :] = main_titlebar(True)
    a[22:65, 10:18] = clutter_bar("")

    # the CD-player readout: time, play state and the analyzer on black
    sunken(a, 20, 20, 84, 43, BLACK)
    for x in (48, 60, 78, 90):
        seven_seg(a, x, 26, "")
    for yy in (29, 34):
        rect(a, 73, yy, 2, 2, LED)

    # title box and the kbps / kHz / mono / stereo row: white edit fields, black text
    sunken(a, 108, 20, 162, 17)
    sunken(a, 108, 38, 162, 18)
    draw_text(a, SMALL, "kbps", 128, 43, BLACK)
    draw_text(a, SMALL, "kHz", 168, 43, BLACK)

    # seek bar channel ends (the track itself is open-ended, under the moving thumb)
    for x0, w, ol, orr in ((14, 2, False, True), (264, 2, True, False)):
        h_channel(a, x0, 73, w, ol, orr)

    # the app's icon in the emblem spot
    emb = emblem(T.face)
    fh, fw = emb.shape[:2]
    a[90:90 + fh, 250:250 + fw] = emb  # the About spot, as main.bmp's 16px icons sit
    return a


# ------------------------------------------------------------------------------------------
# cbuttons.bmp (136 x 36)
# ------------------------------------------------------------------------------------------


def tri_right(a, x, y, h, col):
    half = h // 2
    for r in range(h):
        n = half - abs(r - half) + 1
        rect(a, x, y + r, n, 1, col)


def tri_left(a, x, y, h, col):
    half = h // 2
    for r in range(h):
        n = half - abs(r - half) + 1
        rect(a, x + half + 1 - n, y + r, n, 1, col)


def transport_icon(a, kind, x, y, w, h, pressed):
    ink = BLACK
    o = 1 if pressed else 0
    cx, cy = x + w // 2 + o, y + h // 2 + o
    if kind == "previous":
        rect(a, cx - 6, cy - 3, 2, 7, ink)
        tri_left(a, cx - 4, cy - 3, 7, ink)
        tri_left(a, cx, cy - 3, 7, ink)
    elif kind == "play":
        tri_right(a, cx - 2, cy - 4, 9, ink)
    elif kind == "pause":
        rect(a, cx - 4, cy - 3, 3, 7, ink)
        rect(a, cx + 1, cy - 3, 3, 7, ink)
    elif kind == "stop":
        rect(a, cx - 3, cy - 3, 7, 7, ink)
    elif kind == "next":
        tri_right(a, cx - 5, cy - 3, 7, ink)
        tri_right(a, cx - 1, cy - 3, 7, ink)
        rect(a, cx + 3, cy - 3, 2, 7, ink)
    elif kind == "eject":
        for r in range(4):
            rect(a, cx - 1 - r, cy - 4 + r, 2 * r + 3, 1, ink)
        rect(a, cx - 4, cy + 1, 9, 2, ink)


def make_cbuttons():
    a = new(136, 36)
    # 23px slots abut in the window: each button 22 wide, a face column between them
    specs = [("previous", 0, 22), ("play", 23, 22), ("pause", 46, 22), ("stop", 69, 22), ("next", 92, 22)]
    for kind, x, w in specs:
        for pressed, y in ((False, 0), (True, 18)):
            button(a, x, y, w, 18, "down" if pressed else "up")
            transport_icon(a, kind, x, y, w, 18, pressed)
    for pressed, y in ((False, 0), (True, 16)):
        button(a, 114, y, 22, 16, "down" if pressed else "up")
        transport_icon(a, "eject", 114, y, 22, 16, pressed)
    return a


# ------------------------------------------------------------------------------------------
# shufrep.bmp (92 x 85): latching push buttons
# ------------------------------------------------------------------------------------------


def toggle(a, x, y, w, h, label, on, pressed, font=SMALL):
    state = "checked" if on else ("down" if pressed else "up")
    button(a, x, y, w, h, state)
    if on and pressed:
        frame(a, x, y, w, h, T.dark, T.dark)
        frame(a, x + 1, y + 1, w - 2, h - 2, T.shadow, T.shadow)
    o = 1 if (on or pressed) else 0
    cap = 5
    text_center(a, font, label, x + w // 2 + o, y + (h - cap) // 2 + o, BLACK)


def make_shufrep():
    a = new(92, 85)
    for row, (on, pressed) in enumerate([(False, False), (False, True), (True, False), (True, True)]):
        y = row * 15
        toggle(a, 1, y, 27, 15, "Repeat", on, pressed)       # col 0: the gap after shuffle
        toggle(a, 28, y, 46, 15, "Shuffle", on, pressed)     # its 47th column sits under repeat
    for x, label, pressed in [(0, "EQ", False), (23, "PL", False), (46, "EQ", True), (69, "PL", True)]:
        toggle(a, x, 61, 23, 12, label, False, pressed)
        toggle(a, x, 73, 23, 12, label, True, pressed)
    return a


# ------------------------------------------------------------------------------------------
# monoster, playpaus, numbers, nums_ex, text
# ------------------------------------------------------------------------------------------


def make_monoster():
    a = new(56, 24, WHITE)
    for y, on in ((0, True), (12, False)):
        col = BLACK if on else T.shadow
        text_center(a, SMALL, "stereo", 14, y + 2, col)
        text_center(a, SMALL, "mono", 29 + 13, y + 2, col)
    return a


def make_playpaus():
    a = new(48, 9, BLACK)
    tri_right(a, 2, 1, 7, LED)
    rect(a, 9 + 2, 1, 2, 7, LED)
    rect(a, 9 + 5, 1, 2, 7, LED)
    rect(a, 18 + 2, 2, 5, 5, LED)
    rect(a, 39 + 1, 3, 1, 3, LED_DIM)
    return a


def make_numbers(ex):
    a = new(108 if ex else 99, 13, BLACK)
    for n in range(10):
        seven_seg(a, 9 * n, 0, DIGIT_SEGS[n])
    seven_seg(a, 90, 0, "")
    if ex:
        rect(a, 99, 0, 9, 13, BLACK)
        for r, c in SEG["g"]:
            px(a, 99 + c, r, LED)
    return a


FONT_GRID = [
    list("abcdefghijklmnopqrstuvwxyz\"@") + [None, None, " "],
    list("0123456789") + ["…", ".", ":", "(", ")", "-", "'", "!", "_", "+", "\\", "/", "[", "]", "^", "&", "%",
                          ",", "=", "$", "#"],
    ["å", "ö", "ä", "?", "*"] + [None] * 26,
]


def make_text():
    a = new(155, 18, WHITE)   # the space cell (x 150) is the title box's plain white
    for row, chars in enumerate(FONT_GRID):
        for col, ch in enumerate(chars):
            if ch is None or ch == " ":
                continue
            key = ch if ch in FONT5 else ch.upper()
            draw_text(a, FONT5, key, col * 5, row * 6, BLACK)
    return a


# ------------------------------------------------------------------------------------------
# Trackbars: posbar.bmp (307 x 10), volume.bmp / balance.bmp (68 x 433)
# ------------------------------------------------------------------------------------------


def thumb_down(a, x, y, pressed=False):
    """14x11 trackbar thumb pointing down: a raised body over the groove, then the point."""
    widths = [14] * 5 + [12, 10, 8, 6, 4, 2]
    rows = []
    for r, wd in enumerate(widths):
        l = x + (14 - wd) // 2
        rows.append((l, l + wd - 1))
        rect(a, l, y + r, wd, 1, T.face)
    if pressed:
        for r, (l, rr) in enumerate(rows):
            for c in range(l + 1, rr):
                if (c + r) % 2 == 0 and r > 0:
                    px(a, c, y + r, T.hilight)
    # top and left edges: white; right edges and the point's right slope: grey then black
    rect(a, x, y, 13, 1, T.hilight)
    for r, (l, rr) in enumerate(rows):
        px(a, l, y + r, T.hilight)
        px(a, rr, y + r, T.dark)
        if rr - 1 > l:
            px(a, rr - 1, y + r, T.shadow)
    px(a, x + 13, y, T.dark)


def thumb_right(a, x, y, pressed=False):
    """11x11 vertical-trackbar thumb pointing right (EQ)."""
    heights = [11] * 6 + [9, 7, 5, 3, 1]
    cols = []
    for c, ht in enumerate(heights):
        t = y + (11 - ht) // 2
        cols.append((t, t + ht - 1))
        rect(a, x + c, t, 1, ht, T.face)
    if pressed:
        for c, (t, b) in enumerate(cols):
            for r in range(t + 1, b):
                if (c + r) % 2 == 0 and c > 0:
                    px(a, x + c, r, T.hilight)
    rect(a, x, y, 1, 10, T.hilight)
    for c, (t, b) in enumerate(cols):
        px(a, x + c, t, T.hilight)
        px(a, x + c, b, T.dark)
        if b - 1 > t and c < 6:
            px(a, x + c, b - 1, T.shadow)
    # the point's lower slope: a grey line inside the black
    for c in range(6, 10):
        t, b = cols[c]
        if b - 1 > t:
            px(a, x + c, b - 1, T.shadow)
    rect(a, x, y + 10, 6, 1, T.dark)


def make_posbar():
    a = new(307, 10)
    h_channel(a, 0, 1, 248, True, True)
    for x0, pressed in ((248, False), (278, True)):
        h_channel(a, x0, 1, 29, True, True)
        # an 11px pointer in the 29px sprite (the sprite paints the groove either side of it)
        widths = [11] * 5 + [9, 7, 5, 3, 1]
        rows = []
        for r, wd in enumerate(widths):
            l = x0 + 9 + (11 - wd) // 2
            rows.append((l, l + wd - 1))
            rect(a, l, r, wd, 1, T.face)
        if pressed:
            for r, (l, rr) in enumerate(rows):
                for c in range(l + 1, rr):
                    if (c + r) % 2 == 0 and r > 0:
                        px(a, c, r, T.hilight)
        rect(a, x0 + 9, 0, 10, 1, T.hilight)
        for r, (l, rr) in enumerate(rows):
            px(a, l, r, T.hilight)
            px(a, rr, r, T.dark)
            if rr - 1 > l:
                px(a, rr - 1, r, T.shadow)
        px(a, x0 + 19, 0, T.dark)
    return a


def slider_sheet(width, x0, ticks):
    a = new(68, 433)
    for i in range(28):
        y = i * 15
        h_channel(a, x0, y + 2, width)
        for t in ticks:
            px(a, x0 + t, y + 12, BLACK)
    thumb_down(a, 0, 422, pressed=True)
    thumb_down(a, 15, 422)
    return a


def make_volume():
    return slider_sheet(68, 0, [7 + round(54 * k / 10) for k in range(11)])


def make_balance():
    return slider_sheet(38, 9, [7, 13, 19, 25, 31])


# ------------------------------------------------------------------------------------------
# eqmain.bmp (275 x 315)
# ------------------------------------------------------------------------------------------

EQ_BANDS = ["60", "170", "310", "600", "1k", "3k", "6k", "12k", "14k", "16k"]


def eq_slider_frame(a, x, y):
    """14x63: a vertical trackbar groove with ticks to the right."""
    rect(a, x, y, 14, 63, T.face)
    v_channel(a, x + 2, y, 63)
    for v in (0, 25, 50, 75, 100):
        r = 5 + round((1 - v / 100) * 51)
        rect(a, x + 12, y + r, 2, 1, BLACK)


CHECK = ["......#", ".....##", "#...###", "##.###.", "#####..", ".###...", "..#...."]


def checkbox(a, x, y, w, label, on, pressed):
    """A classic check box (11x11 here) and its label, on the face."""
    rect(a, x, y, w, 12, T.face)
    sunken(a, x, y, 11, 11, T.face if pressed else WHITE)
    if on:
        for r, row in enumerate(CHECK):
            for c, ch in enumerate(row):
                if ch == "#":
                    px(a, x + 2 + c, y + 2 + r, BLACK)
    draw_text(a, SMALL, label, x + 13, y + 3, BLACK)


def make_eqmain():
    a = new(275, 315)
    win = new(275, 116)
    edge_window(win, 0, 0, 275, 116)
    win[0:14, :] = eq_titlebar(True)
    # response graph: the black readout
    sunken(win, 84, 15, 117, 23, BLACK)
    # slider area
    for x in [21] + [78 + 18 * i for i in range(10)]:
        eq_slider_frame(win, x, 38)
    for lbl, yy in (("+12 dB", 41), ("0 dB", 66), ("-12 dB", 92)):
        text_center(win, SMALL, lbl, 56, yy, BLACK)
    text_center(win, SMALL, "Preamp", 28, 104, BLACK)
    for i, lbl in enumerate(EQ_BANDS):
        text_center(win, SMALL, lbl, 78 + 18 * i + 7, 104, BLACK)
    # an etched line between the preamp and the bands
    rect(win, 72, 40, 1, 60, T.shadow)
    rect(win, 73, 40, 1, 60, T.hilight)
    a[0:116, :] = win

    cap_button(a, 0, 125, "close", pressed=True)
    for x, label, on, pressed in [
        (10, "On", False, False), (36, "Auto", False, False), (69, "On", True, False), (95, "Auto", True, False),
        (128, "On", False, True), (154, "Auto", False, True), (187, "On", True, True), (213, "Auto", True, True),
    ]:
        checkbox(a, x, 119, 26 if label == "On" else 32, label, on, pressed)
    a[134:148, :] = eq_titlebar(True)
    a[149:163, :] = eq_titlebar(False)
    rect(a, 0, 164, 11, 23, T.face)
    thumb_right(a, 0, 164)
    thumb_right(a, 0, 176, pressed=True)
    for n in range(28):
        eq_slider_frame(a, 13 + (n % 14) * 15, 164 + (n // 14) * 65)
    for y, pressed in ((164, False), (176, True)):
        button(a, 224, y, 44, 12, "down" if pressed else "up")
        o = 1 if pressed else 0
        text_center(a, SMALL, "Presets", 224 + 22 + o, y + 3 + o, BLACK)
    # graph: black, a dim grid and the 0 dB line
    rect(a, 0, 294, 113, 19, BLACK)
    for x in range(0, 113, 12):
        for y in range(0, 19, 2):
            px(a, 2 + x, 294 + y, (0, 56, 0))
    for x in range(0, 113, 2):
        px(a, x, 294 + 9, (0, 72, 0))
    ramp = [(255, 40, 0)] * 3 + [(255, 220, 0)] * 4 + [LED] * 12
    for r in range(19):
        px(a, 115, 294 + r, ramp[r])
    for x in range(113):
        px(a, x, 314, (200, 200, 0) if x % 3 != 2 else BLACK)
    return a


# ------------------------------------------------------------------------------------------
# pledit.bmp (280 x 186) and gen.bmp (194 x 109): the 20px-titled frames
# ------------------------------------------------------------------------------------------


def bar20(w, lit, left=False, right=False, sunken_top=None):
    """A piece of a 20px titlebar: frame top, a solid caption (these tile, so no gradient), and
    optionally the list's sunken top edge (rows 18-19) from column sunken_top on."""
    a = new(w, 20)
    rect(a, 0, 0, w, 1, T.light)
    rect(a, 0, 1, w, 1, T.hilight)
    x0, x1 = 0, w - 1
    if left:
        rect(a, 0, 0, 1, 20, T.light)
        rect(a, 1, 1, 1, 19, T.hilight)
        x0 = 2
    if right:
        rect(a, w - 1, 0, 1, 20, T.dark)
        rect(a, w - 2, 1, 1, 19, T.shadow)
        x1 = w - 3
    caption(a, x0, x1, lit, gradient=False)
    return a


def size_grip(a, rx, by, n=12):
    """The diagonal size grip with its bottom-right corner at (rx, by): white / grey / grey lines."""
    for d in range(1, n):
        col = T.hilight if d % 4 == 1 else (T.shadow if d % 4 in (2, 3) else None)
        if col is None:
            continue
        for k in range(d + 1):
            px(a, rx - d + k, by - k, col)


def pl_title_piece(lit):
    t = bar20(100, lit)
    rect(t, 0, 18, 100, 1, T.shadow)
    rect(t, 0, 19, 100, 1, T.dark)
    text_center(t, BOLD, "Playlist Editor", 50, 4, cap_text_col(lit))
    return t


def make_pledit():
    a = new(280, 186)
    for lit, y in ((True, 0), (False, 21)):
        t = bar20(25, lit)
        rect(t, 0, 18, 25, 1, T.shadow)
        rect(t, 0, 19, 25, 1, T.dark)
        a[y:y + 20, 127:152] = t
        # top-left: the frame's corner, the window icon, the list's sunken corner
        t = bar20(25, lit, left=True)
        app_icon(t, 4, 3)
        rect(t, 10, 18, 15, 1, T.shadow)
        rect(t, 10, 18, 1, 2, T.shadow)
        rect(t, 11, 19, 14, 1, T.dark)
        a[y:y + 20, 0:25] = t
        a[y:y + 20, 26:126] = pl_title_piece(lit)
        # top-right: close button; the sunken box's top-right corner over the scrollbar
        t = bar20(25, lit, right=True)
        cap_button(t, 14, 3, "close")
        rect(t, 0, 18, 14, 1, T.shadow)
        rect(t, 0, 19, 13, 1, T.dark)
        rect(t, 14, 18, 1, 2, T.hilight)
        rect(t, 13, 19, 1, 1, T.light)
        a[y:y + 20, 153:178] = t

    # left side tile
    t = new(12, 29)
    rect(t, 0, 0, 1, 29, T.light)
    rect(t, 1, 0, 1, 29, T.hilight)
    rect(t, 10, 0, 1, 29, T.shadow)
    rect(t, 11, 0, 1, 29, T.dark)
    a[42:71, 0:12] = t
    # right side tile: the list's white, the scrollbar track, the sunken edge, the frame
    t = new(20, 29)
    rect(t, 0, 0, 5, 29, WHITE)
    rect(t, 5, 0, 8, 29, T.track)
    rect(t, 13, 0, 1, 29, T.light)
    rect(t, 14, 0, 1, 29, T.hilight)
    rect(t, 18, 0, 1, 29, T.shadow)
    rect(t, 19, 0, 1, 29, T.dark)
    a[42:71, 31:51] = t
    t = new(9, 9)
    cap_button(t, 0, 0, "close", pressed=True)
    a[42:51, 52:61] = t
    # scroll handles: a raised scrollbar thumb
    for x in (52, 61):
        button(a, x, 53, 8, 18, "up")

    def bottom_base(w):
        t = new(w, 38)
        rect(t, 0, 0, w, 1, T.light)
        rect(t, 0, 1, w, 1, T.hilight)
        rect(t, 0, 36, w, 1, T.shadow)
        rect(t, 0, 37, w, 1, T.dark)
        return t

    t = bottom_base(125)
    rect(t, 0, 0, 10, 2, T.face)
    rect(t, 10, 0, 1, 1, T.shadow)
    rect(t, 0, 0, 1, 37, T.light)
    rect(t, 1, 0, 1, 36, T.hilight)
    for bx, lbl in ((14, "Add"), (43, "Rem"), (72, "Sel"), (101, "Misc")):
        button(t, bx, 8, 22, 18, "up")
        text_center(t, SMALL, lbl, bx + 11, 14, BLACK)
    a[72:110, 0:125] = t

    t = bottom_base(150)
    rect(t, 145, 0, 5, 2, T.face)
    rect(t, 144, 0, 1, 2, T.hilight)
    rect(t, 143, 0, 1, 1, T.light)
    rect(t, 148, 0, 1, 37, T.shadow)
    rect(t, 149, 0, 1, 38, T.dark)
    rect(t, 0, 36, 148, 1, T.shadow)
    sunken(t, 4, 7, 55, 11)                      # running time (text.bmp at 7, 10)
    for k, kind in enumerate(["previous", "play", "pause", "stop", "next", "eject"]):
        bx = 3 + 10 * k
        button(t, bx, 22, 10, 10, "up")
        mini_transport_icon(t, kind, bx, 22)
    sunken(t, 64, 20, 35, 11)                    # mini time (66, 23); its colon is ours
    px(t, 84, 24, BLACK)
    px(t, 84, 26, BLACK)
    button(t, 106, 8, 22, 18, "up")
    text_center(t, SMALL, "List", 117, 14, BLACK)
    size_grip(t, 147, 35)
    a[72:110, 126:276] = t

    a[0:38, 179:204] = bottom_base(25)
    return a


def mini_transport_icon(a, kind, x, y):
    ink = BLACK
    cx, cy = x + 5, y + 5
    if kind == "previous":
        rect(a, cx - 3, cy - 2, 1, 5, ink)
        tri_left(a, cx - 2, cy - 2, 5, ink)
        tri_left(a, cx + 1, cy - 2, 5, ink)
    elif kind == "play":
        tri_right(a, cx - 1, cy - 3, 7, ink)
    elif kind == "pause":
        rect(a, cx - 2, cy - 2, 2, 5, ink)
        rect(a, cx + 1, cy - 2, 2, 5, ink)
    elif kind == "stop":
        rect(a, cx - 2, cy - 2, 5, 5, ink)
    elif kind == "next":
        tri_right(a, cx - 3, cy - 2, 5, ink)
        tri_right(a, cx, cy - 2, 5, ink)
        rect(a, cx + 3, cy - 2, 1, 5, ink)
    elif kind == "eject":
        for r in range(3):
            rect(a, cx - r, cy - 3 + r, 2 * r + 1, 1, ink)
        rect(a, cx - 2, cy + 1, 5, 1, ink)


GEN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def make_gen():
    a = new(194, 109)
    for lit, y in ((True, 0), (False, 21)):
        t = bar20(25, lit, left=True)
        app_icon(t, 4, 3)
        a[y:y + 20, 0:25] = t
        for x0 in (26, 52, 78, 104):
            a[y:y + 20, x0:x0 + 25] = bar20(25, lit)
        t = bar20(25, lit, right=True)
        cap_button(t, 14, 3, "close")
        a[y:y + 20, 130:155] = t

    def bottom(w, left_edge, grip):
        t = new(w, 14)
        rect(t, 0, 12, w, 1, T.shadow)
        rect(t, 0, 13, w, 1, T.dark)
        if left_edge:
            rect(t, 0, 0, 1, 13, T.light)
            rect(t, 1, 0, 1, 12, T.hilight)
        else:
            rect(t, w - 2, 0, 1, 13, T.shadow)
            rect(t, w - 1, 0, 1, 14, T.dark)
        if grip:
            size_grip(t, w - 3, 11, 10)
        return t

    a[42:56, 0:125] = bottom(125, True, False)
    a[57:71, 0:125] = bottom(125, False, True)
    t = new(25, 14)
    rect(t, 0, 12, 25, 1, T.shadow)
    rect(t, 0, 13, 25, 1, T.dark)
    a[72:86, 127:152] = t
    for x, w, h, outer_left in ((127, 11, 29, True), (158, 11, 24, True), (139, 8, 29, False), (170, 8, 24, False)):
        t = new(w, h)
        if outer_left:
            rect(t, 0, 0, 1, h, T.light)
            rect(t, 1, 0, 1, h, T.hilight)
        else:
            rect(t, w - 2, 0, 1, h, T.shadow)
            rect(t, w - 1, 0, 1, h, T.dark)
        a[42:42 + h, x:x + w] = t
    t = new(9, 9)
    cap_button(t, 0, 0, "close", pressed=True)
    a[42:51, 148:157] = t

    # letters: bold caps on the caption colour, each in its own cell, 1px separators
    for lit, y in ((True, 88), (False, 96)):
        rect(a, 0, y, 194, 7, SEP)
        bg = T.cap_a[0] if lit else T.cap_i[0]
        x = 1
        for c in GEN_LETTERS:
            w = glyph_w(BOLD, c) + 1
            rect(a, x, y, w, 7, bg)
            draw_text(a, BOLD, c, x, y, cap_text_col(lit))
            x += w + 1
        assert x <= 194, x
    return a


# ------------------------------------------------------------------------------------------
# genex.bmp: Media Library colours along the top row, every other pixel from x 48
# ------------------------------------------------------------------------------------------


def genex_colours():
    return [
        WHITE,          # item background
        BLACK,          # item text
        T.face,         # window background
        BLACK,          # button text
        BLACK,          # window text
        T.shadow,       # dividers, sunken borders
        T.select,       # selection bar
        T.face,         # list header background
        BLACK,          # list header text
        T.hilight,      # header frame, light
        T.shadow,       # header frame, dark
        T.shadow,       # header frame, pressed
        T.face,         # header dead area
        T.face,         # scrollbar
        T.hilight,      # scrollbar 2
        T.shadow,       # scrollbar pressed
        T.face,         # scrollbar pressed 2
        T.track,        # scrollbar dead area
    ]


def make_genex():
    a = new(256, 64)
    for i, c in enumerate(genex_colours()):
        px(a, 48 + 2 * i, 0, c)
    button(a, 0, 1, 47, 15, "up")
    button(a, 0, 16, 47, 15, "down")
    return a


# ------------------------------------------------------------------------------------------
# Text files
# ------------------------------------------------------------------------------------------


def viscolor():
    spec = ([(255, 0, 0), (255, 32, 0), (255, 64, 0)] + [(255, 200, 0), (255, 224, 0), (240, 240, 0), (224, 232, 0)]
            + [lerp((96, 255, 0), (0, 176, 0), i / 8) for i in range(9)])
    return ([((0, 0, 0), "background"), ((0, 40, 0), "dots")]
            + [(c, f"spectrum {i + 1}" + (" (top)" if i == 0 else "")) for i, c in enumerate(spec)]
            + [((255, 255, 255), "oscilloscope 1"), ((160, 255, 160), "oscilloscope 2"),
               ((0, 255, 0), "oscilloscope 3"), ((0, 200, 0), "oscilloscope 4"), ((0, 140, 0), "oscilloscope 5"),
               ((224, 224, 224), "peaks")])


PLEDIT_FONT = "Arial"


def pledit_colours():
    return dict(normal="#000000", current=T.pl_current, normal_bg="#FFFFFF", selected_bg=T.pl_selected)


def write_text_files():
    with open(os.path.join(OUT, "viscolor.txt"), "w", newline="\r\n") as f:
        for (r, g, b), note in viscolor():
            f.write(f"{r},{g},{b}, // {note}\n")
    p = pledit_colours()
    with open(os.path.join(OUT, "pledit.txt"), "w", newline="\r\n") as f:
        f.write(f"[Text]\nNormal={p['normal']}\nCurrent={p['current']}\nNormalBG={p['normal_bg']}\n"
                f"SelectedBG={p['selected_bg']}\nMbBG=#FFFFFF\nMbFG=#000000\nFont={PLEDIT_FONT}\n")
    with open(os.path.join(OUT, "readme.txt"), "w", newline="\r\n") as f:
        f.write(
            "YTMinamp Classic - a skin in the grey 3D desktop look of the late 1990s.\n\n"
            "A classic (Winamp 2.x format) skin, drawn by a script (gen_skin.py): face-grey\n"
            "bevels, navy-to-blue title bars, sunken white fields, push buttons and trackbars, a\n"
            "CD-player style readout and hand-made pixel fonts. The emblem is YTMinamp's own icon.\n\n"
            "License: CC0 1.0 Universal (public domain dedication).\n"
        )


# ------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------

SHEETS = {}


def build():
    sheets = {
        "main.bmp": make_main(),
        "titlebar.bmp": make_titlebar(),
        "cbuttons.bmp": make_cbuttons(),
        "shufrep.bmp": make_shufrep(),
        "posbar.bmp": make_posbar(),
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
    SHEETS.clear()
    for name, arr in sheets.items():
        SHEETS[name[:-4]] = save(arr, name)
    write_text_files()
    names = list(sheets) + ["pledit.txt", "viscolor.txt", "readme.txt"]
    wsz = os.path.join(HERE, "YTMinamp-Classic.wsz")
    with zipfile.ZipFile(wsz, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            info = zipfile.ZipInfo(n, date_time=(2026, 10, 26, 0, 0, 0))
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
    for ch in s:
        row, col = FONT_LOOKUP.get(ch.lower(), FONT_LOOKUP[" "])
        blit(dst, SHEETS["text"], (col * 5, row * 6, 5, 6), x, y)
        x += 5


def ui_font():
    for name in ("/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, 11)
        except OSError:
            pass
    return ImageFont.load_default()


def hexcol(s):
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))


def preview_main(lit, state):
    S = SHEETS
    img = Image.new("RGB", (275, 116))
    img.paste(S["main"], (0, 0))
    blit(img, S["titlebar"], (27, 0 if lit else 15, 275, 14), 0, 0)
    for k, x, w in (("previous", 0, 23), ("play", 23, 23), ("pause", 46, 23), ("stop", 69, 23), ("next", 92, 22)):
        pos = {"previous": 16, "play": 39, "pause": 62, "stop": 85, "next": 108}[k]
        blit(img, S["cbuttons"], (x, 18 if state["pressed"] == k else 0, w, 18), pos, 88)
    blit(img, S["cbuttons"], (114, 16 if state["pressed"] == "eject" else 0, 22, 16), 136, 89)
    for name, x0, on in (("eq", 0, state["eq"]), ("pl", 23, state["pl"])):
        sx = x0 + (46 if state["pressed"] == name else 0)
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
    # title: text.bmp's space across the box, then the title in pledit.txt's font and colour
    for x in range(0, 154, 5):
        blit(img, S["text"], (150, 0, min(5, 154 - x), 6), 111 + x, 24)
    title = Image.new("RGB", (154, 14))
    title.paste(img.crop((111, 22, 265, 36)), (0, 0))
    d = ImageDraw.Draw(title)
    d.text((0, 7), state["title"], fill=hexcol(pledit_colours()["normal"]), font=ui_font(), anchor="lm")
    img.paste(title, (111, 22))
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
            vp[x, y] = cols[y]
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
    p = pledit_colours()
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
    d.rectangle((lx, 20, lx + lw - 1, h - 39), fill=hexcol(p["normal_bg"]))
    font = ui_font()
    for i, (txt, dur) in enumerate(rows):
        y = 23 + i * 15
        if y + 15 > h - 38:
            break
        if i == 2:
            d.rectangle((lx, y, lx + lw - 1, y + 14), fill=hexcol(p["selected_bg"]))
        col = hexcol(p["current"] if i == 1 else p["normal"])
        d.text((lx + 2, y + 7), f"{i + 1}. {txt}", fill=col, font=font, anchor="lm")
        d.text((lx + lw - 3, y + 7), dur, fill=col, font=font, anchor="rm")
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
    # a stand-in picture: a teal desktop-like gradient
    pic = Image.linear_gradient("L").resize((w - 22, h - 34)).convert("RGB")
    arr = np.array(pic).astype(np.float32) / 255
    col = np.stack([0 + 30 * arr[..., 0], 128 - 40 * arr[..., 0], 128 - 20 * arr[..., 0]], -1)
    img.paste(Image.fromarray(col.astype(np.uint8)), (11, 20))
    return img


def preview():
    rows = [("Clouds - Blue Sky Again", "4:12"), ("Dial Tone - Modem Song", "3:47"),
            ("Blue Blocks - Defragment", "5:03"), ("Bouncing Cards", "2:58"),
            ("Floppy Disk - Insert Disk 2", "6:21"), ("Pinball - Space Flight", "3:33"),
            ("Screensaver - Starfield", "4:40"), ("Tape Deck - Take 1", "3:09"),
            ("MIDI Trio - Canyon", "5:51"), ("Briefcase - Sync", "4:05"), ("Chime - Fanfare", "0:03")]
    bars = [12, 15, 14, 11, 13, 10, 9, 11, 8, 7, 9, 6, 5, 6, 4, 3, 4, 2, 3]
    A = dict(pressed=None, eq=True, pl=True, clutter="AV", shuffle=True, repeat=False, playing=True, stereo=True,
             pos=0.38, seek=False, volume=72, vdrag=False, balance=0, time=207, remaining=False,
             title="YTMinamp Classic - 3D Look", bars=bars)
    B = dict(pressed="play", eq=False, pl=True, clutter="", shuffle=False, repeat=True, playing=False, stereo=False,
             pos=0.8, seek=True, volume=25, vdrag=True, balance=-60, time=95, remaining=True,
             title="Paused: Quiet Hours (Live)", bars=[3, 2, 4, 1, 2, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    EA = dict(pressed=None, on=True, auto=False, preamp=50, drag=None, bands=[75, 68, 56, 49, 49, 33, 30, 30, 49, 49])
    EB = dict(pressed="close", on=False, auto=True, preamp=70, drag=3, bands=[51, 51, 59, 65, 65, 100, 59, 51, 0, 51])
    cols = []
    for lit, st, est in ((True, A, EA), (False, B, EB)):
        col = Image.new("RGB", (275, 116 + 116 + 232 + 140))
        col.paste(preview_main(lit, st), (0, 0))
        col.paste(preview_eq(lit, est), (0, 116))
        col.paste(preview_playlist(lit, 275, 232, rows, pressed_close=not lit, drag=not lit), (0, 232))
        col.paste(preview_gen(lit, 275, 140, "album art", pressed_close=not lit), (0, 464))
        cols.append(col)
    gap = 12
    out = Image.new("RGB", (275 * 2 + gap * 3, cols[0].height + gap * 2), (0, 128, 128))
    out.paste(cols[0], (gap, gap))
    out.paste(cols[1], (275 + 2 * gap, gap))
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    out.save(os.path.join(HERE, f"preview-{T.name}.png"))
    return cols[0]


if __name__ == "__main__":
    if "--list" in sys.argv[1:]:
        print("\n".join(THEMES))
        sys.exit(0)
    names = sys.argv[1:] or list(THEMES)
    for name in names:
        if name not in THEMES:
            sys.exit(f"unknown theme {name!r}; one of {', '.join(THEMES)}")
        set_theme(name)
        build()
        preview()
        print(f"{name}: YTMinamp-Classic.wsz, preview-{name}.png")
