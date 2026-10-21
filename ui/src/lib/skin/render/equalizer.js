// The equalizer window, drawn from eqmain.bmp: ON/AUTO, presets, preamp and ten bands, and the
// response curve. It looks and moves like Winamp's but changes nothing you hear (there's no EQ
// filter in the player yet), like the balance slider. Coordinates: Webamp's skinSprites.ts
// EQMAIN, equalizer-window.css and EqualizerWindow/Band.tsx + EqGraph.tsx.

export const EQ_W = 275;
export const EQ_H = 116;

const SPRITES = {
	background: { x: 0, y: 0, w: 275, h: 116 },
	titleBar: { x: 0, y: 149, w: 275, h: 14 },
	closeActive: { x: 0, y: 125, w: 9, h: 9 },
	thumb: { x: 0, y: 164, w: 11, h: 11 },
	thumbSelected: { x: 0, y: 176, w: 11, h: 11 },
	on: { x: 10, y: 119, w: 26, h: 12 },
	onDepressed: { x: 128, y: 119, w: 26, h: 12 },
	onSelected: { x: 69, y: 119, w: 26, h: 12 },
	onSelectedDepressed: { x: 187, y: 119, w: 26, h: 12 },
	auto: { x: 36, y: 119, w: 32, h: 12 },
	autoDepressed: { x: 154, y: 119, w: 32, h: 12 },
	autoSelected: { x: 95, y: 119, w: 32, h: 12 },
	autoSelectedDepressed: { x: 213, y: 119, w: 32, h: 12 },
	presets: { x: 224, y: 164, w: 44, h: 12 },
	presetsSelected: { x: 224, y: 176, w: 44, h: 12 },
	graph: { x: 0, y: 294, w: 113, h: 19 },
	/** One pixel wide, a colour per graph row. */
	graphColors: { x: 115, y: 294, w: 1, h: 19 },
	preampLine: { x: 0, y: 314, w: 113, h: 1 }
};

/** Where things sit in the window. */
export const EQ_LAYOUT = {
	close: { x: 264, y: 3, w: 9, h: 9 },
	on: { x: 14, y: 18, w: 26, h: 12 },
	auto: { x: 40, y: 18, w: 32, h: 12 },
	presets: { x: 217, y: 18, w: 44, h: 12 },
	graph: { x: 86, y: 17 },
	preamp: { x: 21, y: 38 },
	/** Band n is at x = firstBand + n * bandStep. */
	firstBand: 78,
	bandStep: 18,
	sliderTop: 38,
	slider: { w: 14, h: 63 },
	/** The thumb's travel: the 62px track less its 11px height. */
	travel: 51
};

export const EQ_BANDS = ['60', '170', '310', '600', '1K', '3K', '6K', '12K', '14K', '16K'];

/** Winamp's built-in presets (Webamp's presets/builtin.json, 1-64 rescaled to 0-100): name,
 *  preamp, ten bands. */
export const EQ_PRESETS = /** @type {[string, number, number[]][]} */ ([
	['Classical', 51, [51, 51, 51, 51, 51, 51, 30, 30, 30, 24]],
	['Club', 51, [51, 51, 59, 65, 65, 65, 59, 51, 51, 51]],
	['Dance', 51, [75, 68, 56, 49, 49, 33, 30, 30, 49, 49]],
	['Laptop speakers/headphones', 51, [62, 78, 63, 40, 43, 54, 62, 75, 83, 87]],
	['Large hall', 51, [76, 76, 65, 65, 51, 37, 37, 37, 51, 51]],
	['Party', 51, [68, 68, 51, 51, 51, 51, 51, 51, 68, 68]],
	['Pop', 51, [44, 62, 68, 70, 63, 46, 43, 43, 44, 44]],
	['Reggae', 51, [51, 51, 48, 33, 51, 67, 67, 51, 51, 51]],
	['Rock', 51, [70, 62, 35, 29, 40, 60, 73, 78, 78, 78]],
	['Soft', 51, [62, 54, 46, 43, 46, 60, 71, 75, 78, 81]],
	['Ska', 51, [43, 37, 38, 48, 60, 65, 73, 75, 78, 75]],
	['Full Bass', 51, [75, 75, 75, 65, 54, 38, 27, 22, 21, 21]],
	['Soft Rock', 51, [60, 60, 56, 48, 38, 35, 40, 48, 57, 73]],
	['Full Treble', 51, [24, 24, 24, 38, 57, 78, 90, 90, 90, 94]],
	['Full Bass & Treble', 51, [68, 65, 51, 30, 37, 54, 71, 78, 81, 81]],
	['Live', 51, [37, 51, 60, 63, 65, 65, 60, 57, 57, 56]],
	['Techno', 51, [70, 65, 51, 35, 37, 51, 70, 75, 75, 73]]
]);

