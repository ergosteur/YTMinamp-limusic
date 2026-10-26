#!/usr/bin/python3
"""Frutiger Aero: a classic Winamp 2.x skin in the Frutiger Aero aesthetic, drawn procedurally.

Sky-to-aqua body with soft bokeh bubbles, light rays and a grassy horizon; glassy panels with
white top gloss; glossy aqua orbs for the transport (a big round play orb); glass-tube sliders
with aqua/green liquid and bubble thumbs; dark aqua glass displays with white/cyan text;
toggles that light up green; a light, airy playlist.

Everything is drawn here from code (gradients, anti-aliased masks, noise-free seeded bokeh,
hand-made pixel fonts, and Open Sans for the window titles). Writes the bitmaps and text files
into out/, zips them flat into YTMinamp-Frutiger-Aero.wsz, and draws preview.png (the windows assembled
from the sprites at their real positions, 2x). Started from skins/ember/gen_skin.py's layouts.
"""

import os
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skins/genex_wacup.py, which finishes each .wsz
import genex_wacup  # noqa: E402
OUT = os.path.join(HERE, "out")
SCRATCH = os.path.join(OUT, "scratch")
os.makedirs(SCRATCH, exist_ok=True)
SKIN = "YTMinamp-Frutiger-Aero"

# ------------------------------------------------------------------------------------------
# Palette
# ------------------------------------------------------------------------------------------

WHITE = (255, 255, 255)
NAVY = (10, 52, 88)
INK = (20, 64, 104)            # dark labels on light glass
INK_DIM = (96, 128, 150)
SKY_STOPS = [(0.0, (176, 228, 252)), (0.35, (122, 204, 244)), (0.72, (64, 172, 222)), (1.0, (40, 150, 206))]
DISP = (6, 40, 56)             # the dark aqua glass of the displays
DISP_GHOST = (10, 50, 67)      # unlit segments
CYAN = (150, 236, 255)
TXT = (210, 248, 255)          # display text
TXT_DIM = (70, 150, 176)
GREEN = (96, 200, 52)
GREEN_HI = (200, 255, 140)
SEP = (255, 0, 255)            # gen.bmp letter separators (never shown)

ORB_AQUA = dict(rim=(14, 78, 128), deep=(18, 104, 172), mid=(40, 172, 222), glow=(160, 246, 255))
ORB_PLAY = dict(rim=(8, 84, 116), deep=(10, 120, 164), mid=(34, 196, 226), glow=(186, 255, 246))
ORB_DOWN = dict(rim=(6, 52, 80), deep=(4, 52, 88), mid=(12, 112, 140), glow=(120, 250, 150))
BUBBLE = dict(rim=(40, 120, 168), deep=(126, 196, 232), mid=(208, 242, 255), glow=(255, 255, 255))
BUBBLE_DOWN = dict(rim=(36, 120, 60), deep=(108, 200, 120), mid=(196, 248, 196), glow=(240, 255, 230))
ORB_RED = dict(rim=(130, 30, 20), deep=(186, 50, 34), mid=(236, 104, 70), glow=(255, 200, 160))
ORB_RED_DOWN = dict(rim=(110, 20, 12), deep=(140, 30, 20), mid=(200, 70, 50), glow=(255, 170, 120))
ORB_GREY = dict(rim=(110, 130, 146), deep=(150, 172, 188), mid=(196, 214, 226), glow=(240, 248, 252))


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(stops, t):
    """Colour along a list of evenly spaced stops, t in 0..1."""
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(n - 1, int(t * n))
    return lerp(stops[i], stops[i + 1], t * n - i)


def stops_at(stops, t):
    """Colour along (position, colour) stops; equal positions make a hard break (a gloss line)."""
    if t <= stops[0][0]:
        return stops[0][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t0 <= t <= t1 and t1 > t0:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1]


def vgrad(h, stops, w=1):
    """(h, w, 3) float array: a vertical gradient through (position, colour) stops."""
    g = np.array([stops_at(stops, (r + 0.5) / h) for r in range(h)], dtype=np.float32)
    return np.repeat(g[:, None, :], w, axis=1)


def rows_at(H, y, h, stops):
    """(H, 1, 3): the gradient laid over rows y..y+h of a canvas H tall (clamped outside)."""
    return np.array([stops_at(stops, max(0.0, min(1.0, (r + 0.5 - y) / max(1e-6, h)))) for r in range(H)],
                    dtype=np.float32)[:, None, :]


# ------------------------------------------------------------------------------------------
# Canvas helpers (numpy, H x W x 3) and anti-aliased masks
# ------------------------------------------------------------------------------------------


def new(w, h, col=(0, 0, 0)):
    a = np.zeros((h, w, 3), dtype=np.float32)
    a[:, :] = col
    return a


def rect(a, x, y, w, h, col):
    if w > 0 and h > 0:
        a[y:y + h, x:x + w] = col


def px(a, x, y, col):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = col


SS = 4


def mask(w, h, fn):
    """Coverage (h, w) in 0..1 of whatever fn(draw, S) draws at S-times scale."""
    im = Image.new("L", (w * SS, h * SS), 0)
    fn(ImageDraw.Draw(im), SS)
    return np.asarray(im.resize((w, h), Image.BOX), dtype=np.float32) / 255.0


def rr_mask(w, h, r, x=0.0, y=0.0, mw=None, mh=None):
    mw = w - x if mw is None else mw
    mh = h - y if mh is None else mh
    r = max(0.0, min(r, mw / 2, mh / 2))

    def fn(d, S):
        d.rounded_rectangle((x * S, y * S, (x + mw) * S - 1, (y + mh) * S - 1), radius=r * S, fill=255)
    return mask(w, h, fn)


def ellipse_mask(w, h, x, y, ew, eh):
    return mask(w, h, lambda d, S: d.ellipse((x * S, y * S, (x + ew) * S - 1, (y + eh) * S - 1), fill=255))


def poly_mask(w, h, pts):
    return mask(w, h, lambda d, S: d.polygon([(px_ * S, py_ * S) for px_, py_ in pts], fill=255))


