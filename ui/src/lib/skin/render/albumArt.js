// The album art window: the playing track's cover in a frame from the skin. Winamp 5's Album Art
// window uses the generic window frame (gen.bmp); most older skins don't have one, so those get
// the playlist editor's frame instead (pledit.bmp, its title replaced by the window's own and its
// bottom bar of buttons cut down to a plain edge), or failing that one cut from the equalizer
// window (eqmain.bmp). Sprite coordinates: Webamp's skinSprites.ts (GEN, PLEDIT, EQ_WINDOW) and
// gen-window.css / equalizer-window.css. Titles are in gen.bmp's own letters, lit while the
// window has focus and dim when it doesn't, as in Winamp.

import { drawText } from './marquee.js';
import { isLit } from '../focus.js';
import { PLEDIT } from './playlist.js';

/** @typedef {'gen' | 'pl' | 'eq'} ArtFrame */
/** @typedef {{ x: number, y: number, w: number, h: number }} Rect */

/** Frame thickness around the picture, per frame. */
const INSET = {
	// gen.bmp's right side is 8 px against the left's 11: widened to match, so what's inside sits
	// in the middle (drawGenFrame fills the difference).
	gen: { top: 20, bottom: 14, left: 11, right: 11 },
	// The playlist's left tile, mirrored on the right (its own right tile holds the scrollbar's
	// groove); of its bottom, the plain strip under the buttons.
	pl: { top: 20, bottom: 9, left: 12, right: 12 },
	eq: { top: 14, bottom: 4, left: 4, right: 4 }
};
/** pledit.bmp's side tile height. */
const PL_TILE_H = 29;
/** pledit.bmp's bottom bar height; its title piece's end caps and a plain column between them. */
const PL_BOTTOM_H = 38;
const PL_TITLE_CAP = 4;
const PL_TITLE_PLAIN_X = 5;
/** The bottom-left piece's column (between its first two buttons) stretched along the bottom: its
 *  last rows, under the buttons, are a plain edge in every skin seen. The filler tile isn't: skins
 *  only ever show it on a widened playlist, and some (Musicmatch 9) give it curved ends. */
const PL_BOTTOM_FILL_X = 39;
/** The top-right piece's rows that hold its buttons (close at 3-11), above the groove's start. */
const PL_CORNER_BUTTONS_H = 12;

/** gen.bmp's titlebar pieces: x only, the row is TOP_Y's. */
const GEN_TOP = { left: 0, leftEnd: 26, centerFill: 52, rightEnd: 78, fill: 104, right: 130, w: 25, h: 20 };
/** Titlebar rows, and the A-Z letter rows below them, focused and not. */
const TOP_Y = { focused: 0, unfocused: 21 };
const GEN_TEXT = { focused: 88, unfocused: 96, h: 7, dy: 4, space: 5 };

const GEN = {
	bottomLeft: { x: 0, y: 42, w: 125, h: 14 },
	bottomRight: { x: 0, y: 57, w: 125, h: 14 },
	bottomFill: { x: 127, y: 72, w: 25, h: 14 },
	middleLeft: { x: 127, y: 42, w: 11, h: 29 },
	middleLeftBottom: { x: 158, y: 42, w: 11, h: 24 },
	middleRight: { x: 139, y: 42, w: 8, h: 29 },
	middleRightBottom: { x: 170, y: 42, w: 8, h: 24 },
	closeSelected: { x: 148, y: 42, w: 9, h: 9 }
};

const EQ = {
	background: { x: 0, y: 0, w: 275, h: 116 },
	titleBar: { x: 0, y: 149, w: 275, h: 14 },
	titleBarFocused: { x: 0, y: 134, w: 275, h: 14 },
	closeSelected: { x: 0, y: 125, w: 9, h: 9 }
};
/** How much of each end of the EQ titlebar is kept as-is. */
const EQ_TITLE_END = 25;
/** A plain stretch of the EQ titlebar, just inside its left end, tiled across the middle in
 *  place of the "EQUALIZER" title. */
const EQ_TITLE_FILL = { x: 25, y: 149, w: 15, h: 14 };

