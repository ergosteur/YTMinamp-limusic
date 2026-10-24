// The mouse on the frame of a window in the skin's generic frame (File info, About, Update, Open
// URL, Save preset, Media Library): a titlebar press becomes a window drag once the mouse moves (so
// a double-click still arrives), the ✕ closes on release over it, and a right-click on the frame
// is the player's main menu, as in Winamp. A resizable
// one (the Media Library) also resizes from its edges, under the ✕: Limusic's ResizeBorders would
// sit on top of it and take its clicks.
import { getCurrentWindow } from '@tauri-apps/api/window';
import { requestMainMenu } from './menu.js';

/** How far in from an edge a press resizes, and from a corner both ways. */
const EDGE = 4;
const CORNER = 10;
const CURSORS = /** @type {const} */ ({
	South: 's-resize',
	West: 'w-resize',
	East: 'e-resize',
	SouthWest: 'sw-resize',
	SouthEast: 'se-resize'
});

/** @typedef {{ top: number, bottom: number, left: number, right: number }} Inset */

/**
 * Whether (x, y) is on the frame of a `w`×`h` window with `inset`, rather than inside it.
 * @param {number} x @param {number} y @param {number} w @param {number} h @param {Inset} inset
 */
export function onFrame(x, y, w, h, inset) {
	return x < inset.left || y < inset.top || x >= w - inset.right || y >= h - inset.bottom;
}

/**
 * A right-click on a frame: the main menu, which the Winamp window shows over this one.
 * @param {MouseEvent} e
 */
export function frameMenu(e) {
	e.preventDefault();
	e.stopPropagation();
	requestMainMenu({ x: e.clientX, y: e.clientY }).catch((err) => console.error('menu request failed', err));
}

/**
 * The edge or corner `e` is on, if any: the sides below the titlebar and the bottom.
 * @param {MouseEvent} e
 * @param {number} titleHeight
 * @returns {keyof typeof CURSORS | null}
 */
function edgeAt(e, titleHeight) {
	const x = e.clientX;
	const y = e.clientY;
	const right = window.innerWidth - 1 - x;
	// Nothing in the titlebar: it drags the window, and its ✕ is small enough to miss.
	if (y < titleHeight) return null;
	const bottom = window.innerHeight - 1 - y;
	const ns = (/** @type {number} */ d) => (bottom < d ? 'South' : '');
	const we = (/** @type {number} */ d) => (x < d ? 'West' : right < d ? 'East' : '');
	// A corner when near two sides, else a single edge.
	const edge = ns(CORNER) && we(CORNER) ? ns(CORNER) + we(CORNER) : ns(EDGE) || we(EDGE);
	return /** @type {keyof typeof CURSORS | null} */ (edge || null);
}

/**
 * @param {HTMLCanvasElement} canvas the frame
 * @param {{
 *   onClose: (e: MouseEvent) => boolean,
 *   inset: () => Inset,
 *   pressed: (down: boolean) => void,
 *   close: () => void,
 *   resizable?: boolean
 * }} o whether `e` is over the ✕; the frame's thickness; the ✕ going down or up (redraw it);
 *   closing the window; whether its edges resize it
 * @returns {() => void} removes the listeners
 */
export function frameMouse(canvas, { onClose, inset, pressed, close, resizable = false }) {
	const titleHeight = () => inset().top;
	let press = /** @type {{ x: number, y: number } | null} */ (null);
	let closeDown = false;
	const onDown = (/** @type {MouseEvent} */ e) => {
		if (e.button !== 0) return;
		if (onClose(e)) {
			closeDown = true;
			pressed(true);
		} else if (resizable && edgeAt(e, titleHeight())) {
			getCurrentWindow().startResizeDragging(/** @type {any} */ (edgeAt(e, titleHeight()))).catch(() => {});
		} else if (e.clientY < titleHeight()) {
			press = { x: e.screenX, y: e.screenY };
		}
	};
	const onMove = (/** @type {MouseEvent} */ e) => {
		if (resizable) {
			const edge = e.target === canvas && !onClose(e) ? edgeAt(e, titleHeight()) : null;
			canvas.style.cursor = edge ? CURSORS[edge] : '';
		}
		if (press && Math.hypot(e.screenX - press.x, e.screenY - press.y) > 3) {
			press = null;
			getCurrentWindow().startDragging();
		}
	};
	const onUp = (/** @type {MouseEvent} */ e) => {
		press = null;
		if (!closeDown) return;
		closeDown = false;
		pressed(false);
		// Released off the button: no close, as in Winamp.
		if (onClose(e)) close();
	};
	const onMenu = (/** @type {MouseEvent} */ e) => {
		if (onFrame(e.clientX, e.clientY, window.innerWidth, window.innerHeight, inset())) frameMenu(e);
	};
	canvas.addEventListener('mousedown', onDown);
	canvas.addEventListener('contextmenu', onMenu);
	window.addEventListener('mousemove', onMove);
	window.addEventListener('mouseup', onUp);
	return () => {
		canvas.removeEventListener('mousedown', onDown);
		canvas.removeEventListener('contextmenu', onMenu);
		window.removeEventListener('mousemove', onMove);
		window.removeEventListener('mouseup', onUp);
	};
}
