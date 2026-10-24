// Readable colours from a skin's own. A skin's palette can put text on a background it barely shows
// against (grey on grey, a selection colour close to the window's), which a 9 px playlist gets away
// with and a page of Limusic's doesn't. Such a colour is moved toward black or white, whichever
// its background leaves room for, just far enough to read; one that already reads is kept as is.

/** @param {string} hex `#rrggbb` @returns {[number, number, number]} */
const rgb = (hex) => /** @type {[number, number, number]} */ ([1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)));

/** @param {number[]} c @returns {string} `#rrggbb` */
const toHex = (c) => `#${c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')}`;

/**
 * `a` mixed into `b`, `t` of the way from `b` (0) to `a` (1).
 * @param {string} a @param {number} t @param {string} b @returns {string}
 */
export function mixHex(a, t, b) {
	const [x, y] = [rgb(a), rgb(b)];
	return toHex(x.map((v, i) => y[i] + (v - y[i]) * t));
}

/** WCAG relative luminance, 0..1. @param {string} hex */
export function luminance(hex) {
	const [r, g, b] = rgb(hex).map((v) => {
		const c = v / 255;
		return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio, 1..21. @param {string} a @param {string} b */
export function contrast(a, b) {
	const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
	return (x + 0.05) / (y + 0.05);
}

/**
 * `fg`, or the nearest colour toward black or white that reads at `min`:1 on each of `bgs`.
 * @param {string} fg @param {string[]} bgs @param {number} min 4.5 for text, 3 for large text
 * @returns {string}
 */
export function readable(fg, bgs, min) {
	const reads = (/** @type {string} */ c) => bgs.every((bg) => contrast(c, bg) >= min);
	if (reads(fg)) return fg;
	// White on dark backgrounds, black on light ones.
	const meanBg = bgs.reduce((sum, bg) => sum + luminance(bg), 0) / bgs.length;
	const end = meanBg < 0.18 ? '#ffffff' : '#000000';
	for (let t = 0.1; t < 1; t += 0.1) {
		const c = mixHex(end, t, fg);
		if (reads(c)) return c;
	}
	return end;
}
