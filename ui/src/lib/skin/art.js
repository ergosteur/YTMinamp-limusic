// The playing track's cover as a loaded image, for the album art window to draw each frame. One
// at a time: a track change starts the next load and keeps showing the old cover until it lands.
import { thumb } from '$lib/thumb';

/** The stacked window draws it 256px across; 544 is a size YouTube publishes. */
const PX = 544;

/** @type {string | undefined} */
let wanted;
/** @type {HTMLImageElement | null} */
let shown = null;

/**
 * The cover for `url` (a track's `thumbnail`), or the previous one while it loads.
 * @param {string | undefined | null} url
 */
export function coverFor(url) {
	if (url === wanted) return shown;
	wanted = url ?? undefined;
	if (!url) {
		shown = null;
		return null;
	}
	load(thumb(url, PX) ?? url, url);
	return shown;
}

/** @param {string} src @param {string} original */
function load(src, original) {
	const img = new Image();
	img.decoding = 'async';
	img.onload = () => {
		if (wanted !== original) return; // a newer track took over meanwhile
		// i.ytimg answers a size it lacks with a 120x90 grey picture (see thumb.ts): fall back.
		if (img.naturalWidth === 120 && img.naturalHeight === 90 && src !== original) {
			load(original, original);
			return;
		}
		shown = img;
	};
	img.onerror = () => {
		if (wanted !== original) return;
		if (src !== original) load(original, original);
		// No cover at all: none shown, rather than the last track's.
		else shown = null;
	};
	img.src = src;
}
