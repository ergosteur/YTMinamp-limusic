// Sprite sub-rectangle and main-window layout constants for classic Winamp skins.
//
// Source: the Webamp project (MIT licensed, github.com/captbaritone/webamp),
// `packages/webamp/js/skinSprites.ts` and `packages/webamp/css/main-window.css`, verified
// against a local clone 2026-10-21 (every table below was spot-checked line-by-line against
// the actual source, not just transcribed from a summary). These are facts (pixel coordinates
// that are the same for every classic skin — only the bitmap pixels differ by skin), not copied
// source code: ytminamp is GPL-3.0-or-later, Webamp is MIT; porting numeric constants between
// differently-licensed projects is fine, copying implementation code is not.

/** @typedef {{x: number, y: number, w: number, h: number}} Rect */
/** @typedef {{x: number, y: number}} Pos */

// ---------------------------------------------------------------------------------------------
// cbuttons.bmp — transport buttons
// ---------------------------------------------------------------------------------------------

export const CBUTTONS = {
  previous: { x: 0, y: 0, w: 23, h: 18 },
  previousActive: { x: 0, y: 18, w: 23, h: 18 },
  play: { x: 23, y: 0, w: 23, h: 18 },
  playActive: { x: 23, y: 18, w: 23, h: 18 },
  pause: { x: 46, y: 0, w: 23, h: 18 },
  pauseActive: { x: 46, y: 18, w: 23, h: 18 },
  stop: { x: 69, y: 0, w: 23, h: 18 },
  stopActive: { x: 69, y: 18, w: 23, h: 18 },
  next: { x: 92, y: 0, w: 22, h: 18 },
  nextActive: { x: 92, y: 18, w: 22, h: 18 },
  eject: { x: 114, y: 0, w: 22, h: 16 },
  ejectActive: { x: 114, y: 16, w: 22, h: 16 },
};

// Main-window position of each button (top-left corner); width/height come from CBUTTONS above.
export const CBUTTONS_POS = {
  previous: { x: 16, y: 88 },
  play: { x: 39, y: 88 },
  pause: { x: 62, y: 88 },
  stop: { x: 85, y: 88 },
  next: { x: 108, y: 88 },
  eject: { x: 136, y: 89 },
};

// ---------------------------------------------------------------------------------------------
// playpaus.bmp — the small playing/paused/stopped indicator + "working" strip
// ---------------------------------------------------------------------------------------------

export const PLAYPAUS = {
  playing: { x: 0, y: 0, w: 9, h: 9 },
  paused: { x: 9, y: 0, w: 9, h: 9 },
  stopped: { x: 18, y: 0, w: 9, h: 9 },
  notWorking: { x: 36, y: 0, w: 9, h: 9 },
  working: { x: 39, y: 0, w: 9, h: 9 },
};

export const PLAY_PAUSE_INDICATOR_POS = { x: 26, y: 28, w: 9, h: 9 };
// Only a 3px-wide slice of the 9px-wide working/not-working sprite is shown — confirmed in
// Webamp's own CSS (`#work-indicator { width: 3px }`), not a transcription error.
export const WORK_INDICATOR_POS = { x: 24, y: 28, w: 3, h: 9 };

// ---------------------------------------------------------------------------------------------
// shufrep.bmp — shuffle/repeat toggles + EQ/playlist window toggles
// ---------------------------------------------------------------------------------------------

