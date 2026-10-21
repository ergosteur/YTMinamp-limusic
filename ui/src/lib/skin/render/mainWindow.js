import {
  BALANCE,
  BALANCE_POS,
  CBUTTONS,
  CBUTTONS_POS,
  CLUTTER_BACKGROUND,
  CLUTTER_BUTTONS,
  CLUTTER_POS,
  MONO_POS,
  MONOSTER,
  PLAY_PAUSE_INDICATOR_POS,
  EQ_TOGGLE_POS,
  KBPS_POS,
  KHZ_POS,
  PLAYLIST_TOGGLE_POS,
  PLAYPAUS,
  POSBAR,
  REPEAT_POS,
  SHUFFLE_POS,
  SHUFREP,
  POSBAR_POS,
  POSBAR_THUMB_TRAVEL,
  SLIDER_THUMB_SIZE,
  STEREO_POS,
  VOLUME,
  VOLUME_POS,
  balanceFrameY,
  volumeFrameY,
} from "./sprites.js";
import { drawTimeDigits } from "./numbers.js";
import { drawText, drawTitle } from "./marquee.js";
import { drawAnalyzer } from "./visualizer.js";

/** @typedef {import("../ipc.js").RegionPayload} RegionPayload */

export const MAIN_W = 275;
export const MAIN_H = 116;

/**
 * Size the canvas buffer *and* its CSS box to the window's content. Both, because the CSS size
 * must not follow the buffer through layout rules (Tailwind's preflight caps canvas width).
 * @param {HTMLCanvasElement} canvas
 * @param {number} width
 * @param {number} height
 */
export function sizeCanvas(canvas, width, height) {
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  // Double size zooms the page: blocky pixels, like Winamp's, not a blur.
  canvas.style.imageRendering = "pixelated";
}

/** Signed area > 0 means counter-clockwise in screen coordinates (y down). */
function clockwise(points) {
  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    area += x1 * y2 - x2 * y1;
  }
  return area >= 0 ? points : [...points].reverse();
}

/**
 * Shapes the canvas to the skin's `region.txt` (the main window, at `mainX`) plus a plain
 * rectangle for each docked panel. Winamp ORs the region's polygons together; a CSS `path()` with
 * every polygon wound the same way does the same under the default nonzero rule. No region.txt:
 * plain rectangle.
 * @param {HTMLCanvasElement} canvas
 * @param {RegionPayload | null} region
 * @param {number} mainX
 * @param {{x: number, y: number, w: number, h: number}[]} rects
 */
export function applyRegionClip(canvas, region, mainX, rects) {
  const parts = [];
  if (region && region.normal.length > 0) {
    for (const polygon of region.normal) {
      if (polygon.length < 3) continue;
      parts.push(`M${clockwise(polygon).map(([x, y]) => `${x + mainX} ${y}`).join(" L")} Z`);
    }
  } else {
    parts.push(`M${mainX} 0 H${mainX + MAIN_W} V${MAIN_H} H${mainX} Z`);
  }
  for (const r of rects) {
    parts.push(`M${r.x} ${r.y} H${r.x + r.w} V${r.y + r.h} H${r.x} Z`);
  }
  canvas.style.clipPath = `path('${parts.join(" ")}')`;
}

/**
 * Draws everything: background, transport buttons (pressed-state aware), play/pause indicator,
 * mono/stereo, seek bar, volume/balance sliders, time digits, marquee title, shuffle/repeat and
 * the EQ/playlist toggles (EQ always off: there is no equalizer window).
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {import("../state.js").state} uiState
 * @param {number} nowMs
 */