/** @typedef {Record<string, { x: number, w: number }>} GenLetters */
/** gen.bmp's letters per sheet, measured once; null where a skin has none to measure. */
const genLetters = /** @type {WeakMap<ImageBitmap, { focused: GenLetters, unfocused: GenLetters } | null>} */ (new WeakMap());

/**
 * gen.bmp's A-Z: each row starts at x 1, every letter its own width, separated by 1px columns of
 * the colour at x 0. Measured from the skin, as Webamp does.
 * @param {ImageBitmap} sheet
 */
function lettersOf(sheet) {
	if (genLetters.has(sheet)) return genLetters.get(sheet) ?? null;
	let result = null;
	try {
		const canvas = document.createElement('canvas');
		canvas.width = sheet.width;
		canvas.height = sheet.height;
		const ctx = canvas.getContext('2d', { willReadFrequently: true });
		if (ctx && sheet.height >= GEN_TEXT.unfocused + GEN_TEXT.h) {
			ctx.drawImage(sheet, 0, 0);
			/** @param {number} y */
			const row = (y) => {
				const px = ctx.getImageData(0, y, sheet.width, 1).data;
				const same = (/** @type {number} */ x) =>
					px[x * 4] === px[0] && px[x * 4 + 1] === px[1] && px[x * 4 + 2] === px[2];
				/** @type {GenLetters} */
				const letters = {};
				let n = 0;
				for (let x = 1; x < sheet.width && n < 26; ) {
					if (same(x)) {
						x++;
						continue;
					}
					const start = x;
					while (x < sheet.width && !same(x)) x++;
					letters[String.fromCharCode(65 + n++)] = { x: start, w: x - start };
				}
				return n === 26 ? letters : null;
			};
			const lit = row(GEN_TEXT.focused);
			const dim = row(GEN_TEXT.unfocused);
			if (lit && dim) result = { focused: lit, unfocused: dim };
		}
	} catch (e) {
		console.error('measuring gen.bmp letters failed', e);
	}
	genLetters.set(sheet, result);
	return result;
}

/** The close button, relative to the frame's top-right corner (same spot on both frames). */
export const ART_CLOSE = { dx: -2 - 9, y: 3, w: 9, h: 9 };

/** Whether `e` is on the close button of a frame `width` wide at the window's top-left. */
export function onCloseButton(/** @type {MouseEvent} */ e, /** @type {number} */ width) {
	const x = width + ART_CLOSE.dx;
	return e.clientX >= x && e.clientX < x + ART_CLOSE.w && e.clientY >= ART_CLOSE.y && e.clientY < ART_CLOSE.y + ART_CLOSE.h;
}

/** The titlebar's height in `frame`: double-click it to float or dock, like the other panels. */
export const artTitleHeight = (/** @type {ArtFrame} */ frame) => INSET[frame].top;
/** The frame's thickness on each side in `frame`. */
export const frameInset = (/** @type {ArtFrame} */ frame) => INSET[frame];

/** Which frame the loaded skin gets. @param {Map<string, unknown>} sprites @returns {ArtFrame} */
export function artFrame(sprites) {
	return sprites.has('gen') ? 'gen' : sprites.has('pledit') ? 'pl' : 'eq';
}

/**
 * The frame size around a square picture, sized to fit one fixed dimension: `{ height }` beside
 * the main window (116), `{ width }` in the stack (275).
 * @param {ArtFrame} frame
 * @param {{ width?: number, height?: number }} fit
 */
export function artSize(frame, fit, caption = false) {
	const i = INSET[frame];
	const cap = caption ? ART_CAPTION_H : 0;
	const side = fit.width !== undefined ? fit.width - i.left - i.right : (fit.height ?? 0) - i.top - i.bottom - cap;
	return { w: side + i.left + i.right, h: side + i.top + i.bottom + cap };
}

/** The album name strip under the picture (the art's right-click menu: Show album name). */
export const ART_CAPTION_H = 14;

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {CanvasImageSource} sheet
 * @param {{x: number, y: number, w: number, h: number}} r
 * @param {number} dx @param {number} dy
 * @param {number} [w] draw only `w` columns
 * @param {number} [sx] starting `sx` columns in
 */