export const SHUFREP = {
  shuffle: { x: 28, y: 0, w: 47, h: 15 },
  shuffleDepressed: { x: 28, y: 15, w: 47, h: 15 },
  shuffleOn: { x: 28, y: 30, w: 47, h: 15 },
  shuffleOnDepressed: { x: 28, y: 45, w: 47, h: 15 },
  repeat: { x: 0, y: 0, w: 28, h: 15 },
  repeatDepressed: { x: 0, y: 15, w: 28, h: 15 },
  repeatOn: { x: 0, y: 30, w: 28, h: 15 },
  repeatOnDepressed: { x: 0, y: 45, w: 28, h: 15 },
  eq: { x: 0, y: 61, w: 23, h: 12 },
  eqOn: { x: 0, y: 73, w: 23, h: 12 },
  eqDepressed: { x: 46, y: 61, w: 23, h: 12 },
  eqOnDepressed: { x: 46, y: 73, w: 23, h: 12 },
  playlist: { x: 23, y: 61, w: 23, h: 12 },
  playlistOn: { x: 23, y: 73, w: 23, h: 12 },
  playlistDepressed: { x: 69, y: 61, w: 23, h: 12 },
  playlistOnDepressed: { x: 69, y: 73, w: 23, h: 12 },
};

// `.shuffle-repeat` container: top:89 left:164; shuffle at relative x:0 (w:47), repeat at x:46 (w:28).
export const SHUFFLE_POS = { x: 164, y: 89 };
export const REPEAT_POS = { x: 164 + 46, y: 89 };
// `.windows` container: top:58 left:219; eq at x:0, playlist at x:23, both 23x12.
export const EQ_TOGGLE_POS = { x: 219, y: 58 };
export const PLAYLIST_TOGGLE_POS = { x: 219 + 23, y: 58 };

// ---------------------------------------------------------------------------------------------
// monoster.bmp — mono/stereo indicator
// ---------------------------------------------------------------------------------------------

export const MONOSTER = {
  stereoOff: { x: 0, y: 12, w: 29, h: 12 },
  stereoOn: { x: 0, y: 0, w: 29, h: 12 },
  monoOff: { x: 29, y: 12, w: 27, h: 12 },
  monoOn: { x: 29, y: 0, w: 27, h: 12 },
};

// `.mono-stereo` container: top:41 left:212; mono at x:0 (w:27), stereo at x:27 (w:29).
export const MONO_POS = { x: 212, y: 41 };

// `#visualizer`: top:43 left:24, a 76x16 canvas.
export const VIS_POS = { x: 24, y: 43, w: 76, h: 16 };
export const STEREO_POS = { x: 212 + 27, y: 41 };

// ---------------------------------------------------------------------------------------------
// posbar.bmp — seek bar
// ---------------------------------------------------------------------------------------------

export const POSBAR = {
  track: { x: 0, y: 0, w: 248, h: 10 },
  thumb: { x: 248, y: 0, w: 29, h: 10 },
  thumbSelected: { x: 278, y: 0, w: 29, h: 10 },
};

export const POSBAR_POS = { x: 16, y: 72 };
// Webamp renders this as a native `<input type=range>` and lets the browser place the thumb;
// for our own hit-testing/drawing, the equivalent travel range (thumb left edge, 0%-100%) is
// track width minus thumb width.
export const POSBAR_THUMB_TRAVEL = POSBAR.track.w - POSBAR.thumb.w; // 219

// ---------------------------------------------------------------------------------------------
// volume.bmp / balance.bmp — sliders. 28 frames, each 15px tall, within the sheet.
// ---------------------------------------------------------------------------------------------

export const SLIDER_FRAME_COUNT = 28;
export const SLIDER_FRAME_HEIGHT = 15;

export const VOLUME = {
  background: { x: 0, y: 0, w: 68, h: 420 },
  thumb: { x: 15, y: 422, w: 14, h: 11 },
  thumbSelected: { x: 0, y: 422, w: 14, h: 11 },
};
export const BALANCE = {
  background: { x: 9, y: 0, w: 38, h: 420 },
  thumb: { x: 15, y: 422, w: 14, h: 11 },
  thumbSelected: { x: 0, y: 422, w: 14, h: 11 },
};