/**
 * @typedef {{ on: boolean, auto: boolean, preamp: number, bands: number[],
 *   dragging: 'preamp' | number | null, pressed: string | null }} EqState
 */

/** @param {{x: number, y: number, w: number, h: number}} r @param {number} x @param {number} y */
const inside = (r, x, y) => x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h;

/** The slider column at x: 'preamp', a band index, or null. @param {number} x */
function sliderAt(x) {
	const L = EQ_LAYOUT;
	if (x >= L.preamp.x && x < L.preamp.x + L.slider.w) return 'preamp';
	const i = Math.floor((x - L.firstBand) / L.bandStep);
	if (i >= 0 && i < 10 && x - (L.firstBand + i * L.bandStep) < L.slider.w) return i;
	return null;
}

/**
 * What's under window-relative (x, y).
 * @param {number} x @param {number} y
 * @returns {'close' | 'on' | 'auto' | 'presets' | 'preamp' | number | 'title' | null}
 */
export function eqHit(x, y) {
	const L = EQ_LAYOUT;
	if (inside(L.close, x, y)) return 'close';
	if (y < 14) return 'title';
	if (inside(L.on, x, y)) return 'on';
	if (inside(L.auto, x, y)) return 'auto';
	if (inside(L.presets, x, y)) return 'presets';
	if (y >= L.sliderTop && y < L.sliderTop + L.slider.h) return sliderAt(x);
	return null;
}

/** A slider's value (0-100, top = 100) for a pointer at window-relative y, thumb centred on it.
 * @param {number} y */