export function drawMainWindow(ctx, sprites, uiState, nowMs) {
  const main = sprites.get("main");
  if (!main) return;
  ctx.drawImage(main, 0, 0);
  // The titlebar ("WINAMP" and its buttons) comes from titlebar.bmp, not main.bmp, whose top strip
  // many skins leave blank. Webamp's MAIN_TITLE_BAR_SELECTED.
  const titlebar = sprites.get("titlebar");
  if (titlebar) ctx.drawImage(titlebar, 27, 0, MAIN_W, 14, 0, 0, MAIN_W, 14);

  if (uiState.visMode === "analyzer") {
    drawAnalyzer(ctx, uiState.viscolor, uiState.vizColumns);
  }

  drawButtons(ctx, sprites, uiState);
  drawPlaylistToggle(ctx, sprites, uiState);
  drawClutterBar(ctx, sprites, uiState);
  drawShuffleRepeat(ctx, sprites, uiState);
  drawPlayPauseIndicator(ctx, sprites, uiState);
  drawMonoStereo(ctx, sprites, uiState);
  drawPosbar(ctx, sprites, uiState);
  drawSlider(ctx, sprites.get("volume"), VOLUME, VOLUME_POS, volumeFrameY(uiState.volume), uiState.volume / 100);
  drawSlider(
    ctx,
    sprites.get("balance"),
    BALANCE,
    BALANCE_POS,
    balanceFrameY(uiState.balance),
    (uiState.balance + 100) / 200,
  );

  const numbers = sprites.get("numbers");
  const numsEx = sprites.get("nums_ex");
  if (numbers || numsEx) {
    const remaining = uiState.timeRemaining && uiState.durationSecs > 0;
    const secs = remaining ? uiState.durationSecs - uiState.positionSecs : uiState.positionSecs;
    drawTimeDigits(ctx, numbers, numsEx, secs, remaining);
  }

  drawTitle(ctx, uiState.loading ? "loading..." : uiState.title, nowMs, uiState.pledit);

  const text = sprites.get("text");
  if (text) {
    if (uiState.kbps != null) drawText(ctx, text, String(uiState.kbps).padStart(3, " ").slice(-3), KBPS_POS.x, KBPS_POS.y);
    if (uiState.khz != null) drawText(ctx, text, String(uiState.khz).padStart(2, " ").slice(-2), KHZ_POS.x, KHZ_POS.y);
  }
}

function drawButtons(ctx, sprites, uiState) {
  const sheet = sprites.get("cbuttons");
  if (!sheet) return;
  const draw = (name, normal, active) => {
    const pos = CBUTTONS_POS[name];
    const r = uiState.pressedButton === name ? active : normal;
    ctx.drawImage(sheet, r.x, r.y, r.w, r.h, pos.x, pos.y, r.w, r.h);
  };
  draw("previous", CBUTTONS.previous, CBUTTONS.previousActive);
  draw("play", CBUTTONS.play, CBUTTONS.playActive);
  draw("pause", CBUTTONS.pause, CBUTTONS.pauseActive);
  draw("stop", CBUTTONS.stop, CBUTTONS.stopActive);
  draw("next", CBUTTONS.next, CBUTTONS.nextActive);
  draw("eject", CBUTTONS.eject, CBUTTONS.ejectActive);
}

function drawPlaylistToggle(ctx, sprites, uiState) {
  const sheet = sprites.get("shufrep");
  if (!sheet) return;
  const pressed = uiState.pressedButton === "playlist";
  const r = uiState.plOpen
    ? pressed ? SHUFREP.playlistOnDepressed : SHUFREP.playlistOn
    : pressed ? SHUFREP.playlistDepressed : SHUFREP.playlist;
  ctx.drawImage(sheet, r.x, r.y, r.w, r.h, PLAYLIST_TOGGLE_POS.x, PLAYLIST_TOGGLE_POS.y, r.w, r.h);
  const eqPressed = uiState.pressedButton === "eq";
  const eq = uiState.eqOpen
    ? eqPressed ? SHUFREP.eqOnDepressed : SHUFREP.eqOn
    : eqPressed ? SHUFREP.eqDepressed : SHUFREP.eq;
  ctx.drawImage(sheet, eq.x, eq.y, eq.w, eq.h, EQ_TOGGLE_POS.x, EQ_TOGGLE_POS.y, eq.w, eq.h);
}

/**
 * O A I D V. A letter lights while pressed, and A (always on top), I (album art), D (double size)
 * and V (visualizer) also while they're on.
 */
function drawClutterBar(ctx, sprites, uiState) {
  const sheet = sprites.get("titlebar");
  if (!sheet) return;
  const bg = CLUTTER_BACKGROUND;
  ctx.drawImage(sheet, bg.x, bg.y, bg.w, bg.h, CLUTTER_POS.x, CLUTTER_POS.y, bg.w, bg.h);
  const on = {
    o: false,
    a: uiState.alwaysOnTop,
    i: uiState.artOpen,
    d: uiState.doubleSize,
    v: uiState.visMode !== "off",
  };
  for (const [letter, b] of Object.entries(CLUTTER_BUTTONS)) {
    if (!on[letter] && uiState.pressedButton !== `clutter-${letter}`) continue;
    const r = b.sprite;
    ctx.drawImage(sheet, r.x, r.y, r.w, r.h, CLUTTER_POS.x, CLUTTER_POS.y + b.y, r.w, r.h);
  }
}