// Visible height is 13px even though each background frame is 15px tall: only the top 13 rows are
// drawn, as in Winamp and Webamp; skins put anything in the last 2 (see drawSlider).
export const VOLUME_POS = { x: 107, y: 57, w: 68, h: 13 };
export const BALANCE_POS = { x: 177, y: 57, w: 38, h: 13 };
export const SLIDER_THUMB_SIZE = { w: 14, h: 11 };

/** 0-100 volume percent -> source Y offset into VOLUME.background. */
export function volumeFrameY(percent) {
  const clamped = Math.max(0, Math.min(100, percent));
  const index = Math.max(0, Math.round((clamped / 100) * SLIDER_FRAME_COUNT) - 1);
  return index * SLIDER_FRAME_HEIGHT;
}

/** -100..100 balance -> source Y offset into BALANCE.background. */
export function balanceFrameY(balance) {
  const clamped = Math.max(-100, Math.min(100, balance));
  const index = Math.floor((Math.abs(clamped) / 100) * (SLIDER_FRAME_COUNT - 1));
  return index * SLIDER_FRAME_HEIGHT;
}

// ---------------------------------------------------------------------------------------------
// numbers.bmp / nums_ex.bmp — time digits
// ---------------------------------------------------------------------------------------------

export const NUMBERS = {
  noMinus: { x: 9, y: 6, w: 5, h: 1 },
  minus: { x: 20, y: 6, w: 5, h: 1 },
  digit: (n) => ({ x: 9 * n, y: 0, w: 9, h: 13 }),
};
export const NUMS_EX = {
  noMinus: { x: 90, y: 0, w: 9, h: 13 },
  minus: { x: 99, y: 0, w: 9, h: 13 },
  digit: (n) => ({ x: 9 * n, y: 0, w: 9, h: 13 }),
};

// `#time` container: top:26 left:39, 59x13. Digit children have no explicit `top` in the CSS
// (so they sit flush with the container's top edge, y:26); minus-sign is the one exception with
// an explicit `top:6px` relative offset.
export const TIME_MINUS_POS = { x: 39 - 1, y: 26 + 6 };
export const TIME_MINUTE_TENS_POS = { x: 39 + 9, y: 26 };
export const TIME_MINUTE_UNITS_POS = { x: 39 + 21, y: 26 };
export const TIME_SECOND_TENS_POS = { x: 39 + 39, y: 26 };
export const TIME_SECOND_UNITS_POS = { x: 39 + 51, y: 26 };
/** The whole time readout; clicking it toggles elapsed/remaining. */
export const TIME_POS = { x: 39, y: 26, w: 59, h: 13 };

export const KBPS_POS = { x: 111, y: 43, w: 15, h: 6 };
export const KHZ_POS = { x: 156, y: 43, w: 10, h: 6 };

// ---------------------------------------------------------------------------------------------
// text.bmp — bitmap font for the marquee title (and kbps/khz/time-adjacent text)
// ---------------------------------------------------------------------------------------------

export const CHAR_W = 5;
export const CHAR_H = 6;

/** char (already lowercased) -> [row, col] in text.bmp's character grid. */
export const FONT_LOOKUP = {
  a: [0, 0], b: [0, 1], c: [0, 2], d: [0, 3], e: [0, 4], f: [0, 5], g: [0, 6],
  h: [0, 7], i: [0, 8], j: [0, 9], k: [0, 10], l: [0, 11], m: [0, 12], n: [0, 13],
  o: [0, 14], p: [0, 15], q: [0, 16], r: [0, 17], s: [0, 18], t: [0, 19], u: [0, 20],
  v: [0, 21], w: [0, 22], x: [0, 23], y: [0, 24], z: [0, 25], '"': [0, 26], "@": [0, 27],
  " ": [0, 30],
  "0": [1, 0], "1": [1, 1], "2": [1, 2], "3": [1, 3], "4": [1, 4], "5": [1, 5],
  "6": [1, 6], "7": [1, 7], "8": [1, 8], "9": [1, 9],
  "…": [1, 10], // ellipsis
  ".": [1, 11], ":": [1, 12], "(": [1, 13], ")": [1, 14], "-": [1, 15], "'": [1, 16],
  "!": [1, 17], "_": [1, 18], "+": [1, 19], "\\": [1, 20], "/": [1, 21], "[": [1, 22],
  "]": [1, 23], "^": [1, 24], "&": [1, 25], "%": [1, 26], ",": [1, 27], "=": [1, 28],
  "$": [1, 29], "#": [1, 30],
  "å": [2, 0], "ö": [2, 1], "ä": [2, 2], "?": [2, 3], "*": [2, 4], // looked up lowercased
  "<": [1, 22], ">": [1, 23], "{": [1, 22], "}": [1, 23],
};

