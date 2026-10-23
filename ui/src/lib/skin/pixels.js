// Skins are pixel art laid out in exact window pixels, so a skinned window's CSS pixel has to be
// one screen pixel.
import { emit, listen } from '@tauri-apps/api/event';
import { getCurrentWebview } from '@tauri-apps/api/webview';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { resizeWinampPanel } from '$lib/api';
import { logUi } from '$lib/errlog';

/** The zoom that makes one CSS px one window px (see `pinOneToOnePixels`). */
let base = 1;
/** Double size: 2, else 1. */
let scale = 1;

/** Window px per CSS px: what a position inside the page is multiplied by for GTK. */
export const zoomFactor = () => base * scale;

/**
 * Draw this window at `factor` times its pixel size (Winamp's double size). Everything inside
 * keeps its CSS coordinates, so hit-testing doesn't change; the caller sizes the window to match.
 * @param {1 | 2} factor
 */
export async function setScale(factor) {
	scale = factor;
	await getCurrentWebview().setZoom(base * scale);
}

/** Where the Winamp window says whether double size is on, for its other windows to read at once
 *  (localStorage is every window's). */
const DOUBLE_KEY = 'ytminamp-double-size';
const DOUBLE_EVENT = 'winamp-double-size';

/** Double size's factor for window sizes: 2 when it's on. Every Winamp window but MilkDrop's asks
 *  Rust for its size times this, and works in 1x coordinates inside. */
export function doubleFactor() {
	try {
		return localStorage.getItem(DOUBLE_KEY) === '1' ? 2 : 1;
	} catch {
		return 1;
	}
}

/** The Winamp window turned double size on or off: tell the others. @param {boolean} on */
export function announceDoubleSize(on) {
	try {
		localStorage.setItem(DOUBLE_KEY, on ? '1' : '0');
	} catch {
		// The other windows just won't follow.
	}
	emit(DOUBLE_EVENT, on).catch(() => {});
}

/**
 * A floating Winamp window following double size: zoomed once the DPI pin is done (it opened at
 * the doubled size already), then rezoomed and resized whenever it's toggled.
 * @param {Promise<unknown>} pinned `pinOneToOnePixels()`
 * @param {import('$lib/api').WinampPanel} panel
 */
export function followDoubleSize(pinned, panel) {
	const ready = pinned
		.then(() => setScale(/** @type {1 | 2} */ (doubleFactor())))
		.catch((e) => logUi('error', `double size failed: ${e}`));
	return listen(DOUBLE_EVENT, async (e) => {
		await ready;
		const f = e.payload ? 2 : 1;
		if (f === scale) return;
		// The size at 1x: the window's, over the zoom it has now (not CSS's, which may lag a frame).
		const win = getCurrentWindow();
		const [physical, dpr] = await Promise.all([win.innerSize(), win.scaleFactor()]);
		const w = Math.round(physical.width / dpr / scale);
		const h = Math.round(physical.height / dpr / scale);
		await setScale(f);
		await resizeWinampPanel(panel, w * f, h * f);
	});
}

/**
 * A pinch as zoom steps (1 bigger, -1 smaller), one per 15% of pinch. Safari's gesture events, which
 * the macOS build's WebKit sends; Windows' WebView2 sends a pinch as Ctrl+wheel instead, which the
 * zoomable windows already take. Returns the unlisten.
 * @param {(step: 1 | -1, e: Event) => void} onStep
 */
export function onPinch(onStep) {
	let base = 1;
	const start = (/** @type {Event} */ e) => {
		e.preventDefault();
		base = 1;
	};
	const change = (/** @type {Event} */ e) => {
		e.preventDefault();
		const scale = /** @type {{ scale?: number }} */ (/** @type {unknown} */ (e)).scale ?? 1;
		if (scale > base * 1.15) {
			base = scale;
			onStep(1, e);
		} else if (scale < base / 1.15) {
			base = scale;
			onStep(-1, e);
		}
	};
	window.addEventListener('gesturestart', start);
	window.addEventListener('gesturechange', change);
	return () => {
		window.removeEventListener('gesturestart', start);
		window.removeEventListener('gesturechange', change);
	};
}

/**
 * CSS px → screen px for this webview. WebKitGTK scales pages by the desktop's font DPI / text
 * scaling, so a 275px canvas can overflow a 275px window and every hit area drifts. Measure the
 * real ratio and cancel it with the webview zoom (zoom is absolute, hence dividing the level we
 * last set).
 */
export async function pinOneToOnePixels() {
	// Measured at 1x; double size is applied on top afterwards (`setScale`).
	const win = getCurrentWindow();
	let level = 1;
	for (let attempt = 0; attempt < 3; attempt++) {
		const physical = await win.innerSize();
		const dpr = await win.scaleFactor();
		const ratio = physical.width / dpr / window.innerWidth;
		logUi(
			'info',
			`${win.label} zoom attempt=${attempt} level=${level} innerWidth=${window.innerWidth} window=${physical.width}/${dpr} ratio=${ratio.toFixed(4)}`
		);
		if (Math.abs(ratio - 1) < 0.005) break;
		level = level / ratio;
		await getCurrentWebview().setZoom(level);
		await new Promise((r) => requestAnimationFrame(() => r(undefined)));
	}
	base = level;
}