function drawShuffleRepeat(ctx, sprites, uiState) {
  const sheet = sprites.get("shufrep");
  if (!sheet) return;
  /** @param {string} name @param {boolean} on @param {{x: number, y: number}} pos */
  const draw = (name, on, pos) => {
    const pressed = uiState.pressedButton === name;
    const r = SHUFREP[`${name}${on ? "On" : ""}${pressed ? "Depressed" : ""}`];
    ctx.drawImage(sheet, r.x, r.y, r.w, r.h, pos.x, pos.y, r.w, r.h);
  };
  draw("shuffle", uiState.shuffle, SHUFFLE_POS);
  // Lit for both repeat-all and repeat-one; the marquee says which when it changes.
  draw("repeat", uiState.repeat !== "off", REPEAT_POS);
}

function drawPlayPauseIndicator(ctx, sprites, uiState) {
  const sheet = sprites.get("playpaus");
  if (!sheet) return;
  const r = uiState.playing ? PLAYPAUS.playing : PLAYPAUS.paused;
  const pos = PLAY_PAUSE_INDICATOR_POS;
  ctx.drawImage(sheet, r.x, r.y, r.w, r.h, pos.x, pos.y, r.w, r.h);
}

function drawMonoStereo(ctx, sprites, uiState) {
  const sheet = sprites.get("monoster");
  if (!sheet) return;
  const mono = uiState.stereo ? MONOSTER.monoOff : MONOSTER.monoOn;
  const stereo = uiState.stereo ? MONOSTER.stereoOn : MONOSTER.stereoOff;
  ctx.drawImage(sheet, mono.x, mono.y, mono.w, mono.h, MONO_POS.x, MONO_POS.y, mono.w, mono.h);
  ctx.drawImage(sheet, stereo.x, stereo.y, stereo.w, stereo.h, STEREO_POS.x, STEREO_POS.y, stereo.w, stereo.h);
}

function drawPosbar(ctx, sprites, uiState) {
  const sheet = sprites.get("posbar");
  if (!sheet) return;
  const track = POSBAR.track;
  ctx.drawImage(sheet, track.x, track.y, track.w, track.h, POSBAR_POS.x, POSBAR_POS.y, track.w, track.h);

  const percent = uiState.durationSecs > 0 ? uiState.positionSecs / uiState.durationSecs : 0;
  const thumbLeft = Math.round(Math.max(0, Math.min(1, percent)) * POSBAR_THUMB_TRAVEL);
  const thumb = uiState.draggingSeek ? POSBAR.thumbSelected : POSBAR.thumb;
  ctx.drawImage(
    sheet,
    thumb.x,
    thumb.y,
    thumb.w,
    thumb.h,
    POSBAR_POS.x + thumbLeft,
    POSBAR_POS.y,
    thumb.w,
    thumb.h,
  );
}

/**
 * A horizontal slider (volume/balance): the background frame shows the fill level, and a
 * separately-positioned thumb travels the slider's width. `percent` is 0 (quietest/full-left)
 * to 1 (loudest/full-right).
 */
function drawSlider(ctx, sheet, table, pos, frameY, percent) {
  if (!sheet) return;
  // Visible window is cropped 1px top/bottom vs. the 15px-tall source frame (Webamp's own
  // documented quirk, see sprites.js).
  const srcY = table.background.y + frameY + 1;
  ctx.drawImage(sheet, table.background.x, srcY, pos.w, pos.h, pos.x, pos.y, pos.w, pos.h);

  const thumb = table.thumb;
  const travel = pos.w - SLIDER_THUMB_SIZE.w;
  const clamped = Math.max(0, Math.min(1, percent));
  const thumbX = pos.x + Math.round(clamped * travel);
  ctx.drawImage(sheet, thumb.x, thumb.y, thumb.w, thumb.h, thumbX, pos.y + 1, thumb.w, thumb.h);
}