def paint(a, x, y, m, col, alpha=1.0):
    """Blends a colour (tuple, or an array broadcastable to the mask) over a through mask m."""
    h, w = m.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(a.shape[1], x + w), min(a.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    mm = np.clip(m[y0 - y:y1 - y, x0 - x:x1 - x] * alpha, 0, 1)[..., None]
    c = np.asarray(col, dtype=np.float32)
    if c.ndim == 3:
        c = np.broadcast_to(c, (h, w, 3))[y0 - y:y1 - y, x0 - x:x1 - x]
    reg = a[y0:y1, x0:x1]
    a[y0:y1, x0:x1] = reg * (1 - mm) + c * mm


def blur(m, r):
    im = Image.fromarray(np.clip(m * 255, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, dtype=np.float32) / 255.0


def gauss(W, H, cx, cy, sx, sy=None):
    sy = sx if sy is None else sy
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
    return np.exp(-(((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2) / 2)


def row_alpha(H, W, y0, y1, a0, a1):
    """(H, W) alpha that runs a0..a1 down rows y0..y1 (clamped)."""
    t = np.clip((np.arange(H, dtype=np.float32) + 0.5 - y0) / max(1e-6, y1 - y0), 0, 1)
    return np.repeat((a0 + (a1 - a0) * t)[:, None], W, axis=1)


def save(a, name):
    img = Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, name))
    return img


# ------------------------------------------------------------------------------------------
# Fonts: pixel fonts for the small labels and the bitmap text; Open Sans for window titles
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

# 3x5 font for small labels (rounded where 3 columns allow).
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


def glyph_w(font, c):
    return len(font[c][0])


def text_w(font, s, gap=1):
    s = [c for c in s if c in font]
    return sum(glyph_w(font, c) for c in s) + gap * max(0, len(s) - 1)


def draw_text(a, font, s, x, y, col, gap=1, shadow=None, sh_alpha=1.0):
    for c in s:
        if c not in font:
            continue
        g = font[c]
        if shadow is not None:
            for r, row in enumerate(g):
                for k, ch in enumerate(row):
                    if ch == "#" and 0 <= y + r + 1 < a.shape[0] and 0 <= x + k < a.shape[1]:
                        a[y + r + 1, x + k] = a[y + r + 1, x + k] * (1 - sh_alpha) + np.asarray(shadow) * sh_alpha
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    px(a, x + k, y + r, col(r) if callable(col) else col)
        x += len(g[0]) + gap
    return x


def text_center(a, font, s, cx, y, col, gap=1, shadow=None, sh_alpha=1.0):
    draw_text(a, font, s, cx - text_w(font, s, gap) // 2, y, col, gap, shadow, sh_alpha)


_FONTS = {}


def ttf(size, weight="Semibold"):
    key = (size, weight)
    if key not in _FONTS:
        for path in (f"/usr/share/fonts/open-sans/OpenSans-{weight}.ttf",
                     "/usr/share/fonts/google-noto/NotoSans-SemiBold.ttf", "DejaVuSans.ttf"):
            try:
                _FONTS[key] = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
        else:
            _FONTS[key] = ImageFont.load_default()
    return _FONTS[key]


def ttf_mask(W, H, s, font, cx, baseline):
    """Coverage of s centred on cx with its baseline at row `baseline`."""
    im = Image.new("L", (W, H), 0)
    ImageDraw.Draw(im).text((cx, baseline), s, font=font, fill=255, anchor="ms")
    return np.asarray(im, dtype=np.float32) / 255.0


def title_text(a, s, cx, baseline, lit, size=10):
    """A window title: white with a soft blue glow when lit; slate grey when not."""
    H, W = a.shape[:2]
    m = ttf_mask(W, H, s, ttf(size), cx, baseline)
    if lit:
        paint(a, 0, 0, np.clip(blur(m, 1.2) * 2.2, 0, 1), (20, 90, 150), 0.55)
        paint(a, 0, 1, m, (12, 60, 104), 0.55)
        paint(a, 0, 0, m, WHITE)
    else:
        paint(a, 0, 0, np.clip(blur(m, 1.2) * 2.0, 0, 1), WHITE, 0.45)
        paint(a, 0, 0, m, (98, 120, 138))


# ------------------------------------------------------------------------------------------
# Shared pieces: the sky, glass, orbs, tubes, pills
# ------------------------------------------------------------------------------------------


def sky(w, h, seed, keep=(), hill=None, sun=None, nbokeh=18, stops=SKY_STOPS, ray_floor=None):
    """The body: a sky-to-aqua gradient, light rays and a glow from `sun`, soft bokeh bubbles
    (kept out of the `keep` rectangles, which stay a pure vertical gradient), and a grassy hill."""
    a = vgrad(h, stops, w)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    floor = np.ones((h, w), np.float32)
    if ray_floor is not None:
        floor = np.clip((ray_floor - yy) / 10.0, 0, 1)
    if sun is not None:
        sx, sy = sun
        ang = np.arctan2(yy - sy, xx - sx)
        dist = np.hypot(xx - sx, yy - sy)
        rays = (0.5 + 0.5 * np.sin(ang * 11.0)) ** 6 + 0.6 * (0.5 + 0.5 * np.sin(ang * 7.0 + 1.3)) ** 8
        rays *= np.exp(-dist / 150.0) * 0.22
        paint(a, 0, 0, rays * floor, WHITE)
        paint(a, 0, 0, gauss(w, h, sx, sy, 34) * floor, (240, 252, 255), 0.75)
        paint(a, 0, 0, gauss(w, h, sx, sy, 9) * floor, WHITE, 0.6)
    rng = np.random.default_rng(seed)
    placed = 0
    tries = 0
    while placed < nbokeh and tries < 500:
        tries += 1
        r = float(rng.uniform(2.5, 11.0))
        cx = float(rng.uniform(-4, w + 4))
        cy = float(rng.uniform(10, h - 4))
        tint = [WHITE, (220, 250, 255), (230, 255, 220)][int(rng.integers(0, 3))]
        al = float(rng.uniform(0.14, 0.30))
        if any(cx + r + 2 > x0 and cx - r - 2 < x1 and cy + r + 2 > y0 and cy - r - 2 < y1 for x0, y0, x1, y1 in keep):
            continue
        disc = ellipse_mask(w, h, cx - r, cy - r, 2 * r, 2 * r)
        inner = ellipse_mask(w, h, cx - r + 1, cy - r + 1, 2 * r - 2, 2 * r - 2)
        paint(a, 0, 0, disc, tint, al)
        paint(a, 0, 0, np.clip(disc - inner, 0, 1), WHITE, al * 1.4)
        paint(a, 0, 0, ellipse_mask(w, h, cx - r * 0.55, cy - r * 0.8, r * 0.7, r * 0.45), WHITE, al * 1.2)
        placed += 1
    if hill is not None:
        far_y, near_y, amp, phase = hill
        far = mask(w, h, lambda d, S: d.polygon(
            [(x * S, (far_y + amp * 0.8 * np.sin(x / 41.0 + phase + 2.0)) * S) for x in range(-2, w + 3)]
            + [((w + 2) * S, (h + 2) * S), (-2 * S, (h + 2) * S)], fill=255))
        paint(a, 0, 0, far, rows_at(h, far_y - amp, h - far_y + amp, [(0, (150, 214, 150)), (1, (90, 170, 120))]),
              0.75)
        near_fn = lambda x: near_y + amp * np.sin(x / 33.0 + phase) + amp * 0.4 * np.sin(x / 13.0 + phase * 2)
        near = mask(w, h, lambda d, S: d.polygon(
            [(x * S, near_fn(x) * S) for x in range(-2, w + 3)] + [((w + 2) * S, (h + 2) * S), (-2 * S, (h + 2) * S)],
            fill=255))
        paint(a, 0, 0, near, rows_at(h, near_y - amp, h - near_y + amp + 2,
                                     [(0, (176, 236, 96)), (0.35, (106, 196, 58)), (1, (44, 140, 44))]))
        crest = np.clip(near - np.roll(near, 2, axis=0), 0, 1)
        paint(a, 0, 0, crest, (236, 255, 200), 0.75)
    return a


def glass_panel(a, x, y, w, h, r=5, body=0.26, gloss=0.42):
    """Frosted glass laid over whatever is under it: a white veil, a strong gloss on its upper
    half, a white rim brighter at the top and a faint dark outline."""
    H, W = a.shape[:2]
    outer = rr_mask(W, H, r + 1, x - 1, y - 1, w + 2, h + 2)
    shape = rr_mask(W, H, r, x, y, w, h)
    inner = rr_mask(W, H, r - 1, x + 1, y + 1, w - 2, h - 2)
    paint(a, 0, 0, np.clip(outer - shape, 0, 1), NAVY, 0.28)
    paint(a, 0, 0, shape, WHITE, body)
    gl = rr_mask(W, H, r - 1, x + 1, y + 1, w - 2, h * 0.46)
    paint(a, 0, 0, gl * row_alpha(H, W, y, y + h * 0.46, gloss, gloss * 0.35), WHITE)
    rim = np.clip(shape - inner, 0, 1) * row_alpha(H, W, y, y + h, 0.95, 0.35)
    paint(a, 0, 0, rim, WHITE)


def orb(a, cx, cy, r, pal, hl=0.85, shadow=0.32):
    """A glossy sphere: soft drop shadow, dark rim, deep top fading to a bright refracted glow
    at the bottom, and a white highlight across the upper half."""
    H, W = a.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
    if shadow:
        paint(a, 0, 0, blur(ellipse_mask(W, H, cx - r, cy - r + 1.2, 2 * r, 2 * r), 0.8), NAVY, shadow)
    paint(a, 0, 0, ellipse_mask(W, H, cx - r, cy - r, 2 * r, 2 * r), pal["rim"])
    t = np.clip((yy - (cy - r)) / (2 * r), 0, 1)
    deep = np.asarray(pal["deep"], np.float32)
    mid = np.asarray(pal["mid"], np.float32)
    body = deep + (mid - deep) * np.clip(t * 1.25, 0, 1)[..., None]
    g = gauss(W, H, cx, cy + 0.55 * r, 0.55 * r, 0.42 * r)[..., None]
    body = body * (1 - 0.85 * g) + np.asarray(pal["glow"], np.float32) * 0.85 * g
    d = (np.hypot(xx - cx, yy - cy) / max(1, r - 1))[..., None]
    body = body * (1 - 0.35 * np.clip(d, 0, 1) ** 4) + deep * 0.35 * np.clip(d, 0, 1) ** 4
    paint(a, 0, 0, ellipse_mask(W, H, cx - r + 1, cy - r + 1, 2 * r - 2, 2 * r - 2), body)
    hm = ellipse_mask(W, H, cx - 0.74 * r, cy - 0.93 * r, 1.48 * r, 0.92 * r)
    paint(a, 0, 0, hm * row_alpha(H, W, cy - 0.93 * r, cy, hl, 0.06), WHITE)


ICON_KINDS = ("previous", "play", "pause", "stop", "next", "eject")


def icon_mask(kind, W, H, cx, cy, s=1.0):
    if kind == "play":
        return poly_mask(W, H, [(cx - 3.2 * s, cy - 5 * s), (cx - 3.2 * s, cy + 5 * s), (cx + 5.2 * s, cy)])
    if kind == "pause":
        return mask(W, H, lambda d, S: (
            d.rounded_rectangle(((cx - 4 * s) * S, (cy - 4 * s) * S, (cx - 1.2 * s) * S - 1, (cy + 4 * s) * S - 1),
                                radius=0.6 * s * S, fill=255),
            d.rounded_rectangle(((cx + 1.2 * s) * S, (cy - 4 * s) * S, (cx + 4 * s) * S - 1, (cy + 4 * s) * S - 1),
                                radius=0.6 * s * S, fill=255)))
    if kind == "stop":
        return mask(W, H, lambda d, S: d.rounded_rectangle(
            ((cx - 3.6 * s) * S, (cy - 3.6 * s) * S, (cx + 3.6 * s) * S - 1, (cy + 3.6 * s) * S - 1),
            radius=0.9 * s * S, fill=255))
    if kind in ("previous", "next"):
        def fn(d, S):
            sg = 1 if kind == "next" else -1
            hh = 3.6 * s
            for bx in (cx - sg * 4.2 * s, cx - sg * 0.6 * s):
                tip = bx + sg * 3.8 * s
                d.polygon([(bx * S, (cy - hh) * S), (bx * S, (cy + hh) * S), (tip * S, cy * S)], fill=255)
            bar = cx + sg * 3.2 * s
            x0, x1 = (bar, bar + 1.6 * s) if sg == 1 else (bar - 1.6 * s, bar)
            d.rectangle((x0 * S, (cy - hh) * S, x1 * S - 1, (cy + hh) * S - 1), fill=255)
        return mask(W, H, fn)
    if kind == "eject":
        return mask(W, H, lambda d, S: (
            d.polygon([((cx - 4.2 * s) * S, (cy + 0.6 * s) * S), ((cx + 4.2 * s) * S, (cy + 0.6 * s) * S),
                       (cx * S, (cy - 4 * s) * S)], fill=255),
            d.rectangle(((cx - 4.2 * s) * S, (cy + 2 * s) * S, (cx + 4.2 * s) * S - 1, (cy + 3.6 * s) * S - 1),
                        fill=255)))
    raise ValueError(kind)


def glyph(a, kind, cx, cy, s, pressed):
    H, W = a.shape[:2]
    m = icon_mask(kind, W, H, cx, cy, s)
    if pressed:
        paint(a, 0, 0, np.clip(blur(m, 1.4) * 2.0, 0, 1), (220, 255, 210), 0.8)
    paint(a, 0, 0, np.roll(m, 1, axis=0), NAVY, 0.5)
    paint(a, 0, 0, m, WHITE)


def tube(a, x, y, w, h, spans=(), liquid=None, vertical=False):
    """A glass tube: dark rim, clear pale interior, liquid over the spans (start, end) and a white
    gloss along its top (left for a vertical tube). liquid(n) -> (n, 3) colours along its length."""
    if vertical:
        t = a.transpose(1, 0, 2)
        tube(t, y, x, h, w, spans, liquid, False)
        return
    H, W = a.shape[:2]
    outer = rr_mask(W, H, h / 2, x, y, w, h)
    inner = rr_mask(W, H, h / 2 - 1, x + 1, y + 1, w - 2, h - 2)
    paint(a, 0, 0, outer, (30, 96, 140), 0.9)
    clear = rows_at(H, y + 1, h - 2, [(0, (140, 186, 210)), (0.45, (206, 236, 248)), (1, (246, 253, 255))])
    paint(a, 0, 0, inner, clear)
    for s0, s1 in spans:
        cm = np.zeros((H, W), np.float32)
        lo, hi = max(0, int(np.floor(s0))), min(W, int(np.ceil(s1)))
        if hi <= lo:
            continue
        cm[:, lo:hi] = 1
        hue = np.zeros((W, 3), np.float32)
        hue[:] = liquid(W)
        shade = rows_at(H, y + 1, h - 2, [(0, (150, 150, 150)), (0.5, (255, 255, 255)), (1, (200, 200, 200))]) / 255
        col = hue[None, :, :] * shade
        col += rows_at(H, y + 1, h - 2, [(0, (0, 0, 0)), (0.6, (0, 0, 0)), (1, (60, 70, 50))])
        paint(a, 0, 0, inner * cm, np.clip(col, 0, 255))
    gl = rr_mask(W, H, 1.0, x + h / 2 - 1, y + 1.3, w - h + 2, max(1.0, (h - 2) * 0.32))
    paint(a, 0, 0, gl, WHITE, 0.75)


def liquid_h(x0, x1):
    """Green at x0 to aqua at x1 (absolute columns), for a tube's fill."""
    def fn(W):
        return np.array([ramp([(110, 214, 60), (60, 206, 150), (40, 190, 230)], (c - x0) / max(1, x1 - x0))
                         for c in range(W)], np.float32)
    return fn


def pill(a, x, y, w, h, style, pressed=False, r=None):
    """A rounded glossy button: 'glass' (off, frosted white) or 'green' (lit)."""
    H, W = a.shape[:2]
    r = h / 2 if r is None else r
    if style == "green":
        edge = (34, 110, 30)
        top, bot = ((170, 240, 110), (44, 140, 24)) if not pressed else ((110, 196, 70), (30, 112, 18))
        glow = (150, 240, 100)
    else:
        edge = (66, 130, 170)
        top, bot = ((255, 255, 255), (196, 228, 244)) if not pressed else ((200, 226, 240), (160, 204, 228))
        glow = (236, 252, 255)
    paint(a, 0, 0, rr_mask(W, H, r, x, y, w, h), edge)
    inner = rr_mask(W, H, r - 1, x + 1, y + 1, w - 2, h - 2)
    paint(a, 0, 0, inner, rows_at(H, y + 1, h - 2, [(0, top), (0.5, lerp(top, bot, 0.45)),
                                                    (0.5, lerp(top, bot, 0.8)), (1, bot)]))
    paint(a, 0, 0, inner * gauss(W, H, x + w / 2, y + h, w * 0.4, h * 0.35), glow, 0.7)
    if not pressed:
        paint(a, 0, 0, rr_mask(W, H, r - 1, x + 1.5, y + 1, w - 3, (h - 2) * 0.45), WHITE, 0.55)


def pill_label(a, x, y, w, h, label, style, pressed):
    o = 1 if pressed else 0
    tx = x + (w - text_w(TINY, label)) // 2
    ty = y + (h - 5) // 2 + o
    if style == "green":
        draw_text(a, TINY, label, tx, ty, WHITE, shadow=(20, 96, 20), sh_alpha=0.8)
    else:
        draw_text(a, TINY, label, tx, ty, INK, shadow=WHITE, sh_alpha=0.6)


def mini_button(a, x, y, kind, lit=True, pressed=False):
    """9x9 titlebar button: a small glossy orb (red for close)."""
    if kind == "close":
        pal = ORB_RED_DOWN if pressed else ORB_RED
    else:
        pal = ORB_DOWN if pressed else ORB_AQUA
    if not lit and not pressed:
        pal = ORB_GREY
    cell = a[y:y + 9, x:x + 9]
    orb(cell, 4.5, 4.5, 4.5, pal, hl=0.8 if not pressed else 0.45, shadow=0)
    ink = WHITE
    if kind == "close":
        m = mask(9, 9, lambda d, S: (d.line((2.7 * S, 2.7 * S, 6.3 * S, 6.3 * S), fill=255, width=int(1.3 * S)),
                                     d.line((6.3 * S, 2.7 * S, 2.7 * S, 6.3 * S), fill=255, width=int(1.3 * S))))
    elif kind == "minimize":
        m = rr_mask(9, 9, 0.5, 2.5, 5, 4, 1.5)
    elif kind == "shade":
        m = rr_mask(9, 9, 0.5, 2.5, 2.8, 4, 1.5) + 0.5 * rr_mask(9, 9, 0.5, 2.5, 5.2, 4, 1.2)
    else:  # options: a small diamond
        m = poly_mask(9, 9, [(4.5, 2.4), (6.6, 4.5), (4.5, 6.6), (2.4, 4.5)])
    paint(cell, 0, 0, np.roll(m, 1, axis=0), NAVY, 0.35)
    paint(cell, 0, 0, m, ink)


# ------------------------------------------------------------------------------------------
# Glass bars (titlebars)
# ------------------------------------------------------------------------------------------

BAR_LIT = [(0, (236, 250, 255)), (0.1, (210, 240, 253)), (0.48, (150, 214, 246)), (0.48, (92, 184, 234)),
           (1, (60, 160, 218))]
BAR_DIM = [(0, (246, 250, 252)), (0.1, (228, 236, 242)), (0.48, (208, 220, 230)), (0.48, (186, 202, 214)),
           (1, (172, 190, 204))]


def glass_bar(w, h, lit):
    a = vgrad(h, BAR_LIT if lit else BAR_DIM, w)
    rect(a, 0, 0, w, 1, (250, 254, 255) if lit else (252, 253, 254))
    rect(a, 0, h - 1, w, 1, (30, 110, 170) if lit else (140, 160, 176))
    return a


def main_titlebar(lit):
    a = glass_bar(275, 14, lit)
    rect(a, 0, 0, 1, 14, (230, 246, 255))
    rect(a, 274, 0, 1, 14, (30, 110, 170) if lit else (140, 160, 176))
    if lit:
        # a little lens flare glint and two bubbles on the glass
        paint(a, 0, 0, gauss(275, 14, 52, 4, 16, 3), WHITE, 0.5)
        paint(a, 0, 0, gauss(275, 14, 222, 9, 20, 3), (200, 250, 255), 0.35)
    title_text(a, "YTMinamp", 137, 11, lit, size=10)
    mini_button(a, 6, 3, "options", lit)
    mini_button(a, 244, 3, "minimize", lit)
    mini_button(a, 254, 3, "shade", lit)
    mini_button(a, 264, 3, "close", lit)
    return a


# ------------------------------------------------------------------------------------------
# main.bmp (275 x 116)
# ------------------------------------------------------------------------------------------

SLIDER_KEEP = (100, 52, 274, 74)
POS_KEEP = (6, 69, 270, 85)


def main_bg():
    """The main window's background before any control is drawn on it."""
    a = sky(275, 116, seed=7, keep=[SLIDER_KEEP, POS_KEEP], hill=(99, 104, 3.0, 0.6), sun=(236, 12),
            nbokeh=30, ray_floor=50)
    # a low sun glinting over the hill at the bottom right, and its lens flare (kept below the
    # seek bar, so the slider rows stay a plain vertical gradient)
    rows = np.clip((np.arange(116, dtype=np.float32) - 84.5) / 4, 0, 1)[:, None]
    yy, xx = np.mgrid[0:116, 0:275].astype(np.float32) + 0.5
    ang = np.arctan2(yy - 99, xx - 246)
    rays = ((0.5 + 0.5 * np.sin(ang * 9.0 + 0.4)) ** 6) * np.exp(-np.hypot(xx - 246, yy - 99) / 40.0) * 0.35
    paint(a, 0, 0, rays * rows, WHITE)
    paint(a, 0, 0, gauss(275, 116, 246, 99, 16, 10) * rows, (246, 255, 236), 0.7)
    for k, (fx, fy, fr, fa) in enumerate(((222, 104, 3.0, 0.35), (204, 108, 1.8, 0.4), (190, 111, 4.0, 0.2))):
        paint(a, 0, 0, ellipse_mask(275, 116, fx - fr, fy - fr, 2 * fr, 2 * fr) * rows,
              [(220, 255, 230), (200, 245, 255), (255, 250, 220)][k], fa)
    glass_panel(a, 5, 16, 266, 55, r=5, body=0.22, gloss=0.36)
    glass_panel(a, 12, 84, 151, 26, r=8, body=0.24, gloss=0.42)
    return a


def display_box(a, x, y, w, h, gloss_rows=4):
    """A dark aqua glass screen: white lip, deep rim, flat glass, a gloss band in its top rows."""
    H, W = a.shape[:2]
    paint(a, 0, 0, rr_mask(W, H, 3, x - 2, y - 2, w + 4, h + 4), WHITE, 0.6)
    paint(a, 0, 0, rr_mask(W, H, 2, x - 1, y - 1, w + 2, h + 2), (8, 56, 86))
    rect(a, x, y, w, h, DISP)
    if gloss_rows:
        for i in range(gloss_rows):
            rect(a, x + 1, y + i, w - 2, 1, lerp(DISP, (120, 210, 236), 0.42 * (1 - i / gloss_rows) ** 1.5))
        rect(a, x + 2, y, w - 4, 1, lerp(DISP, (200, 246, 255), 0.55))


SEG = {
    "a": [(0, c) for c in range(2, 7)],
    "g": [(6, c) for c in range(2, 7)],
    "d": [(12, c) for c in range(2, 7)],
    "f": [(r, c) for r in range(1, 6) for c in (1, 2)],
    "b": [(r, c) for r in range(1, 6) for c in (6, 7)],
    "e": [(r, c) for r in range(7, 12) for c in (1, 2)],
    "c": [(r, c) for r in range(7, 12) for c in (6, 7)],
}
DIGIT_SEGS = {
    0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc",
    5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg",
}


def seg_col(r):
    return lerp(WHITE, CYAN, r / 12)


def seven_seg(a, x, y, lit_segs):
    rect(a, x, y, 9, 13, DISP)
    for s, cells in SEG.items():
        if s not in lit_segs:
            for r, c in cells:
                px(a, x + c, y + r, DISP_GHOST)
    for s, cells in SEG.items():
        if s in lit_segs:
            for r, c in cells:
                px(a, x + c, y + r, seg_col(r))
    # soften the segment corners: the ends of the horizontals are half-lit
    for s in ("a", "g", "d"):
        if s in lit_segs:
            r = SEG[s][0][0]
            for c in (2, 6):
                a[y + r, x + c] = (np.asarray(seg_col(r), np.float32) + np.asarray(DISP, np.float32) * 0.6) / 1.6


def droplet(a, cx, top, h):
    """A glossy water droplet (the About spot): pointed top, round belly."""
    H, W = a.shape[:2]
    r = h * 0.36
    by = top + h - r
    m = np.maximum(ellipse_mask(W, H, cx - r, by - r, 2 * r, 2 * r),
                   poly_mask(W, H, [(cx, top), (cx + r * 0.93, by - r * 0.35), (cx - r * 0.93, by - r * 0.35)]))
    paint(a, 0, 0, blur(np.roll(m, 1, axis=0), 0.8), NAVY, 0.35)
    paint(a, 0, 0, m, (20, 110, 170))
    inner = blur(m, 0.6) * m
    col = rows_at(H, top, h, [(0, (60, 170, 226)), (0.6, (60, 196, 236)), (1, (190, 252, 255))])
    paint(a, 0, 0, np.clip((inner - 0.35) * 1.6, 0, 1), col)
    paint(a, 0, 0, ellipse_mask(W, H, cx - r * 0.62, by - r * 0.55, r * 0.55, r * 0.75), WHITE, 0.85)
    paint(a, 0, 0, gauss(W, H, cx + r * 0.3, by + r * 0.45, 1.2), WHITE, 0.7)


TRANSPORT = [("previous", 16, 23, 8.0), ("play", 39, 23, 11.0), ("pause", 62, 23, 8.0),
             ("stop", 85, 23, 8.0), ("next", 108, 22, 8.0)]
EJECT = (136, 89, 22, 16, 7.0)


def draw_transport(a, pressed=None):
    """The orbs straight onto the main window (pressed: the one kind drawn pressed)."""
    for kind, x, w, r in TRANSPORT:
        cx, cy = x + w / 2, 88 + 9
        down = pressed == kind
        pal = ORB_DOWN if down else (ORB_PLAY if kind == "play" else ORB_AQUA)
        if kind == "play" and down:
            # the big orb spills 2px past its 18px cell: press only its middle, so the rim
            # outside the cell (left as main.bmp has it) still matches
            up = a.copy()
            orb(up, cx, cy, r, ORB_PLAY, hl=0.9)
            orb(a, cx, cy, r, pal, hl=0.6)
            H, W = a.shape[:2]
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
            wgt = np.clip((9.4 - np.hypot(xx - cx, yy - cy)) / 1.6, 0, 1)[..., None]
            a[:] = up * (1 - wgt) + a * wgt
        else:
            orb(a, cx, cy, r, pal, hl=0.9 if not down else 0.6)
        glyph(a, kind, cx + (0.6 if kind == "play" else 0), cy, 1.25 if kind == "play" else 0.92, down)
    x, y, w, h, r = EJECT
    down = pressed == "eject"
    orb(a, x + w / 2, y + h / 2, r, ORB_DOWN if down else ORB_AQUA, hl=0.9 if not down else 0.6)
    glyph(a, "eject", x + w / 2, y + h / 2, 0.82, down)


def volume_strip(bg_seat, level=None):
    """68x13: the volume tube over its seat; level 0..1 (None: empty)."""
    a = bg_seat.copy()
    spans = [] if level is None else [(2, 7 + level * 54)]
    tube(a, 1, 3, 66, 7, spans, liquid_h(2, 66))
    return a


def balance_strip(bg_seat, t=None):
    """38x13 (sheet x 9..47): a short tube filling out from its middle by t 0..1."""
    a = bg_seat.copy()
    spans = [] if not t else [(19 - 12 * t - 0.5, 19 + 12 * t + 0.5)]
    tube(a, 1, 3, 36, 7, spans, lambda W: np.array([ramp([(60, 206, 150), (40, 190, 230)], abs(c - 19) / 18)
                                                     for c in range(W)], np.float32))
    rect(a, 19, 1, 1, 2, (20, 80, 120))
    return a


def make_main():
    a = main_bg()
    base = a.copy()
    # window edge
    rect(a, 0, 0, 1, 116, (236, 250, 255))
    rect(a, 274, 0, 1, 116, (30, 104, 160))
    rect(a, 0, 115, 275, 1, (24, 100, 60))
    a[0:14, :] = main_titlebar(True)

    # left display: indicator, time, analyzer
    display_box(a, 21, 20, 84, 42, gloss_rows=5)
    for x in (48, 60, 78, 90):
        seven_seg(a, x, 26, "")
    for yy in (29, 34):
        rect(a, 73, yy, 2, 2, CYAN)
    # right display: title row, then kbps/kHz/mono/stereo row
    display_box(a, 109, 21, 159, 15, gloss_rows=3)
    display_box(a, 109, 40, 159, 14, gloss_rows=3)
    draw_text(a, TINY, "KBPS", 129, 44, TXT_DIM)
    draw_text(a, TINY, "KHZ", 169, 44, TXT_DIM)

    # sliders (the sheets draw over these)
    a[57:70, 107:175] = volume_strip(base[57:70, 107:175], 0.72)
    a[57:70, 177:215] = balance_strip(base[57:70, 177:215])
    # seek tube
    tube(a, 16, 74, 248, 6)
    draw_transport(a)
    droplet(a, 259.5, 88, 18)
    return a, base


# ------------------------------------------------------------------------------------------
# titlebar.bmp (344 x 87): buttons, bars, clutterbar
# ------------------------------------------------------------------------------------------

CLUTTER_SLOTS = [("O", 3, 8), ("A", 11, 7), ("I", 18, 7), ("D", 25, 8), ("V", 33, 7)]


def clutter_bar(bg, lit_letters):
    """8x43: a slim glass capsule with the letters; lit ones on green."""
    a = bg.copy()
    H, W = a.shape[:2]
    paint(a, 0, 0, rr_mask(W, H, 3.5, 0, 0, 8, 43), (66, 130, 170))
    paint(a, 0, 0, rr_mask(W, H, 2.5, 1, 1, 6, 41), vgrad(43, [(0, (250, 254, 255)), (1, (200, 230, 246))], 8))
    paint(a, 0, 0, rr_mask(W, H, 1, 1.5, 1, 2, 41), WHITE, 0.6)
    for letter, y, h in CLUTTER_SLOTS:
        on = letter in lit_letters
        if on:
            paint(a, 0, 0, rr_mask(W, H, 1.5, 1, y, 6, h), rows_at(H, y, h, [(0, (180, 250, 120)), (1, (70, 176, 36))]))
        gy = y + (h - 5) // 2
        draw_text(a, TINY, letter, 2, gy, WHITE if on else INK)
    return a


def button_cells(bar):
    """The titlebar's 9x9 buttons drawn on the bar they sit on (bar rows 3..11)."""
    out = {}
    for kind, bx in (("options", 6), ("minimize", 244), ("shade", 254), ("close", 264)):
        for pressed in (False, True):
            cell = bar[3:12, bx:bx + 9].copy()
            mini_button(cell, 0, 0, kind, True, pressed)
            out[(kind, pressed)] = cell
    return out


def make_titlebar(main, base):
    a = new(344, 87, (200, 230, 246))
    plain = glass_bar(275, 14, True)
    cells = button_cells(plain)
    for kind, x in (("options", 0), ("minimize", 9), ("close", 18)):
        a[0:9, x:x + 9] = cells[(kind, False)]
        a[9:18, x:x + 9] = cells[(kind, True)]
    a[18:27, 0:9] = cells[("shade", False)]
    a[18:27, 9:18] = cells[("shade", True)]
    a[0:14, 27:302] = main_titlebar(True)
    a[15:29, 27:302] = main_titlebar(False)
    a[29:43, 27:302] = main_titlebar(True)
    a[42:56, 27:302] = main_titlebar(False)
    bg = base[22:65, 10:18]
    unlit = clutter_bar(bg, "")
    lit = clutter_bar(bg, "OAIDV")
    a[0:43, 304:312] = unlit
    a[0:43, 312:320] = unlit
    for (letter, y, h), sx, sy in zip(CLUTTER_SLOTS, [304, 312, 320, 328, 336], [47, 55, 62, 69, 77]):
        a[sy:sy + h, sx:sx + 8] = lit[y:y + h]
    main[22:65, 10:18] = unlit
    return a


# ------------------------------------------------------------------------------------------
# cbuttons.bmp (136 x 36), shufrep.bmp (92 x 85)
# ------------------------------------------------------------------------------------------


def make_cbuttons(main):
    a = new(136, 36)
    sx = {"previous": 0, "play": 23, "pause": 46, "stop": 69, "next": 92}
    for kind, x, w, _r in TRANSPORT:
        a[0:18, sx[kind]:sx[kind] + w] = main[88:106, x:x + w]
    for kind, x, w, _r in TRANSPORT:
        down = MAIN_BASE_NO_ORBS.copy()
        draw_transport(down, pressed=kind)
        a[18:36, sx[kind]:sx[kind] + w] = down[88:106, x:x + w]
    a[0:16, 114:136] = main[89:105, 136:158]
    down = MAIN_BASE_NO_ORBS.copy()
    draw_transport(down, pressed="eject")
    a[16:32, 114:136] = down[89:105, 136:158]
    rect(a, 114, 32, 22, 4, main[105, 147])
    return a


def make_shufrep(base):
    a = new(92, 85, (200, 230, 246))
    for row, (on, pressed) in enumerate([(False, False), (False, True), (True, False), (True, True)]):
        y = row * 15
        style = "green" if on else "glass"
        for x, w, src, label in ((0, 28, 210, "REPEAT"), (28, 47, 164, "SHUFFLE")):
            cell = base[89:104, src:src + w].copy()
            pill(cell, 0, 0, w, 15, style, pressed, r=6)
            pill_label(cell, 0, 0, w, 15, label, style, pressed)
            a[y:y + 15, x:x + w] = cell
    for x, label, pressed in [(0, "EQ", False), (23, "PL", False), (46, "EQ", True), (69, "PL", True)]:
        src = 219 if label == "EQ" else 242
        for on, y in ((False, 61), (True, 73)):
            style = "green" if on else "glass"
            cell = base[58:70, src:src + 23].copy()
            pill(cell, 0.5, 0, 22, 12, style, pressed, r=5)
            pill_label(cell, 0, 0, 23, 12, label, style, pressed)
            a[y:y + 12, x:x + 23] = cell
    return a


# ------------------------------------------------------------------------------------------
# monoster, playpaus, numbers, nums_ex, text
# ------------------------------------------------------------------------------------------


def make_monoster(main):
    a = new(56, 24, DISP)
    for y, on in ((0, True), (12, False)):
        a[y:y + 12, 0:29] = main[41:53, 239:268]
        a[y:y + 12, 29:56] = main[41:53, 212:239]
        col = GREEN_HI if on else DISP_GHOST
        text_center(a, TINY, "STEREO", 14, y + 4, col)
        text_center(a, TINY, "MONO", 29 + 13, y + 4, col)
    return a


def make_playpaus():
    a = new(48, 9, DISP)
    m = poly_mask(9, 9, [(2, 1), (2, 8), (8, 4.5)])
    cell = a[:, 0:9]
    paint(cell, 0, 0, blur(m, 1.0), GREEN, 0.6)
    paint(cell, 0, 0, m, GREEN_HI)
    rect(a, 9 + 2, 1, 2, 7, CYAN)
    rect(a, 9 + 5, 1, 2, 7, CYAN)
    rect(a, 18 + 2, 2, 5, 5, TXT_DIM)
    rect(a, 36, 0, 3, 9, DISP)
    rect(a, 39 + 1, 3, 1, 3, GREEN_HI)
    return a


def make_numbers(ex):
    a = new(108 if ex else 99, 13, DISP)
    for n in range(10):
        seven_seg(a, 9 * n, 0, DIGIT_SEGS[n])
    seven_seg(a, 90, 0, "")
    if ex:
        rect(a, 99, 0, 9, 13, DISP)
        for r, c in SEG["g"]:
            px(a, 99 + c, r, seg_col(6))
    return a


FONT_GRID = [
    list("abcdefghijklmnopqrstuvwxyz\"@") + [None, None, " "],
    list("0123456789") + ["…", ".", ":", "(", ")", "-", "'", "!", "_", "+", "\\", "/", "[", "]", "^", "&", "%",
                          ",", "=", "$", "#"],
    ["å", "ö", "ä", "?", "*"] + [None] * 26,
]


def make_text():
    a = new(155, 18, DISP)
    for row, chars in enumerate(FONT_GRID):
        for col, ch in enumerate(chars):
            if ch is None or ch == " ":
                continue
            key = ch if ch in FONT5 else ch.upper()
            draw_text(a, FONT5, key, col * 5, row * 6, TXT)
    return a


# ------------------------------------------------------------------------------------------
# posbar.bmp (307 x 10), volume.bmp / balance.bmp (68 x 433)
# ------------------------------------------------------------------------------------------


def make_posbar(main):
    a = new(307, 10)
    a[0:10, 0:248] = main[72:82, 16:264]
    for x0 in (248, 278):
        sel = x0 == 278
        cell = main[72:82, 120:149].copy()
        H, W = cell.shape[:2]
        pal = BUBBLE_DOWN if sel else BUBBLE
        paint(cell, 0, 0, rr_mask(W, H, 4.5, 0.5, 0, 28, 10), pal["rim"])
        inner = rr_mask(W, H, 3.5, 1.5, 1, 26, 8)
        col = rows_at(H, 1, 8, [(0, pal["deep"]), (0.55, pal["mid"]), (1, pal["glow"])])
        paint(cell, 0, 0, inner, col)
        paint(cell, 0, 0, inner * gauss(W, H, 14.5, 8.5, 8, 2.5), pal["glow"], 0.8)
        paint(cell, 0, 0, rr_mask(W, H, 2, 3, 1.3, 23, 3.2), WHITE, 0.8)
        # three small bubbles as a grip
        for gx in (10.5, 14.5, 18.5):
            paint(cell, 0, 0, ellipse_mask(W, H, gx - 1.3, 4.5, 2.6, 2.6), (30, 110, 160) if not sel else (30, 120, 50),
                  0.55)
            paint(cell, 0, 0, ellipse_mask(W, H, gx - 0.7, 4.8, 1.2, 1.0), WHITE, 0.9)
        a[0:10, x0:x0 + 29] = cell
    return a


def slider_thumb(bg, pressed):
    """14x11: a glossy bubble on whatever bg is (the tube's cross-section)."""
    cell = bg.copy()
    orb(cell, 7, 5.5, 5.5, BUBBLE_DOWN if pressed else BUBBLE, hl=0.9, shadow=0.25)
    return cell


def thumb_bg_h(seat, filled_left=True):
    """The cross-section of a horizontal tube for a 14x11 thumb cell (thumb rows 1..11 of the
    13-row strip): filled to its middle (left half liquid), empty to the right."""
    strip = seat.copy()
    w = strip.shape[1]
    tube(strip, -20, 3, w + 40, 7, [(-20, 7)] if filled_left else [], liquid_h(-20, 7 + 40))
    return strip[1:12, 0:14]


def make_volume(main, base):
    a = new(68, 433, (200, 230, 246))
    seat = base[57:70, 107:175]
    for i in range(28):
        y = i * 15
        a[y:y + 13, 0:68] = volume_strip(seat, (i + 1) / 28)
        a[y + 13:y + 15, 0:68] = base[70:72, 107:175]
    tb = thumb_bg_h(base[57:70, 140:154])
    a[422:433, 0:14] = slider_thumb(tb, True)
    a[422:433, 15:29] = slider_thumb(tb, False)
    return a


def make_balance(main, base):
    a = new(68, 433, (200, 230, 246))
    seat = base[57:70, 177:215]
    for i in range(28):
        y = i * 15
        a[y:y + 13, 9:47] = balance_strip(seat, i / 27)
        a[y + 13:y + 15, 9:47] = base[70:72, 177:215]
        a[y:y + 15, 0:9] = base[57:72, 168:177]
        a[y:y + 15, 47:68] = base[57:72, 215:236]
    tb = thumb_bg_h(base[57:70, 190:204], filled_left=False)
    a[422:433, 0:14] = slider_thumb(tb, True)
    a[422:433, 15:29] = slider_thumb(tb, False)
    return a


# ------------------------------------------------------------------------------------------
# eqmain.bmp (275 x 315)
# ------------------------------------------------------------------------------------------

EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
BAY = (14, 35, 249, 78)    # x, y, w, h of the sliders' frosted bay
BAY_STOPS = [(0, (250, 254, 255)), (0.06, (232, 246, 252)), (0.25, (214, 238, 250)), (1, (196, 230, 246))]


def eq_titlebar(lit):
    a = glass_bar(275, 14, lit)
    rect(a, 0, 0, 1, 14, (230, 246, 255))
    rect(a, 274, 0, 1, 14, (30, 110, 170) if lit else (140, 160, 176))
    if lit:
        paint(a, 0, 0, gauss(275, 14, 70, 4, 18, 3), WHITE, 0.45)
    title_text(a, "Equalizer", 137, 11, lit, size=10)
    mini_button(a, 264, 3, "close", lit)
    return a


def eq_bg():
    a = sky(275, 116, seed=23, keep=[(BAY[0] - 2, BAY[1] - 2, BAY[0] + BAY[2] + 2, BAY[1] + BAY[3] + 2),
                                     (80, 12, 206, 40)], sun=(30, 16), nbokeh=10)
    x, y, w, h = BAY
    H, W = a.shape[:2]
    paint(a, 0, 0, np.clip(rr_mask(W, H, 6, x - 1, y - 1, w + 2, h + 2) - rr_mask(W, H, 5, x, y, w, h), 0, 1),
          NAVY, 0.3)
    paint(a, 0, 0, rr_mask(W, H, 5, x, y, w, h), rows_at(H, y, h, BAY_STOPS))
    rim = np.clip(rr_mask(W, H, 5, x, y, w, h) - rr_mask(W, H, 4, x + 1, y + 1, w - 2, h - 2), 0, 1)
    paint(a, 0, 0, rim, WHITE, 0.9)
    return a


def eq_frame(bay_col, n):
    """14x63: the vertical glass tube, liquid rising with the value (n of 0..27)."""
    a = bay_col.copy()
    v = n / 27
    top = round((1 - v) * 51) + 5.5
    liq = lambda W: np.array([ramp([(40, 190, 230), (60, 206, 150), (110, 214, 60)], c / max(1, W - 1))
                              for c in range(W)], np.float32)
    tube(a, 4, 1, 6, 61, [(top, 62)], liq, vertical=True)
    # the zero mark either side
    rect(a, 1, 30, 2, 1, (90, 150, 190))
    rect(a, 11, 30, 2, 1, (90, 150, 190))
    return a


def make_eqmain():
    bg = eq_bg()
    a = new(275, 315, (200, 230, 246))
    a[0:116] = bg
    rect(a, 0, 0, 1, 116, (236, 250, 255))
    rect(a, 274, 0, 1, 116, (30, 104, 160))
    rect(a, 0, 115, 275, 1, (30, 104, 160))
    a[0:14, :] = eq_titlebar(True)
    # graph screen
    display_box(a, 86, 17, 113, 19, gloss_rows=0)
    # bay labels
    rect(a, 39, 38, 1, 64, (150, 196, 222))
    rect(a, 40, 38, 1, 64, WHITE)
    for lbl, yy in (("+12DB", 41), ("+0DB", 66), ("-12DB", 92)):
        text_center(a, TINY, lbl, 58, yy, INK)
    bay_col = bg[38:101, 78:92]
    for x in [21] + [78 + 18 * i for i in range(10)]:
        a[38:101, x:x + 14] = eq_frame(bay_col, 14)
    text_center(a, TINY, "PREAMP", 28, 104, INK)
    for i, lbl in enumerate(EQ_BANDS):
        text_center(a, TINY, lbl, 78 + 18 * i + 7, 104, INK)

    # buttons on the window, and their sheet cells (each drawn on the bg it covers)
    for pos, w, lbl in (((14, 18), 26, "ON"), ((40, 18), 32, "AUTO")):
        cell = bg[pos[1]:pos[1] + 12, pos[0]:pos[0] + w].copy()
        pill(cell, 0, 0, w, 12, "glass", False, r=5)
        pill_label(cell, 0, 0, w, 12, lbl, "glass", False)
        a[pos[1]:pos[1] + 12, pos[0]:pos[0] + w] = cell
    for x, label, on, pressed in [
        (10, "ON", False, False), (36, "AUTO", False, False), (69, "ON", True, False), (95, "AUTO", True, False),
        (128, "ON", False, True), (154, "AUTO", False, True), (187, "ON", True, True), (213, "AUTO", True, True),
    ]:
        w = 26 if label == "ON" else 32
        sx = 14 if label == "ON" else 40
        cell = bg[18:30, sx:sx + w].copy()
        style = "green" if on else "glass"
        pill(cell, 0, 0, w, 12, style, pressed, r=5)
        pill_label(cell, 0, 0, w, 12, label, style, pressed)
        a[119:131, x:x + w] = cell
    bar = eq_titlebar(True)
    cell = bar[3:12, 264:273].copy()
    mini_button(cell, 0, 0, "close", True, pressed=True)
    a[125:134, 0:9] = cell
    a[134:148, :] = eq_titlebar(True)
    a[149:163, :] = eq_titlebar(False)
    # thumbs (11x11 at x+1 over a frame): the tube's cross-section, liquid below the middle
    tb = eq_frame(bay_col, 14)[25:36, 1:12].copy()
    for y, pressed in ((164, False), (176, True)):
        c = tb.copy()
        orb(c, 5.5, 5.5, 5.5, BUBBLE_DOWN if pressed else BUBBLE, hl=0.9, shadow=0.25)
        a[y:y + 11, 0:11] = c
    for n in range(28):
        a[164 + (n // 14) * 65:164 + (n // 14) * 65 + 63, 13 + (n % 14) * 15:13 + (n % 14) * 15 + 14] = \
            eq_frame(bay_col, n)
    for y, pressed in ((164, False), (176, True)):
        cell = bg[18:30, 217:261].copy()
        pill(cell, 0, 0, 44, 12, "glass", pressed, r=5)
        pill_label(cell, 0, 0, 44, 12, "PRESETS", "glass", pressed)
        a[y:y + 12, 224:268] = cell
        if not pressed:
            a[18:30, 217:261] = cell
    # graph: 113x19 dark glass with a faint grid, the line colours, the preamp line
    rect(a, 0, 294, 113, 19, DISP)
    for x in range(0, 113, 12):
        for y in range(1, 19, 2):
            px(a, 2 + x, 294 + y, (16, 70, 92))
    for x in range(0, 113, 2):
        px(a, x, 294 + 9, (24, 88, 110))
    for r in range(19):
        px(a, 115, 294 + r, ramp([WHITE, CYAN, (60, 206, 210), (90, 210, 90)], r / 18))
    for x in range(113):
        px(a, x, 314, (120, 230, 120) if x % 3 != 2 else DISP)
    # the window's graph spot shows the empty graph
    a[17:36, 86:199] = a[294:313, 0:113]
    return a


# ------------------------------------------------------------------------------------------
# pledit.bmp (280 x 186) and gen.bmp (194 x 109): the 20px-titled frames
# ------------------------------------------------------------------------------------------

BAR20_LIT = [(0, (236, 250, 255)), (0.1, (210, 240, 253)), (0.5, (150, 214, 246)), (0.5, (96, 186, 234)),
             (0.95, (66, 164, 220)), (1, (40, 120, 176))]
BAR20_DIM = [(0, (246, 250, 252)), (0.1, (228, 236, 242)), (0.5, (208, 220, 230)), (0.5, (188, 204, 216)),
             (0.95, (176, 194, 208)), (1, (150, 168, 184))]
FRAME_LIT_H = [(0, (236, 250, 255)), (0.15, (150, 214, 246)), (0.85, (96, 186, 234)), (1, (40, 120, 176))]
BOT_STOPS = [(0, (236, 250, 255)), (0.08, (196, 234, 252)), (0.42, (140, 208, 244)), (0.42, (100, 188, 234)),
             (0.9, (70, 168, 222)), (1, (36, 116, 172))]


def bar20(w, lit):
    return vgrad(20, BAR20_LIT if lit else BAR20_DIM, w)


def side_tile(w, h, outer_left):
    """A vertical frame strip: glass lit from the outside edge."""
    stops = FRAME_LIT_H if outer_left else FRAME_LIT_H[::-1]
    stops = [(p if outer_left else 1 - p, c) for p, c in stops]
    stops.sort(key=lambda s: s[0])
    row = np.array([stops_at(stops, (c + 0.5) / w) for c in range(w)], np.float32)
    return np.repeat(row[None, :, :], h, axis=0)


def groove_v(t, x, w):
    """A clear glass channel down a tile (the playlist's scrollbar groove)."""
    H, W = t.shape[:2]
    for c in range(w):
        f = (c + 0.5) / w
        t[:, x + c] = stops_at([(0, (90, 150, 190)), (0.2, (200, 232, 246)), (0.7, (236, 250, 255)),
                                (1, (150, 200, 226))], f)


def bottom_base(w):
    t = vgrad(38, BOT_STOPS, w)
    return t


def text_button(t, x, y, w, h, label):
    pill(t, x, y, w, h, "glass", False, r=5)
    pill_label(t, x, y, w, h, label, "glass", False)


def readout(t, x, y, w, h):
    H, W = t.shape[:2]
    paint(t, 0, 0, rr_mask(W, H, 2, x - 1, y - 1, w + 2, h + 2), (8, 56, 86))
    rect(t, x, y, w, h, DISP)


def mini_transport(t, kind, x, y):
    cell = t[y:y + 10, x:x + 10]
    orb(cell, 5, 5, 4.6, ORB_AQUA, hl=0.85, shadow=0)
    m = icon_mask(kind, 10, 10, 5 + (0.3 if kind == "play" else 0), 5, 0.62)
    paint(cell, 0, 0, m, WHITE)


def grip(t, x, y, n):
    for k in range(n):
        for j in range(k + 1):
            gx, gy = x - 3 * k + 3 * j, y - 3 * j
            px(t, gx + 1, gy + 1, (40, 120, 176))
            px(t, gx, gy, WHITE)


def make_pledit():
    a = new(280, 186, (200, 230, 246))
    for lit, y in ((True, 0), (False, 21)):
        a[y:y + 20, 127:152] = bar20(25, lit)
        t = bar20(25, lit)
        rect(t, 0, 0, 1, 20, (236, 250, 255))
        a[y:y + 20, 0:25] = t
        t = bar20(100, lit)
        title_text(t, "Playlist", 50, 14, lit, size=10)
        a[y:y + 20, 26:126] = t
        t = bar20(25, lit)
        rect(t, 24, 0, 1, 20, (30, 104, 160) if lit else (150, 168, 184))
        mini_button(t, 14, 3, "close", lit)
        a[y:y + 20, 153:178] = t

    a[42:71, 0:12] = side_tile(12, 29, True)
    t = side_tile(20, 29, False)
    groove_v(t, 4, 10)
    a[42:71, 31:51] = t
    bar = bar20(25, True)
    cell = bar[3:12, 14:23].copy()
    mini_button(cell, 0, 0, "close", True, pressed=True)
    a[42:51, 52:61] = cell
    # scroll handles: vertical glossy capsules in the groove
    for x, sel in ((52, False), (61, True)):
        g = side_tile(20, 18, False)
        groove_v(g, 4, 10)
        cell = g[:, 5:13].copy()
        H, W = cell.shape[:2]
        pal = BUBBLE_DOWN if sel else ORB_AQUA
        paint(cell, 0, 0, rr_mask(W, H, 3.5, 0, 0, 8, 18), pal["rim"])
        inner = rr_mask(W, H, 2.5, 1, 1, 6, 16)
        cols = np.array([stops_at([(0, pal["mid"]), (0.5, pal["deep"]), (1, pal["mid"])], (c + 0.5) / W)
                         for c in range(W)], np.float32)[None, :, :]
        paint(cell, 0, 0, inner, cols)
        paint(cell, 0, 0, rr_mask(W, H, 1, 1.5, 1.5, 2.2, 15), WHITE, 0.7)
        for gy in (6, 9, 12):
            rect(cell, 2, gy, 4, 1, lerp(pal["deep"], NAVY, 0.4))
            rect(cell, 2, gy + 1, 4, 1, lerp(pal["mid"], WHITE, 0.5))
        a[53:71, x:x + 8] = cell

    t = bottom_base(125)
    rect(t, 0, 0, 1, 38, (236, 250, 255))
    t[:, 0:12] = side_tile(12, 38, True)
    rect(t, 12, 0, 113, 1, (40, 120, 176))
    for bx, lbl in ((14, "ADD"), (43, "REM"), (72, "SEL"), (101, "MISC")):
        text_button(t, bx, 8, 22, 18, lbl)
    rect(t, 0, 37, 125, 1, (30, 104, 160))
    a[72:110, 0:125] = t

    t = bottom_base(150)
    t[:, 130:150] = side_tile(20, 38, False)
    rect(t, 0, 0, 130, 1, (40, 120, 176))
    readout(t, 6, 9, 56, 8)
    for k, kind in enumerate(ICON_KINDS):
        mini_transport(t, kind, 3 + 10 * k, 22)
    readout(t, 65, 22, 33, 8)
    rect(t, 84, 24, 1, 1, TXT_DIM)
    rect(t, 84, 27, 1, 1, TXT_DIM)
    text_button(t, 106, 8, 22, 18, "LIST")
    grip(t, 145, 31, 4)
    rect(t, 0, 37, 150, 1, (30, 104, 160))
    rect(t, 149, 0, 1, 38, (30, 104, 160))
    a[72:110, 126:276] = t

    t = bottom_base(25)
    rect(t, 0, 0, 25, 1, (40, 120, 176))
    rect(t, 0, 37, 25, 1, (30, 104, 160))
    a[0:38, 179:204] = t
    return a


GEN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def make_gen():
    a = new(194, 109, (200, 230, 246))
    for lit, y in ((True, 0), (False, 21)):
        def piece(px0, fn):
            t = bar20(25, lit)
            fn(t)
            a[y:y + 20, px0:px0 + 25] = t

        def left(t):
            rect(t, 0, 0, 1, 20, (236, 250, 255))

        def bead(t, cx):
            H, W = t.shape[:2]
            if lit:
                orb(t, cx, 8, 2.6, ORB_AQUA, hl=0.9, shadow=0.2)
            else:
                orb(t, cx, 8, 2.6, ORB_GREY, hl=0.7, shadow=0.15)

        def left_end(t):
            bead(t, 18.5)

        def right_end(t):
            bead(t, 6.5)

        def right(t):
            mini_button(t, 14, 3, "close", lit)
            rect(t, 24, 0, 1, 20, (30, 104, 160) if lit else (150, 168, 184))

        piece(0, left)
        piece(26, left_end)
        piece(52, lambda t: None)
        piece(78, right_end)
        piece(104, lambda t: None)
        piece(130, right)

    def bottom(w, grip_, left_edge):
        t = vgrad(14, [(0, (96, 186, 234)), (0.15, (150, 214, 246)), (0.9, (80, 172, 226)), (1, (30, 104, 160))], w)
        if left_edge:
            rect(t, 0, 0, 1, 14, (236, 250, 255))
        else:
            rect(t, w - 1, 0, 1, 14, (30, 104, 160))
        if grip_:
            grip(t, w - 4, 10, 3)
        return t

    a[42:56, 0:125] = bottom(125, False, True)
    a[57:71, 0:125] = bottom(125, True, False)
    t = bottom(25, False, True)
    t[:, 0] = t[:, 1]
    a[72:86, 127:152] = t
    for x, w, h, outer_left in ((127, 11, 29, True), (158, 11, 24, True), (139, 8, 29, False), (170, 8, 24, False)):
        a[42:42 + h, x:x + w] = side_tile(w, h, outer_left)
    bar = bar20(25, True)
    cell = bar[3:12, 14:23].copy()
    mini_button(cell, 0, 0, "close", True, pressed=True)
    a[42:51, 148:157] = cell

    # letters: each row starts at x 1, letters in their own cells (the bar's rows 4..10 under
    # them, so they sit seamlessly on the title piece), 1px separators of x 0's colour
    for lit, y in ((True, 88), (False, 96)):
        rect(a, 0, y, 194, 7, SEP)
        strip = bar20(1, lit)[4:11, 0]
        x = 1
        for c in GEN_LETTERS:
            w = glyph_w(FONT5, c) + 1
            a[y:y + 7, x:x + w] = strip[:, None, :]
            if lit:
                draw_text(a, FONT5, c, x, y + 1, WHITE, shadow=(16, 80, 130), sh_alpha=0.75)
            else:
                draw_text(a, FONT5, c, x, y + 1, (98, 120, 138), shadow=WHITE, sh_alpha=0.6)
            x += w + 1
        assert x <= 194, x
    return a


# ------------------------------------------------------------------------------------------
# genex.bmp: Media Library colours along the top row, every other pixel from x 48
# ------------------------------------------------------------------------------------------

GENEX_COLOURS = [
    (244, 251, 254),   # item background
    (18, 50, 74),      # item text
    (221, 241, 250),   # window background
    (14, 62, 98),      # button text
    (18, 50, 74),      # window text
    (156, 205, 228),   # dividers, sunken borders
    (155, 220, 242),   # selection bar
    (205, 235, 248),   # list header background
    (14, 74, 114),     # list header text
    (255, 255, 255),   # header frame, light
    (111, 175, 207),   # header frame, dark
    (143, 208, 234),   # header frame, pressed
    (221, 241, 250),   # header dead area
    (191, 227, 243),   # scrollbar
    (63, 175, 216),    # scrollbar 2
    (168, 216, 238),   # scrollbar pressed
    (70, 180, 70),     # scrollbar pressed 2
    (232, 246, 252),   # scrollbar dead area
]


def make_genex():
    a = new(256, 64, (221, 241, 250))
    for i, c in enumerate(GENEX_COLOURS):
        px(a, 48 + 2 * i, 0, c)
    pill(a, 0, 1, 47, 15, "glass", False, r=6)
    pill(a, 0, 16, 47, 15, "glass", True, r=6)
    return a


# ------------------------------------------------------------------------------------------
# Text files
# ------------------------------------------------------------------------------------------

VISCOLOR = (
    [(DISP, "background"), ((16, 66, 86), "dots")]
    + [(ramp([(255, 255, 255), (196, 250, 255), (90, 224, 244), (40, 196, 214), (60, 200, 130), (80, 186, 50)],
             i / 15), f"spectrum {i + 1} (top)" if i == 0 else f"spectrum {i + 1}") for i in range(16)]
    + [((230, 255, 255), "oscilloscope 1"), ((176, 244, 252), "oscilloscope 2"), ((110, 224, 238), "oscilloscope 3"),
       ((80, 206, 170), "oscilloscope 4"), ((90, 190, 80), "oscilloscope 5"), ((255, 255, 255), "peaks")]
)

PLEDIT = dict(Normal="#1C3E58", Current="#0378B4", NormalBG="#F4FBFE", SelectedBG="#B6E4F6",
              MbBG="#F4FBFE", MbFG="#1C3E58", Font="Arial")


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def write_text_files():
    with open(os.path.join(OUT, "viscolor.txt"), "w", newline="\r\n") as f:
        for (r, g, b), note in VISCOLOR:
            f.write(f"{r},{g},{b}, // {note}\n")
    with open(os.path.join(OUT, "pledit.txt"), "w", newline="\r\n") as f:
        f.write("[Text]\n" + "".join(f"{k}={v}\n" for k, v in PLEDIT.items()))
    with open(os.path.join(OUT, "readme.txt"), "w", newline="\r\n") as f:
        f.write(
            "YTMinamp Frutiger Aero - a skin in the Frutiger Aero aesthetic, drawn from scratch.\n"
            "\n"
            "A classic (Winamp 2.x format) skin: sky-to-aqua glass, bokeh bubbles, a grassy\n"
            "horizon, glossy aqua orbs, glass-tube sliders and green-lit toggles. Every bitmap\n"
            "was drawn by a script (gen_skin.py); nothing was taken from any other skin or\n"
            "product, and it carries no logos or marks.\n\n"
            "License: CC0 1.0 Universal (public domain dedication).\n"
        )


# ------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------

SHEETS = {}
MAIN_BASE_NO_ORBS = None


def build():
    global MAIN_BASE_NO_ORBS
    main, base = make_main()
    # main as it is just before the orbs: for the pressed transport cells
    pre = base.copy()
    pre[0:14, :] = main[0:14, :]
    MAIN_BASE_NO_ORBS = pre
    titlebar = make_titlebar(main, base)
    sheets = {
        "main.bmp": main,
        "titlebar.bmp": titlebar,
        "cbuttons.bmp": make_cbuttons(main),
        "shufrep.bmp": make_shufrep(base),
        "posbar.bmp": make_posbar(main),
        "volume.bmp": make_volume(main, base),
        "balance.bmp": make_balance(main, base),
        "monoster.bmp": make_monoster(main),
        "playpaus.bmp": make_playpaus(),
        "numbers.bmp": make_numbers(False),
        "nums_ex.bmp": make_numbers(True),
        "text.bmp": make_text(),
        "pledit.bmp": make_pledit(),
        "eqmain.bmp": make_eqmain(),
        "gen.bmp": make_gen(),
        "genex.bmp": make_genex(),
    }
    # main.bmp also shows the toggles off where shufrep draws them
    sr = sheets["shufrep.bmp"]
    main[89:104, 164:211] = sr[0:15, 28:75]
    main[89:104, 210:238] = sr[0:15, 0:28]
    main[58:70, 219:242] = sr[61:73, 0:23]
    main[58:70, 242:265] = sr[61:73, 23:46]
    for name, arr in sheets.items():
        SHEETS[name[:-4]] = save(arr, name)
    write_text_files()
    names = list(sheets) + ["pledit.txt", "viscolor.txt", "readme.txt"]
    wsz = os.path.join(HERE, f"{SKIN}.wsz")
    with zipfile.ZipFile(wsz, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(OUT, n), "rb") as f:
                z.writestr(info, f.read())
    # genex.bmp completed for real Winamp and WACUP: all 24 colours, readable text, and the
    # standard 112x59 button and scrollbar layout (skins/genex_wacup.py).
    genex_wacup.process(wsz)
    return names


# ------------------------------------------------------------------------------------------
# Preview: the windows put together from the sprites the way the app does
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
for _k, _v in {"<": "[", ">": "]", "{": "[", "}": "]"}.items():
    FONT_LOOKUP[_k] = FONT_LOOKUP[_v]


def draw_bitmap_text(dst, s, x, y):
    text = SHEETS["text"]
    for ch in s:
        row, col = FONT_LOOKUP.get(ch.lower(), FONT_LOOKUP[" "])
        blit(dst, text, (col * 5, row * 6, 5, 6), x, y)
        x += 5


def viscolors():
    return [c for c, _ in VISCOLOR]


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
    for x in range(0, 154, 5):
        w = min(5, 154 - x)
        blit(img, S["text"], (150, 0, w, 6), 111 + x, 24)
    draw_bitmap_text(img, state["title"][:30], 111, 24)
    draw_bitmap_text(img, "192", 111, 43)
    draw_bitmap_text(img, "44", 156, 43)
    cols = viscolors()
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
    d.rectangle((lx, 20, lx + lw - 1, h - 39), fill=hex_rgb(PLEDIT["NormalBG"]))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 9)
    except OSError:
        font = ImageFont.load_default()
    for i, (txt, dur) in enumerate(rows):
        y = 23 + i * 15
        if y + 15 > h - 38:
            break
        if i == 2:
            d.rectangle((lx, y, lx + lw - 1, y + 14), fill=hex_rgb(PLEDIT["SelectedBG"]))
        col = hex_rgb(PLEDIT["Current"]) if i == 1 else hex_rgb(PLEDIT["Normal"])
        d.text((lx + 2, y + 2), f"{i + 1}. {txt}", fill=col, font=font)
        d.text((lx + lw - 3 - d.textlength(dur, font=font), y + 2), dur, fill=col, font=font)
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
    # a stand-in picture: sky over a hill
    pw, ph = w - 22, h - 34
    pic = sky(pw, ph, seed=99, hill=(ph * 0.62, ph * 0.7, 4.0, 1.7), sun=(pw * 0.7, ph * 0.25), nbokeh=8)
    img.paste(Image.fromarray(np.clip(pic, 0, 255).astype(np.uint8)), (11, 20))
    return img


def preview():
    rows = [("Clear Water - Morning Tide", "4:12"), ("Bubble Garden - Glass Sky", "3:47"),
            ("Aquarium - Blue Lagoon", "5:03"), ("Meadow Light - Dew", "2:58"),
            ("Orbital - Cloud Nine", "6:21"), ("Rainforest - Canopy", "3:33"),
            ("Koi Pond - Ripples", "4:40"), ("Green Hills - Breeze", "3:09"),
            ("Skyline - Aurora", "5:51"), ("Coral Reef - Shimmer", "4:05"),
            ("Dolphin Bay - Surf", "3:22")]
    bars = [12, 15, 14, 11, 13, 10, 9, 11, 8, 7, 9, 6, 5, 6, 4, 3, 4, 2, 3]
    A = dict(pressed=None, eq=True, pl=True, clutter="AV", shuffle=True, repeat=False, playing=True, stereo=True,
             pos=0.38, seek=False, volume=72, vdrag=False, balance=0, time=207, remaining=False,
             title="FRUTIGER AERO - SKY AND WATER", bars=bars)
    B = dict(pressed="play", eq=False, pl=True, clutter="", shuffle=False, repeat=True, playing=False, stereo=False,
             pos=0.8, seek=True, volume=25, vdrag=True, balance=-60, time=95, remaining=True,
             title="PAUSED: GLASS RAIN (LIVE)", bars=[3, 2, 4, 1, 2, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
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
        col.paste(preview_gen(lit, 275, 140, "album art", pressed_close=not lit), (0, 464))
        cols.append(col)
    gap = 12
    out = Image.new("RGB", (275 * 2 + gap * 3, cols[0].height + gap * 2), (52, 64, 76))
    out.paste(cols[0], (gap, gap))
    out.paste(cols[1], (275 + 2 * gap, gap))
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    out.save(os.path.join(HERE, "preview.png"))


if __name__ == "__main__":
    if "--list" in sys.argv[1:]:
        print(SKIN)  # the one theme
        sys.exit(0)
    names = build()
    preview()
    for n in names:
        p = os.path.join(OUT, n)
        if n.endswith(".bmp"):
            im = Image.open(p)
            print(f"{n:14s} {im.size[0]}x{im.size[1]} {im.mode}")
        else:
            print(f"{n:14s} {os.path.getsize(p)} bytes")
