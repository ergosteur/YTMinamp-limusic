// Skins are pixel art laid out in exact window pixels, so a skinned window's CSS pixel has to be
// one screen pixel.
import { getCurrentWebview } from '@tauri-apps/api/webview';
import { getCurrentWindow } from '@tauri-apps/api/window';
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