function blit(ctx, sheet, r, dx, dy, w = r.w, sx = 0) {
	ctx.drawImage(sheet, r.x + sx, r.y, w, r.h, dx, dy, w, r.h);
}

/** The cover last scaled, at the size it was scaled to: a frame copies it rather than scaling the
 * full-size picture again. */
let scaled = { image: /** @type {HTMLImageElement | null} */ (null), w: 0, h: 0, canvas: /** @type {HTMLCanvasElement | null} */ (null) };

/**
 * `image` cropped to a centred square (video thumbnails are 16:9) and scaled to w×h.
 * @param {HTMLImageElement} image @param {number} w @param {number} h
 */
function scaledCover(image, w, h) {
	if (scaled.canvas && scaled.image === image && scaled.w === w && scaled.h === h) return scaled.canvas;
	const canvas = scaled.canvas ?? document.createElement('canvas');
	canvas.width = w;
	canvas.height = h;
	const side = Math.min(image.naturalWidth, image.naturalHeight);
	const sx = (image.naturalWidth - side) / 2;
	const sy = (image.naturalHeight - side) / 2;
	/** @type {CanvasRenderingContext2D} */ (canvas.getContext('2d')).drawImage(image, sx, sy, side, side, 0, 0, w, h);
	scaled = { image, w, h, canvas };
	return canvas;
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {HTMLImageElement | null} image the cover, loaded; null for none yet
 * @param {Rect} at the whole frame, in canvas pixels
 * @param {boolean} closePressed
 * @param {{ text: string, pledit: { font?: string, normal?: string, normalBg?: string } } | null} [caption]
 *   the album name to show under the picture (artSize made room for it), or none
 */
export function drawAlbumArt(ctx, sprites, image, at, closePressed, caption = null) {
	const frame = artFrame(sprites);
	const i = INSET[frame];
	const { x, y, w, h } = at;

	ctx.save();
	ctx.beginPath();
	ctx.rect(x, y, w, h);
	ctx.clip();

	// Picture first: cropped to a centred square (see `scaledCover`).
	const cap = caption ? ART_CAPTION_H : 0;
	const inner = { x: x + i.left, y: y + i.top, w: w - i.left - i.right, h: h - i.top - i.bottom - cap };
	ctx.fillStyle = '#000000';
	ctx.fillRect(inner.x, inner.y, inner.w, inner.h);
	if (image && image.naturalWidth > 0 && inner.w > 0 && inner.h > 0) {
		ctx.drawImage(scaledCover(image, inner.w, inner.h), inner.x, inner.y);
	}
	if (caption) {
		// In the playlist's font and colours: a canvas font, so any script shows (text.bmp is A-Z).
		const strip = { x: inner.x, y: inner.y + inner.h, w: inner.w, h: cap };
		ctx.fillStyle = caption.pledit.normalBg ?? '#000000';
		ctx.fillRect(strip.x, strip.y, strip.w, strip.h);
		ctx.save();
		ctx.beginPath();
		ctx.rect(strip.x, strip.y, strip.w, strip.h);
		ctx.clip();
		ctx.font = `11px ${caption.pledit.font ? `"${caption.pledit.font}", ` : ''}Arial, sans-serif`;
		ctx.fillStyle = caption.pledit.normal ?? '#00ff00';
		ctx.textBaseline = 'middle';
		const fits = ctx.measureText(caption.text).width <= strip.w - 4;
		ctx.textAlign = fits ? 'center' : 'left';
		ctx.fillText(caption.text, fits ? strip.x + strip.w / 2 : strip.x + 2, strip.y + strip.h / 2 + 1);
		ctx.restore();
	}

	drawFrame(ctx, sprites, at, closePressed, w >= 90 ? 'album art' : 'art', isLit('art'));
	ctx.restore();
}

/**
 * Just the frame — gen.bmp's, else the playlist's or the EQ's (see `artFrame`) — with `label` on its titlebar.
 * Album art's, lyrics', MilkDrop's, the Open URL dialog's.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {Rect} at
 * @param {boolean} closePressed
 * @param {string} label
 * @param {boolean} lit the active window's titlebar (focus.js), else the dimmed one
 */
export function drawFrame(ctx, sprites, at, closePressed, label, lit) {
	const gen = sprites.get('gen');
	const pl = sprites.get('pledit');
	const eq = sprites.get('eqmain');
	const text = sprites.get('text');
	const frame = artFrame(sprites);
	if (frame === 'gen' && gen) {
		const letters = lettersOf(gen);
		drawGenFrame(ctx, gen, at, closePressed, letters ? label : '', lit);
		// A gen.bmp without its letters: the title in text.bmp instead.
		if (!letters && text) drawLabel(ctx, text, label, at, 7);
	} else if (frame === 'pl' && pl) {
		drawPlFrame(ctx, pl, text, at, closePressed, label, lit);
	} else if (eq) {
		drawEqFrame(ctx, eq, at, closePressed, lit);
		if (text) drawLabel(ctx, text, label, at, 4);
	}
}

/**
 * A titlebar label in text.bmp, centred (its glyphs carry their own background, so it reads on
 * any bar). @param {CanvasRenderingContext2D} ctx @param {ImageBitmap} text @param {string} label
 * @param {Rect} at @param {number} dy
 */
function drawLabel(ctx, text, label, { x, y, w }, dy) {
	drawText(ctx, text, label, x + Math.floor((w - label.length * 5) / 2), y + dy);
}

/**
 * How wide `text` is in gen.bmp's letters; 0 if the skin has none.
 * @param {ImageBitmap} sheet gen.bmp @param {string} text
 */
export function genTextWidth(sheet, text) {
	const letters = lettersOf(sheet)?.focused;
	if (!letters) return 0;
	return [...text.toUpperCase()].reduce((sum, c) => sum + (letters[c]?.w ?? GEN_TEXT.space), 0);
}

/**
 * `text` in gen.bmp's titlebar letters, lit or dim, at a titlebar's top-left (x, y): the letters
 * sit GEN_TEXT.dy down, on its stripe. A-Z only; anything else is a space.
 * @param {CanvasRenderingContext2D} ctx @param {ImageBitmap} sheet gen.bmp @param {string} text
 * @param {number} x @param {number} y @param {boolean} lit
 */
export function drawGenText(ctx, sheet, text, x, y, lit) {
	const state = lit ? 'focused' : 'unfocused';
	const letters = lettersOf(sheet)?.[state];
	if (!letters) return;
	for (const c of text.toUpperCase()) {
		const l = letters[c];
		if (l) ctx.drawImage(sheet, l.x, GEN_TEXT[state], l.w, GEN_TEXT.h, x, y + GEN_TEXT.dy, l.w, GEN_TEXT.h);
		x += l?.w ?? GEN_TEXT.space;
	}
}

/**
 * gen.bmp: corners at their own size, edges tiled, and the title (in its own letters) centred on
 * the titlebar between its end caps.
 * @param {CanvasRenderingContext2D} ctx @param {ImageBitmap} sheet @param {Rect} at @param {boolean} closePressed
 * @param {string} title '' for none
 * @param {boolean} lit
 */
function drawGenFrame(ctx, sheet, { x, y, w, h }, closePressed, title, lit) {
	const i = INSET.gen;
	const state = lit ? 'focused' : 'unfocused';
	const piece = (/** @type {number} */ px) => ({ x: px, y: TOP_Y[state], w: GEN_TOP.w, h: GEN_TOP.h });
	for (let tx = x; tx < x + w; tx += GEN_TOP.w) blit(ctx, sheet, piece(GEN_TOP.fill), tx, y);
	const textW = genTextWidth(sheet, title);
	// Only with room for both corners and both end caps.
	if (textW && textW + 4 * GEN_TOP.w <= w) {
		const tx = x + Math.floor((w - textW) / 2);
		for (let cx = tx; cx < tx + textW; cx += GEN_TOP.w) blit(ctx, sheet, piece(GEN_TOP.centerFill), cx, y, Math.min(GEN_TOP.w, tx + textW - cx));
		blit(ctx, sheet, piece(GEN_TOP.leftEnd), tx - GEN_TOP.w, y);
		blit(ctx, sheet, piece(GEN_TOP.rightEnd), tx + textW, y);
		drawGenText(ctx, sheet, title, tx, y, lit);
	}
	blit(ctx, sheet, piece(GEN_TOP.left), x, y);
	blit(ctx, sheet, piece(GEN_TOP.right), x + w - GEN_TOP.w, y);
	if (closePressed) blit(ctx, sheet, GEN.closeSelected, x + w + ART_CLOSE.dx, y + ART_CLOSE.y);

	// The right side's own pieces at the edge, their inner column stretched over the rest of the
	// (widened) inset.
	const rightX = x + w - GEN.middleRight.w;
	const extra = i.right - GEN.middleRight.w;
	const right = (/** @type {Rect} */ r, /** @type {number} */ ty) => {
		blit(ctx, sheet, r, rightX, ty);
		ctx.drawImage(sheet, r.x, r.y, 1, r.h, rightX - extra, ty, extra, r.h);
	};
	const sideBottom = y + h - i.bottom - GEN.middleLeftBottom.h;
	for (let ty = y + i.top; ty < sideBottom; ty += GEN.middleLeft.h) {
		blit(ctx, sheet, GEN.middleLeft, x, ty);
		right(GEN.middleRight, ty);
	}
	blit(ctx, sheet, GEN.middleLeftBottom, x, sideBottom);
	right(GEN.middleRightBottom, sideBottom);

	// The two 125px bottom caps over a tiled fill; narrower than 250, each keeps its outer half.
	const by = y + h - i.bottom;
	for (let tx = x; tx < x + w; tx += GEN.bottomFill.w) blit(ctx, sheet, GEN.bottomFill, tx, by);
	const leftW = Math.min(GEN.bottomLeft.w, Math.ceil(w / 2));
	const rightW = Math.min(GEN.bottomRight.w, w - leftW);
	blit(ctx, sheet, GEN.bottomLeft, x, by, leftW);
	blit(ctx, sheet, GEN.bottomRight, x + w - rightW, by, rightW, GEN.bottomRight.w - rightW);
}

/**
 * pledit.bmp, as a plain window: the playlist's top bar (corners, tiles, and its title piece's
 * plain middle under `label` in text.bmp), its left side tile and bottom-left corner, mirrored for
 * the right (whose own tile holds the scrollbar's groove, and corner the resize grip), and of its
 * bottom bar only the plain strip along the very bottom, no buttons.
 * @param {CanvasRenderingContext2D} ctx @param {ImageBitmap} sheet @param {ImageBitmap | undefined} text
 * @param {Rect} at @param {boolean} closePressed @param {string} label @param {boolean} lit
 */
function drawPlFrame(ctx, sheet, text, { x, y, w, h }, closePressed, label, lit) {
	const i = INSET.pl;
	const top = (/** @type {Rect} */ r) => (lit ? { ...r, y: 0 } : r);
	ctx.save();
	ctx.beginPath();
	ctx.rect(x, y, w, h);
	ctx.clip();

	for (let tx = x + PLEDIT.topLeft.w; tx < x + w - PLEDIT.topRight.w; tx += PLEDIT.topTile.w) {
		blit(ctx, sheet, top(PLEDIT.topTile), tx, y);
	}
	const labelW = label.length * 5;
	// Only with room for both corners and the title piece's caps.
	if (text && labelW + 2 * (PLEDIT.topLeft.w + PL_TITLE_CAP + 3) <= w) {
		const t = top(PLEDIT.title);
		const lx = x + Math.floor((w - labelW) / 2);
		ctx.drawImage(sheet, t.x + PL_TITLE_PLAIN_X, t.y, 1, t.h, lx - 3, y, labelW + 6, t.h);
		ctx.drawImage(sheet, t.x, t.y, PL_TITLE_CAP, t.h, lx - 3 - PL_TITLE_CAP, y, PL_TITLE_CAP, t.h);
		ctx.drawImage(sheet, t.x + t.w - PL_TITLE_CAP, t.y, PL_TITLE_CAP, t.h, lx + labelW + 3, y, PL_TITLE_CAP, t.h);
		drawText(ctx, text, label, lx, y + 7);
	}

	// The bottom bar's last rows: one plain column stretched along, and the corner as wide as the
	// side (any wider reaches under the buttons and their labels).
	const by = y + h - i.bottom;
	const row = PL_BOTTOM_H - i.bottom;
	const bl = PLEDIT.bottomLeft;
	ctx.drawImage(sheet, bl.x + PL_BOTTOM_FILL_X, bl.y + row, 1, i.bottom, x, by, w, i.bottom);
	/** The left side and its corners; drawn again mirrored for the right. */
	const leftEdge = (/** @type {number} */ ex) => {
		blit(ctx, sheet, top(PLEDIT.topLeft), ex, y);
		for (let ty = y + i.top; ty < by; ty += PL_TILE_H) blit(ctx, sheet, PLEDIT.leftTile, ex, ty);
		ctx.drawImage(sheet, bl.x, bl.y + row, i.left, i.bottom, ex, by, i.left, i.bottom);
	};
	leftEdge(x);
	ctx.save();
	ctx.translate(2 * x + w, 0);
	ctx.scale(-1, 1);
	leftEdge(x);
	ctx.restore();
	// The real top-right corner's buttons: its rows above the side, where the groove begins.
	const tr = top(PLEDIT.topRight);
	ctx.drawImage(sheet, tr.x, tr.y, tr.w, PL_CORNER_BUTTONS_H, x + w - tr.w, y, tr.w, PL_CORNER_BUTTONS_H);
	if (closePressed) blit(ctx, sheet, PLEDIT.closeSelected, x + w + ART_CLOSE.dx, y + ART_CLOSE.y);
	ctx.restore();
}

/**
 * eqmain.bmp: the titlebar's two ends kept and its middle tiled, then the background's left,
 * right and bottom edges as a thin border, stretched along their length.
 * @param {CanvasRenderingContext2D} ctx @param {ImageBitmap} sheet @param {Rect} at @param {boolean} closePressed
 * @param {boolean} lit
 */
function drawEqFrame(ctx, sheet, { x, y, w, h }, closePressed, lit) {
	const i = INSET.eq;
	const bg = EQ.background;
	const bar = EQ.titleBar;

	// Edges: from just under the background's titlebar down, at the frame's thickness.
	const edgeTop = bar.h;
	const edgeH = bg.h - edgeTop - i.bottom;
	ctx.drawImage(sheet, bg.x, bg.y + edgeTop, i.left, edgeH, x, y + i.top, i.left, h - i.top - i.bottom);
	ctx.drawImage(sheet, bg.x + bg.w - i.right, bg.y + edgeTop, i.right, edgeH, x + w - i.right, y + i.top, i.right, h - i.top - i.bottom);
	// Bottom: corners kept, middle stretched.
	const by = y + h - i.bottom;
	const sy = bg.y + bg.h - i.bottom;
	ctx.drawImage(sheet, bg.x, sy, i.left, i.bottom, x, by, i.left, i.bottom);
	ctx.drawImage(sheet, bg.x + bg.w - i.right, sy, i.right, i.bottom, x + w - i.right, by, i.right, i.bottom);
	ctx.drawImage(sheet, bg.x + i.left, sy, bg.w - i.left - i.right, i.bottom, x + i.left, by, w - i.left - i.right, i.bottom);

	// Titlebar: a plain strip tiled across, then its two ends over that.
	const title = lit ? EQ.titleBarFocused : bar;
	const fill = { ...EQ_TITLE_FILL, y: title.y };
	for (let tx = x; tx < x + w; tx += fill.w) blit(ctx, sheet, fill, tx, y);
	const end = Math.min(EQ_TITLE_END, Math.floor(w / 2));
	blit(ctx, sheet, title, x, y, end);
	blit(ctx, sheet, title, x + w - end, y, end, title.w - end);
	if (closePressed) blit(ctx, sheet, EQ.closeSelected, x + w + ART_CLOSE.dx, y + ART_CLOSE.y);
}
