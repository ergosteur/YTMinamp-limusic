// The album art window: the playing track's cover in a frame from the skin. Winamp 5's Album Art
// window uses the generic window frame (gen.bmp); most older skins don't have one, so those get
// a frame cut from the equalizer window instead (eqmain.bmp — no EQ window here to use it), its
// title covered by an "ALBUM ART" label. Sprite coordinates: Webamp's skinSprites.ts (GEN,
// EQ_WINDOW) and gen-window.css / equalizer-window.css. Title rows are the unfocused ones, like
// the playlist editor's.

import { drawText } from './marquee.js';

/** @typedef {'gen' | 'eq'} ArtFrame */
/** @typedef {{ x: number, y: number, w: number, h: number }} Rect */

/** Frame thickness around the picture, per frame. */
const INSET = {
	gen: { top: 20, bottom: 14, left: 11, right: 8 },
	eq: { top: 14, bottom: 4, left: 4, right: 4 }
};

const GEN = {
	topLeft: { x: 0, y: 21, w: 25, h: 20 },
	topFill: { x: 104, y: 21, w: 25, h: 20 },
	topRight: { x: 130, y: 21, w: 25, h: 20 },
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
	closeSelected: { x: 0, y: 125, w: 9, h: 9 }
};
/** How much of each end of the EQ titlebar is kept as-is. */
const EQ_TITLE_END = 25;
/** A plain stretch of the EQ titlebar, just inside its left end, tiled across the middle in
 *  place of the "EQUALIZER" title. */
const EQ_TITLE_FILL = { x: 25, y: 149, w: 15, h: 14 };

/** The close button, relative to the frame's top-right corner (same spot on both frames). */
export const ART_CLOSE = { dx: -2 - 9, y: 3, w: 9, h: 9 };

/** The titlebar's height in `frame`: double-click it to float or dock, like the other panels. */
export const artTitleHeight = (/** @type {ArtFrame} */ frame) => INSET[frame].top;
/** The frame's thickness on each side in `frame`. */
export const frameInset = (/** @type {ArtFrame} */ frame) => INSET[frame];

/** Which frame the loaded skin gets. @param {Map<string, unknown>} sprites @returns {ArtFrame} */
export function artFrame(sprites) {
	return sprites.has('gen') ? 'gen' : 'eq';
}

/**
 * The frame size around a square picture, sized to fit one fixed dimension: `{ height }` beside
 * the main window (116), `{ width }` in the stack (275).
 * @param {ArtFrame} frame
 * @param {{ width?: number, height?: number }} fit
 */
export function artSize(frame, fit) {
	const i = INSET[frame];
	const side = fit.width !== undefined ? fit.width - i.left - i.right : (fit.height ?? 0) - i.top - i.bottom;
	return { w: side + i.left + i.right, h: side + i.top + i.bottom };
}

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

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {HTMLImageElement | null} image the cover, loaded; null for none yet
 * @param {Rect} at the whole frame, in canvas pixels
 * @param {boolean} closePressed
 */
export function drawAlbumArt(ctx, sprites, image, at, closePressed) {
	const frame = artFrame(sprites);
	const i = INSET[frame];
	const { x, y, w, h } = at;

	ctx.save();
	ctx.beginPath();
	ctx.rect(x, y, w, h);
	ctx.clip();

	// Picture first: cropped to a centred square, since video thumbnails are 16:9.
	const inner = { x: x + i.left, y: y + i.top, w: w - i.left - i.right, h: h - i.top - i.bottom };
	ctx.fillStyle = '#000000';
	ctx.fillRect(inner.x, inner.y, inner.w, inner.h);
	if (image && image.naturalWidth > 0) {
		const side = Math.min(image.naturalWidth, image.naturalHeight);
		const sx = (image.naturalWidth - side) / 2;
		const sy = (image.naturalHeight - side) / 2;
		ctx.drawImage(image, sx, sy, side, side, inner.x, inner.y, inner.w, inner.h);
	}

	drawFrame(ctx, sprites, at, closePressed, w >= 90 ? 'album art' : 'art', frame === 'gen');
	ctx.restore();
}

