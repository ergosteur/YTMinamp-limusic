// Scrolling title marquee, after Webamp's `Marquee.tsx` (a step every 220ms, loop string =
// `text + "  ***  " + text`), computed from wall-clock time each frame instead of a
// `setInterval` counter — this file is driven by the rAF loop in loop.js, not its own timer.
// Also text.bmp text for the small fixed readouts (kbps, kHz, playlist time).

import { CHAR_W, MARQUEE_POS, MARQUEE_SEPARATOR, MARQUEE_STEP_MS, charRect } from "./sprites.js";

function mod(n, m) {
  return ((n % m) + m) % m;
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
 * script (text.bmp has only ASCII) and reads like the playlist. Scrolls like Webamp's marquee —
 * one step per MARQUEE_STEP_MS — but by pixels, since the font is proportional.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} title
 * @param {number} nowMs
 * @param {{ font?: string, normal?: string }} pledit
 */
export function drawTitle(ctx, title, nowMs, pledit) {
  // A TrueType line is taller than text.bmp's 6px row, so it's centred on that row (many skins
  // frame it in a box there) and clipped a little above and below it, well clear of the
  // kbps/kHz row at y 43.
  const top = MARQUEE_POS.y - 2;
  const h = MARQUEE_POS.h + 7;
  ctx.save();
  ctx.beginPath();
  ctx.rect(MARQUEE_POS.x, top, MARQUEE_POS.w, h);
  ctx.clip();
  ctx.font = `11px ${pledit.font ? `"${pledit.font}", ` : ""}Arial, sans-serif`;
  ctx.fillStyle = pledit.normal ?? "#00ff00";
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  // Centred on the bitmap row, a hair low so capitals sit in it rather than over its top.
  const y = MARQUEE_POS.y + MARQUEE_POS.h / 2 + 1;
  const width = ctx.measureText(title).width;
  if (width <= MARQUEE_POS.w) {
    ctx.fillText(title, MARQUEE_POS.x, y);
  } else {
    const loop = `${title}${MARQUEE_SEPARATOR}`;
    const offset = mod(Math.floor(nowMs / MARQUEE_STEP_MS) * CHAR_W, ctx.measureText(loop).width);
    ctx.fillText(`${loop}${title}`, MARQUEE_POS.x - offset, y);
  }
  ctx.restore();
}
