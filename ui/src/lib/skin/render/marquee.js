// Scrolling title marquee, after Webamp's `Marquee.tsx` (a step every 220ms, loop string =
// `text + "  ***  " + text`), computed from wall-clock time each frame instead of a
// `setInterval` counter — this file is driven by the rAF loop in loop.js, not its own timer.
// Also text.bmp text for the small fixed readouts (kbps, kHz, playlist time).

import { CHAR_W, FONT_LOOKUP, MARQUEE_POS, MARQUEE_SEPARATOR, MARQUEE_STEP_MS, charRect } from "./sprites.js";

function mod(n, m) {
  return ((n % m) + m) % m;
}

/** text.bmp's ink colour, per sheet (see `textInk`). */
const inks = new WeakMap();

/**
 * The colour text.bmp's letters are drawn in: the title's, as Winamp takes it from text.bmp, so it
 * shows on the skin's display whatever the playlist's colours are (a light playlist over a dark
 * display would otherwise draw the title dark on dark). The commonest colour in the letter and
 * digit rows that is clearly not the space cell's background; null if there's none.
 * @param {CanvasImageSource & { width: number, height: number }} sheet
 * @returns {string | null}
 */
function textInk(sheet) {
  if (inks.has(sheet)) return inks.get(sheet);
  let ink = null;
  try {
    const w = Math.min(sheet.width, 31 * CHAR_W);
    const h = Math.min(sheet.height, 2 * MARQUEE_POS.h);
    const canvas = new OffscreenCanvas(w, h);
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(sheet, 0, 0);
      const px = ctx.getImageData(0, 0, w, h).data;
      const space = charRect(" ");
      const at = (space.y * w + space.x) * 4;
      const bg = [px[at], px[at + 1], px[at + 2]];
      /** @type {Map<number, number>} */
      const counts = new Map();
      for (let i = 0; i < px.length; i += 4) {
        const d = Math.abs(px[i] - bg[0]) + Math.abs(px[i + 1] - bg[1]) + Math.abs(px[i + 2] - bg[2]);
        if (d < 96) continue;
        const key = (px[i] << 16) | (px[i + 1] << 8) | px[i + 2];
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
      let best = 0;
      for (const [key, n] of counts) {
        if (n > best) {
          best = n;
          ink = `#${key.toString(16).padStart(6, "0")}`;
        }
      }
    }
  } catch {
    ink = null;
  }
  inks.set(sheet, ink);
  return ink;
}

/** Whether text.bmp has every character of `text` (it has no international ones). @param {string} text */
function spellable(text) {
  for (const c of text) if (!(c.toLowerCase() in FONT_LOOKUP)) return false;
  return true;
}

/**
 * The title in text.bmp, as Winamp's bitmap title: a cell per character, scrolling a cell per
 * step when it's longer than the box (the same loop and pace as the TrueType one), clipped to it.
 * @param {CanvasRenderingContext2D} ctx @param {CanvasImageSource} sheet @param {string} title
 * @param {number} nowMs @param {boolean} scroll
 */
function drawBitmapTitle(ctx, sheet, title, nowMs, scroll) {
  const cells = Math.ceil(MARQUEE_POS.w / CHAR_W);
  let shown = title;
  if (scroll && title.length * CHAR_W > MARQUEE_POS.w) {
    const loop = `${title}${MARQUEE_SEPARATOR}`;
    const offset = mod(Math.floor(nowMs / MARQUEE_STEP_MS), loop.length);
    shown = `${loop}${loop}`.slice(offset, offset + cells);
  }
  ctx.save();
  ctx.beginPath();
  ctx.rect(MARQUEE_POS.x, MARQUEE_POS.y, MARQUEE_POS.w, MARQUEE_POS.h);
  ctx.clip();
  drawText(ctx, sheet, shown.slice(0, cells), MARQUEE_POS.x, MARQUEE_POS.y);
  ctx.restore();
}

/** Static text in the skin's text.bmp font at (x, y), e.g. the playlist's running time. */
export function drawText(ctx, textSheet, text, x, y) {
  for (const rawChar of text) {
    const r = charRect(rawChar.toLowerCase());
    ctx.drawImage(textSheet, r.x, r.y, r.w, r.h, x, y, r.w, r.h);
    x += CHAR_W;
  }
}

/**
 * The title in the playlist editor's font (pledit.txt) rather than text.bmp: it can show any
 * script (text.bmp has only ASCII) and reads like the playlist, in text.bmp's colour. Scrolls like Webamp's marquee —
 * one step per MARQUEE_STEP_MS — but by pixels, since the font is proportional.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} title
 * @param {number} nowMs
 * @param {{ font?: string, normal?: string }} pledit
 * @param {boolean} [scroll] scroll a title too long for the box (off: cut it short)
 * @param {CanvasImageSource} [textSheet] text.bmp, whose blank cell fills the box first
 * @param {boolean} [bitmap] in text.bmp itself when it has every character of the title
 */
export function drawTitle(ctx, title, nowMs, pledit, scroll = true, textSheet, bitmap = false) {
  // The box blanked first with text.bmp's space, as Winamp's bitmap title fills all 31 cells:
  // some skins paint credits or a logo there in main.bmp, which the title would scroll over.
  if (textSheet) {
    const blank = charRect(" ");
    for (let x = 0; x < MARQUEE_POS.w; x += CHAR_W) {
      const w = Math.min(CHAR_W, MARQUEE_POS.w - x);
      ctx.drawImage(textSheet, blank.x, blank.y, w, blank.h, MARQUEE_POS.x + x, MARQUEE_POS.y, w, blank.h);
    }
    if (bitmap && spellable(title)) return drawBitmapTitle(ctx, textSheet, title, nowMs, scroll);
  }
  // A TrueType line is taller than text.bmp's 6px row, so it's centred on that row (many skins
  // frame it in a box there) and clipped a little above and below it, well clear of the
  // kbps/kHz row at y 43.
  const top = MARQUEE_POS.y - 2;
  const h = MARQUEE_POS.h + 8;
  ctx.save();
  ctx.beginPath();
  ctx.rect(MARQUEE_POS.x, top, MARQUEE_POS.w, h);
  ctx.clip();
  ctx.font = `11px ${pledit.font ? `"${pledit.font}", ` : ""}Arial, sans-serif`;
  // text.bmp's colour, as Winamp's title; the playlist's only for a sheet without one.
  ctx.fillStyle = (textSheet && textInk(/** @type {any} */ (textSheet))) || pledit.normal || "#00ff00";
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  // Centred on the bitmap row, two pixels low so capitals sit in it rather than over its top.
  const y = MARQUEE_POS.y + MARQUEE_POS.h / 2 + 2;
  const width = ctx.measureText(title).width;
  if (width <= MARQUEE_POS.w || !scroll) {
    ctx.fillText(title, MARQUEE_POS.x, y);
  } else {
    const loop = `${title}${MARQUEE_SEPARATOR}`;
    const offset = mod(Math.floor(nowMs / MARQUEE_STEP_MS) * CHAR_W, ctx.measureText(loop).width);
    ctx.fillText(`${loop}${title}`, MARQUEE_POS.x - offset, y);
  }
  ctx.restore();
}