/**
 * Just the frame — gen.bmp's, or the one cut from eqmain.bmp — with `label` on its titlebar.
 * The album art window's, and the Open URL dialog's.
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {Rect} at
 * @param {boolean} closePressed
 * @param {string} label
 * @param {boolean} [bareGen] leave gen.bmp's titlebar unlabelled (album art's way)
 */
export function drawFrame(ctx, sprites, at, closePressed, label, bareGen = false) {
	const gen = sprites.get('gen');
	const eq = sprites.get('eqmain');
	const text = sprites.get('text');
	if (artFrame(sprites) === 'gen' && gen) {
		drawGenFrame(ctx, gen, at, closePressed);
		if (!bareGen && text) drawLabel(ctx, text, label, at, 7);
	} else if (eq) {
		drawEqFrame(ctx, eq, at, closePressed);
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
 * gen.bmp: corners at their own size, edges tiled.
 * @param {CanvasRenderingContext2D} ctx @param {ImageBitmap} sheet @param {Rect} at @param {boolean} closePressed
 */
function drawGenFrame(ctx, sheet, { x, y, w, h }, closePressed) {
	const i = INSET.gen;
	for (let tx = x; tx < x + w; tx += GEN.topFill.w) blit(ctx, sheet, GEN.topFill, tx, y);
	blit(ctx, sheet, GEN.topLeft, x, y);
	blit(ctx, sheet, GEN.topRight, x + w - GEN.topRight.w, y);
	if (closePressed) blit(ctx, sheet, GEN.closeSelected, x + w + ART_CLOSE.dx, y + ART_CLOSE.y);

	const sideBottom = y + h - i.bottom - GEN.middleLeftBottom.h;
	for (let ty = y + i.top; ty < sideBottom; ty += GEN.middleLeft.h) {
		blit(ctx, sheet, GEN.middleLeft, x, ty);
		blit(ctx, sheet, GEN.middleRight, x + w - i.right, ty);
	}
	blit(ctx, sheet, GEN.middleLeftBottom, x, sideBottom);
	blit(ctx, sheet, GEN.middleRightBottom, x + w - i.right, sideBottom);

	// The two 125px bottom caps over a tiled fill; narrower than 250, each keeps its outer half.
	const by = y + h - i.bottom;
	for (let tx = x; tx < x + w; tx += GEN.bottomFill.w) blit(ctx, sheet, GEN.bottomFill, tx, by);
	const leftW = Math.min(GEN.bottomLeft.w, Math.ceil(w / 2));
	const rightW = Math.min(GEN.bottomRight.w, w - leftW);
	blit(ctx, sheet, GEN.bottomLeft, x, by, leftW);
	blit(ctx, sheet, GEN.bottomRight, x + w - rightW, by, rightW, GEN.bottomRight.w - rightW);
}

/**
 * eqmain.bmp: the titlebar's two ends kept and its middle tiled, then the background's left,
 * right and bottom edges as a thin border, stretched along their length.
 * @param {CanvasRenderingContext2D} ctx @param {ImageBitmap} sheet @param {Rect} at @param {boolean} closePressed
 */
function drawEqFrame(ctx, sheet, { x, y, w, h }, closePressed) {
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
	for (let tx = x; tx < x + w; tx += EQ_TITLE_FILL.w) blit(ctx, sheet, EQ_TITLE_FILL, tx, y);
	const end = Math.min(EQ_TITLE_END, Math.floor(w / 2));
	blit(ctx, sheet, bar, x, y, end);
	blit(ctx, sheet, bar, x + w - end, y, end, bar.w - end);
	if (closePressed) blit(ctx, sheet, EQ.closeSelected, x + w + ART_CLOSE.dx, y + ART_CLOSE.y);
}
