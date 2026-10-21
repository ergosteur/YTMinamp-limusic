import { NUMBERS, NUMS_EX, TIME_MINUS_POS, TIME_MINUTE_TENS_POS, TIME_MINUTE_UNITS_POS, TIME_SECOND_TENS_POS, TIME_SECOND_UNITS_POS } from "./sprites.js";

/**
 * Draws the MM:SS time display. Prefers `numbers.bmp`, falls back to `nums_ex.bmp` — real skins
 * ship either one, the other, or both (confirmed against the 3 fixture skins in `crates/skin`).
 * @param {CanvasRenderingContext2D} ctx
 * @param {ImageBitmap | undefined} numbers
 * @param {ImageBitmap | undefined} numsEx
 * @param {number} totalSeconds
 * @param {boolean} negative time-remaining mode: a minus sign before the digits
 */
export function drawTimeDigits(ctx, numbers, numsEx, totalSeconds, negative = false) {
  const sheet = numbers ?? numsEx;
  const table = numbers ? NUMBERS : NUMS_EX;
  if (!sheet) return;

  if (negative) {
    // numbers.bmp's minus is a 5x1 dash halfway down; nums_ex.bmp's is a full 9x13 glyph.
    const r = table.minus;
    const y = numbers ? TIME_MINUS_POS.y : TIME_MINUS_POS.y - 6;
    ctx.drawImage(sheet, r.x, r.y, r.w, r.h, TIME_MINUS_POS.x, y, r.w, r.h);
  }

  const clamped = Math.max(0, Math.floor(totalSeconds || 0));
  const minutes = Math.min(99, Math.floor(clamped / 60));
  const seconds = clamped % 60;

  const draw = (digit, pos) => {
    const r = table.digit(digit);
    ctx.drawImage(sheet, r.x, r.y, r.w, r.h, pos.x, pos.y, r.w, r.h);
  };

  draw(Math.floor(minutes / 10) % 10, TIME_MINUTE_TENS_POS);
  draw(minutes % 10, TIME_MINUTE_UNITS_POS);
  draw(Math.floor(seconds / 10), TIME_SECOND_TENS_POS);
  draw(seconds % 10, TIME_SECOND_UNITS_POS);
}