export function eqValueAt(y) {
	const t = (y - EQ_LAYOUT.sliderTop - 6) / EQ_LAYOUT.travel;
	return Math.round((1 - Math.max(0, Math.min(1, t))) * 100);
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {Map<string, ImageBitmap>} sprites
 * @param {EqState} eq
 * @param {number} oy where the window starts in the canvas
 */
export function drawEqualizer(ctx, sprites, eq, oy) {
	const sheet = sprites.get('eqmain');
	if (!sheet) return;
	const S = SPRITES;
	const L = EQ_LAYOUT;
	/** @param {{x: number, y: number, w: number, h: number}} r @param {number} x @param {number} y */
	const blit = (r, x, y) => ctx.drawImage(sheet, r.x, r.y, r.w, r.h, x, oy + y, r.w, r.h);

	blit(S.background, 0, 0);
	blit(S.titleBar, 0, 0);
	if (eq.pressed === 'close') blit(S.closeActive, L.close.x, L.close.y);

	const on = eq.pressed === 'on' ? (eq.on ? S.onSelectedDepressed : S.onDepressed) : eq.on ? S.onSelected : S.on;
	blit(on, L.on.x, L.on.y);
	const auto =
		eq.pressed === 'auto' ? (eq.auto ? S.autoSelectedDepressed : S.autoDepressed) : eq.auto ? S.autoSelected : S.auto;
	blit(auto, L.auto.x, L.auto.y);
	blit(eq.pressed === 'presets' ? S.presetsSelected : S.presets, L.presets.x, L.presets.y);

	/** @param {number} x @param {number} value @param {boolean} dragging */
	const slider = (x, value, dragging) => {
		// The track's own picture changes with the value: 28 frames, 14 to a row (Band.tsx).
		const n = Math.round((value / 100) * 27);
		const bg = { x: 13 + (n % 14) * 15, y: 164 + Math.floor(n / 14) * 65, w: L.slider.w, h: L.slider.h };
		blit(bg, x, L.sliderTop);
		const thumbY = L.sliderTop + Math.round((1 - value / 100) * L.travel);
		blit(dragging ? S.thumbSelected : S.thumb, x + 1, thumbY);
	};
	slider(L.preamp.x, eq.preamp, eq.dragging === 'preamp');
	eq.bands.forEach((v, i) => slider(L.firstBand + i * L.bandStep, v, eq.dragging === i));

	drawGraph(ctx, sheet, eq, L.graph.x, oy + L.graph.y);
}

/**
 * The response curve (EqGraph.tsx): the preamp line, then a natural cubic spline through the
 * bands, each pixel coloured from the skin's colour strip at its height.
 * @param {CanvasRenderingContext2D} ctx @param {ImageBitmap} sheet @param {EqState} eq
 * @param {number} gx @param {number} gy
 */
function drawGraph(ctx, sheet, eq, gx, gy) {
	const S = SPRITES;
	const H = S.graph.h;
	ctx.drawImage(sheet, S.graph.x, S.graph.y, S.graph.w, H, gx, gy, S.graph.w, H);
	const preampY = Math.round((eq.preamp / 100) * (H - 1));
	ctx.drawImage(sheet, S.preampLine.x, S.preampLine.y, S.preampLine.w, 1, gx, gy + preampY, S.preampLine.w, 1);

	const xs = eq.bands.map((_, i) => i * 12);
	const ys = eq.bands.map((v) => ((100 - v) / 100) * (H - 1));
	const curve = spline(xs, ys);
	let last = Math.round(ys[0]);
	for (let x = 0; x <= xs[xs.length - 1]; x++) {
		const y = Math.max(0, Math.min(H - 1, Math.round(curve(x))));
		const top = Math.min(y, last);
		const h = 1 + Math.abs(last - y);
		// Colour by height: copy the colour strip's own pixels for these rows.
		ctx.drawImage(sheet, S.graphColors.x, S.graphColors.y + top, 1, h, gx + 2 + x, gy + top, 1, h);
		last = y;
	}
}

/**
 * Natural cubic spline through (xs, ys), xs increasing.
 * @param {number[]} xs @param {number[]} ys
 * @returns {(x: number) => number}
 */
function spline(xs, ys) {
	const n = xs.length - 1;
	const h = xs.slice(1).map((x, i) => x - xs[i]);
	const alpha = [0];
	for (let i = 1; i < n; i++) {
		alpha.push((3 / h[i]) * (ys[i + 1] - ys[i]) - (3 / h[i - 1]) * (ys[i] - ys[i - 1]));
	}
	const l = [1];
	const mu = [0];
	const z = [0];
	for (let i = 1; i < n; i++) {
		l.push(2 * (xs[i + 1] - xs[i - 1]) - h[i - 1] * mu[i - 1]);
		mu.push(h[i] / l[i]);
		z.push((alpha[i] - h[i - 1] * z[i - 1]) / l[i]);
	}
	const c = new Array(n + 1).fill(0);
	const b = new Array(n).fill(0);
	const d = new Array(n).fill(0);
	for (let j = n - 1; j >= 0; j--) {
		c[j] = (j > 0 ? z[j] : 0) - mu[j] * c[j + 1];
		b[j] = (ys[j + 1] - ys[j]) / h[j] - (h[j] * (c[j + 1] + 2 * c[j])) / 3;
		d[j] = (c[j + 1] - c[j]) / (3 * h[j]);
	}
	return (x) => {
		const j = Math.max(0, Math.min(n - 1, Math.floor((x - xs[0]) / h[0])));
		const t = x - xs[j];
		return ys[j] + b[j] * t + c[j] * t * t + d[j] * t * t * t;
	};
}
