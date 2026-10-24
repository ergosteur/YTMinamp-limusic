// The main window's spectrum analyzer, drawn per frame from the latest 75 columns that
// src-tauri/src/viz.rs emits. Bar grouping, falloff, peak hold and colouring are a port of
// Webamp's BarPaintHandler (VisPainter.ts) in its default Winamp configuration: "wide" bands
// (3px bars, 1px gaps), bar falloff 12, peak falloff 1.1, peaks on. The typed arrays and their
// truncating assignments are deliberate — they're what makes the peaks behave like Winamp's.

import { VIS_POS } from './sprites.js';

const MAX_HEIGHT = 15;
const FALLOFF = 12;
const PEAK_FALLOFF = 1.1;
/** Winamp draws the full-size analyzer two rows lower than its 16px box. */
const PUSH_DOWN = 2;
const PEAK_COLOR = 23;

const saPeaks = new Int16Array(76);
const saData2 = new Float32Array(76);
const saData = new Int16Array(76);
const saFalloff = new Float32Array(76);
const barPeak = new Int16Array(76);
/** 75 columns plus the zero Webamp's 76-long buffer carries, read by the last band. */
const sample = new Float32Array(76);

/** Winamp's stock viscolor.txt, for skins that ship none (or too few lines). */
const DEFAULT_COLORS = [
	[0, 0, 0], [24, 33, 41], [239, 49, 16], [206, 41, 16], [214, 90, 0], [214, 102, 0],
	[214, 115, 0], [198, 123, 8], [222, 165, 24], [214, 181, 33], [189, 222, 41], [148, 222, 33],
	[41, 206, 16], [50, 190, 16], [57, 181, 16], [49, 156, 8], [41, 148, 0], [24, 132, 8],
	[255, 255, 255], [214, 214, 222], [181, 189, 189], [160, 170, 175], [148, 156, 165],
	[150, 150, 150]
];

/** The 24 slots as RGBA pixels, skin first, stock palette for anything missing; kept for the
 * skin's palette last asked for, so a frame makes none. */
let paletteFor = /** @type {unknown} */ (undefined);
const pixels = new Uint32Array(24);
function palette(colors) {
	if (colors === paletteFor) return pixels;
	paletteFor = colors;
	const bytes = new Uint8Array(pixels.buffer);
	DEFAULT_COLORS.forEach((d, i) => {
		const c = colors?.[i] ?? d;
		bytes.set([c[0], c[1], c[2], 255], i * 4);
	});
	return pixels;
}

/** The analyzer box, drawn a pixel at a time into `image` and put on the canvas in one go. */
let box = /** @type {HTMLCanvasElement | null} */ (null);
let image = /** @type {ImageData | null} */ (null);

/**
 * The analyzer changes next frame: there's sound, or bars and peaks are still falling. Otherwise
 * every frame of silence draws the same thing.
 * @param {ArrayLike<number> | null} columns as for `drawAnalyzer`
 */
export function analyzerMoving(columns) {
	if (columns) for (let x = 0; x < 75; x++) if (columns[x] > 0) return true;
	for (let x = 0; x < 75; x++) if (saFalloff[x] > 0 || saPeaks[x] > 0) return true;
	return false;
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {[number, number, number][] | null} skinColors the skin's viscolor.txt
 * @param {ArrayLike<number> | null} columns latest 75 analyzer columns, or null for silence
 */
export function drawAnalyzer(ctx, skinColors, columns) {
	const colors = palette(skinColors);
	sample.fill(0);
	if (columns) sample.set(Array.prototype.slice.call(columns, 0, 75));

	const { w, h } = VIS_POS;
	if (!box || !image) {
		box = document.createElement('canvas');
		box.width = w;
		box.height = h;
		image = new ImageData(w, h);
	}
	const px = new Uint32Array(image.data.buffer);
	// Dotted background: colour 0, with colour 1 on every other pixel of every other row.
	for (let y = 0; y < h; y++) {
		for (let x = 0; x < w; x++) px[y * w + x] = y % 2 === 1 && x % 2 === 0 ? colors[1] : colors[0];
	}
	const put = (/** @type {number} */ x, /** @type {number} */ y, /** @type {number} */ c) => {
		if (y >= 0 && y < h) px[y * w + x] = c;
	};

	for (let x = 0; x < 75; x++) {
		const chunk = x & ~3;
		saData[x] = (sample[chunk] + sample[chunk + 1] + sample[chunk + 2] + sample[chunk + 3]) / 4;
		if (saData[x] >= MAX_HEIGHT) saData[x] = MAX_HEIGHT;
		if (saPeaks[x] >= MAX_HEIGHT * 256) saPeaks[x] = MAX_HEIGHT * 256;

		saFalloff[x] -= FALLOFF / 16.0;
		if (saFalloff[x] <= saData[x]) saFalloff[x] = saData[x];

		if (saPeaks[x] <= Math.round(saFalloff[x] * 256)) {
			saPeaks[x] = saFalloff[x] * 256;
			saData2[x] = 3.0;
		}
		barPeak[x] = saPeaks[x] / 256;
		saPeaks[x] -= Math.round(saData2[x]);
		saData2[x] *= PEAK_FALLOFF;
		if (saPeaks[x] <= 0) saPeaks[x] = 0;
		if (Math.round(barPeak[x]) < 1) barPeak[x] = -3;

		// The fourth column of each band is the 1px gap.
		if (x === chunk + 3) continue;

		const barHeight = Math.round(saFalloff[x]) - PUSH_DOWN;
		for (let y = h - barHeight; y < h; y++) {
			// Row y takes colour y: viscolor 2..17 is the gradient, shifted by PUSH_DOWN.
			put(x, y, colors[2 - PUSH_DOWN + y]);
		}
		put(x, h - (barPeak[x] + 1 - PUSH_DOWN), colors[PEAK_COLOR]);
	}
	/** @type {CanvasRenderingContext2D} */ (box.getContext('2d')).putImageData(image, 0, 0);
	ctx.drawImage(box, VIS_POS.x, VIS_POS.y);
}
