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

/** CSS colour strings for all 24 slots, skin first, stock palette for anything missing. */
function palette(colors) {
	return DEFAULT_COLORS.map((d, i) => {
		const c = colors?.[i] ?? d;
		return `rgb(${c[0]},${c[1]},${c[2]})`;
	});
}

/** Dotted background: colour 0, with colour 1 on every other pixel of every other row. */
function drawBackground(ctx, colors) {
	ctx.fillStyle = colors[0];
	ctx.fillRect(VIS_POS.x, VIS_POS.y, VIS_POS.w, VIS_POS.h);
	ctx.fillStyle = colors[1];
	for (let x = 0; x < VIS_POS.w; x += 2) {
		for (let y = 1; y < VIS_POS.h; y += 2) {
			ctx.fillRect(VIS_POS.x + x, VIS_POS.y + y, 1, 1);
		}
	}
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

	ctx.save();
	ctx.beginPath();
	ctx.rect(VIS_POS.x, VIS_POS.y, VIS_POS.w, VIS_POS.h);
	ctx.clip();
	drawBackground(ctx, colors);

	const h = VIS_POS.h;
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
			ctx.fillStyle = colors[2 - PUSH_DOWN + y];
			ctx.fillRect(VIS_POS.x + x, VIS_POS.y + y, 1, 1);
		}
		const peakY = h - (barPeak[x] + 1 - PUSH_DOWN);
		ctx.fillStyle = colors[PEAK_COLOR];
		ctx.fillRect(VIS_POS.x + x, VIS_POS.y + peakY, 1, 1);
	}
	ctx.restore();
}