/** @param {string} char single already-lowercased character @returns {Rect} */
export function charRect(char) {
  const pos = FONT_LOOKUP[char] ?? FONT_LOOKUP[" "];
  const [row, col] = pos;
  return { x: col * CHAR_W, y: row * CHAR_H, w: CHAR_W, h: CHAR_H };
}

export const MARQUEE_POS = { x: 111, y: 24, w: 154, h: 6 };
/** The Winamp logo, bottom right: click for About (Webamp's main-window.css #about). */
export const ABOUT_POS = { x: 253, y: 91, w: 13, h: 15 };
export const MARQUEE_SEPARATOR = "  ***  ";
export const MARQUEE_STEP_MS = 220;

// ---------------------------------------------------------------------------------------------
// titlebar.bmp
// ---------------------------------------------------------------------------------------------

export const TITLEBAR = {
  bar: { x: 27, y: 15, w: 275, h: 14 },
  barSelected: { x: 27, y: 0, w: 275, h: 14 },
  options: { x: 0, y: 0, w: 9, h: 9 },
  optionsDepressed: { x: 0, y: 9, w: 9, h: 9 },
  minimize: { x: 9, y: 0, w: 9, h: 9 },
  minimizeDepressed: { x: 9, y: 9, w: 9, h: 9 },
  shade: { x: 0, y: 18, w: 9, h: 9 },
  shadeDepressed: { x: 9, y: 18, w: 9, h: 9 },
  close: { x: 18, y: 0, w: 9, h: 9 },
  closeDepressed: { x: 18, y: 9, w: 9, h: 9 },
};

export const TITLE_BAR_POS = { x: 0, y: 0, w: 275, h: 14 };
export const OPTIONS_BUTTON_POS = { x: 6, y: 3 };
export const MINIMIZE_BUTTON_POS = { x: 244, y: 3 };
export const SHADE_BUTTON_POS = { x: 254, y: 3 };
export const CLOSE_BUTTON_POS = { x: 264, y: 3 };

// ---------------------------------------------------------------------------------------------
// The clutterbar: the O A I D V strip left of the time display. Webamp's main-window.css
// (#clutter-bar at 10,22, 8x43) and MAIN_CLUTTER_BAR_* in titlebar.bmp.
// ---------------------------------------------------------------------------------------------

export const CLUTTER_POS = { x: 10, y: 22, w: 8, h: 43 };
export const CLUTTER_BACKGROUND = { x: 304, y: 0, w: 8, h: 43 };
/** Each letter: where it sits in the bar, and its lit sprite in titlebar.bmp. */
export const CLUTTER_BUTTONS = /** @type {const} */ ({
  o: { y: 3, h: 8, sprite: { x: 304, y: 47, w: 8, h: 8 } },
  a: { y: 11, h: 7, sprite: { x: 312, y: 55, w: 8, h: 7 } },
  i: { y: 18, h: 7, sprite: { x: 320, y: 62, w: 8, h: 7 } },
  d: { y: 25, h: 8, sprite: { x: 328, y: 69, w: 8, h: 8 } },
  v: { y: 33, h: 7, sprite: { x: 336, y: 77, w: 8, h: 7 } },
});
